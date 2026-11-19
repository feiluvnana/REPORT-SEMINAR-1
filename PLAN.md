# PLAN — Seminar 1 (HUST), Topic A1

## 1. Topic

| Code | Topic | Evaluation requirement |
|---|---|---|
| **A1** | Use AI to detect **ambiguity, incompleteness, and inconsistency** in requirements specification documents (SRS) | Compare the tool's results with an expert's assessment on a public set of specification documents; measure the **correct detection rate** and **miss rate** |

This is an empirical study: **tool + public dataset + expert ground truth + comparison + metrics**.

### Research questions
- **RQ1:** How accurately do AI agent tools detect SRS defects compared with an expert (precision, recall, miss rate, F1)?
- **RQ2:** Does giving the agent a **skill** (taxonomy + checklist + output schema) improve detection compared with a plain prompt?
- **RQ3:** Which defect types (ambiguity / incompleteness / inconsistency) are hardest for AI tools?
- **RQ4:** How stable are the results across repeated runs?

## 2. Key Design Decisions

- **AI tool = several kinds**, compared against each other:

  | Kind | Example | Role in our study |
  |---|---|---|
  | Rule-based NLP "smell" detector | Smella-style vague words, passive voice, TBD | **Baseline (T0)**, Python script |
  | Plain LLM prompt | "Find defects in this SRS" | **T1 / T3**, measures what the skill adds |
  | **LLM agent + skill** | Agent loads `SKILL.md` (taxonomy, checklist, JSON output) | **Main tools (T2 / T4)** |
  | Fine-tuned classifier (BERT, …) | Needs labeled training data | Related work only |
  | Commercial tools (QVscribe, IBM RQA) | Paid licenses | Related work only |

- **Expert = Claude Opus** (`claude` Opus main session + fresh Opus subagent) replaces the human expert.
- **Tools = non-Claude models only.** `agy` can also run Claude models, so non-Claude Gemini models (`gemini-4-hydrogen-high`, `gemini-4-neon-high`) are selected explicitly (§5). This keeps the expert and the tools on different model families and avoids self-preference bias.
- **Metrics are computed by a script**, never by hand.
- **Each phase or tool run is done by a separate agent** (§7).
- **Language:** the report and slides are written in Vietnamese. Code, data, and this plan are in English.
- **Team details** are kept in one file (`meta.tex`) shared by the report and slides: Nhóm 4 — Nguyễn Tùng Dương (20251175M, nhóm trưởng), Trần Xuân Nam (20251177M), Phạm Gia Khánh (20252636M); lecturer TS. Nguyễn Thanh Hùng (Khoa Khoa học Máy tính, SoICT).
- **HUST logo** is fetched from public HUST sources (hust.edu.vn or Wikimedia Commons) into `slide/` and `report/figures/`.
- **Git commit hygiene:** never include any `Co-Authored-By:` or co-author trailer lines in commit messages.

## 3. Folder Layout (`REPORT/`, restructured 2026-11-19)

```
REPORT/
├── README.md  PLAN.md  .gitattributes  .gitignore
├── dataset/                 # inputs + answer key
│   ├── raw/pure_xml/        # PURE XML (Zenodo)
│   ├── keepass.json  peering.json  gammaj.json  seeded_lms.json
│   └── dataset/ground_truth/        # expert_pass1/2, final_gt, seed_key, annotation_guideline, adjudication_log, HASHES.txt
├── prompt/                  # plain.txt, skill.txt, SKILL.md (runner copies SKILL.md to skill/req-defect-detector/ in each scratch dir)
├── script/                  # paths.py (all paths) + every .py/.sh
├── result/                  # run/<tool>/<doc>/run_k.{json,log,meta.json} + run_status.csv, metrics.csv, *.json, tables/
├── report/                  # main.tex, main.pdf, meta.tex (shared with slides), figures/ (charts + logo)
└── slide/                   # slides.tex, slides-notes.tex, beamerthemeHUST.sty, logos, PDFs
```

## 4. Phases

### Phase 1 — Dataset
**Source:** the PURE dataset (Ferrari, Spagnolo & Gnesi, RE 2017), Zenodo record 1414117, file `requirements-xml.zip` (379 KB, 18 documents).

