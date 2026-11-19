"""Unwrap agy / cursor-agent CLI JSON envelopes and validate findings JSON schema.

Usage:
  REPORT/.venv/bin/python parse_tool_output.py \
      --raw raw.log --doc data/peering.json --out run_1.json \
      [--workspace <scratch dir>] [--require-skill] [--meta run_1.meta.json]
Exits non-zero if the CLI failed, JSON cannot be extracted, schema validation fails,
or (for agy stream-json logs) the tool-call audit fails: web/browser tools used,
a file read outside the workspace, or (with --require-skill) SKILL.md never read.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

# Windows consoles default to a legacy code page; force UTF-8 so non-ASCII text prints safely.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

VALID_TYPES = {"ambiguity", "incompleteness", "inconsistency"}
VALID_SUBTYPES = {
    "ambiguity": {"vague_term", "referential", "syntactic", "coordination", "weak_phrase"},
    "incompleteness": {
        "tbd", "missing_actor", "missing_condition",
        "missing_error_handling", "missing_value_or_unit", "missing_consequence",
    },
    "inconsistency": {"conflicting_values", "conflicting_rules", "terminology", "duplicate"},
}


def extract_json_object(text: str) -> dict:
    s = text.strip()
    # Strip markdown code fences if present
    fence_matches = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", s, re.S)
    for cand in reversed(fence_matches):
        try:
            obj = json.loads(cand)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    # Try direct parse
    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    # Balanced-brace scan from first '{' to last '}'
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end > start:
        try:
            obj = json.loads(s[start : end + 1])
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            pass

    raise ValueError("Could not extract a valid JSON object from assistant text.")


def unwrap_cli_envelope(raw_text: str) -> str:
    stripped = raw_text.strip()
    if not stripped:
        raise ValueError("Empty CLI output.")

    # Handle single JSON envelope (agy or cursor-agent) or NDJSON lines
    for line in [stripped, *reversed(stripped.splitlines())]:
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            env = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(env, dict):
            continue
        # agy stream-json: final {"event": "result", "result": {...}}
        if env.get("event") == "result" and isinstance(env.get("result"), dict):
            env = env["result"]
        # agy envelope
        if "response" in env and "status" in env:
            if env.get("status") != "SUCCESS":
                raise ValueError(f"agy CLI returned non-SUCCESS status: {env.get('status')}")
            return str(env["response"])
        # cursor-agent envelope
        if "result" in env and "type" in env:
            if env.get("is_error"):
                raise ValueError(f"cursor-agent CLI returned error: {env.get('result')}")
            return str(env["result"])
        # Already a raw findings JSON object
        if "findings" in env:
            return line

    return raw_text


FORBIDDEN_TOOL_RE = re.compile(r"^(search_web|read_url_content|browser_.*|run_command)$")
READ_TOOLS = {"read_file", "view_file"}
SKILL_REL = "skill/req-defect-detector/SKILL.md"


def collect_stream_events(raw_text: str) -> tuple[list[dict], dict]:
    """Return (tool steps, final result dict) from an agy stream-json log; empty if not stream-json."""
    steps, result = [], {}
    for line in raw_text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(ev, dict):
            continue
        su = ev.get("step_update")
        if ev.get("event") == "step_update" and isinstance(su, dict) and su.get("step_type") == "tool":
            info = su.get("tool_info") or {}
            params = info.get("parameters") or {}
            steps.append({
                "step_index": su.get("step_index"),
                "state": su.get("state"),
                "tool_name": su.get("tool_name") or info.get("name"),
                "path": params.get("Path") or params.get("path") or params.get("AbsolutePath"),
            })
        elif ev.get("event") == "result" and isinstance(ev.get("result"), dict):
            result = ev["result"]
    return steps, result


def _norm(path: str) -> str:
    return os.path.normcase(os.path.realpath(path))


def audit_tool_calls(steps: list[dict], workspace: Path | None, require_skill: bool) -> list[str]:
    errors = []
    ws = _norm(str(workspace)) if workspace else None
    skill_read = False
    seen = set()
    for st in steps:
        if st.get("state") not in (None, "DONE"):
            continue  # in-progress or denied attempt; only completed tool calls can leak information
        name = st.get("tool_name") or ""
        key = (st.get("step_index"), name, st.get("path"))
        if key in seen:
            continue
        seen.add(key)
        if FORBIDDEN_TOOL_RE.match(name):
            errors.append(f"forbidden tool used: {name}")
        if name in READ_TOOLS and st.get("path"):
            rp = st["path"]
            full = rp if os.path.isabs(rp) or not ws else os.path.join(ws, rp)
            nf = _norm(full)
            if re.search(r"ground_truth|seed_key|final_gt|expert_pass", rp, re.I):
                errors.append(f"read of ground-truth path: {rp}")
            elif ws and not (nf == ws or nf.startswith(ws + os.sep)):
                errors.append(f"read outside workspace: {rp}")
            if nf.replace("\\", "/").endswith(SKILL_REL):
                skill_read = True
    if require_skill and not skill_read:
        errors.append("SKILL.md was never read")
    return errors


def validate_findings(obj: dict, expected_doc_id: str, valid_req_ids: set[str]) -> dict:
    if "findings" not in obj or not isinstance(obj["findings"], list):
        raise ValueError("Missing or non-list 'findings' key.")

    doc_id = obj.get("doc_id") or expected_doc_id
    if doc_id != expected_doc_id:
        raise ValueError(f"doc_id mismatch: got {doc_id!r}, expected {expected_doc_id!r}")

    cleaned = []
    for idx, item in enumerate(obj["findings"]):
        if not isinstance(item, dict):
            raise ValueError(f"Finding #{idx} is not a JSON object.")
        req_id = item.get("req_id")
        ftype = str(item.get("type", "")).strip().lower()
        subtype = str(item.get("subtype", "")).strip().lower()
        if req_id not in valid_req_ids:
            raise ValueError(f"Finding #{idx} has unknown req_id {req_id!r} for {expected_doc_id}.")
        if ftype not in VALID_TYPES:
            raise ValueError(f"Finding #{idx} has invalid type {ftype!r}.")
        if subtype not in VALID_SUBTYPES[ftype]:
            raise ValueError(f"Finding #{idx} has invalid subtype {subtype!r} for type {ftype!r}.")
        related = item.get("related_ids", [])
        if related is None:
            related = []
        if not isinstance(related, list):
            raise ValueError(f"Finding #{idx} related_ids must be a list.")
        bad_rel = [r for r in related if r not in valid_req_ids]
        if bad_rel:
            raise ValueError(f"Finding #{idx} has unknown related_ids: {bad_rel}")

        cleaned.append(
            {
                "req_id": req_id,
                "type": ftype,
                "subtype": subtype,
                "evidence": str(item.get("evidence", "")),
                "related_ids": related,
                "rationale": str(item.get("rationale", "")),
            }
        )

    return {"doc_id": expected_doc_id, "findings": cleaned}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", required=True, type=Path)
    ap.add_argument("--doc", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--workspace", type=Path, default=None)
    ap.add_argument("--require-skill", action="store_true")
    ap.add_argument("--meta", type=Path, default=None)
    args = ap.parse_args()

    doc = json.loads(args.doc.read_text(encoding="utf-8"))
    valid_req_ids = {r["req_id"] for r in doc["requirements"]}
    raw_text = args.raw.read_text(errors="replace", encoding="utf-8")

    steps, result = collect_stream_events(raw_text)
    audit_errors = audit_tool_calls(steps, args.workspace, args.require_skill) if (steps or result) else (
        ["SKILL.md was never read (no stream-json tool trace)"] if args.require_skill else [])
    if args.meta:
        args.meta.parent.mkdir(parents=True, exist_ok=True)
        meta = {
            "tool_calls": steps,
            "denied_actions": result.get("denied_actions", []),
            "duration_seconds": result.get("duration_seconds"),
            "num_turns": result.get("num_turns"),
            "usage": result.get("usage"),
            "status": result.get("status"),
            "audit_errors": audit_errors,
        }
        args.meta.write_text(json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    if audit_errors:
        raise ValueError("tool-call audit failed: " + "; ".join(audit_errors))

    assistant_text = unwrap_cli_envelope(raw_text)
    obj = extract_json_object(assistant_text)
    validated = validate_findings(obj, doc["doc_id"], valid_req_ids)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(validated, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"OK: {doc['doc_id']} -> {len(validated['findings'])} findings")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"VALIDATION_ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
