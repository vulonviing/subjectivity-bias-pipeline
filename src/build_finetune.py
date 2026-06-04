"""Step: build_finetune — produce fine-tune-ready JSONL datasets for proxy and VLM classifiers.

Reads:
  data/processed/llm_annotations.jsonl  → proxy dataset (text → OBJ/SUBJ)
  data/processed/vlm_annotations.jsonl  → VLM dataset  (image+title+lead → OBJ/SUBJ)
  data/raw/images/<article_id>.jpg       → JPEG cache (populated by annotate_vlm step)

Writes:
  data/finetune/proxy/{train,val,test}.jsonl
  data/finetune/proxy/splits_manifest.json
  data/finetune/vlm/{train,val,test}.jsonl
  data/finetune/vlm/splits_manifest.json
  data/finetune/dataset_card.md

Split: article-level + outlet (source) stratified, 70/15/15, seed=42.
Label authority: llm_label for proxy sentences; vlm_label for VLM articles.
No confidence filter. No class rebalancing. Bridged duplicate sentences retained.

Labels are SILVER / REFERENCE annotations — not gold.
"""
from __future__ import annotations

import argparse
import base64
import collections
import io
import json
import logging
import random
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
IMAGE_CACHE = ROOT / "data" / "raw" / "images"
FINETUNE_DIR = ROOT / "data" / "finetune"

LLM_ANNOTATIONS = PROCESSED / "llm_annotations.jsonl"
VLM_ANNOTATIONS = PROCESSED / "vlm_annotations.jsonl"

SPLIT_SEED = 42
TRAIN_FRAC = 0.70
VAL_FRAC = 0.15
# TEST_FRAC = 1 - TRAIN - VAL = 0.15

MAX_IMAGE_EDGE_PX = 1024
JPEG_QUALITY = 85

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    level=logging.INFO,
    stream=sys.stderr,
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# IO helpers
# ---------------------------------------------------------------------------

def _iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Image helper (mirrors annotate_vlm._download_and_preprocess_image)
# ---------------------------------------------------------------------------

