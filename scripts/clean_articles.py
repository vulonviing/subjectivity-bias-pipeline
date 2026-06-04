"""Apply blacklist cleaning and outlet masking to articles.jsonl → articles_clean.jsonl."""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from cleaning import OUTLET_TOKEN, clean_body
from utils import PROCESSED, read_jsonl, write_jsonl

MIN_BODY_CHARS = 400
MIN_SENTENCES = 3

_SENT_SPLIT = re.compile(r"[.!?]+\s+")


def main() -> None:
    src = PROCESSED / "articles.jsonl"
    dst = PROCESSED / "articles_clean.jsonl"

    stats: dict[str, dict] = defaultdict(lambda: {"articles": 0, "chars_before": 0, "chars_after": 0, "outlet_masks": 0})
    skipped: list[tuple[str, str, str]] = []

    def process():
        for row in read_jsonl(src):
            source = row["source"]
            body_before = row.get("body") or ""
            body_after = clean_body(body_before, source)
            masks = body_after.count(OUTLET_TOKEN)

            n_sent = sum(1 for s in _SENT_SPLIT.split(body_after) if s.strip())
            if len(body_after) < MIN_BODY_CHARS:
                skipped.append((row["article_id"], source, f"short_body:{len(body_after)}c"))
                continue
            if n_sent < MIN_SENTENCES:
                skipped.append((row["article_id"], source, f"few_sentences:{n_sent}"))
                continue

            stats[source]["articles"] += 1
            stats[source]["chars_before"] += len(body_before)
            stats[source]["chars_after"] += len(body_after)
            stats[source]["outlet_masks"] += masks

            yield {**row, "body": body_after}

    n = write_jsonl(dst, process())
    if skipped:
        print(f"\nSkipped {len(skipped)} articles (min-content filter):", file=sys.stderr)
        for aid, src_name, reason in skipped:
            print(f"  {aid} ({src_name}): {reason}", file=sys.stderr)
    print(f"\nWrote {n} articles to {dst} (skipped {len(skipped)})\n")

    print(f"{'source':<22} {'articles':>8} {'chars_before':>13} {'chars_after':>12} {'reduction%':>11} {'[OUTLET] masks':>15}")
    print("-" * 83)
    totals = {"articles": 0, "chars_before": 0, "chars_after": 0, "outlet_masks": 0}
    for source, s in sorted(stats.items()):
        pct = 100 * (1 - s["chars_after"] / s["chars_before"]) if s["chars_before"] else 0
        print(f"{source:<22} {s['articles']:>8} {s['chars_before']:>13,} {s['chars_after']:>12,} {pct:>10.1f}% {s['outlet_masks']:>15,}")
        for k in totals:
            totals[k] += s[k]
    print("-" * 83)
    total_pct = 100 * (1 - totals["chars_after"] / totals["chars_before"]) if totals["chars_before"] else 0
    print(f"{'TOTAL':<22} {totals['articles']:>8} {totals['chars_before']:>13,} {totals['chars_after']:>12,} {total_pct:>10.1f}% {totals['outlet_masks']:>15,}")


if __name__ == "__main__":
    main()
