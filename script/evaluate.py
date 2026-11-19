"""Compute evaluation metrics, bootstrap 95% CIs, stability (Jaccard & Fleiss' kappa),
skill effect, LaTeX tables, error-analysis samples, and publication charts.

Refuses to run unless ground_truth/HASHES.txt matches all ground_truth files.
Run with --self-test to run unit tests on synthetic data without ground truth.
"""
import argparse
import csv
import itertools
import json
import re
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from check_gt import verify as verify_hashes

# Windows consoles default to a legacy code page; force UTF-8 so non-ASCII text prints safely.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from paths import ROOT, GT_DIR, RUN_DIR, TABLES_DIR, doc_path  # noqa: E402
from paths import RESULT_DIR as RESULTS_DIR, FIG_DIR as PIC_DIR  # noqa: E402

DOCS_PURE = ["keepass", "peering", "gammaj"]
DOCS_ALL = ["keepass", "peering", "gammaj", "seeded_lms"]
TYPES = ["ambiguity", "incompleteness", "inconsistency"]


def load_docs() -> dict[str, dict]:
    return {d: json.loads(doc_path(d).read_text(encoding="utf-8")) for d in DOCS_ALL}


def load_gt() -> dict[str, list[dict]]:
    raw = json.loads((GT_DIR / "final_gt.json").read_text(encoding="utf-8"))
    if "docs" in raw:
        return {k: v["findings"] for k, v in raw["docs"].items()}
    return {k: (v["findings"] if isinstance(v, dict) else v) for k, v in raw.items()}


def canonicalize_predictions(findings: list[dict], req_order: dict[str, int]) -> list[dict]:
    """1. Collapse duplicate (req_id, type) predictions (keep first).
    2. Deduplicate symmetric inconsistency predictions (if A references B and B
       references A, keep only the one anchored on the later req_id).
    """
    dedup_pair: dict[tuple[str, str], dict] = {}
    for f in findings:
        key = (f["req_id"], f["type"])
        if key not in dedup_pair:
            dedup_pair[key] = dict(f)

    # Deduplicate symmetric inconsistencies across pairs
    items = list(dedup_pair.values())
    inc_by_id = {f["req_id"]: f for f in items if f["type"] == "inconsistency"}
    drop_ids: set[str] = set()
    for rid, f in inc_by_id.items():
        for rel in f.get("related_ids", []):
            if rel in inc_by_id:
                other = inc_by_id[rel]
                if rid in other.get("related_ids", []):
                    # Both cite each other; drop the earlier one in document order
                    if req_order.get(rid, 0) < req_order.get(rel, 0):
                        drop_ids.add(rid)
                    elif req_order.get(rel, 0) < req_order.get(rid, 0):
                        drop_ids.add(rel)

    return [f for f in items if not (f["type"] == "inconsistency" and f["req_id"] in drop_ids)]


def match_strict(
    gt_items: list[dict],
    pred_items: list[dict],
    filter_type: str | None = None,
) -> tuple[int, int, int, list[dict], list[dict]]:
    """Strict matching: same (req_id, type), or for inconsistency also any GT related_id.
    Each GT item can be matched at most once.
    Returns (tp, fp, fn, false_positives, false_negatives).
    """
    gts = [g for g in gt_items if filter_type is None or g["type"] == filter_type]
    preds = [p for p in pred_items if filter_type is None or p["type"] == filter_type]

    matched_gt: set[int] = set()
    fps: list[dict] = []
    tp = 0

    for p in preds:
        hit_idx = None
        # Prefer exact req_id + type match first
        for idx, g in enumerate(gts):
            if idx in matched_gt:
                continue
            if p["req_id"] == g["req_id"] and p["type"] == g["type"]:
                hit_idx = idx
                break
        # Fallback for inconsistency: prediction on any GT related_id (or pred related_id hits GT req_id)
        if hit_idx is None and p["type"] == "inconsistency":
            for idx, g in enumerate(gts):
                if idx in matched_gt or g["type"] != "inconsistency":
                    continue
                g_ids = {g["req_id"], *g.get("related_ids", [])}
                p_ids = {p["req_id"], *p.get("related_ids", [])}
                if p["req_id"] in g.get("related_ids", []) or g["req_id"] in p.get("related_ids", []) or len(g_ids & p_ids) >= 2:
                    hit_idx = idx
                    break

        if hit_idx is not None:
            matched_gt.add(hit_idx)
            tp += 1
        else:
            fps.append(p)

    fns = [g for idx, g in enumerate(gts) if idx not in matched_gt]
    return tp, len(fps), len(fns), fps, fns


