"""Rule-based baseline SRS defect detector (T0 — Smella/QuARS-style smells).

Runs deterministically over all 4 normalized documents in REPORT/data/ and writes
REPORT/runs/T0/<doc>/run_1.json matching the shared findings schema.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ["keepass", "peering", "gammaj", "seeded_lms"]

VAGUE_WORDS = [
    "fast", "quickly", "rapid", "rapidly", "easy", "easily", "user-friendly",
    "intuitive", "simple", "clear", "clearly", "sufficient", "sufficiently",
    "adequate", "adequately", "appropriate", "appropriately", "reasonable",
    "reasonably", "acceptable", "timely", "many", "several", "large", "small",
    "effective", "effectively", "efficient", "efficiently", "flexible",
    "minimal", "robust", "reliable", "seamless", "noticeable", "more than a line",
]
WEAK_PHRASES = [
    "where possible", "if possible", "as appropriate", "if appropriate",
    "as needed", "if necessary", "if applicable", "etc.", "and so on",
]
TBD_RE = re.compile(r"\b(tbd|tba|tbc|todo|to be determined|to be defined)\b|\?\?\?", re.I)
COORD_RE = re.compile(r"\band/or\b", re.I)
PRONOUN_RE = re.compile(r"\b(him|his|her|hers|he|she)\b", re.I)
PASSIVE_RE = re.compile(
    r"\b(?:shall|must|will|should|can|cannot|is|are|be)\s+be\s+[a-z]+(?:ed|en)\b"
    r"|\b(?:is|are)\s+(?:defined|identified|reported|detected|rejected|established|deployed|placed|considered|replicated|acted)\b",
    re.I,
)
BY_ACTOR_RE = re.compile(r"\bby\s+(?:the\s+|a\s+|an\s+)?[A-Z][A-Za-z0-9_-]+")
MISSING_VAL_RE = re.compile(r"\b(?:allowed maximum|maximum allowed|configurable limit|defined number)\b", re.I)


def normalize_tokens(text: str) -> set[str]:
    cleaned = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    return {tok for tok in cleaned.split() if len(tok) > 1}


def detect_doc(doc: dict) -> dict:
    findings = []
    seen_pairs: set[tuple[str, str]] = set()
    prior_reqs: list[tuple[str, str, set[str]]] = []

    def add_finding(req_id: str, ftype: str, subtype: str, evidence: str, related_ids: list[str], rationale: str) -> None:
        key = (req_id, ftype)
        if key in seen_pairs:
            return
        seen_pairs.add(key)
        findings.append(
            {
                "req_id": req_id,
                "type": ftype,
                "subtype": subtype,
                "evidence": evidence,
                "related_ids": related_ids,
                "rationale": rationale,
            }
        )

    for req in doc["requirements"]:
        rid = req["req_id"]
        text = req["text"]
        low = text.lower()

        # --- Ambiguity checks ---
        if m := COORD_RE.search(text):
            add_finding(rid, "ambiguity", "coordination", m.group(0), [], "Matched 'and/or' coordination smell.")
        else:
            weak_hits = [p for p in WEAK_PHRASES if re.search(rf"\b{re.escape(p.rstrip('.'))}", low)]
            vague_hits = [w for w in VAGUE_WORDS if re.search(rf"\b{re.escape(w)}\b", low)]
            if weak_hits:
                add_finding(
                    rid, "ambiguity", "weak_phrase", ", ".join(weak_hits), [],
                    f"Matched weak phrase(s): {', '.join(weak_hits)}.",
                )
            elif vague_hits:
                add_finding(
                    rid, "ambiguity", "vague_term", ", ".join(vague_hits), [],
                    f"Matched vague term(s): {', '.join(vague_hits)}.",
                )
            elif m := PRONOUN_RE.search(text):
                add_finding(
                    rid, "ambiguity", "referential", m.group(0), [],
                    f"Matched potentially ambiguous pronoun '{m.group(0)}'.",
                )

        # --- Incompleteness checks ---
        if m := TBD_RE.search(text):
            add_finding(rid, "incompleteness", "tbd", m.group(0), [], f"Matched placeholder '{m.group(0)}'.")
        elif m := MISSING_VAL_RE.search(text):
            add_finding(rid, "incompleteness", "missing_value_or_unit", m.group(0), [], "Unquantified limit phrase without value.")
        elif (m := PASSIVE_RE.search(text)) and not BY_ACTOR_RE.search(text[m.end():]):
            add_finding(
                rid, "incompleteness", "missing_actor", m.group(0), [],
                f"Passive construction '{m.group(0)}' without an explicit 'by <Actor>' agent.",
            )

        # --- Inconsistency (duplicate similarity) checks ---
        toks = normalize_tokens(text)
        dup_ids = []
        for prev_id, prev_text, prev_toks in prior_reqs:
            if not toks or not prev_toks:
                continue
            jacc = len(toks & prev_toks) / len(toks | prev_toks)
            if text.strip().lower() == prev_text.strip().lower() or jacc >= 0.80:
                dup_ids.append(prev_id)
        if dup_ids:
            add_finding(
                rid, "inconsistency", "duplicate", text[:120], dup_ids,
                f"High lexical similarity (Jaccard >= 0.80) with earlier requirement(s): {', '.join(dup_ids)}.",
            )

        prior_reqs.append((rid, text, toks))

    return {"doc_id": doc["doc_id"], "findings": findings}


def main() -> None:
    for doc_id in DOCS:
        doc = json.loads((ROOT / f"data/{doc_id}.json").read_text())
        out = detect_doc(doc)
        out_dir = ROOT / f"runs/T0/{doc_id}"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "run_1.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
        by_type = {}
        for f in out["findings"]:
            by_type[f["type"]] = by_type.get(f["type"], 0) + 1
        print(f"T0 {doc_id}: {len(out['findings'])} findings -> {by_type}")


if __name__ == "__main__":
    main()
