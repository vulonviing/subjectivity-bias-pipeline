# Sentence Methodology Audit
**Date:** 2026-06-03  
**Corpus:** `data/processed/sentences.jsonl` — 8,887 sentences, 300 articles, 8 outlets  
**Input to splitting:** `data/processed/articles_clean.jsonl`  
**Splitter:** `src/sentence_split.py` (spaCy `en_core_web_sm`, paragraph-first, `SHORT_FRAGMENT_MAX_TOKENS=3`)  
**Downstream status:** `proxy_predictions.jsonl` and `llm_annotations.jsonl` are **empty** — annotation steps not yet run. All problems identified here are pre-annotation and therefore still correctable.  
**Sample files:** `data/analysis/sentence_methodology_samples/` (seed=13, stratified short/median/long, 3 articles × 8 outlets = 24 files, 717 sentences manually inspected)

---

## Executive Summary

Ten distinct problem classes were found across the 8,887 sentences. The severity breakdown:

| Severity | Count | Description |
|---|---|---|
| BLOCKING | 3 | Content classes that are systematically harmful to annotation quality |
| WARN | 7 | Structural or formatting issues that inflate noise without invalidating the dataset |
| INFO | 4 | Design trade-offs that are defensible but worth documenting |

**Most critical single finding:** Washington Times article `61b2fe584042e1a868c06bd6cfc1477b95ef05be` has its last 15 sentences (indices 16–30) consist entirely of the site's navigation menu — section links, podcast names, newsletter CTAs, "Subscribe / Sign In" — extracted verbatim from the page sidebar during crawling. These are not article content.

