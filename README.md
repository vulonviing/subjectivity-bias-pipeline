# Media Bias Pipeline

Small end-to-end pipeline that produces a **fine-tuning-ready dataset for sentence-level media bias detection** from English news articles. Built as a PhD technical-exam deliverable (~4–6h scope).

## Chosen sub-task
**Sentence-level subjective / opinionated framing bias** in English news articles.
Subjectivity is treated as a *proxy signal* for opinionated framing — not as a synonym for "media bias". The dataset is designed so a downstream classifier can be fine-tuned on sentence-level subjective-vs-objective framing, with article-level metadata (outlet, outlet block, main image) available for richer analysis.

## Collection plan
- **Total:** 300 articles via RSS feeds.
- **150** from a left-leaning outlet block, **150** from a right-leaning outlet block.
- Concrete outlet list is chosen and documented in `src/crawl.py` (and logged in `ai_usage/step_logs.md`).
- **`outlet_block ∈ {left, right}` is exploratory metadata only**, not a ground-truth ideology label and not the target variable. Block-level differences are descriptive, never causal.

## Unit choices
| Concern | Unit |
|---|---|
| Collection | article |
| Text fine-tuning | sentence |
| Proxy classifier input | sentence (only) |
| VLM input | article main image + title + lead paragraph |
| Metadata (not features) | source, outlet_block, title, url, image_url, feed_url, topic, topic_group |

## Topic taxonomy
Each article in `data/processed/articles.jsonl` carries a `topic` and a `topic_group`. Topics are assigned by a deterministic, first-match-wins keyword rule (see `assign_topic()` in `src/crawl.py`) that scans the article URL path first, then the originating RSS feed URL as fallback for outlets whose URLs do not expose a section (HuffPost, NPR, Washington Times, Daily Caller).

| topic | topic_group | typical signal |
|---|---|---|
| politics | political | `/politics/`, `/election/`, `/congress/`, NPR feed `1014` |
| us | political | `/us-news/`, `/us/`, `/national/`, NPR feed `1003` |
| world | political | `/world/`, `world.xml`, `/world-news/`, `australia-news`, `uk-news` |
| opinion | political | `/opinion/`, `/op-ed/`, `commentisfree`, `/voices/` |
| business | non-political | `/business/`, `/money/`, `/market/`, `/finance/` |
| tech | non-political | `/tech/`, `/science/`, `/ai-/` |
| health | non-political | `/health/`, `covid`, `medic`, `wellness`, `environment` |
| entertainment | non-political | `/entertain/`, `celebrit`, `movie`, `music`, `tv-` |
| sports | non-political | `/sport/`, `outkick`, `nfl`, `nba`, `mlb`, `soccer`, `olymp` |
| lifestyle | non-political | `/food/`, `/travel/`, `/home/`, `fashion` |
| general | uncategorized | generic "News" feeds (NPR `1001`, Fox `latest.xml`, NYPost `/feed/`, Washington Examiner `/feed`, Washington Times `/news/`, Daily Caller `/feed/`) |

**Why `uncategorized` is a separate group.** Articles that arrive only through an outlet's generic news feed have no publisher-provided section signal, and we deliberately do not fold them into `political` to avoid asserting a topic we have not verified. They may be reclassified later by the LLM annotation step.

`topic` is descriptive metadata only and is **not** a target variable or a ground-truth label.

## Pipeline

```
RSS feeds
  -> URL collection            (src/crawl.py)
  -> article extraction        -> data/processed/articles.jsonl
  -> body cleaning             -> data/processed/articles_clean.jsonl  (src/cleaning.py + scripts/clean_articles.py)
  -> sentence split            -> data/processed/sentences.jsonl       (src/sentence_split.py)
  -> HF proxy subjectivity     -> data/processed/proxy_predictions.jsonl  (src/proxy_label.py)
  -> LLM sentence annotation   -> data/processed/llm_annotations.jsonl    (src/annotate_llm.py)
  -> VLM image annotation      -> data/processed/vlm_annotations.jsonl    (src/annotate_vlm.py)
  -> EDA + agreement analysis  -> data/analysis/*                         (src/analyze.py, notebooks/eda.ipynb)
  -> fine-tune datasets        -> data/finetune/proxy/{train,val,test}.jsonl  (src/build_finetune.py)
                                  data/finetune/vlm/{train,val,test}.jsonl
  -> README report
```

