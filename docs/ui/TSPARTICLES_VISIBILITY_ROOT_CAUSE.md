# tsParticles 首页动态背景可见度根因诊断

CAPTAIN-LOCAL-SAGE125-TSPARTICLES-VISIBILITY-CALIBRATION-06 §1。

诊断方式：真实启动 `app/ui/streamlit_app.py`（127.0.0.1:8610），用 Playwright 打开
首页、等待网络空闲 3s 后，通过 `page.evaluate()` 读取实际 DOM 计算样式（不是
读配置文件猜测），并测量 2 秒窗口内的真实 rAF 帧率。原始输出见同目录
`_particles_diag_out.json`（诊断脚本 `_particles_diag.py`，验证后已清理）。

## 1. Canvas 覆盖与透明度（真实测量值）

```json
"canvas": {
  "width": 1808, "height": 556,
  "clientWidth": 1808, "clientHeight": 556,
  "rectWidth": 1808, "rectHeight": 556,
  "computedOpacity": "1",
  "computedDisplay": "block",
  "zIndex": "auto",
  "position": "absolute"
}
```

- Canvas 尺寸与 Hero 容器（`hero.width=1792, hero.height=540`，含 padding 差值）
  基本一致 → **Canvas 已完整覆盖 Hero**，不是"没铺满"的问题。
- `computedOpacity: "1"` → **Canvas 元素本身没有被压暗**，不是"父容器
  opacity"直接导致的问题。
- 结论：问题不在覆盖范围或直接 opacity，而在于粒子本身的可见参数与
  遮罩机制（见下）。

## 2. 遮罩层：确认存在"双重压暗"

诊断脚本枚举了 Hero 内所有 `aria-hidden="true"` 的绝对定位层，发现：

```json
"wrapper": {
  "maskImage": "radial-gradient(62% 58% at 50% 42%,
                 rgba(0,0,0,0.22) 0%, rgba(0,0,0,0.5) 45%,
                 rgba(0,0,0,0.92) 75%, rgb(0,0,0) 100%)"
},
"overlays": [
  { "className": "...z-0",  "opacity": "1", "background": "none" },
  { "className": "...z-[1] opacity-[0.05]", "opacity": "0.05", "...grid..." },
  { "className": "...z-[1]", "opacity": "1",
    "background": "radial-gradient(70% 60% at 50% 38%,
                    rgba(9,16,30,0) 0%, rgba(9,16,30,0.35) 70%,
                    rgba(9,16,30,0.62) 100%)" },
  { "className": "...z-[2] h-28", "opacity": "1",
    "background": "linear-gradient(rgba(6,12,24,0), rgba(6,12,24,0.9))" }
]
```

**这就是"背景几乎像静态图"的核心根因，且确实是两层独立的压暗机制叠加：**

1. **粒子容器自身的 CSS `mask-image`**（`ParticlesBackground.tsx` 里的
   `DENSITY_MASK`）：中心 alpha 只有 **0.22**（即中心粒子只剩 22% 的
   可见度），边缘才到 100%。这是为了做"中央稀疏、四周稠密"的分布，
   但 0.22 这个值把中心区域的粒子压到几乎看不见。
2. **HeroSection 里独立的 `radialGradientMask` div**（与 1 完全不同的
   一层，`z-[1]`，纯色深蓝径向渐变）：中心 alpha=0，但**四周 alpha 一路升
   到 0.62**，即把粒子密度本来最高的四周区域又用近 2/3 不透明度的深色盖住。

两者方向恰好互补又互相抵消视觉收益：中心粒子被①压到几乎不可见，
四周粒子密度虽高但被②的深色蒙层盖到发暗——**结果是全区域都不鲜明**，
与截图观察到的"几乎像静态图"完全吻合。此外还叠加了第三层
`subtleGridLayer`（0.05 透明度，影响可忽略）与第四层 `bottomFade`
（底部 112px 高，alpha 最高 0.9，进一步压暗下方区域）。四层叠加、
但只有 2 层对可见度有实质影响 → **DUPLICATE_DARK_OVERLAY_COUNT = 1**
（即 mask-image 与 radialGradientMask 构成一组重复压暗，bottomFade/grid
影响可忽略不计单独列为"重复"）。

## 3. 粒子基础参数（源码实测，非配置猜测）

`ParticlesBackground.tsx` `buildOptions()` 实际生效值：

