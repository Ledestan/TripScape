/**
 * 行旅识景 TripScape / src/features/narrative/canvas-types
 * 创建日期: 2026-11-26
 *
 * 手账画布的数据模型与纯函数，与渲染（react-konva）解耦，完成:
 *     1. CanvasDoc / CanvasElement：3:4 版式上的照片、文字、碎片卡片、贴纸、胶带
 *     2. 工厂函数：createText / createPhoto / createFragment / createSticker / createTape
 *     3. 编辑操作：updateElement / removeElement / moveLayer
 *     4. 序列化与容错解析：serializeCanvas / parseCanvas（与后端字段一一对应）
 *
 * 依赖:
 *     依赖库: 无（纯 TS，可被 vitest 直接覆盖）
 *
 * 用法:
 *     const doc = parseCanvas(journal.canvas);
 *     const next = moveLayer(doc, id, "up");
 *
 * 注意:
 *     1. 坐标以 720×960 的逻辑画布为准，渲染时统一整体缩放，不存屏幕像素。
 *     2. 后端 services/journal_canvas.py 是同一套字段的另一半：改字段要两边一起改。
 */

export const CANVAS_W = 720;
export const CANVAS_H = 960;
export const CANVAS_RATIO = "3:4" as const;
export const MAX_ELEMENTS = 40;

export type CanvasElementType = "photo" | "text" | "fragment" | "sticker" | "tape";

export type StickerVariant = "star" | "heart" | "circle" | "pin" | "burst";
export type TapePattern = "plain" | "stripe" | "dot";

export interface BaseElement {
  id: string;
  type: CanvasElementType;
  /** 左上角坐标（逻辑像素） */
  x: number;
  y: number;
  width: number;
  height: number;
  /** 旋转角度（度） */
  rotation: number;
  /** 统一缩放（拖拽缩放的备份值，渲染时叠加） */
  scale: number;
  opacity: number;
  /** 图层顺序：数组下标即层级 */
  z: number;
  /** 圆角（px） */
  cornerRadius: number;
  /** 投影开关 */
  shadow: boolean;
  /** 边框宽度（px，0 = 无边框） */
  borderWidth: number;
  borderColor: string;
}

export interface PhotoElement extends BaseElement {
  type: "photo";
  src: string;
  color?: string;
}

export interface TextElement extends BaseElement {
  type: "text";
  text: string;
  fontSize: number;
  color: string;
  align?: "left" | "center";
  fontFamily?: string;
  fontStyle?: "normal" | "italic";
}

export interface FragmentElement extends BaseElement {
  type: "fragment";
  title: string;
  snippet: string;
  year: string;
  landmarkId: number;
  color?: string;
}

export interface StickerElement extends BaseElement {
  type: "sticker";
  variant: StickerVariant;
  color: string;
}

export interface TapeElement extends BaseElement {
  type: "tape";
  color: string;
  pattern: TapePattern;
}

export type CanvasElement =
  | PhotoElement
  | TextElement
  | FragmentElement
  | StickerElement
  | TapeElement;

export interface CanvasDoc {
  version: 1;
  ratio: typeof CANVAS_RATIO;
  width: number;
  height: number;
  background: string;
  elements: CanvasElement[];
}

/** 空白画布（深色底，和产品整体气质一致） */
export function emptyCanvas(): CanvasDoc {
  return {
    version: 1,
    ratio: CANVAS_RATIO,
    width: CANVAS_W,
    height: CANVAS_H,
    background: "#12161d",
    elements: [],
  };
}

let seq = 0;
function nextId(prefix: string): string {
  seq += 1;
  return `${prefix}-${Date.now().toString(36)}-${seq}`;
}

/** 数字夹取，避免把 NaN / 越界值写进画布 */
export function clamp(value: number, low: number, high: number, fallback = 0): number {
  if (!Number.isFinite(value)) return fallback;
  return Math.min(high, Math.max(low, value));
}

function baseOf(
  type: CanvasElementType,
  x: number,
  y: number,
  width: number,
  height: number
): Omit<BaseElement, "id" | "type"> & { id: string; type: CanvasElementType } {
  return {
    id: nextId(type),
    type,
    x,
    y,
    width,
    height,
    rotation: 0,
    scale: 1,
    opacity: 1,
    z: 0,
    cornerRadius: 8,
    shadow: true,
    borderWidth: 0,
    borderColor: "#00000000",
  };
}

/** 新建文字元素 */
export function createText(text = "在这里写一句", x = 80, y = 120): TextElement {
  return {
    ...baseOf("text", x, y, 400, 80),
    type: "text",
    text,
    fontSize: 28,
    color: "#f5f2ea",
    align: "left",
    fontFamily: "serif",
    fontStyle: "normal",
    shadow: false,
  };
}

/** 新建照片元素 */
export function createPhoto(src: string, x = 120, y = 140): PhotoElement {
  return {
    ...baseOf("photo", x, y, 320, 240),
    type: "photo",
    src,
    color: "#1b1b1b",
  };
}

