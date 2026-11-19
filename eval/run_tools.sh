#!/usr/bin/env bash
# Run T1-T4 across all 4 documents x 3 repeats in isolated scratch workspaces.
#   T1/T2: agy (gemini-4-hydrogen-high) Plain / +Skill
#   T3/T4: agy (gemini-4-neon-high)     Plain / +Skill
# Usage: bash REPORT/eval/run_tools.sh [--skip-hash-check]
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHON="$ROOT/.venv/bin/python"
PARSER="$SCRIPT_DIR/parse_tool_output.py"

SKIP_HASH_CHECK="${1:-}"
if [[ "$SKIP_HASH_CHECK" != "--skip-hash-check" ]]; then
  if ! "$PYTHON" "$SCRIPT_DIR/check_gt.py" --verify; then
    echo "Refusing to start Phase 4 runs before ground_truth/HASHES.txt is frozen and verified." >&2
    exit 1
  fi
fi

# Configurable non-Claude models (override via env if needed)
AGY_HYDROGEN_MODEL="${AGY_HYDROGEN_MODEL:-gemini-4-hydrogen-high}"
AGY_NEON_MODEL="${AGY_NEON_MODEL:-gemini-4-neon-high}"
REPEATS="${REPEATS:-3}"
DOCS=("keepass" "peering" "gammaj" "seeded_lms")

STATUS_FILE="$ROOT/runs/run_status.csv"
mkdir -p "$ROOT/runs"
if [[ ! -f "$STATUS_FILE" ]]; then
  echo "tool,doc_id,repeat,attempt,status,findings_count,log_path" > "$STATUS_FILE"
fi

run_one() {
  local tool="$1"
  local doc_id="$2"
  local rep="$3"

  local out_dir="$ROOT/runs/$tool/$doc_id"
  local out_json="$out_dir/run_${rep}.json"
  local out_log="$out_dir/run_${rep}.log"
  mkdir -p "$out_dir"

  if [[ -f "$out_json" ]]; then
    echo "SKIP existing: $tool/$doc_id/run_${rep}.json"
    return 0
  fi

  local doc_path="$ROOT/data/${doc_id}.json"
  local prompt_file=""
  local use_skill=0
  case "$tool" in
    T1|T3) prompt_file="$ROOT/prompts/plain_prompt.txt"; use_skill=0 ;;
    T2|T4) prompt_file="$ROOT/prompts/skill_prompt.txt"; use_skill=1 ;;
    *) echo "Unknown tool: $tool" >&2; return 1 ;;
  esac

  local scratch
  scratch="$(mktemp -d /tmp/srs_run_${tool}_${doc_id}_r${rep}_XXXXXX)"
  cp "$doc_path" "$scratch/${doc_id}.json"
  if [[ "$use_skill" -eq 1 ]]; then
    mkdir -p "$scratch/skill/req-defect-detector"
    cp "$ROOT/skill/req-defect-detector/SKILL.md" "$scratch/skill/req-defect-detector/SKILL.md"
  fi

  local full_prompt
  full_prompt="$(cat "$prompt_file")"$'\n\n'"Document JSON (${doc_id}.json):"$'\n'"$(cat "$doc_path")"

  local success=0
  local attempt=1
  while [[ "$attempt" -le 2 ]]; do
    echo "RUN $tool | $doc_id | repeat $rep | attempt $attempt"
    (
      cd "$scratch" || exit 1
      case "$tool" in
        T1)
          agy --sandbox --disable-slash-commands --model "$AGY_HYDROGEN_MODEL" \
            --output-format json --print-timeout 180s -p "$full_prompt"
          ;;
        T2)
          agy --sandbox --model "$AGY_HYDROGEN_MODEL" \
            --output-format json --print-timeout 180s -p "$full_prompt"
          ;;
        T3)
          agy --sandbox --disable-slash-commands --model "$AGY_NEON_MODEL" \
            --output-format json --print-timeout 180s -p "$full_prompt"
          ;;
        T4)
          agy --sandbox --model "$AGY_NEON_MODEL" \
            --output-format json --print-timeout 180s -p "$full_prompt"
          ;;
      esac
    ) > "$out_log" 2>&1

    if "$PYTHON" "$PARSER" --raw "$out_log" --doc "$doc_path" --out "$out_json"; then
      local cnt
      cnt="$("$PYTHON" -c "import json; print(len(json.load(open('$out_json'))['findings']))")"
      echo "$tool,$doc_id,$rep,$attempt,OK,$cnt,$out_log" >> "$STATUS_FILE"
      success=1
      break
    else
      echo "WARN: Validation failed for $tool/$doc_id/run_${rep} (attempt $attempt)" >&2
      echo "$tool,$doc_id,$rep,$attempt,FAILED,0,$out_log" >> "$STATUS_FILE"
      attempt=$((attempt + 1))
      sleep 2
    fi
  done

  rm -rf "$scratch"
  if [[ "$success" -ne 1 ]]; then
    echo "ERROR: $tool/$doc_id/run_${rep} failed after 2 attempts; logged as FAILED." >&2
  fi
}

for tool in T1 T2 T3 T4; do
  for doc_id in "${DOCS[@]}"; do
    for rep in $(seq 1 "$REPEATS"); do
      run_one "$tool" "$doc_id" "$rep"
    done
  done
done

echo "All runs finished. Summary in $STATUS_FILE"
