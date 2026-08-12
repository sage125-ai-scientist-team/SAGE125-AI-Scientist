# T01 → T07：EvidenceBundle / precheck 验收语义确认

**Date:** 2026-08-10  
**Audience:** T07 Formal Evidence Context Adapter  
**Scope:** 确认公共接口验收语义；**不**修改 T01 内部实现；**不**交付 T04 RAG 索引/文献包。

## 1. 确认结论

T07 使用下列公共接口构造并预检 EvidenceBundle，**符合 T01 验收语义**：

| API | Module |
|---|---|
| `EvidenceCardContract` / `ClaimEvidenceLink` / `EvidenceBundle` | `app.contracts.evidence` |
| `evidence_card_to_validation_wire` | `app.evidence.integration_bridge` |
| `build_validation_context_from_bundle`（或等价手写 `ValidationContext`） | `app.evidence.integration_bridge` |
| `precheck_bundle_for_validation` | `app.evidence.integration_bridge` |
| `ClaimText` + `check_claim_evidence_support`（由 precheck 内部调用） | `app.evidence.support_checker` |

**通过判据（与 T07 门禁对齐）：**

```text
precheck = precheck_bundle_for_validation(bundle=..., claims=..., context=...)
assert precheck.gate.passed is True   # 注意：是 gate.passed，不是顶层 .passed
assert not precheck.field_loss
assert precheck.missing_blocked is False
```

T07 所列停止条件在 T01 侧语义上对齐：

| T07 条件 | T01 对应 |
|---|---|
| `retrieval_hits > 0` | `EvidenceBundle.evidences` 非空（构造期强制） |
| `question_booklet_hits = 0` | booklet 不得用于 `supports`；`BOOKLET_EXCLUDED` / 契约禁止 booklet=`valid` |
| all quotes non-empty | 契约 `quoted_text` 非空；precheck 检查 wire 含 `quoted_text` |
| all locators valid | 契约 locator 非空；`supports` 还需完整 provenance（见下） |
| T01 precheck passed | `precheck.gate.passed is True` |

## 2. EvidenceCard / Bundle 必需条件

### 2.1 `EvidenceCardContract`（每张卡）

最低契约：

- `evidence_id`, `source_id`, `source_type`, `title`
- **`quoted_text` 非空**（且非纯空白）
- **`locator` 非空 dict**
- `verification_status=valid` 时额外：非 title-only、非 booklet、必须有 `content_hash`

对 **`supports` 关系**（科学支撑），支持检查器还要求完整 provenance，否则 `INCOMPLETE_PROVENANCE` **BLOCK**：

- 有效 `locator`（不得是 builder 兜底 `locator_inferred_from_card_identity`）
- `authors` 非空
- `doi` **或** `url` 至少一个非空
- `content_hash` 非空

并 **BLOCK**：

- metadata-only / DOI-only quote（`METADATA_ONLY`）
- booklet / 题册来源（`BOOKLET_EXCLUDED`）
- 虚构 `booklet_excerpt_Q*` id（`FAKE_BOOKLET_EVIDENCE_ID`）

题册 PDF（如 `data/raw/sjtu-booklet.pdf`）**不得**作为科学研究证据进入 `supports`。

### 2.2 `ClaimEvidenceLink` / `EvidenceBundle`

- `evidences`、`links` 均非空；`evidence_id` 唯一
- 每个 `link.evidence_id` 必须存在于 `evidences`
- `supports` 且 claim/evidence 两侧 domain 均给出但不一致 → **构造期拒绝**
- 同一 claim 同时 `supports` + `contradicts` → precheck 记 `T01_CONFLICT_EVIDENCE`（blocking），不得静默当 established fact

### 2.3 `precheck_bundle_for_validation` 额外检查

调用方必须提供：

1. 合法 `EvidenceBundle`
2. `claims: Sequence[ClaimText]`（`claim_id` / `text` / `evidence_ids` / 可选 `relation`/`domain`）
3. `ValidationContext`（建议用 `build_validation_context_from_bundle` 从同一 Bundle 投影，避免字段丢失）

Wire 投影中每张卡必须保留非空：`quoted_text`, `locator`, `source_type`, `content_hash`；否则 `T01_EVIDENCE_FIELD_LOSS`（P0）→ `gate.passed=False`。

## 3. 推荐调用顺序（T07，不改 T01）

```text
RetrievalHit (from T04 retrieve_hits — T04 交付)
  → EvidenceCardContract (+ content_hash)
  → EvidenceBundle(evidences, links)
  → ValidationContext = build_validation_context_from_bundle(...)
  → ClaimText[...] 对齐将提交给 Provider 的 claims/evidence_ids
  → precheck = precheck_bundle_for_validation(...)
  → only if precheck.gate.passed: allow Provider call with pre-existing evidence_ids
```

## 4. 明确非 T01 范围

以下由 **T04 / 队长协调**，T01 **不**在本确认中交付实现：

- `retrieve_hits()` 无损公共接口（队长已授权 T04 实施；见 §6）
- `user_library` / chunks.jsonl / 非题册研究文献包及许可/SHA/加载命令

T01 仅确认：一旦 T07 持有合格 `EvidenceCardContract` 并组成 Bundle，上述 precheck 语义即为验收标准。

## 5. Pairing / 指标边界（不变）

- `PAIRING_STRUCTURE=STRUCTURE_OK`（contract fixture pairing 另册）
- `ACTUAL_RELEVANCE_GOLD=NOT_READY`
- `FORMAL_RETRIEVAL_METRICS_AUTHORIZED=false`（队长 2026-08-12 授权仍保持 false）

## 6. 队长授权后的 T01 后续职责（2026-08-12）

PR #35 队长评论 `[CAPTAIN AUTHORIZATION] T04 无损 RetrievalHit 接口与 Q001 真实文献包责任人` 指定：

```text
Q001_SEMANTIC_SIGNOFF_OWNER=@Yqqxz (T01)
```

T01 **两道语义门**（详见 `docs/modules/T01/q001_t04_semantic_signoff.md`）：

1. **门 A**：对 T04 Draft PR（`t04/c-retrieval-hit-interface`）准确 HEAD 做 `retrieve_hits` 语义 signoff（不写检索代码）。  
2. **门 B**：Q001 真实文献包受控交付并由 T04 验收后，对实际 hits / EvidenceBundle 做语义签字（含 `precheck.gate.passed`）。

当前状态：

```text
T04 Draft PR = #47 @ f77959b43f7f520119070181011e0d0713425cdd → 门 A = PASS
Q001_MATERIAL_STATUS=AWAITING_CONTROLLED_DELIVERY → 门 B = WAIT
T07_REAL_RUN_STATUS=HOLD
READY_AUTHORIZED=false
MERGE_AUTHORIZED=false
```

硬边界：`sjtu-booklet.pdf` 不得进入 scientific `supports`；正式 context 必须 `question_booklet_hits=0`。