**Body cleaning** (`src/cleaning.py`) applies before sentence splitting. The pipeline went through three audit passes (seeds 42, 99, 7) and a risk verification run, documented in `data/analysis/audit_results.md` and `data/analysis/audit_results_v2.md`.

Cleaning layers (in order):
1. **Unicode normalization** — curly quotes and en/em-dashes normalized to ASCII equivalents.
2. **Block-drop** — `MORE LINKS` section in Daily Caller articles drops the marker plus up to 10 following lines.
3. **Blacklist-based line removal** — two levels:
   - *Global*: CTAs (`"click here"`, `"download now"`), wire service bylines (`"associated press writer/writers"`, `"reuters contributed"`, `"ap writers"`), subscribe/newsletter prompts (`"subscribe to"`, `"stay up to date with our"`), social media fragments (`"pic.twitter.com/"`, tweet attribution regex `^- Name (@handle) Month DD, YYYY`), audio-player CTAs (`"clicking the blue play button"`, `"listen to the full story"`), helpline links, and more.
   - *Per-outlet*: Fox News podcast CTAs and download prompts; Daily Caller DCNF syndication text and spent-at-DCNF bio lines; NPR newsletter chrome and Up First mentions; NY Post Google CTAs; Washington Examiner author bio signals; Washington Times AI-disclosure lines (`"constructed with the assistance of artificial intelligence"`, `"ai news desk"`).
4. **Regex patterns** — global email drop (`\S+@\S+\.\S+`); tweet attribution line; emoji-prefixed lines (`^-?\s*[emoji]` — NPR audio chapter markers like `🎧 …`); Daily Caller spent-at-outlet regex.
5. **Trailing bio heuristic** — last non-empty paragraph ≤ 600 chars matching bio-signal terms is dropped.
6. **Outlet name masking** — all outlet names and aliases replaced with `[OUTLET]` token. Masking is applied to *all* articles (not just self-references) to prevent cross-outlet leakage. Source-restricted aliases (`"Caller"` for Daily Caller, `"Screencaps"` for Fox, `"Decider"` for NY Post) are only applied within the owning outlet's articles to avoid false positives.
7. **Cross-outlet references deliberately kept** — mentions of non-corpus outlets (Washington Post, NYT, CNN, MSNBC, etc.) are *not* masked. When an outlet references or criticizes another outlet by name, that is itself a bias-relevant editorial signal. See `TODO_IF_I_HAD_TIME.md` for full rationale.

**Sentence splitting** (`src/sentence_split.py`) runs after cleaning using spaCy `en_core_web_sm`. Splitting is phrase-aware: fragments of ≤ 3 whitespace tokens (e.g. `"hah!"`, `"oh no!"`) are never emitted as isolated rows because they carry pragmatic signal (sarcasm, emphasis, reaction) that becomes uninterpretable without context. Instead they are **bridged**: appended to the preceding long sentence *and* prepended to the following long sentence, so each appears in two consecutive output rows. Consecutive short fragments are merged into a single bridge block before attachment (e.g. `"hah! oh no!"` is one block, not two). A fragment at the very start or end of an article is attached to its single available neighbor only. The output schema is `{sentence_id, article_id, sentence_index, text, n_chars, n_tokens_est}`.

## Models

### Proxy classifier (Step: proxy_label)
- **`GroNLP/mdebertav3-subjectivity-english`** (Hugging Face, CheckThat 2023 Task 2).
- Outputs **OBJ / SUBJ** at the sentence level.
- Input: single cleaned sentence text only. No outlet name, URL, title, or image metadata is passed to the model; these are preserved in the output for analysis only.
- Used as a **proxy for subjective / opinionated framing**, not as a complete media-bias detector. OBJ ≠ unbiased; SUBJ ≠ biased. Opinionated or emotionally loaded language is one signal of framing bias, not proof of it. Agreement with LLM silver annotations is analyzed separately.

