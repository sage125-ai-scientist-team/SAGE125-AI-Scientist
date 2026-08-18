# T03 Wave C：12 题质量门校准

## 结论

这个校准包对 `Q001`、`Q012`、`Q018`、`Q024`、`Q028`、`Q035`、`Q042`、`Q051`、`Q063`、`Q077`、`Q089`、`Q102` 各运行一个完整正向样本和一个关键负向样本，共 24 个 `ValidationContext` 判定。本次记录结果为：

- 正向：12/12 通过，`false_block=0`；
- 负向：12/12 被阻断，`false_pass=0`；
- 预期 finding code 或阻断 issue：0 项不匹配；
- Q028 抽查：完整样本通过，未执行却声称 `accuracy=99%` 的样本以 `RESULTS_INTEGRITY_ERROR` 阻断。

## 证据边界

这些题号是代表性的合同夹具，不是 125 题原文或真实科研结果。题干、证据卡和执行痕迹都是本地构造的 `contract_fixture`。本校准：

- 没有连接 live pipeline 或 production API；
- 没有调用模型、网络或真实数据源；
- 不证明 T07 批量链路、T08 API 或科学执行已完成；
- 耗时只是当前本地 Python 进程观测值，不是服务 SLO。

## 负向覆盖

| 题号 | 负向情形 | 主要阻断证据 |
|---|---|---|
| Q001 | 缺证据卡 | `MISSING_EVIDENCE_CARDS` |
| Q012 | 缺 AgentTrace | `MISSING_AGENT_TRACE` |
| Q018 | 引用不存在证据 | `EVIDENCE_GROUNDING_ERROR` |
| Q024 | dataset 缺 target | `RESEARCH_PLAN_SCHEMA_ERROR` |
| Q028 | 未执行伪造指标 | `RESULTS_INTEGRITY_ERROR` |
| Q035 | 禁用生成模型 | `MODEL_COMPLIANCE_ERROR` |
| Q042 | actual_execution 缺完整证明链 | `EXECUTION_PROOF_INCOMPLETE` |
| Q051 | 执行痕迹失败 | `AGENT_TRACE_NOT_SUCCESSFUL` |
| Q063 | prompt 指纹非法 | `AGENT_TRACE_PROMPT_HASH_INVALID` |
| Q077 | 重复 evidence id | `EVIDENCE_CARD_ID_DUPLICATE` |
| Q089 | reference 缺 id | `REFERENCE_ID_MISSING` |
| Q102 | 未关闭 P1 revision issue | `issue-Q102-open-p1` |

## 复现

在仓库根目录运行：

```powershell
.\.venv\Scripts\python.exe docs\modules\T03\wave_c\run_calibration.py --verify-only
.\.venv\Scripts\python.exe -m pytest -q tests\validation\test_wave_c_calibration.py
```

`--verify-only` 不会改写文件；任一 false-block、false-pass 或预期证据不匹配都会返回非零退出码。需要重新采集本机耗时时，在确认结果后显式运行：

```powershell
.\.venv\Scripts\python.exe docs\modules\T03\wave_c\run_calibration.py --output-dir docs\modules\T03\wave_c
```

## 文件

- `calibration_manifest.json`：冻结题号、合同夹具说明、负向变异和预期证据。
- `calibration_raw_results.json`：24 个样本的 context/report 指纹、状态、finding code 与耗时。
- `calibration_metrics.json`：总体 false-block/false-pass、finding 计数和耗时摘要。
- `run_calibration.py`：可复现 harness，固定 report 时钟并计算排除耗时的语义摘要指纹。
