# T05 真实实验执行器、结果分析与可复现实验闭环

## 1. 模块定位

当前交付阶段是 **Wave A / PR-A**。

当前实现范围：

- versioned execution contracts；
- controlled local runner skeleton；
- entrypoint registry；
- workspace isolation；
- dataset copy/checksum；
- bounded stdout/stderr；
- timeout and cleanup；
- artifact/metric/provenance verification；
- `actual_execution` guard。

当前尚未实现：

- 真实旗舰数据适配；
- 正式基线；
- Round 1；
- Round 2；
- T02 pipeline 接入；
- API/UI；
- container backend；
- 网络隔离；
- CPU、memory、GPU enforcement。

本模块当前是进程级受控本地运行器骨架，**不是完整安全沙箱**。它只适合执行仓库维护者明确注册并信任的 Python 脚本，不能隔离恶意代码。

## 2. Owner 范围和依赖关系

T05 owner 路径：

- `app/execution/**`
- `app/contracts/execution.py`
- `tests/execution/**`
- `experiments/flagship/**`
- `docs/modules/T05/**`

任务关系：

- 上游：T02；
- 下游：T02、T07、T08、T09；
- 配对审查：T06。

边界要求：

- 不直接修改 `pipeline.py`；
- 不把 Mock、expected 或 planned 状态当作 actual；
- 不将测试夹具当正式实验；
- 不在 UI 层或报告层伪造执行状态。

## 3. 公共入口

公共数据契约从 `app.contracts.execution` 导入。稳定 runner 入口从 `app.execution` 导入：

- `EntrypointRegistry`
- `LocalProcessRunner`

以下示例仅执行仓库内受控 test fixture，使用临时 managed root，不读取真实数据、不携带生产密钥、不访问网络，也不产生正式科学结论：

```python
from pathlib import Path
from tempfile import TemporaryDirectory

from app.contracts.execution import ExecutionSpec
from app.execution import EntrypointRegistry, LocalProcessRunner


probe = Path("tests/execution/fixtures/probe.py").resolve()
registry = EntrypointRegistry()
registry.register_python(
    "doc-probe",
    probe,
    entrypoint_class="test",
)

with TemporaryDirectory(prefix="t05-doc-") as temporary_root:
    runner = LocalProcessRunner(
        registry=registry,
        managed_root=Path(temporary_root) / "managed",
    )
    spec = ExecutionSpec.model_validate(
        {
            "spec_id": "doc-test-spec",
            "question_id": "DOC-Q001",
            "round_index": 0,
            "mode": "test",
            "entrypoint": "doc-probe",
            "argv": ["noop"],
            "seed": 7,
            "resources": {
                "timeout_seconds": 5.0,
                "max_stdout_bytes": 4096,
                "max_stderr_bytes": 4096,
                "max_artifact_bytes": 65536,
                "network_access": "not_requested",
            },
            "environment": {
                "variables": {},
                "dependency_allowlist": [],
            },
            "cleanup_policy": "delete",
        }
    )
    result = runner.run(spec)

assert result.mode == "test"
assert result.status == "succeeded"
assert result.actual_execution is False
```

调用方只选择 opaque entrypoint ID，不能提供 executable 或脚本路径。示例中的相对仓库路径在运行时解析，不包含宿主机硬编码绝对路径。

## 4. 快速验证

PowerShell：

```powershell
$Python = (Resolve-Path ".\.venv\Scripts\python.exe").Path

& $Python -X utf8 -m pytest -q tests/execution
& $Python -m pytest -q
& $Python -m pip check
```

在代码 Commit `bfb03900d9c5aad535287d070234148f18c6525c` 上、同步 `upstream/integration/2026-08-10` 后的本地结果：

- `tests/execution`：229 passed，2 skipped，0 failed，0 errors；两个 skip 均为 Windows symlink 权限能力探测；
- 全仓：501 passed，2 skipped，0 failed，0 errors；
- `pip check`：No broken requirements found。

这些数字对应上述具体代码 Commit 和本地宿主环境；后续判断必须以 CI 与 PR 最新 HEAD 为准。skip 只表示宿主缺少创建 symlink 的权限，不代表相关能力已在该宿主上通过动态验证。

## 5. 目录结构

