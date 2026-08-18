# T03 Wave C Schema / 质量门校准报告

> 状态：DRAFT；离线校准、安全回归和接口边界复验已执行，PR-C、最终 HEAD 与远端 CI 待回填。
> 基线：`integration/2026-08-10@20592a0eeb9924d021e3ec75ec28d27e2f971e9f`。
> 范围：T03 owner 路径；不包含 T08 API 接线或生产发布。

## 1. 目的与验收边界

本报告对应 `T03-C-001..003`、`T03-C-007..009`、`T03-METRIC-001..002`
和 FINAL DoD。目标不是追求“全部通过”，而是证明：

1. 12 个代表题的完整产物能被同一套 v1 Schema 与质量门稳定处理；
2. 合法完整输入不会被普遍误阻断；
3. 缺产物、串题、虚构引用、错误执行声明、恶意反馈和并发冲突不会被误放行；
4. 任一 open P0/P1 都使 `validation_status=blocked`；
5. 反馈、决策、修订、gate 和 validation 的审计单链在 SQLite 重启后仍可恢复。

以下状态必须分开记录：

- **契约/夹具校准**：可在离线、无密钥环境复现；
- **actual 代表题抽查**：必须绑定真实输入、产物哈希和当前 commit；
- **live batch**：必须由实际批量运行产出，不能由 fixture、Mock 或单元测试代替。

## 2. 被校准的入口与固定规则

主要入口：

- `app.contracts.validation.ValidationContext`
- `app.quality.gates.build_default_quality_gates()`
- `app.quality.runner.DefaultQualityGateRunner.run(context)`
- `app.validation.implementation.DefaultValidationService.validate(context)`
- `app.validation.metrics.ValidationMetricsCollector`
- `app.validation.audit.ValidationAuditWriter`

默认 gate 顺序由 `build_default_quality_gates()` 决定，gate ID 必须非空且唯一。单个
gate 抛异常时，runner 必须生成 `GATE_EXECUTION_ERROR` 阻断结果并继续运行其他 gate；
runner 无结果、重复 gate ID 或内部失败均不得被解释为通过。

固定 fail-closed 规则：

- `ValidationContext` 同时绑定 ResearchPlan、EvidenceCards、AgentTrace、
  `execution_metadata` 和 `question_item`；
- `research_plan.actual_execution` 与
  `execution_metadata.actual_execution` 必须为布尔值且一致；
- actual 执行必须有完整、可信、非 Mock 的运行证明；
- 计划引用必须能在 EvidenceCards 中解析；
- run/question/version/问题文本不一致时拒绝构造或阻断；
- 下一版本含 accepted feedback 时必须有可核验的 feedback receipt、prompt fingerprint、
  diff hash 和 applied instructions；
- 任一 open P0/P1 revision issue 或 gate finding 都阻断 report。

## 3. 12 个代表题校准计划（T03-METRIC-002）

机器可读 manifest `docs/modules/T03/wave_c/calibration_manifest.json` 是题目与预期的
事实来源；脚本 `docs/modules/T03/wave_c/run_calibration.py` 对每题各运行一个完整正例和
一个指定负例，共 12 题/24 case。原始结果和 metrics 是最终执行事实来源；本表只作人工
审阅索引。manifest 明确标记 `dataset_mode=contract_fixture`、
`production_pipeline_connected=false`，题目文字不是源题册内容。
题号、域和主题固定来自 T01 `domain_audit_12.json`（base blob
`7a1beceb523ec0a946c896d4e148de7707c277ef`）；该来源自身明确
`not_live_pipeline_traces=true`。因此本结果证明跨域契约校准，不证明 12 题 actual 执行。

| 题目 | 域 / 指定负向变异 | 数据等级 | 负例预期 | 正/负例实际 | 证据 |
| --- | --- | --- | --- | --- | --- |
| Q001 | mathematics / `missing_evidence_cards` | contract fixture | `blocked` | passed / blocked | raw results：`Q001-*` |
| Q012 | physics / `missing_agent_trace` | contract fixture | `blocked` | passed / blocked | raw results：`Q012-*` |
| Q018 | chemistry / `fabricated_reference` | contract fixture | `blocked` | passed / blocked | raw results：`Q018-*` |
| Q024 | biology / `missing_dataset_target` | contract fixture | `blocked` | passed / blocked | raw results：`Q024-*` |
| Q028 | medicine / `fabricated_metric` | contract fixture（非 actual Q028） | `blocked` | passed / blocked | raw results：`Q028-*` |
| Q035 | earth_science / `forbidden_model` | contract fixture | `blocked` | passed / blocked | raw results：`Q035-*` |
| Q042 | computer_science / `incomplete_execution_proof` | contract fixture | `blocked` | passed / blocked | raw results：`Q042-*` |
| Q051 | materials / `failed_trace` | contract fixture | `blocked` | passed / blocked | raw results：`Q051-*` |
| Q063 | astronomy / `invalid_prompt_hash` | contract fixture | `blocked` | passed / blocked | raw results：`Q063-*` |
| Q077 | neuroscience / `duplicate_evidence_id` | contract fixture | `blocked` | passed / blocked | raw results：`Q077-*` |
| Q089 | climate / `missing_reference_id` | contract fixture | `blocked` | passed / blocked | raw results：`Q089-*` |
| Q102 | engineering / `open_revision_issue` | contract fixture | `blocked` | passed / blocked | raw results：`Q102-*` |

校准判定：

