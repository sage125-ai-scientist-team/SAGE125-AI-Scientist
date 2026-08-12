# T09 Formal Pairing and Relevance-Gold Rules

`atomic_pair_key = claim_id + evidence_id`; `canonical_pair_id = t01::<claim_id>::<evidence_id>`. Every admitted pair must retain its question, source, relation, decision, verbatim quote, locator, content hash and source hash.

For retrieval, `query_identity = linked_question_id` and `document_identity = source_id + fixed_source_hash`. A positive qrel exists only when `relation == supports` and `expected_decision == allow`. All unlisted material is **unjudged**, never an inferred negative or hard negative. Recall@k and MRR include only questions with an admitted positive whose fixed source actually entered the evaluated index.

Citation correctness and hallucination checks must additionally verify the claim, pair, verbatim quote, locator and fixed source hash; retrieval hit alone is insufficient. Any byte, pair, quote, locator, license or provenance change invalidates this admission and requires a new audit and approval.

The T06 Zenodo package is an approved multimodal input only. `T06_RELEVANCE_GOLD=false`: it produces no retrieval qrels and never enters a retrieval relevance denominator.