- `app/contracts/execution.py`：版本化公共模型、状态约束、真实性信任边界与 legacy 归一化；
- `app/execution/__init__.py`：稳定公共 runner 导出；
- `app/execution/registry.py`：opaque entrypoint 注册与解析；
- `app/execution/security.py`：路径、文件、环境、日志、脱敏与清理控制；
- `app/execution/provenance.py`：受限依赖版本与本地 Git provenance；
- `app/execution/runner.py`：进程生命周期与证据收集；
- `tests/execution/conftest.py`：离线测试 fixtures；
- `tests/execution/fixtures/probe.py`：受控 test entrypoint；
- `tests/execution/fixtures/legacy_execution_metadata.json`：legacy 输入矩阵；
- `tests/execution/test_contracts.py`：契约与序列化测试；
- `tests/execution/test_actual_execution.py`：真实性证明链测试；
- `tests/execution/test_manifests.py`：dataset、artifact、metric 与 provenance 测试；
- `tests/execution/test_runner.py`：命令、进程、输出和 timeout 测试；
- `tests/execution/test_security.py`：路径、环境、并发、脱敏与清理测试。

## 6. 运行生命周期

```text
ExecutionSpec
→ registry resolve
→ policy validation
→ unique workspace
→ dataset staging
→ process spawn
→ bounded log capture
→ timeout/reaping
→ artifact collection
→ metric parsing
→ provenance
→ cleanup
→ ExecutionResult
```

runner 会再次验证已经构造的 `ExecutionSpec`，解析受信 registry 项，创建唯一 workspace，把声明的数据复制并重新校验，在 `shell=False` 下启动注册脚本，同时独立、持续地排空 stdout 和 stderr。进程结束后，只收集声明的 artifact，从经过哈希绑定的 JSON artifact 读取 observed metric，生成受限 dependency/Git fingerprint，最后清理或按策略保留 workspace，并通过内部入口构造 `ExecutionResult`。

`dry_run` 和 `mock` 不启动进程；`test` 可以启动 test entrypoint，但始终不能成为 actual。

## 7. 失败处理

失败状态和稳定错误码不能被解释为成功：

- `rejected`：规范、策略、entrypoint、路径、数据或 capability 在 spawn 前被拒绝；
- `spawn_failed`：受控进程未能启动；
- `nonzero_exit`：进程返回非零状态；
- `timeout`：超过 wall-clock limit，runner 尝试 terminate、kill 和 final wait；
- `artifact_missing`：必需 artifact 不存在；
- `artifact_invalid`：artifact 不是允许的受控普通文件或超限；
- `checksum_mismatch`：artifact 与声明摘要不一致；
- `metric_invalid`：metric artifact、结构、单位、数值、来源或关联无效；
- `provenance_incomplete`：Git provenance 不可用、不完整或不满足 actual 要求；
- `cleanup_failed`：workspace 清理未完成，最终状态为 failed。

此外还可能出现 `invalid_spec`、`policy_rejected`、`capability_unsupported`、`entrypoint_not_allowed`、`path_invalid`、`path_escape`、`symlink_escape`、`dataset_invalid`、`dependency_missing`、`cancelled` 和 `internal_error`。结构化 `ExecutionError` 记录 code、message、stage 与 retryable；错误信息不得携带宿主绝对路径或明文敏感值。

## 8. 安全使用要求

- 只注册可信的仓库脚本；
- caller 不提供 executable、解释器或脚本路径；
- 不运行任意 LLM 生成代码；
- 不传生产密钥；
- 不将 runner 当作 sandbox；
- 不使用它执行未知第三方脚本；
- 不把 unsupported 或 future capability 标为 enforced；
- 不把持久化 JSON 直接恢复为 trusted result；
- 在消费 persisted result 前重新核验 artifact、metric 与 provenance；
- 对实际科学使用另行提供真实数据适配、基线、资源隔离和审查。

## 9. 跨任务交接

- **T02**：显式解析 typed `ExecutionResult`，替换旧 `execution_metadata` truthiness；只有完整、重新核验的证明链才能驱动 actual 分支。
- **T03**：验证 execution evidence、artifact digest、metric source 和 provenance；不能只信状态文本。
- **T06**：通过 `ArtifactManifest` 对接多模态 artifact；需保留 media type、相对路径、摘要、大小和 validation status。
- **T07**：用 `question_id`、`execution_id`、`round_index` 和 `parent_execution_id` 隔离 question/execution，不共享 workspace。
- **T08**：可展示脱敏日志、状态、结构化错误、相对 artifact 信息和 capability state；不可展示宿主路径、密钥或把非 actual 结果包装成正式结果。
- **T09**：把 schema 兼容、证明链、离线复现、skip 能力探测和全仓回归纳入门禁。

本 PR-A 只提供契约与本地 runner 骨架，不修改上述任务实现。

## 10. 回滚

PR-A 合入后的回滚原则：

- revert 最终 Squash Merge commit；
- 不 reset 或 force push integration；
- 不删除其他任务提交；
- 不使用尚不存在的 squash SHA；
- 回滚后 typed execution 尚未接入 pipeline，因此不应影响现有主流程，也不需要执行状态或数据迁移。
