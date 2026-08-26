"use client";

/*
 * Glare Hover —— 鼠标移动时的极轻微反光带。
 *
 * 来源: https://github.com/magicuidesign/magicui
 *       apps/www/registry/magicui/glare-hover.tsx （MIT License）
 * 获取日期: 2026-08-25
 * 使用文件: src/components/magicui/glare-hover.tsx（本文件）
 *
 * 本项目修改说明（对齐 CAPTAIN-LOCAL-...-05 第八节）：
 * - 保留官方版本"沿一个固定角度的线性渐变光带，跟随 hover 触发一次扫过"
 *   的核心思路；
 * - 按任务规格强制夹紧关键参数：
 *     glare opacity <= 0.10
 *     duration 夹在 700-1100ms
 *     angle 夹在 105-125deg
 *   防止出现"刺眼白色光带"；
 * - 用 CSS transition 驱动背景位置平移（而不是官方示例里可能更强的整卡
 *   变亮效果），确保只有光带本身移动，卡片底色/文字亮度不随 hover 变化。
 */

import type { CSSProperties, ReactNode } from "react";

import { cn } from "../../lib/utils";

export interface GlareHoverProps {
  children?: ReactNode;
  className?: string;
  /** 光带不透明度。任务规格要求 <= 0.10，此处会强制夹紧。 */
  glareOpacity?: number;
  /** 扫过时长（ms）。任务规格要求 700-1100，此处会强制夹紧。 */
  duration?: number;
  /** 光带角度（deg）。任务规格要求 105-125，此处会强制夹紧。 */
  angle?: number;
}

const MAX_GLARE_OPACITY = 0.08;
const MIN_DURATION = 700;
const MAX_DURATION = 1100;
const MIN_ANGLE = 105;
const MAX_ANGLE = 125;

export function GlareHover({
  children,
  className,
  glareOpacity = 0.08,
  duration = 900,
  angle = 115,
}: GlareHoverProps) {
  const clampedOpacity = Math.min(glareOpacity, MAX_GLARE_OPACITY);
  const clampedDuration = Math.min(Math.max(duration, MIN_DURATION), MAX_DURATION);
  const clampedAngle = Math.min(Math.max(angle, MIN_ANGLE), MAX_ANGLE);

  const style: CSSProperties = {
    background: `linear-gradient(${clampedAngle}deg, transparent 35%, rgba(255,255,255,${clampedOpacity}) 50%, transparent 65%)`,
    backgroundSize: "250% 250%",
    backgroundPosition: "120% 120%",
    transition: `background-position ${clampedDuration}ms ease`,
  };

  // 依赖最近的祖先元素带 Tailwind `group` 类（CardShell/MagicCard 已提供），
  // hover 该祖先时这里的扫光层从 opacity-0 过渡到 opacity-100。
  return (
    <div
      className={cn("pointer-events-none absolute inset-0 overflow-hidden rounded-[inherit]", className)}
      aria-hidden="true"
    >
      <div
        className="absolute inset-0 opacity-0 transition-opacity duration-300 group-hover:opacity-100"
        style={style}
        data-glare-layer
      />
      {children}
    </div>
  );
}
