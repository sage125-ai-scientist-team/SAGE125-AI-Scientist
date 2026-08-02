# T01 → T09 Actual Gold 交接说明

## 状态

- 已提交 **provenance-complete actual gold 输入**（`pairs.json`，8 条）
- `ready_for_t09_formal_eval=true`：表示 T01 侧认为可供 T09 做正式评测接入校验
- `corpus_inclusion_status=NOT_CLAIMED_IN_FORMAL_CORPUS`：**未宣布已纳入正式 corpus**
- 最终是否纳入正式 corpus：**由 T09 校验 + 组长确认**

## 10 项对照

| # | 要求 | T01 交付位置 |
|---|---|---|
| 1 | source URI | 每条 pair 的 `source_uri` / DOI |
| 2 | 数据版本或获取日期 | `data_version` + `sources/*.meta.json` `retrieved_at_utc` |
| 3 | 许可证/授权/可用范围 | `license_or_authorization`（CC-BY OA） |
| 4 | 原始文件 SHA-256 | `source_file_sha256` + `SOURCES_INDEX.json` |
| 5 | 仓库/受控路径 | `docs/modules/T01/eval_gold/v1/` 与 `sources/` |
| 6 | 可复现命令 | `REPRODUCE.md` + `fetch_eval_gold_sources.py` |
| 7 | 标签/预期/领域映射 | `expected_decision` / `domain` / `linked_question_id` |
| 8 | Git commit | `manifest.provenance.git_commit`（提交后更新） |
| 9 | 非 synthetic/provisional/fixture | pair 与 manifest 均声明 true/false 相应位 |
| 10 | 不能入仓时的受控访问 | PDF 默认不入仓；按 SHA 按需下载验收 |

## 禁止项（已遵守）

- 未覆盖/改写 `docs/modules/T01/evidence_gold_set.json`
- 未自行宣布纳入正式 actual gold corpus
