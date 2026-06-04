# Output Check — Review Notes

**Date:** 2026-06-04  
**Check type:** Read-only reconciliation of README + EDA notebook outputs vs. on-disk artifacts. No pipeline re-runs, no file edits.

---

## 1. File Existence (README §"Required outputs")

| Required file | On disk |
|---|---|
| `data/processed/articles.jsonl` | ✓ |
| `data/processed/articles_clean.jsonl` | ✓ |
| `data/processed/sentences.jsonl` | ✓ |
| `data/processed/proxy_predictions.jsonl` | ✓ |
| `data/processed/llm_annotations.jsonl` | ✓ |
| `data/processed/vlm_annotations.jsonl` | ✓ |
| `data/analysis/agreement_metrics.json` | ✓ |
| `data/analysis/disagreement_examples.csv` | ✓ |
| `data/finetune/proxy/train.jsonl` | ✓ |
| `data/finetune/proxy/val.jsonl` | ✓ |
| `data/finetune/proxy/test.jsonl` | ✓ |
| `data/finetune/proxy/splits_manifest.json` | ✓ |
| `data/finetune/vlm/train.jsonl` | ✓ |
| `data/finetune/vlm/val.jsonl` | ✓ |
| `data/finetune/vlm/test.jsonl` | ✓ |
| `data/finetune/vlm/splits_manifest.json` | ✓ |
| `data/finetune/dataset_card.md` | ✓ |
| `README.md` | ✓ |
| `prompts/llm_sentence_annotation.txt` | ✓ |
| `prompts/vlm_image_annotation.txt` | ✓ |
| `ai_usage/step_logs.md` | ✓ |

**Result: all 21 required outputs present.**

---

## 2. Row Counts (README claim vs. `wc -l`)

| README / dataset_card claim | File | wc -l | Match |
|---|---|---:|---|
| 300 articles | `data/processed/articles.jsonl` | 300 | ✓ |
| 297 cleaned articles | `data/processed/articles_clean.jsonl` | 297 | ✓ |
| 8,561 sentences | `data/processed/sentences.jsonl` | 8,561 | ✓ |
| 8,561 proxy predictions | `data/processed/proxy_predictions.jsonl` | 8,561 | ✓ |
| 8,561 LLM annotations | `data/processed/llm_annotations.jsonl` | 8,561 | ✓ |
| 292 VLM annotations | `data/processed/vlm_annotations.jsonl` | 292 | ✓ |
| proxy train 6,007 | `data/finetune/proxy/train.jsonl` | 6,007 | ✓ |
| proxy val 1,278 | `data/finetune/proxy/val.jsonl` | 1,278 | ✓ |
| proxy test 1,276 | `data/finetune/proxy/test.jsonl` | 1,276 | ✓ |
| VLM train 204 | `data/finetune/vlm/train.jsonl` | 204 | ✓ |
| VLM val 44 | `data/finetune/vlm/val.jsonl` | 44 | ✓ |
| VLM test 44 | `data/finetune/vlm/test.jsonl` | 44 | ✓ |

**Result: all 12 row counts match exactly.**

---

## 3. Headline Metrics (README §Findings ↔ `agreement_metrics.json`)

### 3a. Overall proxy ↔ LLM

| Metric | README claims | `agreement_metrics.json` | Match |
|---|---:|---:|---|
| n | 8,561 | 8,561 | ✓ |
| TP | 1,012 | 1,012 | ✓ |
| FP | 210 | 210 | ✓ |
| FN | 1,052 | 1,052 | ✓ |
| TN | 6,287 | 6,287 | ✓ |
| Accuracy | 85.3% | 85.26% | ✓ (rounds to 85.3) |
| Cohen κ | 0.532 | 0.532 | ✓ |
| SUBJ precision | 0.828 | 0.8282 | ✓ (rounds to 0.828) |
| SUBJ recall | 0.490 | 0.4903 | ✓ (rounds to 0.490) |
| SUBJ F1 | 0.616 | 0.6159 | ✓ (rounds to 0.616) |
| Proxy SUBJ % | 14.3% | 14.27% | ✓ |
| LLM SUBJ % | 24.1% | 24.11% | ✓ |
| LLM mean confidence | 0.930 | 0.9302 | ✓ |