**Selection rule:** use only documents whose requirements are explicitly tagged with `<req>`, so requirement boundaries are objective and not chosen by us.

| Doc ID | PURE file | Domain | #Reqs | Notes |
|---|---|---|---|---|
| `keepass` (KP-xxx) | 2008 - keepass.xml | Password manager | 32 | Informal style, grammar issues |
| `peering` (PE-xxx) | 2008 - peering.xml | CDN peering | 24 | Vague "is defined" statements, several duplicate requirements |
| `gammaj` (GJ-xxx) | 0000 - gamma j.xml | Web store | 51 | Many "easy to use" requirements, explicit performance values |
| **Total PURE** | | | **107** | |

Not used: cctns (120) and ertms (199) are too large for careful expert labeling. eirene_fun (583) is out of scope.

**Seeded document `seeded_lms` (SD-xxx):** a Library Management System SRS with 40 requirements.
1. Write 40 clean, precise requirements: explicit actor, values, units, and error handling.
2. `seed_defects.py` replaces 30 of them with defective versions (10 per type) and writes `seed_key.json` with `req_id, type, subtype, related_ids, original_text`. Each of the 10 seeded `inconsistency` requirements contradicts one of the 10 remaining clean requirements (giving 10 clean + 30 defective = 40 requirements and exactly 30 canonical ground-truth findings), anchored on the mutated `req_id` with the contradicted clean `req_id` in `related_ids`.

Planned injections:

| Type | Subtypes injected (count) | Examples |
|---|---|---|
| Ambiguity (10) | vague term (6), referential/pronoun (1), and/or (1), weak phrase "where possible / if appropriate" (2) | "return results *quickly* when *many* users…", "notify *him*" |
| Incompleteness (10) | TBD / undefined value (4), missing actor (1), missing error handling (1), missing consequence or timeout (3), missing quantity (1) | "renew at most *TBD* times", "lock the account after 5 failed attempts" (no duration) |
| Inconsistency (10) | conflicting values (5), conflicting rules (4), terminology ("patron" vs "member") (1) | max 5 loans vs "may borrow up to 8 items"; bcrypt hashing vs "AES so librarians can retrieve passwords" |

**Status:** PURE part done: downloaded, `script/prepare_data.py` run → 107 requirements, Gamma J title fixed. It uses regex parsing because Python's `pyexpat` is broken on this machine. **Remaining (step 2):** write `seed_defects.py`.

### Phase 2 — Defect Taxonomy (shared by expert and tools)
Based on IEEE 830 / ISO/IEC/IEEE 29148 quality attributes and Berry et al.'s *Ambiguity Handbook*.

| Type | Subtypes |
|---|---|
| **Ambiguity** | `vague_term` (fast, easy, user-friendly, sufficient…), `referential` (unclear pronoun), `syntactic` (two possible readings), `coordination` (and/or), `weak_phrase` (if possible, as appropriate) |
| **Incompleteness** | `tbd` (TBD / undefined value), `missing_actor`, `missing_condition`, `missing_error_handling`, `missing_value_or_unit`, `missing_consequence` |
| **Inconsistency** | `conflicting_values`, `conflicting_rules`, `terminology`, `duplicate` (redundant requirement, counted under inconsistency) |

**Unit of labeling & canonicalization:** one finding = (`req_id`, `type`). A requirement may have several findings of different types, but **at most one finding per `(req_id, type)`** (combine multiple triggers of the same type within one requirement). Pairwise `inconsistency` / `duplicate` findings are **anchored on the later `req_id` in document order**, listing earlier conflicting `req_id`(s) in `related_ids`. Prompts and `SKILL.md` also instruct tools to report the JSON `req_id` (e.g., `KP-017`), never inner text prefixes (e.g., `REQ-18`).

**Shared JSON schema (expert + tools):**
```json
{"doc_id": "keepass",
 "findings": [{"req_id": "KP-019", "type": "ambiguity", "subtype": "vague_term",
               "evidence": "more than a line", "related_ids": [], "rationale": "..."}]}
```

