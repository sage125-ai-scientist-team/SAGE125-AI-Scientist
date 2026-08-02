# T09_HANDOFF_MESSAGE（整改后）

## 摘要

T01 已针对 PR #25 / Commit `bf196567a6bfe5dcc196ba58a5ec94bcb589ea92` 的
`NEEDS_CLARIFICATION` 完成整改：冻结 XML 规范字节、统一 SHA 语义、
payload_commit 字段语义、fixture 无关 domain mapping，并在隔离 clone 复验两命令 exit 0。

**未宣布纳入正式 corpus。** 请 T09 复验；通过后再提交组长确认。

## 固定信息（整改完成后由作者填入 / 见 PR 评论）

- 新固定 payload Commit：`<PAYLOAD_SHA>`
- 新 PR head：`<TIP_SHA>`
- 路径：`docs/modules/T01/eval_gold/v1/`

## 验收命令与期望 exit code

```powershell
python scripts/t01/fetch_eval_gold_sources.py --package docs/modules/T01/eval_gold/v1
# expect exit 0 / RESULT=SOURCE_OK

python scripts/t01/validate_eval_gold.py --package docs/modules/T01/eval_gold/v1 --require-ready
# expect exit 0 / RESULT=ACTUAL_GOLD_OK
```

## Fixture 隔离说明

- 正式标签权威：`pairs.json` + `domain_mapping_eval_gold.json`（EVAL-CLAIM-*）
- 明确排除：`docs/modules/T01/evidence_gold_set.json`（及其中 CLAIM-*）
- `domain_audit_12.json` 不再作为本包 `domain_mapping_doc`

## XML 字节语义

Europe PMC fullTextXML 响应体原样冻结；Git `-text`；SHA-256 = raw bytes。
