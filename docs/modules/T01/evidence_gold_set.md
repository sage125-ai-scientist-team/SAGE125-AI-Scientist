# T01 Evidence Gold Set v4

## Purpose

This document defines 20 provisional evidence contract validation pairs for the T01 evidence contract layer.

These pairs are NOT scientific evidence claims.

They are controlled validation fixtures used to verify:

- evidence object completeness;

- claim-evidence linkage;

- evidence traceability;

- unsupported reference rejection.

Each pair contains:

- claim_id

- claim

- evidence_id

- source_id

- source_type

- quote

- locator

- relation

- validation_status

The fixtures are designed for machine validation.

They must not be interpreted as verified scientific findings.

---

# Evidence Pair 001

claim_id:

CLAIM-001

claim:

Evidence objects require stable identifiers for traceability.

evidence_id:

EV-CONTRACT-001

source_id:

T01-CONTRACT-SPEC-001

source_type:

contract

quote:

"Evidence objects require stable identifiers."

locator:

{

  "document": "T01 Evidence Contract Specification",

  "section": "EvidenceCardContract",

  "field": "evidence_id"

}

relation:

supports

validation_status:

pending

---

# Evidence Pair 002

claim_id:

CLAIM-002

claim:

Evidence objects require source identification information.

evidence_id:

EV-CONTRACT-002

source_id:

T01-CONTRACT-SPEC-002

source_type:

contract

quote:

"Evidence objects preserve source identification information."

locator:

{

  "document": "T01 Evidence Contract Specification",

  "section": "EvidenceCardContract",

  "field": "source_id"

}

relation:

supports

validation_status:

pending

---

# Evidence Pair 003

claim_id:

CLAIM-003

claim:

Evidence records require explicit source categories.

evidence_id:

EV-CONTRACT-003

source_id:

T01-CONTRACT-SPEC-003

source_type:

specification

quote:

"Evidence source types must be explicitly represented."

locator:

{

  "document": "T01 Evidence Contract Specification",

  "section": "EvidenceCardContract",

  "field": "source_type"

}

relation:

supports

validation_status:

pending

---

# Evidence Pair 004

claim_id:

CLAIM-004

claim:

Evidence records require quoted content for provenance checking.

evidence_id:

EV-CONTRACT-004

source_id:

T01-CONTRACT-SPEC-004

source_type:

contract

quote:

"Evidence quotation content is required for provenance."

locator:

{

  "document": "T01 Evidence Contract Specification",

  "section": "EvidenceCardContract",

  "field": "quoted_text"

}

relation:

supports

validation_status:

pending

---

# Evidence Pair 005

claim_id:

CLAIM-005

claim:

Evidence records require location information.

evidence_id:

EV-CONTRACT-005

source_id:

T01-CONTRACT-SPEC-005

source_type:

specification

quote:

"Evidence location information enables traceability."

locator:

{

  "document": "T01 Evidence Contract Specification",

  "section": "EvidenceCardContract",

  "field": "locator"

}

relation:

supports

validation_status:

pending

---

# Evidence Pair 006

claim_id:

CLAIM-006

claim:

Claim and evidence relationships require explicit relation types.

evidence_id:

EV-CONTRACT-006

source_id:

T01-CONTRACT-SPEC-006

source_type:

contract

quote:

"Claim evidence links define explicit relationship categories."

locator:

{

  "document": "T01 Evidence Contract Specification",

  "section": "ClaimEvidenceLink",

  "field": "relation"

}

relation:

supports

validation_status:

pending

---

# Evidence Pair 007

claim_id:

CLAIM-007

claim:

Evidence links require referenced evidence identifiers.

evidence_id:

EV-CONTRACT-007

source_id:

T01-CONTRACT-SPEC-007

source_type:

contract

quote:

"Evidence references must point to identifiable evidence objects."

locator:

{

  "document": "T01 Evidence Contract Specification",

  "section": "ClaimEvidenceLink",

  "field": "evidence_id"

}

relation:

supports

validation_status:

pending

---

# Evidence Pair 008

claim_id:

CLAIM-008

claim:

Evidence confidence values require bounded representation.

evidence_id:

EV-CONTRACT-008

source_id:

T01-CONTRACT-SPEC-008

source_type:

specification

quote:

"Confidence values must remain within defined validation boundaries."

locator:

{

  "document": "T01 Evidence Contract Specification",

  "section": "ClaimEvidenceLink",

  "field": "confidence"

}

relation:

supports

validation_status:

pending

---

# Evidence Pair 009

claim_id:

CLAIM-009

claim:

Evidence bundles require controlled evidence collections.

evidence_id:

EV-CONTRACT-009

source_id:

T01-CONTRACT-SPEC-009

source_type:

contract

quote:

"Evidence bundles contain controlled evidence objects."

locator:

{

  "document": "T01 Evidence Contract Specification",

  "section": "EvidenceBundle",

  "field": "evidences"

}

relation:

supports

validation_status:

pending

---

# Evidence Pair 010

claim_id:

CLAIM-010

claim:

Evidence bundles require claim evidence links.

evidence_id:

EV-CONTRACT-010

source_id:

T01-CONTRACT-SPEC-010

source_type:

contract

quote:

"Evidence bundles maintain links between claims and evidence."

locator:

{

  "document": "T01 Evidence Contract Specification",

  "section": "EvidenceBundle",

  "field": "links"

}

relation:

supports

validation_status:

pending

---

# Evidence Pair 011

claim_id:

CLAIM-011

claim:

Missing evidence quotations should be rejected.

evidence_id:

EV-TEST-011

source_id:

T01-TEST-011

source_type:

test_fixture

quote:

"Empty quoted_text values must fail validation."

locator:

{

  "document": "T01 Evidence Contract Tests",

  "section": "invalid evidence cases",

  "case": "missing quote"

}

relation:

supports

validation_status:

pending

---

# Evidence Pair 012

claim_id:

CLAIM-012

claim:

Missing evidence locations should be rejected.

evidence_id:

EV-TEST-012

source_id:

T01-TEST-012

source_type:

test_fixture

quote:

"Empty locator values must fail validation."

locator:

{

  "document": "T01 Evidence Contract Tests",

  "section": "invalid evidence cases",

  "case": "missing locator"

}

relation:

supports

validation_status:

pending

---

# Evidence Pair 013

claim_id:

CLAIM-013

claim:

Unknown evidence references should be rejected.

evidence_id:

EV-TEST-013

source_id:

T01-TEST-013

source_type:

test_fixture

quote:

"Unknown evidence identifiers must fail reference validation."

locator:

{

  "document": "T01 Evidence Contract Tests",

  "section": "invalid link cases",

  "case": "unknown evidence id"

}

relation:

supports

validation_status:

pending

---

# Evidence Pair 014

claim_id:

CLAIM-014

claim:

Evidence identifiers must remain unique.

evidence_id:

EV-TEST-014

source_id:

T01-TEST-014

source_type:

test_fixture

quote:

"Evidence identifiers are used as unique traceability keys."

locator:

{

  "document": "T01 Evidence Contract Tests",

  "section": "identifier validation"

}

relation:

supports

validation_status:

pending

---

# Evidence Pair 015

claim_id:

CLAIM-015

claim:

Evidence provenance requires reproducible metadata.

evidence_id:

EV-CONTRACT-015

source_id:

T01-CONTRACT-SPEC-015

source_type:

specification

quote:

"Evidence provenance requires reproducible metadata fields."

locator:

{

  "document": "T01 Evidence Contract Specification",

  "section": "provenance"

}

relation:

supports

validation_status:

pending

---

# Evidence Pair 016

claim_id:

CLAIM-016

claim:

Evidence validation status must be explicitly represented.

evidence_id:

EV-CONTRACT-016

source_id:

T01-CONTRACT-SPEC-016

source_type:

contract

quote:

"Validation status records the current evidence checking state."

locator:

{

  "document": "T01 Evidence Contract Specification",

  "section": "validation_status"

}

relation:

supports

validation_status:

pending

---

# Evidence Pair 017

claim_id:

CLAIM-017

claim:

Evidence processing requires traceable intermediate objects.

evidence_id:

EV-CONTRACT-017

source_id:

T01-CONTRACT-SPEC-017

source_type:

specification

quote:

"Intermediate evidence objects preserve traceability."

locator:

{

  "document": "T01 Evidence Contract Specification",

  "section": "traceability"

}

relation:

supports

validation_status:

pending

---

# Evidence Pair 018

claim_id:

CLAIM-018

claim:

Evidence rejection requires explicit validation failure states.

evidence_id:

EV-TEST-018

source_id:

T01-TEST-018

source_type:

test_fixture

quote:

"Invalid evidence objects must produce validation failures."

locator:

{

  "document": "T01 Evidence Contract Tests",

  "section": "negative validation"

}

relation:

supports

validation_status:

pending

---

# Evidence Pair 019

claim_id:

CLAIM-019

claim:

Evidence contracts support downstream agent verification.

evidence_id:

EV-CONTRACT-019

source_id:

T01-CONTRACT-SPEC-019

source_type:

specification

quote:

"Validated evidence objects can be consumed by downstream processes."

locator:

{

  "document": "T01 Evidence Contract Specification",

  "section": "downstream usage"

}

relation:

supports

validation_status:

pending

---

# Evidence Pair 020

claim_id:

CLAIM-020

claim:

Evidence objects should remain traceable throughout processing.

evidence_id:

EV-CONTRACT-020

source_id:

T01-CONTRACT-SPEC-020

source_type:

contract

quote:

"Evidence objects maintain traceability throughout processing."

locator:

{

  "document": "T01 Evidence Contract Specification",

  "section": "traceability requirement"

}

relation:

supports

validation_status:

pending