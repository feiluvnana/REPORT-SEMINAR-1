# Adjudication log

Date: 2026-11-19 · Adjudicator: Claude Opus (main session; had not seen any T1–T4 output — none existed yet).

Inputs: `expert_pass1.json` (PURE, blind Opus subagent), `expert_pass2.json` (all 4 docs, blind Opus subagent), `annotation_guideline.md`.

Rule: findings on which both passes agree at (req_id, type) level are kept as-is (pass-1 wording). Each disagreement is decided below, preferring the decision consistent with how both passes treated the same pattern elsewhere.

Pre-adjudication agreement on PURE (321 binary pairs): Cohen's κ = 0.814 (ambiguity 0.772, incompleteness 0.789, inconsistency 0.936); 16 disagreements.

| Doc | Req | Type | Decision | Source | Reason |
|---|---|---|---|---|---|
| keepass | KP-004 | incompleteness | **REJECT** | — | The consequence (previous database replaced) is stated in the requirement itself; scope wording is clumsy but not a missing element. |
| keepass | KP-019 | incompleteness | **ACCEPT** | P1 | User-input length limit with no failure behaviour; consistent with KP-007/009/013 which both passes flagged as missing_error_handling. |
| keepass | KP-021 | incompleteness | **ACCEPT** | P1 | Command-line validation rule with no stated behaviour on violation; same pattern as KP-007/009/013. |
| keepass | KP-022 | ambiguity | **REJECT** | — | Only one sensible antecedent for 'it' (the path); quoting a lone space is not a plausible reading. |
| keepass | KP-029 | ambiguity | **REJECT** | — | Informational statement about file formats, not an obligation a tester would verify; flagging would be padding. |
| peering | PE-007 | ambiguity | **ACCEPT** | P1 | 'Malicious' has no criteria anywhere in the document; a reviewer would ask for a definition. |
| peering | PE-015 | ambiguity | **ACCEPT** | adjudicator | Consistency with PE-007 decision; 'acted upon' is instead captured as incompleteness. |
| peering | PE-015 | incompleteness | **ACCEPT** | P2 | 'Acted upon' states the trigger but not the resulting behaviour: missing_consequence fits better than vague_term. |
| peering | PE-015 | inconsistency | **ACCEPT** | P1 | Near-restatement of PE-007 with a weaker verb; a reviewer would merge or reconcile them (duplicate, related PE-007). |
| peering | PE-016 | ambiguity | **REJECT** | — | 'Long-term/short-term peering' are established domain terms; the statement's weakness is lack of content, not a vague qualifier. |
| peering | PE-017 | ambiguity | **REJECT** | — | Same reasoning as PE-016. |
| peering | PE-018 | incompleteness | **REJECT** | — | Same declarative style as the 'X is defined' statements both passes left clean; kept consistent. |
| gammaj | GJ-008 | ambiguity | **REJECT** | — | Users Guide is evidently for users; only one sensible attachment of 'for the Administrator'. |
| gammaj | GJ-016 | incompleteness | **ACCEPT** | P2 | Triggering event for the email and start point of the 1-second timing are not stated; untestable as written. |
| gammaj | GJ-017 | incompleteness | **ACCEPT** | P2 | Card validation is an external check where failure is clearly possible and relevant; no failure behaviour given. |
| gammaj | GJ-038 | ambiguity | **ACCEPT** | P1 | 'Clear notifications' is subjective; consistent with other GammaJ usability qualifiers both passes flagged. |

## Seeded document

`final_gt` for `seeded_lms` = `seed_key.json` exactly (30 findings), as planned. Pass 2 recovered 30/30 seeds (100% recall).
Pass 2 also reported one finding outside the key: **SD-023 incompleteness/missing_value_or_unit** ("before the due date": lead time of the SMS not specified). This looks like a genuine, unintended defect in a 'clean' requirement. It is NOT added to the GT (to keep the seeded GT exact), but tools flagging it will be counted as FP; `evaluate`/error analysis should report this case separately.

## Result

- keepass: 11 findings
- peering: 15 findings
- gammaj: 26 findings
- seeded_lms: 30 findings
- total: 82
