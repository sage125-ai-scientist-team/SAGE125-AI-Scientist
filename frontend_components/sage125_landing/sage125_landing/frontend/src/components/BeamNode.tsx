import { forwardRef, type CSSProperties } from "react";

import { cn } from "../lib/utils";

/**
 * Animated Beam 使用的文字节点：胶囊/圆角矩形，仅显示文字，
 * 尺寸由文字内容决定（不使用任何图标）。
 */
export interface BeamNodeProps {
  label: string;
  emphasis?: boolean;
  className?: string;
  style?: CSSProperties;
}

export const BeamNode = forwardRef<HTMLDivElement, BeamNodeProps>(
  ({ label, emphasis = false, className, style }, ref) => {
    return (
      <div
        ref={ref}
        style={style}
        className={cn(
          "z-10 inline-flex items-center justify-center whitespace-nowrap rounded-full border px-3 py-1.5 text-[12px] font-medium leading-none shadow-sm",
          emphasis
            ? "border-[#71A4FF]/45 bg-[#4D7FFF]/18 text-[#EAF1FF]"
            : "border-[rgba(124,164,217,0.28)] bg-[rgba(20,36,58,0.72)] text-[#B7C5D8]",
          className,
        )}
      >
        {label}
      </div>
    );
  },
);

BeamNode.displayName = "BeamNode";
