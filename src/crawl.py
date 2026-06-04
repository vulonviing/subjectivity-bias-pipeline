"""Step: crawl — collect article URLs from RSS feeds, fetch HTML, and extract structured articles.

Targets:
    - 300 articles total (150 left-block + 150 right-block).
    - Outlet block is exploratory metadata only, NOT a ground-truth ideology label.

Outputs:
    - data/raw/html/<sha1(url)>.html
    - data/processed/articles.jsonl  with schema:
        {
          "article_id":   str,              # sha1(url)
          "url":          str,
          "source":       str,              # outlet domain or short name
          "outlet_block": "left" | "right", # metadata only
          "title":        str,
          "lead":         str,              # first paragraph(s)
          "body":         str,              # cleaned full text
          "image_url":    str | None,       # main image URL (metadata only; never sent to VLM)
          "image_path":   str | None,       # local cached path once downloaded
          "published_at": str | None,       # ISO 8601 if available
          "language":     "en",
          "feed_url":     str,              # RSS feed the URL was first seen in (topic signal)
          "topic":        str,              # one of TOPIC_RULES keys, or "general"
          "topic_group":  "political" | "non-political" | "uncategorized"
        }

Notes:
    - Body text is intentionally NOT heavily cleaned here. Ads / boilerplate / promo
      sentences may remain; detailed sentence cleaning is a separate later step.
    - `outlet_block` is descriptive metadata only, not a ground-truth ideology label
      and not a target variable.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import feedparser
import requests
import trafilatura
from dotenv import load_dotenv

from utils import PROCESSED, RAW_HTML, write_jsonl

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# --- Outlet plan -------------------------------------------------------------
# Each block maps a short source name -> list of RSS feed URLs for that outlet.
# `outlet_block` is exploratory metadata only (descriptive, never causal, never a
# ground-truth ideology label). Outlets are widely categorised by independent media
# bias raters; we use that only to balance the two collection buckets.
RSS_FEEDS: dict[str, dict[str, list[str]]] = {
    "left": {
        "theguardian": [
            "https://www.theguardian.com/world/rss",
            "https://www.theguardian.com/us-news/rss",
            "https://www.theguardian.com/politics/rss",
        ],
        "npr": [
            "https://feeds.npr.org/1001/rss.xml",  # News
            "https://feeds.npr.org/1014/rss.xml",  # Politics
            "https://feeds.npr.org/1003/rss.xml",  # National
        ],
        # NOTE: CNN's public RSS endpoints (rss.cnn.com/*) are stale (last refreshed
        # 2023) so they are not usable for current articles. Replaced with HuffPost,
        # another widely categorised left-of-centre US outlet with working feeds.
        "huffpost": [
            "https://chaski.huffpost.com/us/auto/vertical/politics",
            "https://chaski.huffpost.com/us/auto/vertical/us-news",
            "https://chaski.huffpost.com/us/auto/vertical/world-news",
        ],
    },
    "right": {
        "foxnews": [
            "https://moxie.foxnews.com/google-publisher/latest.xml",
            "https://moxie.foxnews.com/google-publisher/politics.xml",
            "https://moxie.foxnews.com/google-publisher/us.xml",
            "https://moxie.foxnews.com/google-publisher/world.xml",
            "https://moxie.foxnews.com/google-publisher/opinion.xml",
        ],
        "nypost": [
            "https://nypost.com/feed/",
            "https://nypost.com/news/feed/",
            "https://nypost.com/us-news/feed/",
            "https://nypost.com/politics/feed/",
        ],
        "washingtonexaminer": [
            "https://www.washingtonexaminer.com/feed",
            "https://www.washingtonexaminer.com/section/news/feed",
            "https://www.washingtonexaminer.com/section/politics/feed",
        ],
        "washingtontimes": [
            "https://www.washingtontimes.com/rss/headlines/news/",
            "https://www.washingtontimes.com/rss/headlines/news/politics/",
        ],
        "dailycaller": [
            "https://dailycaller.com/feed/",
        ],
    },
}

TARGET_PER_BLOCK = 150

# Some outlets (e.g. npr.org) hang/stall on non-browser User-Agents, so default to a
# realistic browser UA. Can still be overridden via .env.
_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
USER_AGENT = os.getenv("USER_AGENT") or _DEFAULT_UA
CRAWL_DELAY_SEC = float(os.getenv("CRAWL_DELAY_SEC", "1.0"))
REQUEST_TIMEOUT = 20  # seconds per HTTP request
MIN_BODY_CHARS = 400  # skip stubs / non-article pages

# --- Topic taxonomy ---------------------------------------------------------
# First-match-wins keyword rules, scanned in order against the article URL path
# first, then the originating feed URL. Topics group into three buckets via
# TOPIC_GROUP. "general" is used when only a generic "news" feed is available
# (e.g. nypost /feed/, npr 1001 News, washingtontimes /news/, dailycaller /feed/);
# we DO NOT silently fold these into "political" because their actual subject is
# unverified.
TOPIC_RULES: list[tuple[str, list[str]]] = [
    ("politics",      ["politic", "election", "congress", "senate", "white-house",
                       "campaigns", "gop", "democrat", "1014"]),  # NPR 1014 = Politics
    ("us",            ["us-news", "us_news", "/us/", "national", "1003",
                       "/section/news/feed"]),                   # NPR 1003 = National
    ("world",         ["/world", "world-news", "world.xml", "international",
                       "foreign", "australia-news", "uk-news"]),
    ("opinion",       ["opinion", "op-ed", "commentisfree", "/voices/", "editorial",
                       "columnist"]),
    ("business",      ["business", "/money", "market", "finance", "econom"]),
    ("tech",          ["/tech", "/science", "/ai-", "/ai/"]),
    ("health",        ["/health", "covid", "medic", "wellness", "environment"]),
    ("entertainment", ["entertain", "celebrit", "tv-", "movie", "music", "media",
                       "magazine", "obituary"]),
    ("sports",        ["/sport", "outkick", "nfl", "nba", "mlb", "soccer", "olymp"]),
    ("lifestyle",     ["lifestyle", "/food", "/travel", "/home", "fashion",
                       "in_focus"]),
    ("general",       ["1001", "front-page", "moxie.foxnews.com/google-publisher/latest",
                       "nypost.com/feed", "washingtonexaminer.com/feed",
                       "washingtontimes.com/rss/headlines/news/",
                       "dailycaller.com/feed"]),
]
TOPIC_GROUP: dict[str, str] = {
    "politics": "political", "us": "political", "world": "political", "opinion": "political",
    "business": "non-political", "tech": "non-political", "health": "non-political",
    "entertainment": "non-political", "sports": "non-political", "lifestyle": "non-political",
    "general": "uncategorized",
}


def assign_topic(url: str, feed_url: str) -> tuple[str, str]:
    """Return (topic, topic_group). URL path wins over feed URL."""
    from urllib.parse import urlparse
    path = urlparse(url).path.lower()
    feed = (feed_url or "").lower()
    for topic, kws in TOPIC_RULES:
        if any(kw in path for kw in kws):
            return topic, TOPIC_GROUP[topic]
    for topic, kws in TOPIC_RULES:
        if any(kw in feed for kw in kws):
            return topic, TOPIC_GROUP[topic]
    return "general", TOPIC_GROUP["general"]


def sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def collect_feed_urls(feeds: list[str], session: requests.Session) -> list[tuple[str, str]]:
    """Return de-duplicated (article_url, feed_url) pairs in feed-read order.

    `feed_url` is the RSS feed the article URL was *first* seen in. We keep this so
    downstream steps can derive a publisher-provided topic label (e.g. .../politics.xml).
    """
    seen: set[str] = set()
    pairs: list[tuple[str, str]] = []
    for feed_url in feeds:
        try:
            resp = session.get(feed_url, timeout=REQUEST_TIMEOUT)
            parsed = feedparser.parse(resp.content)
        except Exception as exc:  # network / parse error — skip this feed
            print(f"    ! feed error {feed_url}: {exc}")
            continue
        n_before = len(pairs)
        for entry in parsed.entries:
            link = entry.get("link")
            if not link:
                continue
            link = link.split("#")[0].strip()
            if link in seen:
                continue
            seen.add(link)
            pairs.append((link, feed_url))
        print(f"    {feed_url} -> {len(pairs) - n_before} new urls")
        time.sleep(CRAWL_DELAY_SEC)
    return pairs


def fetch_html(url: str, session: requests.Session) -> str | None:
    """Fetch and cache raw HTML for a URL. Returns HTML text or None on failure."""
    cache_path = RAW_HTML / f"{sha1(url)}.html"
    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8", errors="ignore")
    html = None
    for attempt in range(2):  # one retry on transient failure
        try:
            resp = session.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            html = resp.text
            break
        except Exception as exc:
            if attempt == 1:
                print(f"    ! fetch error {url}: {exc}")
                return None
    if html is None:
        return None
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(html, encoding="utf-8", errors="ignore")
    time.sleep(CRAWL_DELAY_SEC)
    return html


def extract_article(html: str, url: str, source: str, block: str, feed_url: str) -> dict | None:
    """Extract a structured article dict from raw HTML using trafilatura."""
    extracted = trafilatura.extract(
        html,
        url=url,
        output_format="json",
        with_metadata=True,
        favor_recall=True,
        include_comments=False,
        include_tables=False,
    )
    if not extracted:
        return None
    meta = json.loads(extracted)
    body = (meta.get("text") or "").strip()
    if len(body) < MIN_BODY_CHARS:
        return None

    # Lead: prefer the article description, else first non-empty paragraph of body.
    lead = (meta.get("description") or "").strip()
    if not lead:
        for para in body.split("\n"):
            para = para.strip()
            if para:
                lead = para
                break

    topic, topic_group = assign_topic(url, feed_url)
    return {
        "article_id": sha1(url),
        "url": url,
        "source": source,
        "outlet_block": block,
        "title": (meta.get("title") or "").strip(),
        "lead": lead,
        "body": body,
        "image_url": meta.get("image") or None,
        "image_path": None,
        "published_at": meta.get("date") or None,
        "language": "en",
        "feed_url": feed_url,
        "topic": topic,
        "topic_group": topic_group,
    }


def crawl_block(block: str, sources: dict[str, list[str]], target: int,
                session: requests.Session) -> list[dict]:
    """Collect up to `target` articles for one outlet block, balanced across sources."""
    print(f"\n=== Block: {block} (target {target}) ===")

    # 1) Gather candidate (url, feed_url) pairs per source.
    candidates: dict[str, list[tuple[str, str]]] = {}
    for source, feeds in sources.items():
        print(f"  [{source}] reading feeds...")
        candidates[source] = collect_feed_urls(feeds, session)
        print(f"  [{source}] {len(candidates[source])} candidate urls")

    # 2) Round-robin across sources so no single outlet dominates the block.
    articles: list[dict] = []
    seen_ids: set[str] = set()
    cursors = {s: 0 for s in candidates}
    active = [s for s in candidates if candidates[s]]
    while len(articles) < target and active:
        for source in list(active):
            if len(articles) >= target:
                break
            pairs = candidates[source]
            i = cursors[source]
            if i >= len(pairs):
                active.remove(source)
                continue
            cursors[source] += 1
            url, feed_url = pairs[i]
            aid = sha1(url)
            if aid in seen_ids:
                continue
            html = fetch_html(url, session)
            if not html:
                continue
            art = extract_article(html, url, source, block, feed_url)
            if not art:
                continue
            seen_ids.add(aid)
            articles.append(art)
            if len(articles) % 10 == 0:
                print(f"  ...{len(articles)}/{target} articles")
    print(f"  => collected {len(articles)} articles for block '{block}'")
    return articles


def main() -> None:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    all_articles: list[dict] = []
    for block, sources in RSS_FEEDS.items():
        all_articles.extend(crawl_block(block, sources, TARGET_PER_BLOCK, session))

    out_path = PROCESSED / "articles.jsonl"
    n = write_jsonl(out_path, all_articles)

    # Summary
    by_block: dict[str, int] = {}
    by_source: dict[str, int] = {}
    for a in all_articles:
        by_block[a["outlet_block"]] = by_block.get(a["outlet_block"], 0) + 1
        by_source[a["source"]] = by_source.get(a["source"], 0) + 1
    print(f"\nWrote {n} articles -> {out_path}")
    print(f"By block:  {by_block}")
    print(f"By source: {by_source}")


if __name__ == "__main__":
    main()