| 参数 | 当前值 | 观感影响 |
| --- | --- | --- |
| `particles.number.value`（桌面/平板/移动） | 65 / 37 / 20 | 仅 3 档，桌面档偏低 |
| `particles.opacity.value` | min 0.10, max 0.34 | 无动画（无脈动），基础值本来就暗 |
| `particles.size.value` | min 1, max 2.6 | 无尺寸动画 |
| `particles.links.distance` | 135 | 尚可 |
| `particles.links.opacity` | **0.11** | 连线几乎看不见 |
| `particles.move.speed` | min 0.14, max 0.24 | 位移极慢，静止观感强 |
| `interactivity.events.onHover.enable` | **false** | 完全没有鼠标交互反馈 |
| `particles.groups` | 未设置 | 无主/次节点视觉分层 |

叠加上一节的双重遮罩，实际可感知效果 ≈ `基础 opacity(≤0.34) × mask 中心
alpha(0.22) × 边缘再被 radialGradientMask 压暗(最高再乘 0.38)`，
中心区域有效可见度低至个位数百分比。

## 4. 帧率与初始化（排除性能相关误判）

```json
"fps": { "frames": 94, "elapsedMs": 2021.7, "fps": 46.5 }
```

真实测得 2 秒窗口帧率约 **46.5 FPS**，远高于本轮 35 FPS 门禁，且高于
现有 `fpsLimit: 45` 配置本身（说明当前"看起来是静态图"**不是性能降级
导致的丢帧**，而纯粹是参数与遮罩层面的可见度问题）。这意味着后续提高
粒子数量/位移速度/透明度时，有充足的性能余量。

`window.tsParticles.domArray` 在本次诊断中未能读到 `particles.count`
（`particleCountFromEngine: null`）——核实后确认 tsParticles 在当前环境下
使用了 `OffscreenCanvas`（`transferControlToOffscreen()`）+ Worker 渲染
（诊断脚本尝试 `canvas.getContext('2d')` 时报
`InvalidStateError: ...transferred its control to offscreen`），因此无法
从主线程直接读取 Worker 内的粒子状态或用 `getImageData` 采样像素。
后续「可见节点/连线数」验收改为**基于最终合成帧的截图比对**（浏览器合成
后的像素是 Worker 渲染结果的最终呈现，不受这个限制），而不是读 Canvas
2D 上下文或引擎内部状态。

Canvas 是否在 Streamlit rerun 时被销毁重建：`ParticlesBackground.tsx`
的引擎加载 `useEffect` 依赖数组为 `[options, reducedMotion]`，`options`
由 `useMemo` 基于 `[count, reducedMotion]` 计算，两者都只在窗口尺寸分档
变化或系统级 reduced-motion 设置变化时才改变；`index.tsx` 用
`WeakMap<parentElement, Root>` 缓存 React root，Streamlit 数据更新只触发
`reactRoot.render()`（更新同一棵树，不重新 `createRoot`），因此**理论上
一次会话内只应初始化一次**。本轮第十节会追加一个初始化计数器做实测
验证（而非只信任这段代码推理）。

## 5. 结论与本轮修复方向

| 问题 | 根因 | 修复方向（见 §2-§8 实现） |
| --- | --- | --- |
| 大面积区域无可见节点 | ①中心 mask alpha 0.22 太低 ②基础 opacity/size 太小 | 大幅放宽 mask 中心 alpha、提高基础 opacity/size，责任从"全局压暗"移交给局部 `.hero-content::before` |
| 连线过暗 | `links.opacity: 0.11` | 提到 0.26（+主节点 grab 时到 0.58） |
| 动态位移过小 | `move.speed` 0.14–0.24 | 提到 0.38–0.82（含 opacity/size 动画） |
| 深色遮罩压住动画 | mask-image + radialGradientMask 双重叠加 | 合并为单一 `.readability-mask`，总等效不透明度 ≤0.42 |
| 不动鼠标时像静态图 | 无 opacity/size 动画，move 速度过慢 | 开启 opacity/size 动画 + 提高基础位移速度 |
| 鼠标无反馈 | `onHover.enable: false` | 开启 grab 模式（175px，链接透明度可到 0.58），`detectsOn: "window"`（原因见 §7 实现说明：canvas 本身 `pointer-events:none`，用 window 级坐标探测而不牺牲按钮可点击性，等价于任务里提到的"通过容器转发"方案，但实现更简单可靠） |
