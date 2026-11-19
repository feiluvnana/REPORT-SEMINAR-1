"""Step 15 consistency checker for REPORT/ deliverables and git hygiene.

Usage:
  # Before Phase 3-6 results exist (checks paths, PDFs, and no Co-Authored-By trailers):
  REPORT/.venv/bin/python REPORT/script/check_consistency.py --pre-freeze

  # Full Step 15 check (requires frozen GT, metrics.csv, tables, charts, final TeX):
  REPORT/.venv/bin/python REPORT/script/check_consistency.py
"""
import argparse
import csv
import re
import subprocess
import sys
from pathlib import Path

from check_gt import verify as verify_hashes

# Windows consoles default to a legacy code page; force UTF-8 so non-ASCII text prints safely.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from paths import ROOT, REPORT_DIR, SLIDE_DIR, FIG_DIR, RESULT_DIR  # noqa: E402


def check_tex_refs(tex_path: Path, base_dir: Path, pic_dirs: list[Path]) -> list[str]:
    errs = []
    txt = tex_path.read_text(encoding="utf-8")
    for inc in re.findall(r"\\input\{([^}]+)\}", txt):
        target = (base_dir / inc)
        if not target.exists():
            errs.append(f"{tex_path.name}: missing \\input{{{inc}}}")
    for lst in re.findall(r"\\lstinputlisting(?:\[[^\]]*\])?\{([^}]+)\}", txt):
        target = (base_dir / lst)
        if not target.exists():
            errs.append(f"{tex_path.name}: missing \\lstinputlisting{{{lst}}}")
    for img in re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", txt):
        if not any((d / img).exists() for d in pic_dirs):
            errs.append(f"{tex_path.name}: missing image {img}")
    return errs


def check_git_no_coauthor() -> list[str]:
    res = subprocess.run(
        ["git", "-C", str(ROOT), "log", "--format=%H %B"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )
    if res.returncode != 0:
        return ["Could not read git log."]
    if re.search(r"co-authored-by\s*:", res.stdout, re.I):
        return ["Found forbidden Co-Authored-By line in git history."]
    return []


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pre-freeze", action="store_true")
    ap.add_argument("--allow-pending-human", action="store_true",
                    help="accept a report/slides whose human-check section is still marked as pending")
    args = ap.parse_args()

    errors: list[str] = []
    errors.extend(check_git_no_coauthor())
    errors.extend(check_tex_refs(REPORT_DIR / "main.tex", REPORT_DIR, [FIG_DIR, REPORT_DIR]))
    errors.extend(check_tex_refs(SLIDE_DIR / "slides.tex", SLIDE_DIR, [FIG_DIR, SLIDE_DIR]))

    for pdf in [REPORT_DIR / "main.pdf", SLIDE_DIR / "slides.pdf", SLIDE_DIR / "slides-notes.pdf"]:
        if not pdf.exists():
            errors.append(f"Missing compiled PDF: {pdf}")

    if not args.pre_freeze:
        if not verify_hashes():
            errors.append("HASHES.txt verification failed.")
        metrics_csv = RESULT_DIR / "metrics.csv"
        if not metrics_csv.exists():
            errors.append("Missing result/metrics.csv")
        else:
            with metrics_csv.open(encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
            if not rows:
                errors.append("result/metrics.csv is empty.")
        for chart in [
            "prf1_by_tool.png", "f1_heatmap.png", "skill_effect.png",
            "stability.png", "miss_rate_by_type.png",
        ]:
            if not (FIG_DIR / chart).exists():
                errors.append(f"Missing chart: report/figures/{chart}")
        for tex in [REPORT_DIR / "main.tex", SLIDE_DIR / "slides.tex"]:
            content = tex.read_text(encoding="utf-8")
            for marker in ["Chờ kết quả", "Chờ bảng", "Chờ số liệu", "Chờ Phase", "Sẽ bổ sung", "Sẽ phân loại", "TODO"]:
                if marker in content:
                    errors.append(f"{tex.name} still contains placeholder text: {marker!r}")
            if "numbers.tex" not in content:
                errors.append(f"{tex.name} does not \\input result/tables/numbers.tex")

        # Every quoted number comes from numbers.tex: it must match the current result files exactly.
        from export_numbers import build_text
        numbers = RESULT_DIR / "tables" / "numbers.tex"
        fresh = build_text()
        if not numbers.exists() or numbers.read_text(encoding="utf-8") != fresh:
            errors.append("result/tables/numbers.tex is stale: run script/export_numbers.py and rebuild the PDFs")
        else:
            for pdf in [REPORT_DIR / "main.pdf", SLIDE_DIR / "slides.pdf", SLIDE_DIR / "slides-notes.pdf"]:
                if pdf.exists() and pdf.stat().st_mtime + 1 < numbers.stat().st_mtime:
                    errors.append(f"{pdf.relative_to(ROOT)} is older than numbers.tex: rebuild it")
        from export_numbers import update_readme
        if not update_readme(fresh, write=False):
            errors.append("README.md results block is stale: run script/export_numbers.py")
        pending = "\\newcommand{\\numHumanCheckDone}{0}" in fresh
        if pending and not args.allow_pending_human:
            errors.append("human check still pending (fill dataset/human_check/*.csv, run score_human_check.py), "
                          "or pass --allow-pending-human")

    if errors:
        for e in errors:
            print(f"FAIL: {e}", file=sys.stderr)
        sys.exit(1)

    mode = "PRE-FREEZE" if args.pre_freeze else ("FULL, human check pending" if args.allow_pending_human else "FULL")
    print(f"CONSISTENCY_OK ({mode}): TeX references, PDFs, numbers, hashes and git commit hygiene verified.")


if __name__ == "__main__":
    main()