### 3b. Outlet-level (κ, SUBJ %, FN counts)

| Outlet | README κ | JSON κ | README LLM SUBJ% | JSON LLM SUBJ% | README Proxy% | JSON Proxy% | README FN | JSON FN | Match |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| foxnews | 0.555 | 0.5554 | 36.5 | 36.52 | 26.4 | 26.43 | 193 | 193 | ✓ |
| washingtonexaminer | 0.589 | 0.589 | 31.2 | 31.18 | 20.4 | 20.43 | 87 | 87 | ✓ |
| theguardian | 0.574 | 0.5741 | 28.0 | 28.04 | 18.1 | 18.12 | 299 | 299 | ✓ |
| dailycaller | 0.598 | 0.5981 | 26.3 | 26.30 | 14.7 | 14.74 | 55 | 55 | ✓ |
| huffpost | 0.341 | 0.3408 | 18.8 | 18.75 | 5.8 | 5.75 | 193 | 193 | ✓ |
| nypost | 0.398 | 0.3982 | 17.1 | 17.11 | 7.3 | 7.33 | 94 | 94 | ✓ |
| npr | 0.402 | 0.402 | 13.7 | 13.67 | 8.4 | 8.41 | 65 | 65 | ✓ |
| washingtontimes | 0.403 | 0.4027 | 11.9 | 11.94 | 5.5 | 5.48 | 66 | 66 | ✓ |

### 3c. VLM metrics

| Metric | README claim | JSON value | Match |
|---|---:|---:|---|
| n articles | 292 | 292 | ✓ |
| VLM SUBJ n | 56 (implied by outlet sum) | 56 | ✓ |
| VLM mean confidence | 0.8672 (JSON) | 0.8672 | ✓ |
| nypost VLM SUBJ % | 35.5 | 35.48 | ✓ |
| huffpost VLM SUBJ % | 24.6 | 24.59 | ✓ |
| theguardian VLM SUBJ % | 23.4 | 23.44 | ✓ |
| dailycaller VLM SUBJ % | 15.0 | 15.0 | ✓ |
| washingtontimes VLM SUBJ % | 11.8 | 11.76 | ✓ |
| foxnews VLM SUBJ % | 11.4 | 11.43 | ✓ |
| washingtonexaminer VLM SUBJ % | 8.0 | 8.0 | ✓ |
| npr VLM SUBJ % | 9.1 | 9.09 | ✓ |
| text×image OBJ/OBJ | 218 | 218 | ✓ |
| text×image OBJ/SUBJ | 47 | 47 | ✓ |
| text×image SUBJ/SUBJ | 9 | 9 | ✓ |

**Result: all 3a / 3b / 3c metric claims reconcile with `agreement_metrics.json`.**

---

## 4. Split Label Distributions (dataset_card / README ↔ disk recompute)

Recomputed by reading `label` field of every JSONL row in each split file.

### Proxy splits

| Split | Claimed OBJ | Disk OBJ | Claimed SUBJ | Disk SUBJ | Claimed SUBJ% | Disk SUBJ% | Match |
|---|---:|---:|---:|---:|---:|---:|---|
| train | 4,522 | 4,522 | 1,485 | 1,485 | 24.7% | 24.7% | ✓ |
| val | 968 | 968 | 310 | 310 | 24.3% | 24.3% | ✓ |
| test | 1,007 | 1,007 | 269 | 269 | 21.1% | 21.1% | ✓ |

### VLM splits

| Split | Claimed OBJ | Disk OBJ | Claimed SUBJ | Disk SUBJ | Claimed SUBJ% | Disk SUBJ% | Match |
|---|---:|---:|---:|---:|---:|---:|---|
| train | 166 | 166 | 38 | 38 | 18.6% | 18.6% | ✓ |
| val | 33 | 33 | 11 | 11 | 25.0% | 25.0% | ✓ |
| test | 37 | 37 | 7 | 7 | 15.9% | 15.9% | ✓ |

**Result: all OBJ/SUBJ counts and percentages match exactly.**

---

## 5. EDA Notebook Reconciliation

Checked `notebooks/eda.ipynb` (94 cells) against README §Findings and `data/analysis/*.json/csv`. No cells execute external APIs in the reconciliation-relevant sections (persisted outputs used).