def match_lenient_req(gt_items: list[dict], pred_items: list[dict]) -> tuple[int, int, int]:
    """Binary requirement-level matching: defective (any type) vs clean."""
    gt_reqs = {g["req_id"] for g in gt_items}
    pred_reqs = {p["req_id"] for p in pred_items}
    tp = len(gt_reqs & pred_reqs)
    fp = len(pred_reqs - gt_reqs)
    fn = len(gt_reqs - pred_reqs)
    return tp, fp, fn


def prf1(tp: int, fp: int, fn: int) -> tuple[float, float, float, float]:
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    miss = 1.0 - rec if (tp + fn) > 0 else 0.0
    f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
    return prec, rec, miss, f1


def fleiss_kappa(matrix: np.ndarray) -> float:
    """matrix shape: (N_items, k_categories) with row sums equal to n_raters."""
    n_items, _ = matrix.shape
    if n_items == 0:
        return 1.0
    n_raters = int(matrix[0].sum())
    if n_raters <= 1:
        return 1.0
    p_cat = matrix.sum(axis=0) / (n_items * n_raters)
    p_e = float(np.sum(p_cat ** 2))
    p_i = (np.sum(matrix ** 2, axis=1) - n_raters) / (n_raters * (n_raters - 1))
    p_bar = float(np.mean(p_i))
    if abs(1.0 - p_e) < 1e-12:
        return 1.0 if p_bar == 1.0 else 0.0
    return (p_bar - p_e) / (1.0 - p_e)


def compute_stability(runs_preds: list[dict[str, list[dict]]], docs: dict[str, dict], doc_list: list[str]) -> tuple[float, float]:
    """Compute mean pairwise Jaccard overlap and Fleiss' kappa across 3 repeats."""
    if len(runs_preds) < 2:
        return 1.0, 1.0

    sets = []
    for run in runs_preds:
        s = {(doc_id, f["req_id"], f["type"]) for doc_id in doc_list for f in run[doc_id]}
        sets.append(s)

    jaccards = []
    for a, b in itertools.combinations(sets, 2):
        union = a | b
        jaccards.append(len(a & b) / len(union) if union else 1.0)
    mean_jacc = float(np.mean(jaccards))

    n_raters = len(runs_preds)
    rows = []
    for doc_id in doc_list:
        for r in docs[doc_id]["requirements"]:
            for t in TYPES:
                pos = sum(1 for s in sets if (doc_id, r["req_id"], t) in s)
                rows.append([pos, n_raters - pos])
    fk = fleiss_kappa(np.array(rows, dtype=float))
    return mean_jacc, fk


def bootstrap_ci_f1(
    docs: dict[str, dict],
    gt_by_doc: dict[str, list[dict]],
    runs_preds: list[dict[str, list[dict]]],
    doc_list: list[str],
    n_boot: int = 1000,
    seed: int = 42,
) -> tuple[float, float, np.ndarray]:
    """Requirement-level bootstrap (1000 resamples) over mean strict F1 across repeats."""
    rng = np.random.default_rng(seed)
    all_reqs = [(d, r["req_id"]) for d in doc_list for r in docs[d]["requirements"]]
    n_req = len(all_reqs)

    # Pre-index GT and predictions per (doc_id, req_id)
    gt_req_map: dict[tuple[str, str], list[dict]] = {k: [] for k in all_reqs}
    for d in doc_list:
        for g in gt_by_doc.get(d, []):
            gt_req_map[(d, g["req_id"])].append(g)

    pred_req_maps = []
    for run in runs_preds:
        pm: dict[tuple[str, str], list[dict]] = {k: [] for k in all_reqs}
        for d in doc_list:
            for p in run[d]:
                pm[(d, p["req_id"])].append(p)
        pred_req_maps.append(pm)

    # Note: for bootstrap speed and exact per-req preservation, resample requirements
    # and match within each resampled requirement (with inconsistency fallback restricted to sampled reqs)
    boot_f1s = np.empty(n_boot, dtype=float)
    for b in range(n_boot):
        idxs = rng.integers(0, n_req, size=n_req)
        rep_f1s = []
        for pm in pred_req_maps:
            tp = fp = fn = 0
            for idx in idxs:
                key = all_reqs[idx]
                g_sub = gt_req_map[key]
                p_sub = pm[key]
                t_tp, t_fp, t_fn, _, _ = match_strict(g_sub, p_sub)
                tp += t_tp
                fp += t_fp
                fn += t_fn
            _, _, _, f1 = prf1(tp, fp, fn)
            rep_f1s.append(f1)
        boot_f1s[b] = float(np.mean(rep_f1s))

    lo, hi = np.percentile(boot_f1s, [2.5, 97.5])
    return float(lo), float(hi), boot_f1s


