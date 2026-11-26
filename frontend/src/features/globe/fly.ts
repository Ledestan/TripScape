/**
 * 行旅识景 TripScape / src/features/globe/fly
 * 创建日期: 2026-11-26
 *
 * 相机"落点"运镜的纯计算层，只回答两个问题：此刻距离多远、方向走了多少:
 *     1. 退开（0–0.3s）：先把镜头拉远，让观众看到"要去的这颗地球"
 *     2. 掠过（0.3–1.1s）：沿大圆方向转动，距离保持在最远处
 *     3. 贴地（1.1–1.6s）：方向锁定，距离收到目标值
 *
 * 与 three.js 解耦（只返回数字），因此可以被单测覆盖；
 * Globe.tsx 负责把 (dirT, radius) 应用到相机与四元数上。
 */

export const FLY_OUT_SEC = 0.3;
export const FLY_TRAVEL_SEC = 0.8;
export const FLY_DOWN_SEC = 0.5;
export const FLY_TOTAL_SEC = FLY_OUT_SEC + FLY_TRAVEL_SEC + FLY_DOWN_SEC;

/** 缓出：起步快、收尾稳 */
export function easeOutCubic(t: number): number {
  const x = Math.min(1, Math.max(0, t));
  return 1 - Math.pow(1 - x, 3);
}

/** 缓入缓出：跨越大半个地球时两端都不顿 */
export function easeInOutCubic(t: number): number {
  const x = Math.min(1, Math.max(0, t));
  return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2;
}

export interface FlyFrame {
  /** 半径（相机到地心距离） */
  radius: number;
  /** 方向插值进度：0 = 起点方向，1 = 终点方向 */
  dirT: number;
}

/**
 * 计算某一时刻的运镜状态
 *
 * 参数：
 *     elapsed : number，自起飞起的秒数
 *     fromR   : number，起点半径
 *     toR     : number，终点半径
 *
 * 返回：
 *     FlyFrame，含当前半径与方向插值进度
 */
export function flyAt(elapsed: number, fromR: number, toR: number): FlyFrame {
  const apex = Math.max(fromR, toR) * 1.22;

  if (elapsed <= 0) return { radius: fromR, dirT: 0 };
  if (elapsed >= FLY_TOTAL_SEC) return { radius: toR, dirT: 1 };

  if (elapsed < FLY_OUT_SEC) {
    return {
      radius: fromR + (apex - fromR) * easeOutCubic(elapsed / FLY_OUT_SEC),
      dirT: 0,
    };
  }

  if (elapsed < FLY_OUT_SEC + FLY_TRAVEL_SEC) {
    const t = (elapsed - FLY_OUT_SEC) / FLY_TRAVEL_SEC;
    return { radius: apex, dirT: easeInOutCubic(t) };
  }

  const t = (elapsed - FLY_OUT_SEC - FLY_TRAVEL_SEC) / FLY_DOWN_SEC;
  return { radius: apex + (toR - apex) * easeOutCubic(t), dirT: 1 };
}
