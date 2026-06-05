# Media Bias Pipeline

Small end-to-end pipeline that produces a **fine-tuning-ready dataset for sentence-level media bias detection** from English news articles. Built as a PhD technical-exam deliverable (~4–6h scope).

## Repository layout
```
media-bias-pipeline/
├── CLAUDE.md                       # project rules (logging, conventions)
├── README.md
├── requirements.txt
├── .env.example                    # .env is gitignored
├── .gitignore
├── ai_usage/step_logs.md           # append-only AI-decision log
├── ai_usage/chats/                 # full conversation logs per session
├── prompts/                        # LLM + VLM annotation prompt files
├── src/                            # crawl, split, proxy_label, annotate_llm, annotate_vlm, analyze, build_finetune, utils
├── scripts/                        # clean_articles, sample_for_audit, sample_for_blacklist
├── data/
│   ├── raw/html/                   # raw fetched HTML (gitignored)
│   ├── raw/images/                 # downloaded article images (gitignored)
│   ├── processed/                  # *.jsonl pipeline outputs
│   ├── analysis/                   # tables, metrics, figures, audit samples
│   └── finetune/                   # proxy/ and vlm/ fine-tune datasets
└── notebooks/eda.ipynb
```

## Setup
```bash
python -m venv .venv && source .venv/bin/activate   # macOS/Linux
# Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m spacy download en_core_web_sm             # required for sentence splitting
cp .env.example .env                                # fill OPENAI_API_KEY, USER_AGENT, etc.
```

## Run
```bash
python src/crawl.py
python scripts/clean_articles.py
python src/sentence_split.py
python src/proxy_label.py
python src/annotate_llm.py submit   # submit batch
python src/annotate_llm.py status   # poll
python src/annotate_llm.py fetch    # download results
python src/annotate_vlm.py submit
python src/annotate_vlm.py status
python src/annotate_vlm.py fetch
python src/analyze.py
python src/build_finetune.py all
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

## Chosen sub-task
**Sentence-level subjective / opinionated framing bias** in English news articles.
Subjectivity is treated as a *proxy signal* for opinionated framing — not as a synonym for "media bias". The dataset is designed so a downstream classifier can be fine-tuned on sentence-level subjective-vs-objective framing, with article-level metadata (outlet, outlet block, main image) available for richer analysis.

## Collection plan
- **Total:** 300 articles via RSS feeds.
- **150** from a left-leaning outlet block, **150** from a right-leaning outlet block.
- Concrete outlet list is chosen and documented in `src/crawl.py` (and logged in `ai_usage/step_logs.md`).
- **`outlet_block ∈ {left, right}` is exploratory metadata only**, not a ground-truth ideology label and not the target variable. Block-level differences are descriptive, never causal.

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

**Why `uncategorized` is a separate group.** Articles that arrive only through an outlet's generic news feed have no publisher-provided section signal, and we deliberately do not fold them into `political` to avoid asserting a topic we have not verified.

`topic` is descriptive metadata only and is **not** a target variable or a ground-truth label.

## Models at a glance

| Role | Model | Step |
|---|---|---|
| Proxy classifier (text) | `GroNLP/mdebertav3-subjectivity-english` (HuggingFace) | `src/proxy_label.py` |
| LLM annotator (text, silver) | OpenAI `gpt-5.4-mini` (`gpt-5.4-mini-2026-03-17`) — Batch API + Structured Outputs | `src/annotate_llm.py` |
| VLM annotator (image+text, silver) | OpenAI `gpt-5.4-mini` vision (`gpt-5.4-mini-2026-03-17`) — Batch API + Structured Outputs | `src/annotate_vlm.py` |

## Unit choices
| Concern | Unit |
|---|---|
| Collection | article |
| Text fine-tuning | sentence |
| Proxy classifier input | sentence (only) |
| LLM annotator input | sentence (only) |
| VLM input | article main image + title + lead paragraph |
| Metadata (not features) | source, outlet_block, title, url, image_url, feed_url, topic, topic_group |

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

### Proxy classifier
- **`GroNLP/mdebertav3-subjectivity-english`** (HuggingFace, CheckThat 2023 Task 2).
- Label space: **OBJ / SUBJ** per sentence.
- Input: single cleaned sentence text only — no outlet name, URL, title, or image metadata.
- Used as a proxy for subjective / opinionated framing. OBJ ≠ unbiased; SUBJ ≠ biased.

### LLM annotator
- **OpenAI `gpt-5.4-mini`** snapshot pin `gpt-5.4-mini-2026-03-17`. Context: 400K tokens, max output: 128K tokens.
- Endpoint: `v1/chat/completions` via **Batch API** (50% cost discount, async).
- Structured Outputs (JSON schema) for reliable label parsing.
- Workflow: `submit` → `status` → `fetch` (`src/annotate_llm.py`).
- Input: cleaned sentence text only. Outlet name, URL, title, image are never sent.
- Labels are **silver / reference annotations** — not gold.

### VLM annotator
- **OpenAI `gpt-5.4-mini` vision** snapshot pin `gpt-5.4-mini-2026-03-17`.
- Endpoint: `v1/chat/completions` via **Batch API**. Structured Outputs enforced.
- Workflow: `submit` → `status` → `fetch` (`src/annotate_vlm.py`).
- Images downloaded → resized to max 1024px → JPEG q85 → base64-encoded inline. **Never sent as URLs.**
- Input: inline base64 image + article title + lead paragraph. Outlet name, URL, topic never sent.
- Label space: **OBJ / SUBJ** — aligned with proxy and LLM labels.

## Annotation prompts

The prompts below are stored as standalone files under `prompts/` and reproduced here verbatim. JSON response schemas live alongside as `prompts/llm_response_schema.json` and `prompts/vlm_response_schema.json`.

### LLM — sentence-level OBJ/SUBJ classification

> File: `prompts/llm_sentence_annotation.txt`

```
--- system ---
You are a strict annotator. Your task is to classify a single English news sentence as OBJ (objective) or SUBJ (subjective), following the CheckThat 2023 Task 2 prescriptive annotation guidelines (Ruggeri et al., 2023).

