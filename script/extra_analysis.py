"""Step 5 extra analyses on top of evaluate.py (run evaluate.py first).

  1. PURE-only metrics per defect type (seeded doc is at the ceiling).
  2. PURE-only skill effect (T2-T1, T4-T3) with a paired bootstrap.
  3. "Flag everything" reference baseline (every requirement x every type).
  4. SD-023 sensitivity: count the unseeded SD-023 defect as real.
  5. Seeded count-leak comparison: leaked runs (result/run_leaked) vs clean runs.
  6. Independent hand count of strict PURE metrics for one tool, cross-checking evaluate.py.

Writes result/extra_analysis.json and result/tables/pure_by_type.tex.
Usage: .venv/bin/python script/extra_analysis.py
"""
import copy
import json
import sys
from pathlib import Path

# Windows consoles default to a legacy code page; force UTF-8 so non-ASCII text prints safely.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402

import evaluate as ev  # noqa: E402
from check_gt import verify as verify_hashes  # noqa: E402
from paths import RESULT_DIR, TABLES_DIR  # noqa: E402

LLM_TOOLS = ["T1", "T2", "T3", "T4"]
ALL_TOOLS = ["T0", *LLM_TOOLS]
LEAK_DIR = RESULT_DIR / "run_leaked"


def summarize(res: dict) -> dict:
    return {k: round(res[k], 6) for k in ("p_mean", "p_sd", "r_mean", "r_sd", "miss_mean", "f1_mean", "f1_sd")}


def flag_everything(docs: dict, doc_list: list[str]) -> list[dict]:
    run = {}
    for d in doc_list:
        run[d] = [{"req_id": r["req_id"], "type": t, "subtype": "", "evidence": "", "related_ids": [], "rationale": ""}
                  for r in docs[d]["requirements"] for t in ev.TYPES]
    for d in ev.DOCS_ALL:
        run.setdefault(d, [])
    return [run]


def load_leaked_seeded(tool: str, docs: dict) -> list[dict]:
    order = {r["req_id"]: i for i, r in enumerate(docs["seeded_lms"]["requirements"])}
    runs = []
    for p in sorted((LEAK_DIR / tool / "seeded_lms").glob("run_[0-9].json")):
        raw = json.loads(p.read_text(encoding="utf-8"))
        runs.append({"seeded_lms": ev.canonicalize_predictions(raw["findings"], order)})
    return runs


def hand_count(gt_by_doc: dict, run: dict) -> tuple[int, int, int]:
    """Independent re-implementation: set-based (req_id, type) matching with the
    inconsistency related-id fallback, each GT item matched at most once."""
    tp = fp = fn = 0
    for d in ev.DOCS_PURE:
        gts = list(gt_by_doc[d])
        used = [False] * len(gts)
        for p in run[d]:
            hit = next((i for i, g in enumerate(gts) if not used[i] and (g["req_id"], g["type"]) == (p["req_id"], p["type"])), None)
            if hit is None and p["type"] == "inconsistency":
                for i, g in enumerate(gts):
                    if used[i] or g["type"] != "inconsistency":
                        continue
                    gi, pi = {g["req_id"], *g["related_ids"]}, {p["req_id"], *p["related_ids"]}
                    if p["req_id"] in g["related_ids"] or g["req_id"] in p["related_ids"] or len(gi & pi) >= 2:
                        hit = i
                        break
            if hit is None:
                fp += 1
            else:
                used[hit] = True
                tp += 1
        fn += used.count(False)
    return tp, fp, fn


