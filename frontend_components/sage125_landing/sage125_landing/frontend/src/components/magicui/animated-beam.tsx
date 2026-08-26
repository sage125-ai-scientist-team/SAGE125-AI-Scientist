"use client";

/*
 * Animated Beam —— 两个节点之间的渐变流光连线。
 *
 * 来源: https://github.com/magicuidesign/magicui
 *       apps/www/registry/magicui/animated-beam.tsx （MIT License）
 *
 * 本项目修改：
 * - 路径只在容器与两端节点都已完成布局、且坐标落在容器内时才绘制。
 * - 返回首页后若节点尚未布局，不再用视口坐标画出贯穿整页的巨大弧线。
 * - ResizeObserver / rAF 在卸载时完整清理。
 */

import { motion } from "motion/react";
import { type RefObject, useEffect, useId, useState } from "react";

import { cn } from "../../lib/utils";

export interface AnimatedBeamProps {
  className?: string;
  containerRef: RefObject<HTMLElement | null>;
  fromRef: RefObject<HTMLElement | null>;
  toRef: RefObject<HTMLElement | null>;
  curvature?: number;
  reverse?: boolean;
  pathColor?: string;
  pathWidth?: number;
  pathOpacity?: number;
  gradientStartColor?: string;
  gradientStopColor?: string;
  delay?: number;
  duration?: number;
  startXOffset?: number;
  startYOffset?: number;
  endXOffset?: number;
  endYOffset?: number;
  reducedMotion?: boolean;
}

const MIN_DURATION = 4;
const MAX_DURATION = 7;
const MIN_BOX = 8;

export const AnimatedBeam: React.FC<AnimatedBeamProps> = ({
  className,
  containerRef,
  fromRef,
  toRef,
  curvature = 0,
  reverse = false,
  duration = 5.5,
  delay = 0,
  pathColor = "#c7d5f5",
  pathWidth = 1.6,
  pathOpacity = 0.28,
  gradientStartColor = "#4D7FFF",
  gradientStopColor = "#2CC4D6",
  startXOffset = 0,
  startYOffset = 0,
  endXOffset = 0,
  endYOffset = 0,
  reducedMotion = false,
}) => {
  const id = useId();
  const [pathD, setPathD] = useState("");
  const [svgDimensions, setSvgDimensions] = useState({ width: 0, height: 0 });
  const clampedDuration = Math.min(Math.max(duration, MIN_DURATION), MAX_DURATION);

  const gradientCoordinates = reverse
    ? { x1: ["90%", "-10%"], x2: ["100%", "0%"], y1: ["0%", "0%"], y2: ["0%", "0%"] }
    : { x1: ["10%", "110%"], x2: ["0%", "100%"], y1: ["0%", "0%"], y2: ["0%", "0%"] };

  useEffect(() => {
    let cancelled = false;
    let frame = 0;

    const updatePath = () => {
      if (cancelled) return;
      const container = containerRef.current;
      const fromEl = fromRef.current;
      const toEl = toRef.current;
      if (!container || !fromEl || !toEl) {
        setPathD("");
        return;
      }

      const containerRect = container.getBoundingClientRect();
      const rectA = fromEl.getBoundingClientRect();
      const rectB = toEl.getBoundingClientRect();
      if (
        containerRect.width < MIN_BOX ||
        containerRect.height < MIN_BOX ||
        rectA.width < 1 ||
        rectA.height < 1 ||
        rectB.width < 1 ||
        rectB.height < 1
      ) {
        setPathD("");
        return;
      }

      const startX = rectA.left - containerRect.left + rectA.width / 2 + startXOffset;
      const startY = rectA.top - containerRect.top + rectA.height / 2 + startYOffset;
      const endX = rectB.left - containerRect.left + rectB.width / 2 + endXOffset;
      const endY = rectB.top - containerRect.top + rectB.height / 2 + endYOffset;
      const inset = 2;
      const inside =
        startX >= -inset &&
        startY >= -inset &&
        endX >= -inset &&
        endY >= -inset &&
        startX <= containerRect.width + inset &&
        startY <= containerRect.height + inset &&
        endX <= containerRect.width + inset &&
        endY <= containerRect.height + inset;
      if (!inside) {
        setPathD("");
        return;
      }

      const midX = (startX + endX) / 2;
      const rawControlY = startY - curvature;
      const controlY = Math.min(containerRect.height - 2, Math.max(2, rawControlY));
      setSvgDimensions({ width: containerRect.width, height: containerRect.height });
      setPathD(`M ${startX},${startY} Q ${midX},${controlY} ${endX},${endY}`);
    };

    const schedule = () => {
      if (frame) window.cancelAnimationFrame(frame);
      frame = window.requestAnimationFrame(updatePath);
    };

    const resizeObserver = new ResizeObserver(schedule);
    if (containerRef.current) resizeObserver.observe(containerRef.current);
    schedule();

    return () => {
      cancelled = true;
      resizeObserver.disconnect();
      if (frame) window.cancelAnimationFrame(frame);
      setPathD("");
    };
  }, [containerRef, fromRef, toRef, curvature, startXOffset, startYOffset, endXOffset, endYOffset]);

  if (!pathD || svgDimensions.width < MIN_BOX || svgDimensions.height < MIN_BOX) {
    return null;
  }

  return (
    <svg
      fill="none"
      width={svgDimensions.width}
      height={svgDimensions.height}
      xmlns="http://www.w3.org/2000/svg"
      overflow="hidden"
      className={cn("pointer-events-none absolute left-0 top-0 transform-gpu", className)}
      viewBox={`0 0 ${svgDimensions.width} ${svgDimensions.height}`}
    >
      <path
        d={pathD}
        stroke={pathColor}
        strokeWidth={pathWidth}
        strokeOpacity={pathOpacity}
        strokeLinecap="round"
      />
      <path d={pathD} strokeWidth={pathWidth} stroke={`url(#${id})`} strokeOpacity={0.9} strokeLinecap="round" />
      <defs>
        <motion.linearGradient
          className="transform-gpu"
          id={id}
          gradientUnits="userSpaceOnUse"
          initial={{ x1: "0%", x2: "0%", y1: "0%", y2: "0%" }}
          animate={
            reducedMotion
              ? { x1: "10%", x2: "0%", y1: "0%", y2: "0%" }
              : {
                  x1: gradientCoordinates.x1,
                  x2: gradientCoordinates.x2,
                  y1: gradientCoordinates.y1,
                  y2: gradientCoordinates.y2,
                }
          }
          transition={
            reducedMotion
              ? { duration: 0 }
              : {
                  delay,
                  duration: clampedDuration,
                  ease: [0.16, 1, 0.3, 1],
                  repeat: Infinity,
                  repeatDelay: 0,
                }
          }
        >
          <stop stopColor={gradientStartColor} stopOpacity="0" />
          <stop stopColor={gradientStartColor} />
          <stop offset="32.5%" stopColor={gradientStopColor} />
          <stop offset="100%" stopColor={gradientStopColor} stopOpacity="0" />
        </motion.linearGradient>
      </defs>
    </svg>
  );
};
