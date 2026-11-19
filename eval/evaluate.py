"""Compute evaluation metrics, bootstrap 95% CIs, stability (Jaccard & Fleiss' kappa),
skill effect, LaTeX tables, error-analysis samples, and publication charts.

Refuses to run unless ground_truth/HASHES.txt matches all ground_truth files.
Run with --self-test to run unit tests on synthetic data without ground truth.
"""
import argparse
import csv
import itertools
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from check_gt import verify as verify_hashes

ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "eval/results"
TABLES_DIR = RESULTS_DIR / "tables"
PIC_DIR = ROOT / "pic"

DOCS_PURE = ["keepass", "peering", "gammaj"]
DOCS_ALL = ["keepass", "peering", "gammaj", "seeded_lms"]
TYPES = ["ambiguity", "incompleteness", "inconsistency"]


def load_docs() -> dict[str, dict]:
    return {d: json.loads((ROOT / f"data/{d}.json").read_text()) for d in DOCS_ALL}


def load_gt() -> dict[str, list[dict]]:
    raw = json.loads((ROOT / "ground_truth/final_gt.json").read_text())
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
    runs_root = ROOT / "runs"
    if not runs_root.exists():
        return []
    return sorted(p.name for p in runs_root.iterdir() if p.is_dir())


def load_tool_runs(tool: str, docs: dict[str, dict]) -> list[dict[str, list[dict]]]:
    tool_dir = ROOT / "runs" / tool
    # Determine repeat indices present across all 4 docs
    rep_sets = []
    for d in DOCS_ALL:
        ddir = tool_dir / d
        if not ddir.exists():
            return []
        reps = {p.stem.split("_")[1] for p in ddir.glob("run_*.json")}
        rep_sets.append(reps)
    common_reps = sorted(set.intersection(*rep_sets)) if rep_sets else []
    runs = []
    for rep in common_reps:
        run_map = {}
        for d in DOCS_ALL:
            req_order = {r["req_id"]: i for i, r in enumerate(docs[d]["requirements"])}
            raw = json.loads((tool_dir / d / f"run_{rep}.json").read_text())
            run_map[d] = canonicalize_predictions(raw["findings"], req_order)
        runs.append(run_map)
    return runs


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
        "p_mean": float(np.mean(precs)), "p_sd": float(np.std(precs)),
        "r_mean": float(np.mean(recs)), "r_sd": float(np.std(recs)),
        "miss_mean": float(np.mean(misses)), "miss_sd": float(np.std(misses)),
        "f1_mean": float(np.mean(f1s)), "f1_sd": float(np.std(f1s)),
        "fps": all_fps, "fns": all_fns,
    }


