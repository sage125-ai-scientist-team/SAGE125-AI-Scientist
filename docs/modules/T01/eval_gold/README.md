# T01 Eval Gold（正式评测金标）

## 给 T09 的一句话

当前 `v1` = **已提交 provenance-complete actual gold（8 pairs）**，`ready_for_t09_formal_eval=true`。  
**未宣布纳入正式 corpus**（`corpus_inclusion_status=NOT_CLAIMED_IN_FORMAL_CORPUS`）；请 T09 校验 provenance，组长确认是否纳入。

交接摘要：[`v1/T09_HANDOFF.md`](./v1/T09_HANDOFF.md)

## 给 T09 的边界说明

| 路径 | 用途 | 可否作 T09 actual gold |
|---|---|---|
| `docs/modules/T01/evidence_gold_set.json` | Wave B **harness / provisional fixture** | **否**（未覆盖） |
| `docs/modules/T01/eval_gold/v1/` | T01 提交的 actual gold 包 | 待 T09 校验 + 组长确认后纳入正式 corpus |

## 目录

```text
eval_gold/
  README.md
  INTERFACE.md
  v1/
    manifest.json
    pairs.json                 # 8 条 CC-BY 真实摘录
    pair.example.json
    checksums.sha256
    REPRODUCE.md
    CURATION_CHECKLIST.md
    T09_HANDOFF.md
    sources/                   # XML 快照 + SHA 索引；PDF 按需下载
```

## 校验

```powershell
python scripts/t01/fetch_eval_gold_sources.py --package docs/modules/T01/eval_gold/v1
python scripts/t01/validate_eval_gold.py --package docs/modules/T01/eval_gold/v1 --require-ready
```

期望：`SOURCE_OK` + `ACTUAL_GOLD_OK`。

接口细节见 [`INTERFACE.md`](./INTERFACE.md)。
