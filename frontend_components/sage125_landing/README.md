# sage125_landing

SAGE125 AI Scientist 首页专用的 Streamlit Custom Component v2。

本组件严格基于 Streamlit 官方 `streamlit/component-template`（v2 / React + TypeScript + Vite）结构手工搭建，
用于承载：

- Hero 区域的 tsParticles 动态科研知识网络背景；
- "系统能力" 区域的 Magic UI Bento Grid（可追溯证据 / 可验证研究 / 多智能体协同 / 开放与透明）；
- 首页真实数据的 Number Ticker 展示。

第三方开源组件的许可证与来源见项目根目录的 `THIRD_PARTY_NOTICES.md`。

## 目录结构

```
sage125_landing/
├── pyproject.toml               # 顶层 Python 包配置
├── README.md
└── sage125_landing/
    ├── __init__.py              # Streamlit 侧组件注册与 Python API
    ├── pyproject.toml           # CCv2 组件清单（asset_dir = frontend/build）
    └── frontend/
        ├── package.json
        ├── vite.config.ts
        ├── tsconfig.json
        ├── src/                 # React + TypeScript 源码
        └── build/               # `npm run build` 产物（生产环境唯一依赖）
```

## 开发

```bash
cd sage125_landing/frontend
npm install
npm run dev      # 仅开发阶段使用
```

## 生产构建（正式运行前必须执行一次）

```bash
cd sage125_landing/frontend
npm run build
```

构建产物写入 `frontend/build/`，之后 Streamlit 应用运行时不再需要 Node/npm/Vite dev server，
也不需要访问任何 CDN。

## 从项目根目录以可编辑模式安装

```bash
pip install -e frontend_components/sage125_landing
```