### Phase 3 — Expert Ground Truth (Claude Opus Only)
> **Model pinning:** Expert Pass 1, Expert Pass 2, and Adjudication must run on **Claude Opus** (never on Gemini/Hydrogen/Neon) to keep the expert strictly separate from the evaluated tools.
1. **Pass 1:** a Claude session/agent labels all 107 PURE requirements against the taxonomy → `expert_pass1.json`.
2. **Pass 2:** an independent fresh Claude subagent/session with no access to pass 1, the seed key, or any tool output labels all 4 documents (147 requirements) → `expert_pass2.json`.
3. Compute **Cohen's κ** on PURE (pass 1 vs pass 2) over all `107 × 3 = 321` `(req_id, type)` binary pairs (plus per-type κ) with a script; this is expert self-consistency.
4. **Seeded-document validation:** pass-2 recall against `seed_key.json`. Pass 2 is used here, not pass 1, because whoever wrote `seed_defects.py` already knows the answers.
5. **Adjudication:** a Claude session resolves disagreements between pass 1 and pass 2 and records each decision in `adjudication_log.md` → `final_gt.json`. For the seeded document, `final_gt` = `seed_key`.
6. **Freeze:** write SHA-256 hashes and a timestamp of all ground-truth files to `HASHES.txt` **before Phase 4 starts**. `evaluate.py` checks the hashes and refuses to run if any file has changed.

### Phase 4 — Tool Runs
Smoke test (done): `agy --sandbox` runs headless cleanly on both `gemini-4-hydrogen-high` and `gemini-4-neon-high` (`cursor-agent` / `composer-2.5` dropped).

| ID | Tool | Model (non-Claude) | Setting | Command sketch |
|---|---|---|---|---|
| T0 | `baseline_rules.py` | — | Word lists + regex (vague words, TBD, passive voice without an actor, duplicates by text similarity) | `python3 script/baseline_rules.py` |
| T1 | agy | `gemini-4-hydrogen-high` | Plain prompt | `agy --sandbox --disable-slash-commands --model gemini-4-hydrogen-high --output-format json -p "<plain + doc>"` |
| T2 | agy | `gemini-4-hydrogen-high` | + skill | `agy --sandbox --model gemini-4-hydrogen-high --output-format json -p "<skill + doc>"` |
| T3 | agy | `gemini-4-neon-high` | Plain prompt | `agy --sandbox --disable-slash-commands --model gemini-4-neon-high --output-format json -p "<plain + doc>"` |
| T4 | agy | `gemini-4-neon-high` | + skill | `agy --sandbox --model gemini-4-neon-high --output-format json -p "<skill + doc>"` |

- 4 LLM configurations × 4 documents × **3 repeats** = **48 LLM runs**, plus T0.
- Tools run in separate isolated scratch workspaces (`plain` without any skill files and `--disable-slash-commands`; `skill` with `prompt/SKILL.md`), never `dataset/ground_truth/`, using `--sandbox` so `agy` executes cleanly and returns JSON instead of entering planning mode.
- Plain and skill prompts share the same task sentence and output schema. The only difference is the taxonomy and checklist in the skill.
- `run_tools.sh` saves raw CLI output (`.log`), unwraps `--output-format json` CLI envelopes and validates the findings schema (`script/parse_tool_output.py`), and uses per-run timeouts (`--print-timeout 180s`). Invalid JSON or schema errors get one retry; a second failure is logged as a failed run, never silently dropped.

### Phase 5 — Metrics Script (`script/evaluate.py`)
- **Pre-matching normalization:** collapse duplicate `(req_id, type)` predictions and deduplicate symmetric inconsistency predictions (where two predicted inconsistency findings cross-reference each other via `related_ids`) so tools are not penalized for reporting both ends of a conflict pair.
- **Matching**
  - **strict:** same `req_id` + same `type`. An inconsistency finding also matches if it is on any of the ground truth's `related_ids`.
  - **lenient:** binary requirement-level match (`N = 147`: requirement flagged with any defect vs. clean).
  - Each ground-truth item can be matched at most once.
- **Metrics** per tool, per defect type, and per document subset (**PURE 107**, **Seeded 40**, **All 147**), averaged over the 3 repeats with standard deviation:
  - Precision = TP / (TP + FP)
  - **Recall (correct detection rate)** = TP / (TP + FN)
  - **Miss rate** = FN / (TP + FN) = 1 − Recall
  - F1
