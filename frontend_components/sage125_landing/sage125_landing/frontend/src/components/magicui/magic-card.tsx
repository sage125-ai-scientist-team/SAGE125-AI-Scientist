"use client";

/*
 * Magic Card —— 鼠标聚光边缘效果。
 *
 * 来源: https://github.com/magicuidesign/magicui
 *       apps/www/registry/magicui/magic-card.tsx （MIT License）
 * 获取日期: 2026-08-24
 * 使用文件: src/components/magicui/magic-card.tsx（本文件）
 *
 * 本项目修改说明（对齐 CAPTAIN-LOCAL-...-05 第八节）：
 * - 移除 next-themes 依赖（未在本任务批准的依赖清单中）；
 * - 移除官方版本自带的白色 padding-box 背景与边框渐变——本组件现在只负责
 *   “鼠标聚光边缘”这一层视觉效果，卡片真正的背景/边框/圆角统一交给外层
 *   .glass-card（见 globals.css 与 CardShell.tsx）用 isolation + ::before
 *   分层实现，避免两套背景逻辑打架，也避免聚光层意外盖住文字；
 * - 按任务规格强制夹紧关键参数上限：
 *     gradientOpacity <= 0.10（比上一轮的 0.12 更严格）
 *     gradientSize（聚光半径）夹在 220-320px
 *   即使调用方传入更大的值，也会在本文件内被截断，防止出现“高亮炫光”；
 * - hover 时的位移/缩放改为在外层通过 CSS class 控制
 *   （translateY 最大 -2px，scale 最大 1.005，过渡 180-240ms），
 *   而不是 Magic UI 原版的强烈发光/放大效果。
 */

import { motion, useMotionTemplate, useMotionValue } from "motion/react";
import type React from "react";
import { useCallback, useEffect } from "react";

import { cn } from "../../lib/utils";

export interface MagicCardProps {
  children?: React.ReactNode;
  className?: string;
  /** 聚光半径（px）。任务规格要求 220-320，此处会强制夹紧。 */
  gradientSize?: number;
  /** 聚光颜色（不透明度由 gradientOpacity 控制）。 */
  gradientColor?: string;
  /** 聚光不透明度。任务规格要求 <= 0.10，此处会强制夹紧。 */
  gradientOpacity?: number;
}

const MAX_GRADIENT_OPACITY = 0.08;
const MIN_GRADIENT_SIZE = 220;
const MAX_GRADIENT_SIZE = 320;

export function MagicCard({
  children,
  className,
  gradientSize = 260,
  gradientColor = "rgba(113, 164, 255, 0.55)",
  gradientOpacity = 0.08,
}: MagicCardProps) {
  const clampedSize = Math.min(Math.max(gradientSize, MIN_GRADIENT_SIZE), MAX_GRADIENT_SIZE);
  const clampedOpacity = Math.min(gradientOpacity, MAX_GRADIENT_OPACITY);

  const mouseX = useMotionValue(-clampedSize);
  const mouseY = useMotionValue(-clampedSize);

  const reset = useCallback(() => {
    mouseX.set(-clampedSize);
    mouseY.set(-clampedSize);
  }, [mouseX, mouseY, clampedSize]);

  const handlePointerMove = useCallback(
    (e: React.PointerEvent<HTMLDivElement>) => {
      const rect = e.currentTarget.getBoundingClientRect();
      mouseX.set(e.clientX - rect.left);
      mouseY.set(e.clientY - rect.top);
    },
    [mouseX, mouseY],
  );

  useEffect(() => {
    reset();
  }, [reset]);

  return (
    <motion.div
      className={cn("sage-magic-card group relative", className)}
      onPointerMove={handlePointerMove}
      onPointerLeave={reset}
    >
      <motion.div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 z-0 rounded-[inherit] opacity-0 transition-opacity duration-200 group-hover:opacity-100"
        style={{
          background: useMotionTemplate`
            radial-gradient(${clampedSize}px circle at ${mouseX}px ${mouseY}px,
              ${gradientColor},
              transparent 100%
            )
          `,
          opacity: clampedOpacity,
        }}
      />
      <div className="relative z-10">{children}</div>
    </motion.div>
  );
}
