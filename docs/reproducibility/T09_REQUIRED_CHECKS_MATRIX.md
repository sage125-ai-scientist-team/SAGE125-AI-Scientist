# T09 固定 Required Checks 契约

## 契约目的

本矩阵定义后续 GitHub Actions 使用的稳定 job 名称与最低行为契约。名称一经启用为分支保护 required check，不得为临时绕过而重命名、跳过或设置 `continue-on-error`。

所有 Fork PR 均使用离线 Mock/fixture；不得注入生产密钥、代理凭据或其他私密配置。当前仓库唯一 workflow 是 `.github/workflows/ci.yml`：它在 `push` 与 `pull_request` 时运行名为 `pytest` 的 Windows/Python 3.12 job，并执行 `python -m pytest -q`。该触发会覆盖提交到 `integration/2026-08-10` 的 PR，但 job 名称和能力均不足以承担下列契约。

## 固定 Job 矩阵

| Job 名称 | 目标与命令 | 触发与环境 | 网络/密钥 | 超时、缓存与产物 | Owner | 当前状态与 required 前置条件 |
| --- | --- | --- | --- | --- | --- | --- |
| `lint` | 代码风格与静态规则；计划命令：`ruff check app tests scripts`。 | `pull_request`、`push`；Windows + Python 3.12。 | 禁止网络；无真实密钥。 | 10 分钟；缓存按锁定依赖；上传机器可读报告（如启用）。 | T09，受影响模块 owner 配合。 | 缺失。先固定 Ruff 版本、规则与豁免策略，再启用 required。 |
| `type` | 类型契约；计划命令：`mypy app` 或经批准的 `pyright` 命令。 | `pull_request`、`push`；Windows + Python 3.12。 | 禁止网络；无真实密钥。 | 15 分钟；缓存类型缓存；上传文本/JSON 结果。 | T09，模块 owner 负责类型债务。 | 缺失。需选择一个工具、定义覆盖范围和基线，不可将既有错误静默忽略。 |
| `unit` | 离线单元与 Mock 回归；过渡命令：`python -m pytest -q`。 | `pull_request`、`push`；Windows + Python 3.12。 | `MOCK_LLM=true`；禁止网络及真实密钥。 | 30 分钟；pip 缓存；上传 JUnit XML 和失败日志。 | T09，测试所有者共同维护。 | 部分已有（当前 job `pytest`）。本轮 1 项失败，关闭后才可设为 required。 |
| `integration` | 跨模块离线契约与最小 E2E；计划命令：`python -m pytest -q tests/integration`。 | `pull_request`、`push`；Windows + Python 3.12。 | 仅 Mock/fixture；禁止真实密钥和外网。 | 30 分钟；pip 缓存；上传 JUnit、失败 trace 与最小 artifacts。 | T09；T01–T08 提供稳定接口和 fixture。 | 缺失：`tests/integration/**` 尚不存在。建立目录、测试边界及离线 fixture 后再启用。 |
| `security` | 秘密、依赖和发布边界审计；过渡命令包括 `python scripts/audit_project.py`，后续补充受锁定依赖支持的审计与 SBOM 校验。 | `pull_request`、`push`、发布候选。 | 禁止真实密钥；扫描仅使用仓库内容和受控 fixture。 | 15 分钟；不缓存敏感输出；上传脱敏报告。 | T09，队长负责仓库 Secrets 与发布准入。 | 部分已有脚本/测试；缺少独立 CI job、依赖审计、许可证及 SBOM。上线 required 前需关闭工具链缺口。 |
| `build` | 验证可导入/可编译/可构建；当前最小命令：`python -m compileall -q app`，后续增加可安装性和前端/容器构建（若引入）。 | `pull_request`、`push`；Windows + Python 3.12。 | 默认离线；无真实密钥。 | 20 分钟；pip 缓存；上传构建与导入日志。 | T09；T08 负责部署/前端交付接口。 | 部分已有：本轮 `compileall` 通过。无打包配置、Dockerfile、前端工程或构建产物契约，暂不可作为完整 required。 |

## 通用执行策略

- 工作流触发必须至少覆盖 `pull_request` 到 `integration/2026-08-10` 与同分支 `push`；可以增加路径过滤缩短反馈，但不得让 required check 被路径过滤后消失。
- 统一使用 `actions/setup-python` 的 Python 3.12 与 `python -m pip install -r requirements.txt`；缓存键必须包含解释器版本和依赖清单哈希。
- 所有测试 job 必须设置 `MOCK_LLM=true`，并明确清除/不传入生产凭据；网络测试只能使用已声明的受控 fixture。
- 失败时上传 JUnit、覆盖率（启用后）、诊断日志或 trace；报告应脱敏，不能上传 `.env`、用户文献、索引、缓存或真实 exports。
- required check 启用按依赖排序：先修复全量 pytest 红灯，再建立 `unit`；随后建立 `integration` 与离线 fixture；再引入 `lint`、`type`、`security`、`build` 的固定工具链和报告。

## 当前禁止项

- 不使用 `continue-on-error` 掩盖 required job 失败。
- 不以删除断言、添加无理由 skip、降低覆盖率阈值或重命名 job 的方式取得绿色。
- 不在 Fork PR 中提供生产 API Key、Token、代理凭据或私有数据。
- 不在 T09-A 本阶段修改分支保护规则或创建 workflow；实施将在经过 owner 评审后单独进行。
