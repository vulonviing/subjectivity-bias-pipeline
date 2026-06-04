"""One-off sentence health audit: heuristic healthy/unhealthy classification.

Unhealthy categories:
  too_short   — n_tokens_est < 4
  too_long    — n_tokens_est > 80
  all_caps    — pure all-caps line (headline residue)
  transcript  — SPEAKER: / BYLINE: / SOUNDBITE pattern (transcript residue)
  url_heavy   — line mostly URL/email tokens
  fragment    — no sentence-ending punctuation AND < 6 tokens

A sentence flagged by any category is unhealthy.
"""
from __future__ import annotations

import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path

SENTENCES = Path("data/processed/sentences.jsonl")
ARTICLES  = Path("data/processed/articles_clean.jsonl")

ALL_CAPS_PAT   = re.compile(r"^[A-Z0-9][A-Z0-9\s,.'\"\?!:;()&/\-\[\]]{10,}$")
TRANSCRIPT_PAT = re.compile(r"^[A-Z][A-Z.\-']{2,30}(\s+[A-Z][A-Z.\-']{2,30})?:\s+\S|^\(SOUNDBITE OF")
URL_PAT        = re.compile(r"https?://\S+|www\.\S+|\S+@\S+\.\S+")
SENT_END_PAT   = re.compile(r"[.!?…\"')\]]\s*$")

def classify(row: dict) -> list[str]:
    t = row["text"]
    n = row["n_tokens_est"]
    flags: list[str] = []
    if n < 4:
        flags.append("too_short")
    if n > 80:
        flags.append("too_long")
    if ALL_CAPS_PAT.match(t):
        flags.append("all_caps")
    if TRANSCRIPT_PAT.match(t):
        flags.append("transcript")
    tokens = t.split()
    url_tokens = sum(1 for tok in tokens if URL_PAT.search(tok))
    if url_tokens > 0 and (len(tokens) - url_tokens) < 2:
        flags.append("url_heavy")
    if not SENT_END_PAT.search(t) and n < 6 and not flags:
        flags.append("fragment")
    return flags

# Load source map
src_map: dict[str, str] = {}
with open(ARTICLES) as f:
    for line in f:
        a = json.loads(line)
        src_map[a["article_id"]] = a["source"]

total = 0
healthy = 0
src_total:   dict[str, int] = defaultdict(int)
src_healthy: dict[str, int] = defaultdict(int)
cat_counts:  Counter = Counter()
cat_examples: dict[str, list] = defaultdict(list)

with open(SENTENCES) as f:
    for line in f:
        row = json.loads(line)
        src = src_map.get(row["article_id"], "unknown")
        flags = classify(row)
        total += 1
        src_total[src] += 1
        if not flags:
            healthy += 1
            src_healthy[src] += 1
        else:
            for flag in flags:
                cat_counts[flag] += 1
                if len(cat_examples[flag]) < 8:
                    cat_examples[flag].append((row["sentence_id"], row["text"][:140]))

# ---- Report ----
print(f"\n{'='*60}")
print(f"  SENTENCE HEALTH AUDIT")
print(f"  sentences={total}  healthy={healthy}  unhealthy={total-healthy}")
pct = 100 * healthy / total if total else 0
print(f"  overall healthy: {pct:.1f}%  (target ≥75%)")
print(f"{'='*60}")

print(f"\n{'source':<22} {'total':>7} {'healthy':>8} {'healthy%':>9} {'status':>8}")
print("-" * 58)
for src in sorted(src_total.keys()):
    tot = src_total[src]
    hlt = src_healthy[src]
    p   = 100 * hlt / tot if tot else 0
    status = "OK" if p >= 70 else "WARN" if p >= 60 else "FAIL"
    print(f"{src:<22} {tot:>7} {hlt:>8} {p:>8.1f}%  {status:>6}")
print("-" * 58)
print(f"{'TOTAL':<22} {total:>7} {healthy:>8} {pct:>8.1f}%")

print(f"\n{'Unhealthy category breakdown':}")
print(f"{'category':<14} {'count':>7} {'% of total':>11}")
print("-" * 35)
for cat, cnt in cat_counts.most_common():
    print(f"{cat:<14} {cnt:>7} {100*cnt/total:>10.1f}%")

for cat, examples in cat_examples.items():
    print(f"\n--- {cat} examples (up to 8) ---")
    for sid, txt in examples:
        print(f"  [{sid}]")
        print(f"  {txt!r}")