def discover_tools() -> list[str]:
    runs_root = RUN_DIR
    if not runs_root.exists():
        return []
    return sorted(p.name for p in runs_root.iterdir() if p.is_dir())


def load_tool_runs(tool: str, docs: dict[str, dict]) -> list[dict[str, list[dict]]]:
    tool_dir = RUN_DIR / tool
    # Determine repeat indices present across all 4 docs
    rep_sets = []
    for d in DOCS_ALL:
        ddir = tool_dir / d
        if not ddir.exists():
            return []
        # Only run_<k>.json result files (not run_<k>.meta.json metadata).
        reps = {m.group(1) for p in ddir.glob("run_*.json") if (m := re.fullmatch(r"run_(\d+)\.json", p.name))}
        rep_sets.append(reps)
    common_reps = sorted(set.intersection(*rep_sets)) if rep_sets else []
    runs = []
    for rep in common_reps:
        run_map = {}
        for d in DOCS_ALL:
            req_order = {r["req_id"]: i for i, r in enumerate(docs[d]["requirements"])}
            raw = json.loads((tool_dir / d / f"run_{rep}.json").read_text(encoding="utf-8"))
            run_map[d] = canonicalize_predictions(raw["findings"], req_order)
        runs.append(run_map)
    return runs


def _sd(xs: list[float]) -> float:
    """Sample standard deviation over repeats (0 for a single run)."""
    return float(np.std(xs, ddof=1)) if len(xs) > 1 else 0.0


def eval_subset(
    docs: dict[str, dict],
    gt_by_doc: dict[str, list[dict]],
    runs: list[dict[str, list[dict]]],
    doc_list: list[str],
    filter_type: str | None = None,
    lenient: bool = False,
) -> dict:
    precs, recs, misses, f1s = [], [], [], []
    all_fps, all_fns = [], []
    for run in runs:
        tp = fp = fn = 0
        for d in doc_list:
            if lenient:
                t_tp, t_fp, t_fn = match_lenient_req(gt_by_doc.get(d, []), run[d])
            else:
                t_tp, t_fp, t_fn, fps, fns = match_strict(gt_by_doc.get(d, []), run[d], filter_type)
                for x in fps:
                    all_fps.append({"doc_id": d, **x})
                for x in fns:
                    all_fns.append({"doc_id": d, **x})
            tp += t_tp
            fp += t_fp
            fn += t_fn
        p, r, m, f1 = prf1(tp, fp, fn)
        precs.append(p)
        recs.append(r)
        misses.append(m)
        f1s.append(f1)
    return {
        "p_mean": float(np.mean(precs)), "p_sd": _sd(precs),
        "r_mean": float(np.mean(recs)), "r_sd": _sd(recs),
        "miss_mean": float(np.mean(misses)), "miss_sd": _sd(misses),
        "f1_mean": float(np.mean(f1s)), "f1_sd": _sd(f1s),
        "fps": all_fps, "fns": all_fns,
    }


# Validated categorical slots (dataviz reference palette, light surface) and text inks.
C_BLUE, C_ORANGE, C_AQUA = "#2a78d6", "#eb6834", "#1baf7a"
C_GRAY, INK, INK_2, SURFACE = "#9a9994", "#0b0b0b", "#52514e", "#fcfcfb"
TYPE_VI = {"ambiguity": "Mơ hồ", "incompleteness": "Thiếu sót", "inconsistency": "Mâu thuẫn"}


