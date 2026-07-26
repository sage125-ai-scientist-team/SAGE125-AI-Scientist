# SAGE125 Cursor PR 审核与受控合并 · 队长运行手册

本手册面向**队长（liuyanbo12）**，说明「PR 审核自动化」配置合并后，Cursor Agent
在本地 Cursor IDE 中如何执行 PR 审核与合并工作流。

配套文件：

| 文件 | 作用 |
|---|---|
| `.cursor/rules/sage125-captain-pr-review.mdc` | Cursor 永久规则：定义触发词、"最新 PR" 的判定、安全约束 |
| `.cursor/BUGBOT.md` | 项目级审核规则：分支策略、任务路径归属、安全、科学真实性、CI/测试完整性、发现格式 |
| `docs/governance/task-owner-map.yaml` | 机器可读的 T01–T09 路径所有权表 |
| `docs/governance/pr-review-policy.yaml` | 机器可读的合并门禁配置 |
| `scripts/captain/review_latest_pr.ps1` | 审核辅助脚本：选 PR、抓元数据、路径检查、Checks/Bugbot 判定、（可选）合并 |
| 本文档 | 运行手册 |

---

## 1. 一次性配置文件说明

以上文件由 `captain/cursor-pr-review-automation` 分支引入，通过 Draft PR 提交到
`integration/2026-08-10`。它们本身**不修改任何业务代码**，只新增治理配置。

合并到 `integration/2026-08-10` 之后，Cursor Agent 在本仓库任意会话中都会自动
读取 `.cursor/rules/sage125-captain-pr-review.mdc`（`alwaysApply: true`），
无需每次手动提示。

---

## 2. "帮我审核最新的PR" 的完整行为

你在 Cursor Agent 中输入：

```
帮我审核最新的PR
```

Agent 将按顺序执行：

1. **选 PR**：在 `sage125-ai-scientist-team/SAGE125-AI-Scientist` 中查找
   `state=open`、`base=integration/2026-08-10`、按 `updatedAt` 降序排序的第一个 PR。
   若无法唯一确定（多个 PR 同分钟更新），Agent 会列出候选并停止，不会猜测。
2. **开场报告**：输出 PR 编号、标题、作者、Draft/Ready、base、head、head SHA、
   更新时间、changed files、additions/deletions、PR URL。
3. **读取上下文**：PR 描述、全部 commit、完整 diff、已有评论/Review、
   GitHub Checks、Bugbot 状态、`AGENTS.md`、`.cursor/BUGBOT.md`、
   `task-owner-map.yaml`、对应任务文档。
4. **隔离检出**：优先使用临时 git worktree 或独立临时目录，不在你当前工作目录
   直接切换到队员分支。
5. **静态 + 语义审核**：按 `.cursor/BUGBOT.md` 的 22 项检查清单逐条核对
   （分支、Draft、路径归属、密钥、科学真实性、Reviewer/反馈闭环、
   125 题隔离、测试真实性等）。
6. **运行验证**：至少 `python -m compileall app scripts tests`，再按任务运行
   对应测试目录（如 `pytest -q tests/rag`）；目录不存在时会如实说明"未运行"，
   不会假装通过。
7. **Bugbot 处理**：
   - 若已有 `Cursor Bugbot` Check → 必须 `success` 才算通过；
     `neutral`/`failure`/`pending`/`cancelled` 都视为阻断。
   - 若尚无该 Check → 评论 `cursor review` 触发，并按
     `pr-review-policy.yaml` 的 `require_bugbot_check`（当前为 `false`）
     决定是否阻断；若账号套餐无法为该 PR 生成 Bugbot Check，会明确标记
     `BUGBOT_NOT_AVAILABLE`，继续完成 Agent 自身的深度审核。
