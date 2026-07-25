# T09 质量工程审计说明

## 审计边界

本审计针对 `upstream/integration/2026-08-10` 的当前工程状态。审计仅读取仓库配置并运行离线 Mock 测试；不读取 `.env`、不调用真实模型或公开文献 API、不运行 125 题批量任务。

T09 的 owner 范围为 `.github/workflows/**`、`tests/integration/**`、`scripts/eval/**`、`docs/reproducibility/**`、依赖清单/锁文件、LICENSE 和 SBOM。本阶段仅在 `docs/reproducibility/**` 新增审计材料；没有修改应用、测试、工作流或依赖。

## CI 与测试盘点

### 当前 GitHub Actions

`.github/workflows/ci.yml` 是唯一 workflow。

- 触发：所有 `push` 与 `pull_request`；因此 PR 到 `integration/2026-08-10` 会触发，但没有专用分支过滤或 required-check 契约。
- 平台：`windows-latest`。
- 解释器：Python 3.12。
- 当前 job：`pytest`。
- 安装：`python -m pip install -r requirements.txt`。
- 执行：`MOCK_LLM=true python -m pytest -q`。
- 缺失：lint、类型检查、独立 unit/integration/security/build job、覆盖率阈值、JUnit、失败日志、覆盖率或构建 artifact 上传。
- 未发现 `continue-on-error`；当前工作流不会显式隐藏测试失败。

### 测试结构

仓库追踪 64 个 Python 测试文件。覆盖范围包括 API、pipeline、Mock 模式、RAG/文档库、UI、导出、调用审计、配置与安全规则。测试中存在以问题清单或本地 PDF 是否存在为条件的 `skipif`/`skip`，但本轮完整运行没有产生 skip。未发现 xfail 配置或 marker 注册。

`tests/integration/**` 不存在，因此现有测试不能被稳定地区分为 unit 与 integration required checks。少数 `scripts` 提供 doctor、项目审计、API/前端 smoke、真实百炼 smoke 和批处理工具；真实 smoke 与 125 题批处理不得放入普通 PR CI。

## 依赖、发布与产物盘点

- Python 要求由 `pyproject.toml` 声明为 `>=3.10,<3.15`；CI 选择 Python 3.12。
- `requirements.txt` 使用固定版本，但不存在 Poetry、uv、PDM、Pipenv 或 Node 锁文件。
- 未发现 `package.json`、Dockerfile、Compose 文件、LICENSE、SBOM、Dependabot、CODEOWNERS、CONTRIBUTING 或根 `AGENTS.md`。
- `.gitignore` 已排除 `.env`、虚拟环境、缓存、索引、用户上传、exports、覆盖率和前端构建目录；这些规则降低误提交风险，但不能替代 CI 秘密扫描或发布包校验。
- 当前未发现 tracked `exports/`、`artifacts/`、`reports/` 或 `results/` 文件；本地则有被 `.gitignore` 排除的 `exports/`、`data/cache/`、`data/index/` 和 `data/processed/` 运行/测试残留。它们未纳入本次提交，但会影响本地测试条件；CI 必须使用临时目录和显式 artifact allowlist，不得依赖这些本地状态。
- 未发现 Ruff、Black、Mypy、Pyright、Bandit、pip-audit 或 pytest-cov 的仓库声明/配置；没有覆盖率阈值。

## 风险分级

### P0

1. 全量 pytest 当前为红色：`test_embed_texts_maps_sdk_proxy_error_without_echoing_secret` 的代理配置变量断言与实际提示不一致。修复前不能把全量 pytest 标记为稳定 required。
2. 缺少 LICENSE 与 SBOM；发布包无法证明许可证边界或组件清单，发布准入应保持阻塞。
3. Fork PR 缺少显式 secret-scanning 与依赖风险检查，不能依赖人工检查替代。
4. 问题清单和 PDF 输入未追踪；干净 CI 预计跳过约 41 个受输入门控的测试，当前测试覆盖不具备可复现的一致性。

### P1

1. CI 只有单一 `pytest` job，缺少固定的 lint/type/unit/integration/security/build 名称及失败产物。
2. `tests/integration/**` 和 `scripts/eval/**` 不存在；跨模块质量、指标、消融与失败诊断没有独立入口。
3. 无类型、lint、覆盖率或构建契约；当前 `compileall` 只能证明语法可编译。
4. 当前 CI 对所有 PR 触发但没有基于 `integration/2026-08-10` 的 required-check 管理证据。

### P2

1. 历史复现记录与本轮实际结果不同，后续文档必须始终标明命令、解释器、输入条件和 commit。
2. 项目结构与团队 V3.0 owner map 存在演进差异；新增共享质量配置前需要队长指定唯一编辑者和受影响模块 owner。
3. 本地 PDF、问题清单与字体会影响部分测试可用性，需要在 clean-room fixture 策略中明确。

## 需要其他 owner 配合的事项

- 各模块 owner：为集成测试提供无网络、无密钥的 fixture、失败路径和稳定接口。
- T01/T04/T06：提供有版本、checksum 和许可边界清晰的 gold set/评测输入。
- T05/T07/T08：提供执行、批处理和交付的可观测 artifacts 与最小 E2E 合同。
- 队长：确认 shared CI 文件的唯一编辑者、分支保护 required check 名称、LICENSE 选择、SBOM 策略与发布准入。

## 下一步：CI skeleton 文件计划

依赖顺序优先于日期：

1. 先由对应 owner 解决或确认全量 pytest 的代理提示断言，再复跑本基线命令。
2. 在队长批准后，由 T09 修改 `.github/workflows/ci.yml` 或新建按固定名称划分的 workflow，并为每个 job 设定超时、Mock 环境和脱敏 artifact。
3. 新建 `tests/integration/**` 与 `scripts/eval/**` 的最小离线骨架；不得把真实 API smoke 或 125 题任务加入 PR CI。
4. 确定 lint/type/security 工具及固定版本后，再把各 job 逐项设为 required。
5. 与队长完成 LICENSE、SBOM、checksum 和 clean-room 发布包验证策略后，再开放 release gate。

## Wave A 依赖顺序

PR #1（`f644442`）是已批准的前置 shared change，仍保持 Draft；其 256 passed 只证明候选分支，不能写成 integration 基线。T09 PR-A 可与 PR #1 并行保持 Draft。PR-A Ready 之前必须先按队长顺序处理 PR #1、同步新的 upstream integration、重跑六项检查与最小 E2E，并关闭 P0/P1；仅队长有合并权限。
