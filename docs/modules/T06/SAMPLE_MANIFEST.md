# T06 SAMPLE_MANIFEST（PR-A）

机器可读清单位于：

`tests/multimodal/fixtures/SAMPLE_MANIFEST.json`

## 数量门槛（T06-A-003 / T06-METRIC-004）

| 类别 | 最少 | 本 PR 提供 |
|------|------|------------|
| PDF 表格/图表（`table`/`chart`） | 3 | 5（3 table + 2 chart） |
| CSV/时序（`timeseries`） | 3 | 3 |

另附非法夹具：`invalid/row_width_mismatch.json`、`invalid/duplicate_headers.json`。

## 声明

全部合法样例为 **synthetic_fixture**，仅用于契约与骨架验证，**不是**真实论文解析结果，不得计入 Wave C 正式准确率。