8. **结论分支**：
   - 存在 P0/P1 → 在 PR 提交正式 **Request Changes**，注明文件/行号/风险/
     必须修改内容/验证命令，然后停止（不改代码、不合并）。
   - 无 P0/P1，但存在等待项（Draft/Checks pending/Bugbot 未完成/分支落后/
     讨论未关闭）→ 在 PR 评论写明等待项，停止（不 Approve、不合并）。
   - 全部门禁满足 → 提交 **Approve**，随后执行
     `gh pr merge --squash --match-head-commit <REVIEWED_HEAD_SHA>`，
     合并到 `integration/2026-08-10`，并输出新的 integration commit SHA。
9. **固定输出块**：无论结论如何，最后都会输出
   `PR_NUMBER=` … `ACTION=` … `MERGED=` … 等字段（见规则文件第九节的完整列表）。

**该指令绝不会触碰 `main` 分支**，即使你是仓库管理员。

---

## 3. 如何指定 PR 编号

```
重新审核PR #17
审核PR #23
```

Agent 会直接对该编号执行同样的完整流程（步骤 2–9），不做"最新 PR"的自动选择。
适用场景：队员已按上一轮 Request Changes 修改并 push 后，你想针对性复查。

---

## 4. Request Changes 之后，队员应该怎么做

1. 阅读 PR 中的 Request Changes 评论：每条包含文件、行号、风险、必须修改内容、
   验证命令。
2. 在**自己的任务分支**上修改（Agent **不会**替队员改代码）。
3. 本地运行评论中给出的验证命令，确认通过。
4. `git push` 到原分支（同一个 PR 会自动更新）。
5. 同步一次最新 `integration/2026-08-10`（避免落后）：

```powershell
git fetch upstream --prune
git switch <TASK_BRANCH>
git merge upstream/integration/2026-08-10
git push origin <TASK_BRANCH>
```

6. 回复 PR，附上新的 commit SHA 和本地测试结果。
7. 你（队长）再次输入 `帮我审核最新的PR` 或 `重新审核PR #<编号>`。

---

## 5. Draft / Checks 0 / Bugbot neutral 分别代表什么

| 状态 | 含义 | Agent 行为 |
|---|---|---|
| **Draft** | 作者尚未标记 Ready for review | 可以审核内容，但**绝不合并**；在评论中提示"仍为 Draft" |
| **Checks 0** | GitHub 没有任何 Check 结果（CI 未触发或配置问题） | 视为**未验证**，不是"没有问题"；阻断合并，提示排查 CI 触发条件 |
| **CI pending/queued** | Check 仍在运行 | 阻断合并；提示稍后重试或等待 |
| **CI skipped/cancelled** | Check 被跳过或取消 | 阻断合并；绝不当作通过 |
| **Bugbot neutral/failure/pending/cancelled** | Bugbot 未给出明确通过结论 | 阻断合并（即使 `require_bugbot_check=false`，只要该 Check 存在且非 success，也阻断） |
| **未解决 Review Thread** | 还有讨论没有标记 Resolved | 阻断合并 |
| **分支落后（behind）** | 队员分支落后于当前 `integration/2026-08-10` | 阻断合并；要求队员同步 upstream 后重新推送 |

---

## 6. 什么条件允许自动合并（Ordinary PR → integration）

全部满足才会执行 Approve + Squash Merge：

- 非 Draft；`base=integration/2026-08-10`；
- 无 P0；无 P1；
- 路径所有权检查通过（无越界、无未批准的队长专属/共享路径改动）；
- 无密钥/隐私/大文件污染；
- 无 merge conflict；分支已同步最新 integration；
- 相关本地测试已实际运行并通过；
- `lint/type/unit/integration/security/build` 六类检查中，**已存在**的检查项
  必须全部 success（见第 8 节：当前仅有 `unit`/`pytest` 一类，其余尚未接入，
  按"暂不可用"处理，不算作通过也不算作阻断，直到 T09 补齐）；
