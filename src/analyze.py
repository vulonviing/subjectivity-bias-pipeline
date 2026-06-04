"""Step: analyze — EDA + proxy/LLM agreement analysis.

Required outputs:
    data/analysis/agreement_metrics.json       # confusion matrix + precision/recall/F1 + Cohen's kappa
    data/analysis/disagreement_examples.csv    # proxy FPs and FNs vs LLM reference

Also produces:
    - summary_tables.csv         (distributions per outlet, block, topic, etc.)
    - llm_rationale_terms.csv    (token frequency in LLM rationales for SUBJ sentences)
    - figures/outlet_subj_bar.png
    - figures/block_topic_heatmap.png
    - figures/proxy_conf_hist.png

Reminders:
    - LLM labels are SILVER, not gold.
    - Outlet-block differences are DESCRIPTIVE, never causal.
    - Subjectivity is a PROXY for one facet of opinionated framing, not "bias".
"""
from __future__ import annotations

import json
import re
import collections
from pathlib import Path
from typing import Any

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns

from src.utils import ROOT, ANALYSIS, PROCESSED, read_jsonl


STOPWORDS = {
    "the", "a", "an", "of", "in", "to", "is", "it", "that", "this",
    "and", "or", "for", "on", "with", "as", "are", "which", "by",
    "not", "be", "has", "was", "have", "than", "its", "from", "their",
    "at", "but", "more", "most", "they", "so", "all", "about", "been",
    "will", "s", "sentence", "author", "text", "language", "rather", "own",
    "contains", "use", "using", "used", "makes", "make", "statement",
}


def _load_sentences() -> pd.DataFrame:
    rows = list(read_jsonl(PROCESSED / "llm_annotations.jsonl"))
    return pd.DataFrame(rows)


def _load_vlm() -> pd.DataFrame:
    rows = list(read_jsonl(PROCESSED / "vlm_annotations.jsonl"))
    return pd.DataFrame(rows)


# ── Agreement metrics ─────────────────────────────────────────────────────────

def compute_agreement(df: pd.DataFrame) -> dict[str, Any]:
    n = len(df)
    tp = int(((df.proxy_label == "SUBJ") & (df.llm_label == "SUBJ")).sum())
    fp = int(((df.proxy_label == "SUBJ") & (df.llm_label == "OBJ")).sum())
    fn = int(((df.proxy_label == "OBJ") & (df.llm_label == "SUBJ")).sum())
    tn = int(((df.proxy_label == "OBJ") & (df.llm_label == "OBJ")).sum())

    accuracy = (tp + tn) / n
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0

    p_proxy_subj = (tp + fp) / n
    p_llm_subj = (tp + fn) / n
    pe = p_proxy_subj * p_llm_subj + (1 - p_proxy_subj) * (1 - p_llm_subj)
    kappa = (accuracy - pe) / (1 - pe) if (1 - pe) else 0.0

    return {
        "n": n,
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "accuracy": round(accuracy, 4),
        "cohen_kappa": round(kappa, 4),
        "subj_precision": round(prec, 4),
        "subj_recall": round(rec, 4),
        "subj_f1": round(f1, 4),
        "proxy_subj_pct": round((tp + fp) / n * 100, 2),
        "llm_subj_pct": round((tp + fn) / n * 100, 2),
        "llm_mean_confidence": round(float(df.llm_confidence.mean()), 4),
    }


def compute_agreement_by(df: pd.DataFrame, col: str) -> list[dict]:
    rows = []
    for key, grp in df.groupby(col):
        m = compute_agreement(grp)
        rows.append({"group_col": col, "group_key": key, **m})
    return rows


# ── Summary tables ────────────────────────────────────────────────────────────

def _subj_stats(grp: pd.DataFrame) -> dict:
    n = len(grp)
    return {
        "n": n,
        "subj_llm_pct": round(float((grp.llm_label == "SUBJ").mean() * 100), 2),
        "subj_proxy_pct": round(float((grp.proxy_label == "SUBJ").mean() * 100), 2),
        "agreement_pct": round(float((grp.proxy_label == grp.llm_label).mean() * 100), 2),
        "fn_count": int(((grp.proxy_label == "OBJ") & (grp.llm_label == "SUBJ")).sum()),
        "fp_count": int(((grp.proxy_label == "SUBJ") & (grp.llm_label == "OBJ")).sum()),
    }


