# T05 Wave A 公共执行契约

本文件是 T05 PR-A 的接口控制文档。`app/contracts/execution.py` 是唯一事实源；本文不替代运行时校验器。

## 1. Schema 信息

- `schema_version` 固定为 `"1.0"`。
- 模型基于 Pydantic v2。
- 所有公共 Pydantic 模型继承同一配置：`extra="forbid"`、`frozen=True`、`validate_default=True`、`allow_inf_nan=False`、`hide_input_in_errors=True`、`revalidate_instances="always"`。
- JSON 序列化使用 `model_dump(mode="json")`；普通 `model_validate`、`model_validate_json` 和 `ExecutionResult.model_validate_untrusted` 均属于 untrusted 构造路径。
- timestamp 必须是带时区的 ISO-8601 字符串；naive datetime 字符串无效。
- SHA-256 必须是 64 位小写十六进制；Git SHA 必须是 40 位小写十六进制。
- workspace/dataset/artifact 路径必须是非空相对路径，并拒绝绝对路径、drive/UNC/device 语义、空段、`.`、`..`、ADS、Windows reserved name、危险尾随字符、控制字符和重复 percent-decoding 后的绕过。
- `source_uri` 只接受显式 allowlist scheme，拒绝 userinfo、host path、密钥型 query/fragment 参数与歧义分隔符。
- `workspace_uri` 是 canonical opaque `workspace://...` 标识，不是宿主路径。
- strict bool/int 字段不接受普通 truthiness coercion；所有浮点值必须有限。

## 2. 公共模型

表中的“默认”为空时表示必填。`[]`、`{}` 均由 `default_factory` 为每个实例独立创建。

### 2.1 `ExecutionSpec`

| 字段 | 类型 | 默认 | 校验与语义 |
|---|---|---:|---|
| `schema_version` | `Literal["1.0"]` | `"1.0"` | 版本固定 |
| `spec_id` | `str` | — | 非空，最长 256 |
| `question_id` | `str` | — | 非空，最长 256 |
| `round_index` | strict `int` | — | `>= 0` |
| `parent_execution_id` | `str \| None` | `null` | 非空 ID 或 null |
| `mode` | `ExecutionMode` | — | `actual/dry_run/mock/test` |
| `entrypoint` | `str` | — | opaque ID；非 executable |
| `argv` | `list[str]` | `[]` | 必须是 list；元素是无 NUL 字符串 |
| `datasets` | `list[DatasetManifest]` | `[]` | `dataset_id` 唯一 |
| `required_artifacts` | `list[ArtifactRequirement]` | `[]` | `artifact_id` 唯一 |
| `required_metrics` | `list[MetricRequirement]` | `[]` | metric name 唯一且引用已声明 artifact |
| `seed` | strict `int` | — | `>= 0`；当前只记录，不强制子程序实际使用 |
| `resources` | `ResourceLimitRequest` | — | 资源请求 |
| `environment` | internal environment object | — | `variables: dict[str,str]`、`dependency_allowlist: list[str]`；禁止额外字段 |
| `cleanup_policy` | `delete \| preserve` | — | workspace 收尾策略 |

`environment.variables` 的名称和值必须是字符串，名称非空，值不能含 NUL；最终能否进入子进程还要经过 registry allowlist、secret-name 与 reserved-name 策略。`dependency_allowlist` 必须是无重复 list，并排序存储。

### 2.2 `ExecutionResult`

