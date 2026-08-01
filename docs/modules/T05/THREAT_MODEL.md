# T05 Wave A 威胁模型

## 1. 系统边界

```text
caller / LLM JSON                     [不可信]
        ↓
ExecutionSpec                         [结构验证后的请求，仍不可信]
        ↓
registry / policy                     [内部可信配置]
        ↓
workspace / staged data               [受控边界；文件内容仍需验证]
        ↓
local process                         [输出不可信；只允许可信注册脚本]
        ↓
stdout / stderr / files               [不可信]
        ↓
validation / checksum / provenance    [内部控制与本地 provider]
        ↓
ExecutionResult                       [只有内部完整证明链可产生 trusted actual]
        ↓ serialize / reload
persisted JSON                        [重新读取后不可信]
```

信任规则：

- caller 不可信，不能选择 executable、host path 或真实性字段；
- `ExecutionSpec` 通过 schema 后仍只是一项请求，runner 会重新验证；
- registry 和 provenance provider 是 host 内部可信配置，误配置不由 schema 自动修复；
- child process 的 stdout、stderr、exit code 和文件内容不可信；
- filesystem artifact 必须重新检查类型、containment、size 和 checksum；
- runner result 只有通过内部 attestation 和完整证明链时才可信；
- persisted JSON 不携带 attestation，重新读取后必须 fail-closed。

PR-A 的安全目标是缩小可信本地脚本的运行面并保留可审计证据。它不是 hostile-code security boundary。

## 2. 保护资产

- 生产密钥与其他 credential；
- 原始数据和 dataset provenance；
- 仓库文件与 Git worktree；
- managed root 之外的文件；
- 执行真实性与 `actual_execution`；
- metric 的来源、数值和验证状态；
- artifact 完整性、类型、大小与摘要；
- dependency/Git/seed provenance；
- stdout/stderr 的边界、分离和脱敏结果；
- Git SHA、dirty state 与 tracked entrypoint；
- 下游 `RevisionContext` 和所有基于执行状态的决策。

## 3. 威胁矩阵

Severity 表示在相应边界被绕过或误用时的潜在影响，不等同于当前存在未修复的审查 finding。Current control 只陈述 PR-A 已有代码；Residual risk 不得被解释为已实现隔离。

