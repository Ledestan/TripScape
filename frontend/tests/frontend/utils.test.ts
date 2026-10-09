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
