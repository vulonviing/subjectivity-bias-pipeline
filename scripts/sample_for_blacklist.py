"""Write 5 random articles per outlet to data/analysis/blacklist_samples/ for manual pattern review."""
from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from utils import ANALYSIS, PROCESSED, read_jsonl

SEED = 42
N = 5
OUT_DIR = ANALYSIS / "blacklist_samples"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def main() -> None:
    by_source: dict[str, list[dict]] = {}
    for row in read_jsonl(PROCESSED / "articles.jsonl"):
        by_source.setdefault(row["source"], []).append(row)

    for source, articles in sorted(by_source.items()):
        rng = random.Random(SEED)
        sample = rng.sample(articles, min(N, len(articles)))
        for i, art in enumerate(sample, 1):
            path = OUT_DIR / f"{source}_{i}.txt"
            with path.open("w", encoding="utf-8") as f:
                f.write(f"article_id: {art['article_id']}\n")
                f.write(f"url: {art['url']}\n")
                f.write(f"title: {art['title']}\n")
                f.write(f"source: {art['source']} ({art['outlet_block']})\n")
                f.write(f"topic: {art['topic']}\n")
                f.write("=" * 60 + "\n")
                f.write(art.get("body") or "")
                f.write("\n")
        print(f"{source}: {len(sample)} samples written")


if __name__ == "__main__":
    main()
