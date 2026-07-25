# T09 质量基线

## 范围与可追溯性

本记录由 T09 在 `t09/a-quality-contract` 分支上建立，用于描述当前集成基线的实际质量状态，而不是发布声明。

- 集成基线：`upstream/integration/2026-08-10`
- 集成提交：`450551f1b7d4dc4a714cf499cd063b8044301f16`（`chore(repo): import audited project baseline`）
- 审计分支：`t09/a-quality-contract`
- 分支初始状态：与集成基线相同；未包含额外提交。
- 运行模式：`MOCK_LLM=true`，未加载或读取 `.env`，未进行真实 API 调用。

历史 `BASELINE_2026-07-22.md` 中的结果仅用于追溯，不是本记录的测试结论。本文件只记录本轮命令的实际输出。

## Python 与依赖环境

| 项目 | 实际值 |
| --- | --- |
| 解释器 | `D:\AI-Projects\SAGE125-AI-Scientist\.venv\Scripts\python.exe` |
| Python | `3.12.10` |
| pytest | `9.0.3` |
| 项目声明 | `requires-python >=3.10,<3.15` |
| CI 当前版本 | Python `3.12` |
| 安装清单 | `requirements.txt`（锁定版本） |

项目根目录没有 `.python-version`、`pytest.ini`、`setup.cfg`、`tox.ini` 或 Python 依赖锁文件。现有虚拟环境可用；本轮没有升级、安装或改写依赖。

## 实际执行的命令

```powershell
$env:MOCK_LLM='true'
.venv\Scripts\python.exe -m pytest --collect-only -q
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m pip check
.venv\Scripts\python.exe -m compileall -q app
```

环境变量在命令结束后移除。所有测试均在离线 Mock 模式下运行；没有运行批量 125 题任务。

## 测试结果

| 检查 | 结果 | 耗时 |
| --- | --- | --- |
| pytest 收集 | 250 项 | 1.17 秒 |
| 全量 pytest | 249 passed、1 failed、0 skipped、0 xfailed、0 xpassed、0 errors | 11.80 秒 |
| `pip check` | `No broken requirements found.` | 已完成 |
| `compileall -q app` | 通过 | 已完成 |

### 未通过项

`tests/test_embedding_error_mapping.py::test_embed_texts_maps_sdk_proxy_error_without_echoing_secret`

- 直接原因：断言要求错误提示包含 `HTTP_PROXY`，实际提示使用 `OUTBOUND_HTTPS_PROXY`。
- 初步分类：接口/测试断言不一致，非网络、凭据或外部服务环境问题。
- 处理原则：本轮不修改产品代码或测试，不增加 skip，不降低断言。
- 质量影响：当前全量 pytest 不是绿色基线，不能将现有单一 CI job 作为稳定 required check。

## 现有测试与质量能力

- 跟踪的测试文件：64 个；测试大致覆盖 API、pipeline、UI、RAG/文档库、安全与配置、导出/运行产物、Qwen/Embedding/DeepResearch。
- 当前没有 `tests/integration/**`；集成测试边界尚未独立命名或组织。
- 条件跳过逻辑存在，主要依赖 `questions_125.json` 或本地 PDF 输入；本轮实际运行未出现 skip。
- 本地工作副本含未跟踪的问题清单等输入，因此本轮没有触发条件跳过；这些输入不在 Git 中。干净 CI 环境预计会跳过约 41 项受问题清单/PDF 门控的测试，不能将本轮 250 项收集结果直接等同于 CI 覆盖范围。
- 未发现 xfail 标记或自定义 pytest marker 配置。
- `scripts/audit_project.py`、`scripts/doctor.py` 和相关测试存在，但尚未成为 CI 独立 job。

## 静态、类型、安全与构建现状

| 能力 | 当前状态 | 本轮结论 |
| --- | --- | --- |
| lint | 缺失 | 未声明 Ruff、Black 或等效工具及配置。 |
| 类型检查 | 缺失 | 未声明 Mypy、Pyright 或等效工具及配置。 |
| 覆盖率 | 缺失 | 未声明 pytest-cov、阈值或报告格式。 |
| 依赖审计 | 缺失 | 未声明 pip-audit 或锁文件审计。 |
| 密钥扫描 | 部分已有 | `scripts/audit_project.py` 有应用级审计，但 CI 没有独立秘密扫描 job。 |
| 构建验证 | 部分已有 | `compileall -q app` 通过；没有打包元数据、Dockerfile、前端构建或安装包验证。 |

## 基线使用规则

1. 任何后续修复必须保留失败用例，先确认期望的代理配置契约，再修改相应实现或断言。
2. CI 不得通过删除断言、隐藏失败、`continue-on-error` 或跳过 job 获得绿色状态。
3. 单元与未来集成测试必须显式使用 Mock 或 fixture，Fork PR 不得获得生产密钥。
4. 全量 pytest 转为 required 之前，必须先将本记录中的失败项关闭并复跑完整基线。

## 候选 Shared Change 验证（未进入 integration）

`f644442 fix(deepresearch): enforce explicit outbound proxy policy` 位于独立 Draft PR #1，尚未合入 `integration/2026-08-10`，不得替代上方 integration 基线。该候选提交的独立离线验证为：256 项收集、256 passed、`pip check` 通过、`compileall -q app` 通过。它将失败断言的代理变量同步为 `OUTBOUND_HTTPS_PROXY`，但 T09 只能在该提交进入 integration 后重新建立绿色基线。