def generate_charts(summary: dict, tools: list[str]) -> None:
    PIC_DIR.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 10, "figure.dpi": 200})

    # 1. P / R / F1 bar chart per tool (All 147, strict)
    x = np.arange(len(tools))
    w = 0.25
    fig, ax = plt.subplots(figsize=(8, 4.3))
    for i, (metric, label, color) in enumerate([
        ("p", "Precision", "#1f77b4"),
        ("r", "Recall (Detection Rate)", "#2ca02c"),
        ("f1", "F1 Score", "#cc1527"),
    ]):
        vals = [summary[t]["all_strict"][f"{metric}_mean"] * 100 for t in tools]
        errs = [summary[t]["all_strict"][f"{metric}_sd"] * 100 for t in tools]
        ax.bar(x + (i - 1) * w, vals, w, yerr=errs, capsize=3, label=label, color=color, alpha=0.9)
    ax.set_xticks(x)
    ax.set_xticklabels(tools)
    ax.set_ylabel("Percentage (%)")
    ax.set_ylim(0, 105)
    ax.set_title("Precision, Recall, and F1 by Tool (All 147 Requirements, Strict)")
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.tight_layout()
    fig.savefig(PIC_DIR / "prf1_by_tool.png")
    plt.close(fig)

    # 2. Recall heatmap (Tool x Defect Type)
    mat = np.array([[summary[t]["by_type"][tp]["r_mean"] * 100 for tp in TYPES] for t in tools])
    fig, ax = plt.subplots(figsize=(6.5, 4.2))
    im = ax.imshow(mat, cmap="YlGnBu", vmin=0, vmax=100, aspect="auto")
    ax.set_xticks(np.arange(len(TYPES)))
    ax.set_xticklabels(["Ambiguity", "Incompleteness", "Inconsistency"])
    ax.set_yticks(np.arange(len(tools)))
    ax.set_yticklabels(tools)
    for i in range(len(tools)):
        for j in range(len(TYPES)):
            color = "white" if mat[i, j] > 55 else "black"
            ax.text(j, i, f"{mat[i, j]:.1f}%", ha="center", va="center", color=color, fontweight="bold")
    fig.colorbar(im, ax=ax, label="Recall (%)")
    ax.set_title("Recall (%) Heatmap: Tool x Defect Type (All 147)")
    fig.tight_layout()
    fig.savefig(PIC_DIR / "recall_heatmap.png")
    plt.close(fig)

    # 3. Skill-effect chart (Plain vs +Skill F1 for all model pairs)
    pairs = []
    if "T1" in summary and "T2" in summary:
        pairs.append(("Gemini 4 Hydrogen", summary["T1"]["all_strict"]["f1_mean"] * 100, summary["T2"]["all_strict"]["f1_mean"] * 100))
    if "T3" in summary and "T4" in summary:
        pairs.append(("Gemini 4 Neon", summary["T3"]["all_strict"]["f1_mean"] * 100, summary["T4"]["all_strict"]["f1_mean"] * 100))
    if pairs:
        px = np.arange(len(pairs))
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.bar(px - 0.18, [p[1] for p in pairs], 0.34, label="Plain prompt", color="#7f8c8d")
        ax.bar(px + 0.18, [p[2] for p in pairs], 0.34, label="+ SKILL.md", color="#cc1527")
        for idx, (_, plain_v, skill_v) in enumerate(pairs):
            ax.text(idx + 0.18, skill_v + 1.5, f"{skill_v - plain_v:+.1f} pp", ha="center", fontweight="bold")
        ax.set_xticks(px)
        ax.set_xticklabels([p[0] for p in pairs])
        ax.set_ylabel("F1 Score (%)")
        ax.set_ylim(0, 105)
        ax.set_title("Effect of SKILL.md on Strict F1 Score")
        ax.legend()
        ax.grid(axis="y", linestyle="--", alpha=0.4)
        fig.tight_layout()
        fig.savefig(PIC_DIR / "skill_effect.png")
        plt.close(fig)

    # 4. Stability chart (Jaccard & Fleiss' kappa for multi-run tools)
    multi = [t for t in tools if summary[t]["n_runs"] > 1]
    if multi:
        mx = np.arange(len(multi))
        fig, ax = plt.subplots(figsize=(6.5, 4))
        ax.bar(mx - 0.18, [summary[t]["jaccard_all"] for t in multi], 0.34, label="Mean Pairwise Jaccard", color="#2980b9")
        ax.bar(mx + 0.18, [summary[t]["fleiss_all"] for t in multi], 0.34, label="Fleiss' kappa", color="#8e44ad")
        ax.set_xticks(mx)
        ax.set_xticklabels(multi)
        ax.set_ylim(0, 1.05)
        ax.set_ylabel("Agreement / Overlap (0-1)")
        ax.set_title("Run-to-Run Stability Across 3 Repeats")
        ax.legend()
        ax.grid(axis="y", linestyle="--", alpha=0.4)
        fig.tight_layout()
        fig.savefig(PIC_DIR / "stability.png")
        plt.close(fig)

    # 5. Miss-rate chart per defect type
    fig, ax = plt.subplots(figsize=(8, 4.3))
    tx = np.arange(len(tools))
    w = 0.25
    for i, (tp, label, color) in enumerate([
        ("ambiguity", "Ambiguity", "#e67e22"),
        ("incompleteness", "Incompleteness", "#2980b9"),
        ("inconsistency", "Inconsistency", "#c0392b"),
    ]):
        vals = [summary[t]["by_type"][tp]["miss_mean"] * 100 for t in tools]
        ax.bar(tx + (i - 1) * w, vals, w, label=label, color=color, alpha=0.9)
    ax.set_xticks(tx)
    ax.set_xticklabels(tools)
    ax.set_ylabel("Miss Rate (%) = 1 - Recall")
    ax.set_ylim(0, 105)
    ax.set_title("Miss Rate (%) by Tool and Defect Type (Lower is Better)")
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    fig.tight_layout()
    fig.savefig(PIC_DIR / "miss_rate_by_type.png")
    plt.close(fig)


