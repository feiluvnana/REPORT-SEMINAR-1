"""Expert ground-truth QA helper: Cohen's kappa (Pass 1 vs Pass 2),
Pass 2 recall on seeded_lms, disagreement report, and SHA-256 freeze.

Usage:
  # 1. Check kappa, seeded recall, and emit disagreement list:
  REPORT/.venv/bin/python eval/check_gt.py --analyze

  # 2. Freeze ground_truth/*.json into ground_truth/HASHES.txt (after adjudication):
  REPORT/.venv/bin/python eval/check_gt.py --freeze

  # 3. Verify HASHES.txt integrity:
  REPORT/.venv/bin/python eval/check_gt.py --verify
"""
import argparse
import datetime
import hashlib
import json
import sys
from pathlib import Path

# Windows consoles default to a legacy code page; force UTF-8 so non-ASCII text prints safely.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]
GT_DIR = ROOT / "ground_truth"
PURE_DOCS = ["keepass", "peering", "gammaj"]
TYPES = ["ambiguity", "incompleteness", "inconsistency"]


def load_doc_reqs(doc_id: str) -> list[dict]:
    return json.loads((ROOT / f"data/{doc_id}.json").read_text(encoding="utf-8"))["requirements"]


def load_gt_map(path: Path) -> dict[str, list[dict]]:
    """Load expert_pass1.json / expert_pass2.json keyed by doc_id -> findings list.
    Accepts either {"docs": {"keepass": {"findings": [...]}}} or {"keepass": [...]}.
    """
    raw = json.loads(path.read_text(encoding="utf-8"))
    if "docs" in raw:
        return {k: v["findings"] for k, v in raw["docs"].items()}
    return {k: (v["findings"] if isinstance(v, dict) else v) for k, v in raw.items()}


def cohens_kappa(y1: list[int], y2: list[int]) -> float:
    assert len(y1) == len(y2) and len(y1) > 0
    n = len(y1)
    po = sum(a == b for a, b in zip(y1, y2)) / n
    p1 = sum(y1) / n
    p2 = sum(y2) / n
    pe = p1 * p2 + (1 - p1) * (1 - p2)
    if abs(1.0 - pe) < 1e-12:
        return 1.0 if po == 1.0 else 0.0
    return (po - pe) / (1.0 - pe)


def analyze() -> None:
    p1_path = GT_DIR / "expert_pass1.json"
    p2_path = GT_DIR / "expert_pass2.json"
    sk_path = GT_DIR / "seed_key.json"
    for p in (p1_path, p2_path, sk_path):
        if not p.exists():
            sys.exit(f"Missing required file: {p}")

    p1 = load_gt_map(p1_path)
    p2 = load_gt_map(p2_path)
    seed_key = json.loads(sk_path.read_text(encoding="utf-8"))

    # 1. Cohen's kappa over all 107 x 3 = 321 (req_id, type) pairs on PURE
    all_y1, all_y2 = [], []
    per_type_y1 = {t: [] for t in TYPES}
    per_type_y2 = {t: [] for t in TYPES}
    disagreements = []

    for doc_id in PURE_DOCS:
        reqs = load_doc_reqs(doc_id)
        f1 = {(f["req_id"], f["type"]): f for f in p1.get(doc_id, [])}
        f2 = {(f["req_id"], f["type"]): f for f in p2.get(doc_id, [])}
        for r in reqs:
            rid = r["req_id"]
            for t in TYPES:
                b1 = int((rid, t) in f1)
                b2 = int((rid, t) in f2)
                all_y1.append(b1)
                all_y2.append(b2)
                per_type_y1[t].append(b1)
                per_type_y2[t].append(b2)
                if b1 != b2:
                    disagreements.append((doc_id, rid, t, f1.get((rid, t)), f2.get((rid, t)), r["text"]))

    print(f"PURE pairs: {len(all_y1)} (107 reqs x 3 types)")
    print(f"Overall Cohen's kappa: {cohens_kappa(all_y1, all_y2):.4f}")
    for t in TYPES:
        print(f"  {t:15s} kappa: {cohens_kappa(per_type_y1[t], per_type_y2[t]):.4f}")
    print(f"Disagreements to adjudicate: {len(disagreements)}")
    for doc_id, rid, t, a, b, txt in disagreements:
        print(f"  [{doc_id}] {rid} ({t}): pass1={'YES' if a else 'NO'}, pass2={'YES' if b else 'NO'} | {txt[:90]}")

    # 2. Seeded validation (Pass 2 vs seed_key.json)
    gt_items = seed_key["findings"]
    p2_seeded = p2.get("seeded_lms", [])
    matched = 0
    missed = []
    p2_pairs = {(f["req_id"], f["type"]) for f in p2_seeded}
    for g in gt_items:
        ok = (g["req_id"], g["type"]) in p2_pairs
        if not ok and g["type"] == "inconsistency":
            ok = any((rel, "inconsistency") in p2_pairs for rel in g.get("related_ids", []))
        if ok:
            matched += 1
        else:
            missed.append((g["req_id"], g["type"], g["subtype"]))
    recall = matched / len(gt_items)
    print(f"\nSeeded LMS validation (Pass 2): {matched}/{len(gt_items)} = {recall:.1%} recall")
    if missed:
        print("  Missed seeds:", missed)


def freeze() -> None:
    targets = sorted(
        p for p in GT_DIR.iterdir()
        if p.is_file() and p.name != "HASHES.txt"
    )
    # Also freeze the tool inputs so the skill/prompts cannot be tuned after seeing GT.
    extra = sorted((ROOT / "skill").rglob("*.md")) + sorted((ROOT / "prompts").glob("*.txt"))
    if not (GT_DIR / "final_gt.json").exists():
        sys.exit("Refusing to freeze: ground_truth/final_gt.json does not exist yet.")
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    lines = [f"# Frozen UTC timestamp: {now}"]
    for p in targets:
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
        lines.append(f"{digest}  {p.name}")
    for p in extra:
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
        lines.append(f"{digest}  ../{p.relative_to(ROOT)}")
    targets = targets + extra
    (GT_DIR / "HASHES.txt").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"Froze {len(targets)} ground_truth files to ground_truth/HASHES.txt at {now}")


def verify() -> bool:
    hash_file = GT_DIR / "HASHES.txt"
    if not hash_file.exists():
        print("ERROR: ground_truth/HASHES.txt not found.", file=sys.stderr)
        return False
    recorded = {}
    for line in hash_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        digest, fname = line.split(None, 1)
        recorded[fname.strip()] = digest.strip()
    if "final_gt.json" not in recorded:
        print("ERROR: final_gt.json missing from HASHES.txt.", file=sys.stderr)
        return False
    for fname, expected in recorded.items():
        fpath = GT_DIR / fname
        if not fpath.exists():
            print(f"ERROR: Frozen file missing: {fpath}", file=sys.stderr)
            return False
        actual = hashlib.sha256(fpath.read_bytes()).hexdigest()
        if actual != expected:
            print(f"ERROR: Hash mismatch for {fname}: expected {expected}, got {actual}", file=sys.stderr)
            return False
    print("OK: All ground_truth hashes match HASHES.txt.")
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--analyze", action="store_true")
    g.add_argument("--freeze", action="store_true")
    g.add_argument("--verify", action="store_true")
    args = ap.parse_args()
    if args.analyze:
        analyze()
    elif args.freeze:
        freeze()
    elif args.verify:
        sys.exit(0 if verify() else 1)


if __name__ == "__main__":
    main()
