# Eval Gold Sources（受控原文工件）

## 规范字节语义（XML）

| 项 | 定义 |
|---|---|
| 来源 | Europe PMC `fullTextXML` HTTP 响应体 |
| 落盘 | `Path.write_bytes`（无换行转换、无 BOM） |
| Git | `docs/modules/T01/eval_gold/v1/sources/*.xml -text` |
| 哈希 | 对冻结文件原始字节 SHA-256 |
| 验收 | `fetch_eval_gold_sources.py` **只读校验**冻结快照，默认不重下 |

重新冻结（维护者）：`python scripts/t01/freeze_eval_gold_sources.py`

## 仓库内提交

| 类型 | 入仓 | 说明 |
|---|---|---|
| `PMC*.xml` | 是 | 冻结快照 |
| `PMC*.meta.json` | 是 | DOI / CC-BY / SHA / 复现 URL |
| `SOURCES_INDEX.json` | 是 | 源索引 |
| `PMC*.pdf` | 默认否 | SHA 钉死；`--pdf --refetch-missing` 按需下载 |

## 许可

各源 Open Access **CC-BY**（见 `*.meta.json` 的 `license` 与 DOI 页）。