### LLM annotator (Step: annotate_llm)
- **OpenAI `gpt-5.4-mini`** (verified 2026-06-01; snapshot pin `gpt-5.4-mini-2026-03-17`).
  - Context window: **400,000 tokens**, max output: **128,000 tokens**.
  - Endpoint: `v1/chat/completions` via **Batch API** (50% cost discount, async, up to 24h).
  - Structured Outputs (JSON schema) used for reliable label parsing.
- **Workflow:** `submit` → `status` → `fetch` (three subcommands in `src/annotate_llm.py`).
  - `submit` builds a JSONL of 8,561 requests, uploads to OpenAI Files, creates batch, saves `data/processed/llm_batch_state.json`.
  - `status` polls the batch object for completion.
  - `fetch` downloads the output file, joins via `custom_id` (= `sentence_id`), writes `data/processed/llm_annotations.jsonl`.
- **Input to the model:** only cleaned sentence text (`prompts/llm_sentence_annotation.txt`). Outlet name, URL, title, and image metadata are never sent to the model.
- **LLM labels = silver / reference annotations** — not gold. Label space: `OBJ` / `SUBJ` (aligned with proxy).
- **Prompt design:** CheckThat 2023 Task 2 prescriptive criteria (Ruggeri et al., 2023) verbatim; 8 edge-case few-shot examples; system/user split; `prompts/llm_response_schema.json` strict JSON schema.
- **Results (2026-06-03):** 8,561 sentences annotated, 0 failures. OBJ: 6,497 (75.9%) / SUBJ: 2,064 (24.1%). Left block: 22.8% SUBJ; right block: 25.6% SUBJ. Mean confidence: 0.930. Cost: ~$0.88 (batch discount). Proxy–LLM agreement: **85.3%** (confusion: OBJ→OBJ 6,287 / OBJ→SUBJ 1,052 / SUBJ→OBJ 210 / SUBJ→SUBJ 1,012).

### VLM annotator (Step: annotate_vlm)
- **OpenAI `gpt-5.4-mini`** (vision mode; snapshot pin `gpt-5.4-mini-2026-03-17`).
  - Endpoint: `v1/chat/completions` via **Batch API**.
  - Structured Outputs (JSON schema) used for reliable label parsing.
- **Workflow:** `submit` → `status` → `fetch` (three subcommands in `src/annotate_vlm.py`).
- **Images are NOT sent as URLs** (CLAUDE.md Rule 6). Images are downloaded → resized to max 1024px → JPEG q85 → base64-encoded inline. Cached under `data/raw/images/`. `image_url` stays as dataset metadata only.
- **Input to the model:** inline base64 image + article title + lead paragraph. Outlet name, URL, and topic are never sent.
- **Label space:** `OBJ` / `SUBJ` (aligned with proxy and LLM). Prompt design: visual framing criteria adapted from Ruggeri et al. (2023); 5 few-shot text examples; `prompts/vlm_response_schema.json` with 4 output fields (`vlm_label`, `vlm_rationale`, `vlm_confidence`, `image_description`).
- **Results (2026-06-03):** 292 articles annotated (4 no-image, 1 stale 404 skipped), 0 failures. OBJ: 236 (80.8%) / SUBJ: 56 (19.2%). Left block: 21.8% SUBJ; right block: 16.6% SUBJ. Mean confidence: 0.867. Cost: ~$0.05 (batch discount).

## Repository layout
```
media-bias-pipeline/
├── CLAUDE.md                       # project rules (logging, conventions)
├── README.md
├── requirements.txt
├── .env.example                    # .env is gitignored
├── .gitignore
├── ai_usage/step_logs.md           # append-only AI-decision log
├── prompts/                        # LLM + VLM prompt templates
├── src/                            # crawl, split, proxy_label, annotate_llm, annotate_vlm, analyze, utils
├── data/
│   ├── raw/html/                   # raw fetched HTML (gitignored)
│   ├── processed/                  # *.jsonl pipeline outputs
│   └── analysis/                   # tables, metrics, figures
└── notebooks/eda.ipynb
```