def build_summary_tables(df: pd.DataFrame) -> pd.DataFrame:
    records = []

    def add(dim, key, grp):
        records.append({"dimension": dim, "key": str(key), **_subj_stats(grp)})

    # overall
    add("overall", "all", df)

    # block
    for k, g in df.groupby("outlet_block"):
        add("block", k, g)

    # outlet
    for k, g in df.groupby("source"):
        add("outlet", k, g)

    # topic_group
    for k, g in df.groupby("topic_group"):
        add("topic_group", k, g)

    # topic
    for k, g in df.groupby("topic"):
        add("topic", k, g)

    # block × topic_group
    for k, g in df.groupby(["outlet_block", "topic_group"]):
        add("block_topic_group", "/".join(k), g)

    # block × topic
    for k, g in df.groupby(["outlet_block", "topic"]):
        add("block_topic", "/".join(k), g)

    # outlet × topic
    for k, g in df.groupby(["source", "topic"]):
        add("outlet_topic", "/".join(k), g)

    return pd.DataFrame(records)


# ── Disagreement examples ─────────────────────────────────────────────────────

def build_disagreement_examples(df: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "sentence_id", "source", "outlet_block", "topic",
        "text", "proxy_label", "proxy_score", "llm_label",
        "llm_confidence", "llm_rationale",
    ]
    fn_mask = (df.proxy_label == "OBJ") & (df.llm_label == "SUBJ")
    fp_mask = (df.proxy_label == "SUBJ") & (df.llm_label == "OBJ")

    fn_df = df[fn_mask][cols].copy(); fn_df["kind"] = "proxy_missed_subj"
    fp_df = df[fp_mask][cols].copy(); fp_df["kind"] = "proxy_false_subj"

    out = pd.concat([fn_df, fp_df], ignore_index=True)
    out = out.sort_values("llm_confidence", ascending=False)
    return out


# ── LLM rationale terms ───────────────────────────────────────────────────────

def build_rationale_terms(df: pd.DataFrame) -> pd.DataFrame:
    subj = df[df.llm_label == "SUBJ"]["llm_rationale"].dropna()
    counts: dict[str, int] = collections.Counter()
    for text in subj:
        tokens = re.findall(r"[a-z']+", text.lower())
        for t in tokens:
            if len(t) > 2 and t not in STOPWORDS:
                counts[t] += 1
    top = sorted(counts.items(), key=lambda x: -x[1])[:50]
    return pd.DataFrame(top, columns=["term", "freq"])


# ── VLM summary ───────────────────────────────────────────────────────────────

def compute_vlm_summary(vlm: pd.DataFrame, sent: pd.DataFrame) -> dict:
    n = len(vlm)
    subj_n = int((vlm.vlm_label == "SUBJ").sum())

    by_block: dict = {}
    for k, g in vlm.groupby("outlet_block"):
        by_block[k] = {
            "n": len(g),
            "subj_pct": round(float((g.vlm_label == "SUBJ").mean() * 100), 2),
            "mean_confidence": round(float(g.vlm_confidence.mean()), 4),
        }

    by_outlet: dict = {}
    for k, g in vlm.groupby("source"):
        by_outlet[k] = {
            "n": len(g),
            "subj_pct": round(float((g.vlm_label == "SUBJ").mean() * 100), 2),
            "mean_confidence": round(float(g.vlm_confidence.mean()), 4),
        }

    # article-level text SUBJ majority vs VLM image label
    art_text = (
        sent.groupby("article_id")
        .apply(lambda g: (g.llm_label == "SUBJ").mean() >= 0.5)
        .rename("text_subj_majority")
        .reset_index()
    )
    merged = vlm[["article_id", "vlm_label"]].merge(art_text, on="article_id", how="inner")
    cross: dict = {}
    for (ts, vs), cnt in merged.groupby(["text_subj_majority", "vlm_label"]).size().items():
        cross[f"text_subj_majority={ts}_vlm={vs}"] = int(cnt)

    return {
        "n_articles": n,
        "vlm_subj_n": subj_n,
        "vlm_subj_pct": round(subj_n / n * 100, 2),
        "vlm_mean_confidence": round(float(vlm.vlm_confidence.mean()), 4),
        "by_block": by_block,
        "by_outlet": by_outlet,
        "text_vs_image_cross": cross,
    }


# ── Figures ───────────────────────────────────────────────────────────────────

