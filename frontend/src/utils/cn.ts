/**
 * 行旅识景 TripScape / src/utils/cn
 * 创建日期: 2026-10-09
 *
 * 该模块的工具函数与类型定义；对外导出见文件内 export。
 */

import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