## Required outputs
- `data/processed/articles.jsonl`
- `data/processed/articles_clean.jsonl`
- `data/processed/sentences.jsonl`
- `data/processed/proxy_predictions.jsonl`
- `data/processed/llm_annotations.jsonl`
- `data/processed/vlm_annotations.jsonl`
- `data/analysis/agreement_metrics.json`
- `data/analysis/disagreement_examples.csv`
- `data/finetune/proxy/{train,val,test}.jsonl` + `splits_manifest.json`
- `data/finetune/vlm/{train,val,test}.jsonl` + `splits_manifest.json`
- `data/finetune/dataset_card.md`
- `README.md`, `prompts/`, `ai_usage/step_logs.md`

## Analysis plan (`src/analyze.py` + `notebooks/eda.ipynb`)
1. **Dataset overview** — article count, sentence count, outlet/block distribution, image availability.
2. **Proxy distribution** — OBJ/SUBJ counts overall and per outlet block.
3. **LLM distribution** — objective / subjective_framing overall and per outlet block.
4. **Agreement analysis** — confusion matrix, precision, recall, F1, Cohen's κ, using **LLM labels as silver / reference annotations** (not gold).
5. **Disagreement analysis** — proxy false positives and false negatives vs. the LLM reference.
6. **Sentence length** — short / medium / long buckets vs. subjectivity rate.
7. **VLM analysis** — visual framing label distribution and selected image/text examples.
8. *(Optional, later)* Rationale / token analysis.

## Setup
```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m spacy download en_core_web_sm   # required for sentence splitting
Copy-Item .env.example .env       # fill OPENAI_API_KEY, USER_AGENT, etc.
```

## Run
```powershell
python src/crawl.py
python scripts/clean_articles.py
python src/sentence_split.py
python src/proxy_label.py
python src/annotate_llm.py
python src/annotate_vlm.py
python src/analyze.py
python src/build_finetune.py all
```

## Conventions & guarantees (see [CLAUDE.md](CLAUDE.md))
- **No `config.yaml`.** All runtime settings come from `.env` (and small constants in `src/`).
- `.env` is gitignored; `.env.example` is committed.
- Every critical AI-assisted decision is logged forward-only as a new entry in [ai_usage/step_logs.md](ai_usage/step_logs.md).
- All prompts live under `prompts/`.

## Claims we are careful **not** to make
- LLM labels are **silver / reference annotations**, not gold.
- Outlet-block differences are **descriptive, not causal**.
- **Subjectivity ≠ bias**; it is a proxy signal for one facet of opinionated framing.
- We do **not** claim classifier-grade accuracy from this small dataset.

## Report

### Why this sub-task

**Sentence-level subjective / opinionated framing** is grounded in CheckThat 2023 Task 2 (Ruggeri et al., 2023) — a published, reproducible benchmark with prescriptive annotation criteria. It meets the exam's three conditions:

- **Tractable in the time budget.** Sentence-length inputs are short and cheap to annotate via the OpenAI Batch API (~$0.88 for 8,561 sentences). A well-scoped HuggingFace proxy model exists with the same OBJ/SUBJ label space, enabling a direct agreement analysis. No multi-label schema, no entity resolution, no external databases needed.
- **Measurable from text.** A sentence can be annotated for subjective / evaluative language using text alone. The signal (evaluative framing, loaded diction, intensifiers) is self-contained in the sentence string.
- **Measurable from images.** The same OBJ/SUBJ frame applies to visual content: a VLM can assess whether an image composition, subject pose, or editorial crop conveys evaluative intent, and return a label in the same space. This enables a direct text ↔ image comparison (see Findings §4: text and visual framing are largely independent — only 9 of 292 articles are SUBJ in both modalities).

Subjectivity is used as a *proxy signal for opinionated framing*, not as a definition of bias. The dataset enables a downstream fine-tuning task; it does not claim to measure all facets of media bias.

### Why the proxy classifier is a reasonable fit

`GroNLP/mdebertav3-subjectivity-english` (HuggingFace, CheckThat 2023 Task 2) was trained on the same annotation criteria used for the LLM silver annotations. The etiket spaces are 1:1 aligned (OBJ / SUBJ), so the confusion matrix is directly interpretable without a mapping step.