| EDA output | Matches README / disk? |
|---|---|
| Cell [3]: "Total articles: 300, left 150, right 150" | ✓ README §Collection plan |
| Cell [23]: "Raw: 300 → Clean: 297 → Dropped: 3" | ✓ row counts |
| Cell [25]: "Duplicate URLs: 0, titles: 0, article_id: 0" | ✓ no duplicates |
| Cell [48]: "Sentences: 8561 / VLM: 292 / Proxy SUBJ: 1222 / LLM SUBJ: 2064 / VLM SUBJ: 56" | ✓ matches §Findings §1 and metrics JSON |
| Cell [50]: "Proxy OBJ: 7339 (85.7%) / SUBJ: 1222 (14.3%)" | ✓ README 14.3% (1,222) |
| Cell [55]: "LLM OBJ: 6497 (75.9%) / SUBJ: 2064 (24.1%) / mean conf: ~0.930" | ✓ README 24.1% (2,064) |
| Cell [58]: "All 8,561 completions finished with `stop` reason" | ✓ no truncated outputs |
| Cell [62]: "VLM OBJ: 236 (80.8%) / SUBJ: 56 (19.2%) / mean_conf: 0.8672" | ✓ metrics JSON |
| Cell [74]: Outlet κ table — huffpost 0.3408 through dailycaller 0.5981 | ✓ JSON by_outlet, all 8 rows |
| Cell [86]: "Cross-modality TP=9 FP=47 FN=18 TN=218 — self-verified against agree_metrics.json" | ✓ JSON text_vs_image_cross |
| Block × topic table (summary_tables.csv): left/political n=3880, subj=24.05% etc. | ✓ README §3 table |
| Topic breakdown: opinion 57.0%/61.8%, sports 47.6%/49.9%, politics 24.6%/15.6% | ✓ README §3 topic table |
| All 26 figure files in `data/analysis/figures/` | ✓ all present |

EDA notebook's cross-modality cell explicitly self-verifies against `agreement_metrics.json` and prints the JSON values — no discrepancy.

**Result: EDA notebook outputs are consistent with README and on-disk JSON/CSV.**

---

## 6. Schema Spot-Checks

| File | Expected schema | Observed keys | image_b64 / extra checks | Pass |
|---|---|---|---|---|
| `data/processed/llm_annotations.jsonl` (row 1) | `llm_label`, `llm_rationale`, `llm_confidence` | All present (22 fields total incl. sentence metadata) | — | ✓ |
| `data/processed/vlm_annotations.jsonl` (row 1) | `vlm_label`, `image_description`, `vlm_rationale`, `vlm_confidence` | All present (20 fields total incl. article metadata) | — | ✓ |
| `data/finetune/proxy/train.jsonl` (row 1) | `sentence_id`, `article_id`, `text`, `label` | Exactly these 4 fields | — | ✓ |
| `data/finetune/vlm/train.jsonl` (row 1) | `article_id`, `title`, `lead`, `image_b64`, `image_mime`, `label` | Exactly these 6 fields | `image_b64` length = 137,220 chars; no `data:` prefix | ✓ |
| `data/analysis/disagreement_examples.csv` | FN+FP rows with sentence_id / source / text / labels / kind | 1,262 rows (= FN 1,052 + FP 210) | `kind` ∈ {proxy_missed_subj, proxy_false_subj} | ✓ |

**Result: all schema checks pass.**

---

## 7. Deltas / Flags

No factual errors found. One minor narrative coverage note:

**Minor (not a bug):** README §Findings §4 cross-modality paragraph names three of four cells in the 2×2 table (218 OBJ/OBJ; 47 OBJ-text/SUBJ-image; 9 SUBJ/SUBJ) but does not explicitly state the fourth cell (18 SUBJ-text / OBJ-image). The number is present in `agreement_metrics.json → text_vs_image_cross` and in EDA cell [86]; the total 218+47+18+9 = 292 ✓. The sentence "only 9 of 292 articles are SUBJ in both modalities" is accurate. This is a narrative omission, not a data error. Mentioning the 18 SUBJ-text/OBJ-image articles in the README would give a more complete picture (it implies 27 articles have subjective text but neutral images, reinforcing the independence claim).

---

