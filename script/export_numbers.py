"""Export every number quoted in the report and slides as LaTeX macros (result/tables/numbers.tex).

Both report/main.tex and slide/slides.tex \\input this file, so text, tables and slides can never
drift from result/metrics.csv and result/*.json. Run after evaluate.py, extra_analysis.py and
(if available) score_human_check.py.  Usage: .venv/bin/python script/export_numbers.py
"""
import csv
import json
import statistics as st
import sys
from collections import Counter
from pathlib import Path

# Windows consoles default to a legacy code page; force UTF-8 so non-ASCII text prints safely.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import GT_DIR, RESULT_DIR, RUN_DIR, TABLES_DIR  # noqa: E402

TOOL_NAME = {"T0": "Tzero", "T1": "Tone", "T2": "Ttwo", "T3": "Tthree", "T4": "Tfour"}
TYPE_NAME = {"ambiguity": "Amb", "incompleteness": "Inc", "inconsistency": "Con"}


def pct(x: float, nd: int = 1) -> str:
    return f"{x * 100:.{nd}f}".replace(".", "{,}")


def dec(x: float, nd: int = 2) -> str:
    return f"{x:.{nd}f}".replace(".", "{,}")


def build_text() -> str:
    """Return the full numbers.tex content (used by main() and by check_consistency.py)."""
    macros: dict[str, str] = {}
    m = {(r["tool"], r["scope"]): r for r in csv.DictReader(open(RESULT_DIR / "metrics.csv", encoding="utf-8"))}
    x = json.loads((RESULT_DIR / "extra_analysis.json").read_text(encoding="utf-8"))

    for tool, n in TOOL_NAME.items():
        p = m[(tool, "pure_strict")]
        a = m[(tool, "all_strict")]
        macros[f"P{n}"] = pct(float(p["precision_mean"]))
        macros[f"R{n}"] = pct(float(p["recall_mean"]))
        macros[f"F{n}"] = pct(float(p["f1_mean"]))
        macros[f"Miss{n}"] = pct(float(p["miss_rate_mean"]))
        macros[f"Fsd{n}"] = pct(float(p["f1_sd"]))
        lo, hi = x["pure_f1_ci95"][tool]
        macros[f"Flo{n}"], macros[f"Fhi{n}"] = pct(lo), pct(hi)
        macros[f"FAll{n}"] = pct(float(a["f1_mean"]))
        macros[f"FSeed{n}"] = pct(float(m[(tool, "seeded_strict")]["f1_mean"]))
        macros[f"FLen{n}"] = pct(x["pure_lenient"][tool]["f1_mean"])
        # reviewer effort: findings to inspect per real (ground-truth) defect = 1 / precision
        macros[f"Effort{n}"] = dec(1 / float(p["precision_mean"]), 1)
        for tp, tn in TYPE_NAME.items():
            macros[f"F{tn}{n}"] = pct(x["pure_by_type"][tool][tp]["f1_mean"], 0)
            macros[f"R{tn}{n}"] = pct(x["pure_by_type"][tool][tp]["r_mean"], 0)
    stab = x["stability_pure"]
    for tool in ["T1", "T2", "T3", "T4"]:
        n = TOOL_NAME[tool]
        macros[f"Jac{n}"] = dec(stab[tool]["jaccard"])
        macros[f"Fleiss{n}"] = dec(stab[tool]["fleiss"])

    fe = x["flag_everything"]["pure"]
    macros["PFlagAll"], macros["FFlagAll"] = pct(fe["p_mean"]), pct(fe["f1_mean"])
    for eff in x["pure_skill_effect"]:
        n = "Hydro" if eff["pair"] == "T2-T1" else "Neon"
        macros[f"SkillDF{n}"] = pct(eff["delta_f1"])
        macros[f"SkillDP{n}"] = pct(eff["delta_precision"])
        macros[f"SkillDR{n}"] = pct(abs(eff["delta_recall"]))
        macros[f"SkillLo{n}"], macros[f"SkillHi{n}"] = pct(eff["ci95"][0]), pct(eff["ci95"][1])
    for pair, n in (("T3-T1", "Plain"), ("T4-T2", "Skill")):
        e = x["model_effect"][pair]
        macros[f"ModelDF{n}"] = pct(e["delta_f1"])
        macros[f"ModelLo{n}"], macros[f"ModelHi{n}"] = pct(e["ci95"][0]), pct(e["ci95"][1])
    macros["SDMaxShift"] = pct(max(abs(v["seeded_f1_with_sd023"] - v["seeded_f1_base"]) for v in x["sd023_sensitivity"].values()))
    macros["LeakMaxShift"] = pct(max(v["leaked"]["f1_mean"] - v["clean"]["f1_mean"] for v in x["seeded_leak_comparison"].values()))

    # run cost
    rows = list(csv.DictReader(open(RUN_DIR / "run_summary.csv", encoding="utf-8")))
    for tool in ["T1", "T2", "T3", "T4"]:
        r = [q for q in rows if q["tool"] == tool]
        n = TOOL_NAME[tool]
        macros[f"Dur{n}"] = f"{st.mean(float(q['duration_s']) for q in r):.0f}"
        macros[f"Tok{n}"] = dec(st.mean(int(q["total_tokens"]) for q in r) / 1000, 1)
        pure_counts = Counter()
        for q in r:
            if q["doc_id"] != "seeded_lms":
                pure_counts[q["run"]] += int(q["findings"])
        macros[f"Found{n}"] = f"{st.mean(pure_counts.values()):.0f}"
    macros["AgyMinutes"] = f"{sum(float(q['duration_s']) for q in rows) / 60:.0f}"
    macros["AgyMTokens"] = dec(sum(int(q["total_tokens"]) for q in rows) / 1e6, 2)
    gt = json.loads((GT_DIR / "final_gt.json").read_text(encoding="utf-8"))["docs"]
    macros["GTPure"] = str(sum(len(gt[d]["findings"]) for d in ("keepass", "peering", "gammaj")))

    # AI second reviewer on the 30 Part-B cases (blind; complements, not replaces, the human check)
    cat = {c["case_id"]: c for c in json.loads((RESULT_DIR / "error_categories.json").read_text(encoding="utf-8"))["cases"]}
    key = {c["case_id"]: c for c in json.loads((RESULT_DIR / "human_check_key.json").read_text(encoding="utf-8"))["part_b"]}
    tool_ids = [k for k in key if key[k]["source"] == "tool_only"]
    v = Counter(cat[i]["verdict"] for i in tool_ids)
    c = Counter(cat[i]["category"] for i in tool_ids)
    macros["AIRevN"] = str(len(tool_ids))
    macros["AIRevReal"], macros["AIRevBorder"], macros["AIRevNot"] = str(v["real"]), str(v["borderline"]), str(v["not_real"])
    macros["AIRevRealLo"] = pct(v["real"] / len(tool_ids), 0)
    macros["AIRevRealHi"] = pct((v["real"] + v["borderline"]) / len(tool_ids), 0)
    macros["AIRevOverLiteral"], macros["AIRevNonReq"] = str(c["over_literal"]), str(c["non_requirement_text"])
    exp_ids = [k for k in key if key[k]["source"] == "expert_only"]
    macros["AIRevExpN"] = str(len(exp_ids))
    macros["AIRevExpReal"] = str(sum(cat[i]["verdict"] == "real" for i in exp_ids))

    # human check (optional until the sheets are filled)
    hc = RESULT_DIR / "human_check_results.json"
    macros["HumanCheckDone"] = "1" if hc.exists() else "0"
    if hc.exists():
        h = json.loads(hc.read_text(encoding="utf-8"))
        macros["HCKappa"] = dec(h["part_a"]["kappa"])
        macros["HCAgree"] = pct(h["part_a"]["agreement"], 0)
        rate = h["part_b"]["tool_only_real_rate"]
        macros["HCRealRate"] = pct(rate or 0, 0)
        macros["HCExpConfirmed"] = str(h["part_b"]["expert_only_confirmed"])
        macros["HCExpTotal"] = str(h["part_b"]["expert_only_total"])
        for tool, n in TOOL_NAME.items():
            macros[f"PAdj{n}"] = pct(h["adjusted_precision_pure"][tool]["adjusted_precision"])

    # Ready-made slide lines (beamer frames cannot hold \if...\fi around itemize safely).
    pending = r"\textbf{[Đang chờ kết quả kiểm tra bởi người]}"
    if hc.exists():
        macros["HCSlideA"] = rf"20 yêu cầu gắn nhãn độc lập: $\kappa = {macros['HCKappa']}$"
        macros["HCSlideB"] = rf"30 trường hợp bất đồng (ẩn nguồn): {macros['HCRealRate']}\% cảnh báo thừa là lỗi thật"
        macros["HCSlideC"] = rf"Người kiểm tra: {macros['HCRealRate']}\% là lỗi thật; Precision điều chỉnh của T4: {macros['PAdjTfour']}\%"
    else:
        macros["HCSlideA"] = macros["HCSlideB"] = macros["HCSlideC"] = pending

    lines = ["% Generated by script/export_numbers.py -- do not edit by hand."]
    lines += [f"\\newcommand{{\\num{k}}}{{{v}}}" for k, v in sorted(macros.items())]
    return "\n".join(lines) + "\n"