def plot_outlet_bar(df: pd.DataFrame, out_path: Path) -> None:
    tbl = (
        df.groupby("source")
        .agg(
            llm_subj=("llm_label", lambda x: (x == "SUBJ").mean() * 100),
            proxy_subj=("proxy_label", lambda x: (x == "SUBJ").mean() * 100),
            block=("outlet_block", "first"),
        )
        .reset_index()
        .sort_values("llm_subj", ascending=False)
    )

    x = range(len(tbl))
    width = 0.38
    colors = {"left": "#4878d0", "right": "#d65f5f"}

    fig, ax = plt.subplots(figsize=(10, 5))
    bar_colors = [colors.get(b, "#aaa") for b in tbl["block"]]
    ax.bar([i - width / 2 for i in x], tbl["llm_subj"], width, label="LLM SUBJ %", color=bar_colors, alpha=0.85)
    ax.bar([i + width / 2 for i in x], tbl["proxy_subj"], width, label="Proxy SUBJ %", color=bar_colors, alpha=0.42)
    ax.set_xticks(list(x))
    ax.set_xticklabels(tbl["source"], rotation=30, ha="right", fontsize=9)
    ax.set_ylabel("SUBJ %")
    ax.set_title("Outlet SUBJ rate — LLM (dark) vs Proxy (light)\nBlue = left block, Red = right block")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_block_topic_heatmap(df: pd.DataFrame, out_path: Path) -> None:
    tbl = (
        df.groupby(["outlet_block", "topic"])
        .apply(lambda g: round((g.llm_label == "SUBJ").mean() * 100, 1))
        .reset_index(name="subj_llm_pct")
    )
    pivot = tbl.pivot(index="outlet_block", columns="topic", values="subj_llm_pct")
    # count mask: hide cells with < 30 sentences
    count = df.groupby(["outlet_block", "topic"]).size().reset_index(name="n")
    count_pivot = count.pivot(index="outlet_block", columns="topic", values="n").fillna(0)
    mask = count_pivot < 30

    fig, ax = plt.subplots(figsize=(12, 3))
    sns.heatmap(
        pivot, mask=mask, annot=True, fmt=".1f", cmap="YlOrRd",
        vmin=0, vmax=65, linewidths=0.5, ax=ax, cbar_kws={"label": "LLM SUBJ %"},
    )
    ax.set_title("LLM SUBJ % by block × topic  (cells with n<30 hidden)")
    ax.set_xlabel(""); ax.set_ylabel("")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def plot_proxy_conf_hist(df: pd.DataFrame, out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(8, 4))
    for label, grp in df.groupby("llm_label"):
        ax.hist(grp["proxy_score"], bins=40, alpha=0.55, label=f"LLM={label}", density=True)
    ax.set_xlabel("Proxy confidence score")
    ax.set_ylabel("Density")
    ax.set_title("Proxy confidence distribution by LLM silver label")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    ANALYSIS.mkdir(parents=True, exist_ok=True)
    (ANALYSIS / "figures").mkdir(exist_ok=True)

    print("Loading sentences …")
    df = _load_sentences()
    print(f"  {len(df)} sentences loaded")

    print("Loading VLM annotations …")
    vlm = _load_vlm()
    print(f"  {len(vlm)} articles loaded")

    # 1. Agreement metrics
    print("Computing agreement metrics …")
    metrics: dict[str, Any] = {"overall": compute_agreement(df)}
    metrics["by_block"] = compute_agreement_by(df, "outlet_block")
    metrics["by_outlet"] = compute_agreement_by(df, "source")
    metrics["vlm"] = compute_vlm_summary(vlm, df)

    out = ANALYSIS / "agreement_metrics.json"
    out.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Written: {out}")

    # 2. Summary tables
    print("Building summary tables …")
    st = build_summary_tables(df)
    out = ANALYSIS / "summary_tables.csv"
    st.to_csv(out, index=False)
    print(f"  Written: {out}  ({len(st)} rows)")

    # 3. Disagreement examples
    print("Building disagreement examples …")
    dis = build_disagreement_examples(df)
    out = ANALYSIS / "disagreement_examples.csv"
    dis.to_csv(out, index=False)
    print(f"  Written: {out}  ({len(dis)} rows)")

    # 4. LLM rationale terms
    print("Building rationale terms …")
    terms = build_rationale_terms(df)
    out = ANALYSIS / "llm_rationale_terms.csv"
    terms.to_csv(out, index=False)
    print(f"  Written: {out}")

    # 5. Figures
    print("Generating figures …")
    plot_outlet_bar(df, ANALYSIS / "figures" / "outlet_subj_bar.png")
    print("  outlet_subj_bar.png")
    plot_block_topic_heatmap(df, ANALYSIS / "figures" / "block_topic_heatmap.png")
    print("  block_topic_heatmap.png")
    plot_proxy_conf_hist(df, ANALYSIS / "figures" / "proxy_conf_hist.png")
    print("  proxy_conf_hist.png")

    print("\nDone.")


if __name__ == "__main__":
    main()