The model is **related but not identical** to the target task in exactly the way the exam asks for: it operates purely at the lexical/syntactic surface, and is therefore expected to miss pragmatically loaded phrases that are grammatically neutral. This prediction held: proxy recall is 0.490 vs. LLM SUBJ recall (proxy misses 1,052 LLM-SUBJ sentences), while precision is high (0.828) — the proxy fires conservatively. Example failure cases:

| Sentence | Why proxy fails |
|---|---|
| *"…the area right in front of historic Union Station became infested with the dregs of society."* | Declarative syntax; loaded diction captured by LLM, not proxy. |
| *"Trump's nearly $2 billion MAGA slush fund is his most brazen act of self-dealing yet…"* | "Slush fund", "most brazen" — evaluative, but surface-neutral to a lexical classifier. |
| *"Doing so eight times in less than five years is wildly impressive."* | Author-evaluative intensifier, not a subjective sentence syntactically. |

Where disagreement is expected to be highest: stylistically loaded outlets (Fox News, Washington Examiner) where the proxy systematically under-calls subjectivity (κ = 0.555 and 0.589 respectively, with ~10 ppt LLM–proxy gaps).

### Shortcuts taken

- **RSS-only crawler** — no sitemap, Wayback, or archive API; collection is point-in-time (June 2026) with no diachronic coverage.
- **Keyword-rule topic taxonomy** — deterministic first-match-wins; BERTopic or LLM-based topic inference would be more robust (see `TODO_IF_I_HAD_TIME.md`).
- **Outlet convenience sample** — 8 outlets, binary left/right block; outlet_block is an abstraction, not a ground-truth ideology label.
- **spaCy `en_core_web_sm` sentence splitter** — fast but not transformer-grade; fragment bridging was added manually to compensate.
- **Single hero image per article** — VLM sees only the first extracted image; inline galleries and embedded media are ignored.
- **Single LLM snapshot, single pass** — `gpt-5.4-mini-2026-03-17` with no ensemble and no multiple-annotator reliability check.
- **300 articles** — convenience volume; outlet-level n is small for some outlets (Daily Caller: 20 VLM-annotated articles).

### Risks of the approach

- **Subjectivity ≠ bias.** The pipeline measures one facet of opinionated framing. Other bias types (source selection, omission, headline framing, loaded imagery) are not captured.
- **LLM as silver reference.** LLM labels are produced by `gpt-5.4-mini`; evaluating them with a close-family model risks circular agreement. An independent human annotation sample would be needed to validate label quality.
- **Block-level inference is underpowered.** Outlet-within-block variance is larger than block-level variance (Findings §4). Any aggregate "left vs. right" observation is descriptive and confounded by outlet editorial style.
- **Temporal and topic drift.** Crawl is a point-in-time snapshot; topic distribution is driven by what happened to be published during the crawl window, not a balanced editorial sample.
- **VLM image context is partial.** The model receives only the hero image + article title + lead paragraph. Caption text, image source credit, and article body context are absent — the VLM may mis-assess framing intent when the image is generic stock photography.
- **Cross-outlet references as confound.** Outlet names are masked but cross-outlet criticism (e.g., one outlet naming another) is deliberately retained as a bias-relevant signal (cleaning layer 7). This could also act as a topical confound if certain outlets are disproportionately cited.

### AI usage during development

Claude Code (Claude Opus 4.7) was used as the primary coding assistant throughout this project. Every discrete action — scaffold decisions, script writing, cleaning audit passes, model verification, analysis design — was logged forward-only in [`ai_usage/step_logs.md`](ai_usage/step_logs.md) (36 steps, ~480 lines), as required by CLAUDE.md Rule 1. Full conversation logs are under `ai_usage/chats/`.

Data annotation was performed by external models:
- **LLM and VLM annotation:** OpenAI `gpt-5.4-mini` (snapshot `gpt-5.4-mini-2026-03-17`) via Batch API with Structured Outputs — 8,561 sentences (LLM) and 292 articles (VLM). Model ID, context window, and supported endpoints were verified against OpenAI docs before use (Step 22, step_logs.md).
- **Proxy classifier:** `GroNLP/mdebertav3-subjectivity-english` (HuggingFace) — run locally via `transformers` pipeline.

### Annotation prompts

The prompts used by the LLM and VLM during the annotation step are stored as standalone files under `prompts/` — not inlined in Python code. They are part of the pipeline's data inputs, not development tooling:

