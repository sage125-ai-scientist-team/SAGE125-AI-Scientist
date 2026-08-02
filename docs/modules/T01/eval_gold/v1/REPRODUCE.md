# T01 Eval Gold v1 — 可重现命令

## 环境

- Windows 11 + PowerShell（或 Linux/macOS）
- Python 3.11+
- 工作目录：仓库根
- Git 检出需尊重 `.gitattributes`（`sources/*.xml` 为 `-text`，禁止换行改写）

## XML 规范字节语义

权威 XML 字节 = 仓库内冻结快照 `sources/PMC*.xml`：

1. 来源：Europe PMC `fullTextXML` HTTP 响应体；
2. 落盘：`Path.write_bytes`（不转换换行、不写 BOM）；
3. Git：`docs/modules/T01/eval_gold/v1/sources/*.xml -text`；
4. 哈希：对磁盘原始字节做 SHA-256；与 `SOURCES_INDEX.json` / 校验器同一语义。

维护者重新冻结（非验收步骤）：

```powershell
python scripts/t01/freeze_eval_gold_sources.py --package docs/modules/T01/eval_gold/v1
```

## 验收命令（只读；期望 exit 0）

```powershell
python scripts/t01/fetch_eval_gold_sources.py --package docs/modules/T01/eval_gold/v1
python scripts/t01/validate_eval_gold.py --package docs/modules/T01/eval_gold/v1 --require-ready
```

期望：`RESULT=SOURCE_OK` 与 `RESULT=ACTUAL_GOLD_OK`。

## payload commit 语义

`manifest.provenance.git_commit` = **payload commit**（冻结 pairs/sources/domain mapping 的内容提交），  
**不是**仅更新 manifest/checksums 的 tip metadata commit，也不是“包含自身的最终 tip SHA”。

## 可选：PDF

```powershell
python scripts/t01/fetch_eval_gold_sources.py --package docs/modules/T01/eval_gold/v1 --pdf --refetch-missing
```

## Fixture 隔离

- 正式金标：`docs/modules/T01/eval_gold/v1/`
- 排除：`docs/modules/T01/evidence_gold_set.json`
- 领域映射：`domain_mapping_eval_gold.json`（仅 `EVAL-CLAIM-*`，不依赖 fixture `CLAIM-*`）