| 字段 | 类型 | 默认 | 校验与语义 |
|---|---|---:|---|
| `schema_version` | `Literal["1.0"]` | `"1.0"` | 版本固定 |
| `execution_id` | `str` | — | 非空 ID |
| `spec_id` | `str` | — | 非空 ID |
| `question_id` | `str` | — | 非空 ID |
| `round_index` | strict `int` | — | `>= 0` |
| `parent_execution_id` | `str \| None` | `null` | 非空 ID 或 null |
| `mode` | `ExecutionMode` | — | 请求模式 |
| `status` | `ExecutionStatus` | — | 受状态不变量约束 |
| `entrypoint` | `str` | — | opaque ID |
| `entrypoint_class` | `scientific \| test \| None` | `null` | registry 分类 |
| `seed` | strict `int` | — | `>= 0` |
| `started_at` | `str \| None` | `null` | aware ISO-8601 |
| `finished_at` | `str \| None` | `null` | aware ISO-8601；不得早于 started |
| `duration_seconds` | finite `float \| None` | `null` | `>= 0` |
| `process_started` | strict `bool` | — | 是否启动直接子进程 |
| `exit_code` | strict `int \| None` | `null` | 只有已启动进程可携带 |
| `timed_out` | strict `bool` | — | 仅与 `timed_out` status 同时为 true |
| `process_reaped` | strict `bool` | `false` | 只有已启动进程可为 true |
| `process_alive_after_cleanup` | strict `bool` | `false` | 不能与 `process_reaped=true` 并存 |
| `stdout` | `str` | `""` | 已脱敏、可能因截断/reader 异常置空 |
| `stderr` | `str` | `""` | 已脱敏、与 stdout 分离 |
| `stdout_bytes` | strict `int` | `0` | `>= 0`；原始总字节数 |
| `stderr_bytes` | strict `int` | `0` | `>= 0`；原始总字节数 |
| `stdout_truncated` | strict `bool` | `false` | retained cap 标记 |
| `stderr_truncated` | strict `bool` | `false` | retained cap 标记 |
| `workspace_uri` | `str \| None` | `null` | opaque URI，不是 host path |
| `datasets` | `list[DatasetManifest]` | `[]` | ID 唯一 |
| `artifacts` | `list[ArtifactManifest]` | `[]` | ID 唯一；按 ID 排序 |
| `metrics` | `list[MetricRecord]` | `[]` | name 唯一；按 name 排序；关联 artifact/round |
| `cleanup_status` | `CleanupStatus` | — | workspace 收尾结果 |
| `resource_enforcement` | `ResourceLimitEnforcement \| None` | `null` | runner-owned；untrusted payload 只能省略或为 null |
| `environment_fingerprint` | `EnvironmentFingerprint \| None` | `null` | dependency/Git/seed evidence |
| `warnings` | `list[str]` | `[]` | 每项非空且最长 1024 |
| `error` | `ExecutionError \| None` | `null` | 结构化错误 |
| `runner_verified` | strict `bool` | `false` | runner-owned，只读真实性字段 |
| `datasets_validated` | strict `bool` | `false` | runner-owned，只读真实性字段 |
| `artifacts_validated` | strict `bool` | `false` | runner-owned，只读真实性字段 |
| `metrics_validated` | strict `bool` | `false` | runner-owned，只读真实性字段 |
| `provenance_complete` | strict `bool` | `false` | runner-owned，只读真实性字段 |
| `scientific_result_usable` | strict `bool` | `false` | runner-owned，只读真实性字段 |
| `actual_execution` | strict `bool` | `false` | Scheme B 派生值，caller 不可选择 |

普通构造、JSON 反序列化或 untrusted validation 只接受省略或显式为 false 的 runner-owned truth fields；任何非 false claim 会被拒绝。成功构造的 untrusted result 中这些字段全部为 false。字段完整并不等于可信。

### 2.3 `DatasetManifest`

| 字段 | 类型 | 默认 | 校验与语义 |
|---|---|---:|---|
| `schema_version` | `Literal["1.0"]` | `"1.0"` | 固定版本 |
| `dataset_id` | `str` | — | 非空 ID |
| `source_uri` | `str` | — | safe explicit URI；不得含 secret/userinfo/host path |
| `license` | `str` | — | 非空，最长 512 |
| `version` | `str` | — | 非空，最长 512 |
| `sha256` | `str` | — | canonical SHA-256 |
| `size_bytes` | strict `int` | — | `>= 0` |
| `workspace_relative_path` | `str` | — | safe relative path |

### 2.4 `ArtifactRequirement`

| 字段 | 类型 | 默认 | 校验与语义 |
|---|---|---:|---|
| `schema_version` | `Literal["1.0"]` | `"1.0"` | 固定版本 |
| `artifact_id` | `str` | — | 非空 ID |
| `relative_path` | `str` | — | safe relative path |
| `kind` | `ArtifactKind` | — | 允许的 artifact 类别 |
| `media_type` | `str` | — | 非空，最长 256 |
| `required` | strict `bool` | — | 是否必需 |
| `expected_sha256` | `str \| None` | `null` | canonical SHA-256 或 null |
| `max_bytes` | strict `int \| None` | `null` | `> 0` |

### 2.5 `ArtifactManifest`

