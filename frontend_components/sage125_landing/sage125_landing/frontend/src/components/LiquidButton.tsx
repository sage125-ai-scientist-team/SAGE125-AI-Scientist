"use client";

/*
 * 液态玻璁按钮 —— 固定使用 liquid-glass-react（§10）。
 *
 * 来源: https://github.com/rdev/liquid-glass-react （MIT License）
 * 使用文件: src/components/LiquidButton.tsx（本文件）
 * 使用位置: Hero 主 CTA“进入研究工作区”、次 CTA“查看代表案例”。
 *
 * 关键设计说明：
 * - 该库官方 README 明确写明 "Safari and Firefox only partially support
 *   the effect (displacement will not be visible)"——也就是说库本身在这些
 *   浏览器里已经会自动退化为"只剩 backdrop-filter 磨砂 + 边缘高光，没有
 *   SVG 折射位移"，并不会导致按钮消失。本组件在此基础上再加两层保险：
 *     1) 特性检测：不支持 backdrop-filter 或 SVG 滤镜元素时，直接不渲染
 *        `<LiquidGlass>`，改用纯 CSS 磨砂降级按钮（仍保留 hover/点击缩放/
 *        反光边缘，只是没有液态折射）；
 *     2) 运行期错误边界：即使特性检测通过，`<LiquidGlass>` 内部渲染仍抛出
 *        异常，也会被捕获并切换到同一套纯 CSS 降级按钮，而不是让整个
 *        Hero 报错白屏。
 * - 真正可点击/可聚焦/可用键盘操作的元素始终是内部原生 `<button>`，
 *   `LiquidGlass` 只作为其外层的视觉容器，不接管 onClick——保证不会被
 *   渲染成不可访问的 Canvas/div。
 */

import LiquidGlass from "liquid-glass-react";
import { Component, type ButtonHTMLAttributes, type ReactNode } from "react";

import { cn } from "../lib/utils";

export type LiquidButtonVariant = "primary" | "secondary";

export interface LiquidButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: LiquidButtonVariant;
  children: ReactNode;
}

function supportsLiquidGlass(): boolean {
  if (typeof window === "undefined" || typeof document === "undefined") return false;
  try {
    const backdropOk =
      typeof CSS !== "undefined" &&
      (CSS.supports("backdrop-filter", "blur(2px)") || CSS.supports("-webkit-backdrop-filter", "blur(2px)"));
    const svgFilterOk = typeof SVGFEDisplacementMapElement !== "undefined";
    return backdropOk && svgFilterOk;
  } catch {
    return false;
  }
}

const VARIANT_STYLE: Record<LiquidButtonVariant, { bg: string; border: string; text: string }> = {
  primary: { bg: "rgba(55, 113, 234, 0.35)", border: "rgba(129, 181, 255, 0.44)", text: "#F7FAFF" },
  secondary: { bg: "rgba(13, 36, 60, 0.40)", border: "rgba(124, 164, 217, 0.32)", text: "#E7EEFB" },
};

/** 纯 CSS 磨砂降级按钮：不支持 SVG 折射位移/backdrop-filter 时使用，
 *  或 LiquidGlass 运行期渲染异常时的兜底。保留 hover 高光与点击缩放。 */
function FallbackGlassButton({
  variant = "primary",
  className,
  children,
  ...rest
}: LiquidButtonProps) {
  const tone = VARIANT_STYLE[variant];
  return (
    <button
      {...rest}
      className={cn(
        "relative inline-flex items-center justify-center rounded-full border px-6 py-2.5 text-[14px] font-medium",
        "transition-all duration-200 ease-out active:scale-[0.97] hover:brightness-110",
        "backdrop-blur-md backdrop-saturate-150",
        className,
      )}
      style={{
        background: tone.bg,
        borderColor: tone.border,
        color: tone.text,
        boxShadow: "inset 0 1px 0 rgba(255,255,255,0.12), 0 8px 24px rgba(0,0,0,0.22)",
      }}
    >
      {children}
    </button>
  );
}

interface BoundaryState {
  hasError: boolean;
}

/** liquid-glass-react 在部分环境下的 SVG 滤镜渲染是运行期行为，
 *  用 Error Boundary 兜底比单纯的特性检测更保险。 */
class LiquidGlassErrorBoundary extends Component<{ children: ReactNode; fallback: ReactNode }, BoundaryState> {
  state: BoundaryState = { hasError: false };
  static getDerivedStateFromError() {
    return { hasError: true };
  }
  componentDidCatch() {
    // 静默降级，不向控制台外的用户界面暴露技术细节。
  }
  render() {
    return this.state.hasError ? this.props.fallback : this.props.children;
  }
}

/**
 * Hero 主/次 CTA 按钮。
 *
 * 参数方向严格对齐任务规格 §10：
 * - frosty level 中等 -> blurAmount ≈ 0.09
 * - elasticity 轻微 -> 0.12
 * - chromatic aberration 极低 -> aberrationIntensity = 1（库最小可用档）
 * - hover displacement 克制 -> displacementScale 从库默认 70 降到 42
 * - 高亮随背景变化 -> saturation 130（库默认），不额外覆盖
 */
export function LiquidButton({ variant = "primary", className, children, onClick, disabled, "aria-label": ariaLabel, ...rest }: LiquidButtonProps) {
  const tone = VARIANT_STYLE[variant];
  const canUseLiquidGlass = supportsLiquidGlass() && !disabled;

  const innerButton = (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-label={ariaLabel}
      {...rest}
      className={cn(
        "relative z-10 inline-flex items-center justify-center whitespace-nowrap px-6 py-2.5 text-[14px] font-medium leading-none",
        "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2",
        "disabled:cursor-not-allowed disabled:opacity-40",
        className,
      )}
      style={{ color: tone.text, outlineColor: "#71A4FF" }}
    >
      {children}
    </button>
  );

  if (!canUseLiquidGlass) {
    return (
      <FallbackGlassButton variant={variant} onClick={onClick} disabled={disabled} aria-label={ariaLabel} {...rest}>
        {children}
      </FallbackGlassButton>
    );
  }

  return (
    <LiquidGlassErrorBoundary
      fallback={
        <FallbackGlassButton variant={variant} onClick={onClick} disabled={disabled} aria-label={ariaLabel} {...rest}>
          {children}
        </FallbackGlassButton>
      }
    >
      {/*
       * liquid-glass-react 内部用 `top:50%; left:50%; transform:
       * translate(-50%,-50%)` 把自身在"最近的定位祖先"内居中——这意味着它
       * 期望被放进一个具备真实尺寸的 `position: relative` 容器，而不是直接
       * 参与外层 flex 排列。这里用一个不可见的占位 span 撑开与真实按钮文字
       * 相同的尺寸来确定容器大小，LiquidGlass 再用 `position: absolute` 在
       * 这个容器正中央铺满渲染出玻璁按钮。
       */}
      <span className="relative inline-flex">
        <span
          aria-hidden="true"
          className="invisible inline-flex h-11 items-center whitespace-nowrap rounded-full px-6 text-[14px] font-medium"
        >
          {children}
        </span>
        <LiquidGlass
          displacementScale={42}
          blurAmount={0.09}
          saturation={130}
          aberrationIntensity={1}
          elasticity={0.12}
          cornerRadius={999}
          padding="0"
          style={{
            background: tone.bg,
            border: `1px solid ${tone.border}`,
            position: "absolute",
            top: "50%",
            left: "50%",
            width: "100%",
            height: "100%",
          }}
        >
          {innerButton}
        </LiquidGlass>
      </span>
    </LiquidGlassErrorBoundary>
  );
}