- `prompts/llm_sentence_annotation.txt` — system + user prompt for sentence-level OBJ/SUBJ classification; includes CheckThat 2023 Task 2 prescriptive criteria and 8 few-shot examples.
- `prompts/llm_response_schema.json` — JSON schema enforced via OpenAI Structured Outputs for the LLM response.
- `prompts/vlm_image_annotation.txt` — prompt for visual framing assessment; receives inline base64 image + article title + lead paragraph.
- `prompts/vlm_response_schema.json` — JSON schema for the VLM response (`vlm_label`, `vlm_rationale`, `vlm_confidence`, `image_description`).

---

## Findings (descriptive)

> All observations below are **descriptive**. Block-level or outlet-level differences are **not causal** claims. LLM labels are **silver / reference annotations**, not gold. Subjectivity is a **proxy signal** for one facet of opinionated framing — not a synonym for "bias".

### 1) Overall proxy ↔ LLM agreement

| Metric | Value |
|---|---|
| Total sentences | 8,561 |
| Proxy SUBJ rate | 14.3% (1,222) |
| LLM SUBJ rate | 24.1% (2,064) |
| Accuracy | 85.3% |
| Cohen κ | 0.532 (moderate) |
| SUBJ precision (vs. LLM silver) | 0.828 |
| SUBJ recall (vs. LLM silver) | 0.490 |
| SUBJ F1 | 0.616 |
| LLM mean confidence | 0.930 |

**Confusion matrix (proxy → LLM silver):**

| | LLM OBJ | LLM SUBJ |
|---|---:|---:|
| **Proxy OBJ** | 6,287 | 1,052 |
| **Proxy SUBJ** | 210 | 1,012 |

The dominant error is a single direction: the proxy labels 1,052 sentences as OBJ that the LLM silver labels as SUBJ. Proxy precision is high (82.8%) but recall is low (49.0%) — **the proxy systematically under-calls subjectivity**, missing evaluative language that appears structurally neutral at the lexical/syntactic level.

### 2) Examples where the LLM is more sensitive (proxy = OBJ, LLM = SUBJ, conf ≥ 0.99)

| Outlet / Block | Sentence | LLM rationale (summary) |
|---|---|---|
| huffpost / left | *"Trump's nearly $2 billion MAGA slush fund is his most brazen act of self-dealing yet and one of the most corrupt schemes ever launched by a president."* | "slush fund", "most brazen", "most corrupt" — strongly evaluative author judgement. |
| dailycaller / right | *"…the area right in front of historic Union Station became infested with the dregs of society."* | "infested with the dregs of society" — derogatory, loaded language toward a social group. |
| foxnews / right | *"Doing so eight times in less than five years is wildly impressive."* | "wildly impressive" — author-evaluative phrase with intensifier. |

All three receive proxy OBJ scores between 0.50–0.91. The proxy misses pragmatically loaded phrases ("slush fund", "dregs of society", "wildly impressive") because they are grammatically similar to neutral constructions. The LLM captures the evaluative intent.

### 3) Block × topic analysis (LLM SUBJ %)

| Block | topic_group | n | LLM SUBJ % | Proxy SUBJ % | Agreement % |
|---|---|---:|---:|---:|---:|
| left | political | 3,880 | 24.1 | 13.4 | 84.8 |
| left | non-political | 206 | 20.9 | 14.6 | 89.8 |
| left | uncategorized | 435 | 12.2 | 5.8 | 89.4 |
| right | political | 2,055 | 20.5 | 11.2 | 86.4 |
| right | non-political | 1,038 | **37.7** | 29.2 | 81.3 |
| right | uncategorized | 947 | 23.6 | 12.1 | 86.3 |

Topic breakdown (LLM SUBJ %, n ≥ 30):

| Topic | Left | Right | Δ (right − left) |
|---|---:|---:|---:|
| opinion | 57.0% (n=446) | 61.8% (n=212) | +4.8 |
| sports | 47.6% (n=63) | 49.9% (n=603) | +2.3 |
| tech | — | 27.9% (n=136) | — |
| politics | **24.6%** (n=1,728) | 15.6% (n=1,350) | −9.0 |
| world | 17.4% (n=941) | 16.9% (n=65) | ≈0 |
| us | 11.8% (n=765) | 15.9% (n=428) | +4.1 |
| business | 2.8% (n=71) | 13.0% (n=69) | +10.2 |
| general | 12.2% (n=435) | 23.6% (n=947) | +11.4 |

