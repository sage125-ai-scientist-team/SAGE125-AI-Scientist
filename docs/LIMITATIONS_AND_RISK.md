# SAGE125 AI Scientist · 局限性与风险

> 本文件描述 **AI Scientist 应用本体** 的能力边界与风险，供研究/演示时如实说明。
> 参赛最终 PDF/PPT 与演示视频不属于本系统功能，由团队人工整理。

## 能力边界
- 系统输出的是**可验证科研假设与研究计划**，不是经过实验验证的科学结论。
- 未执行真实实验时，Results 一律为 pending，不提供任何量化指标数值。
- 不声称“预测到下一次疫情”等确定性结论；仅提供概率性早期预警的研究思路。

## 已知局限
1. **真实百炼联调覆盖**：默认测试为 mock；真实链路需运行 `scripts/smoke_bailian.py` 验证
   （chat / embedding / rerank / deepresearch）。rerank 若走 fallback 会标注
   `TODO_REQUIRES_BAILIAN_API_TEST`。
2. **领域分配**：125 问题的领域来自 PDF 字体+分栏几何抽取；系统已加入连续 ID、领域分布、残句、跨栏标题、重复题及关键语义锚点质量门，但新增 PDF 版本仍建议人工抽检。
3. **批量成本**：真实模式默认关闭 DeepResearch，避免 125 次高成本调用。
4. **ResearchPlan 报告 PDF 中文字体**：不分发字体文件；WeasyPrint 不可用时用 ReportLab 内置
   CID 字体（STSong-Light）兜底；若系统无 CJK 字体，PDF 中文可能显示异常，需自行安装系统字体。
   该 PDF 是**当前运行报告**，不限制页数、不是参赛技术方案 PDF。
5. **真实实验未执行**：数据集/实验/指标均为“待执行”的可复现设计。

## 合规风险控制
- API Key 仅存本地 `.env`，不进入代码/日志/导出/前端（`audit_project.py` 扫描）。
- References 仅来自 EvidenceCards，禁止伪造 DOI/URL/作者。
- DeepResearch 输出仅作调研来源，须经下游核验，不直接作为最终报告。
- 用户反馈仅作修订偏好，不作为事实来源；要求造假/去引用/强行 validated 会被拒绝。

## 未来工作
- 真实百炼小批量联调与成本评估；
- 领域标注的人工校验与半自动纠错；
- 垂直领域数据接入与领域专用评测；
- 真实实验执行与 validated 状态闭环。
- 生产部署前将同步长任务迁移到持久化任务队列；当前本地原型通过进程内回调展示实时进度。
