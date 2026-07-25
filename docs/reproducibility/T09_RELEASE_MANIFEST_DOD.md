# T09 Release Manifest 与 Definition of Done

## Release manifest 契约

未来发布包必须包含可机器读取的 manifest，至少记录 Git commit、Python/Node 版本、锁定依赖、LICENSE、SBOM、文件 SHA-256、125 题 manifest、API 说明、Qwen/百炼调用凭证清单（仅配置状态和掩码）、actual/planned/mock 状态、测试/评测结果和回滚说明。

manifest 校验必须拒绝 `.env`、API Key、代理凭据、无许可数据、旧 Mock 产物、旧失败 exports、用户上传资料、缓存、索引和本地 PDF。缺少 LICENSE、SBOM、依赖锁或 checksum 时，发布状态必须为 blocked。

## Wave A Definition of Done

- 固定 job 名称 `lint`、`type`、`unit`、`integration`、`security`、`build` 可执行且不忽略失败。
- 所有 Fork PR 在 Mock/fixture 模式下运行，不获得生产密钥，不执行 125 题或真实模型调用。
- `tests/integration/**` fixture 不依赖本地问题清单、PDF、缓存、索引或 `.env`。
- benchmark skeleton 可生成并验证五个 `planned` 消融变体的 JSON/CSV schema，不产生伪造指标。
- 失败 artifact 仅包含脱敏 JUnit、收集信息和日志；不得包含受忽略私有输入。
- 当前 integration 基线 `450551f` 的 `249 passed, 1 failed` 作为红灯事实保留；候选 `f644442` 的 `256 passed` 仅作为尚未合入的前置 shared-change 证据。

## Ready 前置条件

PR #1 与 T09 PR-A 保持 Draft。只有 PR #1 已进入 integration、T09 同步最新 upstream、六项检查与模块/契约/最小 E2E 重跑、P0/P1 关闭、配对审查和 Codex review 完成后，T09 PR-A 才能转 Ready。仅队长可以合并。
