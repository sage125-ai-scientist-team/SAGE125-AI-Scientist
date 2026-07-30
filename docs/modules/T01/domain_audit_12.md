# T01 12-Domain Audit Table（08/04）

Machine-readable source: `domain_audit_12.json`.

| QID | Domain | Topic relevant | Cross-domain policy |
|---|---|---|---|
| Q001 | mathematics | Yes | allow_if_quote_overlaps |
| Q012 | physics | Yes | allow_if_quote_overlaps |
| Q018 | chemistry | Yes | allow_if_quote_overlaps |
| Q024 | biology | Yes | allow_if_quote_overlaps |
| Q028 | medicine | Yes | DEGRADE OVERGENERALIZATION (single cancer ↛ all cancers) |
| Q035 | earth_science | Yes | allow_if_quote_overlaps |
| Q042 | computer_science | Yes | allow_if_quote_overlaps |
| Q051 | materials | Yes | allow_if_quote_overlaps |
| Q063 | astronomy | Yes | allow_if_quote_overlaps |
| Q077 | neuroscience | Yes | allow_if_quote_overlaps |
| Q089 | climate | No (oncology evidence) | DEGRADE CROSS_DOMAIN |
| Q102 | engineering | Yes | allow_if_quote_overlaps |
