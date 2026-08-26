/*
 * Bento Grid —— 12 列网格 + 卡片容器。
 *
 * 来源: https://github.com/magicuidesign/magicui
 *       apps/www/registry/magicui/bento-grid.tsx （MIT License）
 * 获取日期: 2026-08-24
 * 使用文件: src/components/magicui/bento-grid.tsx（本文件）
 *
 * 本项目修改说明：
 * - 移除官方版本中的 Icon（@radix-ui/react-icons）与 CTA 箭头按钮
 *   （本任务要求能力卡内 0 个图标，且不需要跳转按钮）；
 * - 移除对 shadcn/ui Button 组件的依赖（本工程未引入 shadcn 组件体系）；
 * - BentoCard 简化为纯网格定位容器，网格列宽/行高由调用方通过 className
 *   传入，以匹配任务规格的 12 列布局与逐卡尺寸要求；
 * - 移除官方版本自带的白色背景/浅色边框/阴影——真正的卡片视觉（深色玻璁
 *   背景/边框/圆角/阴影）现在统一由内部的 CardShell（.glass-card）提供，
 *   BentoCard 只负责网格布局，避免出现两层背景叠加或"纯白卡片"。
 */

import type { ComponentPropsWithoutRef, ReactNode } from "react";

import { cn } from "../../lib/utils";

interface BentoGridProps extends ComponentPropsWithoutRef<"div"> {
  children: ReactNode;
  className?: string;
}

export function BentoGrid({ children, className, ...props }: BentoGridProps) {
  return (
    <div
      className={cn("grid w-full grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-12", className)}
      {...props}
    >
      {children}
    </div>
  );
}

interface BentoCardProps extends ComponentPropsWithoutRef<"div"> {
  className?: string;
  children: ReactNode;
}

export function BentoCard({ className, children, ...props }: BentoCardProps) {
  return (
    <div className={cn("relative flex flex-col", className)} {...props}>
      {children}
    </div>
  );
}
