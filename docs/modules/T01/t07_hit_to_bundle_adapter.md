# T07：`RetrievalHit` → EvidenceBundle 适配说明（T01 侧契约）

**Audience:** `@myr-111`（T07）及下游消费方  
**Owner:** T01 `@Yqqxz`（只定义消费语义；**不**实现 `app/rag/**`）  
**Gate A HEAD（接口已签字）:** PR #47 @ `f77959b43f7f520119070181011e0d0713425cdd`  
**Captain Gate A:** `GATE_A_TECHNICAL_REVIEW=PASS`；`READY_AUTHORIZED=YES`；`MERGE_AFTER_READY=YES`；`WAVE_C_DONE=NO`  
**Gate B:** 仍 WAIT（Q001 未受控交付）  
**Date:** 2026-08-12

## 1. 允许的调用链

```text
LocalRAGRetriever.retrieve_hits(query, filters=None, source_scope="all")
  → tuple[RetrievalHit, ...]
  → EvidenceCardContract[]          # 本文件映射
  → EvidenceBundle(evidences, links)
  → ValidationContext = build_validation_context_from_bundle(...)
  → precheck_bundle_for_validation(bundle=..., claims=..., context=...)
  → 仅当 precheck.gate.passed is True 才允许带 evidence_ids 调 Provider
```

判定字段必须是 **`precheck.gate.passed`**，不要读顶层其它布尔字段。

## 2. 字段映射（接口文档）

### 2.1 `hit_to_evidence_card_contract(hit) -> EvidenceCardContract`

| 源（`RetrievalHit`） | 目标（`EvidenceCardContract`） | 规则 |
|---|---|---|
| （派生） | `evidence_id` | 稳定派生（建议 `chunk_id` 或 `content_hash` 前缀）；**禁止** `booklet_excerpt_Q*` |
| `metadata["source_id"]` | `source_id` | 必填；Gate A 接口已 fail-closed 要求非空 |
| `source_type` | `source_type` | `paper`/`web`/`dataset` 同名；`booklet` → **`question_booklet`**；`unknown` **不得**作 scientific supports |
| `title` | `title` | 原样 |
| `quoted_text` | `quoted_text` | 原样；禁 LLM 改写 |
| `source_locator` | `locator` | 见 §2.2 |
| `metadata.get("authors")` | `authors` | 列表；supports 要求非空（缺则 T01 BLOCK） |
| `metadata.get("year")` | `year` | 可选 |
| `doi` / `url` | `doi` / `url` | supports 至少其一非空 |
| `content_hash` | `content_hash` | 完整 64-hex；勿截断 |
| （默认） | `verification_status` | 未人工核验前保持 `pending` |

### 2.2 `source_locator` → `locator` dict

T04 `SourceLocator` 键名：`document_id`, `page`, `section`, `chunk_id`, `char_start`, `char_end`。

T01 `incomplete_support_provenance_fields` 认可的定位键包括：`page`, `section`, `document`, `source_path`, `chunk`。

推荐投影：

```text
locator = {
  "document": hit.source_locator.document_id,   # 始终写入
  "chunk": hit.source_locator.chunk_id,           # 若有
  "page": hit.source_locator.page,                # 若有
  "section": hit.source_locator.section,          # 若有
  "char_start": hit.source_locator.char_start,    # 若有
  "char_end": hit.source_locator.char_end,        # 若有
}
# 去掉值为 None 的键；禁止写入 note=locator_inferred_from_card_identity
```

若只拷贝 `model_dump()` 且**没有** `page`/`section`，仅剩 `document_id`/`chunk_id`，T01 会判 locator 不完整 → supports `INCOMPLETE_PROVENANCE`。

## 3. `ClaimEvidenceLink` / Bundle

| 字段 | 要求 |
|---|---|
| `claim_id` / `evidence_id` | 非空；`evidence_id` 必须落在 `evidences` |
| `relation` | `supports` \| `contradicts` \| `context` |
| booklet / `question_booklet` | **不得**用于 scientific `supports` |
| 同 claim 同时 supports+contradicts | precheck 记冲突；不得静默当 established fact |
| 跨域 supports | 两侧 domain 均给出且不一致 → Bundle 构造期拒绝 |

## 4. 硬边界（T07 必须遵守）

```text
BOOKLET_AS_SUPPORTS=FORBIDDEN
question_booklet_hits 正式 context 必须为 0
FORMAL_RETRIEVAL_METRICS_AUTHORIZED=false
FIVE_REAL_RUNS=HOLD until captain + Gate B
不得使用 tests/rag/fixtures 或题册充当正式 evidence
```

## 5. 相关链接

- Gate A 签字清单：`docs/modules/T01/q001_t04_semantic_signoff.md`
- Precheck 语义：`docs/modules/T01/t07_evidence_context_acceptance.md`
- T04 PR：https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/47
