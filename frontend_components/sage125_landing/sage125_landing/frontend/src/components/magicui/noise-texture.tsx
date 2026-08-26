"use client";

/*
 * Noise Texture —— SVG fractal noise 磨砂纹理叠层。
 *
 * 来源: https://github.com/magicuidesign/magicui
 *       apps/www/registry/magicui/noise.tsx （MIT License，"Noise Texture" 组件）
 * 获取日期: 2026-08-25
 * 使用文件: src/components/magicui/noise-texture.tsx（本文件）
 *
 * 本项目修改说明（对齐 CAPTAIN-LOCAL-...-05 第八节）：
 * - 保留官方版本核心思路：用 `feTurbulence` 生成细颗粒噪点，而不是位图噪点
 *   图片（避免额外网络请求/资源体积，且可无限缩放不失真）；
 * - 按任务规格强制夹紧强度：
 *     opacity 固定夹在 0.025–0.055
 *     blend-mode 固定为 soft-light（不允许改成更强烈的 overlay/screen）
 * - `baseFrequency` 调高到 0.9，产出的是"细颗粒"而不是官方默认示例里更粗的
 *   颗粒感，符合"不使用大颗粒噪点"的要求。
 */

import { useId } from "react";

import { cn } from "../../lib/utils";

export interface NoiseTextureProps {
  className?: string;
  /** 噪点不透明度。任务规格要求 0.025-0.055，此处会强制夹紧。 */
  opacity?: number;
}

const MIN_OPACITY = 0.025;
const MAX_OPACITY = 0.055;

export function NoiseTexture({ className, opacity = 0.04 }: NoiseTextureProps) {
  const filterId = useId();
  const clamped = Math.min(Math.max(opacity, MIN_OPACITY), MAX_OPACITY);

  return (
    <svg
      aria-hidden="true"
      className={cn("pointer-events-none absolute inset-0 h-full w-full", className)}
      style={{ opacity: clamped, mixBlendMode: "soft-light" }}
    >
      <filter id={filterId}>
        <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" stitchTiles="stitch" />
        <feColorMatrix type="saturate" values="0" />
      </filter>
      <rect width="100%" height="100%" filter={`url(#${filterId})`} />
    </svg>
  );
}