| 字段 | 类型 | 默认 | 校验与语义 |
|---|---|---:|---|
| `schema_version` | `Literal["1.0"]` | `"1.0"` | 固定版本 |
| `artifact_id` | `str` | — | 非空 ID |
| `relative_path` | `str` | — | safe relative path |
| `kind` | `ArtifactKind` | — | artifact 类别 |
| `media_type` | `str` | — | 非空 |
| `required` | strict `bool` | — | 是否必需 |
| `sha256` | `str \| None` | `null` | canonical SHA-256 或 null |
| `size_bytes` | strict `int \| None` | `null` | `>= 0` |
| `validation_status` | `ArtifactValidationStatus` | — | pending/valid/missing/invalid/checksum_mismatch |
| `collected_at` | `str \| None` | `null` | aware ISO-8601 |

`valid` 必须同时携带 checksum、size 和 collection time；`missing` 不得携带这三项 evidence。

### 2.6 `MetricRequirement`

| 字段 | 类型 | 默认 | 校验与语义 |
|---|---|---:|---|
| `schema_version` | `Literal["1.0"]` | `"1.0"` | 固定版本 |
| `name` | `str` | — | 非空 ID |
| `unit` | `str` | — | 非空，最长 256 |
| `artifact_id` | `str` | — | 引用声明的 artifact |
| `required` | strict `bool` | — | 是否必需 |

### 2.7 `MetricRecord`

| 字段 | 类型 | 默认 | 校验与语义 |
|---|---|---:|---|
| `schema_version` | `Literal["1.0"]` | `"1.0"` | 固定版本 |
| `name` | `str` | — | 非空 ID |
| `value` | finite `float` | — | 不允许 NaN/Infinity/bool |
| `unit` | `str` | — | 非空 |
| `source` | `MetricSource` | — | observed/expected/default/mock/test |
| `artifact_id` | `str` | — | 引用已收集 artifact |
| `validation_status` | `MetricValidationStatus` | — | pending/valid/missing/invalid |
| `round_index` | strict `int` | — | `>= 0` 且匹配 result |

runner 只从已哈希绑定的声明 JSON artifact 接受 `source="observed"` 的 finite metric；不从 stdout/stderr 解析 metric。

### 2.8 `ResourceLimitRequest`

| 字段 | 类型 | 默认 | 校验与语义 |
|---|---|---:|---|
| `schema_version` | `Literal["1.0"]` | `"1.0"` | 固定版本 |
| `timeout_seconds` | finite `float` | `300.0` | `> 0`、`<= 86400` |
| `max_stdout_bytes` | strict `int` | `1048576` | `> 0`、`<= 1073741824` |
| `max_stderr_bytes` | strict `int` | `1048576` | 同上 |
| `max_artifact_bytes` | strict `int` | `104857600` | `> 0`、`<= 1099511627776` |
| `cpu_seconds` | finite `float \| None` | `null` | 请求可记录，`> 0`、`<= 86400`，当前不 enforce |
| `memory_bytes` | strict `int \| None` | `null` | 请求可记录，`> 0`、`<= 1099511627776`，当前不 enforce |
| `network_access` | `NetworkAccess` | `"not_requested"` | 请求记录；当前无网络隔离 |

### 2.9 `ResourceLimitEnforcement`

| 字段 | 类型 | 默认 | 语义 |
|---|---|---:|---|
| `schema_version` | `Literal["1.0"]` | `"1.0"` | 固定版本 |
| `wall_clock` | `CapabilityState` | — | 直接子进程 wall-clock 实际状态 |
| `output_bytes` | `CapabilityState` | — | retained output cap |
| `artifact_bytes` | `CapabilityState` | — | artifact byte cap |
| `cpu` | `CapabilityState` | — | 当前 `not_enforced` |
| `memory` | `CapabilityState` | — | 当前 `not_enforced` |
| `network` | `CapabilityState` | — | 当前 `future_container_backend` |

### 2.10 `EnvironmentFingerprint`

| 字段 | 类型 | 默认 | 校验与语义 |
|---|---|---:|---|
| `schema_version` | `Literal["1.0"]` | `"1.0"` | 固定版本 |
| `python_version` | `str` | — | 非空 |
| `python_implementation` | `str` | — | 非空 |
| `platform` | `str` | — | 非空 |
| `architecture` | `str` | — | 非空 |
| `dependency_versions` | `dict[str,str]` | `{}` | 仅 explicit allowlist；排序；拒绝 host path |
| `git_sha` | `str \| None` | `null` | canonical 40-char SHA |
| `git_dirty` | strict `bool` | — | Git dirty evidence |
| `git_available` | strict `bool` | — | true 时必须有 SHA；false 时 SHA 必须 null 且 dirty=false |
| `seed` | strict `int` | — | `>= 0` 且匹配 result seed |

