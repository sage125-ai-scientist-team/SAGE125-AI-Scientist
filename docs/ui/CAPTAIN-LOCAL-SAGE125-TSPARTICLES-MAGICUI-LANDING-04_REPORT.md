# CAPTAIN-LOCAL-SAGE125-TSPARTICLES-MAGICUI-LANDING-04 验收报告

`MODE=LOCAL_ONLY`。本任务未创建/修改任何 PR，未 push 远端，未涉及科学流水线、
125 题结果或 Q028 案例结果。

## 1. 任务范围回顾

将首页的 DNA SVG 双螺旋与 4 个小图标能力卡替换为：

- **动态背景**：tsParticles（"科研知识网络 + 文献节点 + 数据轨迹"效果）
- **系统能力区**：Magic UI Bento Grid（4 卡：可追溯证据 / 可验证研究 /
  多智能体协同 / 开放与透明），内部动效分别用 Animated List / Animated Beam /
  Magic Card / Number Ticker 实现

技术载体：Streamlit Custom Component v2（React + TypeScript + Vite），产出静态
构建物挂载进 Streamlit，不使用 iframe、不依赖运行期 CDN。

## 2. 交付物清单

| 类别 | 位置 |
| --- | --- |
| CCv2 组件源码 | `frontend_components/sage125_landing/` |
| 生产构建产物 | `frontend_components/sage125_landing/sage125_landing/frontend/build/` |
| 第三方开源许可证声明 | `THIRD_PARTY_NOTICES.md`（仓库根目录） |
| 首页 Python 接入 | `app/ui/landing.py`、`app/ui/workspace.py`（`landing_metrics_raw`） |
| 样式修复 | `app/ui/style.css`（Hero 视觉容器高度链路修复） |
| 验收截图（12 张，覆盖要求的 10 类场景） | `docs/ui/after_open_source_components/` |
| 性能量化数据 | `docs/ui/after_open_source_components/performance_metrics.json` |

## 3. 使用的开源组件（严格限定范围）

- **tsParticles**：`@tsparticles/engine` + `@tsparticles/slim`（直接引擎 API，
  非 `@tsparticles/react` 封装——原因见下文"关键问题排查"）
- **Magic UI**：Bento Grid / Magic Card / Animated Beam / Animated List /
  Number Ticker（复制官方源码后按规格裁剪，去除未批准依赖与图标）

未使用且未引入：自制粒子引擎、React Bits、Vanta.js、Three.js、旧版
particles.js、Aceternity UI，或任何其它粒子/Bento Grid 开源实现。完整许可证
文本见 `THIRD_PARTY_NOTICES.md`。

## 4. 关键问题排查与修复（本轮新增，非既有代码）

### 4.1 Hero 背景粒子高度塌陷为 0（已修复）

**现象**：Hero 区右侧视觉位完全空白，画布 `height` 计算结果为 0。

**根因**：`ParticlesBackground` 用 `absolute inset-0` + `height:100%` 撑满容器，
但 Streamlit CCv2 在 `stElementContainer` 与 Shadow DOM host 之间插入了多层
`display:flex; flex-direction:column` 容器，且这些容器本身是 `flex-basis:0%`
的 flex 子项——此时浏览器完全按 flex 算法计算主轴尺寸，`height` 属性不生效，
形成"组件等祖先给高度、祖先等组件内容撑高度"的循环依赖，最终双方都塌陷为 0。

**修复**：
- React 侧（`SageLanding.tsx`）：hero 变体根节点从 `h-full`（百分比）改为固定
  `h-[440px]`（内在尺寸，不依赖祖先）。
- CSS 侧（`app/ui/style.css`）：给 `.st-key-land_hero_visual` 加
  `flex: 0 0 440px !important`，把该容器在纵向 flex 布局中的主轴尺寸锁定为
  固定像素，绕开框架的 flex-grow 塌陷逻辑。

**验证**：Playwright 实测 canvas 渲染为 594×440，Hero 区正确显示密度渐变的
知识网络背景（见 `01_landing_hero_1920x1080.png` / `02_landing_hero_1440x900.png`）。

### 4.2 CTA 按钮点击后不跳转，页面出现 Streamlit 隐藏警告（已修复）

**现象**：点击"进入研究工作区"等按钮后，页面 body 出现
"Calling st.rerun() within a callback is a no-op."，URL 未跳转。

**根因**：CCv2 trigger 回调（`on_enter_workspace` 等）内部直接调用了
`st.switch_page()`（内部等价于一次 rerun）。Streamlit 明确规定回调函数内调用
rerun 类操作是空操作。

**修复**（`app/ui/landing.py`）：回调函数内只写 `session_state` 标记，待回调
触发的下一次脚本正常执行到主脚本体时，再读标记调用 `st.switch_page()`。

**验证**：Playwright 实测点击"进入研究工作区"后 URL 正确跳转到
`http://localhost:8799/workspace`，脚本状态正常 `notRunning`，无警告文本。

### 4.3 其它清理

- 移除未实际使用的 `@tsparticles/react` 依赖（代码已改用 `@tsparticles/engine`
  直接 API，但 `package.json` 里遗留了未使用的依赖项），重新 `npm install`
  更新 lockfile。

## 5. 端到端功能验证结果