| # | Threat | Entry point | Current control | Residual risk | Severity | Future mitigation | Owner |
|---:|---|---|---|---|---|---|---|
| 1 | 任意 executable | `ExecutionSpec.entrypoint` | caller 只传 opaque ID；registry 绑定解析后的 trusted Python 与 `.py` regular file | trusted host 可能误注册危险脚本；同进程恶意 host code 不在边界内 | P0 | registration policy、code owner review、container backend | T05 |
| 2 | shell injection | `argv` | list-of-strings、NUL 拒绝、`shell=False` | 注册脚本可能自行把 argv 交给 shell | P1 | entrypoint review、container policy、禁止 wrapper | T05 |
| 3 | shell wrapper | registry script | 解释器固定为 `sys.executable`，caller 不能选 shell | trusted `.py` 脚本内部仍可调用 shell | P1 | signed/hashed registry manifest、container profile | T05 |
| 4 | argv 注入 | caller argv | 参数保持独立元素，不做 command string 拼接 | 业务脚本自身参数解析仍可能有语义注入 | P1 | per-entrypoint argv schema | T05 / entrypoint owner |
| 5 | absolute path | spec path fields | contract/runtime 双重拒绝 rooted/drive/UNC 语义 | trusted provider 可返回 host source path，且 host 内部需要访问 source | P1 | provider capability boundary、container mounts | T05 |
| 6 | traversal | relative paths | percent-decode 多轮检查，拒绝 `.`、`..`、空段，runtime containment | 文件系统并发变化形成 TOCTOU | P1 | descriptor-relative APIs/container mounts | T05 |
| 7 | Windows drive/UNC/device/ADS | path fields | PureWindowsPath、drive/root、colon、reserved device name 和尾随字符检查 | Windows namespace 仍有复杂兼容边角 | P1 | Windows 专用 canonicalization test matrix | T05 |
| 8 | symlink escape | dataset/artifact/workspace | lstat、symlink/reparse 拒绝，resolve 前后 containment | 宿主无 symlink 权限时动态攻击测试会 skip；TOCTOU 不能完全消除 | P1 | privileged Windows CI、descriptor-relative handling | T05 / T09 |
| 9 | junction/reparse escape | workspace tree | `Path.is_junction`、file attribute reparse 检查、cleanup no-follow | Python/OS 对新 reparse 类型识别可能不完整 | P1 | Windows Job/container boundary、native handle inspection | T05 |
| 10 | TOCTOU | validation→open/spawn | `O_NOFOLLOW`（可用时）、`O_EXCL`、fstat、inode/device/size 前后复核 | Windows 缺少完整 descriptor-relative primitives；注册脚本在 check 与 spawn 间可变 | P1 | immutable copy/content-addressed entrypoint/container image | T05 |
| 11 | source dataset mutation | resolver/staging | source 前后 SHA/size，复制两级 workspace copy，不把 source 直接暴露给 child | 外部 actor 可持续竞争 source；provider 本身是 trusted host boundary | P1 | immutable dataset store、read-only mount | T05 / data owner |
| 12 | artifact substitution | child filesystem output | spawn 前 destination 不得存在；收集时 regular-file、containment、digest 与再次绑定读取 | child 可在验证窗口内竞态替换；非恶意脚本前提仍必要 | P1 | open-handle artifact capture、container snapshot | T05 |
| 13 | artifact 超限 | artifact file | per-artifact 与 run-total byte cap，streaming hash | 文件稀疏性/文件系统资源消耗不完全覆盖 | P1 | disk quota/container volume quota | T05 |
| 14 | checksum mismatch | artifact/dataset | canonical SHA-256，copy/collect/re-read 比对 | SHA 证明 bytes，不证明科学含义 | P1 | signed manifest、semantic validator | T05 / T03 |
| 15 | metric spoofing | metric artifact | 只从声明、valid、哈希绑定 JSON artifact 解析 finite observed metric | 可信脚本仍可生成科学上错误的数值；runner 不验证实验方法 | P1 | T03 scientific validation、baseline/reproduction gates | T03 / T05 |
| 16 | expected/mock metric 伪装 observed | metric JSON | source 必须精确为 observed；mock/dry_run 禁 observed；失败状态清空 metric | 恶意可信脚本可直接标 observed，需科学复核 | P1 | method-specific validator、independent reproduction | T03 |
| 17 | caller 伪造 actual | JSON/result fields | untrusted validation、`model_copy`、`model_construct` 均 fail-closed；私有 builder 要求 module-private capability；Scheme B 内部重算 | Python private API 仍不是恶意同进程代码边界 | P0 | process/service boundary、signed attestation | T05 |
| 18 | persisted JSON 恢复信任 | deserialize | attestation 不序列化；untrusted reload 全部 truth fields=false | 下游若跳过 adapter/validation 仍可能误用原始 dict | P1 | T02 typed-only consumption、signature/reverification | T02 / T05 |
| 19 | provider 返回恶意 provenance | injected provider | 类型、key、长度、SHA、bool、host-path 与 allowlist 规范化 | trusted provider 可以给出语义上虚假但格式合法的值 | P1 | provider registry、independent Git/dependency verification | T05 |
| 20 | dirty Git 伪装 clean | local Git/provider | local `git status`、tracked entrypoint check、actual 要求 available+clean | injected provider 若被错误信任可撒谎；submodules 被忽略 | P1 | 禁止 production injected Git provider、commit signing policy | T05 / release owner |
| 21 | 环境密钥泄漏 | requested/parent env | child 采用最小环境；registry allowlist；secret/reserved names 拒绝 | 非敏感名称中可能承载未知格式 secret | P0 | value classifier、secret broker、不向 local runner传生产密钥 | T05 |
| 22 | stdout/stderr 密钥泄漏 | child output | explicit/pattern redaction、路径变体 redaction；截断或 reader 异常时 text 置空 | 未知 credential 格式仍可能遗漏 | P0 | centralized secret scanner、structured logging | T05 / T09 |
| 23 | URI secret 泄漏 | `source_uri` | scheme allowlist、userinfo 与 secret query/fragment key 拒绝、多轮 decode | 未知参数名或 path-embedded secret 可能通过 | P1 | opaque dataset IDs、URI policy expansion | T05 / data owner |
| 24 | 无界输出内存消耗 | stdout/stderr | reader 持续 drain，retained bytes capped，记录 total/truncated | child 可产生高 I/O 和系统级 pipe/CPU 压力 | P1 | OS I/O quota/container | T05 |
| 25 | pipe deadlock | child PIPE | stdout/stderr 独立 daemon reader，wait 同时 drain，join/finish 检查 | escaped descendant 持有 pipe handle 可延迟 EOF | P1 | process-tree containment、Job Object/container | T05 |
| 26 | timeout | direct child | wall-clock wait、terminate、grace、kill、final wait，失败显式降级 | OS 不响应 kill 或 descendant 逃逸时不能完整停止 | P1 | Job Object/cgroup/container | T05 |
| 27 | orphan direct child | timeout/error | final `poll/kill/wait`，`process_reaped` 与 alive evidence | OS 极端失败时保留 workspace并报告 not enforced | P1 | native process supervisor | T05 |
| 28 | escaped descendant | registered script | 不声称完整进程树；父进程输出与 cleanup 受控 | descendant 可脱离、持有文件/网络/pipe | P0 | Windows Job Object、process group/cgroup、container | T05 PR-B/C |
| 29 | cleanup 删除错误目录 | cleanup target | target 必须是 managed root 的非根后代；no-follow recursion；拒绝 mount | filesystem 并发与未知 reparse 类型仍有 residual | P0 | descriptor-relative deletion、container volume | T05 |
| 30 | cleanup failure 被吞 | finalization | catch 后 status=`failed`、code=`cleanup_failed`；actual 被清零 | workspace 残留仍可能包含数据 | P1 | quarantine/retention policy、operator cleanup | T05 / operations |
| 31 | 并发 workspace 碰撞 | multiple `run` | `mkdtemp` 唯一 workspace；artifact state per-run | managed root 共享磁盘仍会竞争容量 | P1 | quota/scheduler | T05 / T07 |
| 32 | Windows 文件句柄导致清理失败 | open child/artifact handle | 先确认 direct child、关闭 pipes，再 cleanup；失败显式报告 | descendant 或外部进程可持有 handle | P1 | Job Object/container、retry/quarantine | T05 |
| 33 | network access | child process | 无网络隔离；capability 明确为 `future_container_backend` | trusted script可访问宿主允许的网络 | P0 | container network namespace/deny-by-default | T05 PR-C |
| 34 | CPU/memory/GPU 滥用 | child process | 请求可记录；CPU/memory=`not_enforced`，GPU=`unsupported` | child 可耗尽宿主资源 | P0 | cgroup/Job Object/container quotas | T05 PR-C |
| 35 | read-only filesystem 缺失 | child filesystem | workspace containment只约束 runner 操作，不限制 child OS 权限 | child 可按宿主权限访问仓库或其他路径 | P0 | read-only mounts、low-privilege container/user | T05 PR-C |
| 36 | malicious-code execution | registered script | 使用要求明确只允许可信仓库脚本 | 本地进程不是恶意代码 sandbox | P0 | audited container backend；仍不执行任意 LLM code | T05 |
| 37 | registry script 注册后被替换 | registration→spawn | spawn 前重新检查 regular/reparse；actual 必须位于仓库且 Git tracked/clean provenance | recheck 与 spawn 间仍有 TOCTOU；test entrypoint不要求仓库 containment | P1 | content-addressed immutable script copy | T05 |
| 38 | dependency/Git probe 绝对路径泄漏 | provider/subprocess errors | provider output规范化；底层异常不持久化；result error使用通用消息 | platform string 或未来 provider 字段需持续审查 | P1 | centralized persistence scrubber | T05 |
| 39 | seed 仅记录但未实际使用 | spec/environment | seed 在 spec/result/fingerprint 一致性校验 | runner 不证明脚本随机库实际采用 seed | P1 | entrypoint-specific seed injection/echo evidence | T05 / experiment owner |
| 40 | secret redaction 未知格式遗漏 | all persisted text | common patterns、explicit values、encoded path/secret detection | 未知格式、短 secret、分片/变形输出可能漏过 | P0 | structured output allowlist、DLP scanner、禁止生产密钥 | T05 / T09 |