- 没有 `skipped`/`neutral`/`cancelled`/`pending`；
- 已有 Review Thread 全部 Resolved；已有 Request Changes 均已实质处理；
- 若 `Cursor Bugbot` Check 存在，必须为 `success`；
- 合并时的 head SHA 与审核开始时完全一致（`scripts/captain/review_latest_pr.ps1`
  会在合并前重新拉取并比对，不一致直接中止）。

---

## 7. 为什么普通 PR 只能进入 integration，不能进 main

- `integration/2026-08-10` 是团队集成分支，用于持续汇总 T01–T09 各任务的成果并
  互相验证兼容性；
- `main` 是最终发布分支，只应包含经过完整发布门禁验证的、集成分支的一次性快照；
- 允许任意任务 PR 直接进 `main` 会导致：未完成集成验证的代码被当作"已发布"，
  且无法在合并前统一做发布级检查（比如完整 E2E、安全扫描、依赖锁文件核验）；
- 因此 `.cursor/rules/sage125-captain-pr-review.mdc` 与
  `pr-review-policy.yaml` 都把 `ordinary_base_branch` 硬编码为
  `integration/2026-08-10`，任何 base 不是它的普通 PR 直接判定为 P1。

---

## 8. 最终 Release PR 如何进入 main

**只有你明确输入：**

```
审核最终发布PR并在全部发布门禁通过后合并到main
```

**Agent 才会**审核 `integration/2026-08-10 → main` 的 Release PR，且必须同时满足：

- `base=main`
- `head=integration/2026-08-10`
- 标题以 `[RELEASE]` 开头

流程与普通 PR 审核基本一致，但合并目标是 `main`，且发布门禁通常应比普通 PR 更严格
（建议：全部 T01–T09 任务 PR 均已合并进 integration、完整回归测试、安全审计、
`scripts/audit_project.py` 通过）。**普通指令"帮我审核最新的PR"永远不会触发这个流程**。

对应脚本调用方式：

```powershell
pwsh scripts/captain/review_latest_pr.ps1 -ReleaseMode -InspectOnly
```

---

## 9. 如何回滚错误的 Squash Merge

1. 找到合并前的 `integration/2026-08-10` commit SHA（Agent 每次合并后都会输出
   "新的 integration commit SHA"，其**上一个** commit 就是合并前状态；也可以
   在 GitHub 的 `integration/2026-08-10` 分支 commit 历史中找到对应的 squash
   commit 及其 parent）。
2. 在中央仓库网页上创建一个新的 **revert PR**（推荐），而不是直接 force push：

```powershell
git fetch origin --prune
git switch integration/2026-08-10
git pull --ff-only origin integration/2026-08-10
git revert -m 1 <SQUASH_MERGE_COMMIT_SHA>
git push origin integration/2026-08-10
```

   > 注：squash merge 产生的是单个 commit（无第二个 parent），所以通常不需要
   > `-m 1`；只有当误合并的是一个真正的 merge commit 时才需要该参数。先用
   > `git log --oneline -1 <SHA>` 确认该 commit 的父提交数。

3. **绝不使用** `git push --force` / `git reset --hard` 后强推来"抹掉"错误合并——
   这会破坏其他人已经拉取的历史，产生不可预期的冲突。Revert 是唯一允许的回滚方式。
4. 如果错误合并已经被其他 PR 基于它继续开发，先与相关队员沟通协调。

---

## 10. 如何关闭自动合并能力（临时禁用）

三种粒度，按需选择：

- **临时口头约束（最快）**：直接告诉 Agent "本次只审核，不要合并"，Agent 会以
  `-InspectOnly` 模式运行，不会调用 `-AllowMerge`。
- **单次强制**：调用脚本时不传 `-AllowMerge`（这是默认行为），脚本本身就不会
  执行任何 `gh pr review` / `gh pr merge`。
