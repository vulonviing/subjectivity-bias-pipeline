"""Step: proxy_label — run the HF subjectivity classifier on each sentence.

Model: GroNLP/mdebertav3-subjectivity-english
    - Output labels: OBJ, SUBJ
    - Input: single cleaned sentence text only. No outlet name, URL, title, or
      image metadata is passed to the model. Metadata is preserved in the output
      for analysis only.
    - Used as a PROXY for subjective / opinionated framing, not as a complete
      media-bias detector. Subjectivity != bias. OBJ != unbiased, SUBJ != biased.
    - Expected disagreements with the LLM silver annotations are analyzed later.

Input  : data/processed/sentences.jsonl
Output : data/processed/proxy_predictions.jsonl  (all original fields + metadata
         join from articles_clean.jsonl + proxy_model / proxy_label / proxy_score)
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch
from tqdm import tqdm
from transformers import pipeline, set_seed

PROXY_MODEL_ID = "GroNLP/mdebertav3-subjectivity-english"

# HF pipeline may return raw LABEL_0/LABEL_1 instead of human-readable labels.
# mdebertav3-subjectivity-english id2label: {0: "OBJ", 1: "SUBJ"}
LABEL_NORMALIZER: dict[str, str] = {
    "LABEL_0": "OBJ",
    "LABEL_1": "SUBJ",
    "OBJ": "OBJ",
    "SUBJ": "SUBJ",
}

_META_FIELDS = (
    "source", "outlet_block", "title", "url", "image_url",
    "published_at", "topic", "topic_group", "language",
)

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    level=logging.INFO,
    stream=sys.stderr,
)
log = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Proxy subjectivity labeling via HF text-classification pipeline"
    )
    p.add_argument("--input", default="data/processed/sentences.jsonl")
    p.add_argument("--output", default="data/processed/proxy_predictions.jsonl")
    p.add_argument(
        "--articles",
        default="data/processed/articles_clean.jsonl",
        help="Metadata source for join (source, outlet_block, title, url, image_url, ...)",
    )
    p.add_argument("--model-name", default=PROXY_MODEL_ID)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--text-field", default="text")
    p.add_argument(
        "--device", type=int, default=-1, help="-1 = CPU, 0+ = GPU index"
    )
    return p.parse_args()


def _load_article_meta(path: str) -> dict[str, dict]:
    meta: dict[str, dict] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            aid = row.get("article_id")
            if not aid:
                continue
            meta[aid] = {k: row.get(k) for k in _META_FIELDS}
    return meta


def _iter_sentences(path: str):
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def _pick_top(preds: list[dict]) -> dict:
    """Return the highest-scoring label dict from top_k=None output."""
    return max(preds, key=lambda x: x["score"])


def main() -> None:
    args = _parse_args()

    set_seed(42)
    np.random.seed(42)
    torch.manual_seed(42)

    log.info("Loading article metadata from %s", args.articles)
    article_meta = _load_article_meta(args.articles)
    log.info("  %d articles loaded", len(article_meta))

    log.info("Loading model: %s (device=%d)", args.model_name, args.device)
    clf = pipeline(
        "text-classification",
        model=args.model_name,
        tokenizer=args.model_name,
        top_k=None,
        device=args.device,
        truncation=True,
        max_length=512,
    )
    log.info(
        "  Model ready. batch-size=%d, text-field=%s",
        args.batch_size, args.text_field,
    )
    log.info("Input : %s", args.input)
    log.info("Output: %s", args.output)

    total = skipped = 0
    errors: list[dict] = []

    input_rows: list[dict] = list(_iter_sentences(args.input))
    n_total = len(input_rows)

    valid_rows: list[dict] = []
    valid_texts: list[str] = []
    for row in input_rows:
        total += 1
        text = row.get(args.text_field)
        if not text or not isinstance(text, str) or not text.strip():
            reason = f"empty or missing field '{args.text_field}'"
            log.warning("Skipping %s: %s", row.get("sentence_id", "?"), reason)
            errors.append({
                "sentence_id": row.get("sentence_id"),
                "article_id": row.get("article_id"),
                "reason": reason,
            })
            skipped += 1
            continue
        aid = row.get("article_id")
        if aid not in article_meta:
            reason = f"article_id '{aid}' not found in articles metadata"
            log.warning("Skipping %s: %s", row.get("sentence_id", "?"), reason)
            errors.append({
                "sentence_id": row.get("sentence_id"),
                "article_id": aid,
                "reason": reason,
            })
            skipped += 1
            continue
        valid_rows.append(row)
        valid_texts.append(text.strip())

    log.info(
        "Valid rows: %d / %d  (skipped: %d)", len(valid_rows), n_total, skipped
    )

    predictions: list[dict] = []
    batch_size = args.batch_size
    for i in tqdm(
        range(0, len(valid_texts), batch_size), desc="Predicting", unit="batch"
    ):
        batch_texts = valid_texts[i : i + batch_size]
        batch_preds = clf(batch_texts)
        for preds in batch_preds:
            predictions.append(_pick_top(preds))

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    label_counts: Counter = Counter()
    label_scores: dict[str, list[float]] = defaultdict(list)

    with open(out_path, "w", encoding="utf-8") as f:
        for row, pred in zip(valid_rows, predictions):
            raw_label = pred["label"]
            label = LABEL_NORMALIZER.get(raw_label.upper(), raw_label.upper())
            score = float(pred["score"])

            label_counts[label] += 1
            label_scores[label].append(score)

            out = dict(row)
            out.update(article_meta[row["article_id"]])
            out["proxy_model"] = args.model_name
            out["proxy_label"] = label
            out["proxy_score"] = round(score, 6)
            f.write(json.dumps(out, ensure_ascii=False) + "\n")

    if errors:
        err_path = out_path.parent / (out_path.stem + ".errors.jsonl")
        with open(err_path, "w", encoding="utf-8") as f:
            for e in errors:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
        log.warning("Error report written: %s (%d rows)", err_path, len(errors))

    log.info("=== Done ===")
    log.info("  Total input rows   : %d", n_total)
    log.info("  Processed          : %d", len(predictions))
    log.info("  Skipped / errors   : %d", skipped)
    n_pred = max(len(predictions), 1)
    for lbl in ("OBJ", "SUBJ"):
        cnt = label_counts[lbl]
        avg = (sum(label_scores[lbl]) / cnt) if cnt else 0.0
        log.info(
            "  %-6s: %d (%.1f%%)  avg score %.4f",
            lbl, cnt, 100 * cnt / n_pred, avg,
        )


if __name__ == "__main__":
    main()
