"use client";

/*
 * Number Ticker —— 首次进入视口时从起始值滚动到目标值的数字动画。
 *
 * 来源: https://github.com/magicuidesign/magicui
 *       apps/www/registry/magicui/number-ticker.tsx （MIT License）
 * 获取日期: 2026-08-24
 * 使用文件: src/components/magicui/number-ticker.tsx（本文件）
 *
 * 本项目修改说明：
 * - `useInView(ref, { once: true })` 保留官方“只在首次进入视口触发一次”的行为，
 *   不会随 Streamlit 每次 rerun 重新从 0 动画（Streamlit rerun 不会重新挂载
 *   DOM 节点，React 组件树在数据不变时保持稳定）；
 * - 新增 `value` 为 `null` 时的降级：直接渲染 "—"，不启动任何动画，
 *   避免用真实数据缺失时伪造为 0 或其他数字。
 */

import { useInView, useMotionValue, useSpring } from "motion/react";
import { useEffect, useRef, type ComponentPropsWithoutRef } from "react";

import { cn } from "../../lib/utils";

interface NumberTickerProps extends Omit<ComponentPropsWithoutRef<"span">, "children"> {
  value: number | null;
  startValue?: number;
  direction?: "up" | "down";
  delay?: number;
  decimalPlaces?: number;
  suffix?: string;
}

export function NumberTicker({
  value,
  startValue = 0,
  direction = "up",
  delay = 0,
  className,
  decimalPlaces = 0,
  suffix = "",
  ...props
}: NumberTickerProps) {
  const ref = useRef<HTMLSpanElement>(null);
  const motionValue = useMotionValue(direction === "down" ? (value ?? 0) : startValue);
  const springValue = useSpring(motionValue, { damping: 60, stiffness: 100 });
  const isInView = useInView(ref, { once: true, margin: "0px" });

  useEffect(() => {
    if (value === null || !isInView) return undefined;

    const timer = setTimeout(() => {
      motionValue.set(direction === "down" ? startValue : value);
    }, delay * 1000);

    return () => clearTimeout(timer);
  }, [motionValue, isInView, delay, value, direction, startValue]);

  useEffect(
    () =>
      springValue.on("change", (latest) => {
        if (ref.current && value !== null) {
          ref.current.textContent =
            Intl.NumberFormat("en-US", {
              minimumFractionDigits: decimalPlaces,
              maximumFractionDigits: decimalPlaces,
            }).format(Number(latest.toFixed(decimalPlaces))) + suffix;
        }
      }),
    [springValue, decimalPlaces, suffix, value],
  );

  if (value === null) {
    return (
      <span className={cn("tabular-nums", className)} {...props}>
        —
      </span>
    );
  }

  const initial = Intl.NumberFormat("en-US", {
    minimumFractionDigits: decimalPlaces,
    maximumFractionDigits: decimalPlaces,
  }).format(startValue === value ? value : startValue) + suffix;

  return (
    <span ref={ref} className={cn("tabular-nums", className)} {...props}>
      {initial}
    </span>
  );
}