- **Uncertainty:** bootstrap 95% CI over requirements (1000 resamples).
- **Stability:** Jaccard overlap of findings between repeats, and Fleiss' κ across the 3 runs over `(req_id, type)` binary pairs (`147 × 3 = 441` overall; `107 × 3 = 321` PURE).
- **Skill effect:** ΔF1 for T2 − T1 and T4 − T3, with a paired bootstrap.
- **Outputs:** `results/metrics.csv`, LaTeX tables in `results/tables/`, and charts in `report/figures/`:
  - P/R/F1 bar chart per tool
  - Recall heatmap, tool × defect type
  - Skill-effect chart
  - Stability chart
  - Miss-rate chart per type

### Phase 6 — Error Analysis
- Sample about 30 false positives and 30 misses across tools.
- The main session categorizes them, for example:
  - expert too strict / judgment call
  - needs domain knowledge
  - spans several requirements
  - tool mislabeled the type
  - tool hallucinated or used the wrong requirement ID
- Output: `results/error_analysis.md` plus 4–6 concrete examples for the report and slides.

### Phase 7 — Report (`main.tex` → `main.pdf`)
- Keep the template's colors and `tcolorbox` environments (`notebox`, `examplebox`, `definitionbox`), while replacing all content, headers, and `hypersetup` metadata. Compile with **xelatex** (`latexmk -xelatex`), using `\usepackage[english,vietnamese]{babel}` (so Vietnamese is the active main language for `\chaptername`/`\tablename`/`\contentsname`) and `fontspec`/removed `inputenc` & `T5 fontenc`.
- Title page fields come from `meta.tex`: HUST logo (`report/figures/hust_logo.png`), Đại học Bách khoa Hà Nội, Trường CNTT&TT, Seminar 1, topic A1, lecturer, group, members.
- Chapters:
  1. **Giới thiệu:** motivation (cost of requirement defects), problem A1, RQ1–RQ4, contributions
  2. **Cơ sở lý thuyết:** SRS quality (IEEE 830 / ISO 29148), the three defect types, NLP4RE tools (Smella, QuARS), LLMs, agents and skills
  3. **Phương pháp:** taxonomy, tools T0–T4, skill design, expert protocol (AI expert, κ, freeze/hash), matching, metrics
  4. **Thiết lập thực nghiệm:** dataset table, seeded design, models, environment, number of runs
  5. **Kết quả:** answers to RQ1–RQ4 with tables and charts
  6. **Thảo luận:** error analysis, threats to validity (AI expert replacing a human, small dataset, seeded-defect realism, model version drift, possible PURE data contamination in LLM training)
  7. **Kết luận và hướng phát triển**
  8. **Tài liệu tham khảo** (real sources, each checked before citing):
     - ISO/IEC/IEEE 29148:2018; IEEE Std 830-1998
     - Berry, Kamsties & Krieger (2003), *From Contract Drafting to Software Specification: Linguistic Sources of Ambiguity* (Ambiguity Handbook)
     - Ferrari, Spagnolo & Gnesi (2017), PURE dataset, RE'17
     - Femmer et al. (2017), "Rapid quality assurance with Requirements Smells", JSS
     - Lami et al., QuARS
     - Zhao et al. (2021), "Natural Language Processing for Requirements Engineering: A Systematic Mapping Study", ACM CSUR
     - Recent work on LLMs for requirements quality
- Appendix: the full `SKILL.md`, prompts, and an example output JSON.

### Phase 8 — Presentation Slides (LaTeX Beamer, HUST style)
- **Generated with LaTeX (Beamer)** and compiled with xelatex. Custom theme `slide/beamerthemeHUST.sty`:
  - HUST red (RGB 204,21,39, sampled from the official logo) with a white/grey background
  - logo on the title slide and in the top-right corner of each slide
  - footer with the group name, topic A1, and slide number