## Definitions

A sentence is SUBJ if it contains any of the following (judge the author's own communicative act, not what is being reported):

(i)   Explicit personal opinion — the author directly endorses, condemns, or evaluates a person, event, or state of affairs. Rhetorical questions count as opinions.
(ii)  Sarcasm or irony — language whose literal meaning is undercut by the opposite intended meaning.
(iii) Exhortations or personal auspices — the author urges, recommends, or expresses wishes about what should happen.
(iv)  Discriminating or downgrading expressions — language that demeans, belittles, or stereotypes a person or group, whether explicit or through loaded vocabulary.
(v)   Rhetorical figures that convey a subjective stance — metaphors, hyperbole, or other figurative language used to express the author's attitude rather than to describe.
(vi)  Speculations that draw conclusions — the author infers, predicts, or asserts an unverified claim as if it were established.
(vii) Intensifiers attributable to the author — adverbs and adjectives that amplify a claim beyond neutral description (e.g., "outrageous", "absolutely", "shockingly", "total disaster") when the author uses them, not a quoted source.

A sentence is OBJ if:

(vii-OBJ) The author expresses their own emotions or feelings but does NOT simultaneously convey an opinion on another matter — pure emotional disclosure without evaluative judgment → OBJ.
(viii-OBJ) The opinion or evaluative content is attributable to a third party, including direct quotes, paraphrased attribution ("Senator Smith said …"), or reported speech — the author is merely relaying someone else's stance → OBJ.

## Annotation rules

1. Judge the sentence **in isolation** — do not infer context from surrounding sentences or article topic.
2. Use only the sentence text; apply no external knowledge about the speaker, outlet, or event.
3. Label the **author's communicative stance in this sentence only**, not the general topic.
4. When criteria conflict, apply the most specific criterion that fits.
5. Output **only** the JSON object — no explanation outside the JSON fields.

## Examples

Sentence: "The Senate voted 52-48 on Tuesday to confirm the nominee."
{"llm_label": "OBJ", "llm_rationale": "Factual report of a vote count — no author opinion, no intensifiers, no evaluative language.", "llm_confidence": 0.97}

Sentence: "This decision is a total disaster for working families."
{"llm_label": "SUBJ", "llm_rationale": "Author uses intensifier 'total disaster' to directly condemn the decision — criterion (vii) + (i).", "llm_confidence": 0.96}

Sentence: "'The policy will hurt the economy,' Senator Smith said."
{"llm_label": "OBJ", "llm_rationale": "Evaluative claim is attributed to Senator Smith via direct quote — criterion (viii-OBJ); author stance is neutral relay.", "llm_confidence": 0.95}

Sentence: "The administration's response was shockingly inadequate."
{"llm_label": "SUBJ", "llm_rationale": "Author uses intensifier 'shockingly' and evaluative 'inadequate' to condemn the response — criterion (vii).", "llm_confidence": 0.95}

Sentence: "I felt a quiet sadness watching the ceremony."
{"llm_label": "OBJ", "llm_rationale": "Author discloses personal emotion but makes no evaluative judgment about another matter — criterion (vii-OBJ).", "llm_confidence": 0.88}

Sentence: "How can anyone defend such reckless spending?"
{"llm_label": "SUBJ", "llm_rationale": "Rhetorical question implies the spending is indefensible — criterion (i); rhetorical questions count as opinions.", "llm_confidence": 0.94}

Sentence: "If this trend continues, the party will surely collapse by November."
{"llm_label": "SUBJ", "llm_rationale": "Author speculates and asserts a conclusion ('surely collapse') as if established — criterion (vi).", "llm_confidence": 0.92}

Sentence: "The so-called reform package is nothing more than political theater."
{"llm_label": "SUBJ", "llm_rationale": "Author uses downgrading 'so-called' and dismissive metaphor 'political theater' to belittle the package — criteria (iv) + (v).", "llm_confidence": 0.96}

--- user ---
Sentence: "{sentence}"
```

Response schema fields: `llm_label` (`OBJ`/`SUBJ`), `llm_rationale` (string), `llm_confidence` (float 0–1).

### VLM — main-image visual framing classification

> File: `prompts/vlm_image_annotation.txt`

The user message carries the inline base64 JPEG image as a second content block (image_url type with base64 data URI), in addition to the text fields below.

```
--- system ---
You are a strict visual-framing annotator. Your task is to classify a news article's main image — judged together with the article's title and lead paragraph — as OBJ (objective / neutral framing) or SUBJ (subjective / opinionated framing), following prescriptive annotation guidelines adapted from CheckThat 2023 Task 2 (Ruggeri et al., 2023).

## Definitions

An image is SUBJ if the IMAGE ITSELF (or the image-text pairing) carries visually opinionated framing:

(i)   Emotionally loaded expression — the image features a subject with a strongly negative, contemptuous, mocking, or anguished facial expression selected or cropped to foreground that emotion.
(ii)  Symbolic or loaded prop — the image prominently features symbolic objects that carry political or ideological charge (e.g., torn flags, flames, cages, fists raised in anger, weapons displayed in non-documentary context).
(iii) Demeaning or diminishing framing — angle, crop, or lighting is used to belittle, tower over, or dehumanize a subject (e.g., extreme low/high angle emphasizing power imbalance, unflattering isolating crop).
(iv)  Dramatic or manipulative editing — heavy colour grading, montage, illustration, or caricature that amplifies emotional tone beyond neutral documentary.
(v)   Image amplifies editorial stance — the image selection intensifies or editorializes the text's sentiment rather than neutrally illustrating the event.

An image is OBJ if:

(vi-OBJ) The image is neutral photo-journalism — wide or medium shot, even lighting, straightforward documentary capture of the event or subject described in the text.
(vii-OBJ) The image is generic stock or a standard institutional portrait — unrelated to a specific editorial angle, low specificity.
(viii-OBJ) The image illustrates the text without amplifying or contradicting its tone.

## Annotation rules

1. Judge only on what is **visually present** in the image — do not speculate about the outlet, photographer, or publication source.
2. The title and lead are provided to assess image-text alignment; the PRIMARY subject of your label is the **image's own visual framing**.
3. A sensitive topic does NOT make an image SUBJ. Only deliberate framing choices that editorialize the topic make it SUBJ.
4. If the image is ambiguous or stock-generic, prefer OBJ with lower confidence.
5. Output ONLY the JSON object — no prose outside the JSON.

## Examples

Title: "City council votes to raise minimum wage"
Lead: "The council approved the measure 7-4 after a two-hour debate."
Image: A wide-angle photo of councillors seated at a dais during the meeting.
{"vlm_label": "OBJ", "image_description": "Wide shot of council chamber, officials seated at dais, neutral lighting.", "vlm_rationale": "Standard documentary photo of the event; neutral framing, no emotional loading — criterion (vi-OBJ).", "vlm_confidence": 0.93}

Title: "Senator faces backlash over climate vote"
Lead: "Critics accused the senator of ignoring scientific consensus."
Image: A heavily contrast-boosted close-up of the senator mid-grimace, dark vignette around the face.
{"vlm_label": "SUBJ", "image_description": "Extreme close-up of senator mid-grimace, high-contrast with dark vignette.", "vlm_rationale": "Dramatic crop and contrast editing foreground a negative expression, editorializing tone — criteria (i) + (iii) + (iv).", "vlm_confidence": 0.91}

Title: "Protest erupts outside parliament"
Lead: "Demonstrators gathered to oppose the new austerity bill."
Image: A wide street photo of a large crowd carrying placards, daylight.
{"vlm_label": "OBJ", "image_description": "Wide street photo of protest crowd carrying placards in daylight.", "vlm_rationale": "Neutral wide shot documenting the event without amplifying emotional angle — criterion (vi-OBJ).", "vlm_confidence": 0.87}

Title: "New immigration rules draw criticism"
Lead: "Advocacy groups warn the policy will separate families."
Image: A symbolic photo of a chain-link fence in dramatic red-orange sunset light, no people visible.
{"vlm_label": "SUBJ", "image_description": "Chain-link fence in dramatic red-orange sunset light, no people present.", "vlm_rationale": "Symbolic prop (fence) and dramatic lighting amplify the article's critical tone — criteria (ii) + (iv) + (v).", "vlm_confidence": 0.89}

Title: "Tech giant posts record quarterly profits"
Lead: "The company reported earnings of $28 billion, beating analyst forecasts."
Image: Standard corporate headshot of the CEO against a plain background.
{"vlm_label": "OBJ", "image_description": "Standard corporate headshot of executive against plain neutral background.", "vlm_rationale": "Generic institutional portrait, no editorial framing choices — criterion (vii-OBJ).", "vlm_confidence": 0.95}

--- user ---
Title: "{title}"
Lead: "{lead}"
```

Response schema fields: `vlm_label` (`OBJ`/`SUBJ`), `image_description` (string), `vlm_rationale` (string), `vlm_confidence` (float 0–1).

## Finetune output

Article-level, outlet-stratified 70/15/15 split (seed=42). All sentences from a single article land in one split — no leakage. Class balance retained raw; handle imbalance at fine-tune time (e.g., class weights, loss reweighting).

### Proxy dataset (`data/finetune/proxy/`)
Text-only sentence classifier. Label source: `llm_label` (LLM preferred on proxy↔LLM disagreement).

| Field | Type | Description |
|---|---|---|
| `sentence_id` | str | `<article_sha>:<index>` — unique sentence identifier |
| `article_id` | str | SHA of source article |
| `text` | str | Cleaned sentence, outlet name masked as `[OUTLET]` |
| `label` | str | `OBJ` or `SUBJ` |

| Split | Sentences | OBJ | SUBJ | SUBJ % |
|---|---:|---:|---:|---:|
| train | 6,007 | 4,522 | 1,485 | 24.7% |
| val | 1,278 | 968 | 310 | 24.3% |
| test | 1,276 | 1,007 | 269 | 21.1% |
| **total** | **8,561** | | | |

### VLM dataset (`data/finetune/vlm/`)
Multimodal article classifier. Label source: `vlm_label`. Images are base64 JPEG (max 1024px, q85) without `data:` URI prefix.

| Field | Type | Description |
|---|---|---|
| `article_id` | str | SHA of source article |
| `title` | str | Article headline |
| `lead` | str | First paragraph (cleaned) |
| `image_b64` | str | Base64-encoded JPEG (no `data:image/jpeg;base64,` prefix) |
| `image_mime` | str | `image/jpeg` |
| `label` | str | `OBJ` or `SUBJ` |

| Split | Articles | OBJ | SUBJ | SUBJ % |
|---|---:|---:|---:|---:|
| train | 204 | 166 | 38 | 18.6% |
| val | 44 | 33 | 11 | 25.0% |
| test | 44 | 37 | 7 | 15.9% |
| **total** | **292** | | | |

See `data/finetune/dataset_card.md` for split manifests and a HuggingFace `datasets` loader snippet.

## Report

### Why this sub-task

**Sentence-level subjective / opinionated framing** is grounded in CheckThat 2023 Task 2 (Ruggeri et al., 2023) — a published, reproducible benchmark with prescriptive annotation criteria. It meets the exam's three conditions:

- **Tractable in the time budget.** Sentence-length inputs are short and cheap to annotate via the OpenAI Batch API (~$0.88 for 8,561 sentences). A well-scoped HuggingFace proxy model exists with the same OBJ/SUBJ label space, enabling a direct agreement analysis. No multi-label schema, no entity resolution, no external databases needed.
- **Measurable from text.** A sentence can be annotated for subjective / evaluative language using text alone. The signal (evaluative framing, loaded diction, intensifiers) is self-contained in the sentence string.
- **Measurable from images.** The same OBJ/SUBJ frame applies to visual content: a VLM can assess whether an image composition, subject pose, or editorial crop conveys evaluative intent, and return a label in the same space. This enables a direct text ↔ image comparison (see Findings §4: text and visual framing are largely independent — only 9 of 292 articles are SUBJ in both modalities).

Subjectivity is used as a *proxy signal for opinionated framing*, not as a definition of bias. The dataset enables a downstream fine-tuning task; it does not claim to measure all facets of media bias.

### Why the proxy classifier is a reasonable fit

`GroNLP/mdebertav3-subjectivity-english` (HuggingFace, CheckThat 2023 Task 2) was trained on the same annotation criteria used for the LLM silver annotations. The label spaces are 1:1 aligned (OBJ / SUBJ), so the confusion matrix is directly interpretable without a mapping step.

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

---

## Results

> All observations are **descriptive**. Block- and outlet-level differences are **not causal** claims. LLM/VLM labels are **silver / reference annotations**, not gold. Subjectivity is a **proxy signal** for one facet of opinionated framing — not a synonym for "bias".
>
> Figures live under `data/analysis/figures/`; full derivations and per-cell outputs are in `notebooks/eda.ipynb`.

### Statistical methods

Five techniques appear in the EDA; rationale for each choice is given here so the numbers below are interpretable without re-running the notebook.

| Method | What it measures | Why used here (vs. alternative) |
|---|---|---|
| **Wilson 95 % CI** | Confidence interval for a proportion | Small n and mid-range rates make the Wald interval unreliable (can produce negative bounds); Wilson stays valid at n = 31. Used for NYP VLM-SUBJ. |
| **Cohen's κ** | Chance-corrected inter-annotator agreement | Accounts for the fact that two annotators who both prefer OBJ would agree often by luck alone. With 76 % OBJ labels here κ is pulled down by class prevalence, so F1-SUBJ is the more informative companion metric. |
| **Spearman ρ** | Rank correlation between two measurement sets | Used for article-level three-judge comparison (proxy, LLM, VLM SUBJ rates). Rank correlation is preferred over Pearson for proportion data because it does not assume a linear relationship or normal distribution. |
| **Mann-Whitney U** | Non-parametric two-group location test | Used to compare LLM rationale lengths across two groups. Character-count distributions are right-skewed; Mann-Whitney is more robust than a t-test, which assumes normality. |
| **Precision / Recall / F1** | Per-class classification agreement | F1-SUBJ is the headline metric because OBJ-class dominance inflates accuracy (85.3 % accuracy is trivially achievable by predicting OBJ always). Precision answers "of the proxy's SUBJ calls, how many did the LLM confirm?"; Recall answers "of the LLM's SUBJ labels, how many did the proxy catch?". |

### 1. Corpus

8,561 sentences across 300 articles (150 left-block / 150 right-block); 292 of 300 articles passed VLM annotation (5 skipped: 4 missing `image_url`, 1 stale 404 — Washington Times). All 8,561 LLM completions finished with `stop` — no truncation.

### 2. Proxy ↔ LLM agreement (sentence level)

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

The error is directional: **1,052 false negatives vs. 210 false positives**. Proxy precision is high (82.8%) but recall is low (49.0%) — the proxy under-calls subjectivity, missing evaluative language that is structurally neutral at the lexical/syntactic surface. The proxy almost never hallucinates SUBJ.

At disagreement points the LLM retains high confidence (mean 0.910 on FN cases); at false-positive points the proxy fires with mean score 0.638 — above threshold but only moderately confident. Disagreements reflect systematic model divergence, not random noise. Caveat: LLM confidence is anchored to the few-shot examples in `prompts/llm_sentence_annotation.txt` (range 0.88–0.97); proxy softmax lives on a different scale. Cross-model confidence comparisons here are descriptive, not calibrated.

### 3. Where the proxy misses

| Outlet / Block | Sentence | LLM rationale (summary) |
|---|---|---|
| huffpost / left | *"Trump's nearly $2 billion MAGA slush fund is his most brazen act of self-dealing yet and one of the most corrupt schemes ever launched by a president."* | "slush fund", "most brazen", "most corrupt" — strongly evaluative author judgement. |
| dailycaller / right | *"…the area right in front of historic Union Station became infested with the dregs of society."* | "infested with the dregs of society" — derogatory, loaded language toward a social group. |
| foxnews / right | *"Doing so eight times in less than five years is wildly impressive."* | "wildly impressive" — author-evaluative phrase with intensifier. |

All three receive proxy OBJ scores 0.50–0.91. The proxy misses pragmatically loaded phrases because they are grammatically similar to neutral constructions.

**Rationale-term log-odds analysis** (`notebooks/eda.ipynb` §4.2): LLM rationales for proxy-missed SUBJ sentences over-use abstract framing terms (`characterization`, `loaded`, `exhortation`, `downgrading`, `unverified`) while agreement-SUBJ rationales over-use surface-marker terms (`rhetorical`, `question`, `figurative`, `explicit`). The proxy has learned the visible surface cues; it has not learned context-dependent, single-token subjectivity signals. This contrast identifies exactly the type of hard examples that would most improve the proxy at fine-tune time.

### 4. Block × topic (LLM SUBJ %)

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

Opinion (~57–62%) tops both blocks — a calibration check confirming the subjectivity signal is sensible. Sports (~48–50%) is unexpectedly high in both blocks; this reflects genre convention (evaluative commentary is the norm in sports writing), not political framing. Left-block politics carries the highest SUBJ load in that block (24.6%), driven by HuffPost and Guardian opinion-adjacent political pieces. Right-block non-political content (sports, tech, entertainment, business) is markedly more evaluative than its left-block counterpart (+16.8 ppt).

### 5. Outlet level — text (LLM + proxy)

| Outlet | Block | n sentences | LLM SUBJ % | Proxy SUBJ % | Agreement % | κ | Proxy FN |
|---|---|---:|---:|---:|---:|---:|---:|
| foxnews | right | 1,309 | **36.5** | 26.4 | 80.6 | 0.555 | 193 |
| washingtonexaminer | right | 651 | **31.2** | 20.4 | 84.0 | 0.589 | 87 |
| theguardian | left | 2,368 | 28.0 | 18.1 | 84.7 | 0.574 | 299 |
| dailycaller | right | 441 | 26.3 | 14.7 | 86.6 | 0.598 | 55 |
| huffpost | left | 1,392 | 18.8 | 5.8 | 85.3 | 0.341 | 193 |
| nypost | right | 818 | 17.1 | 7.3 | 86.8 | 0.398 | 94 |
| npr | left | 761 | 13.7 | 8.4 | 88.2 | 0.402 | 65 |
| washingtontimes | right | 821 | **11.9** | 5.5 | **90.4** | 0.403 | 66 |

Outlet-level variance is much larger than the block-level gap (left vs. right: +2.8 ppt LLM SUBJ). Aggregating to block level conceals outlet-specific editorial styles. HuffPost has the lowest outlet κ (0.341) — its evaluative language is lexically subtle enough to consistently fool the proxy. Washington Times (lowest LLM SUBJ, highest agreement) is consistent with a wire-report, declarative style.

### 6. Outlet level — image (VLM)

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

NYP shows the highest VLM-SUBJ rate (35.5%), but the sample is **n = 31**. The Wilson 95 % CI for this proportion is approximately **[20 %, 53 %]** — a band that overlaps HuffPost (24.6 %) and The Guardian (23.4 %). NYP's VLM-SUBJ rate is therefore **not statistically distinguishable** from those outlets at this sample size.

A plausible confound: the VLM-SUBJ criteria in `prompts/vlm_image_annotation.txt` — (i) emotionally loaded expression, (iii) demeaning or diminishing framing, (iv) dramatic or manipulative editing — map closely to tabloid cover-photo conventions regardless of editorial intent. Part of NYP's high score may be a prompt-format artefact rather than an editorial signal. This is a hypothesis to be tested with a larger sample and criteria disambiguation, not a finding from this data.

Fox News and Washington Examiner have unexpectedly low VLM SUBJ (11.4 % and 8.0 %) despite ranking first and second on text subjectivity. NPR has the highest VLM confidence (0.900) and one of the lowest VLM SUBJ rates, consistent with measured wire-photo image selection throughout.

### 7. Text ↔ image cross-modality (article level, n = 292)

Article majority labels: LLM sentence labels ≥ 50 % SUBJ → text-SUBJ; VLM label → image-SUBJ.

| | Image OBJ | Image SUBJ |
|---|---:|---:|
| **Text OBJ** | 218 | 47 |
| **Text SUBJ** | 18 | 9 |

- Accuracy: 0.777 — Cohen κ = 0.105 — Spearman ρ = 0.134 (p = 0.022)

The correlation is **statistically non-zero** (p = 0.022) but **practically negligible** (κ = 0.105, ρ = 0.134). Only 9 of 27 text-SUBJ articles also carry a SUBJ image. Text and visual framing are largely independent signals in this corpus — consistent with copy and image being curated under separate editorial pipelines, but this data does not establish a causal direction or outlet intent.

### 8. Rationale length — proxy's missed SUBJ (Mann-Whitney U)

**Hypothesis:** when the proxy misses a SUBJ sentence that the LLM caught, the LLM writes a longer rationale (reflecting greater explanatory effort for harder cases).

| Group | n | Median chars | IQR |
|---|---:|---:|---|
| Agreement-SUBJ (both agree SUBJ) | 1,012 | 198 | [170, 200] |
| Proxy-missed SUBJ (LLM=SUBJ, proxy=OBJ) | 1,052 | 193 | [169, 200] |

Mann-Whitney U = 510,328 — p = 0.089

p > 0.05: the hypothesis is **not supported**. Rationale length is not a usable signal for detection difficulty. (The rationale field is also schema-capped at 200 characters, which compresses the tail and reduces sensitivity.)

### Summary

1. **Moderate overall agreement** — κ = 0.532, F1-SUBJ = 0.616. The proxy under-calls subjectivity; it almost never over-calls it. F1-SUBJ is the more informative headline metric given 76 % OBJ prevalence.
2. **Directional error** — 83 % of disagreements are false negatives. The proxy reliably catches rhetorical questions, figurative language, and explicit evaluative phrases, but consistently misses single-word signals: intensifiers (`staggering`, `wildly`), loaded nouns (`slush fund`, `dregs`), and framing verbs (`slammed`, `insisted`).
3. **Outlet variance dominates block variance** — the left/right gap (+2.8 ppt) is small relative to within-block outlet differences. Aggregating to block level is the coarser, less accurate story.
4. **Text and image are independent** — Spearman ρ = 0.134 (p = 0.022) at article level: statistically present, practically negligible. Editorial choices for copy and images appear to follow separate logics.
5. **Small-sample caveats matter** — outlet-level VLM SUBJ rates carry wide confidence intervals at n ≤ 35. NYP's headline number (35.5 %) is within Wilson CI [20 %, 53 %] — not distinguishable from neighbouring outlets. Rationale-length as a difficulty proxy is also ruled out (p = 0.089).

---

## If I had more time

Ideas captured during the build window that were out of scope for the 4–6h budget. Not part of the delivered pipeline.

- **Topic modeling (BERTopic)** — Replace the current URL/feed keyword rule with BERTopic run over the corpus body. The keyword rule is fast but depends on publisher section names; BERTopic would produce data-driven, outlet-agnostic topic clusters and could auto-assign articles that arrive through generic news feeds (currently labelled `uncategorized` because they carry no section signal).

- **Balance the non-political bucket across blocks** — The left block has far fewer non-political articles than the right (left=9 vs right=33). Adding non-political left-leaning feeds (Guardian `/sport/`, `/culture/`, HuffPost entertainment vertical) would make political-vs-non-political comparisons within each block meaningful.

- **Branded columnist articles (Fox / CyberGuy)** — Fox carries branded property columns (CyberGuy, Outkick, Tucker) where editorial voice and CTAs drown out news content. A future pass would either detect these via brand-mention density and drop them, or maintain a per-outlet curated list for masking.

- **NPR show names and correspondent names as outlet signals** — NPR identity leaks through branded show names ("Up First", "Morning Edition") and named correspondents. Masking these risks false positives; a proper fix requires a curated NPR-specific entity list with line-context heuristics.

- **Replace NPR with a written-news outlet** — NPR RSS feeds return radio transcripts (`HOST:/BYLINE:/SOUNDBITE:` format) rather than written news, which polluted the dataset and created significant cleaning overhead. A next iteration should substitute NPR with a purely written-news source (AP News, Reuters, Politico, or The Hill).

- **Drop Daily Caller** — Like NPR, Daily Caller introduced noise: an intensely partisan editorial voice and a low news-to-opinion ratio that sets it apart from the other right-leaning outlets. Next iteration: remove both NPR and Daily Caller and replace with higher-quality, more balanced sources.

- **Manual sample review** — Time pressure prevented a hands-on sanity check. At minimum: pull one sample per outlet per block, read the cleaned text and LLM/VLM annotations directly. This is the fastest way to catch systematic errors (mis-masking, label drift, noisy text) before they compound.

- **Iterative stop-word list expansion** — After seeing the first frequency/TF-IDF tables, add outlet-specific boilerplate and overly common news jargon to the stop-word list and re-run. This is inherently iterative; the words to suppress cannot be identified before the first run.

- **Prompt cross-validation for LLM and VLM** — Compare prompt variants on a small hold-out set: zero-shot vs. few-shot, rewording of definitions, chain-of-thought addition. Goal: measure how much of the inter-annotator inconsistency on SUBJ/framing labels comes from prompt formulation vs. genuine ambiguity.

- **Proxy VLM pass** — Run a smaller, cheaper vision-language model as a first pass before the main VLM. This would surface prompt errors, masking issues, and edge cases at low cost before committing to the full Batch API run.

- **PABAK** — Add Prevalence-Adjusted Bias-Adjusted Kappa alongside Cohen's κ. With 76 % OBJ prevalence, standard κ is pulled downward by class imbalance; PABAK corrects for this and gives a more reliable inter-annotator agreement figure for LLM–proxy and LLM–VLM comparisons.

- **Balance topic distribution across blocks** — The topic mix differs between blocks not just in the non-political bucket but also within political topics. Block-level comparisons are cleaner when both sides share a similar topic profile; this would require feed selection or post-hoc stratified sampling.