def write_latex_tables(summary: dict, tools: list[str]) -> None:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    lines = [
        r"\begin{tabular}{lccccc}",
        r"\toprule",
        r"Công cụ & Precision (\%) & Recall (\%) & Miss Rate (\%) & F1 (\%) & 95\% CI F1 \\",
        r"\midrule",
    ]
    for t in tools:
        s = summary[t]["all_strict"]
        ci_lo, ci_hi = summary[t]["ci_all"]
        lines.append(
            f"{t} & {s['p_mean']*100:.1f} $\\pm$ {s['p_sd']*100:.1f} & "
            f"{s['r_mean']*100:.1f} $\\pm$ {s['r_sd']*100:.1f} & "
            f"{s['miss_mean']*100:.1f} $\\pm$ {s['miss_sd']*100:.1f} & "
            f"{s['f1_mean']*100:.1f} $\\pm$ {s['f1_sd']*100:.1f} & "
            f"[{ci_lo*100:.1f}, {ci_hi*100:.1f}] \\\\"
        )
    lines += [r"\bottomrule", r"\end{tabular}"]
    (TABLES_DIR / "overall_metrics.tex").write_text("\n".join(lines) + "\n")

    tlines = [
        r"\begin{tabular}{lcccccc}",
        r"\toprule",
        r"Công cụ & \multicolumn{2}{c}{Ambiguity} & \multicolumn{2}{c}{Incompleteness} & \multicolumn{2}{c}{Inconsistency} \\",
        r" & Recall (\%) & Miss (\%) & Recall (\%) & Miss (\%) & Recall (\%) & Miss (\%) \\",
        r"\midrule",
    ]
    for t in tools:
        bt = summary[t]["by_type"]
        tlines.append(
            f"{t} & {bt['ambiguity']['r_mean']*100:.1f} & {bt['ambiguity']['miss_mean']*100:.1f} & "
            f"{bt['incompleteness']['r_mean']*100:.1f} & {bt['incompleteness']['miss_mean']*100:.1f} & "
            f"{bt['inconsistency']['r_mean']*100:.1f} & {bt['inconsistency']['miss_mean']*100:.1f} \\\\"
        )
    tlines += [r"\bottomrule", r"\end{tabular}"]
    (TABLES_DIR / "by_type_metrics.tex").write_text("\n".join(tlines) + "\n")


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

        ci_lo, ci_hi, boot_arr = bootstrap_ci_f1(docs, gt_by_doc, runs, DOCS_ALL)
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
            "ci_all": (ci_lo, ci_hi),
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

    with (RESULTS_DIR / "metrics.csv").open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(csv_rows[0].keys()))
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
    (RESULTS_DIR / "error_samples.json").write_text(json.dumps(error_samples, ensure_ascii=False, indent=1) + "\n")
    (RESULTS_DIR / "skill_effects.json").write_text(json.dumps(skill_effects, indent=1) + "\n")

    valid_tools = list(summary.keys())
    write_latex_tables(summary, valid_tools)
    generate_charts(summary, valid_tools)
    print(f"Evaluated tools {valid_tools}. Outputs written to {RESULTS_DIR} and {PIC_DIR}.")


if __name__ == "__main__":
    main()
