# T09_HANDOFF_MESSAGE — 最终 provenance 整改包

## 申请意向

- **ACCEPT_CANDIDATE = YES**（请 T09 做 provenance-only 最终复验）
- 正式 corpus 纳入 = **NO**（不自行宣布；待 T09 + 组长）
- Merge = **NO**；PR 保持 **OPEN + Draft**

## 1. PR / HEAD

- PR：**#25**（https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/25）
- 固定复验 HEAD：以本分支 tip 为准（提交本文件后的 `git rev-parse HEAD` / `gh pr view 25 --json headRefOid`）
- payload commit（`manifest.provenance.git_commit`）：`14494e7f2e4ba30f5717332e030a65a9da448d6a`
- 完整冻结包说明：`FINAL_PROVENANCE_PACKAGE.md`

## 2. 来源 / 提供人

- 提供人：T01 `Yqqxz`
- 来源：5 篇 CC-BY OA 论文（DOI 见 `SOURCES_INDEX.json` / `pairs.json`）
- 非来源：`docs/modules/T01/evidence_gold_set.json`（排除）

## 3–4. 文件 SHA / 授权

- 包文件：`checksums.sha256`
- XML：`sources/SOURCES_INDEX.json`（字节数 + 完整 SHA-256）
- 授权：各篇 CC-BY Open Access；摘录署名

## 5. 一致性

`SOURCES_INDEX.json` ↔ `manifest.json` ↔ `REPRODUCE.md` ↔ `T09_HANDOFF*.md` ↔ `FINAL_PROVENANCE_PACKAGE.md` ↔ `domain_mapping_eval_gold.json`

## 6. 无待填占位

无 `PENDING_CONFIRMATION`；无无法解释占位。`pair.example.json` 仅为示例形状。

## 7. 隔离验证命令

```powershell
git clone --depth 1 --branch t01/b-evidence-core https://github.com/Yqqxz/SAGE125-AI-Scientist-t01.git
cd SAGE125-AI-Scientist-t01
python scripts/t01/fetch_eval_gold_sources.py --package docs/modules/T01/eval_gold/v1
python scripts/t01/validate_eval_gold.py --package docs/modules/T01/eval_gold/v1 --require-ready
```

期望：两命令均为 **exit 0**（`SOURCE_OK` / `ACTUAL_GOLD_OK`）。

## 8. CI

见 PR #25 Checks：lint / type / unit / integration / security / build（以固定 HEAD 最新 run 为准）。

## 9–10

ACCEPT_CANDIDATE=YES；Draft 保持；不 Ready/Merge（未经授权）。