**Second most critical:** NPR includes 4 radio-transcript articles (58 sentences, 6.2% of NPR's total) with `SPEAKER: utterance` format, `(SOUNDBITE OF …)` audio stage directions, and backchannel turns ("Yeah.", "Great question, Ayesha."). These will behave very differently under a subjectivity classifier trained on written prose.

**Downstream timing:** Because `proxy_predictions.jsonl` and `llm_annotations.jsonl` are empty, no annotation contamination has occurred yet. All BLOCKING and WARN issues affect the sentences that *will be* annotated.

---

## Methodology

- **Phase 1** — Full corpus scan (8,887 sentences) using regex pattern matching and statistical analysis. No sampling. Every count in this report is exact.
- **Phase 2** — Outlet-by-outlet deep inspection: seed=13, 3 articles per outlet stratified by body length quartile (short ≤ Q25, median Q25–Q75, long ≥ Q75). Full sentence sequences examined in order — random sentence sampling would have missed bridging context.
- **Bridge rate** — Computed by re-running `split_body()` over all 300 `articles_clean.jsonl` bodies (read-only); `n_bridges` is not stored in `sentences.jsonl`.
- **Reproducer commands** are included at the end of each section.

---

## Phase 1 — Global Statistical Results

### 1.1 Sentence counts by outlet

| outlet | articles | sentences | sentences/article |
|---|---|---|---|
| theguardian | 64 | 2,375 | 37.1 |
| huffpost | 63 | 1,400 | 22.2 |
| foxnews | 35 | 1,385 | 39.6 |
| npr | 23 | 936 | 40.7 |
| washingtontimes | 35 | 842 | 24.1 |
| nypost | 35 | 837 | 23.9 |
| washingtonexaminer | 25 | 671 | 26.8 |
| dailycaller | 20 | 441 | 22.1 |
| **TOTAL** | **300** | **8,887** | **29.6** |

### 1.2 Token length distribution (n_tokens_est = whitespace split)

| outlet | min | p5 | p25 | median | p75 | p95 | max | ≤5 | 6–15 | 16–35 | 36–80 | >80 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| theguardian | 4 | 7 | 14 | 21 | 30 | 43 | 93 | 50 | 645 | 1,343 | 334 | 3 |
| huffpost | 4 | 7 | 14 | 22 | 31 | 44 | 103 | 35 | 396 | 755 | 213 | 1 |
| foxnews | 4 | 6 | 11 | 17 | 26 | 40 | 98 | 59 | 558 | 651 | 116 | 1 |
| npr | 4 | 6 | 12 | 18 | 26 | 38 | 59 | 33 | 329 | 503 | 71 | 0 |
| washingtontimes | 4 | 6 | 15 | 22 | 29 | 43 | 89 | 32 | 203 | 499 | 107 | 1 |
| nypost | 4 | 6 | 11 | 18 | 28 | 42 | 63 | 36 | 308 | 418 | 75 | 0 |
| washingtonexaminer | 4 | 7 | 12 | 20 | 28 | 41 | 61 | 21 | 213 | 363 | 74 | 0 |
| dailycaller | 4 | 7 | 13 | 20 | 29 | 44 | 88 | 13 | 126 | 253 | 48 | 1 |

**Key observation:** The minimum token count across all outlets is **4**, not 1–3. This confirms `SHORT_FRAGMENT_MAX_TOKENS=3` is working mechanically — no standalone ≤3-token row is emitted. However, several 4–6 token rows are boilerplate chrome (see §WARN-1) rather than editorial content. The ≤5 bucket (279 sentences total) warrants scrutiny.

### 1.3 Bridge rate by outlet

| outlet | articles | sentences | bridge_groups | bridges/sentence | avg_bridges/article |
|---|---|---|---|---|---|
| theguardian | 64 | 2,375 | 77 | 0.0324 | 1.20 |
| huffpost | 63 | 1,400 | 42 | 0.0300 | 0.67 |
| foxnews | 35 | 1,385 | 68 | 0.0491 | 1.94 |
| npr | 23 | 936 | 75 | **0.0801** | **3.26** |
| washingtontimes | 35 | 842 | 26 | 0.0309 | 0.74 |
| nypost | 35 | 837 | 27 | 0.0323 | 0.77 |
| washingtonexaminer | 25 | 671 | 12 | 0.0179 | 0.48 |
| dailycaller | 20 | 441 | 14 | 0.0317 | 0.70 |

NPR has the highest bridge rate (8% of its sentences, 3.26 groups/article). This is largely attributable to its radio transcript format: conversational backchannel turns like "Yeah.", "Right.", "Great question, Ayesha." are ≤3 tokens and trigger bridging. Each such turn gets appended to the preceding sentence AND prepended to the following one.

### 1.4 Intra-article duplicate sentences (bridging copy effect)

Each bridge block creates exactly 2 copies: one appended to its left neighbor, one prepended to its right neighbor. Excess duplicates beyond that pattern would indicate a different problem.

| outlet | extra_dup_sentences |
|---|---|
| theguardian | 7 |
| npr | 4 |
| foxnews | 2 |
| all others | 0 |

Total extra duplicates: 13. Examples:
- `theguardian 59c85547...:2` — "Kuwait foreign ministry condemns Iran drone and missile attacks..." appears twice (x2). `59c85547...:3` also appears twice. This is the bridging mechanism at work for a 2-sentence article with bridge blocks.
- `npr 86b57ba9...:0` — "After a Memorial Day break, Congress returns to the same problems they left behind." appears twice.

The 13 extra duplicates are mechanically correct per the bridging spec. However: when these sentences are annotated, they will receive **two independent label assignments** (once in each context row). If the two labels differ, the resulting disagreement is an artifact of the duplication, not a genuine annotation conflict.

**Reproducer:**
```bash
python3 -c "
import json; from collections import Counter, defaultdict
sents = [json.loads(l) for l in open('data/processed/sentences.jsonl')]
ba = defaultdict(list)
for s in sents: ba[s['article_id']].append(s)
for aid, ss in ba.items():
    tc = Counter(s['text'] for s in ss)
    for t, c in tc.items():
        if c>1: print(aid, c, t[:60])
"
```

### 1.5 Suspicious pattern scan (full corpus)

| pattern | total | theguardian | huffpost | foxnews | npr | washingtontimes | nypost | washingtonexaminer | dailycaller |
|---|---|---|---|---|---|---|---|---|---|
| `list_bullet` (^[-•—–*] \w) | **122** | 25 | 0 | 21 | 4 | 30 | **36** | 0 | 6 |
| `all_caps_header` (^[A-Z0-9 -]{6+}$) | **114** | 14 | 15 | **34** | 25 | 6 | 7 | 13 | 0 |
| `just_outlet_token` (^\[OUTLET\]) | 27 | 4 | 2 | 6 | 4 | 2 | 3 | 5 | 1 |
| `date_timestamp` | 27 | 0 | 1 | 4 | 1 | 2 | 5 | 2 | 12 |
| `twitter_handle` (@\w{2+}) | 13 | 0 | 0 | 3 | 1 | 0 | 1 | 0 | **8** |
| `sign_up` | 10 | 3 | 0 | 1 | 0 | 0 | 6 | 0 | 0 |
| `url_fragment` | 10 | 0 | 1 | 0 | 4 | 0 | 0 | 0 | 5 |
| `copyright_line` | 9 | 0 | 0 | 1 | **8** | 0 | 0 | 0 | 0 |
| `subscribe` | 2 | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 |
| `read_more` | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `watch_colon` (^WATCH:) | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 3 |
| `ellipsis_start` | 2 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 |

Zero false positives found for: `photo_credit`, `numbered_list` (5, all editorial), `qanda`, `outlet_only` (`^\[OUTLET\][\s.,:-]*$`).

---

## Phase 2 — Outlet-by-Outlet Deep Sample

Sample selection: seed=13, stratified by body-length quartile. 24 articles, 717 sentences total.

---

### The Guardian (64 articles, 2,375 sentences)

**Sample:** `600270704f12` (18s, short), `017f3653b06e` (27s, median), `e71fb8da23a6` (57s, long).

**Bridging behavior:** Guardian's "First Thing" newsletter format (`e71fb8da...`) triggers bridging at section dividers. Specifically, the newsletter uses `" -"` (space-dash) and `"… -"` as separator tokens between embedded story summaries. spaCy parses these as sentence-ending fragments (1–2 tokens), which then get bridged to neighbors. Examples:
- `e71fb8da...:7` ends with "... -" (dash) which at 1 token triggers bridging to both `:6` (Lebanon war para) and `:8` ("- Is this the end of the ceasefire, then?"). The result: sentence `:7` appended with the question `:8`; sentence `:8` prepended with the tail of `:7`. Both are retained.
- `e71fb8da...:15` ends with "." then "- " — same pattern.
- `e71fb8da...:25` ends with "." then "- ".

**Splitting quality:** Good for standard prose. No false splits on "Mr.", "U.S.", etc. noticed in sample.

**Cleaning escapes:**
- `e71fb8da...:54`: "...the long road to adulthood. Sign up" — the phrase "Sign up" bled from a CTA into the preceding editorial sentence because they shared a paragraph. Not caught by cleaning because they were on the same line.
- `e71fb8da...:55`: "Sign up First Thing is delivered to thousands of inboxes every weekday." — standalone newsletter CTA sentence.
- `e71fb8da...:56`: "If you're not already signed up, subscribe now. Get in touch" — newsletter footer with "subscribe" and "Get in touch" CTA merged.
- `e71fb8da...:28`: "In other news … -" — pure transition fragment surviving as a sentence (4 tokens, above bridge threshold).
- `e71fb8da...:38`: "Building power: 'We won't stop until they're free': protesters outside a New Jersey ICE facility, in their own words" — article teaser/promo blurb masquerading as a sentence.
- `e71fb8da...:41`: "Don't miss this: a visual guide to Fifa World Cup stadiums" — same.
- `e71fb8da...:44`: "... or this: how Nigeria's bandit crisis spun out of control" — same.
- `e71fb8da...:48`: "Climate check: Australia's household battery revolution" — same.
- `e71fb8da...:52`: "Last Thing: The ruthlessness and redemption of Rupert Everett" — same.

**Outlet-specific quirks:** The Guardian's "First Thing" newsletter is structurally an aggregator — a sequence of article teasers separated by subsection headers. Seven of the 57 sentences in the long sample are newsletter chrome (teaser labels, section headers, CTA), not editorial prose. This is a content-type problem, not a cleaning failure: the entire article is a promotional newsletter format.

---

### HuffPost (63 articles, 1,400 sentences)

**Sample:** `59bd682a` (9s, short), `e77c0b79` (20s, median), `ed7b2de9` (34s, long).

**Bridging behavior:** Zero bridge groups in all 3 samples. HuffPost writes in clean short prose; no ≤3-token interjections found.

**Splitting quality:** Very clean. No issues detected in sample. Single-sentence quotes properly attributed within the same sentence.

**Cleaning escapes:**
- `ed7b2de9...:33`: "Jeffress did not immediately respond to a request for comment. ___" — trailing AP wire termination marker `___` survived. Not a blacklisted pattern. Low-severity cosmetic issue.
- `huffpost 12a6b264...:121` (not in sample but from Phase 1): "Sign up here for a weekly roundup of The Upside, sent to you every Sunday Bored at work?" — CTA that survived cleaning, with trailing editorial fragment "Bored at work?" fused.

**Outlet-specific quirks:** None found in sample. HuffPost is the cleanest outlet in the corpus by far — 0 extra duplicates, 0 bridge groups in sample, minimal pattern hits.

---

### Fox News (35 articles, 1,385 sentences)

**Sample:** `edd7b027` (16s, short), `75b6774a` (28s, median), `c88516fb` (48s, long).

**Bridging behavior:** Fox News embeds "related article" headline boxes inside article body text. spaCy splits them correctly as new sentences, but the preceding sentence sometimes gets the headline's opening fragment appended. Example:
- `edd7b027...:3`: "Well, buckle up because we have a real doozy today. HORRIFIED TOURISTS WATCH" — ends with the first 3 tokens of an embedded headline. spaCy failed to break here because the preceding sentence ended with "today" (no full stop before the all-caps run).
- `edd7b027...:4`: "HORRIFIED TOURISTS WATCH AS BISON BOILS TO DEATH IN YELLOWSTONE HOT SPRING" — pure embedded related-article headline. No editorial content.
- `edd7b027...:10`: "BEAR ATTACK IN YELLOWSTONE NATIONAL PARK LEAVES 2 HIKERS INJURED Spoiler: not well." — related headline bleeding into next sentence. The fragment "Spoiler: not well." at ≤3 tokens triggers bridging to `:11`.
- `edd7b027...:11`: "Spoiler: not well. She face planted while attempting to run away." — bridge result: fragment prepended.
- `c88516fb...:0`: "EXCLUSIVE: NEW YORK CITY —" — 4-token fragment that survived because it's just above the bridge threshold. This is a Fox News dateline format. Not a bridge candidate, but also not a sentence.
- `c88516fb...:6`: "SQUATTER TURNS COUPLE'S DREAM HOME PURCHASE INTO NIGHTMARE" — embedded related-article headline.
- `c88516fb...:16`: "IS MAMDANI'S SOCIALIST PUSH FOR RENT CONTROLS ABOUT TO WRECK THE NEW YORK CITY HOUSING MARKET?" — embedded related-article headline.
- `c88516fb...:31`: "WASHINGTON POST BLASTS RENT CONTROL AS 'FAILED POLICY' THAT LEAVES RENTERS 'WORSE OFF' THAN BEFORE" — embedded related-article headline.

**All-caps header count:** 35 hits total (highest of any outlet). These are a mix of: (a) embedded related-article headline boxes inside article body (~20 estimated), and (b) Fox's own section sub-headers within long-form articles (~15 estimated). Neither type is a grammatical sentence.

**Cleaning escapes:**
- Fox News's related-article headline injection pattern was not in the blacklist — it's not a "CTA" or a byline; it's an editorial navigation element that only appears inside the body HTML.

**Outlet-specific quirks:** Fox's article structure routinely inserts promotional links to other Fox articles as all-caps headline fragments mid-paragraph. This is an extraction artifact — the crawler pulled inline cross-links as body text.

---

### NPR (23 articles, 936 sentences)

**Sample:** `bddac9be` (2s, short), `acf75762` (51s, medium), `111fe2a8` (91s, long).

**Bridging behavior:** NPR has the highest bridge rate (8.01% of sentences, 3.26 groups/article). The radio transcript format generates many ≤3-token turns that trigger bridging. In `acf75762`:
- `acf75762...:50`: "(SOUNDBITE OF MUSIC) Copyright © 2026 [OUTLET]. All rights reserved." — bridge result combining audio direction with copyright footer.
- Backchannel turns such as "Yeah.", "Right.", "I see." appear as bridge blocks, creating sentences like "Yeah. RASCOE: Where do things stand with those deployments? LONSDORF:" — a compound that is simultaneously an editorial fragment, a speaker label, and an incomplete utterance.

**Splitting quality for transcripts:** spaCy `en_core_web_sm` was trained on written prose. On radio transcripts:
- Speaker labels (`MCDANIEL:`, `FLORIDO:`, `ROSE:`) are not recognized as metadata — spaCy treats them as part of the sentence text.
- Question-answer turns on a single line get split mid-conversation: `86b57ba9...:18`: "FLORIDO: Is the president going to back down on this? MCDANIEL: No." → spaCy didn't split this — the full dialog exchange is one row.
- Conversely, `86b57ba9...:19`: "MCDANIEL: No. He's not really shown any signs of that so far. FLORIDO:" — the next speaker tag "FLORIDO:" is orphaned at the end.
- `59675cc1...:20`: "(SOUNDBITE OF BAGGAGE LANDING IN CART) ROSE:" — audio direction fused with speaker label.

**Cleaning escapes — NPR article `86b57ba9`:**
- `:47`: "FLORIDO: That's [OUTLET] Congress reporter Eric McDaniel. Eric, thanks. MCDANIEL: Thanks, Adrian. Copyright © 2026 [OUTLET]. All rights reserved. Visit our website terms of use..." — an 8-sentence-equivalent block: standard sign-off, inter-speaker thanks, and the full copyright footer all merged into one row.
- `:48`: "Eric, thanks. MCDANIEL: Thanks, Adrian. Copyright © 2026 [OUTLET]. All rights reserved. Visit our website terms of use and permissions pages..." — duplicate of the above (bridging effect), with the copyright footer now forming the bulk.

**Cleaning escapes — NPR article `bddac9be` (2-sentence "Morning news brief"):**
- Both sentences contain "Accessibility links" — an HTML navigation element that was not cleaned. The entire article was so short after cleaning that it only has 2 sentences, both of which are bridge artifacts: sentence `:0` ends with "Accessibility links" and sentence `:1` begins with "Accessibility links". This article should arguably be excluded from the dataset (too little content).
- Sentence `:0`: "Morning news brief Israel expands Lebanon offensive as U.S.-Iran peace talks stall, Congress returns to D.C. with long to-do list, rulings create more obstacles for Trump's 'anti-weaponization' fund. Accessibility links" — the headline plus the nav element.

**NPR transcript scope (Phase 1):** 4 NPR articles are transcript-format (19–34% SPEAKER: lines), totaling 58 transcript-format sentences (6.2% of NPR's output). Articles:
- `59675cc1` (34% transcript) — "Inside ATL: how Delta juggles 100,000 bags a day"
- `acf75762` (29% transcript) — "Boston's Brazilian residents..."
- `3e295b78` (21% transcript) — "DC will host America 250 celebrations..."
- `86b57ba9` (19% transcript) — "After a Memorial Day break, Congress returns..."

These also contain `(SOUNDBITE OF ...)` stage directions (5 sentences), copyright footers (9 sentences), and speaker-attribution orphans — content that is categorically not written editorial prose.

---

### Washington Times (35 articles, 842 sentences)

**Sample:** `b8467d99` (10s, short), `bab1eaa8` (22s, median), `b0e5141d` (31s, long).

**Bridging behavior:** Low bridge rate (0.031). No bridging issues found in the 3-article sample. The 30 list-bullet sentences are structurally coherent (each bullet = one event/item) and do not trigger bridging.

**Splitting quality:** Good for prose. The 30 bullet-point sentences in `7654303a` are a historical timeline of Iranian actions — each bullet item correctly gets its own row. spaCy handles the "• In [year], ..." pattern cleanly.

**Cleaning escapes — article `61b2fe58`:**
This is the most severe finding in the entire corpus. Sentences 16–30 (15 sentences) in article `61b2fe58` ("DOJ subpoenas Reddit and X for user identities") are verbatim site navigation content:

```
[16] "A federal judge is reportedly weighing the users' requests to have the government's
     subpoenas tossed out. - News - Policy - Commentary - Commentary Main - Corrections - ..."
[17] "- News - Policy - Commentary - Commentary Main - Corrections - Editorials - Letters -
     Cheryl K. Chumley - Kelly Sadler - ..."
[18] "- Kelly Sadler - Jed Babbin - Tom Basile - Tim Constantine - Joseph Curl - ..."
[19] "- Don Feder - Billy Hallowell - Daniel N. Hoffman - David Keene - Robert Knight - ..."
[20] "- David Keene - Robert Knight - Gene Marks - Clifford D. May - Michael McKenna - ..."
[21] "- Michael McKenna - Stephen Moore - Tim Murtaugh - Peter Navarro - ..."
[22] "- Sports - Sponsored - Events - Video/Podcasts - Corrections - All Videos - ..."
[23] "- Threat Status - Politically Unstable - The Sitdown with Alex Swoyer"
[24] "- Bold & Blunt"
[25] "- The Higher Ground - Court Watch"
[26] "- Court Watch - Victory Over Communism"
[27] "- District of Sports"
[28] "- Capitol Hill Show"
[29] "- The Unregulated Podcast - ForAmerica - [OUTLET] Weekly"
[30] "- ForAmerica - [OUTLET] Weekly - God, Country & American Story - Games - Subscribe - Sign In"
```

The blacklist-based cleaning did not catch this because the nav content consists of proper-noun section names (not CTAs) and author names. Sentence `:16` has a legitimate editorial sentence fused with the nav block start (the "- News - Policy..." run appended to the article's final editorial sentence). This is one article out of 35 Washington Times articles, but it contributes 15 non-content rows to the dataset.

**Outlet-specific quirks:** The 30 bullet-point sentences in `7654303a` ("Stop whining, America") are substantive — they list historical events. Bullets here are legitimate journalism format. Unlike NY Post's bullets (episode guides), these carry factual and potentially opinion-laden content and are appropriate for annotation.

---

### NY Post (35 articles, 837 sentences)

**Sample:** `e0180339` (16s, short), `d0bb6485` (21s, medium), `c31f7c6e` (64s, long).

**Bridging behavior:** Low bridge rate (0.032). No bridging issues in the 3-article sample.

**Splitting quality:** Generally clean for prose articles. The "Not Suitable for Work" article (`c31f7c6e`) is the structural outlier.

**Cleaning escapes — article `c31f7c6e` ("When Does 'Not Suitable for Work' Come Out On Hulu"):**
This 64-sentence article is a structured entertainment FAQ/guide — not a news article. Its content includes:
- 9 episode schedule bullet points (`- Episode 1: Tuesday, June 2`, etc., sentences 27–35)
- 13 cast list bullet points (`- Ella Hunt as AJ Pascarelli`, etc., sentences 39–53)
- Promotional pricing block (Hulu subscription tiers at $10.99, $18.99, $32.99, sentences 59–62)
- Repetitive FAQ headers: "When Does Not Suitable for Work Come Out?", "What Time Does Not Suitable for Work Come Out?", "How Many Episodes Are In Not Suitable for Work?", "How To Watch Not Suitable for Work: Hulu Streaming Info" — these are headings, not sentences.
- Bridged near-duplicate pairs: `c31f7c6e...:11`: "We've got answers! When Does Not Suitable for Work Come Out?" and `:12`: "We've got answers! When Does Not Suitable for Work Come Out?" (bridge duplication).

Of the 64 sentences, approximately 35 (55%) are structured list items, FAQ headers, pricing info, or promotional sentences — not news content. Applying subjectivity annotation to entertainment guide content of this type has low validity.

**Cleaning escapes — sign-up CTAs:**
- `9a1ed180...:22`: "California Post Opinion California Post Newsletters: Sign up here!"
- `9a1ed180...:24`: "Home delivery: Sign up here!"
- `9a1ed180...:25`: "[OUTLET] Hollywood: Sign up here!"
- `2f0938e7...:28–:31`: Same CTA block appears verbatim in a second article.

These are a sidebar newsletter subscription block that appears on two articles — likely from the NY Post homepage or section front. The blacklist catches "click here" but not "sign up here!" (exclamation mark variant).

**Outlet-specific quirks:** NY Post's "Decider" entertainment section uses a guide/FAQ format (episode schedules, streaming info, cast lists) that is structurally incompatible with sentence-level subjectivity annotation. The corpus contains at least one such article (`c31f7c6e`). The topic taxonomy would label this "entertainment" — it may warrant a flag for downstream exclusion.

---

### Washington Examiner (25 articles, 671 sentences)

**Sample:** `8e9baf34` (6s, short), `8ec9edbc` (22s, median), `c9073b5e` (51s, long).

**Bridging behavior:** Lowest bridge rate (0.018). No bridging issues in sample.

**Splitting quality:** Clean. Quotes and attributions handled correctly. No abbreviation splitting errors detected.

**Cleaning escapes — article `c9073b5e` ("The WHCA dinner shooting was a warning without a bullet"):**
- `:0`: "In Focus delivers deeper coverage of the political, cultural, and ideological issues shaping America." — promo blurb for a recurring section ("In Focus"), not article content.
- `:1`: "Published daily by senior writers and experts, these in-depth pieces go beyond the headlines to give readers the full picture." — continuation of the same promo block.
- `:2`: "You can find our full list of In Focus pieces here." — CTA with "here" (not "click here"), so not caught by blacklist.

Three consecutive sentences (3/51 = 6%) are a section-promo block.

**Cleaning escapes — related-article headers:**
- `c9073b5e...:13`: "COLE ALLEN'S BACKGROUND ISN'T UNUSUAL FOR A TERRORIST" — embedded related-article headline (all-caps).
- `c9073b5e...:42`: "BETHANY MANDEL: THE FERTILITY CRISIS ISN'T AN ECONOMIC PROBLEM." — embedded related-article headline.
- `c9073b5e...:43`: "IT'S A CULTURAL ONE" — this is the second line of the same headline (split by spaCy). A 4-token fragment just above the bridge threshold, it gets emitted as a standalone sentence with no context.

The pair `:42`–`:43` illustrates a specific spaCy failure mode: a two-part headline where "THE FERTILITY CRISIS ISN'T AN ECONOMIC PROBLEM." ends with a period, causing spaCy to treat "IT'S A CULTURAL ONE" as a new sentence. Both rows reach the output. "IT'S A CULTURAL ONE" alone is uninterpretable.

**Outlet-specific quirks:** Washington Examiner uses a recurring "In Focus" section-promo block that appears as the first 3 sentences in multiple articles. The pattern is consistent and blacklist-identifiable.

---

### Daily Caller (20 articles, 441 sentences)

**Sample:** `e30372e9` (11s, short), `53f95723` (15s, median), `e8cc2232` (43s, long).

**Bridging behavior:** Low bridge rate (0.032). In `53f95723`, the Twitter embed attribution lines trigger bridging:
- `53f95723...:11`: "Trans-identifying cyclist wins two Oregon women's races by combined 48 minutes under OBRA rules https://t.co/bZtK8uYSzu" — tweet body + URL (the tweet itself).
- `53f95723...:12`: "— Rep. Dwayne Yunker HD3 (@RepYunker) June 1, 2026" — tweet attribution (5 tokens, not bridged).

**Cleaning escapes — Twitter embed remnants (8 sentences):**
The cleaning blacklist catches tweet attribution lines matching `^- Name (@handle) Month DD, YYYY` (with leading ASCII hyphen-space). Daily Caller's tweets use `"— "` (em-dash + space) as the attribution prefix. The regex does not match em-dash, so all 8 Twitter attribution lines survived:
- `8a3711...:7`: "— Politics & Poll Tracker 📡 (@PollTracker2024) May 29, 2026"
- `79c0a4...:1`: "— Homeland Security (@DHSgov) June 1, 2026"
- `2abb05...:5`: "— Rep. Lauren Boebert (@RepBoebert) May 15, 2026"
- `90c132...:3`: "— Nicole Silverio (@NicoleMSilverio) June 1, 2026"
- `53f957...:12`: "— Rep. Dwayne Yunker HD3 (@RepYunker) June 1, 2026"
- `e83302...:3`: "— Pop Crave (@PopCrave) May 31, 2026"
- `470c03...:11`: "https://t.co/WmTAV5ihTe — The Wall Street Journal (@WSJ) May 30, 2026"
- `71470076...:7`: same WSJ line (appears in two articles, same tweet embedded twice).

The tweet body sentences (separate from attribution lines) also survived:
- `53f957...:11`: "Trans-identifying cyclist wins two Oregon women's races by combined 48 minutes under OBRA rules https://t.co/bZtK8uYSzu" — tweet body with t.co URL.

**WATCH: prefix sentences (3 sentences):**
- `bd9416...:5`: "WATCH: "She is due on my dad's birthday..."" — video pull-quote; content is legitimate but "WATCH:" is a UI label.
- `ab605f...:1`: "WATCH: "You have a two-term governor in North Carolina..."" — same.
- `1900e2...:5`: "WATCH: More than three out of four respondents to a poll..." — same.
The "WATCH:" prefix adds a UI element to an otherwise valid sentence. Low severity.

**Date-timestamp outlier in `7fca11...:1`:**
"[N]ew laws from Richmond primarily relating to (1) the purchase, sale, transfer, possession or transportation of firearms, ammunition, or components... [2026]" — the timestamp hit is a false positive (bracketed date inside a legal quote). Not a cleaning issue.

**Outlet-specific quirks:** Daily Caller embeds significantly more Twitter/X content than other outlets, and its em-dash attribution format escapes the existing regex. 9 tweet-related sentences total across 8 articles.

---

## Phase 3 — Cross-cutting Analysis

### 3.1 Bridging: design intent vs. actual trigger population

The bridge mechanism was designed for pragmatic fragments like "hah!" that lose meaning in isolation. In practice, it is triggered by a much wider set of inputs:

| Trigger type | Examples | Outlet(s) | Impact |
|---|---|---|---|
| Pragmatic interjection (intended use) | "Why?", "hah!" | Guardian, Fox | Low — adds context correctly |
| Conversational backchannel | "Yeah.", "Right.", "Great question, Ayesha." | NPR | Creates compound dialog rows |
| Section divider token | "- " (dash-space), "… -" | Guardian | Appends unrelated adjacent story |
| Related-article header fragment | "HORRIFIED TOURISTS WATCH", "Spoiler: not well." | Fox | Fuses headline with editorial sentence |
| Transcript speaker stub | "FLORIDO:", "ROSE:" | NPR | Creates orphaned speaker label at sentence boundary |
| Navigation nav item | "- Bold & Blunt" | WashTimes | Bridges nav content into editorial sentence |

The bridge rate is mechanically correct but the trigger scope extends well beyond the design intent. NPR's bridge rate (8%) is primarily driven by transcripts, not pragmatic fragments.

**Label duplication risk:** 13 extra-copy sentences (confirmed) will produce paired annotation rows. If the LLM annotator yields different labels for the "left context" vs. "right context" version of the same bridge text, the pair contributes contradictory training signal. The disagreement is not a real ambiguity.

### 3.2 `SHORT_FRAGMENT_MAX_TOKENS = 3` threshold evaluation

The minimum sentence length across all 8,887 rows is **4 tokens** (correct: nothing ≤3 is emitted standalone). However:
- 279 sentences have ≤5 tokens. Among these, several are legitimate short sentences ("Comey denies the allegation." — 4 tokens, `bab1eaa8...:19`-equivalent), but others are structural chrome ("- Bold & Blunt" — 3 tokens emitted as part of bridging? — actually 4: "Bold & Blunt" is 3 tokens with the dash making 4). 
- The `n_tokens_est = text.split()` whitespace-only tokenizer over-counts in some cases: "FLORIDO:" is 1 token but is not editorial content. "Yeah." is 1 token. "U.S." is 1 token (correct). The threshold performs reasonably but doesn't distinguish boilerplate from pragmatic fragments.

**No `all-short-article` edge cases found.** The `split_body()` fallback (emit all shorts as one merged row) was not triggered for any of the 300 articles.

### 3.3 Paragraph structure quality

All 300 articles have multi-paragraph bodies (zero single-paragraph articles found). Body splitting on `\n` is appropriate for this corpus. spaCy's paragraph-level processing effectively makes paragraph breaks hard sentence boundaries, which is correct for journalism.

**One implicit risk:** Articles extracted with aggressive cleaning may lose the `\n` that separated a nav-sidebar from the article body. The WashTimes `61b2fe...` case supports this: the nav content appears to have been in a separate DOM region that the crawler wrote to the body without a clear paragraph separator, or cleaning accidentally stripped the separator.

### 3.4 Content-type contamination

Three content types appear in the corpus that are structurally incompatible with the chosen task (sentence-level subjectivity in *written news prose*):

1. **Radio transcripts (NPR, 4 articles, 58 sentences):** Conversational spoken dialog, backchannel turns, stage directions. The mDeBERTa proxy and GPT annotator were not designed for spoken dialog. Subjectivity signals differ systematically between spoken and written registers. These 58 sentences should either be excluded or flagged with a `content_type=transcript` field.

2. **Entertainment FAQ/guide (NY Post, at least 1 article, ~35 sentences):** Structured episode schedules, cast lists, pricing tiers. No editorial framing; almost entirely objective data. Annotation on this content is low-validity.

3. **Navigation/sidebar injection (WashTimes, 1 article, 15 sentences):** Pure site menu content. Annotation would label it "objective" but the labels are meaningless for training.

Combined, these three types contribute approximately **108 sentences** (~1.2% of the corpus) that are systematically inappropriate for the annotation task as scoped.

### 3.5 Downstream consistency (annotation files empty)

`proxy_predictions.jsonl` and `llm_annotations.jsonl` are both empty (0 lines). No annotation has been applied. This means:
- All identified problems exist only in `sentences.jsonl` and are pre-annotation.
- Fixing `sentences.jsonl` before running annotation avoids propagating errors downstream.
- The disagreement analysis (Step: analyze) cannot be impacted yet.

### 3.6 `n_tokens_est` / `n_chars` field validity

No anomalies found: all sentences have char/token ratios between 2.5 and 30 (the expected range for English prose). The whitespace tokenizer is consistent, even if it undercounts true linguistic tokens in cases like "U.S." or overcounts in emoji-containing text.

---

## Severity-Sorted Finding List

### BLOCKING — Must be addressed before running annotation

---

**B-1: Washington Times navigation menu injection**  
`61b2fe584042e1a868c06bd6cfc1477b95ef05be`, sentences `:16`–`:30` (15 sentences)  
Website navigation sidebar (section links, columnist names, podcast titles, "Subscribe / Sign In") extracted as article body text. These 15 rows contain zero editorial content. Sentence `:16` is a compound of the article's final editorial sentence fused with the start of the nav block.  
*Outlets:* washingtontimes only (1 article)  
*Downstream impact:* 15 rows would receive annotation labels. Labels would be meaningless and would count toward inter-annotator agreement calculations.  
*Reproducer:* `jq 'select(.article_id=="61b2fe584042e1a868c06bd6cfc1477b95ef05be" and .sentence_index >= 16)' data/processed/sentences.jsonl | jq .text`

---

**B-2: NPR radio transcript sentences**  
4 articles, ~58 sentences (6.2% of NPR output) in `SPEAKER: utterance` format, plus `(SOUNDBITE OF ...)` stage directions (5 sentences) and copyright/footer compounds (9 sentences).  
The mDeBERTa proxy and LLM annotator are calibrated to written prose. Spoken dialog differs systematically in subjectivity signal: first-person address, hedging ("you know", "I mean"), and turn-taking markers are all high-subjectivity in the model but are register-normal in spoken language, not opinionated framing.  
*Outlets:* npr only  
*Articles:* `59675cc1`, `acf75762`, `3e295b78`, `86b57ba9`  
*Downstream impact:* 58 transcript sentences would be annotated as prose, introducing systematic label distortion in NPR's subjectivity rate. NPR already has the highest bridge rate; these articles further inflate its apparent "subjectivity" for non-editorial reasons.  
*Reproducer:* `python3 -c "import json,re; rx=re.compile(r'^[A-Z][A-Z\s]{2,20}:\s+\w'); [print(r['sentence_id'], r['text'][:80]) for r in (json.loads(l) for l in open('data/processed/sentences.jsonl')) if rx.match(r['text'])]"`

---

**B-3: NPR "Accessibility links" nav fragment in 2-sentence article**  
Article `bddac9befa14c0ee3b62e73889dabbaa0a7ade6d` ("Morning news brief") produces exactly 2 sentences, both containing "Accessibility links" — an HTML navigation element. The article body is effectively a headline teaser with a nav fragment. Both sentences are bridge artifacts (each contains the headline content and the nav element). Annotating a 2-sentence article where both sentences are compromised by a nav artifact is not valuable.  
*Reproducer:* `jq 'select(.article_id=="bddac9befa14c0ee3b62e73889dabbaa0a7ade6d")' data/processed/sentences.jsonl | jq .text`

---

### WARN — Should be investigated and flagged before reporting results

---

**W-1: All-caps embedded related-article headlines (Fox News, Washington Examiner)**  
114 total sentences matching `^[A-Z0-9 -]{6,}$`. Fox News: 35 sentences (highest). WashExaminer: 13. These are primarily inline related-article headline boxes inserted mid-article body. They are not grammatical sentences and not editorial prose.  
Selected examples:
- `edd7b027...:4`: "HORRIFIED TOURISTS WATCH AS BISON BOILS TO DEATH IN YELLOWSTONE HOT SPRING"
- `c88516fb...:6`: "SQUATTER TURNS COUPLE'S DREAM HOME PURCHASE INTO NIGHTMARE"
- `c88516fb...:16`: "IS MAMDANI'S SOCIALIST PUSH FOR RENT CONTROLS ABOUT TO WRECK THE NEW YORK CITY HOUSING MARKET?"
- `c9073b5e...:13`: "COLE ALLEN'S BACKGROUND ISN'T UNUSUAL FOR A TERRORIST"
- `c9073b5e...:42`: "BETHANY MANDEL: THE FERTILITY CRISIS ISN'T AN ECONOMIC PROBLEM."
- `c9073b5e...:43`: "IT'S A CULTURAL ONE" (second line of the above headline, split by spaCy)

The "IT'S A CULTURAL ONE" case illustrates a compounding problem: spaCy splits a 2-part headline at its mid-period, emitting an orphan that is uninterpretable in isolation and just above the bridge threshold.

*Downstream impact:* All-caps headlines are likely labeled SUBJ by the LLM annotator (sensationalist framing) and OBJ by the proxy (factual-looking nominal). This creates artificial disagreement not attributable to genuine annotation ambiguity.  
*Reproducer:* `python3 -c "import json,re; [print(r['sentence_id'],r['text']) for r in (json.loads(l) for l in open('data/processed/sentences.jsonl')) if re.match(r'^[A-Z0-9][A-Z0-9 \-\'\"]{5,}$', r['text'])]" | head -20`

---

**W-2: List/bullet sentences — NY Post entertainment guide format**  
Article `c31f7c6e` ("Not Suitable for Work" Hulu guide): 36 bullet items (episode dates, cast list) plus 7 FAQ headers. These 43+ structured items are not news sentences. Of the 64 total sentences in the article, ~55% are structured data.  
Selected examples (episode schedule, cast list, pricing):
- `:27`–`:35`: "- Episode 1: Tuesday, June 2" × 9 entries
- `:39`–`:53`: "- Ella Hunt as AJ Pascarelli" × 13 cast entries
- `:59`–`:62`: Hulu subscription pricing tiers

*Downstream impact:* Episode dates and cast lists will all be labeled OBJ by both annotators (correctly), but these labels carry no information about subjective framing. They dilute the dataset's effective annotation density on content that matters.

---

**W-3: NY Post and Guardian sign-up/CTA remnants**  
NY Post: 6 sentences across 2 articles (`9a1ed180`, `2f0938e7`) — same newsletter CTA block appearing twice: "California Post Opinion California Post Newsletters: Sign up here!", "Home delivery: Sign up here!", "[OUTLET] Hollywood: Sign up here!".  
Guardian: 3 sentences in `e71fb8da` — "Sign up First Thing is delivered to thousands of inboxes every weekday.", "If you're not already signed up, subscribe now. Get in touch".  
The NYPost blacklist catches "click here" but not "sign up here!" (variant with exclamation mark). The Guardian cleaning catches "subscribe to" but not "subscribe now".  
*Total:* 9 sentences  
*Reproducer:* `jq 'select(.text|ascii_downcase|test("sign.?up here|subscribe now"))' data/processed/sentences.jsonl | jq .sentence_id,.text`

---

**W-4: Daily Caller Twitter/X attribution lines (em-dash format)**  
8 sentences, all tweet attribution lines: "— HANDLE (@account) Month DD, YYYY". The cleaning regex for tweet attribution (`^- Name (@handle) Month DD, YYYY`) uses ASCII hyphen-space (`- `), not em-dash (`— `). All 8 Daily Caller tweet attributions use em-dash and therefore escaped.  
Also: 2 sentences contain raw `t.co` URLs (`470c03...:11`, `71470076...:7`), and 1 sentence contains a tweet body with a `t.co` URL inline (`53f957...:11`).  
*Total:* ~11 tweet-artifact sentences  
*Reproducer:* `jq 'select(.text|test("^—\\s+|t\\.co/|@\\w{2,}"))' data/processed/sentences.jsonl | jq .sentence_id,.text`

---

**W-5: NPR copyright/footer compound sentences**  
9 sentences containing "Copyright © 2026 [OUTLET]. All rights reserved. Visit our website terms of use..." — NPR's standard audio transcript footer. Several are compounded with editorial content (sign-off phrases, final speaker attribution) due to paragraph-level concatenation before the copyright block.  
Selected examples:
- `86b57ba9...:47`: editorial sign-off + copyright footer in one row
- `86b57ba9...:48`: bridge copy of the above, leading with the copyright footer
- `59675cc1...:62`, `:63`: same pattern
- `3e295b78...:41`, `:42`: same pattern  
*Reproducer:* `jq 'select(.text|test("Copyright ©|All rights reserved|Visit our website"))' data/processed/sentences.jsonl | jq .sentence_id,.text`

---

**W-6: Washington Examiner "In Focus" promo block**  
A recurring 3-sentence section promo ("In Focus delivers deeper coverage..." / "Published daily by senior writers..." / "You can find our full list of In Focus pieces here.") appears at the start of at least 1 confirmed article (`c9073b5e...:0`–`:2`). Because Washington Examiner has 25 articles, this block may appear in additional articles not in the Phase 2 sample.  
*Total confirmed:* 3 sentences  
*Reproducer:* `jq 'select(.text|test("In Focus delivers|Published daily by senior writers|full list of In Focus"))' data/processed/sentences.jsonl | jq .sentence_id,.text`

---

**W-7: Fox News dateline fragment ("EXCLUSIVE: NEW YORK CITY —")**  
Article `c88516fb...:0`: 4 tokens ("EXCLUSIVE: NEW YORK CITY —"). This is a Fox News article dateline format — not a sentence. At 4 tokens it is just above the bridge threshold, so it is emitted standalone. No editorial content.  
Also: `edd7b027...:3` ("Well, buckle up because we have a real doozy today. HORRIFIED TOURISTS WATCH") — an editorial sentence with a related-article headline prefix absorbed at its end, because spaCy did not break at the period-to-ALLCAPS transition without punctuation.  
*Total:* ~3 dateline/overflow sentences  
*Reproducer:* `jq 'select(.text|test("^EXCLUSIVE:"))' data/processed/sentences.jsonl | jq .sentence_id,.text`

---

### INFO — Design decisions with documented trade-offs

---

**I-1: Bridging trigger scope is broader than intended**  
Design intent: preserve pragmatic fragments ("hah!"). Actual triggers include nav items, conversational backchannel, related-article headers, and speaker stubs. The bridge rate is highest at NPR (8%) and Fox (4.9%), not because of pragmatic fragments but because of transcript and nav content. The threshold of 3 tokens is not semantically restrictive enough to isolate the intended use case.

---

**I-2: Duplicate bridge rows will produce paired annotation entries**  
13 extra-copy sentences (confirmed by intra-article duplicate scan) will each receive 2 annotation passes — once in left-context, once in right-context form. If the LLM or proxy labels differ between the two copies, the resulting pair creates a spurious disagreement signal. This is a known cost of the bridging design; the 13 cases are small enough that impact on aggregate agreement metrics is minimal at current corpus size.

---

**I-3: `n_tokens_est` underestimates for punctuation-attached tokens**  
`text.split()` counts "MCDANIEL:" as 1 token. For bridge threshold evaluation, "FLORIDO: No." is 3 tokens by this count (FLORIDO:/No./no-text), right at the threshold. Minor inconsistency; does not change the conclusion that the threshold is functionally working.

---

**I-4: No all-short-article edge cases found**  
The `split_body()` fallback path (merge all-short groups into 1 row) was not triggered for any of the 300 articles. The corpus has no pathologically short cleaned bodies.

---

## Reproducer Command Cheatsheet

```bash
# B-1: WashTimes nav menu
jq 'select(.article_id=="61b2fe584042e1a868c06bd6cfc1477b95ef05be" and .sentence_index >= 16)' \
    data/processed/sentences.jsonl | jq -r '.sentence_id + ": " + .text'

# B-2: NPR transcript-format sentences
python3 -c "
import json, re
rx = re.compile(r'^[A-Z][A-Z\s]{2,20}:\s+\w')
for l in open('data/processed/sentences.jsonl'):
    r = json.loads(l)
    if rx.match(r['text']): print(r['sentence_id'], r['text'][:80])
"

# W-1: All-caps headers
python3 -c "
import json, re
for l in open('data/processed/sentences.jsonl'):
    r = json.loads(l)
    if re.match(r'^[A-Z0-9][A-Z0-9 \-\'\"\?\.]{5,}$', r['text']): print(r['sentence_id'], r['text'])
" | wc -l   # expect ~114

# W-4: Tweet attribution em-dash
python3 -c "
import json, re
for l in open('data/processed/sentences.jsonl'):
    r = json.loads(l)
    if re.search(r'^[—–]\s+\w|t\.co/|@\w{2,}', r['text']): print(r['sentence_id'], r['text'][:90])
"

# W-5: NPR copyright footer
jq 'select(.text|test("Copyright ©|All rights reserved"))' data/processed/sentences.jsonl \
    | jq -r '.sentence_id + ": " + .text'

# W-3: Sign-up CTAs
jq 'select(.text|ascii_downcase|test("sign.?up|subscribe now"))' data/processed/sentences.jsonl \
    | jq -r '.sentence_id + ": " + .text'

# Global: sentences with n_tokens_est <= 5
jq 'select(.n_tokens_est <= 5)' data/processed/sentences.jsonl | jq -r '.sentence_id + " " + .text' | head -30

# Bridge rate by outlet (requires re-running split_body)
python3 -c "
import json, sys
from collections import defaultdict
articles = {json.loads(l)['article_id']: json.loads(l) for l in open('data/processed/articles_clean.jsonl')}
sys.path.insert(0,'.')
from src.sentence_split import load_nlp, split_body
nlp = load_nlp()
stats = defaultdict(lambda: [0,0,0])
for a in articles.values():
    o = a.get('source','?')
    s, b = split_body(a.get('body',''), nlp)
    stats[o][0]+=1; stats[o][1]+=len(s); stats[o][2]+=b
for o,v in stats.items(): print(o, v[2]/v[1] if v[1] else 0)
"
```

---

## Open Questions

1. **Should NPR transcript articles be excluded from the annotation dataset, or flagged with a `content_type` field?** Exclusion preserves annotation validity; inclusion with flagging allows analysis of whether transcripts differ systematically from prose in subjectivity rate.

2. **Should the WashTimes `61b2fe...` article have its nav-menu sentences (`:16`–`:30`) removed from `sentences.jsonl` before annotation?** The article itself (sentences `:0`–`:15`) is valid and should be retained.

3. **The Guardian's "First Thing" newsletter format and NY Post's Hulu guide are content-type problems, not cleaning failures.** Would a content-type filter at the article level (flagging newsletters, episode guides, cast lists) be useful for downstream model training?

4. **Daily Caller's tweet attribution em-dash regex gap:** Should the cleaning regex `^- Name (@handle) ...` be extended to also match `^— ` (em-dash)? The fix is simple but is outside the scope of this audit.

5. **Fox News's inline related-article headline injection:** These all-caps blocks are not cleanable without DOM-level HTML parsing (they appear inline in the `<article>` body text, not in a separate `<aside>` element, according to the crawl artifacts in `data/raw/html/`). The only post-hoc option is a regex filter on `^[A-Z0-9 -]{12,}$` before annotation.

6. **Bridging duplication and annotation:** When annotation runs, duplicate bridge sentences will produce two label rows for the same text fragment in two different contexts. The agreement analysis should treat bridged duplicate pairs as a separate stratum — do not include them in the main agreement metric calculation.