- Shares `meta.tex` and the `report/figures/` charts with the report, so the report and slides always show the same numbers.
- Speaker notes use Beamer `\note{}`. A separate `slides-notes.pdf` is built via a thin `slide/slides-notes.tex` wrapper setting `\setbeameroption{show notes}`. Notes are written in Vietnamese and split across the 3 presenters (Dương, Nam, Khánh).
- Outline (~18 slides, ~15 minutes):
  1. Title
  2. Agenda
  3. Why it matters (cost of late requirement defects)
  4. Problem A1 + RQ1–RQ4
  5. Taxonomy with one real PURE example per type
  6. Method overview diagram (TikZ: dataset → expert → freeze → tools → metrics script)
  7. Dataset (PURE table + seeded design)
  8. AI tools T0–T4 (agent + skill concept)
  9. Expert ground-truth protocol (2 passes, κ, adjudication, hash freeze)
  10. Metrics (Precision, Recall, Miss rate, F1)
  11. Results table
  12. P/R/F1 chart
  13. Recall per defect type (heatmap)
  14. Skill effect
  15. Stability + seeded validation
  16. Error analysis examples
  17. Limitations
  18. Conclusion & future work + Q&A
- Live-demo backup slide: one requirement in, skill JSON out (shown as a static screenshot in case the live demo fails).
- Output: `slide/slides.pdf` + `slide/slides-notes.pdf`.

## 5. Tool Environment (verified 2026-11-17)
| Tool | Path | Headless flag | Non-Claude models available |
|---|---|---|---|
| agy | `~/.local/bin/agy` | `-p/--print`, `--output-format json`, `--sandbox` | gemini-4-hydrogen-{xhigh,high,medium,low}, gemini-4-neon-{xhigh,high,medium,low}, gemini-3.8-flash-{high,medium,low} |
| cursor-agent | `~/.local/bin/cursor-agent` | `-p`, `--output-format json`, `--mode ask` | gpt-5.3-codex(-high/…), gpt-5.2, gpt-5.6-*, grok-4.x, composer-2.5 |
| LaTeX | `/Library/TeX/texbin` | xelatex, latexmk | — |
| Python | `/opt/homebrew/bin/python3` (3.15) + `REPORT/.venv` (uv, Python 3.12.13) | — | System 3.15 has broken `pyexpat`/`ensurepip`. Always use `REPORT/.venv/bin/python` (`uv` at `~/.local/bin/uv`; `pillow`, `numpy`, `matplotlib` installed) |

## 6. Execution Order & Checklist
| # | Step | Depends on | Status |
|---|---|---|---|
| 1 | Create folders, download PURE, `prepare_data.py` (Gamma J title fixed) | — | ✅ done |
| 2 | `seed_defects.py` → `seeded_lms.json` + `seed_key.json` | 1 | ✅ done (40 reqs, 30 canonical defects) |
| 3 | Write `SKILL.md`, `prompt/plain.txt`, `prompt/skill.txt` | taxonomy | ✅ done |
| 4 | Expert pass 1 (Claude Opus) | 1 | ✅ done (blind Opus subagent, 55 findings; guideline `dataset/ground_truth/annotation_guideline.md`) |
| 5 | Expert pass 2 (fresh Claude Opus subagent), in parallel with 4 | 2, 3 | ✅ done (78 findings; seeded recall 30/30) |
| 6 | κ + seeded validation + adjudication (`check_gt.py`) → `final_gt.json` | 4, 5 | ✅ done (κ=0.814; 16 disagreements → 9 accepted/7 rejected; final GT 82 findings) |
| 7 | **Freeze:** `HASHES.txt` (`check_gt.py --freeze`) | 6 | ✅ done 2026-11-19T01:59Z; re-frozen 06:23Z after the prompt change (GT + SKILL.md + prompts) |
| 8 | `baseline_rules.py` (T0) + `run_tools.sh` (T1–T4 × 4 docs × 3) | 3, 7 | ⏳ T0 done; smoke run OK; full T1–T4 run in progress (2026-11-19) |
| 9 | `evaluate.py` → metrics, tables, charts | 7, 8 | ✅ done 2026-11-19: `result/metrics.csv`, `result/extra_analysis.json`, tables `overall_pure/overall_all/pure_by_type.tex`, 5 PURE charts in `report/figures/` |
| 10 | Error analysis | 9 | ☐ |
| 11 | Fetch HUST logo; write `meta.tex` | — | ✅ done (`slide/hust_logo.png`, `report/figures/hust_logo.png`, `slide/hust_banner_white.png` from hust.edu.vn) |
| 12 | `main.tex` → `main.pdf` | 9, 10, 11 | ⏳ Ch. 1–4, References & Appendix written + `xelatex` verified; Ch. 5–7 await Phase 3–6 results |
| 13 | `beamerthemeHUST.sty` + `slides.tex` → PDFs | 9, 10, 11 | ⏳ HUST theme + Slides 1–10, 17–18 + notes written & `xelatex` verified; results slides await Phase 3–6 |
| 14 | Write `README.md` in Vietnamese (overview, layout, reproduction steps, status) | 12, 13 | ✅ done (refresh final metrics summary after step 15 if needed) |
| 15 | Final check: numbers in report = slides = `metrics.csv`; references verified; PDFs compile without errors | 12, 13, 14 | ☐ |

