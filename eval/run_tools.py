"""Run T1-T4 across all 4 documents x 3 repeats in isolated scratch workspaces.

  T1/T2: agy (gemini-4-hydrogen-high) Plain / +Skill
  T3/T4: agy (gemini-4-neon-high)     Plain / +Skill

Usage:
  python eval/run_tools.py [--skip-hash-check] [--tools T1 T2] [--docs keepass] [--repeats 3]

Env overrides: AGY_HYDROGEN_MODEL, AGY_NEON_MODEL, REPEATS, AGY_BIN, AGY_TIMEOUT_S.
"""
import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Windows consoles default to a legacy code page; force UTF-8 so non-ASCII text prints safely.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))
from check_gt import verify as verify_hashes  # noqa: E402

PARSER = SCRIPT_DIR / "parse_tool_output.py"
GT_DIR = ROOT / "ground_truth"
STATUS_FILE = ROOT / "runs" / "run_status.csv"
ALL_TOOLS = ["T1", "T2", "T3", "T4"]
ALL_DOCS = ["keepass", "peering", "gammaj", "seeded_lms"]
AUDIT_RE = re.compile(r"ground_truth|seed_key|final_gt|expert_pass|gt_hidden", re.I)

HYDROGEN = os.environ.get("AGY_HYDROGEN_MODEL", "gemini-4-hydrogen-high")
NEON = os.environ.get("AGY_NEON_MODEL", "gemini-4-neon-high")
TIMEOUT_S = int(os.environ.get("AGY_TIMEOUT_S", "180"))

TOOL_CFG = {
    "T1": {"model": HYDROGEN, "skill": False},
    "T2": {"model": HYDROGEN, "skill": True},
    "T3": {"model": NEON, "skill": False},
    "T4": {"model": NEON, "skill": True},
}


def find_agy() -> str:
    exe = os.environ.get("AGY_BIN") or shutil.which("agy")
    if not exe:
        home_bin = Path.home() / ".local" / "bin" / ("agy.exe" if os.name == "nt" else "agy")
        if home_bin.exists():
            exe = str(home_bin)
    if not exe:
        sys.exit("agy executable not found (set AGY_BIN or add it to PATH).")
    return exe


def agy_cmd(agy: str, tool: str, prompt: str) -> list[str]:
    cfg = TOOL_CFG[tool]
    cmd = [agy, "--sandbox"]
    if not cfg["skill"]:
        cmd.append("--disable-slash-commands")
    cmd += ["--model", cfg["model"], "--output-format", "json",
            "--print-timeout", f"{TIMEOUT_S}s", "-p", prompt]
    return cmd


def append_status(row: list) -> None:
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    new = not STATUS_FILE.exists()
    with STATUS_FILE.open("a", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        if new:
            w.writerow(["tool", "doc_id", "repeat", "attempt", "status", "findings_count", "log_path"])
        w.writerow(row)


def run_one(agy: str, tool: str, doc_id: str, rep: int) -> bool:
    out_dir = ROOT / "runs" / tool / doc_id
    out_json = out_dir / f"run_{rep}.json"
    out_log = out_dir / f"run_{rep}.log"
    out_dir.mkdir(parents=True, exist_ok=True)
    if out_json.exists():
        print(f"SKIP existing: {tool}/{doc_id}/run_{rep}.json")
        return True

    doc_path = ROOT / "data" / f"{doc_id}.json"
    use_skill = TOOL_CFG[tool]["skill"]
    prompt_file = ROOT / "prompts" / ("skill_prompt.txt" if use_skill else "plain_prompt.txt")
    doc_text = doc_path.read_text(encoding="utf-8")
    full_prompt = (prompt_file.read_text(encoding="utf-8")
                   + f"\n\nDocument JSON ({doc_id}.json):\n" + doc_text)

    scratch = Path(tempfile.mkdtemp(prefix=f"srs_run_{tool}_{doc_id}_r{rep}_"))
    try:
        shutil.copy2(doc_path, scratch / f"{doc_id}.json")
        if use_skill:
            skill_dst = scratch / "skill" / "req-defect-detector"
            skill_dst.mkdir(parents=True)
            shutil.copy2(ROOT / "skill" / "req-defect-detector" / "SKILL.md", skill_dst / "SKILL.md")

        for attempt in (1, 2):
            print(f"RUN {tool} | {doc_id} | repeat {rep} | attempt {attempt}", flush=True)
            try:
                res = subprocess.run(
                    agy_cmd(agy, tool, full_prompt), cwd=scratch,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    timeout=TIMEOUT_S + 60, check=False,
                )
                out_log.write_bytes(res.stdout or b"")
            except subprocess.TimeoutExpired as exc:
                out_log.write_bytes((exc.stdout or b"") + b"\n[run_tools] TIMEOUT\n")

            parsed = subprocess.run(
                [sys.executable, str(PARSER), "--raw", str(out_log), "--doc", str(doc_path), "--out", str(out_json)],
                capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
            )
            if parsed.returncode == 0:
                cnt = len(json.loads(out_json.read_text(encoding="utf-8"))["findings"])
                append_status([tool, doc_id, rep, attempt, "OK", cnt, out_log.relative_to(ROOT).as_posix()])
                return True
            print(f"WARN: validation failed for {tool}/{doc_id}/run_{rep} (attempt {attempt}): "
                  f"{parsed.stderr.strip()[:200]}", file=sys.stderr)
            append_status([tool, doc_id, rep, attempt, "FAILED", 0, out_log.relative_to(ROOT).as_posix()])
            time.sleep(2)
        print(f"ERROR: {tool}/{doc_id}/run_{rep} failed after 2 attempts; logged as FAILED.", file=sys.stderr)
        return False
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def audit_logs() -> None:
    hits = [p for p in sorted((ROOT / "runs").glob("T[1-4]/*/run_*.log"))
            if AUDIT_RE.search(p.read_text(encoding="utf-8", errors="replace"))]
    if hits:
        for p in hits:
            print(p, file=sys.stderr)
        print("WARNING: the logs above mention ground-truth files; inspect them and re-run those runs.", file=sys.stderr)
    else:
        print("Audit OK: no run log mentions ground-truth files.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-hash-check", action="store_true")
    ap.add_argument("--tools", nargs="+", default=ALL_TOOLS, choices=ALL_TOOLS)
    ap.add_argument("--docs", nargs="+", default=ALL_DOCS, choices=ALL_DOCS)
    ap.add_argument("--repeats", type=int, default=int(os.environ.get("REPEATS", "3")))
    args = ap.parse_args()

    if not args.skip_hash_check and not verify_hashes():
        sys.exit("Refusing to start Phase 4 runs before ground_truth/HASHES.txt is frozen and verified.")

    agy = find_agy() if args.repeats > 0 else ""

    # Hide the answer files from the tools while they run (agy --sandbox may not block reads).
    hidden_root = Path(tempfile.mkdtemp(prefix="gt_hidden_"))
    hidden = hidden_root / "ground_truth"
    shutil.move(str(GT_DIR), str(hidden))
    try:
        for tool in args.tools:
            for doc_id in args.docs:
                for rep in range(1, args.repeats + 1):
                    run_one(agy, tool, doc_id, rep)
    finally:
        shutil.move(str(hidden), str(GT_DIR))
        shutil.rmtree(hidden_root, ignore_errors=True)

    audit_logs()
    print(f"All runs finished. Summary in {STATUS_FILE}")


if __name__ == "__main__":
    main()