def main() -> None:
    if not verify_hashes():
        sys.exit("Refusing to analyse: HASHES.txt mismatch.")
    docs = ev.load_docs()
    gt = ev.load_gt()
    runs = {t: ev.load_tool_runs(t, docs) for t in ALL_TOOLS}
    out: dict = {}

    # 1. PURE per type
    out["pure_by_type"] = {t: {tp: summarize(ev.eval_subset(docs, gt, runs[t], ev.DOCS_PURE, filter_type=tp)) for tp in ev.TYPES}
                           for t in ALL_TOOLS}
    out["pure_lenient"] = {t: summarize(ev.eval_subset(docs, gt, runs[t], ev.DOCS_PURE, lenient=True)) for t in ALL_TOOLS}

    # 2. PURE skill effect (paired: same seed -> same resampled requirements for every tool)
    boots = {t: ev.bootstrap_ci_f1(docs, gt, runs[t], ev.DOCS_PURE) for t in ALL_TOOLS}
    out["pure_f1_ci95"] = {t: [round(boots[t][0], 6), round(boots[t][1], 6)] for t in ALL_TOOLS}
    out["pure_skill_effect"] = []
    for base, skill in (("T1", "T2"), ("T3", "T4")):
        diff = boots[skill][2] - boots[base][2]
        lo, hi = np.percentile(diff, [2.5, 97.5])
        d_f1 = ev.eval_subset(docs, gt, runs[skill], ev.DOCS_PURE)["f1_mean"] - ev.eval_subset(docs, gt, runs[base], ev.DOCS_PURE)["f1_mean"]
        d_p = ev.eval_subset(docs, gt, runs[skill], ev.DOCS_PURE)["p_mean"] - ev.eval_subset(docs, gt, runs[base], ev.DOCS_PURE)["p_mean"]
        d_r = ev.eval_subset(docs, gt, runs[skill], ev.DOCS_PURE)["r_mean"] - ev.eval_subset(docs, gt, runs[base], ev.DOCS_PURE)["r_mean"]
        out["pure_skill_effect"].append({"pair": f"{skill}-{base}", "delta_f1": round(d_f1, 6), "delta_precision": round(d_p, 6),
                                         "delta_recall": round(d_r, 6), "ci95": [round(float(lo), 6), round(float(hi), 6)]})

    # 2b. Model effect (Neon - Hydrogen), same paired bootstrap
    out["model_effect"] = {}
    for base, other in (("T1", "T3"), ("T2", "T4")):
        diff = boots[other][2] - boots[base][2]
        lo, hi = np.percentile(diff, [2.5, 97.5])
        d_f1 = ev.eval_subset(docs, gt, runs[other], ev.DOCS_PURE)["f1_mean"] - ev.eval_subset(docs, gt, runs[base], ev.DOCS_PURE)["f1_mean"]
        out["model_effect"][f"{other}-{base}"] = {"delta_f1": round(d_f1, 6), "ci95": [round(float(lo), 6), round(float(hi), 6)]}

    # 2c. Stability on PURE (pairwise Jaccard, Fleiss' kappa over the 3 repeats)
    out["stability_pure"] = {}
    for t in LLM_TOOLS:
        jac, fk = ev.compute_stability(runs[t], docs, ev.DOCS_PURE)
        out["stability_pure"][t] = {"jaccard": round(jac, 6), "fleiss": round(fk, 6)}

    # 3. Flag-everything reference
    out["flag_everything"] = {scope: summarize(ev.eval_subset(docs, gt, flag_everything(docs, dl), dl))
                              for scope, dl in (("pure", ev.DOCS_PURE), ("all", ev.DOCS_ALL))}

    # 4. SD-023 sensitivity
    gt_sd = copy.deepcopy(gt)
    gt_sd["seeded_lms"].append({"req_id": "SD-023", "type": "incompleteness", "subtype": "missing_value_or_unit",
                                "evidence": "before the due date", "related_ids": [], "rationale": "sensitivity"})
    out["sd023_sensitivity"] = {t: {"seeded_f1_base": round(ev.eval_subset(docs, gt, runs[t], ["seeded_lms"])["f1_mean"], 6),
                                    "seeded_f1_with_sd023": round(ev.eval_subset(docs, gt_sd, runs[t], ["seeded_lms"])["f1_mean"], 6),
                                    "all_f1_base": round(ev.eval_subset(docs, gt, runs[t], ev.DOCS_ALL)["f1_mean"], 6),
                                    "all_f1_with_sd023": round(ev.eval_subset(docs, gt_sd, runs[t], ev.DOCS_ALL)["f1_mean"], 6),
                                    "flagged_sd023": sum(any(f["req_id"] == "SD-023" and f["type"] == "incompleteness" for f in r["seeded_lms"]) for r in runs[t])}
                                for t in ALL_TOOLS}

    # 5. Leak comparison (seeded only)
    out["seeded_leak_comparison"] = {}
    for t in LLM_TOOLS:
        leaked = load_leaked_seeded(t, docs)
        out["seeded_leak_comparison"][t] = {"clean": summarize(ev.eval_subset(docs, gt, runs[t], ["seeded_lms"])),
                                            "leaked": summarize(ev.eval_subset(docs, gt, leaked, ["seeded_lms"])),
                                            "clean_counts": [len(r["seeded_lms"]) for r in runs[t]],
                                            "leaked_counts": [len(r["seeded_lms"]) for r in leaked]}

    # 6. Hand-count cross-check for T2 (PURE, strict)
    checks = []
    for i, run in enumerate(runs["T2"]):
        tp, fp, fn = hand_count(gt, run)
        p, r, _, f1 = ev.prf1(tp, fp, fn)
        e_tp = e_fp = e_fn = 0
        for d in ev.DOCS_PURE:
            a, b, c, _, _ = ev.match_strict(gt[d], run[d])
            e_tp, e_fp, e_fn = e_tp + a, e_fp + b, e_fn + c
        checks.append({"run": i + 1, "hand": [tp, fp, fn], "evaluate": [e_tp, e_fp, e_fn], "f1": round(f1, 6), "match": (tp, fp, fn) == (e_tp, e_fp, e_fn)})
    out["hand_check_T2_pure"] = checks
    if not all(c["match"] for c in checks):
        sys.exit("Hand count disagrees with evaluate.py: " + json.dumps(checks))

    (RESULT_DIR / "extra_analysis.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")

    # LaTeX: PURE per-type F1 / recall table
    lines = [r"\begin{tabular}{l" + "ccc" * 3 + "}", r"\toprule",
             r"& \multicolumn{3}{c}{\textbf{Ambiguity}} & \multicolumn{3}{c}{\textbf{Incompleteness}} & \multicolumn{3}{c}{\textbf{Inconsistency}} \\",
             r"\textbf{Công cụ} & P & R & $F_1$ & P & R & $F_1$ & P & R & $F_1$ \\", r"\midrule"]
    for t in ALL_TOOLS:
        cells = []
        for tp in ev.TYPES:
            m = out["pure_by_type"][t][tp]
            cells += [f"{m['p_mean']:.2f}", f"{m['r_mean']:.2f}", f"{m['f1_mean']:.2f}"]
        lines.append(f"{t} & " + " & ".join(cells).replace(".", "{,}") + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    (TABLES_DIR / "pure_by_type.tex").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("OK: extra analyses written to result/extra_analysis.json and result/tables/pure_by_type.tex")


if __name__ == "__main__":
    main()
