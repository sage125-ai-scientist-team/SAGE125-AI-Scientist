# 首页完整修复根因报告

任务：`CAPTAIN-LOCAL-SAGE125-HOMEPAGE-COMPLETE-FIX-09`  
模式：`LOCAL_ONLY`  
START_SHA：`bfac1de2c64801ecc6964147dadcb26e6a4d0730`  
备份：`D:\SAGE125_Local_Backups\homepage_complete_fix_20260825-195701`

本报告对应修改前代码定位与修改后验收。修改前完整 30 次循环截图已无法在不覆盖未提交工作的前提下“先冻结再改”；修改前视觉以既有截图为准（`01_home_before.png`、`02_metrics_before.png`、`docs/ui/final_open_source_stack/04_liquid_buttons.png`）。修改后循环与 DOM 统计见 `docs/ui/homepage_complete_fix_09/`。

## 1. 权威数据源

```
CURRENT_RESULTS_ROOT=D:\SAGE125_Local_Runs\formal_125_release_candidate_zh_paper_20260822-232920
CURRENT_MANIFEST_PATH=D:\SAGE125_Local_Runs\formal_125_release_candidate_zh_paper_20260822-232920\manifest.json
CURRENT_UI_INDEX_PATH=D:\SAGE125-AI-Scientist\data\ui\ui_question_index.json
CURRENT_UI_SUMMARY_PATH=D:\SAGE125-AI-Scientist\data\ui\ui_summary.json
CURRENT_STATS_API=none (首页读 ui_summary，不经独立 stats HTTP)
CURRENT_CATALOG_PATH=D:\SAGE125-AI-Scientist\data\processed\questions_125.json
```

解析顺序：`SAGE125_RESULTS_ROOT` → `data/ui/results_root_pointer.json`。  
指针 `path` 来自该发布候选的显式声明，不是按目录 mtime 猜测。

Catalog 校验：Q001–Q125 连续、唯一题号 125、无缺号、无重复。  
首页、工作区轻量索引、API 配置对象读取同一 `SAGE125_RESULTS_ROOT`。

## 2. 修改前问题与根因

### A/B 统计第二、第四项显示「—」

**字段来源错误（不是 CSS）。**  
旧 `landing_metrics_raw` 用当前会话 `evidence_cards`（首页未选题 → 空）和 `coverage=None`。  
研究计划用「最近 50 次 run」冒充全库，所以第三项看起来像 50。

真实 Schema（不得按理想字段硬猜）：

- EvidenceCard：`id` / `quoted_text` / `url|doi`；`locator` 与 `content_sha256` 在 `reliability_note`
- 研究计划：`problem_statement` + `methods` + `datasets` + `generated_hypotheses[].falsifiable_prediction` + `supporting_evidence_ids`
- 回链：假设 `supporting_evidence_ids`、`references[].id`、`datasets.source[].id`（当前 Schema 存在的计划引用）

### C/D 统计卡与能力卡主题割裂

统计卡与 Bento 曾混用浅色/表单底、图标与不同玻璃参数。文字层若与 `backdrop-filter` 同层会被磨糊。

### E Hero 双层按钮

`ABNORMAL_LINE` 的按钮侧来源：`LiquidButton` + `liquid-glass-react`。  
外层矩形是 wrapper / displacement 容器，内层才是 button。  
DOM：嵌套结构 + Hero SVG filter（`sage125-hero-cta-*`）。

### F 返回首页巨大弧线 / 重复连线 / 残留 Canvas SVG

**主来源（已在 DOM 中定位）：**

```
ABNORMAL_LINE_SOURCE=AnimatedBeam quadratic path + leftover liquid-glass SVG filter + extra tsParticles canvas
ABNORMAL_LINE_COMPONENT=AnimatedBeam (ResearchBeamCard / MultiAgentCard) ; 旧 LiquidButton SVG filter ; 旧手工/重复 Particles
ABNORMAL_LINE_DOM_SELECTOR=svg path (Q 贝塞尔，容器 0 尺寸时坐标落到视口) ; filter[id*="sage125-hero-cta"] ; canvas#sage125-hero-particles
ABNORMAL_LINE_CREATED_BY=getBoundingClientRect 在容器未布局时计算 path；CCv2 重挂载后未 cleanup 的 filter/canvas
ABNORMAL_LINE_INSTANCE_COUNT=修复后 path 越界=0 ; canvas=1 ; hero liquid filter=0
```

当 `containerRef` 宽高 < 8 或节点尚未布局时，Magic UI AnimatedBeam 仍用视口坐标写 `M … Q …`，SVG `position:absolute` 且原先不校验边界，于是画出贯穿整页的巨大弧线。  
`curvature=40` 的评审回流线会把控制点推到卡片外。  
旧 Hero 液态玻璃 SVG filter 在 Streamlit 切页后残留，也会画大弧/折射边。  
重复 `tsParticles` / 双 Custom Component iframe 会留下第二张全页连线 Canvas。

