# T01 Interface Freeze — 2026-08-03

本文件冻结 Wave B（08/03）对外交接面，供 T02 / T03 / T08 消费。
变更须经队长明示；日常开发不得悄悄改签名或删字段。

## 1. 冻结范围

| Symbol | Module | Role |
|---|---|---|
| `EvidenceCardContract` | `app.contracts.evidence` | 证据卡契约（含 `quoted_text`） |
| `ClaimEvidenceLink` | `app.contracts.evidence` | claim↔evidence 关系 |
| `EvidenceBundle` | `app.contracts.evidence` | 受控证据包 |
| `build_evidence_bundle` | `app.evidence.bundle_builder` | Bundle 构建 |
| `check_claim_evidence_support` | `app.evidence.support_checker` | 支持性检查 |
| `build_t08_citation_payload` | `app.evidence.citation_renderer` | T08 引用载荷 |
| `run_q028_regression` | `app.evidence.q028_regression` | Q028 回归 |
| `attach_bundle_to_plan_version` | `app.evidence.integration_bridge` | T02 指纹挂载 |
| `build_validation_context_from_bundle` | `app.evidence.integration_bridge` | T03 ValidationContext 投影 |
| `precheck_bundle_for_validation` | `app.evidence.integration_bridge` | 缺证据/冲突预检 |

## 2. T02 挂载约定

```text
PlanVersion.prompt_fingerprints["t01_evidence_bundle_sha256"] = <hex>
PlanVersion.prompt_fingerprints["t01_evidence_ids"] = "id1,id2,..."
PlanVersion.hypothesis_generation["evidence_bundle"] = {
  bundle_id, fingerprint, evidence_ids, link_count,
  token_budget, truncated, truncation_reason
}
```

## 3. T03 投影约定

`ValidationContext.evidence_cards[]` 必须至少保留：

- `id`（= `evidence_id`，兼容 T03 示例）
- `evidence_id`, `source_id`, `source_type`, `title`
- `quoted_text`, `locator`, `content_hash`
- `run_id`, `version_id`, `question_id`（身份字段）

丢失任一关键 provenance → `T01_EVIDENCE_FIELD_LOSS`（P0）。

## 4. Gate 错误码（T01 预检）

| Code | Severity | Meaning |
|---|---|---|
| `T01_MISSING_EVIDENCE` | P1 | claim 引用不存在的 evidence_id |
| `T01_FAKE_BOOKLET_EVIDENCE_ID` | P0 | 伪造 booklet_excerpt_Q* |
| `T01_CONFLICT_EVIDENCE` | P1 | 同 claim 同时 supports+contradicts |
| `T01_EVIDENCE_FIELD_LOSS` | P0 | 投影丢失 quote/locator/hash 等 |

## 4b. Support checker 错误码（消费侧）

| Code | Decision | Meaning |
|---|---|---|
| `METADATA_ONLY` | BLOCK | 标题 / DOI-only / URL-only quote |
| `BOOKLET_EXCLUDED` | BLOCK | 问题册（含改名线索） |
| `INCOMPLETE_PROVENANCE` | BLOCK | supports 缺少 locator/authors/DOI\|URL/hash（T04 loader 缺口 fail-closed） |

## 4c. T04 loader → T01 最低字段（联审要求）

上游（T04）交付给 T01 的每张可用于 **supports** 的卡，必须完整包含：

1. `locator`（真实页码/章节/路径，禁止仅 identity 兜底）
2. `authors`
3. `doi` 或 `url`
4. `content_hash`（或可由非空 `quoted_text` 确定性生成）
5. 非空科学 `quoted_text`（不得为 DOI-only）

## 5. 非所有权（不得改）

- `app/workflow/pipeline.py`（T02）
- T02 / T03 owner 实现与其测试树
- 已合并 Wave A 契约语义（除非队长要求解冻）
