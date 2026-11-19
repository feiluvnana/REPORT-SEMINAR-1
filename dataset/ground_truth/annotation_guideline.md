# Expert Annotation Guideline — SRS Defect Labeling (Topic A1)

You are acting as an expert requirements-engineering reviewer (IEEE 830 / ISO/IEC/IEEE 29148 quality attributes; Berry, Kamsties & Krieger *Ambiguity Handbook*). Label every requirement in each document.

## Judgment standard
Flag a defect only when a careful reviewer would **ask the author to revise the requirement** because a developer or tester could misread it, could not verify it, or would get conflicting instructions. Do **not** flag:
- pure grammar/spelling/style problems that do not change meaning;
- a term that is vague in isolation but made precise by the same requirement (a number, unit, standard, or explicit list);
- design choices you merely disagree with.

Read the whole document first. Judge each requirement in the context of the document (a term defined elsewhere in the document is not vague).

## Taxonomy (use these exact `type` / `subtype` values)

| type | subtype | Meaning |
|---|---|---|
| ambiguity | `vague_term` | Subjective or unquantified qualifier with no testable threshold ("fast", "easy to use", "large number of") |
| ambiguity | `referential` | Pronoun/demonstrative with more than one plausible antecedent |
| ambiguity | `syntactic` | Sentence structure admits two grammatical readings (attachment, scope of "only"/"all…not") |
| ambiguity | `coordination` | "and/or", or mixed and/or with unclear precedence |
| ambiguity | `weak_phrase` | Loophole qualifier making the obligation optional ("if possible", "as appropriate", "etc.") |
| incompleteness | `tbd` | Explicit placeholder (TBD, TBC, ???, "to be defined") |
| incompleteness | `missing_actor` | Operational action whose performer (user role or system component) cannot be determined |
| incompleteness | `missing_condition` | Missing trigger, precondition, or scope where several are plausible |
| incompleteness | `missing_error_handling` | Validation/lookup/external call with no stated behaviour on failure or invalid input, where failure is clearly possible and relevant |
| incompleteness | `missing_value_or_unit` | Refers to a limit/threshold/quantity but gives no number, or gives a number without unit |
| incompleteness | `missing_consequence` | States a trigger/condition but not the resulting system behaviour, duration, or recovery |
| inconsistency | `conflicting_values` | Two requirements give incompatible values for the same quantity |
| inconsistency | `conflicting_rules` | Two requirements state incompatible policies/behaviours |
| inconsistency | `terminology` | A different name is used for an entity/role already named differently earlier |
| inconsistency | `duplicate` | Identical or near-identical restatement of an earlier requirement with no distinct scope |

Neutral illustrations (not from the documents you label): "The kiosk shall respond quickly" → ambiguity/vague_term. "Invoices are archived monthly" → incompleteness/missing_actor (who archives?). "The pump shall stop after 3 sensor faults" → incompleteness/missing_consequence (then what? alarm? restart?). Req 4 "max 2 bags" vs Req 9 "up to 3 bags" → inconsistency/conflicting_values on Req 9 with related_ids [Req 4].

## Canonicalization rules (mandatory)
1. One finding = (`req_id`, `type`). **At most one finding per (`req_id`, `type`)**; if several triggers of the same type occur, pick the primary subtype and mention all triggers in `evidence`/`rationale`.
2. A requirement may carry findings of different types.
3. `inconsistency` (incl. `duplicate`) is anchored on the **later** `req_id` in document order; list the earlier req_id(s) in `related_ids`. Other types use `related_ids: []`.
4. Use the outer JSON `req_id` (e.g. `KP-017`), never labels inside the text (e.g. "REQ-18").
5. Clean requirements get no finding. Do not pad.

## Output
One JSON file:
```json
{"annotator": "<pass name>",
 "docs": {
   "<doc_id>": {"findings": [
     {"req_id": "KP-019", "type": "ambiguity", "subtype": "vague_term",
      "evidence": "<verbatim span>", "related_ids": [], "rationale": "<one sentence>"}
   ]}
 }}
```
Include every assigned doc_id key, even if its findings list is empty.
