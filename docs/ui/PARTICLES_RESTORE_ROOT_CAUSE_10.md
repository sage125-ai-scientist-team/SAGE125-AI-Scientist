# 首页粒子恢复根因（CAPTAIN-LOCAL-SAGE125-INTERACTIVE-PARTICLES-RESTORE-10）

修改前实测（`http://127.0.0.1:8610`，新 Playwright 上下文）：

```
PARTICLES_REACT_COMPONENT_PRESENT=True
PARTICLES_PROVIDER_PRESENT=True
PARTICLES_CANVAS_PRESENT=True
PARTICLES_CANVAS_COUNT=1
PARTICLES_CANVAS_WIDTH=1920
PARTICLES_CANVAS_HEIGHT=960
PARTICLES_CANVAS_OPACITY=1
PARTICLES_CANVAS_DISPLAY=inline
PARTICLES_CANVAS_VISIBILITY=visible
PARTICLES_CANVAS_Z_INDEX=auto
PARTICLES_CONTAINER_LOADED_CALLBACK_FIRED=True
PARTICLES_ENGINE_INITIALIZED=True
LOAD_SLIM_COMPLETED=True
REDUCED_MOTION=False
VISIBLE_PARTICLE_COUNT=肉眼 0（截图像素仅见静态网格）
```

截图：`docs/ui/particles_restore_10/01_before_no_particles.png`

## 精确根因

**不是**「配置写成 0」「reduced-motion 被写死」「只渲染了 fallback 而没有 `<Particles>`」。

官方 `@tsparticles/react` 4.3.2 的 `<Particles id="sage125-hero-particles">` 内部执行：

```js
tsParticles.load({ id })
document.getElementById(id)  // 找不到则 destroy
```

引擎 `getDomContainer`（`@tsparticles/engine` 4.3.2）：

```js
let domContainer = source ?? document.getElementById(id);
if (!domContainer) {
  domContainer = document.createElement("canvas");
  domContainer.id = id;
  document.body.append(domContainer);
}
```

Streamlit Custom Components **v2** 默认 `isolate_styles=True`，React 树在 **Shadow DOM** 内。  
`document.getElementById` **不能穿过 ShadowRoot**（open/closed 皆然）。

因此：

1. `load({ id })` 在 document 上找不到 Hero 内的 DIV；
2. 引擎在 **`document.body` 追加一张全视口 Canvas**（1920×960，原点 (0,0)）；
3. React 侧随后 `getElementById` 能找到这张 body Canvas，**不会 destroy**，`particlesLoaded` 仍会触发；
4. Canvas 位于 Streamlit `.stApp` 不透明深蓝背景之后，评委只看到 Hero 里的 **静态网格**（`.ambient-light-layer`）；
5. Hero 实测 1792×540，与 body Canvas 尺寸/坐标系不一致。

次要放大因素（修复时一并去掉）：

- `pauseOnOutsideViewport: true` 在错误挂载的全页 Canvas 上会误暂停；
- Hero `min-height` 仅 460–540，低于门禁 650；
- 组件 key 仍为 `sage125-landing-home-v1`，样式规则绑旧 key。

## 排除项

| 假设 | 结论 |
| --- | --- |
| Canvas 不存在 | 否，存在 1 张 |
| Canvas 0×0 / 默认 150px | 否，1920×960 |
| display:none / visibility:hidden / opacity:0 | 否 |
| prefers-reduced-motion 永久 true | 否，实测 false |
| particles.number=0 / move.enable=false | 否（源码仅在 reducedMotion 时为 0） |
| 只渲染静态 fallback | 否，`<Particles>` 已挂，另有网格层 |
| loadSlim 抛错 | 否，callback 已触发 |
| 旧 Service Worker | Playwright 已 `service_workers=block`，现象仍在 |

## 修复方向（仅粒子栈）

1. 组件挂载改为 `isolate_styles=False`，使官方 wrapper 的 `getElementById` 命中 Hero 内宿主 DIV。  
2. `particlesLoaded`：若 Canvas 不在 Hero 层则移回并 `resize()` + `play()`。  
3. `pauseOnOutsideViewport: false`，改用 Hero `IntersectionObserver`。  
4. 固定可见配置（autoPlay、86 粒子、detectsOn:window）。  
5. Hero 粒子层明确高度 ≥700px。  
6. 稳定 key `sage125-landing-home-v2`。  
7. 重建 bundle，新浏览器上下文验收。

## 修复后复核（2026-08-26）

- 组件改为 `isolate_styles=False`，官方 `<Particles id>` 的 `getElementById` 命中 Hero 内 DIV。
- Canvas 实测 **1792×700**，与 Hero 重合（不再是 body 上 1920×960）。
- `PARTICLES_STATUS=ready`，`loadSlim` 每生命周期 1 次，`pauseOnOutsideViewport=false`。
- 浏览器加载 `index-r96ktMW1.js`（SHA-256 `5fa29acca100afd0137273e9b3f7b20eac2b1f387ef476bf3baaec4e7415954c`），与当前 build 一致。
- 引擎快照：约 86–89 个节点、100+ 条连线；截图可见星座状节点与连线。
- Hover 诊断必须从 `container.plugins[].interactionManager.interactivityData.mouse` 读取，v4.3.2 的 `Container` 上没有 `interactivity` 字段。复测：左/中/右 `grabBoosted` 为 14/14/18，连线不透明度 0.25→0.62。
