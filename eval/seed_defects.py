"""Build the seeded Library Management System (LMS) SRS and its exact answer key.

Generates:
  - REPORT/data/seeded_lms.json       (40 requirements, no defect labels)
  - REPORT/ground_truth/seed_key.json (30 canonical ground-truth findings: 10 per type)

Each of the 10 seeded inconsistency findings is anchored on a later req_id and
contradicts an earlier clean requirement listed in `related_ids`.
"""
import json
from pathlib import Path
import sys

# Windows consoles default to a legacy code page; force UTF-8 so non-ASCII text prints safely.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[1]

# 40 requirements arranged across realistic LMS SRS modules.
# Clean items appear early enough so every inconsistency seed pairs with an earlier clean item.
ITEMS = [
    # --- Module 1: Account & Authentication ---
    {
        "req_id": "SD-001",
        "clean_text": (
            "A Librarian shall create a new Member account only after verifying the applicant's "
            "government-issued photo ID and recording full name, email address, and phone number; "
            "if verification fails, the Circulation System shall reject account creation and log reason code ERR-ID-01."
        ),
        "defect": None,
    },
    {
        "req_id": "SD-002",
        "clean_text": (
            "The Authentication Service shall enforce Member passwords of at least 12 characters containing "
            "uppercase, lowercase, and numeric characters; passwords failing validation shall be rejected with HTTP 400."
        ),
        "defect": None,
    },
    {
        "req_id": "SD-003",
        "clean_text": (
            "The Authentication Service shall hash all Member and Librarian passwords using bcrypt with a "
            "cost factor of 12 before database storage, and shall never store or log plaintext passwords."
        ),
        "defect": None,
    },
    {
        "req_id": "SD-004",
        "clean_text": (
            "The Authentication Service shall terminate an authenticated web portal session after 15 minutes "
            "of user inactivity and redirect the user to the login page with status message SESSION_EXPIRED."
        ),
        "defect": None,
    },
    {
        "req_id": "SD-005",
        "clean_text": (
            "The Authentication Service shall lock a Member account for 30 minutes after 5 consecutive failed "
            "login attempts within a 10-minute window and display error code ERR-AUTH-LOCK."
        ),
        "defect": {
            "type": "incompleteness",
            "subtype": "missing_consequence",
            "related_ids": [],
            "defective_text": (
                "The Authentication Service shall lock a Member account after 5 consecutive failed login attempts "
                "within a 10-minute window."
            ),
            "evidence": "lock a Member account after 5 consecutive failed login attempts",
            "rationale": "Specifies the lockout trigger but omits the lockout duration and unlock/error behavior.",
        },
    },
    {
        "req_id": "SD-006",
        "clean_text": (
            "When a Librarian links a Member account to a Guarantor profile, the Notification Service shall "
            "send a confirmation email to the Member within 60 seconds and log delivery status."
        ),
        "defect": {
            "type": "ambiguity",
            "subtype": "referential",
            "related_ids": [],
            "defective_text": (
                "When a Librarian links a Member account to a Guarantor profile, the Notification Service shall "
                "notify him by email within 60 seconds and log delivery status."
            ),
            "evidence": "notify him by email",
            "rationale": "Ambiguous pronoun 'him' could refer to the Librarian, the Member, or the Guarantor.",
        },
    },
    {
        "req_id": "SD-007",
        "clean_text": (
            "The Authentication Service shall expire password-reset tokens exactly 15 minutes after issuance "
            "and invalidate any unused token upon a subsequent reset request."
        ),
        "defect": {
            "type": "incompleteness",
            "subtype": "tbd",
            "related_ids": [],
            "defective_text": (
                "The Authentication Service shall expire password-reset tokens TBD minutes after issuance "
                "and invalidate any unused token upon a subsequent reset request."
            ),
            "evidence": "TBD minutes",
            "rationale": "Uses placeholder 'TBD' instead of a concrete expiration duration.",
        },
    },
    {
        "req_id": "SD-008",
        "clean_text": (
            "The Portal Interface shall render the Member dashboard and navigation menu in compliance with "
            "WCAG 2.1 Level AA contrast (minimum 4.5:1) and complete initial page load within 1.5 seconds on 10 Mbps links."
        ),
        "defect": {
            "type": "ambiguity",
            "subtype": "vague_term",
            "related_ids": [],
            "defective_text": (
                "The Portal Interface shall provide a user-friendly Member dashboard that is easy to navigate "
                "and loads rapidly on standard connections."
            ),
            "evidence": "user-friendly ... easy to navigate ... loads rapidly",
            "rationale": "Subjective, unmeasurable usability and performance terms without quantitative criteria.",
        },
    },

    # --- Module 2: Borrowing, Renewals & Holds ---
    {
        "req_id": "SD-009",
        "clean_text": (
            "The Circulation System shall allow an active Member in good standing to have at most 5 physical "
            "items checked out simultaneously; any checkout exceeding 5 items shall be blocked with error ERR-LOAN-LIMIT."
        ),
        "defect": None,
    },
    {
        "req_id": "SD-010",
        "clean_text": (
            "The Circulation System shall assign a standard loan duration of 14 calendar days from the checkout "
            "timestamp for all circulating print books."
        ),
        "defect": None,
    },
    {
        "req_id": "SD-011",
        "clean_text": (
            "The Circulation System shall hold a reserved item on the pickup shelf for exactly 72 hours after "
            "sending the pickup-ready notice; if uncollected after 72 hours, the system shall cancel the hold and notify the next Member in queue."
        ),
        "defect": None,
    },
    {
        "req_id": "SD-012",
        "clean_text": (
            "The Circulation System shall allow a Member to renew an eligible loan at most 2 consecutive times "
            "provided no other Member has an active hold on that title; ineligible renewals shall return error ERR-RENEW-DENIED."
        ),
        "defect": {
            "type": "incompleteness",
            "subtype": "tbd",
            "related_ids": [],
            "defective_text": (
                "The Circulation System shall allow a Member to renew an eligible loan at most TBD consecutive times "
                "provided no other Member has an active hold on that title; ineligible renewals shall return error ERR-RENEW-DENIED."
            ),
            "evidence": "at most TBD consecutive times",
            "rationale": "Maximum renewal count is left as TBD.",
        },
    },
    {
        "req_id": "SD-013",
        "clean_text": (
            "When a Member scans an item barcode at a self-checkout kiosk, the Circulation System shall validate "
            "item eligibility within 2 seconds and print a receipt; if the barcode is unreadable or the item is reference-only, the kiosk shall display an error alert and abort checkout."
        ),
        "defect": {
            "type": "incompleteness",
            "subtype": "missing_error_handling",
            "related_ids": [],
            "defective_text": (
                "When a Member scans an item barcode at a self-checkout kiosk, the Circulation System shall validate "
                "item eligibility within 2 seconds and issue the loan receipt."
            ),
            "evidence": "validate item eligibility ... and issue the loan receipt",
            "rationale": "Omits error handling when the barcode is invalid or the item is ineligible for checkout.",
        },
    },
    {
        "req_id": "SD-014",
        "clean_text": (
            "The Hold Queue Service shall allow each Member to maintain at most 3 active hold requests simultaneously "
            "and reject additional requests with message ERR-HOLD-CAP."
        ),
        "defect": {
            "type": "incompleteness",
            "subtype": "missing_value_or_unit",
            "related_ids": [],
            "defective_text": (
                "The Hold Queue Service shall restrict each Member to the allowed maximum number of active hold "
                "requests and reject additional requests with message ERR-HOLD-CAP."
            ),
            "evidence": "the allowed maximum number of active hold requests",
            "rationale": "Fails to specify the numeric maximum hold limit.",
        },
    },
    {
        "req_id": "SD-015",
        "clean_text": (
            "The Circulation System shall restrict standard Members to a maximum of 8 simultaneous physical "
            "item checkouts via the online reservation cart."
        ),
        "defect": {
            "type": "inconsistency",
            "subtype": "conflicting_values",
            "related_ids": ["SD-009"],
            "defective_text": (
                "The Circulation System shall allow a standard Member in good standing to borrow up to 8 physical "
                "items simultaneously through the desk or self-checkout terminal."
            ),
            "evidence": "borrow up to 8 physical items simultaneously",
            "rationale": "Conflicts with SD-009, which limits active simultaneous loans to at most 5 items.",
        },
    },
    {
        "req_id": "SD-016",
        "clean_text": (
            "The Circulation System shall enforce a 14-day return window for print monographs checked out by Members."
        ),
        "defect": {
            "type": "inconsistency",
            "subtype": "conflicting_values",
            "related_ids": ["SD-010"],
            "defective_text": (
                "The Circulation System shall set the standard loan period for circulating print books to 21 calendar days "
                "from the checkout timestamp."
            ),
            "evidence": "21 calendar days",
            "rationale": "Conflicts with SD-010, which defines the standard loan duration as 14 calendar days.",
        },
    },
    {
        "req_id": "SD-017",
        "clean_text": (
            "The Registration Portal shall allow Librarians to pre-register visitors in person prior to ID check."
        ),
        "defect": {
            "type": "inconsistency",
            "subtype": "conflicting_rules",
            "related_ids": ["SD-001"],
            "defective_text": (
                "Unverified visitors shall be able to self-register online with only an email address and immediately "
                "check out physical books without Librarian ID verification."
            ),
            "evidence": "self-register online ... and immediately check out physical books without Librarian ID verification",
            "rationale": "Directly contradicts SD-001, which requires in-person Librarian verification of a government-issued photo ID before account creation.",
        },
    },
    {
        "req_id": "SD-018",
        "clean_text": (
            "The Hold Queue Service shall release uncollected reserved items after 72 hours and notify the Member of cancellation."
        ),
        "defect": {
            "type": "inconsistency",
            "subtype": "conflicting_rules",
            "related_ids": ["SD-011"],
            "defective_text": (
                "Reserved items placed on the pickup shelf shall remain held indefinitely until the requesting Member "
                "explicitly cancels the hold."
            ),
            "evidence": "remain held indefinitely until the requesting Member explicitly cancels",
            "rationale": "Directly contradicts SD-011, which mandates automatic cancellation after 72 hours.",
        },
    },

    # --- Module 3: Fines, Penalties & Notifications ---
    {
        "req_id": "SD-019",
        "clean_text": (
            "The Billing Service shall assess an overdue fine of $0.50 USD per overdue day per item, capped at a "
            "maximum of $20.00 USD per item, starting 24 hours after the due timestamp."
        ),
        "defect": None,
    },
    {
        "req_id": "SD-020",
        "clean_text": (
            "The Circulation System shall block any Member with an unpaid fine balance exceeding $5.00 USD from "
            "borrowing or renewing items until the balance drops to $5.00 USD or below."
        ),
        "defect": None,
    },
    {
        "req_id": "SD-021",
        "clean_text": (
            "When an item becomes 7 days overdue, the Notification Service shall send an overdue reminder email "
            "to the Member and suspend borrowing privileges until the item is returned."
        ),
        "defect": {
            "type": "ambiguity",
            "subtype": "coordination",
            "related_ids": [],
            "defective_text": (
                "When an item becomes 7 days overdue, the Notification Service shall send an overdue email "
                "and/or suspend borrowing privileges and/or apply a penalty flag."
            ),
            "evidence": "and/or suspend borrowing privileges and/or apply a penalty flag",
            "rationale": "Multiple 'and/or' coordinations leave unclear which subset of actions is mandatory.",
        },
    },
    {
        "req_id": "SD-022",
        "clean_text": (
            "The Billing Service shall allow a Librarian to waive overdue fines up to $25.00 USD after entering "
            "a mandatory reason code in the audit log; waivers above $25.00 USD require Administrator approval."
        ),
        "defect": {
            "type": "incompleteness",
            "subtype": "missing_actor",
            "related_ids": [],
            "defective_text": (
                "Overdue fine waiver requests up to $25.00 USD shall be reviewed, approved, and recorded with a "
                "reason code in the audit log within 1 business day."
            ),
            "evidence": "shall be reviewed, approved, and recorded",
            "rationale": "Passive construction omits the authorized actor responsible for reviewing and approving waivers.",
        },
    },
    {
        "req_id": "SD-023",
        "clean_text": (
            "The Notification Service shall dispatch SMS due-date alerts 24 hours before the due timestamp to "
            "all Members who have opted into SMS notifications."
        ),
        "defect": {
            "type": "ambiguity",
            "subtype": "weak_phrase",
            "related_ids": [],
            "defective_text": (
                "The Notification Service shall dispatch SMS due-date alerts to Members before the due date if appropriate."
            ),
            "evidence": "if appropriate",
            "rationale": "Weak conditional phrase 'if appropriate' leaves trigger conditions and timing undefined.",
        },
    },
    {
        "req_id": "SD-024",
        "clean_text": (
            "The Billing Service shall delete archived payment receipts after 7 years in accordance with the "
            "library retention policy."
        ),
        "defect": {
            "type": "incompleteness",
            "subtype": "tbd",
            "related_ids": [],
            "defective_text": (
                "The Billing Service shall retain payment receipts for TBD years before purging them from archival storage."
            ),
            "evidence": "TBD years",
            "rationale": "Retention period is marked as TBD instead of a concrete number of years.",
        },
    },
    {
        "req_id": "SD-025",
        "clean_text": (
            "The Billing Service shall calculate late fees at $0.50 USD per day with a $20.00 USD maximum cap."
        ),
        "defect": {
            "type": "inconsistency",
            "subtype": "conflicting_values",
            "related_ids": ["SD-019"],
            "defective_text": (
                "The Billing Service shall charge an overdue fine of $1.25 USD per overdue day per item with no "
                "maximum cap on accumulated fines."
            ),
            "evidence": "$1.25 USD per overdue day ... with no maximum cap",
            "rationale": "Conflicts with SD-019, which specifies $0.50 USD per day capped at $20.00 USD.",
        },
    },
    {
        "req_id": "SD-026",
        "clean_text": (
            "The Circulation System shall block online renewals when a Member's unpaid fine balance exceeds $5.00 USD."
        ),
        "defect": {
            "type": "inconsistency",
            "subtype": "conflicting_rules",
            "related_ids": ["SD-020"],
            "defective_text": (
                "A Member shall be permitted to renew borrowed items online at any time regardless of any unpaid "
                "overdue fine balance."
            ),
            "evidence": "renew borrowed items online at any time regardless of any unpaid overdue fine balance",
            "rationale": "Directly contradicts SD-020, which blocks renewals when unpaid fines exceed $5.00 USD.",
        },
    },
    {
        "req_id": "SD-027",
        "clean_text": (
            "The Circulation System shall display a Member's active loan list, due dates, and current fine balance "
            "on the account summary screen within 1 second."
        ),
        "defect": {
            "type": "inconsistency",
            "subtype": "terminology",
            "related_ids": ["SD-001", "SD-009"],
            "defective_text": (
                "The Circulation System shall display each Patron's active loan count and enforce the 5-item "
                "borrowing limit on the Patron profile screen within 1 second."
            ),
            "evidence": "Patron's ... Patron profile",
            "rationale": "Uses 'Patron' instead of the established SRS term 'Member' defined in SD-001 and SD-009.",
        },
    },

    # --- Module 4: Catalog, Search & Discovery ---
    {
        "req_id": "SD-028",
        "clean_text": (
            "The Catalog Search Service shall return paginated results of 25 items per page within 800 milliseconds "
            "under a sustained load of 500 concurrent queries."
        ),
        "defect": {
            "type": "ambiguity",
            "subtype": "vague_term",
            "related_ids": [],
            "defective_text": (
                "The Catalog Search Service shall return search results quickly even when many users are querying "
                "the catalog simultaneously."
            ),
            "evidence": "quickly ... many users",
            "rationale": "Unquantified terms 'quickly' and 'many users' lack measurable latency and concurrency thresholds.",
        },
    },
    {
        "req_id": "SD-029",
        "clean_text": (
            "The Catalog Search Service shall highlight exact matched query terms inside title and abstract "
            "snippets using HTML <mark> tags when query length is between 2 and 100 characters."
        ),
        "defect": {
            "type": "ambiguity",
            "subtype": "weak_phrase",
            "related_ids": [],
            "defective_text": (
                "The Catalog Search Service shall highlight matched query terms inside result snippets where possible."
            ),
            "evidence": "where possible",
            "rationale": "Weak phrase 'where possible' makes the requirement non-verifiable and optional without criteria.",
        },
    },
    {
        "req_id": "SD-030",
        "clean_text": (
            "The Catalog Search Service shall normalize ISBN-10 and ISBN-13 search strings by stripping hyphens "
            "and spaces, and return matching bibliographic records within 500 milliseconds."
        ),
        "defect": {
            "type": "ambiguity",
            "subtype": "vague_term",
            "related_ids": [],
            "defective_text": (
                "The Catalog Search Service shall provide sufficient ISBN matching accuracy and acceptable response "
                "times for catalog lookups."
            ),
            "evidence": "sufficient ... acceptable",
            "rationale": "Vague qualifiers 'sufficient' and 'acceptable' provide no testable acceptance threshold.",
        },
    },
    {
        "req_id": "SD-031",
        "clean_text": (
            "The Catalog Import Service shall process batch MARC21 files up to 50,000 records within 5 minutes "
            "and quarantine malformed records into an error CSV report."
        ),
        "defect": {
            "type": "ambiguity",
            "subtype": "vague_term",
            "related_ids": [],
            "defective_text": (
                "The Catalog Import Service shall efficiently process large batch MARC21 files without noticeable "
                "system slowdown."
            ),
            "evidence": "efficiently ... large ... noticeable",
            "rationale": "Vague terms 'efficiently', 'large', and 'noticeable' lack concrete volume and latency bounds.",
        },
    },
    {
        "req_id": "SD-032",
        "clean_text": (
            "When a Librarian deletes a bibliographic record that still has active loans or holds, the Catalog "
            "Service shall block deletion and return error ERR-CAT-INUSE."
        ),
        "defect": {
            "type": "incompleteness",
            "subtype": "missing_consequence",
            "related_ids": [],
            "defective_text": (
                "When a Librarian attempts to delete a bibliographic record that still has active loans or holds, "
                "the Catalog Service shall detect the active references."
            ),
            "evidence": "shall detect the active references",
            "rationale": "States that the system detects active references but omits what action/consequence follows (block, warn, or cascade).",
        },
    },

    # --- Module 5: Administration, Security & Reliability ---
    {
        "req_id": "SD-033",
        "clean_text": (
            "The Reporting Service shall allow an Administrator to export daily circulation logs in UTF-8 CSV "
            "format up to 100,000 rows per file, returning status HTTP 200 within 10 seconds."
        ),
        "defect": None,
    },
    {
        "req_id": "SD-034",
        "clean_text": (
            "The Backup Service shall execute an encrypted full database backup daily at 02:00 UTC and verify "
            "checksum integrity; backup failures shall trigger an alert to the Administrator within 5 minutes."
        ),
        "defect": {
            "type": "incompleteness",
            "subtype": "tbd",
            "related_ids": [],
            "defective_text": (
                "The Backup Service shall execute an encrypted full database backup at TBD intervals and verify "
                "checksum integrity; backup failures shall trigger an alert to the Administrator within 5 minutes."
            ),
            "evidence": "at TBD intervals",
            "rationale": "Backup frequency is unspecified (TBD).",
        },
    },
    {
        "req_id": "SD-035",
        "clean_text": (
            "The Audit Service shall log all Librarian and Administrator privilege changes within 1 second "
            "and retain logs in append-only storage for 365 days."
        ),
        "defect": {
            "type": "ambiguity",
            "subtype": "vague_term",
            "related_ids": [],
            "defective_text": (
                "The Audit Service shall record important administrative actions in a timely manner and retain them "
                "for an appropriate period."
            ),
            "evidence": "important ... timely manner ... appropriate period",
            "rationale": "Multiple vague terms leave event scope, latency, and retention period undefined.",
        },
    },
    {
        "req_id": "SD-036",
        "clean_text": (
            "If the primary database node becomes unreachable for more than 10 seconds, the Failover Manager "
            "shall promote the synchronous standby replica within 30 seconds and log event FAILOVER-01."
        ),
        "defect": {
            "type": "incompleteness",
            "subtype": "missing_consequence",
            "related_ids": [],
            "defective_text": (
                "If the primary database node becomes unreachable for more than 10 seconds, the Failover Manager "
                "shall log event FAILOVER-01."
            ),
            "evidence": "unreachable for more than 10 seconds, the Failover Manager shall log event FAILOVER-01",
            "rationale": "Omits the recovery action/timeout when primary database failover occurs.",
        },
    },
    {
        "req_id": "SD-037",
        "clean_text": (
            "The Portal Interface shall restrict Member login pages to TLS 1.3 and display clear error codes "
            "for expired certificates within 3 seconds."
        ),
        "defect": {
            "type": "ambiguity",
            "subtype": "vague_term",
            "related_ids": [],
            "defective_text": (
                "The Portal Interface shall provide adequate transport security and clear error messages during "
                "authentication."
            ),
            "evidence": "adequate ... clear",
            "rationale": "Vague terms 'adequate' and 'clear' lack concrete protocol and error-format specifications.",
        },
    },
    {
        "req_id": "SD-038",
        "clean_text": (
            "The Authentication Service shall enforce a minimum password length of 12 characters."
        ),
        "defect": {
            "type": "inconsistency",
            "subtype": "conflicting_values",
            "related_ids": ["SD-002"],
            "defective_text": (
                "The Authentication Service shall accept any Member password of at least 8 characters during "
                "account registration and password reset."
            ),
            "evidence": "at least 8 characters",
            "rationale": "Conflicts with SD-002, which requires Member passwords of at least 12 characters.",
        },
    },
    {
        "req_id": "SD-039",
        "clean_text": (
            "The Authentication Service shall automatically log out inactive web portal users after 15 minutes."
        ),
        "defect": {
            "type": "inconsistency",
            "subtype": "conflicting_values",
            "related_ids": ["SD-004"],
            "defective_text": (
                "The Authentication Service shall keep authenticated web portal sessions active for 60 minutes "
                "of user inactivity before requiring re-authentication."
            ),
            "evidence": "60 minutes of user inactivity",
            "rationale": "Conflicts with SD-004, which terminates inactive sessions after 15 minutes.",
        },
    },
    {
        "req_id": "SD-040",
        "clean_text": (
            "The Authentication Service shall hash Member and Librarian passwords using bcrypt."
        ),
        "defect": {
            "type": "inconsistency",
            "subtype": "conflicting_rules",
            "related_ids": ["SD-003"],
            "defective_text": (
                "The Authentication Service shall encrypt all Member passwords using reversible AES-256 encryption "
                "so Administrators can decrypt and retrieve forgotten passwords upon request."
            ),
            "evidence": "reversible AES-256 encryption so Administrators can decrypt and retrieve forgotten passwords",
            "rationale": "Directly contradicts SD-003, which mandates one-way bcrypt hashing and forbids storing recoverable passwords.",
        },
    },
]


