# T02 Known Limitations

## External model dependency

真实 LLM 调用依赖外部模型服务、有效凭据、网络可用性、配额与限流策略。本地
mock/offline 回归证明的是工作流、合同、版本和恢复逻辑，不替代外部供应商的
可用性保证。

## Production scale

大规模生产部署需要进一步压力测试，尤其是并发 reviewer callback、长时执行、
大量 artifact/metric、checkpoint 存储增长、进程中断频率和恢复吞吐。

## Bounded projection

Prompt projection 有意丢弃 raw multimodal rows、完整 stdout/stderr 和超出上限
的列表项。消费者需要通过保留的 execution/artifact/provenance ID，在获得授权
时从源系统取回完整证据。

## Environment-dependent skips

冻结全量测试的 37 个 skip 均为已知环境条件：2 个 Windows symlink privilege
探针，以及缺少可选 `questions_125.json`、booklet PDF 或相关本地 fixture。
这些 skip 不由 T02 代码引入，也没有通过修改断言或新增 xfail 隐藏失败。

## Release procedure

这些限制不构成当前 PR 的技术 Ready blocker，但生产发布仍需负责人确认外部
模型、凭据、容量和监控准备度。PR Ready、merge 与部署均不由本 handoff 自动
执行。