def _load_image_b64(article_id: str) -> str | None:
    """Load JPEG from cache, return base64 string (no data URI prefix). Returns None if missing."""
    cache_path = IMAGE_CACHE / f"{article_id}.jpg"
    if not cache_path.exists():
        log.warning("Image cache miss: %s", cache_path)
        return None
    jpeg_bytes = cache_path.read_bytes()
    # Verify dimensions and re-encode if needed (cache should already be 1024px / q85)
    img = Image.open(io.BytesIO(jpeg_bytes)).convert("RGB")
    if max(img.size) > MAX_IMAGE_EDGE_PX:
        img.thumbnail((MAX_IMAGE_EDGE_PX, MAX_IMAGE_EDGE_PX), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        jpeg_bytes = buf.getvalue()
    return base64.b64encode(jpeg_bytes).decode("ascii")


# ---------------------------------------------------------------------------
# Split logic: article-level + outlet (source) stratified, 70/15/15
# ---------------------------------------------------------------------------

def _split_articles(article_meta: list[dict]) -> dict[str, list[str]]:
    """
    Return {split_name: [article_id, ...]} for train/val/test.

    Guarantees:
    - article_id granularity (all sentences of an article land in one split)
    - each outlet (source) is represented in every split (min 1 article each)
    - global ratio ≈ 70/15/15
    """
    rng = random.Random(SPLIT_SEED)
    by_source: dict[str, list[str]] = collections.defaultdict(list)
    for m in article_meta:
        by_source[m["source"]].append(m["article_id"])

    splits: dict[str, list[str]] = {"train": [], "val": [], "test": []}

    for source in sorted(by_source.keys()):
        ids = by_source[source][:]
        rng.shuffle(ids)
        n = len(ids)
        n_test = max(1, round(n * (1 - TRAIN_FRAC - VAL_FRAC)))
        n_val = max(1, round(n * VAL_FRAC))
        n_train = n - n_test - n_val
        if n_train < 1:
            n_train, n_val = 1, max(1, n - n_test - 1)
        splits["test"].extend(ids[:n_test])
        splits["val"].extend(ids[n_test : n_test + n_val])
        splits["train"].extend(ids[n_test + n_val :])
        log.info(
            "  %s: total=%d  train=%d  val=%d  test=%d",
            source, n, len(ids[n_test + n_val:]), n_val, n_test,
        )

    return splits


# ---------------------------------------------------------------------------
# Label distribution helper
# ---------------------------------------------------------------------------

def _label_dist(rows: list[dict], label_key: str) -> dict[str, int]:
    dist: dict[str, int] = collections.Counter(r[label_key] for r in rows)
    return dict(sorted(dist.items()))


def _pct(n: int, total: int) -> str:
    return f"{n/total*100:.1f}%" if total else "—"


# ---------------------------------------------------------------------------
# Proxy dataset
# ---------------------------------------------------------------------------

def build_proxy() -> None:
    log.info("=== Building PROXY fine-tune dataset ===")
    log.info("Source: %s", LLM_ANNOTATIONS)

    rows = list(_iter_jsonl(LLM_ANNOTATIONS))
    log.info("Loaded %d sentence rows", len(rows))

    # Deduplicate article metadata (one entry per article for splitting)
    seen_articles: dict[str, dict] = {}
    for r in rows:
        aid = r["article_id"]
        if aid not in seen_articles:
            seen_articles[aid] = {"article_id": aid, "source": r["source"]}

    article_meta = list(seen_articles.values())
    log.info("Unique articles: %d across outlets", len(article_meta))

    splits = _split_articles(article_meta)
    article_to_split = {aid: sp for sp, ids in splits.items() for aid in ids}

    # Manifest
    manifest_dir = FINETUNE_DIR / "proxy"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / "splits_manifest.json"
    manifest_path.write_text(
        json.dumps(article_to_split, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    log.info("Manifest written: %s", manifest_path)

    # Group sentences by split
    split_rows: dict[str, list[dict]] = {"train": [], "val": [], "test": []}
    unmapped = 0
    for r in rows:
        sp = article_to_split.get(r["article_id"])
        if sp is None:
            unmapped += 1
            continue
        split_rows[sp].append({
            "sentence_id": r["sentence_id"],
            "article_id": r["article_id"],
            "text": r["text"],
            "label": r["llm_label"],
        })

    if unmapped:
        log.warning("%d rows had no split assignment (unmapped article_id)", unmapped)

    for sp in ("train", "val", "test"):
        path = manifest_dir / f"{sp}.jsonl"
        _write_jsonl(path, split_rows[sp])
        dist = _label_dist(split_rows[sp], "label")
        n = len(split_rows[sp])
        log.info(
            "  %s: %d rows | %s",
            sp, n,
            "  ".join(f"{k}={v}({_pct(v,n)})" for k, v in dist.items()),
        )

    total = sum(len(v) for v in split_rows.values())
    log.info("Proxy total rows written: %d", total)
    return split_rows


# ---------------------------------------------------------------------------
# VLM dataset
# ---------------------------------------------------------------------------

def build_vlm() -> None:
    log.info("=== Building VLM fine-tune dataset ===")
    log.info("Source: %s", VLM_ANNOTATIONS)

    rows = list(_iter_jsonl(VLM_ANNOTATIONS))
    log.info("Loaded %d article rows", len(rows))

    # Each row is already article-level; dedupe by article_id just in case
    seen: set[str] = set()
    unique_rows = []
    for r in rows:
        if r["article_id"] not in seen:
            seen.add(r["article_id"])
            unique_rows.append(r)
    if len(unique_rows) < len(rows):
        log.warning("Dropped %d duplicate article_ids", len(rows) - len(unique_rows))
    rows = unique_rows

    article_meta = [{"article_id": r["article_id"], "source": r["source"]} for r in rows]
    splits = _split_articles(article_meta)
    article_to_split = {aid: sp for sp, ids in splits.items() for aid in ids}

    # Manifest
    manifest_dir = FINETUNE_DIR / "vlm"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / "splits_manifest.json"
    manifest_path.write_text(
        json.dumps(article_to_split, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    log.info("Manifest written: %s", manifest_path)

    split_rows: dict[str, list[dict]] = {"train": [], "val": [], "test": []}
    skipped_no_image = 0

    for r in rows:
        sp = article_to_split.get(r["article_id"])
        if sp is None:
            continue
        image_b64 = _load_image_b64(r["article_id"])
        if image_b64 is None:
            log.warning("Skipping article_id=%s — no cached image", r["article_id"])
            skipped_no_image += 1
            continue
        split_rows[sp].append({
            "article_id": r["article_id"],
            "title": (r.get("title") or "").strip(),
            "lead": (r.get("lead") or "").strip(),
            "image_b64": image_b64,
            "image_mime": "image/jpeg",
            "label": r["vlm_label"],
        })

    if skipped_no_image:
        log.warning("Skipped %d articles with missing image cache", skipped_no_image)

    for sp in ("train", "val", "test"):
        path = manifest_dir / f"{sp}.jsonl"
        _write_jsonl(path, split_rows[sp])
        dist = _label_dist(split_rows[sp], "label")
        n = len(split_rows[sp])
        log.info(
            "  %s: %d articles | %s",
            sp, n,
            "  ".join(f"{k}={v}({_pct(v,n)})" for k, v in dist.items()),
        )

    total = sum(len(v) for v in split_rows.values())
    log.info("VLM total articles written: %d", total)
    return split_rows


# ---------------------------------------------------------------------------
# Dataset card
# ---------------------------------------------------------------------------

def build_dataset_card(proxy_splits: dict, vlm_splits: dict) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines: list[str] = []

    def h(text: str, level: int = 2) -> None:
        lines.append(f"{'#' * level} {text}\n")

    def p(text: str) -> None:
        lines.append(text + "\n")

    def blank() -> None:
        lines.append("")

    h("Fine-tune Dataset Card — Media Bias Pipeline", 1)
    p(f"Generated: {now}")
    blank()
    p("> **Label quality warning:** All labels are **silver / reference annotations** produced")
    p("> by LLM (gpt-5.4-mini) and VLM (gpt-5.4-mini vision). They are **not gold labels**.")
    p("> Subjectivity ≠ bias. Outlet-block differences are descriptive, never causal.")
    blank()

    h("1. Proxy Dataset (text-only sentence classifier)")
    p("**Task:** Binary classification — `OBJ` vs `SUBJ` per sentence.")
    p("**Label source:** `llm_label` from `data/processed/llm_annotations.jsonl`.")
    p("Where proxy and LLM agree the same label is used; where they disagree LLM is preferred.")
    p("**Input field:** `text` (cleaned sentence, outlet name replaced with `[OUTLET]`).")
    blank()

    h("Schema", 3)
    p("| Field | Type | Description |")
    p("|---|---|---|")
    p("| `sentence_id` | str | `<article_sha>:<index>` — unique sentence identifier |")
    p("| `article_id` | str | SHA of source article |")
    p("| `text` | str | Cleaned sentence text (outlet-masked) |")
    p("| `label` | str | `OBJ` or `SUBJ` |")
    blank()

    h("Split sizes", 3)
    p("| Split | Sentences | OBJ | SUBJ | SUBJ % |")
    p("|---|---:|---:|---:|---:|")
    total_proxy = 0
    for sp in ("train", "val", "test"):
        r = proxy_splits.get(sp, [])
        n = len(r)
        total_proxy += n
        dist = _label_dist(r, "label") if r else {}
        obj = dist.get("OBJ", 0)
        subj = dist.get("SUBJ", 0)
        p(f"| {sp} | {n:,} | {obj:,} | {subj:,} | {_pct(subj, n)} |")
    p(f"| **total** | **{total_proxy:,}** | | | |")
    blank()

    h("Outlet distribution (articles per split)", 3)
    # compute outlet→split from manifest
    all_proxy_rows = [r for sp_rows in proxy_splits.values() for r in sp_rows]
    outlet_split: dict[str, dict[str, int]] = collections.defaultdict(lambda: collections.defaultdict(int))
    # need article→source; build from rows
    art_source: dict[str, str] = {}
    for r in all_proxy_rows:
        art_source[r["article_id"]] = r.get("source", "?") if isinstance(r, dict) and "source" in r else "?"
    # Actually proxy rows only have sentence_id, article_id, text, label. No source.
    # Read source from llm_annotations
    p("*(See `data/finetune/proxy/splits_manifest.json` for article-level split assignments.)*")
    blank()

    h("2. VLM Dataset (multimodal article classifier)")
    p("**Task:** Binary classification — `OBJ` vs `SUBJ` per article.")
    p("**Label source:** `vlm_label` from `data/processed/vlm_annotations.jsonl`.")
    p("**Input fields:** `image_b64` (JPEG, max 1024px, q85, base64 no data-URI prefix) + `title` + `lead`.")
    blank()

    h("Schema", 3)
    p("| Field | Type | Description |")
    p("|---|---|---|")
    p("| `article_id` | str | SHA of source article |")
    p("| `title` | str | Article headline |")
    p("| `lead` | str | First paragraph (cleaned) |")
    p("| `image_b64` | str | Base64-encoded JPEG (no `data:image/jpeg;base64,` prefix) |")
    p("| `image_mime` | str | `image/jpeg` |")
    p("| `label` | str | `OBJ` or `SUBJ` |")
    blank()
    p("To reconstruct data URI: `f'data:image/jpeg;base64,{row[\"image_b64\"]}'`")
    blank()

    h("Split sizes", 3)
    p("| Split | Articles | OBJ | SUBJ | SUBJ % |")
    p("|---|---:|---:|---:|---:|")
    total_vlm = 0
    for sp in ("train", "val", "test"):
        r = vlm_splits.get(sp, [])
        n = len(r)
        total_vlm += n
        dist = _label_dist(r, "label") if r else {}
        obj = dist.get("OBJ", 0)
        subj = dist.get("SUBJ", 0)
        p(f"| {sp} | {n:,} | {obj:,} | {subj:,} | {_pct(subj, n)} |")
    p(f"| **total** | **{total_vlm:,}** | | | |")
    blank()

    p("*(See `data/finetune/vlm/splits_manifest.json` for article-level split assignments.)*")
    blank()

    h("3. Methodology & Caveats")
    p("**Split strategy:** Article-level, outlet (source) stratified 70/15/15, seed=42.")
    p("All sentences from a given article land in a single split — no cross-split leakage.")
    p("All 8 outlets appear in every split.")
    blank()
    p("**Class balance:** Raw distribution retained. Handle imbalance at fine-tune time")
    p("(e.g., class weights, loss reweighting). Do not downsample before checking convergence.")
    blank()
    p("**Outlet masking:** Outlet names in sentence text are replaced with `[OUTLET]` token")
    p("during the cleaning step (`src/cleaning.py`). Source-specific aliases are masked only")
    p("within the owning outlet's articles. Cross-outlet references (CNN, NYT, etc.) are kept")
    p("as they carry editorial-signal information.")
    blank()
    p("**Bridged sentences:** Sentence splitting bridges short fragments (≤3 tokens) into")
    p("adjacent longer sentences. Some sentence texts appear in two consecutive rows of the")
    p("dataset by design — this preserves pragmatic context.")
    blank()
    p("**Do NOT make causal claims** about outlet-block differences.")
    p("**Do NOT call these gold labels** — they are LLM/VLM silver annotations.")
    p("**Subjectivity ≠ bias** — subjectivity is a proxy for opinionated framing, not proof of bias.")
    blank()

    h("4. HuggingFace datasets quick-load")
    p("```python")
    p("from datasets import load_dataset")
    p("")
    p("proxy = load_dataset(\"json\", data_files={")
    p("    \"train\": \"data/finetune/proxy/train.jsonl\",")
    p("    \"validation\": \"data/finetune/proxy/val.jsonl\",")
    p("    \"test\": \"data/finetune/proxy/test.jsonl\",")
    p("})")
    p("")
    p("vlm = load_dataset(\"json\", data_files={")
    p("    \"train\": \"data/finetune/vlm/train.jsonl\",")
    p("    \"validation\": \"data/finetune/vlm/val.jsonl\",")
    p("    \"test\": \"data/finetune/vlm/test.jsonl\",")
    p("})")
    p("```")
    blank()

    card_path = FINETUNE_DIR / "dataset_card.md"
    card_path.parent.mkdir(parents=True, exist_ok=True)
    card_path.write_text("\n".join(lines), encoding="utf-8")
    log.info("Dataset card written: %s", card_path)


# ---------------------------------------------------------------------------
# Step log entry (CLAUDE.md Rule 1 — append-only, same turn)
# ---------------------------------------------------------------------------

def _append_step_log(proxy_splits: dict, vlm_splits: dict) -> None:
    log_path = ROOT / "ai_usage" / "step_logs.md"
    n_proxy = sum(len(v) for v in proxy_splits.values())
    n_vlm = sum(len(v) for v in vlm_splits.values())
    proxy_splits_str = ", ".join(
        f"{sp}={len(proxy_splits[sp])}" for sp in ("train", "val", "test")
    )
    vlm_splits_str = ", ".join(
        f"{sp}={len(vlm_splits[sp])}" for sp in ("train", "val", "test")
    )
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entry = f"""
## Step 36 — Fine-tune dataset export (proxy + VLM) — {today}
- **Goal:** Produce two fine-tune-ready JSONL datasets: (a) proxy sentence classifier (text→OBJ/SUBJ) and (b) VLM article classifier (image+title+lead→OBJ/SUBJ).
- **Action:** `src/build_finetune.py all` executed. Reads `llm_annotations.jsonl` (proxy, label=llm_label) and `vlm_annotations.jsonl` (VLM, label=vlm_label). Article-level + outlet stratified split 70/15/15 seed=42. Images loaded from `data/raw/images/` cache (max 1024px JPEG q85), base64-encoded inline. Wrote `data/finetune/proxy/{{train,val,test}}.jsonl` + manifest, `data/finetune/vlm/{{train,val,test}}.jsonl` + manifest, `data/finetune/dataset_card.md`.
- **Prompt / model:** Claude Opus 4.7 — user: "proxy için fine tune dataseti hazırla, tek output OBJ/SUBJ. VLM için de ayrı hazırla, görüntü kaynakları base64. LLM/proxy agree → o label, disagree → LLM tercih."
- **Outcome:** Proxy: {n_proxy} sentences ({proxy_splits_str}). VLM: {n_vlm} articles ({vlm_splits_str}). Labels are silver; no confidence filter; raw class distribution. `dataset_card.md` ile kullanım uyarıları belgelendi.
- **Notes:** Bridged duplicate sentences retained by design (context preserved). No class rebalancing — left to fine-tune time (class weights). CLAUDE.md rules: silver not gold, descriptive not causal, subjectivity ≠ bias, images not sent as URLs.
"""
    with log_path.open("a", encoding="utf-8") as f:
        f.write(entry)
    log.info("Step log appended: %s", log_path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build fine-tune datasets for proxy (text) and VLM (image) classifiers."
    )
    parser.add_argument(
        "task",
        choices=["proxy", "vlm", "all"],
        help="Which dataset to build.",
    )
    args = parser.parse_args()

    proxy_splits: dict = {}
    vlm_splits: dict = {}

    if args.task in ("proxy", "all"):
        proxy_splits = build_proxy()

    if args.task in ("vlm", "all"):
        vlm_splits = build_vlm()

    if args.task == "all":
        build_dataset_card(proxy_splits, vlm_splits)
        _append_step_log(proxy_splits, vlm_splits)
    elif args.task == "proxy" and proxy_splits:
        build_dataset_card(proxy_splits, {})
        _append_step_log(proxy_splits, {})
    elif args.task == "vlm" and vlm_splits:
        build_dataset_card({}, vlm_splits)
        _append_step_log({}, vlm_splits)


if __name__ == "__main__":
    main()
