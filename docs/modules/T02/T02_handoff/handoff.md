# T02 Handoff

## 1. 模块目标

T02 提供 Reviewer 驱动真实科研迭代闭环：将结构化评审、执行证据与多模态
证据安全地带入下一轮假设和实验设计，保存可解释版本差异，并在失败、重试或
重复事件下保持版本与 issue lineage 一致。

## 2. 核心入口

冻结公共合同位于 `app/contracts/revision.py`：

- `RevisionContext`：修订轮次、评审反馈与 issue 状态的公共输入边界。
- `ReviewFeedback`：Reviewer 结论、问题、必要修订、评论、风险等级与评分。
- `PlanVersion`：使用 `<run_id>:vN` 的完整、可寻址计划快照。
- `IssueClosure`：issue 从打开到关闭的版本化状态。

工作流侧强化入口位于 `app/workflow/revision_feedback.py`、
`app/workflow/revision_integrity.py`、`app/workflow/revision_recovery.py` 和
`app/workflow/explainable_revision.py`。本次冻结未修改上述公共合同。

## 3. 已完成能力

- Reviewer 的 critical issues、required revisions 与 comments 进入下一轮。
- 消费冻结 `ExecutionResult`，保留执行状态、指标、产物、失败和 provenance。
- 消费 `MultimodalArtifact.to_consumer_summary()` 的安全多模态摘要。
- 通过 allowlist、数量/文本上限和 canonical fingerprint 实现 bounded prompt
  projection，不向 prompt 复制 raw rows 或完整 stdout/stderr。
- 保存 V1→V2 source/parent/generated version、时间戳与 SHA-256 provenance
  lineage。
- 重复 reviewer callback 与 revision event 幂等，不生成重复 `PlanVersion`。
- 中断状态可序列化恢复；timeout、空结果、Agent 失败与 execution 失败记录
  failure reason、retry count、final status，并阻止错误 issue closure。
- 向 T08/UI 提供扁平、自哈希的版本、issue、diff、状态事件与 stop reason
  摘要，无需解析内部计划或恢复对象。

## 4. 测试证据

冻结复核结果：

- Wave C：`25 passed`，`0 failed`，`0 skipped`。
- Workflow：`67 passed`，`0 failed`，`0 skipped`。
- Unit：`796 passed`，`0 failed`，`37 skipped`。
- Integration：`1 passed`，`0 failed`，`0 skipped`。
- 全量：`797 passed`，`0 failed`，`37 skipped`。

详细命令和 skip 说明见 `acceptance_evidence/test_output.txt` 与
`acceptance_evidence/metrics.json`。

## 5. PR

- PR: `#37`
- URL: `https://github.com/sage125-ai-scientist-team/SAGE125-AI-Scientist/pull/37`
- Branch: `t02/c-revision-hardening`
- Audited implementation commit:
  `20195d47c07e483049960cf053663b1a64a36372`

## 6. Known limitations

- 真实 LLM 调用依赖外部模型服务的可用性、凭据和限流策略。
- 大规模生产部署仍需要并发、长时运行、存储增长和恢复吞吐压力测试。

完整限制和非阻断环境 skip 见
`acceptance_evidence/known_limitations.md`。

## 7. 回滚

`20195d47` 的直接父提交为 `5355f555c3883868a8f69eedd4177ac3e0af8fbf`。
若负责人决定只回退 C-004/005/006 实现，应使用可审计的 revert commit，避免
重写共享分支历史：

```text
git switch t02/c-revision-hardening
git pull --ff-only origin t02/c-revision-hardening
git revert 20195d47c07e483049960cf053663b1a64a36372
git push origin t02/c-revision-hardening
```

若冻结文档提交也需移除，应先单独 revert 最新的文档提交，再执行上面的实现
revert。目标代码状态是 `5355f555c3883868a8f69eedd4177ac3e0af8fbf`。
禁止用 `reset --hard` 或 force push 回滚已发布历史。
