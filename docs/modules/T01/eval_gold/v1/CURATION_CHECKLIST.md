# T01 Eval Gold v1 — 人工著录清单

完成每一条后再把 `pairs.json` 写入真实条目，并运行：

```powershell
python docs/modules/T01/scripts/validate_eval_gold.py --package docs/modules/T01/eval_gold/v1 --require-ready
```

## 每条 pair 必填

- [ ] 真实 `source_uri`（DOI URL 或出版商/仓库 URI，可打开）
- [ ] `data_version`（版本日 / DOI 版本 / 快照 ID）
- [ ] `license_or_authorization`（CC-BY / 出版商摘录许可 / 书面授权路径）
- [ ] 非空科学 `quote`（原文片段，**禁止** DOI-only / 题册；字段名不是 quoted_text）
- [ ] 真实 `locator`（page/section 等）
- [ ] `authors` +（`doi` 或 `url`）+ `content_hash`
- [ ] `expected_decision` ∈ {allow, degrade, block}
- [ ] `domain` + 可选 `linked_question_id`
- [ ] `provisional=false`
- [ ] `synthetic=false`
- [ ] `fixture=false`
- [ ] `evaluation_tier=actual_gold`

## 包级

- [ ] 更新 `manifest.json` 中 `pair_count`、`git_commit`、`ready_for_t09_formal_eval=true`
- [ ] 重算 `checksums.sha256`
- [ ] 在 PR 评论贴：路径 + commit + manifest SHA-256 给 T09

## 禁止

- 把 `evidence_gold_set.json` 直接改 `provisional=false`
- 编造 DOI / 伪造摘录
- 仅口头说明、无 SHA / 无复现命令