Key observations:
- **Opinion** tops both blocks (~57–62%) — expected; confirms the subjectivity signal is calibrated.
- **Sports** is unexpectedly high (~48–50%) in both blocks. This reflects genre convention (dramatic, evaluative commentary) rather than political framing bias — a downstream classifier should be aware of this.
- In left-block articles, **politics** carries the highest SUBJ load (24.6%); driven by HuffPost and Guardian opinion-adjacent political pieces.
- Right-block non-political content (sports, tech, entertainment, business) carries significantly higher evaluative language than left-block equivalents (+16.8 ppt). Right-block political SUBJ is lower (15.6%) than left-block political SUBJ (24.6%).

### 4) Outlet-level analysis

| Outlet | Block | n sentences | LLM SUBJ % | Proxy SUBJ % | Agreement % | κ | Proxy FN (missed SUBJ) |
|---|---|---:|---:|---:|---:|---:|---:|
| foxnews | right | 1,309 | **36.5** | 26.4 | 80.6 | 0.555 | 193 |
| washingtonexaminer | right | 651 | **31.2** | 20.4 | 84.0 | 0.589 | 87 |
| theguardian | left | 2,368 | 28.0 | 18.1 | 84.7 | 0.574 | 299 |
| dailycaller | right | 441 | 26.3 | 14.7 | 86.6 | 0.598 | 55 |
| huffpost | left | 1,392 | 18.8 | 5.8 | 85.3 | 0.341 | 193 |
| nypost | right | 818 | 17.1 | 7.3 | 86.8 | 0.398 | 94 |
| npr | left | 761 | 13.7 | 8.4 | 88.2 | 0.402 | 65 |
| washingtontimes | right | 821 | **11.9** | 5.5 | **90.4** | 0.403 | 66 |

Outlet-level visual framing (VLM, article-level):

| Outlet | n articles | VLM SUBJ % | VLM mean conf |
|---|---:|---:|---:|
| nypost | 31 | **35.5** | 0.855 |
| huffpost | 61 | 24.6 | 0.860 |
| theguardian | 64 | 23.4 | 0.862 |
| dailycaller | 20 | 15.0 | 0.839 |
| washingtontimes | 34 | 11.8 | 0.877 |
| foxnews | 35 | 11.4 | 0.886 |
| washingtonexaminer | 25 | 8.0 | 0.868 |
| npr | 22 | **9.1** | 0.900 |

Descriptive patterns:
- **Highest LLM SUBJ** (text): Fox News (36.5%) and Washington Examiner (31.2%). Both show large LLM–proxy gaps (~10 ppt), suggesting these outlets use grammatically neutral but pragmatically loaded constructions that the proxy classifier misses.
- **Washington Times** records the lowest LLM SUBJ (11.9%) and highest agreement (90.4%) — consistent with a wire-report, declarative writing style.
- **HuffPost** has the largest proxy blind spot: only 5.8% proxy-SUBJ vs. 18.8% LLM-SUBJ (κ = 0.341, lowest of all outlets). Its evaluative language is lexically subtle enough to fool the proxy.
- **NPR** (text) is the most measured outlet at 13.7% SUBJ; highest VLM confidence (0.900) — visually neutral images as well.
- **Outlet-level variance is much larger than block-level variance** (left vs. right: +2.8 ppt). Aggregating to block level obscures outlet-specific editorial style differences.
- **VLM vs. text dissociation:** Visual framing and text framing do not co-vary reliably. NY Post and HuffPost have relatively high VLM SUBJ images despite being in opposite blocks; Fox News and Washington Examiner have unexpectedly low VLM SUBJ despite high text SUBJ. Text–image cross-table (article majority): 218 articles are OBJ-text / OBJ-image; 47 are OBJ-text / SUBJ-image; only 9 are SUBJ-text / SUBJ-image — confirming that image and text framing signals are largely independent in this corpus.