- **仓库级永久关闭**：在 `docs/governance/pr-review-policy.yaml` 中把
  `require_no_p0_p1` 等门禁项之外新增一个 `merge_disabled: true`
  标记（如需要，队长可以提交后续 PR 增加此字段并让规则识别它），
  或更简单地：临时把 `.cursor/rules/sage125-captain-pr-review.mdc` 的
  `alwaysApply` 改为 `false`，Agent 就不会再自动进入 PR 审核模式
  （需要走一次新的配置 PR）。

---

## 11. 如何将 require_bugbot_check 从 false 改为 true

前置条件（缺一不可）：

1. 队长的 Cursor Team 套餐已确认可以为**队员的** PR（非队长自己的 PR）生成
   `Cursor Bugbot` GitHub Check —— 在 Cursor Dashboard → Integrations → GitHub
   中确认 Bugbot 已对中央仓库启用，且团队席位覆盖所有队员账号。
2. 连续观察至少 3–5 个真实队员 PR，确认它们都能稳定产生 `Cursor Bugbot` Check
   （而不是长期停留在 `pending` 或完全缺失）。

修改步骤：

1. 编辑 `docs/governance/pr-review-policy.yaml`，把
   `require_bugbot_check: false` 改为 `require_bugbot_check: true`。
2. 提交一个新的 `captain/*` 分支 + PR，走本手册同样的审核流程合并到
   `integration/2026-08-10`。
3. 合并后，之后所有普通 PR 若完全没有 `Cursor Bugbot` Check（而不仅仅是结果不是
   success），也会被视为等待项而阻断合并。

> 无论这个开关是 `true` 还是 `false`，只要 `Cursor Bugbot` Check **已经存在**，
> 其结果不是 `success` 就永远阻断合并——这一点不受此开关影响。

---

## 12. 如何排查 GitHub CLI、Bugbot 或权限问题

| 现象 | 排查步骤 |
|---|---|
| `gh auth status` 显示未登录，或账号不是 `liuyanbo12` | 运行 `gh auth login`，选择 `github.com`，用队长账号完成浏览器授权 |
| `gh repo view sage125-ai-scientist-team/SAGE125-AI-Scientist` 失败 | 确认账号在组织中有访问权限；确认仓库名拼写；检查网络代理 |
| `review_latest_pr.ps1` 报 "未找到符合条件的 Open PR" | 确认该 PR 的 `base` 确实是 `integration/2026-08-10`（普通模式）或满足
  ReleaseMode 的三个条件；确认 PR 状态是 `open` 而不是 `merged`/`closed` |
| Checks 长期为 0 | 检查 `.github/workflows/ci.yml` 的 `on:` 触发条件是否包含
  `pull_request`；确认 workflow 文件本身没有语法错误（GitHub Actions 页面会显示
  "This workflow has a syntax error" 之类提示） |
| `gh api graphql` 查询未解决讨论失败 | 通常是 token scope 不足；确认 `gh auth status` 的 Token scopes 至少包含
  `repo`；必要时 `gh auth refresh -s repo` |
| Bugbot 长期 `pending` 不出结果 | 在 PR 下评论 `cursor review` 手动触发；检查 Cursor Dashboard 的
  GitHub 集成是否针对该仓库启用；确认套餐额度未耗尽 |
| 脚本报 "task-owner-map.yaml 缺失" | 确认当前分支已包含本次治理配置 PR 的内容（`integration/2026-08-10`
  合并后才会有这些文件） |

---

## 附：安全边界重申

- 本工作流永远不会读取、显示或提交真实 `.env`。
- 永远不会打印任何 API Key / Token / 密码 / 私钥的值。
- 永远不会使用 `git push --force`、`git push --force-with-lease`、
  `gh pr merge --admin`。
- 永远不会直接 `git push` 到 `main` 或 `integration/2026-08-10`——所有变更都
  必须经过 `gh pr merge` 合并一个已审核的 PR。
- 普通指令"帮我审核最新的PR"永远不会触及 `main`。
- 任何不确定的合并条件，都按"不允许合并"处理。
