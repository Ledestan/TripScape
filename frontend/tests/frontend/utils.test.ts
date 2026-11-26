/**
 * 行旅识景 TripScape / tests/frontend/utils.test
 * 创建日期: 2026-10-09
 *
 * 该模块的工具函数与类型定义；对外导出见文件内 export。
 */

import { describe, it, expect } from "vitest";
import { cn } from "@/utils/cn";

describe("cn 工具", () => {
  it("合并类名", () => {
    expect(cn("a", "b")).toBe("a b");
  });

  it("条件类名", () => {
    expect(cn("base", { active: true, hidden: false })).toBe("base active");
  });

  it("tailwind-merge 去重冲突", () => {
    expect(cn("px-2", "px-4")).toBe("px-4");
  });
});
