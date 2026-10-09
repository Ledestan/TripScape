import { describe, it, expect } from "vitest";
import { z } from "zod";

// 与 Login 页一致的校验规则
const loginSchema = z.object({
  username: z.string().min(3, "用户名至少 3 个字符"),
  password: z.string().min(6, "密码至少 6 位"),
});

describe("登录表单校验（zod schema）", () => {
  it("合法输入通过", () => {
    const r = loginSchema.safeParse({ username: "demo", password: "demo123456" });
    expect(r.success).toBe(true);
  });

  it("用户名过短被拦截", () => {
    const r = loginSchema.safeParse({ username: "ab", password: "demo123456" });
    expect(r.success).toBe(false);
  });

  it("密码过短被拦截", () => {
    const r = loginSchema.safeParse({ username: "demo", password: "123" });
    expect(r.success).toBe(false);
  });
});
