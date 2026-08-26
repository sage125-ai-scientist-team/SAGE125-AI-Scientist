import type { ReactNode } from "react";

import { cn } from "../lib/utils";
import { GlareHover } from "./magicui/glare-hover";
import { MagicCard } from "./magicui/magic-card";
import { NoiseTexture } from "./magicui/noise-texture";

export interface CardShellProps {
  title: string;
  description: string;
  visual: ReactNode;
  className?: string;
}

/**
 * 4 张能力卡的统一外壳（§6-§8 固定规格）。
 *
 * 层叠结构（由下到上）：
 * 1. `.glass-card::before`  —— 深色磨砂背景（isolation + 独立层，不模糊文字，见 globals.css）
 * 2. `NoiseTexture`         —— SVG fractal noise 磨砂纹理（opacity 0.025-0.055）
 * 3. `MagicCard` 聚光层     —— 鼠标聚光边缘（gradient opacity <= 0.10）
 * 4. `GlareHover`           —— 鼠标移动扫光（opacity <= 0.10）
 * 5. `.glass-card-content`  —— 真正的标题/说明/可视化内容，`filter: none`
 *
 * hover 位移/缩放严格控制在任务规格范围内：translateY 最大 -2px，
 * scale 最大 1.005，过渡 180-240ms；不做"整卡变亮"。
 */
export function CardShell({ title, description, visual, className }: CardShellProps) {
  return (
    <div
      className={cn(
        "glass-card group h-full transition-transform duration-200 ease-out hover:-translate-y-0.5 hover:scale-[1.005]",
        className,
      )}
    >
      <NoiseTexture className="z-[1]" />
      <GlareHover className="z-[2]" />
      <MagicCard className="glass-card-content flex h-full flex-col gap-3 p-5">
        <div className="flex flex-col gap-1.5">
          <h3 className="text-[21px] font-semibold leading-snug text-[#F1F6FF]">{title}</h3>
          <p className="text-[14px] leading-[1.65] text-[#B2C1D5]">{description}</p>
        </div>
        <div className="relative min-h-0 flex-1">{visual}</div>
      </MagicCard>
    </div>
  );
}
