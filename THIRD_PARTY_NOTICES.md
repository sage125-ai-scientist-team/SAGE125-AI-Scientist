# 第三方开源组件声明（THIRD_PARTY_NOTICES）

本文件列出 `frontend_components/sage125_landing/`（首页 Streamlit Custom Component v2：
tsParticles 动态背景 + Magic UI Bento Grid 能力区）在构建产物
（`sage125_landing/frontend/build/`）中实际打包的第三方开源代码及其许可证。

所有资源均在**构建期**通过 `npm install` 拉取到本地 `node_modules/`，并由
`npm run build`（Vite）打包进最终的静态 JS/CSS 产物；**运行期不存在任何 CDN 请求**。

---

## 1. tsParticles（动态粒子背景）

- **用途**：Hero 区"科研知识网络 + 文献节点 + 数据轨迹"动态背景
  （`src/components/ParticlesBackground.tsx`）。
- **来源**：<https://github.com/tsparticles/tsparticles>
- **使用方式**：作为 npm 依赖直接引用，未修改源码。
- **打包的子包**：
  - `@tsparticles/engine` v4.3.2 —— 核心引擎（`tsParticles.load()` 单例 API）
  - `@tsparticles/slim` v4.3.2 —— 精简特性包（`loadSlim`），仅加载本效果所需的
    粒子/连线/交互特性，用于控制打包体积
- **许可证**：MIT License
- **版权**：Copyright (c) 2020 Matteo Bruni

