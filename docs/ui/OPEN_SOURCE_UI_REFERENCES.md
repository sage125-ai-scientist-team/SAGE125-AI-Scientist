# SAGE125 开源 UI 参考（仅信息架构与视觉模式）

本文件记录正式编码前查阅的开源设计参考。只吸收信息架构与克制的视觉模式，
不复制品牌、Logo、完整页面代码、专有插图，也不引入许可证不兼容资产或未使用的大型依赖。

当前正式前端为 Streamlit，因此不安装 shadcn/ui、React 或上述项目的运行时代码。

| 项目 | 官方仓库 | 许可证 | 参考的设计模式 | 不采用的部分 |
|------|----------|--------|----------------|--------------|
| shadcn/ui | https://github.com/shadcn-ui/ui ；文档 https://ui.shadcn.com/blocks | MIT | Dashboard / Sidebar 组合：左侧导航 + 顶栏 + 主内容；折叠为图标；移动端 Sheet/Drawer；Card / Tabs / Progress / Table / Tooltip / Skeleton 的层级与密度 | 不引入 React、Tailwind、shadcn 组件库；不复制 blocks 源码；不做玻璃拟态与营销风仪表盘 |
| Open WebUI | https://github.com/open-webui/open-webui | 专有 / 多层（需保留 Open WebUI 品牌，见 LICENSE） | 工作区左侧导航；知识库与模型配置入口分离；历史记录列表；RAG 来源在详情侧展示 | 不复制任何代码、品牌或 Logo；不做聊天机器人首页；不把知识库做成对话附件流 |
| Dify | https://github.com/langgenius/dify | Dify Open Source License（Apache-2.0 衍生，附加条件） | 工作空间分区；工作流/运行状态；运行日志与可检索 run id；Agent 与 RAG 功能分区；监控与质量信息放在次级页面 | 不复制可视化画布、品牌与专有插图；不引入其前端依赖；不把内部模型变量做成首页卖点 |
| Vane / Perplexica | https://github.com/ItzCrazyKns/Vane （原 Perplexica） | MIT | citation-first：答案与来源并排；来源侧栏/抽屉；原文片段与链接可回跳；来源筛选 | 不复制搜索框品牌体验；不做天气等非科研 widget；不把证据卡做成聊天引用气泡 |
| Streamlit 官方 multipage | https://docs.streamlit.io/develop/concepts/multipage-apps/page-and-navigation | Apache-2.0 | `st.Page` + `st.navigation`；页面函数/文件；`url_path`；`st.session_state` 与 `st.query_params` 保状态；切页不重跑任务 | 不使用默认浅色模板；不把每个页面做成独立无状态脚本；不引入额外 multipage 框架 |
| Lucide | https://github.com/lucide-icons/lucide | ISC | 单一线性图标体系；18–24 px；`stroke` 一致；`currentColor`；按需使用少量路径 | 不打包整套图标字体；不混用 Font Awesome / Emoji；不逐行给表格加图标 |

## 选型结论

- 视觉目标对齐已确认的深蓝黑科学产品图，而不是上述产品的品牌皮肤。
- 因正式入口仍为 Streamlit，用结构化 CSS + 少量内联 SVG（Lucide 风格路径）实现图标，不新增 npm 依赖。
- Open WebUI / Dify 的许可证不允许复制实现，仅作 IA 对照。
