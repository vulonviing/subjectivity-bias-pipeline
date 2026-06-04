"""Step: sentence_split — split article bodies into sentences.

Two-phase cleaning:
    1) Minimal split here (this script): tokenize body into sentences, keep order,
       record article_id + sentence_index.
    2) Detailed sentence cleaning (boilerplate stripping, quote handling, length
       filtering, deduplication) is a SEPARATE step done before LLM annotation.
       Document that step in ai_usage/step_logs.md when it lands.

Short-fragment bridging (n <= SHORT_FRAGMENT_MAX_TOKENS words):
    Fragments too short to stand alone (e.g. "hah!", "oh no!") are not emitted
    as independent rows. Instead they are appended to the previous long sentence
    AND prepended to the next long sentence. Consecutive short fragments are
    merged into a single bridge block before attachment.

    Example:
        body: "Trump says it is nothing. hah! oh no! He should ask the workers."
        output:
            "Trump says it is nothing. hah! oh no!"
            "hah! oh no! He should ask the workers."

Output: data/processed/sentences.jsonl with schema:
    {
      "sentence_id":    str,              # f"{article_id}:{sentence_index}"
      "article_id":     str,
      "sentence_index": int,              # 0-based, within article
      "text":           str,              # raw sentence text (minimal cleaning)
      "n_chars":        int,
      "n_tokens_est":   int               # rough whitespace token count
    }
"""
from __future__ import annotations

import sys
from typing import Iterator

import spacy

from .utils import PROCESSED, read_jsonl, write_jsonl

SHORT_FRAGMENT_MAX_TOKENS = 3
SPACY_MODEL = "en_core_web_sm"


def load_nlp() -> spacy.Language:
    nlp = spacy.load(SPACY_MODEL)
    # Keep tok2vec + whichever component sets sentence boundaries
    sent_component = "senter" if "senter" in nlp.pipe_names else "parser"
    disable = [p for p in nlp.pipe_names if p not in ("tok2vec", sent_component)]
    if disable:
        nlp.disable_pipes(*disable)
    return nlp


def n_tokens(text: str) -> int:
    return len(text.split())


def split_body(body: str, nlp: spacy.Language) -> tuple[list[str], int]:
    """Split body into sentences with short-fragment bridging.

    Returns (sentences, n_bridge_groups) where n_bridge_groups counts how many
    short-fragment groups were absorbed into neighboring sentences.
    """
    # Treat each newline-separated paragraph independently so paragraph breaks
    # always become sentence boundaries (spaCy doesn't guarantee this otherwise)
    paragraphs = [p.strip() for p in body.split("\n") if p.strip()]
    raw_sents: list[str] = []
    for para in paragraphs:
        raw_sents.extend(s.text.strip() for s in nlp(para).sents if s.text.strip())

    if not raw_sents:
        return [], 0

    # Run-length group consecutive short fragments into single bridge blocks
    groups: list[tuple[str, bool]] = []  # (text, is_short)
    for sent in raw_sents:
        is_short = n_tokens(sent) <= SHORT_FRAGMENT_MAX_TOKENS
        if groups and groups[-1][1] and is_short:
            groups[-1] = (groups[-1][0] + " " + sent, True)
        else:
            groups.append((sent, is_short))

    n_bridges = sum(1 for _, is_short in groups if is_short)

    # Edge case: article contains only short fragments → emit as one row
    if all(is_short for _, is_short in groups):
        return [" ".join(t for t, _ in groups)], 0

    # Emit one row per long group, bridging adjacent short blocks
    output: list[str] = []
    for i, (text, is_short) in enumerate(groups):
        if is_short:
            continue
        parts: list[str] = []
        if i > 0 and groups[i - 1][1]:
            parts.append(groups[i - 1][0])
        parts.append(text)
        if i < len(groups) - 1 and groups[i + 1][1]:
            parts.append(groups[i + 1][0])
        output.append(" ".join(parts))

    return output, n_bridges


def process_article(article: dict, nlp: spacy.Language) -> Iterator[dict]:
    sents, _ = split_body(article.get("body", ""), nlp)
    for i, text in enumerate(sents):
        yield {
            "sentence_id": f"{article['article_id']}:{i}",
            "article_id": article["article_id"],
            "sentence_index": i,
            "text": text,
            "n_chars": len(text),
            "n_tokens_est": n_tokens(text),
        }


def main() -> None:
    nlp = load_nlp()
    articles = list(read_jsonl(PROCESSED / "articles_clean.jsonl"))

    rows: list[dict] = []
    total_bridges = 0
    for article in articles:
        body = article.get("body", "")
        sents, n_bridges = split_body(body, nlp)
        total_bridges += n_bridges
        aid = article["article_id"]
        for i, text in enumerate(sents):
            rows.append({
                "sentence_id": f"{aid}:{i}",
                "article_id": aid,
                "sentence_index": i,
                "text": text,
                "n_chars": len(text),
                "n_tokens_est": n_tokens(text),
            })

    write_jsonl(PROCESSED / "sentences.jsonl", rows)

    avg = len(rows) / len(articles) if articles else 0
    print(
        f"articles={len(articles)}  sentences={len(rows)}  "
        f"avg={avg:.1f}/article  bridge_groups={total_bridges}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
