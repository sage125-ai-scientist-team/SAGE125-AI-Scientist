# T01 Evidence Gold Set v1

## Purpose

Initial fact-evidence pairs for validating EvidenceCardV2,

ClaimEvidenceLink and EvidenceBundle contracts.

This file defines validation samples only.

No fabricated paper metadata or unsupported scientific claims are included.

---

# Sample Format

Each evidence pair contains:

- claim_id
- claim
- evidence_id
- source_status
- relation
- validation_status

---

# Evidence Pairs

## Pair 001

claim_id:

CLAIM-001

claim:

A scientific claim requires traceable supporting evidence.

evidence_id:

EV-PENDING-001

source_status:

pending

relation:

supports

validation_status:

pending

---

## Pair 002

claim_id:

CLAIM-002

claim:

Evidence location information should be preserved.

evidence_id:

EV-PENDING-002

source_status:

pending

relation:

supports

validation_status:

pending

---

## Pair 003

claim_id:

CLAIM-003

claim:

Title-only information should not establish scientific facts.

evidence_id:

EV-PENDING-003

source_status:

pending

relation:

context

validation_status:

pending

---

## Pair 004

claim_id:

CLAIM-004

claim:

Question booklet content should not become scientific evidence.

evidence_id:

EV-PENDING-004

source_status:

pending

relation:

contradicts

validation_status:

pending

---

## Pair 005

claim_id:

CLAIM-005

claim:

Evidence IDs must map to existing EvidenceCard objects.

evidence_id:

EV-PENDING-005

source_status:

pending

relation:

supports

validation_status:

pending

---

# Pair 006-020

The remaining 15 validation pairs follow the same schema:

- unique claim_id
- unique evidence_id
- explicit relation
- validation status
- no fabricated scientific metadata

They will be populated with verified literature evidence after EvidenceCardV2 integration.