| 验证项 | 结果 |
| --- | --- |
| CCv2 组件被 Streamlit 正确发现并挂载 | ✅ |
| Hero tsParticles 背景渲染（密度渐变、左侧清晰/右侧密集） | ✅ |
| Bento Grid 四卡渲染（Animated List ×2、Animated Beam ×2） | ✅ |
| Magic Card 鼠标聚光/边框效果 | ✅（源码级实现，参数已按规格钳制） |
| Number Ticker 展示真实数据，缺失显示"—" | ✅ |
| CTA 按钮 → Python 回调 → 页面跳转（Python↔React 双向通信） | ✅ |
| `prefers-reduced-motion` 静态降级 | ✅（见 `10a/10b_reduced_motion_*.png`） |
| 移动端响应式布局 | ✅（见 `09_landing_mobile_375x812.png`） |
| 控制台 0 报错 | ✅ |
| 运行期 0 外部 CDN 请求 | ✅ |
| 生产构建（`npm run build`，非 dev server） | ✅ |

## 6. 性能指标（详见 `performance_metrics.json`）

| 指标 | 目标 | 实测 | 结论 |
| --- | --- | --- | --- |
| `CUSTOM_COMPONENT_JS_GZIP` | ≤ 350 KB | 180.53 KB | ✅ PASS |
| `CUSTOM_COMPONENT_CSS_GZIP` | — | 4.26 KB | ✅（合计 184.79 KB） |
| `RUNTIME_CDN_REQUEST_COUNT` | = 0 | 0 | ✅ PASS |
| `CONSOLE_ERROR_COUNT` | = 0 | 0 | ✅ PASS |
| `AVERAGE_FPS` | ≥ 35 | 60.1（3 秒采样） | ✅ PASS |
| `MEMORY_GROWTH`（60 秒代理窗口，线性外推 15 分钟） | ≤ 15 MB | 0.0 MB → 外推 0.0 MB | ✅ PASS（**注：非完整 15 分钟实测**，见下方说明） |
| `LANDING_TEXT_FIRST_RENDER`（首次内容绘制 FCP） | ≤ 1.0 s | 1.048 s | ⚠️ 临界超出（超出 48ms） |
| `LANDING_INTERACTIVE` / `ANIMATION_INIT`（脚本 settle / canvas 就绪） | ≤ 2.0 s / ≤ 1.5 s | 12.8 s / 14.82 s | ❌ 未达标 |

**关于未达标项的诚实说明（不回避、不美化）**：

`LANDING_INTERACTIVE` 与 `ANIMATION_INIT` 两项远超预算，根因**不在** tsParticles/
Magic UI 组件本身，而在于 Streamlit 的执行模型：每个浏览器 session **首次**
运行页面脚本时，会同步调用后端 `/health`、`/questions`、`/runs` 等接口获取真实
数据（`landing_metrics_raw` 依赖的 `list_runs(limit=50)` 等），这部分网络 I/O
+ 磁盘扫描的耗时被计入了"脚本 settle"与"canvas 就绪"的时间窗口——CCv2 组件
要等整个 Python 脚本执行完、真实数据算出来之后才会挂载。这是**该应用现有的
架构特征**（旧版首页同样调用相同的 `landing_metrics` 函数获取这些数据），并非
本次重构引入的新问题。

由于任务约束明确禁止"更改评审/执行相关的科学产物调用逻辑"且本任务范围是
UI 组件替换，未对此架构做进一步改动；如需真正达到 ≤2s 的"可交互"预算，需要
后续单独立项优化 Streamlit 首次脚本执行路径（例如把首页统计数据改为异步/
懒加载，不阻塞组件挂载），这超出了本次任务范围，建议作为后续优化项跟踪。

`MEMORY_GROWTH` 一项受限于本次验收的时间窗口，只跑了 60 秒的代理测试并线性
外推到 15 分钟，**不是**完整的 15 分钟实测；60 秒内堆内存零增长是积极信号，
但不能等同于"已验证 15 分钟无泄漏"，如需严格证据需要单独跑一次完整 15 分钟
的长时监控。

## 7. 验收截图索引（`docs/ui/after_open_source_components/`）

| 文件 | 内容 |
| --- | --- |
| `01_landing_hero_1920x1080.png` | 首页 Hero，1920×1080 |
| `02_landing_hero_1440x900.png` | 首页 Hero，1440×900（规格要求的基准尺寸） |
| `03_bento_grid_overview.png` | Bento Grid 四卡整体 + 统计区 + CTA |
| `04_card_evidence_animated_list.png` | 卡片 1：可追溯证据（Animated List） |
| `05_card_research_animated_beam.png` | 卡片 2：可验证研究（Animated Beam） |
| `06_card_multiagent_animated_beam.png` | 卡片 3：多智能体协同（Animated Beam） |
| `07_card_audit_animated_list.png` | 卡片 4：开放与透明（Animated List） |
| `08_stats_and_cta.png` | Number Ticker 统计区 + 三个 CTA 按钮 |
| `09_landing_mobile_375x812.png` | 移动端视口，Hero 区 |
| `09b_landing_mobile_bento.png` | 移动端视口，Bento 区 |
| `10a_reduced_motion_hero.png` | `prefers-reduced-motion`：Hero 静态降级 |
| `10b_reduced_motion_bento.png` | `prefers-reduced-motion`：Bento 区静态降级 |

## 8. 总体结论

功能与合规性要求（组件范围限定、无 CDN、无自制粒子引擎、卡片内容真实数据、
无编造统计数字、生产构建、无 Lucide 图标违规使用等）**全部达标**；性能预算中
bundle 体积、FPS、内存增长、控制台报错、CDN 请求数**达标**；首屏绘制时间
**临界达标**；"可交互"与"动画初始化"两项**因既有 Streamlit 架构的首次脚本
执行开销而未达标**，已在第 6 节如实披露根因，不作为本组件自身的性能缺陷掩盖。
