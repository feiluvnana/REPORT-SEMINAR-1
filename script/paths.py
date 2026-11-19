"""Single source of truth for repository paths (imported by every script)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DATASET_DIR = ROOT / "dataset"
RAW_DIR = DATASET_DIR / "raw" / "pure_xml" / "XMLZIPFile"
GT_DIR = DATASET_DIR / "ground_truth"

PROMPT_DIR = ROOT / "prompt"
SKILL_FILE = PROMPT_DIR / "SKILL.md"
PLAIN_PROMPT = PROMPT_DIR / "plain.txt"
SKILL_PROMPT = PROMPT_DIR / "skill.txt"

RESULT_DIR = ROOT / "result"
RUN_DIR = RESULT_DIR / "run"
TABLES_DIR = RESULT_DIR / "tables"

REPORT_DIR = ROOT / "report"
FIG_DIR = REPORT_DIR / "figures"
SLIDE_DIR = ROOT / "slide"


def doc_path(doc_id: str) -> Path:
    return DATASET_DIR / f"{doc_id}.json"
