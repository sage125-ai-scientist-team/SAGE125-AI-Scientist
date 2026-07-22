# SAGE125 AI Scientist · 前端风格说明

> 本文件说明前端（Streamlit 科研发现控制台）的视觉与交互规范，供开发维护参考。
> 这不是参赛材料；系统不自动生成最终参赛 PDF/PPT 或演示视频。

## 视觉基调
- 科学、现代、可信、专业；不是普通白底表单，不是聊天机器人；
- 深蓝/靛蓝/青蓝科学渐变 + 轻量网格与星点（纯 CSS，不加载外部图片/CDN）；
- 不使用 SJTU/Science/AAAS 官方 logo（除非后续获授权）；
- 保持 1366×768 屏幕可演示；克制、不霓虹、不赛博朋克。

## 配色（见 app/ui/theme.py）
- 主蓝 `#2563EB`、科学青 `#06B6D4`、金 `#F59E0B`；
- 12 领域各有专属色（DOMAIN_COLORS）；
- Agent 状态：pending 灰 / running 蓝 / completed 绿 / failed 红 / skipped 琥珀。

## 组件规范（app/ui/components.py）
- 所有进入 `unsafe_allow_html` 的动态文本必须先经 `esc()`（html.escape）转义；
- 可选依赖（streamlit-antd-components / streamlit-extras）不可用时自动降级为原生组件；
- 空状态统一用 `render_empty_state(title, hint)`；
- Mock 数据统一用 `mock_for_testing` 徽标标注，绝不伪装成真实结论。
- 运行进度卡只增加在既有运行状态容器内：青蓝表示运行中、绿色表示完成、红色表示失败；展示阶段、百分比与友好千问型号，不展示密钥、端点或 request_id。

## 页面结构（10 区域）
System Hero · First Run Wizard · Select Scientific Question · Data & RAG Workspace ·
AI Scientist Run Console · Agent Observatory · Evidence Wall · ResearchPlan Studio ·
Human Feedback Bench · ResearchPlan Export Center。

## 图表（app/ui/charts.py）
Agent Timeline / Evidence Distribution / Relevance Histogram / Readiness Radar（规则预览，非实验验证）/
Domain Coverage / Knowledge Graph；统一透明背景，适配暗色控制台。

## 安全红线
- 前端不提供 API Key 输入框，不显示/上传 Key；
- 不展示完整本地绝对路径；
- 不出现 Submission Export Center / 参赛提交包 / 技术方案 PDF / 演示视频脚本等措辞。