### 2.11 `ExecutionError`

| 字段 | 类型 | 默认 | 校验与语义 |
|---|---|---:|---|
| `schema_version` | `Literal["1.0"]` | `"1.0"` | 固定版本 |
| `code` | `ExecutionFailureCode` | — | 稳定 failure code |
| `message` | `str` | — | 非空，最长 4096；持久化前脱敏 |
| `stage` | `str` | — | 非空 stage ID |
| `retryable` | strict `bool` | — | 是否建议重试 |

### 2.12 `LegacyExecutionMetadataAdapter`

该类型不是 Pydantic 模型。`normalize(metadata: Mapping[str, object])` 返回冻结、slots-only 的内部 normalization：

| 输出字段 | 类型 | 固定规则 |
|---|---|---|
| `legacy_claim` | `bool \| None` | 只记录可识别 legacy 意图 |
| `canonical_actual_execution` | `bool` | 始终为 `false` |
| `warning` | `str \| None` | missing/null/empty/unverified true 的稳定 warning |
| `error` | `str \| None` | 无效容器或值的稳定 error |

adapter 只做 fail-closed 归一化，不颁发 runner attestation。

## 3. 状态、模式与枚举

### 3.1 合法值

- `ExecutionMode`：`actual`、`dry_run`、`mock`、`test`
- `ExecutionStatus`：`planned`、`rejected`、`running`、`succeeded`、`failed`、`timed_out`、`cancelled`
- `CleanupStatus`：`not_started`、`succeeded`、`failed`、`preserved`
- `CapabilityState`：`enforced`、`not_enforced`、`unsupported`、`future_container_backend`
- `MetricSource`：`observed`、`expected`、`default`、`mock`、`test`
- `DatasetValidationStatus`：`declared`、`validated`、`invalid`
- `ArtifactValidationStatus`：`pending`、`valid`、`missing`、`invalid`、`checksum_mismatch`
- `MetricValidationStatus`：`pending`、`valid`、`missing`、`invalid`
- `ArtifactKind`：`metrics`、`raw`、`report`、`log`、`plot`、`table`、`model`
- `EntrypointClass`：`scientific`、`test`
- `NetworkAccess`：`not_requested`、`allow`、`deny`
- `CleanupPolicy`：`delete`、`preserve`

failure codes：

`invalid_spec`、`policy_rejected`、`capability_unsupported`、`entrypoint_not_allowed`、`path_invalid`、`path_escape`、`symlink_escape`、`dataset_invalid`、`dependency_missing`、`spawn_failed`、`nonzero_exit`、`timeout`、`artifact_missing`、`artifact_invalid`、`checksum_mismatch`、`metric_invalid`、`provenance_incomplete`、`cleanup_failed`、`cancelled`、`internal_error`。

### 3.2 合法状态关系

```text
planned
├─→ rejected        (spawn 前验证/策略拒绝)
├─→ running         (公共契约可表达；当前同步 runner 不持久化中间 result)
├─→ succeeded       (模式相关成功不变量满足)
├─→ failed          (结构化 error)
├─→ timed_out       (started + timeout evidence + timeout error)
└─→ cancelled       (公共状态预留)
```

关键非法组合：

- planned/rejected 携带 process outcome；
- running 没有 started、已有 exit code、timed out 或 finished time；
- succeeded 携带 error、timeout 或非零 exit；
- actual/test 的 succeeded 未启动进程或 exit code 不为 0；
- dry_run/mock 启动进程或携带 observed metric；
- failed 没有 `ExecutionError`；
- timed_out 缺 process start、timeout flag 或 `error.code="timeout"`；
- cleanup failed 却报告 succeeded；
- required artifact 无效却报告 succeeded；
- failed/timed_out 发布 observed metric；
- metric 引用不存在的 artifact，或 metric round 与 result 不一致；
- environment fingerprint seed 与 result seed 不一致。

## 4. `actual_execution` Scheme B

`actual_execution=true` 只能由 runner 内部完整证明链派生，全部条件同时满足：

1. `mode == "actual"`；
2. registry entrypoint class 是 `scientific`；
3. `status == "succeeded"`；
4. process 已启动，`exit_code == 0`，未 timeout；
5. 没有 execution error；
6. 直接子进程已 reaped，cleanup 后未存活；
7. dataset、artifact、metric、provenance 四类 evidence 均由 runner 标记验证完成；
8. cleanup 为 `succeeded` 或显式 `preserved`；
9. environment fingerprint 存在；
10. Git available、SHA 有效且 worktree clean；
11. dataset、artifact、metric 均非空；
12. 每个 artifact 都是 valid；
13. 每个 metric 都是 observed、valid，并引用 valid artifact；
14. `scientific_result_usable` 通过同一组 evidence 校验；
15. 构造发生在 runner 私有 attestation context 内。

