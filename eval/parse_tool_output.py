"""Unwrap agy / cursor-agent CLI JSON envelopes and validate findings JSON schema.

Usage:
  REPORT/.venv/bin/python parse_tool_output.py \
      --raw raw.log --doc data/peering.json --out run_1.json
Exits non-zero if the CLI failed, JSON cannot be extracted, or schema validation fails.
"""
import argparse
import json
import re
import sys
from pathlib import Path

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
    args = ap.parse_args()

    doc = json.loads(args.doc.read_text())
    valid_req_ids = {r["req_id"] for r in doc["requirements"]}
    raw_text = args.raw.read_text(errors="replace")

    assistant_text = unwrap_cli_envelope(raw_text)
    obj = extract_json_object(assistant_text)
    validated = validate_findings(obj, doc["doc_id"], valid_req_ids)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(validated, ensure_ascii=False, indent=1) + "\n")
    print(f"OK: {doc['doc_id']} -> {len(validated['findings'])} findings")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"VALIDATION_ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