### Changes made on 2026-11-19 (review)
- **SKILL.md leak fixed:** its examples had been copied from the seeded defects (5 vs 8 loans, 14 vs 21 days, bcrypt vs AES, Member vs Patron, …). They were replaced with neutral examples from other domains. Both prompts' schema example (`KP-019` "more than a line", a real PURE item) became `XX-001` "user-friendly".
- **T0 leak fixed:** dropped `"more than a line"`, the seeded `"allowed maximum"` phrase and the peering-specific passive-verb list. The rules are now generic.
- **Expert passes:** both ran as blind Opus subagents with their own `annotation_guideline.md`, separate from SKILL.md. Pass 1 was not run in the main session, because that session had already seen the skill and seed key.
- **Freeze also hashes** `prompt/SKILL.md` and `prompt/*.txt`.
- **`run_tools.sh` fixes:** it moves `dataset/ground_truth/` out of the repo during runs, greps the logs for GT file names afterwards, and the macOS `seq 1 0` loop bug is fixed.
- **agy behaviour** (agy 1.5.12, verified 2026-11-19; notes kept in Claude memory `agy-cli-facts`): `--sandbox` does not block `read_file`, and web search cannot be disabled, so the runner now uses:
  - `--settings` with `toolPermission: request-review`; T2/T4 are only allowed `read_file(<scratch>/**)`;
  - `stream-json` output, so `parse_tool_output.py` can audit tool calls (no web, browser or command tools, no reads outside scratch; T2/T4 must read SKILL.md);
  - a 300 s timeout and a per-run `run_k.meta.json` (duration, tokens, tool calls);
  - one identical no-web rule in both prompts.

  Re-frozen 2026-11-19T06:23Z, before any kept tool run.
- **Step 4 run check (2026-11-19):** 48/48 OK; audit clean (no web/browser/command tools, no outside reads, SKILL.md read in 12/12 T2/T4 runs, 0/24 tool calls in T1/T3, no GT strings in logs); no duplicate (req_id, type) pairs, no mis-anchored inconsistencies. Cost: 119.6 agy-minutes, 1.81M tokens; per-run table in `result/run/run_summary.csv`.
- **Leak #3 found in Step 4:** `dataset/seeded_lms.json` `source` said "10 clean, 30 defective"; every T1–T4 run (and expert pass 2) returned exactly 30 seeded findings. PURE results unaffected. **Fixed in Step 4b:** `source` became "Synthetic Library Management System SRS (40 requirements)" (seed_defects.py too); 12 leaked runs moved to `result/run_leaked/`; seeded runs re-run (12/12 OK, audit clean). A fresh blind Opus expert on the clean doc found 30/30 seeds with 0 extras (`result/expert_seeded_check.json`). Clean-doc tool recall is 28–30/30 (leaked: 30/30), so the seeded doc sits at the ceiling and PURE is the discriminating measure. `script/audit_runs.py` reproduces `run_summary.csv`.
- **Folder restructure (2026-11-19, after the 48 runs):** lean layout of §3; all paths live in `script/paths.py`; HASHES.txt path entries rewritten (digests and freeze time unchanged).

