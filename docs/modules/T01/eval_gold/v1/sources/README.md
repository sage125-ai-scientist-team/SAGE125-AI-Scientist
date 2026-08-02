# Eval Gold Sources（受控原文工件）

## 仓库内提交

| 类型 | 是否入仓 | 说明 |
|---|---|---|
| `PMC*.xml` | 是 | Europe PMC fullTextXML 快照（引文核验权威文本） |
| `PMC*.meta.json` | 是 | DOI / license / SHA-256 / 复现命令 |
| `SOURCES_INDEX.json` | 是 | 源索引 |
| `PMC*.pdf` | **默认否**（体积大） | Publisher PDF；SHA-256 已钉死在 meta；按需下载 |

## 复现 PDF（受控访问）

```powershell
python scripts/t01/fetch_eval_gold_sources.py --package docs/modules/T01/eval_gold/v1 --pdf
```

仅校验已入仓 XML：

```powershell
python scripts/t01/fetch_eval_gold_sources.py --package docs/modules/T01/eval_gold/v1
```

## 许可

各源均为 Open Access **CC-BY**（见对应 `*.meta.json` 的 `license` 字段与 DOI 页面）。摘录入 `pairs.json` 时保留署名与 DOI。
