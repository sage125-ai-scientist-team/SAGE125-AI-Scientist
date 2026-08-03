# T01 → T09 Actual Gold 交接（NEEDS_CLARIFICATION 整改后）

## 状态

- 已按 T09 `NEEDS_CLARIFICATION` 整改并新增 commit（不改写旧 commit）
- `ready_for_t09_formal_eval=true`：可供 T09 复验
- `corpus_inclusion_status=NOT_CLAIMED_IN_FORMAL_CORPUS`：未宣布纳入正式 corpus
- 最终纳入：T09 复验通过后由组长确认

## `provenance.git_commit` 语义

| 字段 | 含义 |
|---|---|
| `provenance.git_commit` | **payload commit**：冻结金标内容（pairs / frozen XML / domain mapping）的提交 SHA |
| PR head / tip | 可为后续 metadata commit（仅回填 payload SHA + checksums）；**不要**要求 tip == payload |

`git_commit_semantics` 字段有同样说明。

## XML 规范字节

见 `REPRODUCE.md` 与 `sources/*.meta.json` 的 `xml_byte_semantics`。

## Fixture 隔离

| 工件 | 角色 |
|---|---|
| `eval_gold/v1/pairs.json` | 正式 gold 标签与 expected_decision 唯一权威 |
| `eval_gold/v1/domain_mapping_eval_gold.json` | 正式领域映射（仅 EVAL-CLAIM-*） |
| `evidence_gold_set.json` | harness fixture，**排除**，不参与正式标签 |
| `domain_audit_12.json` | Wave B 采样表，**不是**本包正式 mapping |

## 验收命令

```powershell
python docs/modules/T01/scripts/fetch_eval_gold_sources.py --package docs/modules/T01/eval_gold/v1
python docs/modules/T01/scripts/validate_eval_gold.py --package docs/modules/T01/eval_gold/v1 --require-ready
```

## CC-BY 归属

每条 pair 保留 DOI、作者、`license_or_authorization`（CC-BY）与 source URI；XML/PDF 哈希见 `sources/SOURCES_INDEX.json`。