`actual_execution`：

- 不是“启动过进程”；
- 不是“exit code=0 就够”；
- 不是“mode=real”；
- 不是“LLM 自报”；
- 不是“JSON 中写 true”；
- 不是“pipeline completed”；
- 不是“Validator passed”。

概念差异：

| 概念 | 含义 |
|---|---|
| `process_started` | 直接子进程曾成功创建 |
| `status` | 生命周期结果分类 |
| `runner_verified` | 完整 actual 证明链已由 runner 内部重算；与 `actual_execution` 同步 |
| `datasets_validated` | 非空声明数据已复制并通过 size/checksum |
| `artifacts_validated` | 非空声明 artifact 全部有效 |
| `metrics_validated` | 非空声明 metric 全部从绑定 artifact 验证 |
| `provenance_complete` | dependency/Git/seed fingerprint 完整，actual 还要求 clean Git |
| `scientific_result_usable` | runner state 具备科学结果所需的完整 evidence |
| `actual_execution` | Scheme B 最终派生布尔值 |

test/mock/dry_run/planned/rejected/failed/timed_out/cancelled 均不能产生 actual。

## 5. JSON 信任边界

- 普通构造属于 untrusted；
- `model_validate` 属于 untrusted；
- `model_validate_json` 属于 untrusted；
- `model_validate_untrusted` 对 accepted payload 采用 untrusted 路径：省略的 truth fields 会保持 false，显式非 false claim 会被拒绝；已有实例也会先转为普通 payload 再验证；
- `_from_runner()` 是私有内部入口，只允许 runner host code 使用，并要求 module-private attestation capability；普通直接调用失败；
- 私有 attestation 不持久化，本文不描述其具体值；
- 序列化后重新加载不能自动恢复 trusted；
- persisted result 后续必须重新核验 artifact、metric 和 provenance；
- `ExecutionResult.model_copy(update=...)` 会重新验证并丢弃既有 attestation；truth/evidence 非 false/null 更新被拒绝；
- `ExecutionResult.model_construct()` 被覆写为 fail-closed：不能创建 runner-owned truth 或 resource enforcement evidence；它仍不替代完整 validation；
- runner 会重新验证 `ExecutionSpec`，下游必须对 result 使用 untrusted validation；
- Python 的私有命名不是针对同进程恶意代码的安全边界。trusted host code 不得替调用方调用私有入口。

## 6. Legacy normalization

禁止 `bool(value)`。完整输入分类如下：

| Legacy 输入 | `legacy_claim` | canonical actual | warning | error |
|---|---:|---:|---|---|
| `True` | true | false | `legacy_unverified_true` | null |
| `False` | false | false | null | null |
| `1`（exact int） | true | false | `legacy_unverified_true` | null |
| `0`（exact int） | false | false | null | null |
| `"true"`（trim/casefold 后） | true | false | `legacy_unverified_true` | null |
| `"false"` | false | false | null | null |
| `"1"` | true | false | `legacy_unverified_true` | null |
| `"0"` | false | false | null | null |
| `""` 或仅空白 | null | false | `legacy_empty` | null |
| `null` | null | false | `legacy_null` | null |
| field missing | null | false | `legacy_missing` | null |
| garbage string | null | false | null | `legacy_actual_execution_invalid` |
| 其他数字 | null | false | null | `legacy_actual_execution_invalid` |
| list value | null | false | null | `legacy_actual_execution_invalid` |
| dict value | null | false | null | `legacy_actual_execution_invalid` |
| metadata 容器不是 Mapping | null | false | null | `legacy_actual_execution_invalid` |
| Mapping 容器访问异常 | 不返回 normalization | 不产生 true | 不适用 | 异常向调用方传播；调用方必须 fail closed |

legacy true 只表示未验证历史声明，仍不能产生 canonical actual=true。

## 7. Capability matrix

状态只使用契约合法值；“best effort/partial”写在说明中，不伪造 Literal。

