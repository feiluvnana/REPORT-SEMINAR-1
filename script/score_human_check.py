"""Score the filled human-check sheets (Step 6). Does not modify the frozen ground truth.

Part A -> Cohen's kappa between the human labeller and the frozen ground truth over the
          20 x 3 (req_id, type) binary pairs (overall and per type).
Part B -> share of sampled tool-only flags the team judged to be real defects (per type),
          an "adjusted precision" per tool on PURE that counts that share of each type's
          false positives as correct, and how many expert-only labels the team confirmed.

Writes result/human_check_results.json. Usage:
  .venv/bin/python script/score_human_check.py [--dir dataset/human_check]
"""
import argparse
import csv
import json
import sys
from pathlib import Path

# Windows consoles default to a legacy code page; force UTF-8 so non-ASCII text prints safely.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evaluate as ev  # noqa: E402
from check_gt import cohens_kappa  # noqa: E402
from paths import DATASET_DIR, RESULT_DIR  # noqa: E402

YES = {"yes", "y", "có", "co", "1", "true", "đúng", "dung"}
NO = {"no", "n", "không", "khong", "0", "false", "sai"}
UNSURE = {"unsure", "?", "không chắc", "khong chac", "chưa chắc", "chua chac"}


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def to01(value: str, where: str) -> int:
    v = (value or "").strip().lower()
    if v in {"1", "x", "yes", "có", "co"}:
        return 1
    if v in {"0", "no", "không", "khong"}:
        return 0
    raise ValueError(f"{where}: expected 0 or 1, got {value!r}")


def decision(value: str, where: str) -> str:
    v = (value or "").strip().lower()
    if v in YES:
        return "yes"
    if v in NO:
        return "no"
    if v in UNSURE:
        return "unsure"
    raise ValueError(f"{where}: expected yes / no / unsure, got {value!r}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, default=DATASET_DIR / "human_check")
    args = ap.parse_args()

    key = json.loads((RESULT_DIR / "human_check_key.json").read_text(encoding="utf-8"))
    docs = ev.load_docs()
    gt = ev.load_gt()
    gt_pairs = {(d, g["req_id"], g["type"]) for d in ev.DOCS_PURE for g in gt[d]}
    errors: list[str] = []
    out: dict = {}

    # ---------- Part A ----------
    rows_a = {r["case_id"]: r for r in read_csv(args.dir / "part_a.csv")}
    human, expert = {t: [] for t in ev.TYPES}, {t: [] for t in ev.TYPES}
    for k in key["part_a"]:
        r = rows_a.get(k["case_id"])
        if r is None:
            errors.append(f"part_a: missing row {k['case_id']}")
            continue
        for t in ev.TYPES:
            try:
                human[t].append(to01(r[f"{t}_0_1"], f"part_a {k['case_id']} {t}"))
                expert[t].append(int((k["doc_id"], k["req_id"], t) in gt_pairs))
            except ValueError as exc:
                errors.append(str(exc))
    if not errors:
        all_h = [x for t in ev.TYPES for x in human[t]]
        all_e = [x for t in ev.TYPES for x in expert[t]]
        out["part_a"] = {
            "pairs": len(all_h),
            "agreement": round(sum(a == b for a, b in zip(all_h, all_e)) / len(all_h), 4),
            "kappa": round(cohens_kappa(all_h, all_e), 4),
            "kappa_by_type": {t: round(cohens_kappa(human[t], expert[t]), 4) for t in ev.TYPES},
            "human_positive": sum(all_h), "expert_positive": sum(all_e),
        }

    # ---------- Part B ----------
    rows_b = {r["case_id"]: r for r in read_csv(args.dir / "part_b.csv")}
    tally = {"tool_only": {t: {"yes": 0, "no": 0, "unsure": 0} for t in ev.TYPES},
             "expert_only": {t: {"yes": 0, "no": 0, "unsure": 0} for t in ev.TYPES}}
    for k in key["part_b"]:
        r = rows_b.get(k["case_id"])
        if r is None:
            errors.append(f"part_b: missing row {k['case_id']}")
            continue
        try:
            tally[k["source"]][k["type"]][decision(r["is_real_defect_yes_no_unsure"], f"part_b {k['case_id']}")] += 1
        except ValueError as exc:
            errors.append(str(exc))
    if errors:
        print("The sheets are not complete yet:", file=sys.stderr)
        for e in errors:
            print("  -", e, file=sys.stderr)
        sys.exit(1)

    def real_rate(c: dict) -> float | None:
        n = c["yes"] + c["no"]
        return c["yes"] / n if n else None

    rate_by_type = {t: real_rate(tally["tool_only"][t]) for t in ev.TYPES}
    tool_all = {s: sum(tally["tool_only"][t][s] for t in ev.TYPES) for s in ("yes", "no", "unsure")}
    overall = real_rate(tool_all)
    out["part_b"] = {"tally": tally, "tool_only_real_rate_by_type": rate_by_type, "tool_only_real_rate": overall,
                     "expert_only_confirmed": sum(tally["expert_only"][t]["yes"] for t in ev.TYPES),
                     "expert_only_total": sum(sum(tally["expert_only"][t].values()) for t in ev.TYPES)}

    # Adjusted precision on PURE: each false positive of type t counts as correct with probability rate_t
    # (falls back to the overall rate when a type had no decided sample).
    adj = {}
    for tool in ["T0", "T1", "T2", "T3", "T4"]:
        vals = []
        for run in ev.load_tool_runs(tool, docs):
            tp = fp = 0.0
            for d in ev.DOCS_PURE:
                t_tp, _, _, fps, _ = ev.match_strict(gt[d], run[d])
                tp += t_tp
                for x in fps:
                    r = rate_by_type.get(x["type"])
                    fp += 1
                    tp += (r if r is not None else (overall or 0.0))
                    fp -= (r if r is not None else (overall or 0.0))
            vals.append(tp / (tp + fp) if tp + fp else 0.0)
        strict = ev.eval_subset(docs, gt, ev.load_tool_runs(tool, docs), ev.DOCS_PURE)["p_mean"]
        adj[tool] = {"strict_precision": round(strict, 4), "adjusted_precision": round(sum(vals) / len(vals), 4)}
    out["adjusted_precision_pure"] = adj

    (RESULT_DIR / "human_check_results.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n",
                                                         encoding="utf-8", newline="\n")
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
