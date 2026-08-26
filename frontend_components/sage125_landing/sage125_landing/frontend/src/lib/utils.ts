import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/**
 * Magic UI 官方组件源码中普遍使用的 `cn` 工具函数（clsx + tailwind-merge）。
 * 来源: https://github.com/magicuidesign/magicui （MIT License）。
 * 详见项目根目录 THIRD_PARTY_NOTICES.md。
 */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}