不是用 `overflow:hidden` 遮住，而是：

1. 路径必须落在容器内才渲染；
2. 卸载时 disconnect ResizeObserver、cancel rAF、清空 path；
3. 删除 Hero liquid-glass；
4. 官方 `<Particles id="sage125-hero-particles">` 只挂一次，禁止手工 `tsParticles.load`。

### G/H 切页慢、深蓝空白

首页 `bootstrap()`（健康检查 + 题库 HTTP）挡在 Custom Component 之前。  
`load_or_build_ui_summary` 每次比较 250 个文件 mtime。  
`hide_sidebar`/`show_workspace_shell`/`load_css` 曾每次追加 `<style>`。  
统计与 Hero 若包在同一 fragment 或双组件里，刷新会拆掉 tsParticles。

## 3. 修改后统计（一次计算）

`data/ui/ui_summary.json` schema `sage125-ui-summary-v3`  
digest SHA-256：`825f9701f4e9d80d0e8058f1690afa12230efb3b748260a87abb2aabb8964dde`

| 字段 | 值 |
| --- | --- |
| official_question_count | 125（Catalog 唯一题号，非筛选结果） |
| traceable_evidence_count | 425 |
| traceable_evidence_question_count | 112 |
| invalid_evidence_card_count | 0 |
| research_plan_count | 125（旧 UI「50」来自最近 50 次 run，口径错误） |
| total_supporting_evidence_links | 1093 |
| resolved_supporting_evidence_links | 993 |
| unresolved_supporting_evidence_links | 100 |
| evidence_link_coverage | 90.9 |
| evidence_link_coverage_status | calculated |

未硬编码 125 / 50 / 100% / Evidence 数。覆盖率不得显示 100%。

## 4. 截图索引

目录：`docs/ui/homepage_complete_fix_09/`

- 当前首页：`07_home_first_load.png`
- 统计卡：`03_metrics_after.png` / `04_glass_metrics.png`
- 能力卡：`05_glass_bento.png`
- 第 1 次返回：`_home_after_1_cycle.png`
- 第 5 / 20 / 30 次：`08_` / `09_` / `10_home_after_*_cycles.png`
- DOM / 性能：`12_dom_canvas_count.png` `13_dom_svg_filter_count.png` `14_performance_timing.png` + `.json`

## 5. 30 次循环 DOM（热路径）

首次与第 30 次：

| 指标 | 第 1 次 | 第 30 次 | Delta |
| --- | ---: | ---: | ---: |
| canvas | 1 | 1 | 0 |
| iframe | 0 | 0 | 0 |
| svg | 25 | 25 | 0 |
| style | 4 | 4 | 0 |
| metric-card | 4 | 4 | 0 |
| glass-card | 4 | 4 | 0 |
| hero-cta | 2 | 2 | 0 |
| abnormalCurves | 0 | 0 | 0 |
| memoryMB | 32 | 32 | 0 |

说明：Streamlit Custom Component v2 走 Shadow DOM，**没有**落地 iframe。  
`#sage125-hero-particles` 在官方 wrapper 里同时出现在 DIV 与 CANVAS 上，实例仍是 1 个 `<Particles>` + 1 个 canvas。

性能（30 次首页↔工作区）：

```
HOME_RETURN_WARM_P50=0.166s
HOME_RETURN_WARM_P95=0.218s
PAGE_SWITCH_WARM_P50=0.228s
PAGE_SWITCH_WARM_P95=0.286s
BROWSER_CONSOLE_ERROR_COUNT=0
BROWSER_NETWORK_5XX_COUNT=0
```

`STATS_SKELETON_FIRST_PAINT`：宿主 `style.css` 在入口一次注入，`.st-key-sage125-landing-home-v1` 带 min-height 占位；React 统计卡在返回首页后随组件可见。独立 150ms 骨架仪未与热切页分开埋点；热返回到 `.metric-card` 的 P95 为 0.218s。

## 6. 修复策略摘要

1. `app/ui/results_root.py` + `SAGE125_RESULTS_ROOT` 统一根目录。  
2. `app/ui/ui_summary.py` 一次审计，写入 `ui_summary.json`；首页 `st.cache_data` 只读文件，刷新按钮才 `force` 重建。  
3. `render_landing` 只调用一次 `sage125_landing(..., key="sage125-landing-home-v1")`；统计刷新在独立 fragment。  
4. `page_landing` 先画首页再 `bootstrap()`。  
5. 四张统计卡统一 `.metric-card` 玻璃分层；能力卡统一 `.glass-card`，无图标、无纯白。  
6. Hero 改为两个原生 `button.hero-cta`，删除 liquid-glass。  
7. AnimatedBeam 校验布局与边界；ParticlesProvider + 固定 id。  
8. 侧栏/工作区壳不再每次注入 `<style>`。
