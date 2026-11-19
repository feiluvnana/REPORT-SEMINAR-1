"""Build the human-check sheets (Step 6). Deterministic (seed 2026).

Part A (blind labelling): 20 PURE requirements, stratified by document and by whether the
  frozen ground truth has a finding (10 with, 10 without). No AI labels are shown.
Part B (disagreement review): every PURE (req_id, type) the expert labelled but some LLM run
  missed, plus 25 tool-only flags sampled per defect type. Shuffled, with no source shown
  (reviewers do not see whether a claim came from a tool or the expert).

Writes dataset/human_check/part_a.csv, part_b.csv (UTF-8 with BOM so Excel shows Vietnamese)
and the hidden key result/human_check_key.json. Usage: .venv/bin/python script/make_human_check.py
"""
import csv
import json
import random
import sys
from collections import Counter
from pathlib import Path

# Windows consoles default to a legacy code page; force UTF-8 so non-ASCII text prints safely.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
import evaluate as ev  # noqa: E402
from paths import DATASET_DIR, RESULT_DIR  # noqa: E402

SEED = 2026
OUT_DIR = DATASET_DIR / "human_check"
N_A_WITH, N_A_WITHOUT, N_B_FP = 10, 10, 25
TYPE_VI = {"ambiguity": "Mơ hồ", "incompleteness": "Thiếu sót", "inconsistency": "Mâu thuẫn"}


def write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def main() -> None:
    rng = random.Random(SEED)
    docs = ev.load_docs()
    gt = ev.load_gt()
    text = {(d, r["req_id"]): r["text"] for d in ev.DOCS_PURE for r in docs[d]["requirements"]}

    # ---------- Part A ----------
    with_gt = sorted({(d, g["req_id"]) for d in ev.DOCS_PURE for g in gt[d]})
    without_gt = sorted(k for k in text if k not in set(with_gt))

    def stratified(pool: list, n: int) -> list:
        by_doc = {d: [k for k in pool if k[0] == d] for d in ev.DOCS_PURE}
        total = len(pool)
        quota = {d: round(n * len(v) / total) for d, v in by_doc.items()}
        while sum(quota.values()) != n:  # fix rounding drift
            d = max(by_doc, key=lambda x: len(by_doc[x])) if sum(quota.values()) < n else max(quota, key=quota.get)
            quota[d] += 1 if sum(quota.values()) < n else -1
        picked = []
        for d in ev.DOCS_PURE:
            picked += rng.sample(by_doc[d], quota[d])
        return picked

    part_a = stratified(with_gt, N_A_WITH) + stratified(without_gt, N_A_WITHOUT)
    rng.shuffle(part_a)
    rows_a = [[f"A{i + 1:02d}", d, rid, text[(d, rid)], "", "", "", "", ""] for i, (d, rid) in enumerate(part_a)]
    write_csv(OUT_DIR / "part_a.csv",
              ["case_id", "doc_id", "req_id", "requirement_text",
               "ambiguity_0_1", "incompleteness_0_1", "inconsistency_0_1", "inconsistency_related_ids", "note"], rows_a)

    # ---------- Part B ----------
    fp, fn, example = Counter(), Counter(), {}
    for t in ["T1", "T2", "T3", "T4"]:
        for run in ev.load_tool_runs(t, docs):
            for d in ev.DOCS_PURE:
                _, _, _, fps, fns = ev.match_strict(gt[d], run[d])
                for x in fps:
                    k = (d, x["req_id"], x["type"])
                    fp[k] += 1
                    example.setdefault(k, x)
                for x in fns:
                    fn[(d, x["req_id"], x["type"])] += 1
    gt_item = {(d, g["req_id"], g["type"]): g for d in ev.DOCS_PURE for g in gt[d]}

    fp_by_type = {tp: sorted(k for k in fp if k[2] == tp) for tp in ev.TYPES}
    total_fp = len(fp)
    quota = {tp: max(1, round(N_B_FP * len(v) / total_fp)) for tp, v in fp_by_type.items() if v}
    while sum(quota.values()) > N_B_FP:
        quota[max(quota, key=quota.get)] -= 1
    while sum(quota.values()) < N_B_FP:
        quota[max(quota, key=lambda t: len(fp_by_type[t]))] += 1
    fp_pick = [k for tp in ev.TYPES for k in rng.sample(fp_by_type[tp], quota.get(tp, 0))]
    cases = [("tool_only", k) for k in fp_pick] + [("expert_only", k) for k in sorted(fn)]
    rng.shuffle(cases)

    rows_b, key = [], []
    for i, (src, (d, rid, tp)) in enumerate(cases):
        item = example[(d, rid, tp)] if src == "tool_only" else gt_item[(d, rid, tp)]
        rel = item.get("related_ids", []) or []
        rel_text = " | ".join(f"{r}: {text.get((d, r), '')}" for r in rel)
        cid = f"B{i + 1:02d}"
        rows_b.append([cid, d, rid, text[(d, rid)], TYPE_VI[tp], item.get("subtype", ""), item.get("evidence", ""),
                       item.get("rationale", ""), rel_text, "", ""])
        key.append({"case_id": cid, "doc_id": d, "req_id": rid, "type": tp, "source": src,
                    "llm_runs_flagging" if src == "tool_only" else "llm_runs_missing": (fp if src == "tool_only" else fn)[(d, rid, tp)]})
    write_csv(OUT_DIR / "part_b.csv",
              ["case_id", "doc_id", "req_id", "requirement_text", "claimed_defect_type", "claimed_subtype",
               "evidence", "rationale", "related_requirements", "is_real_defect_yes_no_unsure", "note"], rows_b)

    (RESULT_DIR / "human_check_key.json").write_text(json.dumps({
        "seed": SEED,
        "part_a": [{"case_id": r[0], "doc_id": r[1], "req_id": r[2]} for r in rows_a],
        "part_b": key,
        "population": {"tool_only_pairs": total_fp, "tool_only_by_type": {tp: len(v) for tp, v in fp_by_type.items()},
                       "expert_only_pairs": len(fn), "part_b_tool_only_quota": quota},
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"Part A: {len(rows_a)} requirements; Part B: {len(rows_b)} cases "
          f"({len(fp_pick)} tool-only of {total_fp}, {len(fn)} expert-only). Key: result/human_check_key.json")


if __name__ == "__main__":
    main()