### Step 5 headline results (PURE, 107 reqs, strict, mean of 3 runs)
| Tool | P | R | F1 | F1 95% CI |
|---|---|---|---|---|
| T0 rules | 0.400 | 0.423 | 0.411 | [0.297, 0.519] |
| T1 Hydrogen | 0.252 | 1.000 | 0.403 | [0.332, 0.470] |
| T2 Hydrogen + skill | 0.366 | 0.949 | 0.528 | [0.450, 0.601] |
| T3 Neon | 0.283 | 0.994 | 0.439 | [0.364, 0.509] |
| T4 Neon + skill | 0.397 | 0.929 | 0.556 | [0.470, 0.632] |
| flag everything | 0.162 | 1.000 | 0.279 | — |

- Skill effect (PURE, paired bootstrap): T2−T1 ΔF1 +0.125 [0.088, 0.163]; T4−T3 +0.116 [0.078, 0.154]. It comes from precision (+0.11) at a small recall cost (−0.05/−0.06).
- By type (PURE F1): inconsistency is easiest (0.69–0.89); incompleteness is hardest (0.37–0.46 for LLMs, 0.23 for T0); T0 is competitive on ambiguity (0.67).
- Stability (PURE): Jaccard 0.82–0.93, Fleiss κ 0.77–0.89.
- Seeded doc at the ceiling (F1 0.96–1.00); SD-023 sensitivity changes F1 by ≤ 0.02; the count leak inflated seeded F1 by ≤ 0.04.
- The SD over repeats is the sample SD (ddof=1). Charts are PURE-scoped with Vietnamese labels and a validated palette; the recall heatmap was replaced by an F1 heatmap, since LLM recall is at the ceiling.

## 7. Agent Assignment
| Work | Agent |
|---|---|
| Orchestration, scripts, T0, report/slides scaffolding, evaluation & charts | Claude Opus main session (scaffolds already prepared) |
| Expert pass 1, Expert pass 2 (isolated), Adjudication | **Claude Opus only** (`claude` CLI / Claude Opus subagent — isolated passes) |
| T1 / T2 detection | agy (`gemini-4-hydrogen-high`) — separate process per run |
| T3 / T4 detection | agy (`gemini-4-neon-high`) — separate process per run |
| Error analysis, Report writing (`main.tex`), Slides (`slides.tex`) | Claude Opus session / subagent (given frozen GT, `metrics.csv`, error analysis) |
| Final consistency review | Automated check + reviewer verification of numbers and citations |

## 8. Risks & Mitigations
| Risk | Mitigation |
|---|---|
| AI expert ≠ human expert | 2 independent passes + κ; validation on the seeded document; stated as a threat to validity |
| Expert bias toward Claude-like answers | Tools use non-Claude models only |
| Main session knows the seed key | Seeded validation uses pass 2; seeded GT = exact key |
| Ground truth changed after seeing tools | SHA-256 freeze before tool runs; `evaluate.py` checks the hashes |
| LLM non-determinism | 3 repeats, mean ± SD, stability metrics |
| Invalid JSON / CLI failures | 1 retry, failures logged and reported |
| PURE documents seen during LLM training | Seeded document is new; contamination discussed in threats to validity |
| Small dataset (147 reqs) | Bootstrap CIs; documented as a limitation |
| Fabricated references | Only cite sources that have been checked |

## 9. Team Information (in `meta.tex`)
| Role | Name | Student ID |
|---|---|---|
| Lecturer | TS. Nguyễn Thanh Hùng — Khoa Khoa học Máy tính, SoICT | — |
| Group | Nhóm 4 | — |
| Leader | Nguyễn Tùng Dương | 20251175M |
| Member | Trần Xuân Nam | 20251177M |
| Member | Phạm Gia Khánh | 20252636M |

HUST logo: fetched from hust.edu.vn (`/uploads/sys/logobk-mb.png`); emblem cropped to `slide/hust_logo.png` + `report/figures/hust_logo.png` (392×577); full white-text banner kept as `slide/hust_banner_white.png` for dark backgrounds.

## 10. Deliverables
- `REPORT/README.md`: Vietnamese project guide and reproduction documentation
- `REPORT/main.pdf`: the full report (Vietnamese)
- `REPORT/slide/slides.pdf` + `slides-notes.pdf`: LaTeX Beamer presentation with HUST theme and speaker notes
- Reproducible artifacts: data, skill, prompts, frozen ground truth, raw runs, evaluation scripts, and charts