| Capability | 状态 | 当前实现与限制 |
|---|---|---|
| entrypoint allowlist | `enforced` | opaque ID 解析为 host 注册的 immutable Python registration |
| argv list | `enforced` | list-of-strings、拒绝 NUL；不作 shell 解析 |
| `shell=False` | `enforced` | runner 与本地 Git probes 均使用 argv list |
| trusted absolute interpreter | `enforced` | registry 绑定解析后的 `sys.executable` regular file |
| unique workspace | `enforced` | managed root 下 `mkdtemp`，随机唯一目录 |
| relative paths | `enforced` | contract 与 runtime 双重检查 |
| containment | `enforced` | `Path.relative_to`/resolve 前后复核，不用字符串 prefix |
| symlink/junction/reparse validation | `enforced` | lstat、junction/reparse 检查；宿主无创建权限时动态测试 skip |
| dataset copy | `enforced` | source→input→working copy，copy 前后 size/SHA 复核 |
| environment allowlist | `enforced` | 最小环境；禁止 secret/reserved/interpreter-control names |
| secret redaction | `enforced` | explicit secret、常见格式、编码路径脱敏；未知格式仍是 residual risk |
| stdout/stderr separation | `enforced` | 独立 PIPE 与 reader |
| retained output cap | `enforced` | 持续 drain，只保留各自 byte cap；截断时不持久化 partial text |
| timeout | `enforced` | direct child terminate/grace/kill/final wait；无法 reap 时 per-run wall-clock 降为 `not_enforced` |
| direct child reaping | `enforced` | 明确 final wait 与 result evidence；不是 process-tree guarantee |
| artifact allowlist | `enforced` | 只收集声明路径，spawn 前拒绝已存在 destination |
| artifact size | `enforced` | per-artifact 与 run total cap |
| SHA-256 | `enforced` | streaming hash、descriptor/stat consistency、expected digest |
| metric artifact binding | `enforced` | bounded JSON、duplicate-key/NaN 拒绝、只接受 observed |
| selected dependency fingerprint | `enforced` | 最多 128 个 explicit names，不枚举全部 distributions |
| Git provenance | `enforced` | local-only Git，timeout，actual 要求 clean/tracked entrypoint |
| seed record | `enforced` | spec/result/fingerprint 一致；不证明脚本实际应用 seed |
| CPU | `not_enforced` | 请求可记录，无 quota |
| memory | `not_enforced` | 请求可记录，无 quota |
| GPU | `unsupported` | 无请求或 enforcement 字段 |
| network | `future_container_backend` | `network_access` 仅记录，当前不隔离 |
| read-only filesystem | `not_enforced` | workspace 与宿主权限未挂载只读 |
| whole process tree | `unsupported` | 只保证 direct child best-effort，escaped descendant 可能存活 |
| malicious-code isolation | `unsupported` | 只运行可信脚本，不提供 hostile-code boundary |
| container backend | `future_container_backend` | PR-A 未实现 |

## 8. 由当前模型生成的 JSON 示例

所有代码块均由当前模型实例经 `model_dump(mode="json")` 生成，并在文档提交前后用当前 schema 重新验证。没有示例声称正式 actual。

### 8.1 ExecutionSpec：test mode

<!-- model: ExecutionSpec -->
```json
{
  "argv": [
    "noop"
  ],
  "cleanup_policy": "delete",
  "datasets": [],
  "entrypoint": "doc-probe",
  "environment": {
    "dependency_allowlist": [],
    "variables": {}
  },
  "mode": "test",
  "parent_execution_id": null,
  "question_id": "DOC-Q001",
  "required_artifacts": [],
  "required_metrics": [],
  "resources": {
    "cpu_seconds": null,
    "max_artifact_bytes": 65536,
    "max_stderr_bytes": 4096,
    "max_stdout_bytes": 4096,
    "memory_bytes": null,
    "network_access": "not_requested",
    "schema_version": "1.0",
    "timeout_seconds": 5.0
  },
  "round_index": 0,
  "schema_version": "1.0",
  "seed": 7,
  "spec_id": "doc-test-spec"
}
```

### 8.2 ExecutionSpec：dry_run

<!-- model: ExecutionSpec -->
```json
{
  "argv": [
    "noop"
  ],
  "cleanup_policy": "preserve",
  "datasets": [],
  "entrypoint": "doc-probe",
  "environment": {
    "dependency_allowlist": [],
    "variables": {}
  },
  "mode": "dry_run",
  "parent_execution_id": null,
  "question_id": "DOC-Q001",
  "required_artifacts": [],
  "required_metrics": [],
  "resources": {
    "cpu_seconds": null,
    "max_artifact_bytes": 65536,
    "max_stderr_bytes": 4096,
    "max_stdout_bytes": 4096,
    "memory_bytes": null,
    "network_access": "not_requested",
    "schema_version": "1.0",
    "timeout_seconds": 5.0
  },
  "round_index": 0,
  "schema_version": "1.0",
  "seed": 7,
  "spec_id": "doc-dry-run-spec"
}
```