**Overall verdict: all required outputs present; all claimed numbers reconcile with on-disk artifacts. Pipeline output is clean.**

---

## 8. EDA Markdown-Claim Audit

Read-only verification of every substantive claim made in `notebooks/eda.ipynb` markdown cells. Each claim is checked against the named source file, on-disk data, or referenced EDA code-cell output.

Legend: ✓ verified · ✗ contradicted · ⚠ imprecise / partially overstated

| # | Cell | Claim (short) | Verified against | Result |
|---|---|---|---|---|
| 1 | [2] | 300 articles, 150 per outlet block | `articles.jsonl` groupby outlet_block | ✓ |
| 2 | [2] | `assign_topic` at `src/crawl.py` line 155, scans URL then feed URL | `src/crawl.py:155` — `def assign_topic(url, feed_url)`, path check first then feed check | ✓ |
| 3 | [12] | `general` elevated in right block because 4 of 5 right-block outlets use generic feeds | articles.jsonl uncategorized counts per right-block outlet: washingtontimes=19, dailycaller=15, nypost=7, washingtonexaminer=3; foxnews=0 (URL paths encode sections). 4 of 5 produce uncategorized articles ✓ | ✓ |
| 4 | [26] | 300 articles, 150/block | §2 row-count check | ✓ |
| 5 | [26] | Right block higher `general` share, 4 of 5 right-block outlets generic | same as #3 | ✓ |
| 6 | [26] | Vast majority carry `image_url`; small number skipped for VLM | articles.jsonl: 4 null image_url (all nypost); 300 total; VLM annotated 292/297 = 98.3% | ✓ |
| 7 | [26] | Articles within narrow publication window | `published_at` min/max: 2026-04-28 → 2026-06-01 (≈5 weeks) | ✓ |
| 8 | [26] | 3 dropped in cleaning; no duplicate URLs or article IDs | 300 raw → 297 clean ✓; dup_urls=0, dup_ids=0 ✓ | ✓ |
| 9 | [27] | Cleaning pipeline: 7 ordered layers | `src/cleaning.py::clean_body()`: (1) unicode lines 413–416; (2) block-drop lines 418–436; (3–5) blacklist+regex in `_line_is_boilerplate()` lines 362–386; (6) trailing-bio lines 456–472; (7) masking lines 474–481. All 7 layers present, order matches | ✓ |
| 10 | [27] | Min-content filters: `MIN_BODY_CHARS=400`, `MIN_SENTENCES=3` | `scripts/clean_articles.py:13–14` | ✓ |
| 11 | [27] | Cleaning removes only boilerplate — editorial content not altered | `src/cleaning.py` operates line-by-line on blacklist/regex matches; editorial body lines are passed through. Spot-check: random cleaned article retains full editorial text | ✓ |
| 12 | [35] | Per-layer attribution: blacklist / block-drop / trailing-bio / outlet-mask | Cell [36] output shows 4 delta columns (`unicode_delta`, `blacklist_delta`, `bio_delta`, `mask_delta`) corresponding to layers 1–2 merged into unicode+block, then 3–5 as blacklist, 6 as bio, 7 as mask. Attribution model consistent with code order | ✓ |
| 13 | [46] | "Median ~5–15% body-char reduction" | **Recomputed from disk:** overall median = 1.6%. Per-outlet medians: huffpost/theguardian/washingtontimes = 0.0%, washingtonexaminer = 3.1%, npr = 0.7%, foxnews = 5.2%, nypost = 8.0%, dailycaller = 23.1%. Only foxnews and nypost fall in the 5–15% range. Cell [28] itself prints "Overall median reduction: 1.6%". The Takeaway's "5–15%" claim does not match the computed data. | ⚠ **inaccurate** — takeaway overstates typical reduction. |
| 14 | [46] | DailyCaller and NPR show highest blacklist hit rates | Cell [39]: NPR mean_bp_rate=18.72%, dailycaller=17.23% — top two ✓ (foxnews 15.38% is third) | ✓ |
| 15 | [46] | Trailing-bio layer small but non-zero, concentrated in Wash Examiner + Guardian | Cell [36]: `bio_delta` — huffpost=0.4%, nypost=0.3%, theguardian=0.5%, washingtonexaminer=0.0%. Guardian has non-zero bio contribution ✓; Wash Examiner shows 0.0% (bio signals go through blacklist path for that outlet, not `_BIO_SIGNALS`). Minor mismatch on Wash Examiner. | ⚠ minor — Wash Examiner bio_delta=0.0% in layer attribution (bio removal handled via OUTLET_BLACKLIST, not `_BIO_SIGNALS` path) |
| 16 | [46] | "[OUTLET] masking contributes ≤1% character removal" | Cell [36] `mask_delta`: values range −1.0% (washingtonexaminer, net addition) to +0.1% (npr, nypost). Magnitude is ≤1% ✓. But "removal" is wrong for outlets where masking adds characters (short alias → 8-char `[OUTLET]` token). | ⚠ imprecise — effect is ≤1% in magnitude, but can be net addition, not removal |
| 17 | [46] | 3 dropped articles (min-content filter) | 300 → 297 ✓ | ✓ |
| 18 | [46] | spaCy splitter; ≤3-token phrase-bridging | `src/sentence_split.py:41` `SHORT_FRAGMENT_MAX_TOKENS = 3`; `split_body()` implements bridge logic lines 76–101 ✓ | ✓ |
| 19 | [46] | Cross-outlet refs (WaPo, CNN) NOT masked — retained as editorial signal | `src/cleaning.py OUTLET_ALIASES` lists only 8 corpus outlets; no WaPo/NYT/CNN/MSNBC entries. `TODO_IF_I_HAD_TIME.md` line 10 documents the design rationale | ✓ |
| 20 | [47] | Three annotators: proxy/LLM/VLM with correct models, label spaces | `src/proxy_label.py`: `GroNLP/mdebertav3-subjectivity-english` OBJ/SUBJ; `src/annotate_llm.py:1` LLM via Batch API; `src/annotate_vlm.py:42` `DEFAULT_MODEL="gpt-5.4-mini"` Batch API. All match EDA table | ✓ |
| 21 | [49] | Proxy receives sentence text only — no outlet, title, image | `src/proxy_label.py:68` `--text-field text` (default); `proxy_label.py:141–164` passes only `text` field value to classifier | ✓ |
| 22 | [54] | LLM via Batch API, structured outputs (json_schema), mean conf ~0.93 | `src/annotate_llm.py:5` "Batch API, Structured Outputs"; line 191 `response_format: {type: json_schema}`; metrics JSON `llm_mean_confidence=0.9302` | ✓ |
| 23 | [58 output] | All 8,561 completions finished with `stop` | Recomputed from `llm_annotations.jsonl`: `finish_reason` Counter = `{'stop': 8561}` | ✓ |
| 24 | [61] | VLM input = base64 image + title + lead; outlet/URL/topic never sent | `src/annotate_vlm.py:236` `text_content = user_template.format(title=title, lead=lead)` — only title and lead; no source/outlet_block/url/topic in user_content | ✓ |
| 25 | [68] | Proxy SUBJ 14.3% (1,222 / 8,561) | §3 metrics check ✓ | ✓ |
| 26 | [68] | LLM SUBJ 24.1% (2,064 / 8,561), mean conf 0.930 | §3 metrics check ✓ | ✓ |
| 27 | [68] | 0 truncated responses | `llm_finish_reason` all `stop` ✓ (same as #23) | ✓ |
| 28 | [68] | Highest proxy SUBJ: Fox News, Guardian, Wash Examiner | Recomputed: foxnews=26.4%, washingtonexaminer=20.4%, theguardian=18.1% — top 3 ✓ | ✓ |
| 29 | [68] | VLM SUBJ 19.2% (56/292), mean conf 0.867 | §3c metrics check ✓ | ✓ |
| 30 | [68] | 5 articles skipped: 4 no image_url, 1 stale 404 — Washington Times | `articles_clean.jsonl`: 4 null image_url, all from nypost ✓; `vlm_download_errors.jsonl`: 1 entry, washingtontimes URL, "404 Not Found" ✓. Total 4+1=5 ✓ | ✓ |
| 31 | [68] | Highest VLM SUBJ: NY Post (35.5%), HuffPost (24.6%), Guardian (23.4%) | §3c metrics check ✓ | ✓ |
| 32 | [71] | κ = 0.532, recall = 0.49 | §3a metrics ✓ | ✓ |
| 33 | [93] | 83% of disagreements are False Negatives | 1,052 / (1,052 + 210) = 83.4% ✓ | ✓ |
| 34 | [93] | HuffPost hardest (κ 0.34), Daily Caller easiest (κ 0.60) | §3b outlet table ✓ | ✓ |
| 35 | [93] | Short sentences show higher proxy_FN rate | Cell [77]: FN rate short=13.66%, medium=12.20%, long=11.61% — monotone decreasing ✓ | ✓ |
| 36 | [93] | "Both judges retain high confidence at disagreement points" | FN (proxy missed SUBJ): LLM mean conf = 0.900 ✓ high. FP (proxy false SUBJ): proxy mean score = 0.638 — above threshold but only moderate. | ⚠ partially overstated — LLM is high-confidence at FN points (0.900), but proxy mean score at FP points (0.638) is moderate, not clearly "high" |
| 37 | [93] | LLM rationale terms at missed-SUBJ: evaluative adj, intensifiers, attribution verbs, loaded nouns | Cell [83] LOR table top missed terms: `loaded`, `characterization`, `reporting`, `exhortation`, `expression` — maps to loaded nouns, attribution verbs, exhortation theme ✓; `llm_rationale_terms.csv` confirms term frequencies | ✓ |
| 38 | [91] | Five themes from manual inspection; no automated clustering | Cell [92] output: 5 rows matching the 5 named themes, with manually chosen keyword examples. The LOR ranking (cell [83]) is statistical, but the theme names/taxonomy in cell [91] are hand-curated, not cluster IDs | ✓ |
| 39 | [93] | "LLM-text ↔ VLM-image effectively uncorrelated (κ ≈ 0)" | Cell [86]: κ = 0.105. Cell [90]: Spearman ρ (LLM↔VLM) = 0.134, **p = 0.022** — statistically significant. Weak but non-zero. | ⚠ overstated — κ = 0.105 and ρ = 0.134 (p=0.022) indicate a weak but statistically significant positive correlation. "Effectively uncorrelated" understates a small real signal. |
| 40 | [89] | Spearman ρ triple-judge analysis | Cell [90]: all three pairs computed — Proxy↔LLM ρ=0.736 (p=0.000), LLM↔VLM ρ=0.134 (p=0.022), Proxy↔VLM ρ=0.078 (p=0.185) ✓ | ✓ |

### Findings summary

**35 of 40 claims: ✓ fully verified.**

**5 items flagged (all ⚠ — imprecision or overstatement; no ✗ outright contradictions):**

| # | Claim | Issue |
|---|---|---|
| 13 | "Median ~5–15% body-char reduction" | Overall median is 1.6% (printed by cell [28] itself). Per-outlet medians range 0%–23%; only foxnews (5.2%) and nypost (8.0%) land in the 5–15% range. The takeaway overstates typical reduction. |
| 15 | Trailing-bio concentrated in Wash Examiner + Guardian | Guardian bio_delta=0.5% ✓; Wash Examiner bio_delta=0.0% in layer attribution (its author-bio signals are caught by `OUTLET_BLACKLIST`, not `_BIO_SIGNALS` regex path). Minor outlet mismatch. |
| 16 | "[OUTLET] masking ≤1% character removal" | Net character *change* is ≤1% in magnitude, but for outlets with short aliases (e.g. washingtonexaminer: −1.0%), masking is a net character *addition*. "Removal" is the wrong direction for several outlets. |
| 36 | "Both judges retain high confidence at disagreement points" | LLM at FN points: mean conf 0.900 ✓. Proxy at FP points: mean score 0.638 — above threshold but only moderately high, not "high confidence." |
| 39 | "Effectively uncorrelated (κ ≈ 0)" | κ = 0.105; Spearman ρ = 0.134, p = 0.022. Small but statistically significant. Saying "effectively uncorrelated" is an overstatement; "very weakly correlated" is more accurate. |

No claim is outright wrong in a way that invalidates any analytical finding. The largest actionable discrepancy is **#13**: the Stage 2 Takeaway narrative should match its own cell's printed number (1.6% overall, 0%–23% per-outlet range), not an unsourced "5–15%" figure.