矩阵中的 network、CPU/memory/GPU、read-only filesystem、malicious-code 和 whole-process-tree 风险是明确的未实现能力。PR-A 不能用“local runner”措辞掩盖这些边界。

## 4. Windows 特殊风险

- **WinError 1314**：普通 Windows 用户可能没有创建 symlink 的权限。相关测试以 capability probe 决定 skip；skip 不等于控制通过。
- **junction/reparse**：代码同时检查 `Path.is_junction` 和 reparse attribute；未知 reparse 类型仍需 native/container 边界。
- **drive-relative paths**：`C:relative` 与普通相对路径不同，contract/runtime 均拒绝 drive 语义。
- **UNC/device namespace**：root、UNC、device 和 reserved device name 均被拒绝；未来新增 namespace 需要扩展回归矩阵。
- **ADS**：任一路径 segment 含 colon 即拒绝。
- **reserved device names**：CON、PRN、AUX、NUL、COM/LPT 变体被拒绝，大小写不敏感。
- **case-insensitive paths**：artifact/dataset collision 以 casefold 后的 slash-normalized 路径检查。
- **open handle cleanup**：Windows open handle 可阻止删除；此时必须报告 `cleanup_failed` 或 preserve，不能伪装成功。
- **direct child vs process tree**：当前只管理 `Popen` 直接子进程，不保证 descendant 全部终止。
- **no Job Object**：PR-A 未创建 Windows Job Object，不能声称 process-tree、CPU、memory enforcement。

## 5. 非目标

当前 PR-A 不提供：

- arbitrary untrusted code sandbox；
- network sandbox；
- container isolation；
- seccomp/AppArmor；
- Windows Job Object；
- read-only mount；
- CPU quota；
- memory quota；
- GPU quota；
- full descendant containment；
- production multi-tenant execution。

如果需求依赖上述任一能力，必须拒绝使用 PR-A runner，不能通过 capability 文案把请求改写为“已实现”。

## 6. 开源和官方参考

架构层面仅参考以下公开概念：

- Python `subprocess` 的 argv、PIPE、timeout 与 process lifecycle；
- pytest `tmp_path` 的测试级临时目录隔离；
- Qwen-Agent Docker Code Interpreter 的容器化代码执行边界；
- Sakana AI Scientist v2 的 workspace/timeout 思路。

声明：

- 本 PR-A 未复制外部源码；
- 未引入外部依赖；
- 未采用外部项目许可证代码；
- 当前能力低于完整 container sandbox；
- 只借鉴工作目录、timeout 和隔离边界思想。