### 8.3 DatasetManifest

<!-- model: DatasetManifest -->
```json
{
  "dataset_id": "doc-dataset",
  "license": "CC0-1.0",
  "schema_version": "1.0",
  "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
  "size_bytes": 128,
  "source_uri": "fixture://docs/sample.csv",
  "version": "doc-fixture-v1",
  "workspace_relative_path": "datasets/sample.csv"
}
```

### 8.4 ArtifactRequirement

<!-- model: ArtifactRequirement -->
```json
{
  "artifact_id": "doc-metrics",
  "expected_sha256": null,
  "kind": "metrics",
  "max_bytes": 4096,
  "media_type": "application/json",
  "relative_path": "artifacts/metrics.json",
  "required": true,
  "schema_version": "1.0"
}
```

### 8.5 planned / untrusted ExecutionResult

<!-- model: ExecutionResult:untrusted -->
```json
{
  "actual_execution": false,
  "artifacts": [],
  "artifacts_validated": false,
  "cleanup_status": "not_started",
  "datasets": [],
  "datasets_validated": false,
  "duration_seconds": null,
  "entrypoint": "doc-probe",
  "entrypoint_class": "test",
  "environment_fingerprint": null,
  "error": null,
  "execution_id": "doc-execution-planned",
  "exit_code": null,
  "finished_at": null,
  "metrics": [],
  "metrics_validated": false,
  "mode": "test",
  "parent_execution_id": null,
  "process_alive_after_cleanup": false,
  "process_reaped": false,
  "process_started": false,
  "provenance_complete": false,
  "question_id": "DOC-Q001",
  "resource_enforcement": null,
  "round_index": 0,
  "runner_verified": false,
  "schema_version": "1.0",
  "scientific_result_usable": false,
  "seed": 7,
  "spec_id": "doc-test-spec",
  "started_at": null,
  "status": "planned",
  "stderr": "",
  "stderr_bytes": 0,
  "stderr_truncated": false,
  "stdout": "",
  "stdout_bytes": 0,
  "stdout_truncated": false,
  "timed_out": false,
  "warnings": [],
  "workspace_uri": null
}
```

### 8.6 rejected ExecutionResult

<!-- model: ExecutionResult:untrusted -->
```json
{
  "actual_execution": false,
  "artifacts": [],
  "artifacts_validated": false,
  "cleanup_status": "not_started",
  "datasets": [],
  "datasets_validated": false,
  "duration_seconds": null,
  "entrypoint": "doc-probe",
  "entrypoint_class": "test",
  "environment_fingerprint": null,
  "error": {
    "code": "policy_rejected",
    "message": "request rejected by local policy",
    "retryable": false,
    "schema_version": "1.0",
    "stage": "policy"
  },
  "execution_id": "doc-execution-rejected",
  "exit_code": null,
  "finished_at": null,
  "metrics": [],
  "metrics_validated": false,
  "mode": "actual",
  "parent_execution_id": null,
  "process_alive_after_cleanup": false,
  "process_reaped": false,
  "process_started": false,
  "provenance_complete": false,
  "question_id": "DOC-Q001",
  "resource_enforcement": null,
  "round_index": 0,
  "runner_verified": false,
  "schema_version": "1.0",
  "scientific_result_usable": false,
  "seed": 7,
  "spec_id": "doc-test-spec",
  "started_at": null,
  "status": "rejected",
  "stderr": "",
  "stderr_bytes": 0,
  "stderr_truncated": false,
  "stdout": "",
  "stdout_bytes": 0,
  "stdout_truncated": false,
  "timed_out": false,
  "warnings": [],
  "workspace_uri": null
}
```

### 8.7 failed / nonzero ExecutionResult