- **过松**：任何缺关键产物、身份污染、虚构引用、执行真值不可信或 open P0/P1 的案例通过；
- **过严**：合同允许且五类产物完整、一致、无 blocker 的代表案例被无理由阻断；
- **可接受阻断**：稳定 finding code、严重级别、路径和可审计原因都存在；
- **不可接受阻断**：只返回未分类异常、泄漏输入内容或结果不可复现。

最终汇总（不得在原始结果生成前填写）：

| 指标 | 门槛 | 结果 | 状态 |
| --- | ---: | ---: | --- |
| 代表题数量 | 12 actual 代表题 | 12 synthetic contract fixtures | PARTIAL |
| 合法完整输入误阻断数 | 0 个普遍性误阻断 | 0 / 12 | PASS |
| 指定负向样本误放行数 | 0 | 0 / 12 | PASS |
| open P0/P1 误放行数 | 0 | 0（Q102 P1 正确 blocked） | PASS |

## 4. 至少 10 个负向/安全/并发案例（T03-METRIC-001）

事实来源为 `examples/wave_c_attack_case_manifest.json` 和
`examples/wave_c_attack_case_results.json`；可执行测试会校验两者逐项一致。20 个独立案例为：

- 2 个中英文 prompt injection；
- 3 个超长/NUL/双向控制字符输入；
- 5 个必需产物逐项缺失；
- 2 个伪引用/伪 actual execution；
- 3 个跨 run/question/version 污染；
- 3 个幂等、冲突和 12 线程并发重放；
- 2 个阻断审计重试/重启及 SQLite 篡改检测。

结果为 `20 passed / 0 failed`；pytest 另含 1 个机器证据一致性检查，专项输出为
`21 passed`。`T03-METRIC-001=20`，满足 `>=10`。

## 5. 旗舰、Q028 与批量抽查

| 抽查对象 | 当前诚实状态 | 完成条件 |
| --- | --- | --- |
| 旗舰题 / Q028 | T05 actual receipt 已按 SHA-256 绑定；因没有原生 T03 AgentTrace，正确输出 `blocked/draft` | 上游补齐真实五类 T03 输入后再验；不得把构造 envelope 当 actual 全链路 |
| T07 GateResult 边界 | contract fixture 正例通过；缺 EvidenceCards 负例在 aggregate 中保持 blocked | 仅证明冻结对象可直接消费，不证明默认 adapter 已接线 |
| live batch | **未运行** | 由授权运行产生非 Mock、可追溯的原始输出；不得用 fixture 冒充 |

机器记录见 `examples/wave_c_flagship_t07_pairing_results.json`。T05 receipt SHA-256 为
`c780df9f1504f60855faac4226f55dd972ba30631bbb47306727720c5e83cde4`；其 8 个 artifact
均在 receipt 中标记 valid。由于 receipt 本身不是原生 T03 AgentTrace，T03 audit 以
`ACTUAL_EXECUTION_HAS_UNTRUSTED_TRACE` 阻断。这是正确的 fail-closed 结果，而不是通过声明。

当前 `app.batch.completion_gate.run_t03_quality_gates()` 仍动态调用旧的
`app.workflow.quality_gates.run_all_quality_gates`，再通过 `GateResult.from_legacy()`
转换。它尚未直接调用 `DefaultQualityGateRunner` / `DefaultValidationService`，因此不能据此
宣称 T07 与冻结 T03 v1 入口已经完成配对。

## 6. 复现命令与结果记录

建议从仓库根目录运行：

```powershell
.\.venv\Scripts\python.exe docs/modules/T03/wave_c/run_calibration.py --verify-only
.\.venv\Scripts\python.exe docs/modules/T03/wave_c/run_calibration.py `
  --output-dir docs/modules/T03/wave_c
.\.venv\Scripts\python.exe -m pytest -q tests/validation/test_wave_c_calibration.py
.\.venv\Scripts\python.exe -m pytest -q tests/validation/test_wave_c_security_stability.py
.\.venv\Scripts\python.exe -m pytest -q tests/validation/test_wave_c_flagship_t07_pairing.py
.\.venv\Scripts\python.exe -m pytest -q tests/validation
.\.venv\Scripts\python.exe -m pytest -q tests/validation -W error
.\.venv\Scripts\python.exe -m pytest -q tests/batch/test_completion_gate.py
```

```text
校准专项：7 passed
安全/稳定专项：21 passed
Q028/T07 边界专项：4 passed
tests/validation：137 passed
T02/T03 配对 + T07 completion gate + Q028/T07 边界：30 passed
原始输出：docs/modules/T03/wave_c/calibration_raw_results.json
manifest：docs/modules/T03/wave_c/calibration_manifest.json
metrics：docs/modules/T03/wave_c/calibration_metrics.json
语义摘要：fb628528a79078602047f068a10b17a0a9f77e2e7a406b512da19ed0b1bf6303
证据 commit：815b7fee98f45034964f3eb27816358a924340d7
```

任何 `skipped` 必须逐项说明原因；涉及私有数据或 live provider 的跳过不得计入
12 题与至少 10 个负向案例的完成数。

## 7. 当前结论

```text
T03_WAVE_C_CALIBRATION=PASS_OFFLINE_CONTRACT_FIXTURE
T03_METRIC_001=20_PASS
T03_METRIC_002=12_CONTRACT_FIXTURES_ONLY_PARTIAL
Q028_ACTUAL_RECEIPT_AUDIT=FAIL_CLOSED_MISSING_NATIVE_T03_TRACE
LIVE_BATCH_EXECUTED=NO
T07_FROZEN_GATE_RESULT_BOUNDARY=PASS_OFFLINE
T07_DEFAULT_ADAPTER_PAIRED=NO
```

T08 API/部署联调明确不属于本次 Wave C 文档与验收范围。