```
MIT License

Copyright (c) 2020 Matteo Bruni

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 2. Magic UI（Bento Grid / Magic Card / Animated Beam / Animated List / Number Ticker / Noise Texture / Glare Hover）

- **用途**：首页「系统能力」玻璃 Bento Grid 能力区四张卡片的结构、磨砂纹理、
  鼠标反光与动效（`src/components/magicui/*.tsx`）。
- **来源**：<https://github.com/magicuidesign/magicui>（`registry/magicui/` 下对应组件）
- **使用方式**：Magic UI 以"复制源码到项目中"的方式分发（非 npm 包），本项目按其
  官方源码手工移植了以下 **7 个免费开源组件**，并做了适配本任务规格的裁剪
  （均为免费版本，未使用 Magic UI Pro/付费模板）：
  - `bento-grid.tsx` —— 简化为纯网格定位容器，背景/边框/阴影/圆角改由
    `CardShell` 的 `.glass-card` 玻璃样式统一提供
  - `magic-card.tsx` —— 去掉 `next-themes` 依赖，仅保留鼠标聚光效果，
    `gradientOpacity` 钳制 ≤ 0.10
  - `animated-beam.tsx` —— 保留路径计算与 `ResizeObserver` 逻辑，
    并增加 `prefers-reduced-motion` 静态降级；用于「可验证研究」
    （科学问题→文献证据→候选假设→可检验预测→研究计划）与「多智能体协同」
    （文献检索→证据核验→假设生成→科学评审→研究计划）两张卡片
  - `animated-list.tsx` —— 增加"鼠标悬停暂停"与 `prefers-reduced-motion` 静态
    降级；用于「可追溯证据」（文献来源/原文片段/定位信息/EvidenceCard/内容
    校验）与「开放与透明」（result.json/evidence_cards.json/validation.json/
    provider_audit.json/checksums.sha256）两张卡片
  - `number-ticker.tsx` —— 保留"仅首次进入视口触发一次"逻辑，增加 `value=null`
    时显示"—"的降级分支（不编造数据）
  - `noise-texture.tsx`（**本轮新增**） —— SVG `feTurbulence` fractal noise，
    `opacity` 钳制 0.025–0.055，`mix-blend-mode: soft-light`，用于每张玻璃卡的
    微细磨砂纹理层
  - `glare-hover.tsx`（**本轮新增**） —— CSS `background-position` 过渡实现的
    线性反光，`glare opacity` 钳制 ≤ 0.10，`duration` 700–1100ms，
    `angle` 105–125deg
- **许可证**：MIT License
- **版权**：Copyright (c) Magic UI

```
MIT License

Copyright (c) Magic UI

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 3. liquid-glass-react（液态玻璃按钮）

- **用途**：Hero 主 CTA「进入研究工作区」与次 CTA「查看代表案例」
  （`src/components/LiquidButton.tsx`）；Bento 能力卡表面的玻璃基底样式
  （`CardShell.tsx` 的 `.glass-card`）在视觉语言上与其保持一致，但卡片本身
  的 `backdrop-filter` 玻璃层由纯 CSS 实现，未额外套用 `liquid-glass-react`
  的 SVG 位移滤镜（避免在信息密度高的卡片上引入过强的折射畸变）。
- **来源**：<https://github.com/rdev/liquid-glass-react>
- **版本**：`liquid-glass-react` 1.1.1
- **使用方式**：作为 npm 依赖直接引用，未修改源码；仅通过公开 props
  （`displacementScale`/`blurAmount`/`saturation`/`aberrationIntensity`/
  `elasticity`/`cornerRadius`）按规格钳制参数（中等磨砂、轻微弹性、
  极低色差、克制 hover 位移）。
- **浏览器降级**：`LiquidButton.tsx` 在渲染前检测 `backdrop-filter` 与
  SVG `feDisplacementMap` 支持情况（`supportsLiquidGlass()`），并额外用
  `LiquidGlassErrorBoundary` 包裹；不支持或运行时抛错时，回退到
  `FallbackGlassButton`（纯 CSS `backdrop-filter` 磨砂 + 边框反光 + hover/
  点击缩放），按钮始终可见、可点击、保留原生 `<button>`/`focus`/`aria-label`。
- **许可证**：MIT License
- **版权**：Copyright (c) Rachit Dev

```
MIT License

Copyright (c) Rachit Dev

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## 4. Fontsource（本地字体包，无运行时 CDN 请求）

- **用途**：Hero/Bento 卡片/统计数字全部文本渲染；`--font-cn`（中文正文/
  标题）与 `--font-latin`（品牌行/数字/状态指标）两个 CSS 变量
  （`src/styles/globals.css`）。
- **来源**：<https://github.com/fontsource/fontsource>
- **打包的子包**：
  - `@fontsource-variable/noto-sans-sc` 5.2.7 —— 中文可变字重字体
    （`Noto Sans SC Variable`）
  - `@fontsource-variable/geist` 5.2.8 —— 英文/数字/品牌可变字重字体
    （`Geist Variable`）
- **使用方式**：`npm install` 时随依赖下载字体二进制文件到本地
  `node_modules/`，`npm run build` 时由 Vite 一并打包进
  `sage125_landing/frontend/build/`（`@import "@fontsource-variable/noto-sans-sc"`
  与 `@import "@fontsource-variable/geist/wght.css"`）；**运行期不发起任何
  Google Fonts / 字体 CDN 网络请求**，字体文件随生产构建产物一起离线加载。
  未向用户输出、复制或分享任何字体文件本体。
- **许可证**：
  - Fontsource 打包脚本本身：MIT License（Copyright (c) Fontsource）
  - Noto Sans SC 字体文件：SIL Open Font License 1.1（Copyright 2014-2021
    Adobe/Google）
  - Geist 字体文件：SIL Open Font License 1.1（Copyright 2023 Vercel）

---

## 5. Streamlit（含 Custom Components v2）

- **用途**：本项目的正式前端框架；`app/ui/streamlit_app.py` 使用
  `st.navigation`/`st.Page`/`st.switch_page`/`st.fragment`/`st.cache_data`/
  `st.cache_resource`/`st.session_state` 等官方 API 组织 26 项既有功能的
  多页导航与状态管理；`frontend_components/sage125_landing/` 通过
  Streamlit **Custom Components v2**（`@streamlit/component-v2-lib`）把
  本轮新增的 React/TypeScript 首页组件（Hero/tsParticles/玻璃 Bento Grid/
  液态玻璃按钮/字体）以本地生产构建（`npm run build` 产物）的形式嵌入正式
  Streamlit 页面，而非另起一套独立网站。
- **来源**：<https://github.com/streamlit/streamlit>
- **许可证**：Apache License 2.0
- **版权**：Copyright Snowflake Inc. / Streamlit Inc.

---

## 6. Docker Compose

- **用途**：`compose.local.yaml` 定义 `sage125-api`（FastAPI）与
  `sage125-ui`（Streamlit）两个服务的本地后台常驻运行；两者均配置
  `restart: unless-stopped`，`sage125-ui` 通过 `depends_on:
  condition: service_healthy` 等待 `sage125-api` 健康检查通过后再启动。
  `start_sage125.bat`/`stop_sage125.bat`/`restart_sage125.bat`/
  `status_sage125.bat`/`open_sage125.bat`/`logs_sage125.bat` 六个脚本
  分别负责后台启动+等待健康+打开浏览器、停止、重启、查看状态、打开浏览器、
  查看日志，脚本执行完毕后自身退出，容器在关闭终端/关闭 Cursor 后仍由
  Docker 引擎在后台持续运行。
- **来源**：<https://github.com/docker/compose>
- **许可证**：Apache License 2.0
- **版权**：Copyright Docker, Inc.

---

## 7. 其余直接运行期依赖

以下依赖同样会被 Vite 打包进最终产物（`build/index-*.js`），均为 MIT 许可证，
未修改源码，随 npm 依赖直接引用：

| 包名 | 版本 | 用途 | 版权 |
| --- | --- | --- | --- |
| `motion` | 12.43.0 | Magic UI 组件的动画驱动（`useMotionValue`/`useSpring` 等） | Copyright (c) 2024 Motion B.V. |
| `clsx` | 2.1.1 | className 条件拼接工具（`cn()` 辅助函数） | Copyright (c) Luke Edwards |
| `tailwind-merge` | 2.6.1 | Tailwind className 合并去冲突 | Copyright (c) Dany Castillo |
| `react` / `react-dom` | 19.1.1 | 组件渲染框架（因 `liquid-glass-react` 要求 peer `react>=19` 而从 18 升级） | Copyright (c) Meta Platforms, Inc. and affiliates |

以上均为标准 MIT License 文本（与上文 tsParticles/Magic UI 条款一致，仅版权人不同），
完整文本可在对应包的 npm 发布页或 GitHub 仓库中查阅，此处不再逐一重复全文。

---

## 8. 明确未使用的库

按任务约束，以下类型的库/项目**未被使用**，不适用于本组件：

- 自制粒子引擎、React Bits、Vanta.js、Three.js、旧版 particles.js、视频/GIF 背景
- Magic UI Pro、付费模板、Aceternity UI，或任何其它粒子/Bento Grid/卡片组件开源实现
- 网络字体 CDN、Google Fonts 运行时请求、版权不明中文字体

---

*最后更新：2026-08-25（CAPTAIN-LOCAL-SAGE125-FIXED-OPEN-SOURCE-UI-RUNTIME-PERFORMANCE-05）。
如后续升级依赖版本或新增/替换开源组件，请同步更新本文件。*
