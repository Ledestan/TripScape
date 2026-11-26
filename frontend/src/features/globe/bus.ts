/**
 * 行旅识景 TripScape / src/features/globe/bus
 * 创建日期: 2026-11-26
 *
 * 地球与外部浮窗之间的事件总线：一个极小的发布/订阅层，负责:
 *     1. flyTo：让地球飞到某个经纬度（搜索结果、消息卡片、地标页都会用）
 *     2. setBearing / resetView：只调整相机方位与距离，不改变看向的地点
 *     3. hasUserBearing：控件据此判断是否停用自转
 *
 * 为什么单独一个文件：
 *     Globe.tsx 会引入 three.js / @react-three/fiber（数百 KB）。
 *     以前外部模块为了拿这个总线而 import Globe，导致个人主页、消息条、
 *     搜索结果等分包都被迫打包一份 3D 引擎（实测 857 KB）。抽出来之后，
 *     这些模块只依赖几十行事件代码。
 */

export type FlyPayload = { lat: number; lon: number; id?: number; dist?: number };

const flyListeners = new Set<(payload: FlyPayload) => void>();
const bearingListeners = new Set<(deg: number) => void>();
const resetViewListeners = new Set<() => void>();
const bearingChangeHooks = new Set<(hasUserBearing: boolean) => void>();

/** 用户是否设定过方位（设定后本次会话停用自转，重置后恢复） */
let userSetBearing = false;
/** 是否有浮窗盖在地球上：有则停自转，省 GPU 也避免隔着面板看见地球在动 */
let overlayOpen = false;
const overlayHooks = new Set<(open: boolean) => void>();

export const globeBus = {
  /** 浮窗开合（叙事档案 / 手记）：打开时暂停自转，并让 Canvas 转入按需渲染 */
  setOverlay(open: boolean) {
    if (overlayOpen === open) return;
    overlayOpen = open;
    overlayHooks.forEach((fn) => fn(open));
  },
  /** 当前是否有浮窗盖在地球上 */
  get hasOverlay() {
    return overlayOpen;
  },
  /** 飞到地标（点搜索结果/消息卡片/地标页） */
  flyTo(lat: number, lon: number, id?: number, dist?: number) {
    flyListeners.forEach((fn) => fn({ lat, lon, id, dist }));
  },
  /** 设定方向角（0-360，真实旋转相机方位） */
  setBearing(deg: number) {
    userSetBearing = true;
    bearingChangeHooks.forEach((fn) => fn(true));
    bearingListeners.forEach((fn) => fn(deg));
  },
  /** 重置：只恢复方向角与缩放距离，不改变看向的地点 */
  resetView() {
    userSetBearing = false;
    bearingChangeHooks.forEach((fn) => fn(false));
    resetViewListeners.forEach((fn) => fn());
  },
  /** 当前是否处于用户设定方位状态（控件禁用自转用） */
  get hasUserBearing() {
    return userSetBearing;
  },
};

/** 订阅"飞到某点"，返回取消函数（供 Canvas 内部注册） */
export function subscribeFly(fn: (payload: FlyPayload) => void): () => void {
  flyListeners.add(fn);
  return () => flyListeners.delete(fn);
}

/** 订阅"设定方位角"，返回取消函数 */
export function subscribeBearing(fn: (deg: number) => void): () => void {
  bearingListeners.add(fn);
  return () => bearingListeners.delete(fn);
}

/** 订阅"重置视角"，返回取消函数 */
export function subscribeResetView(fn: () => void): () => void {
  resetViewListeners.add(fn);
  return () => resetViewListeners.delete(fn);
}

/** 订阅"用户是否设定过方位"的变化，返回取消函数 */
export function subscribeBearingChange(fn: (hasUserBearing: boolean) => void): () => void {
  bearingChangeHooks.add(fn);
  return () => bearingChangeHooks.delete(fn);
}

/** 订阅"浮窗开合"，返回取消函数（Canvas 据此切换按需渲染） */
export function subscribeOverlay(fn: (open: boolean) => void): () => void {
  overlayHooks.add(fn);
  return () => overlayHooks.delete(fn);
}
