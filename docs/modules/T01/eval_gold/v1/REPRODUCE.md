# T01 Eval Gold v1 — 可重现命令

## 环境

- Windows 11 + PowerShell
- Python 3.11+（与仓库一致）
- 工作目录：仓库根 `SAGE125-AI-Scientist`

## 1. 定位包与 commit

```powershell
git rev-parse HEAD
git log -1 --oneline -- docs/modules/T01/eval_gold/v1
Get-ChildItem docs/modules/T01/eval_gold/v1
Get-ChildItem docs/modules/T01/eval_gold/v1/sources
```

## 2. 校验 XML 源 SHA（仓库内快照）

```powershell
python scripts/t01/fetch_eval_gold_sources.py --package docs/modules/T01/eval_gold/v1
```

期望：`RESULT=SOURCE_OK`。

## 3. （可选）拉取 publisher PDF 并核对 SHA-256

PDF 默认不入仓（体积）；哈希钉死在 `sources/*.meta.json`：

```powershell
python scripts/t01/fetch_eval_gold_sources.py --package docs/modules/T01/eval_gold/v1 --pdf
```

## 4. 包级 provenance / actual-gold 门禁

```powershell
python scripts/t01/validate_eval_gold.py --package docs/modules/T01/eval_gold/v1 --write-checksums
python scripts/t01/validate_eval_gold.py --package docs/modules/T01/eval_gold/v1 --require-ready
```

期望：`ready_for_t09_formal_eval=True` 且 `RESULT=ACTUAL_GOLD_OK`。

## 5. 明确排除的 harness fixture

```powershell
# Wave B fixture，不得当作 T09 actual gold：
Get-FileHash docs/modules/T01/evidence_gold_set.json -Algorithm SHA256
```

## 6. 给 T09 交接最小信息

1. 路径：`docs/modules/T01/eval_gold/v1/`
2. `git rev-parse HEAD`
3. `manifest.json` SHA-256（见 `checksums.sha256`）
4. `ready_for_t09_formal_eval` 与 `corpus_inclusion_status`
5. **未自行宣布纳入正式 corpus**；请 T09 校验 provenance，组长确认是否纳入
