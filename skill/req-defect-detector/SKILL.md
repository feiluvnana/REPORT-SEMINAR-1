---
name: req-defect-detector
description: Systematic detection of ambiguity, incompleteness, and inconsistency defects in Software Requirements Specifications (SRS) grounded in IEEE 830 / ISO/IEC/IEEE 29148 and Berry et al.'s Ambiguity Handbook.
---

# SRS Requirements Defect Detector

Analyze every requirement in the provided SRS JSON document (`requirements`: list of `{"req_id", "text"}`) and output a single JSON object of defect findings.

## 1. Defect Taxonomy & Detection Checklist

### A. `ambiguity` — Requirement allows multiple interpretations or lacks measurable criteria
Check each requirement for:
1. **`vague_term`**: Subjective, unquantified adjectives/adverbs or open-ended quantities with no testable threshold.
   - Watch for: *fast, quickly, rapid(ly), slow(ly), easy, user-friendly, intuitive, simple, clear, sufficient, adequate, appropriate, reasonable, acceptable, timely, many, several, large, small, normal, standard, effective, efficient, flexible, minimal, robust, reliable, seamless, noticeable, more than a line* (without unit).
   - **Guardrail:** Do **not** flag terms that are immediately paired with an explicit quantitative metric/standard in the same requirement (e.g., *"within 800 milliseconds under 500 concurrent queries"*, *"WCAG 2.1 Level AA contrast (minimum 4.5:1)"*).
2. **`referential`**: Unclear pronoun or demonstrative reference (*he, him, his, she, her, it, its, they, them, their, this, that, these, those*) where two or more plausible antecedents exist.
3. **`syntactic`**: Sentence structure permits two grammatically valid readings (e.g., dangling modifier, unclear scope of *"only"*, *"all ... not"*, or attachment of prepositional/conditional clauses).
4. **`coordination`**: Ambiguous logical connectives such as **`and/or`**, or stacked **`and`/`or`** clauses where operator precedence is unclear.
5. **`weak_phrase`**: Non-binding or loophole qualifiers that make verification optional or subjective.
   - Watch for: *where possible, if possible, as appropriate, if appropriate, as needed, if necessary, if applicable, to the extent practical, may (when mandatory behavior is unclear), etc., and so on*.

### B. `incompleteness` — Essential operational, actor, boundary, or failure information is missing
Check each requirement for:
1. **`tbd`**: Explicit placeholders or deferred specifications (*TBD, TBA, TBC, TODO, ???, to be determined, to be defined*).
2. **`missing_actor`**: Passive voice or nominalization (*"shall be reviewed"*, *"is defined"*, *"must be printed"*) where **who/which system component** performs or initiates the action cannot be determined from the sentence.
   - **Guardrail:** Do not flag passive voice if the responsible actor/system is explicitly named elsewhere in the same sentence (e.g., *"shall be blocked by the Circulation System"*) or if the requirement purely defines an invariant/constraint on data format where no runtime actor is needed—unless an operational action is left unowned.
3. **`missing_condition`**: States an action without specifying the triggering event, precondition, or scope boundary when multiple modes/states are implied.
4. **`missing_error_handling`**: Describes a validation, lookup, external dependency, authentication check, or state-changing operation on the happy path without specifying what happens on invalid input, failure, or denial.
5. **`missing_value_or_unit`**: References a numeric limit, capacity, threshold, retention, or measurement without giving the actual number or unit (e.g., *"up to the allowed maximum limit"* with no number; *"within 10"* with no unit).
6. **`missing_consequence`**: Specifies a trigger, fault, or detection condition (e.g., *"after 5 failed attempts"*, *"shall detect active references"*) without specifying the resulting system behavior, timeout duration, or recovery action.

### C. `inconsistency` — Contradiction, terminology drift, or duplication across requirements
Compare every requirement against **all earlier requirements** in the document:
1. **`conflicting_values`**: Two requirements specify incompatible numeric limits, durations, rates, capacities, currencies, or versions for the same entity/operation (e.g., max 5 loans vs. up to 8 items; 14 days vs. 21 days; 15 min vs. 60 min).
2. **`conflicting_rules`**: Two requirements state mutually incompatible policies, permissions, security mechanisms, or state transitions (e.g., one-way bcrypt hashing vs. reversible AES decryption; ID check required vs. unverified self-checkout; auto-cancel after 72h vs. hold indefinitely).
3. **`terminology`**: Uses a different term/label for an already-established domain entity or role defined in earlier requirements (e.g., switching from *"Member"* to *"Patron"* or *"Subscriber"* for the same borrower role).
4. **`duplicate`**: Repeats an identical or near-identical requirement already stated earlier in the document with no distinct scope.

## 2. Step-by-Step Analysis Procedure
1. **Read the entire `requirements` array once** to build a mental map of domain roles, actors, numeric parameters, and policy rules.
2. **Pass 1 (Per-requirement scan):** Evaluate each `req_id` against the Ambiguity and Incompleteness checklists. Ignore embedded legacy labels inside `text` (e.g., `"REQ-18: ..."`) and garbled leading characters—always record the outer JSON `req_id` (e.g., `"KP-017"`).
3. **Pass 2 (Cross-requirement scan):** Compare each requirement `R_j` against earlier requirements `R_i` (`i < j`) for `conflicting_values`, `conflicting_rules`, `terminology`, and `duplicate`.
4. **Canonicalize & Deduplicate:**
   - Emit **at most one finding per `(req_id, type)`**. If a requirement triggers multiple subtypes of the same `type` (e.g., two `vague_term`s, or both `vague_term` and `weak_phrase`), pick the primary/most severe `subtype` and combine all quoted triggers in `evidence` and `rationale`.
   - A single requirement **may** have multiple findings of **different** `type`s (e.g., both `ambiguity` and `incompleteness`).
   - For every `inconsistency` (including `duplicate`), anchor the finding on the **later `req_id`** in document order and list all earlier conflicting/duplicated `req_id`(s) in `related_ids`.
   - Do **not** flag clean, well-quantified requirements just to increase count.

## 3. Output Format
Return **only** a valid JSON object (no surrounding prose) matching:
```json
{
  "doc_id": "<doc_id from input>",
  "findings": [
    {
      "req_id": "<exact JSON req_id, e.g. KP-019>",
      "type": "ambiguity | incompleteness | inconsistency",
      "subtype": "<exact subtype name from taxonomy>",
      "evidence": "<verbatim quoted span(s) from requirement text>",
      "related_ids": ["<earlier req_id(s) for inconsistency, else []>"],
      "rationale": "<concise explanation>"
    }
  ]
}
```