def main() -> None:
    assert len(ITEMS) == 40, f"Expected 40 items, got {len(ITEMS)}"
    req_index = {item["req_id"]: idx for idx, item in enumerate(ITEMS)}

    seeded_reqs = []
    findings = []
    originals = {}

    for item in ITEMS:
        rid = item["req_id"]
        d = item["defect"]
        if d is None:
            seeded_reqs.append({"req_id": rid, "text": item["clean_text"]})
        else:
            seeded_reqs.append({"req_id": rid, "text": d["defective_text"]})
            for rel in d["related_ids"]:
                assert rel in req_index, f"Unknown related_id {rel} in {rid}"
                assert req_index[rel] < req_index[rid], (
                    f"Canonical rule violation: {rid} references later/equal {rel}"
                )
            findings.append(
                {
                    "req_id": rid,
                    "type": d["type"],
                    "subtype": d["subtype"],
                    "evidence": d["evidence"],
                    "related_ids": d["related_ids"],
                    "rationale": d["rationale"],
                }
            )
            originals[rid] = item["clean_text"]

    # Validate exact counts from PLAN.md
    by_type = {}
    by_subtype = {}
    for f in findings:
        by_type[f["type"]] = by_type.get(f["type"], 0) + 1
        by_subtype[(f["type"], f["subtype"])] = by_subtype.get((f["type"], f["subtype"]), 0) + 1

    assert by_type == {"ambiguity": 10, "incompleteness": 10, "inconsistency": 10}, by_type

    doc_out = {
        "doc_id": "seeded_lms",
        "title": "Library Management System (LMS) — Software Requirements Specification",
        "source": "Synthetic seeded benchmark (40 requirements: 10 clean, 30 defective)",
        "requirements": seeded_reqs,
    }
    key_out = {
        "doc_id": "seeded_lms",
        "findings": findings,
        "original_texts": originals,
    }

    (ROOT / "data/seeded_lms.json").write_text(json.dumps(doc_out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    (ROOT / "ground_truth/seed_key.json").write_text(json.dumps(key_out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")

    print("Generated seeded_lms.json (40 reqs) and seed_key.json (30 findings)")
    print("Type counts:", by_type)
    print("Subtype counts:", sorted(by_subtype.items()))


if __name__ == "__main__":
    main()