def _style_axes(ax) -> None:
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(INK_2)
    ax.tick_params(colors=INK_2)
    ax.grid(axis="y", color="#dcdbd5", linewidth=0.6)
    ax.set_axisbelow(True)


def _bars(ax, x, vals, width, color, label, errs=None, value_labels=False):
    bars = ax.bar(x, vals, width * 0.92, yerr=errs, capsize=2.5, label=label, color=color,
                  edgecolor=SURFACE, linewidth=1.0, error_kw={"elinewidth": 0.8, "ecolor": INK_2})
    if value_labels:
        for k, (b, v) in enumerate(zip(bars, vals)):
            top = v + (errs[k] if errs is not None else 0)  # sit above the error cap, not on it
            ax.text(b.get_x() + b.get_width() / 2, top + 1.5, f"{v:.0f}", ha="center", va="bottom", fontsize=8, color=INK)
    return bars


def generate_charts(summary: dict, tools: list[str], ref_f1: float | None = None) -> None:
    """All charts use the PURE subset (107 real requirements); the seeded doc is at the ceiling."""
    PIC_DIR.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 10, "figure.dpi": 200, "savefig.facecolor": SURFACE, "text.color": INK})

    # 1. P / R / F1 per tool (PURE, strict) + flag-everything reference
    x = np.arange(len(tools))
    w = 0.26
    fig, ax = plt.subplots(figsize=(8, 4.3))
    _style_axes(ax)
    for i, (metric, label, color) in enumerate([("p", "Precision", C_BLUE), ("r", "Recall (tỷ lệ phát hiện đúng)", C_ORANGE), ("f1", "F1", C_AQUA)]):
        vals = [summary[t]["pure_strict"][f"{metric}_mean"] * 100 for t in tools]
        errs = [summary[t]["pure_strict"][f"{metric}_sd"] * 100 for t in tools]
        _bars(ax, x + (i - 1) * w, vals, w, color, label, errs, value_labels=True)
    if ref_f1 is not None:
        ax.axhline(ref_f1 * 100, color=INK_2, linestyle="--", linewidth=1.0, label=f"F1 khi gắn cờ mọi yêu cầu ({ref_f1 * 100:.0f})")
    ax.set_xticks(x)
    ax.set_xticklabels(tools)
    ax.set_ylabel("%")
    ax.set_ylim(0, 112)
    ax.set_title("Precision, Recall, F1 theo công cụ (PURE, 107 yêu cầu, so khớp chặt)", color=INK)
    ax.legend(frameon=False, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.08), fontsize=8.5)
    fig.tight_layout()
    fig.savefig(PIC_DIR / "prf1_by_tool.png")
    plt.close(fig)

    # 2. F1 heatmap (tool x type, PURE) - sequential blue ramp. Recall is near the ceiling for
    #    every LLM tool, so F1 (driven by precision) is what separates the defect types.
    from matplotlib.colors import LinearSegmentedColormap
    seq = LinearSegmentedColormap.from_list("seq_blue", ["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"])
    mat = np.array([[summary[t]["pure_by_type"][tp]["f1_mean"] * 100 for tp in TYPES] for t in tools])
    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    im = ax.imshow(mat, cmap=seq, vmin=0, vmax=100, aspect="auto")
    ax.set_xticks(np.arange(len(TYPES)))
    ax.set_xticklabels([TYPE_VI[t] for t in TYPES])
    ax.set_yticks(np.arange(len(tools)))
    ax.set_yticklabels(tools)
    ax.tick_params(colors=INK_2, length=0)
    for side in ax.spines.values():
        side.set_visible(False)
    for i in range(len(tools)):
        for j in range(len(TYPES)):
            ax.text(j, i, f"{mat[i, j]:.0f}%", ha="center", va="center", color="white" if mat[i, j] > 60 else INK, fontweight="bold")
    fig.colorbar(im, ax=ax, label="F1 (%)")
    ax.set_title("F1 theo loại khiếm khuyết (PURE)", color=INK)
    fig.tight_layout()
    fig.savefig(PIC_DIR / "f1_heatmap.png")
    plt.close(fig)

    # 3. Skill effect: plain vs + SKILL.md, F1 on PURE
    pairs = []
    if "T1" in summary and "T2" in summary:
        pairs.append(("Gemini 4 Hydrogen\n(T1 → T2)", summary["T1"]["pure_strict"]["f1_mean"] * 100, summary["T2"]["pure_strict"]["f1_mean"] * 100))
    if "T3" in summary and "T4" in summary:
        pairs.append(("Gemini 4 Neon\n(T3 → T4)", summary["T3"]["pure_strict"]["f1_mean"] * 100, summary["T4"]["pure_strict"]["f1_mean"] * 100))
    if pairs:
        px = np.arange(len(pairs))
        fig, ax = plt.subplots(figsize=(6, 4))
        _style_axes(ax)
        _bars(ax, px - 0.18, [p[1] for p in pairs], 0.36, C_GRAY, "Câu lệnh thuần", value_labels=True)
        _bars(ax, px + 0.18, [p[2] for p in pairs], 0.36, C_BLUE, "+ SKILL.md", value_labels=True)
        for idx, (_, plain_v, skill_v) in enumerate(pairs):
            ax.text(idx, max(plain_v, skill_v) + 10, f"{skill_v - plain_v:+.1f} điểm %".replace(".", ","), ha="center", fontweight="bold", color=INK)
        ax.set_xticks(px)
        ax.set_xticklabels([p[0] for p in pairs])
        ax.set_ylabel("F1 (%)")
        ax.set_ylim(0, 100)
        ax.set_title("Tác động của SKILL.md lên F1 (PURE)", color=INK)
        ax.legend(frameon=False, loc="upper right")
        fig.tight_layout()
        fig.savefig(PIC_DIR / "skill_effect.png")
        plt.close(fig)

    # 4. Stability across the 3 repeats (PURE)
    multi = [t for t in tools if summary[t]["n_runs"] > 1]
    if multi:
        mx = np.arange(len(multi))
        fig, ax = plt.subplots(figsize=(6.5, 4))
        _style_axes(ax)
        _bars(ax, mx - 0.18, [summary[t]["jaccard_pure"] * 100 for t in multi], 0.36, C_BLUE, "Jaccard trung bình giữa các cặp lượt", value_labels=True)
        _bars(ax, mx + 0.18, [summary[t]["fleiss_pure"] * 100 for t in multi], 0.36, C_ORANGE, "Fleiss' κ (×100)", value_labels=True)
        ax.set_xticks(mx)
        ax.set_xticklabels(multi)
        ax.set_ylim(0, 112)
        ax.set_ylabel("Mức trùng khớp (0–100)")
        ax.set_title("Độ ổn định qua 3 lượt chạy lặp (PURE)", color=INK)
        ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.08), ncol=2)
        fig.tight_layout()
        fig.savefig(PIC_DIR / "stability.png")
        plt.close(fig)

    # 5. Miss rate per defect type (PURE)
    fig, ax = plt.subplots(figsize=(8, 4.3))
    _style_axes(ax)
    tx = np.arange(len(tools))
    w = 0.26
    for i, (tp, color) in enumerate([("ambiguity", C_BLUE), ("incompleteness", C_ORANGE), ("inconsistency", C_AQUA)]):
        vals = [summary[t]["pure_by_type"][tp]["miss_mean"] * 100 for t in tools]
        _bars(ax, tx + (i - 1) * w, vals, w, color, TYPE_VI[tp], value_labels=True)
    ax.set_xticks(tx)
    ax.set_xticklabels(tools)
    ax.set_ylabel("Miss rate (%) = 1 − Recall")
    ax.set_ylim(0, 105)
    ax.set_title("Tỷ lệ bỏ sót theo loại khiếm khuyết (PURE, thấp hơn là tốt hơn)", color=INK)
    ax.legend(frameon=False, ncol=3, loc="upper right")
    fig.tight_layout()
    fig.savefig(PIC_DIR / "miss_rate_by_type.png")
    plt.close(fig)


