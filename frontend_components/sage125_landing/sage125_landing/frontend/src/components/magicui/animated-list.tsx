"use client";

/*
 * Animated List —— 逐项淡入/位移的滚动列表。
 *
 * 来源: https://github.com/magicuidesign/magicui
 *       apps/www/registry/magicui/animated-list.tsx （MIT License）
 * 获取日期: 2026-08-24
 * 使用文件: src/components/magicui/animated-list.tsx（本文件）
 *
 * 本项目修改说明（均为任务规格的硬性要求，官方版本不含这些行为）：
 * - 新增鼠标悬停暂停：`isPaused` state，hover 时停止推进 index；
 * - 新增 `prefers-reduced-motion` 支持：命中时直接渲染全部项、不做动画；
 * - 默认 `delay` 提高到 2600ms（“速度缓慢，不循环得过快，一次只移动一项”）；
 * - 列表长度通过 `maxVisible` 限制可见项数，避免无限增长撑破卡片高度。
 */

import React, { useEffect, useMemo, useState, type ComponentPropsWithoutRef } from "react";
import { AnimatePresence, motion, type MotionProps } from "motion/react";

import { cn } from "../../lib/utils";

export function AnimatedListItem({ children }: { children: React.ReactNode }) {
  const animations: MotionProps = {
    initial: { scale: 0.94, opacity: 0 },
    animate: { scale: 1, opacity: 1, originY: 0 },
    exit: { scale: 0.94, opacity: 0 },
    transition: { type: "spring", stiffness: 260, damping: 32 },
  };

  return (
    <motion.div {...animations} layout className="mx-auto w-full">
      {children}
    </motion.div>
  );
}

export interface AnimatedListProps extends ComponentPropsWithoutRef<"div"> {
  children: React.ReactNode;
  /** 相邻两项之间的间隔（毫秒）。任务规格要求“速度缓慢”，默认 2600ms。 */
  delay?: number;
  maxVisible?: number;
  reducedMotion?: boolean;
}

export const AnimatedList = React.memo(
  ({
    children,
    className,
    delay = 2600,
    maxVisible = 4,
    reducedMotion = false,
    ...props
  }: AnimatedListProps) => {
    const [index, setIndex] = useState(0);
    const [isPaused, setIsPaused] = useState(false);
    const childrenArray = useMemo(() => React.Children.toArray(children), [children]);

    useEffect(() => {
      if (reducedMotion || isPaused) return undefined;

      const timeout = setTimeout(() => {
        setIndex((prevIndex) => (prevIndex + 1) % childrenArray.length);
      }, delay);

      return () => clearTimeout(timeout);
    }, [index, delay, childrenArray.length, isPaused, reducedMotion]);

    const itemsToShow = useMemo(() => {
      if (reducedMotion) {
        return childrenArray.slice(0, maxVisible).reverse();
      }
      const upperBound = Math.min(index + 1, childrenArray.length);
      const windowStart = Math.max(0, upperBound - maxVisible);
      return childrenArray.slice(windowStart, upperBound).reverse();
    }, [index, childrenArray, maxVisible, reducedMotion]);

    return (
      <div
        className={cn("flex flex-col items-center gap-2", className)}
        onMouseEnter={() => setIsPaused(true)}
        onMouseLeave={() => setIsPaused(false)}
        {...props}
      >
        <AnimatePresence>
          {itemsToShow.map((item) => (
            <AnimatedListItem key={(item as React.ReactElement).key}>{item}</AnimatedListItem>
          ))}
        </AnimatePresence>
      </div>
    );
  },
);

AnimatedList.displayName = "AnimatedList";
