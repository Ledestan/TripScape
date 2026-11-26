/**
 * 行旅识景 TripScape / tests/frontend/fly.test
 * 创建日期: 2026-11-26
 *
 * 覆盖运镜三段的关键断言，完成:
 *     1. 起步先退开：前 0.3s 半径必须变大
 *     2. 掠过阶段：半径钉在最远处，方向插值从 0 递增到 1
 *     3. 贴地阶段：方向锁定，半径单调收到目标值
 *
 * 依赖:
 *     依赖库: vitest
 *
 * 用法:
 *     pnpm --dir frontend test
 */

import { describe, expect, it } from "vitest";
import { FLY_TOTAL_SEC, FLY_TRAVEL_SEC, flyAt } from "@/features/globe/fly";

const FROM = 2.6;
const TO = 1.6;

describe("flyAt 三段运镜", () => {
  it("t=0 停在起点", () => {
    const frame = flyAt(0, FROM, TO);
    expect(frame.radius).toBeCloseTo(FROM, 5);
    expect(frame.dirT).toBe(0);
  });

  it("前 0.3s 先退开：半径严格大于起点", () => {
    const early = flyAt(0.12, FROM, TO);
    const apex = Math.max(FROM, TO) * 1.22;
    expect(early.radius).toBeGreaterThan(FROM);
    expect(early.radius).toBeLessThan(apex);
    // 退开阶段方向不动，否则会边转边退，看起来像"打滑"
    expect(early.dirT).toBe(0);
  });

  it("掠过阶段半径保持最远，方向单调增加", () => {
    const apex = Math.max(FROM, TO) * 1.22;
    const a = flyAt(0.35, FROM, TO);
    const b = flyAt(0.7, FROM, TO);
    const c = flyAt(0.3 + FLY_TRAVEL_SEC - 0.01, FROM, TO);

    expect(a.radius).toBeCloseTo(apex, 5);
    expect(b.radius).toBeCloseTo(apex, 5);
    expect(a.dirT).toBeGreaterThan(0);
    expect(b.dirT).toBeGreaterThan(a.dirT);
    expect(c.dirT).toBeGreaterThan(b.dirT);
    expect(c.dirT).toBeLessThanOrEqual(1);
  });

  it("贴地阶段方向锁定，半径单调收敛到目标", () => {
    const start = flyAt(0.3 + FLY_TRAVEL_SEC, FROM, TO);
    const mid = flyAt(0.3 + FLY_TRAVEL_SEC + 0.25, FROM, TO);
    const end = flyAt(FLY_TOTAL_SEC, FROM, TO);

    expect(start.dirT).toBe(1);
    expect(mid.dirT).toBe(1);
    expect(mid.radius).toBeLessThan(start.radius);
    expect(end.radius).toBeCloseTo(TO, 5);
    expect(end.dirT).toBe(1);
  });

  it("超时后保持在终点，不会继续漂移", () => {
    const frame = flyAt(FLY_TOTAL_SEC + 3, FROM, TO);
    expect(frame.radius).toBeCloseTo(TO, 5);
    expect(frame.dirT).toBe(1);
  });

  it("由远及近总时长 1.6s（0.3 + 0.8 + 0.5）", () => {
    expect(FLY_TOTAL_SEC).toBeCloseTo(1.6, 5);
  });
});
