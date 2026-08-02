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
```

## 2. 校验 provenance 结构（脚手架 / 正式包通用）

```powershell
python scripts/t01/validate_eval_gold.py --package docs/modules/T01/eval_gold/v1
```

脚手架期望输出含：`STRUCTURE_OK` 且 `ready_for_t09_formal_eval=false`。

## 3. 重算并核对 SHA-256

```powershell
python scripts/t01/validate_eval_gold.py --package docs/modules/T01/eval_gold/v1 --write-checksums
Get-Content docs/modules/T01/eval_gold/v1/checksums.sha256
```

## 4. 正式评测就绪门禁（仅当实际金标已著录）

```powershell
python scripts/t01/validate_eval_gold.py --package docs/modules/T01/eval_gold/v1 --require-ready
```

仅当 `manifest.ready_for_t09_formal_eval=true` 且全部 pair 满足 non-provisional / non-fixture 时通过。

## 5. 明确排除的 harness 金标

```powershell
# 下列文件是 Wave B fixture，不得作为 T09 actual gold：
Get-FileHash docs/modules/T01/evidence_gold_set.json -Algorithm SHA256
```

## 6. 给 T09 的交接最小信息

提交 PR 评论时附：

1. 路径：`docs/modules/T01/eval_gold/v1/`
2. `git rev-parse HEAD`
3. `manifest.json` 的 SHA-256（见 `checksums.sha256`）
4. `ready_for_t09_formal_eval` 当前布尔值
