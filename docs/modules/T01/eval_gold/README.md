# T01 Eval Gold（正式评测金标）

## 给 T09 的一句话

当前 `v1` = **provenance 脚手架（STRUCTURE_OK）**，`ready_for_t09_formal_eval=false`。  
正式 actual gold 需按 `CURATION_CHECKLIST.md` 著录真实摘录后，再把就绪位置为 true。

## 给 T09 的边界说明

| 路径 | 用途 | 可否作 T09 actual gold |
|---|---|---|
| `docs/modules/T01/evidence_gold_set.json` | Wave B **harness / provisional fixture** | **否** |
| `docs/modules/T01/eval_gold/v1/` | T09 正式评测用 actual gold 包 | 仅当 `manifest.ready_for_t09_formal_eval=true` |

当前 `v1` 为 **结构与 provenance 脚手架**：已具备 T09 要求的 9 项字段位置与校验脚本；`pairs.json` 在人工附上真实文献摘录与授权前保持为空，**不得**把 harness 金标改口冒充 actual gold。

## 目录

```text
eval_gold/
  README.md                 # 本说明
  INTERFACE.md              # CLI / 数据契约接口文档
  v1/
    manifest.json           # 包级 provenance（T09 9 项）
    pairs.json              # 金标对（actual gold 正文；脚手架为空）
    pair.example.json       # 单条 pair 形状示例（不计入 pairs）
    checksums.sha256        # 包内文件摘要
    REPRODUCE.md            # 可重现获取/校验命令
    CURATION_CHECKLIST.md   # 人工著录清单
```

## 校验

```powershell
python scripts/t01/validate_eval_gold.py --package docs/modules/T01/eval_gold/v1
```

脚手架阶段期望：`ready_for_t09_formal_eval=false`，校验以 **STRUCTURE_OK** 通过；宣称 `actual_gold` 但 pairs 为空或仍含 provisional 时必须失败。

接口细节见同目录 [`INTERFACE.md`](./INTERFACE.md)。