/** 新建碎片卡片元素（来自某个地标的叙事卡片） */
export function createFragment(
  data: { title: string; snippet?: string; year?: string; landmarkId?: number },
  x = 90,
  y = 300
): FragmentElement {
  return {
    ...baseOf("fragment", x, y, 360, 150),
    type: "fragment",
    title: data.title.slice(0, 60),
    snippet: (data.snippet || "").slice(0, 200),
    year: (data.year || "").slice(0, 16),
    landmarkId: data.landmarkId ?? 0,
    color: "#12161d",
    cornerRadius: 10,
  };
}

/** 新建贴纸元素 */
export function createSticker(
  variant: StickerVariant = "star",
  color = "#d9a441",
  x = 120,
  y = 140
): StickerElement {
  return {
    ...baseOf("sticker", x, y, 96, 96),
    type: "sticker",
    variant,
    color,
    cornerRadius: 0,
    shadow: false,
  };
}

/** 新建胶带元素 */
export function createTape(color = "#d6ba84", x = 80, y = 70): TapeElement {
  return {
    ...baseOf("tape", x, y, 200, 44),
    type: "tape",
    color,
    pattern: "plain",
    rotation: -6,
    cornerRadius: 2,
    shadow: false,
  };
}

/** 更新指定元素（不做夹取，交给 serializeCanvas 统一处理） */
export function updateElement(
  doc: CanvasDoc,
  id: string,
  patch: Partial<CanvasElement>
): CanvasDoc {
  return {
    ...doc,
    elements: doc.elements.map((element) =>
      element.id === id ? ({ ...element, ...patch } as CanvasElement) : element
    ),
  };
}

/** 删除元素 */
export function removeElement(doc: CanvasDoc, id: string): CanvasDoc {
  return { ...doc, elements: doc.elements.filter((element) => element.id !== id) };
}

/**
 * 调整图层顺序
 *
 * 参数：
 *     doc  : CanvasDoc
 *     id   : string，目标元素
 *     move : "up" | "down" | "top" | "bottom"
 *
 * 返回：
 *     CanvasDoc：数组顺序即渲染顺序（越靠后越上层）
 */
export function moveLayer(
  doc: CanvasDoc,
  id: string,
  move: "up" | "down" | "top" | "bottom"
): CanvasDoc {
  const index = doc.elements.findIndex((element) => element.id === id);
  if (index === -1) return doc;
  const elements = [...doc.elements];
  const [element] = elements.splice(index, 1);

  let target = index;
  if (move === "up") target = Math.min(elements.length, index + 1);
  if (move === "down") target = Math.max(0, index - 1);
  if (move === "top") target = elements.length;
  if (move === "bottom") target = 0;

  elements.splice(target, 0, element);
  return { ...doc, elements };
}

/** 把元素数值夹到安全区间（保存前统一调用） */
export function clampElement(element: CanvasElement): CanvasElement {
  return {
    ...element,
    x: clamp(element.x, -2000, CANVAS_W + 2000),
    y: clamp(element.y, -2000, CANVAS_H + 2000),
    width: clamp(element.width, 16, CANVAS_W * 2, 240),
    height: clamp(element.height, 16, CANVAS_H * 2, 160),
    rotation: clamp(element.rotation, -180, 180),
    scale: clamp(element.scale, 0.1, 4, 1),
    opacity: clamp(element.opacity, 0.1, 1, 1),
    cornerRadius: clamp(element.cornerRadius, 0, 120, 8),
    borderWidth: clamp(element.borderWidth, 0, 12, 0),
  };
}

/** 输出可直接提交给后端的结构（z 按数组顺序重排，元素做一次夹取） */
export function serializeCanvas(doc: CanvasDoc): CanvasDoc {
  const elements = doc.elements
    .slice(0, MAX_ELEMENTS)
    .map((element, index) => ({ ...clampElement(element), z: index }));
  return {
    version: 1,
    ratio: CANVAS_RATIO,
    width: CANVAS_W,
    height: CANVAS_H,
    background: doc.background,
    elements,
  };
}

/**
 * 容错解析：后端返回的 canvas 可能是空对象或旧结构，这里补默认值。
 *
 * 参数：
 *     raw : unknown，接口里的 canvas 字段
 *
 * 返回：
 *     CanvasDoc：永远可渲染的文档（解析失败时返回空画布）
 */
export function parseCanvas(raw: unknown): CanvasDoc {
  const base = emptyCanvas();
  if (!raw || typeof raw !== "object") return base;
  const source = raw as Partial<CanvasDoc>;
  if (!Array.isArray(source.elements)) return base;

  const allowed: CanvasElementType[] = ["photo", "text", "fragment", "sticker", "tape"];
  const elements = source.elements
    .filter((item): item is CanvasElement => {
      if (!item || typeof item !== "object") return false;
      return allowed.includes((item as CanvasElement).type);
    })
    .slice(0, MAX_ELEMENTS)
    .map((element, index) => clampElement({ ...element, z: index }));

  return {
    ...base,
    background:
      typeof source.background === "string" && /^#[0-9a-fA-F]{6}$/.test(source.background)
        ? source.background
        : base.background,
    elements,
  };
}