README_START, README_END = "<!-- RESULTS:START (generated by script/export_numbers.py) -->", "<!-- RESULTS:END -->"


def readme_block(text: str) -> str:
    """Vietnamese results summary for README.md, built from the same macros as the report."""
    n = {}
    for line in text.splitlines():
        if line.startswith("\\newcommand{\\num"):
            k, v = line[len("\\newcommand{\\num"):].split("}{", 1)
            n[k] = v[:-1].replace("{,}", ",").replace("\\%", "%").replace("\\textbf{", "").replace("}", "")
    rows = [("T0", "Bộ dò luật", "Tzero"), ("T1", "Gemini 4 Hydrogen", "Tone"), ("T2", "Gemini 4 Hydrogen + kỹ năng", "Ttwo"),
            ("T3", "Gemini 4 Neon", "Tthree"), ("T4", "Gemini 4 Neon + kỹ năng", "Tfour")]
    table = ["| Công cụ | Cấu hình | Precision | Recall | Miss rate | F1 |", "|---|---|---|---|---|---|"]
    table += [f"| {t} | {name} | {n['P' + k]}% | {n['R' + k]}% | {n['Miss' + k]}% | **{n['F' + k]}%** |" for t, name, k in rows]
    human = (f"- **Kiểm tra bởi người:** κ = {n['HCKappa']} trên 20 yêu cầu; {n['HCRealRate']}% cảnh báo thừa được xác nhận là lỗi thật."
             if n.get("HumanCheckDone") == "1" else "- **Kiểm tra bởi người:** đang chờ nhóm điền phiếu (mục 7).")
    lines = [README_START,
             "PURE (107 yêu cầu thật), so khớp chặt, trung bình 3 lượt chạy:", "", *table, "",
             f"- **RQ1:** LLM gần như không bỏ sót (Recall ≥ {n['RTfour']}%) nhưng gắn cờ quá nhiều (Precision {n['PTone']}–{n['PTfour']}%). Không có kỹ năng, LLM không hơn bộ dò luật T0.",
             f"- **RQ2:** kỹ năng `SKILL.md` tăng F1 +{n['SkillDFHydro']} (Hydrogen) và +{n['SkillDFNeon']} điểm % (Neon); khoảng tin cậy 95% không chứa 0.",
             f"- **RQ3:** thiếu sót khó nhất (F1 {n['FIncTone']}–{n['FIncTfour']}%), mâu thuẫn dễ nhất (F1 {n['FConTthree']}–{n['FConTtwo']}%).",
             f"- **RQ4:** ổn định cao qua 3 lượt (Jaccard {n['JacTtwo']}–{n['JacTone']}).",
             f"- **Phân tích lỗi:** khoảng {n['AIRevRealLo']}–{n['AIRevRealHi']}% cảnh báo thừa có thể là lỗi thật mà nhãn chuẩn bỏ qua, nên Precision thật có lẽ cao hơn.",
             human, "", "Chi tiết: `report/main.pdf`, Chương 4.", README_END]
    return "\n".join(lines)


def update_readme(text: str, write: bool = True) -> bool:
    """Replace the generated block in README.md. Returns True if it was already up to date."""
    from paths import ROOT
    readme = ROOT / "README.md"
    content = readme.read_text(encoding="utf-8")
    i, j = content.index(README_START), content.index(README_END) + len(README_END)
    new = content[:i] + readme_block(text) + content[j:]
    if write and new != content:
        readme.write_text(new, encoding="utf-8", newline="\n")
    return new == content


def main() -> None:
    text = build_text()
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    (TABLES_DIR / "numbers.tex").write_text(text, encoding="utf-8", newline="\n")
    update_readme(text)
    pending = "\\newcommand{\\numHumanCheckDone}{0}" in text
    print(f"Wrote {text.count(chr(10)) - 1} macros to result/tables/numbers.tex (human check {'pending' if pending else 'included'})")


if __name__ == "__main__":
    main()