def _vn(x: float) -> str:
    """One decimal with a Vietnamese decimal comma, for LaTeX."""
    return f"{x * 100:.1f}".replace(".", "{,}")


def write_latex_tables(summary: dict, tools: list[str]) -> None:
    """overall_pure.tex (main, PURE 107 reqs) and overall_all.tex (all 147 reqs).
    The PURE per-type table (pure_by_type.tex) is written by extra_analysis.py."""
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    for name, key, ci_key in (("overall_pure.tex", "pure_strict", "ci_pure"), ("overall_all.tex", "all_strict", "ci_all")):
        lines = [
            r"\begin{tabular}{lccccc}",
            r"\toprule",
            r"\textbf{Công cụ} & \textbf{Precision (\%)} & \textbf{Recall (\%)} & \textbf{Miss rate (\%)} & \textbf{$F_1$ (\%)} & \textbf{KTC 95\% của $F_1$} \\",
            r"\midrule",
        ]
        for t in tools:
            m = summary[t][key]
            lo, hi = summary[t][ci_key]
            lines.append(
                f"{t} & {_vn(m['p_mean'])} $\\pm$ {_vn(m['p_sd'])} & {_vn(m['r_mean'])} $\\pm$ {_vn(m['r_sd'])} & "
                f"{_vn(m['miss_mean'])} $\\pm$ {_vn(m['miss_sd'])} & {_vn(m['f1_mean'])} $\\pm$ {_vn(m['f1_sd'])} & "
                f"[{_vn(lo)}; {_vn(hi)}] \\\\"
            )
        lines += [r"\bottomrule", r"\end{tabular}"]
        (TABLES_DIR / name).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def run_self_test() -> None:
    """Verify matching, canonicalization, Fleiss' kappa, and bootstrap logic on synthetic data."""
    req_order = {"R1": 0, "R2": 1, "R3": 2, "R4": 3}
    preds = [
        {"req_id": "R1", "type": "ambiguity", "subtype": "vague_term", "related_ids": []},
        {"req_id": "R1", "type": "ambiguity", "subtype": "weak_phrase", "related_ids": []},  # dup
        {"req_id": "R1", "type": "inconsistency", "subtype": "conflicting_values", "related_ids": ["R3"]},
        {"req_id": "R3", "type": "inconsistency", "subtype": "conflicting_values", "related_ids": ["R1"]},
    ]
    canon = canonicalize_predictions(preds, req_order)
    assert len(canon) == 2, f"Expected 2 canonical items, got {canon}"
    assert any(c["req_id"] == "R3" and c["type"] == "inconsistency" for c in canon)

    gt = [
        {"req_id": "R1", "type": "ambiguity", "related_ids": []},
        {"req_id": "R3", "type": "inconsistency", "related_ids": ["R1"]},
    ]
    tp, fp, fn, _, _ = match_strict(gt, canon)
    assert (tp, fp, fn) == (2, 0, 0), (tp, fp, fn)
    fk = fleiss_kappa(np.array([[3, 0], [0, 3], [3, 0]], dtype=float))
    assert abs(fk - 1.0) < 1e-9, fk
    print("SELF_TEST_OK: canonicalization, strict matching, and Fleiss' kappa verified.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        run_self_test()
        return

    if not verify_hashes():
        sys.exit("Refusing to evaluate: ground_truth/HASHES.txt missing or mismatched.")

    docs = load_docs()
    gt_by_doc = load_gt()
    tools = discover_tools()
    if not tools:
        sys.exit("No tool runs found under REPORT/runs/.")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    summary: dict[str, dict] = {}
    csv_rows = []
    boot_cache: dict[str, np.ndarray] = {}

    for t in tools:
        runs = load_tool_runs(t, docs)
        if not runs:
            print(f"Skipping {t}: incomplete runs.", file=sys.stderr)
            continue

        all_strict = eval_subset(docs, gt_by_doc, runs, DOCS_ALL)
        pure_strict = eval_subset(docs, gt_by_doc, runs, DOCS_PURE)
        seed_strict = eval_subset(docs, gt_by_doc, runs, ["seeded_lms"])
        all_lenient = eval_subset(docs, gt_by_doc, runs, DOCS_ALL, lenient=True)
        by_type = {tp: eval_subset(docs, gt_by_doc, runs, DOCS_ALL, filter_type=tp) for tp in TYPES}
        pure_by_type = {tp: eval_subset(docs, gt_by_doc, runs, DOCS_PURE, filter_type=tp) for tp in TYPES}

        ci_lo, ci_hi, boot_arr = bootstrap_ci_f1(docs, gt_by_doc, runs, DOCS_ALL)
        ci_pure_lo, ci_pure_hi, _ = bootstrap_ci_f1(docs, gt_by_doc, runs, DOCS_PURE)
        boot_cache[t] = boot_arr
        jacc_all, fk_all = compute_stability(runs, docs, DOCS_ALL)
        jacc_pure, fk_pure = compute_stability(runs, docs, DOCS_PURE)

        summary[t] = {
            "n_runs": len(runs),
            "all_strict": all_strict,
            "pure_strict": pure_strict,
            "seed_strict": seed_strict,
            "all_lenient": all_lenient,
            "by_type": by_type,
            "pure_by_type": pure_by_type,
            "ci_all": (ci_lo, ci_hi),
            "ci_pure": (ci_pure_lo, ci_pure_hi),
            "jaccard_all": jacc_all,
            "fleiss_all": fk_all,
            "jaccard_pure": jacc_pure,
            "fleiss_pure": fk_pure,
        }

        for scope, res in [
            ("all_strict", all_strict),
            ("pure_strict", pure_strict),
            ("seeded_strict", seed_strict),
            ("all_lenient", all_lenient),
            *((f"type_{tp}", by_type[tp]) for tp in TYPES),
        ]:
            csv_rows.append({
                "tool": t,
                "scope": scope,
                "n_runs": len(runs),
                "precision_mean": round(res["p_mean"], 4),
                "precision_sd": round(res["p_sd"], 4),
                "recall_mean": round(res["r_mean"], 4),
                "recall_sd": round(res["r_sd"], 4),
                "miss_rate_mean": round(res["miss_mean"], 4),
                "miss_rate_sd": round(res["miss_sd"], 4),
                "f1_mean": round(res["f1_mean"], 4),
                "f1_sd": round(res["f1_sd"], 4),
                "f1_ci95_lo": round(ci_lo, 4) if scope == "all_strict" else "",
                "f1_ci95_hi": round(ci_hi, 4) if scope == "all_strict" else "",
                "jaccard": round(jacc_all, 4) if scope == "all_strict" else "",
                "fleiss_kappa": round(fk_all, 4) if scope == "all_strict" else "",
            })

    with (RESULTS_DIR / "metrics.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(csv_rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(csv_rows)

    # Paired bootstrap skill effect (T2-T1, T4-T3)
    skill_effects = []
    for base_t, skill_t in [("T1", "T2"), ("T3", "T4")]:
        if base_t in boot_cache and skill_t in boot_cache:
            diff = boot_cache[skill_t] - boot_cache[base_t]
            lo, hi = np.percentile(diff, [2.5, 97.5])
            skill_effects.append({
                "pair": f"{skill_t}-{base_t}",
                "delta_f1": float(summary[skill_t]["all_strict"]["f1_mean"] - summary[base_t]["all_strict"]["f1_mean"]),
                "ci95": [float(lo), float(hi)],
            })

    # Export error samples for Phase 6 error analysis
    error_samples = {
        t: {"false_positives": summary[t]["all_strict"]["fps"][:35], "false_negatives": summary[t]["all_strict"]["fns"][:35]}
        for t in summary
    }
    (RESULTS_DIR / "error_samples.json").write_text(json.dumps(error_samples, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    (RESULTS_DIR / "skill_effects.json").write_text(json.dumps(skill_effects, indent=1) + "\n", encoding="utf-8", newline="\n")

    valid_tools = list(summary.keys())
    write_latex_tables(summary, valid_tools)
    # Reference: flag every (requirement, type) pair on PURE -> recall 1, precision = base rate.
    flag_all = {d: [{"req_id": r["req_id"], "type": t, "related_ids": []} for r in docs[d]["requirements"] for t in TYPES] for d in DOCS_PURE}
    ref_f1 = eval_subset(docs, gt_by_doc, [flag_all], DOCS_PURE)["f1_mean"]
    generate_charts(summary, valid_tools, ref_f1)
    print(f"Evaluated tools {valid_tools}. Outputs written to {RESULTS_DIR} and {PIC_DIR}.")


if __name__ == "__main__":
    main()
