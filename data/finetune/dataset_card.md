# Fine-tune Dataset Card — Media Bias Pipeline

Generated: 2026-06-04


> **Label quality warning:** All labels are **silver / reference annotations** produced

> by LLM (gpt-5.4-mini) and VLM (gpt-5.4-mini vision). They are **not gold labels**.

> Subjectivity ≠ bias. Outlet-block differences are descriptive, never causal.


## 1. Proxy Dataset (text-only sentence classifier)

**Task:** Binary classification — `OBJ` vs `SUBJ` per sentence.

**Label source:** `llm_label` from `data/processed/llm_annotations.jsonl`.

Where proxy and LLM agree the same label is used; where they disagree LLM is preferred.

**Input field:** `text` (cleaned sentence, outlet name replaced with `[OUTLET]`).


### Schema

| Field | Type | Description |

|---|---|---|

| `sentence_id` | str | `<article_sha>:<index>` — unique sentence identifier |

| `article_id` | str | SHA of source article |

| `text` | str | Cleaned sentence text (outlet-masked) |

| `label` | str | `OBJ` or `SUBJ` |


### Split sizes

| Split | Sentences | OBJ | SUBJ | SUBJ % |

|---|---:|---:|---:|---:|

| train | 6,007 | 4,522 | 1,485 | 24.7% |

| val | 1,278 | 968 | 310 | 24.3% |

| test | 1,276 | 1,007 | 269 | 21.1% |

| **total** | **8,561** | | | |


### Outlet distribution (articles per split)

*(See `data/finetune/proxy/splits_manifest.json` for article-level split assignments.)*


## 2. VLM Dataset (multimodal article classifier)

**Task:** Binary classification — `OBJ` vs `SUBJ` per article.

**Label source:** `vlm_label` from `data/processed/vlm_annotations.jsonl`.

**Input fields:** `image_b64` (JPEG, max 1024px, q85, base64 no data-URI prefix) + `title` + `lead`.


### Schema

| Field | Type | Description |

|---|---|---|

| `article_id` | str | SHA of source article |

| `title` | str | Article headline |

| `lead` | str | First paragraph (cleaned) |

| `image_b64` | str | Base64-encoded JPEG (no `data:image/jpeg;base64,` prefix) |

| `image_mime` | str | `image/jpeg` |

| `label` | str | `OBJ` or `SUBJ` |


To reconstruct data URI: `f'data:image/jpeg;base64,{row["image_b64"]}'`


### Split sizes

| Split | Articles | OBJ | SUBJ | SUBJ % |

|---|---:|---:|---:|---:|

| train | 204 | 166 | 38 | 18.6% |

| val | 44 | 33 | 11 | 25.0% |

| test | 44 | 37 | 7 | 15.9% |

| **total** | **292** | | | |


*(See `data/finetune/vlm/splits_manifest.json` for article-level split assignments.)*


## 3. Methodology & Caveats

**Split strategy:** Article-level, outlet (source) stratified 70/15/15, seed=42.

All sentences from a given article land in a single split — no cross-split leakage.

All 8 outlets appear in every split.


**Class balance:** Raw distribution retained. Handle imbalance at fine-tune time

(e.g., class weights, loss reweighting). Do not downsample before checking convergence.


**Outlet masking:** Outlet names in sentence text are replaced with `[OUTLET]` token

during the cleaning step (`src/cleaning.py`). Source-specific aliases are masked only

within the owning outlet's articles. Cross-outlet references (CNN, NYT, etc.) are kept

as they carry editorial-signal information.


**Bridged sentences:** Sentence splitting bridges short fragments (≤3 tokens) into

adjacent longer sentences. Some sentence texts appear in two consecutive rows of the

dataset by design — this preserves pragmatic context.


**Do NOT make causal claims** about outlet-block differences.

**Do NOT call these gold labels** — they are LLM/VLM silver annotations.

**Subjectivity ≠ bias** — subjectivity is a proxy for opinionated framing, not proof of bias.


## 4. HuggingFace datasets quick-load

```python

from datasets import load_dataset



proxy = load_dataset("json", data_files={

    "train": "data/finetune/proxy/train.jsonl",

    "validation": "data/finetune/proxy/val.jsonl",

    "test": "data/finetune/proxy/test.jsonl",

})



vlm = load_dataset("json", data_files={

    "train": "data/finetune/vlm/train.jsonl",

    "validation": "data/finetune/vlm/val.jsonl",

    "test": "data/finetune/vlm/test.jsonl",

})

```