<!-- model: ExecutionResult:untrusted -->
```json
{
  "actual_execution": false,
  "artifacts": [],
  "artifacts_validated": false,
  "cleanup_status": "succeeded",
  "datasets": [],
  "datasets_validated": false,
  "duration_seconds": null,
  "entrypoint": "doc-probe",
  "entrypoint_class": "test",
  "environment_fingerprint": null,
  "error": {
    "code": "nonzero_exit",
    "message": "registered process exited with a nonzero status",
    "retryable": false,
    "schema_version": "1.0",
    "stage": "process"
  },
  "execution_id": "doc-execution-failed",
  "exit_code": 2,
  "finished_at": null,
  "metrics": [],
  "metrics_validated": false,
  "mode": "test",
  "parent_execution_id": null,
  "process_alive_after_cleanup": false,
  "process_reaped": true,
  "process_started": true,
  "provenance_complete": false,
  "question_id": "DOC-Q001",
  "resource_enforcement": null,
  "round_index": 0,
  "runner_verified": false,
  "schema_version": "1.0",
  "scientific_result_usable": false,
  "seed": 7,
  "spec_id": "doc-test-spec",
  "started_at": null,
  "status": "failed",
  "stderr": "",
  "stderr_bytes": 0,
  "stderr_truncated": false,
  "stdout": "",
  "stdout_bytes": 0,
  "stdout_truncated": false,
  "timed_out": false,
  "warnings": [],
  "workspace_uri": null
}
```

### 8.8 timed_out ExecutionResult

<!-- model: ExecutionResult:untrusted -->
```json
{
  "actual_execution": false,
  "artifacts": [],
  "artifacts_validated": false,
  "cleanup_status": "succeeded",
  "datasets": [],
  "datasets_validated": false,
  "duration_seconds": null,
  "entrypoint": "doc-probe",
  "entrypoint_class": "test",
  "environment_fingerprint": null,
  "error": {
    "code": "timeout",
    "message": "registered process exceeded its wall-clock limit",
    "retryable": true,
    "schema_version": "1.0",
    "stage": "process"
  },
  "execution_id": "doc-execution-timeout",
  "exit_code": -15,
  "finished_at": null,
  "metrics": [],
  "metrics_validated": false,
  "mode": "test",
  "parent_execution_id": null,
  "process_alive_after_cleanup": false,
  "process_reaped": true,
  "process_started": true,
  "provenance_complete": false,
  "question_id": "DOC-Q001",
  "resource_enforcement": null,
  "round_index": 0,
  "runner_verified": false,
  "schema_version": "1.0",
  "scientific_result_usable": false,
  "seed": 7,
  "spec_id": "doc-test-spec",
  "started_at": null,
  "status": "timed_out",
  "stderr": "",
  "stderr_bytes": 0,
  "stderr_truncated": false,
  "stdout": "",
  "stdout_bytes": 0,
  "stdout_truncated": false,
  "timed_out": true,
  "warnings": [],
  "workspace_uri": null
}
```

### 8.9 test-mode succeeded ExecutionResult

<!-- model: ExecutionResult:untrusted -->
```json
{
  "actual_execution": false,
  "artifacts": [],
  "artifacts_validated": false,
  "cleanup_status": "succeeded",
  "datasets": [],
  "datasets_validated": false,
  "duration_seconds": null,
  "entrypoint": "doc-probe",
  "entrypoint_class": "test",
  "environment_fingerprint": null,
  "error": null,
  "execution_id": "doc-execution-test-success",
  "exit_code": 0,
  "finished_at": null,
  "metrics": [],
  "metrics_validated": false,
  "mode": "test",
  "parent_execution_id": null,
  "process_alive_after_cleanup": false,
  "process_reaped": true,
  "process_started": true,
  "provenance_complete": false,
  "question_id": "DOC-Q001",
  "resource_enforcement": null,
  "round_index": 0,
  "runner_verified": false,
  "schema_version": "1.0",
  "scientific_result_usable": false,
  "seed": 7,
  "spec_id": "doc-test-spec",
  "started_at": null,
  "status": "succeeded",
  "stderr": "",
  "stderr_bytes": 0,
  "stderr_truncated": false,
  "stdout": "",
  "stdout_bytes": 0,
  "stdout_truncated": false,
  "timed_out": false,
  "warnings": [],
  "workspace_uri": null
}
```

## 9. 兼容、迁移和回滚

- 当前 pipeline 仍使用旧 `execution_metadata`；
- T02 尚未接入 typed `ExecutionResult`；
- legacy adapter 只做 fail-closed 归一化；
- pipeline truthiness 风险未在 T05 PR-A 修复；
- 下游必须显式迁移，不能把 legacy true 直接映射为 canonical actual；
- 删除字段、改名或改变字段类型属于 breaking change；
- 新增可选字段必须提供兼容默认并增加序列化/迁移测试；
- persisted result 必须重新核验后才能用于执行真实性判断；
- 回滚采用 PR/Squash Merge commit revert，不对 integration 做 reset 或 force push。
