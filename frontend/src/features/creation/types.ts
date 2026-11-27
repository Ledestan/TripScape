/**
 * 行旅识景 TripScape / src/features/creation/types
 *
 * 旅行拼贴画布（CreationComposeWindow）的数据模型与纯函数，完成:
 *     1. ComposeDoc / ComposeElement：照片、文字、贴纸、胶带四类元素
 *     2. 素材插槽 AssetSlots：由宿主注入，窗口自己不请求接口
 *     3. 模板：2—3 套只含图形与占位的版面组合
 *     4. 文档操作：增删改、图层排序、夹取、序列化、脏检查
 *
 * 依赖:
 *     依赖库: 无（纯 TS，vitest 可直接覆盖）
 *
 * 用法:
 *     const doc = createTemplate("postcard");
 *     const next = updateElement(doc, id, { rotation: 15 });
 *
 * 注意:
 *     1. 坐标按 720×960 逻辑画布存，渲染时整体缩放，导出始终按原尺寸 3:4。
 *     2. 这个模块不碰后端：落库、审核、足迹都由宿主在 onSave 里处理。
 */

export const COMPOSE_W = 720;
export const COMPOSE_H = 960;
export const COMPOSE_RATIO = "3:4" as const;
export const MAX_ELEMENTS = 60;
/** 历史步数上限（规格要求至少 20 步） */
export const HISTORY_LIMIT = 30;

export type ComposeKind = "photo" | "fragment" | "text" | "sticker" | "tape";

export type StickerVariant = "star" | "heart" | "circle" | "pin" | "burst";

export interface ComposeBase {
  id: string;
  kind: ComposeKind;
  x: number;
  y: number;
  width: number;
  height: number;
  rotation: number;
  opacity: number;
  /** 图层：数组下标即层级，越大越靠上 */
  z: number;
  cornerRadius: number;
  shadow: boolean;
  borderWidth: number;
  borderColor: string;
}

export interface PhotoElement extends ComposeBase {
  kind: "photo";
  src: string;
}

export interface TextElement extends ComposeBase {
  kind: "text";
  text: string;
  fontSize: number;
  color: string;
  fontFamily: string;
  fontStyle: "normal" | "italic";
  align: "left" | "center";
}

export interface StickerElement extends ComposeBase {
  kind: "sticker";
  variant: StickerVariant;
  color: string;
}

export interface TapeElement extends ComposeBase {
  kind: "tape";
  color: string;
  pattern: "plain" | "stripe" | "dot";
}

export type ComposeElement =
  | PhotoElement
  | TextElement
  | StickerElement
  | TapeElement;

export interface ComposeDoc {
  version: 1;
  ratio: typeof COMPOSE_RATIO;
  width: number;
  height: number;
  background: string;
  elements: ComposeElement[];
}

/** 宿主注入的素材：图片地址可选，没有 src 时按内置图形渲染 */
export interface AssetItem {
  id: string;
  label: string;
  kind: ComposeKind | "background";
  src?: string;
  variant?: StickerVariant;
  color?: string;
  pattern?: TapeElement["pattern"];
  /** 文字素材的默认内容 */
  text?: string;
}

export interface AssetSlots {
  photos?: AssetItem[];
  stickers?: AssetItem[];
  tapes?: AssetItem[];
  backgrounds?: AssetItem[];
}

/** 文字不是"素材"，用这个常量单独生成一个文字元素 */
export const TEXT_ASSET: AssetItem = {
  id: "compose-text",
  label: "加一段文字",
  kind: "text",
  text: "在这里写一句",
};

export const ASSET_TABS: { key: keyof AssetSlots; label: string }[] = [
  { key: "photos", label: "照片" },
  { key: "stickers", label: "贴纸" },
  { key: "tapes", label: "胶带" },
  { key: "backgrounds", label: "底纹" },
];

let seq = 0;
function nextId(kind: string): string {
  seq += 1;
  return `${kind}-${Date.now().toString(36)}-${seq}`;
}

/** 数字夹取，避免 NaN 或越界值写进画布 */
export function clamp(value: number, low: number, high: number, fallback = 0): number {
  if (!Number.isFinite(value)) return fallback;
  return Math.min(high, Math.max(low, value));
}

export function emptyDoc(background = "#f3ece1"): ComposeDoc {
  return {
    version: 1,
    ratio: COMPOSE_RATIO,
    width: COMPOSE_W,
    height: COMPOSE_H,
    background,
    elements: [],
  };
}

/** 元素的公共默认值（新增元素时按类型覆盖） */
function baseOf(kind: ComposeKind, x: number, y: number, width: number, height: number): ComposeBase {
  return {
    id: nextId(kind),
    kind,
    x,
    y,
    width,
    height,
    rotation: 0,
    opacity: 1,
    z: 0,
    cornerRadius: 6,
    shadow: true,
    borderWidth: 0,
    borderColor: "rgba(0,0,0,0.18)",
  };
}

export function createText(text = "写一句旅行里的话", x = 90, y = 120): TextElement {
  return {
    ...baseOf("text", x, y, 420, 90),
    kind: "text",
    text,
    fontSize: 30,
    color: "#2b2620",
    fontFamily: "serif",
    fontStyle: "normal",
    align: "left",
    shadow: false,
  };
}

export function createPhoto(src: string, x = 90, y = 80): PhotoElement {
  return { ...baseOf("photo", x, y, 340, 420), kind: "photo", src };
}

export function createSticker(
  variant: StickerVariant = "star",
  color = "#d9a441",
  x = 120,
  y = 120
): StickerElement {
  return {
    ...baseOf("sticker", x, y, 96, 96),
    kind: "sticker",
    variant,
    color,
    cornerRadius: 0,
    shadow: false,
  };
}

export function createTape(color = "rgba(214,186,132,0.62)", x = 80, y = 60): TapeElement {
  return {
    ...baseOf("tape", x, y, 200, 46),
    kind: "tape",
    color,
    pattern: "plain",
    rotation: -8,
    cornerRadius: 2,
    shadow: false,
  };
}

/** 素材 → 元素：素材栏点击、拖入都走这里 */
export function createFromAsset(asset: AssetItem, index = 0): ComposeElement {
  const offset = (index % 6) * 24;
  if (asset.kind === "photo") return createPhoto(asset.src || "", 80 + offset, 90 + offset);
  if (asset.kind === "sticker")
    return createSticker(asset.variant || "star", asset.color || "#d9a441", 110 + offset, 140 + offset);
  if (asset.kind === "tape") {
    const tape = createTape(asset.color || undefined);
    return { ...tape, pattern: asset.pattern || "plain", x: 80 + offset, y: 70 + offset };
  }
  return createText(asset.text || asset.label, 90 + offset, 140 + offset);
}

export function updateElement(
  doc: ComposeDoc,
  id: string,
  patch: Partial<ComposeElement>
): ComposeDoc {
  return {
    ...doc,
    elements: doc.elements.map((element) =>
      element.id === id ? ({ ...element, ...patch } as ComposeElement) : element
    ),
  };
}

export function removeElement(doc: ComposeDoc, id: string): ComposeDoc {
  return { ...doc, elements: doc.elements.filter((element) => element.id !== id) };
}

/**
 * 图层排序
 *
 * 参数：
 *     doc  : ComposeDoc
 *     id   : string，目标元素
 *     move : "up" | "down" | "top" | "bottom"
 *
 * 返回：
 *     ComposeDoc：数组顺序即渲染顺序
 */
export function moveLayer(doc: ComposeDoc, id: string, move: "up" | "down" | "top" | "bottom"): ComposeDoc {
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

/** 元素夹取：位置留出画布外一点余量，尺寸与角度保持在可用区间 */
export function clampElement(element: ComposeElement): ComposeElement {
  return {
    ...element,
    x: clamp(element.x, -300, COMPOSE_W + 300),
    y: clamp(element.y, -300, COMPOSE_H + 300),
    width: clamp(element.width, 24, COMPOSE_W * 2, 200),
    height: clamp(element.height, 24, COMPOSE_H * 2, 120),
    rotation: clamp(element.rotation, -180, 180),
    opacity: clamp(element.opacity, 0.05, 1, 1),
    cornerRadius: clamp(element.cornerRadius, 0, 120, 0),
    borderWidth: clamp(element.borderWidth, 0, 12, 0),
  };
}

/** 导出/保存前的规范化：夹取 + 重排 z + 补齐版式字段 */
export function serializeDoc(doc: ComposeDoc): ComposeDoc {
  return {
    version: 1,
    ratio: COMPOSE_RATIO,
    width: COMPOSE_W,
    height: COMPOSE_H,
    background: doc.background,
    elements: doc.elements
      .slice(0, MAX_ELEMENTS)
      .map((element, index) => ({ ...clampElement(element), z: index })),
  };
}

/** 容错解析：宿主的 initialElements 可能是旧结构或脏数据 */
export function parseDoc(raw: unknown, background = "#f3ece1"): ComposeDoc {
  const base = emptyDoc(background);
  if (!raw || typeof raw !== "object") return base;
  const source = raw as Partial<ComposeDoc>;
  if (!Array.isArray(source.elements)) return base;
  const allowed: ComposeKind[] = ["photo", "fragment", "text", "sticker", "tape"];
  const elements = source.elements
    .filter((item): item is ComposeElement => {
      if (!item || typeof item !== "object") return false;
      return allowed.includes((item as ComposeElement).kind);
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

/** 脏检查用的签名：只比内容，不比引用 */
export function docSignature(doc: ComposeDoc): string {
  return JSON.stringify(serializeDoc(doc));
}

/** 模板：只含图形与占位文字，不含任何业务数据 */
export interface ComposeTemplate {
  id: string;
  name: string;
  description: string;
  background: string;
  build: () => ComposeElement[];
}

export const COMPOSE_TEMPLATES: ComposeTemplate[] = [
  {
    id: "postcard",
    name: "明信片",
    description: "一张主图 + 手写体标题 + 一枚邮戳贴纸",
    background: "#f4ecdf",
    build: () => {
      const photo = { ...createPhoto("", 96, 90), width: 528, height: 400 };
      const title = { ...createText("在旅途中，写给未来的自己", 96, 540), fontSize: 28 };
      const line = { ...createText("—— 一个普通下午的旅行笔记", 96, 600), fontSize: 16 };
      const stamp = { ...createSticker("burst", "#c8874a", 520, 88), width: 74, height: 74 };
      return [photo, title, line, stamp];
    },
  },
  {
    id: "filmstrip",
    name: "胶片条",
    description: "三格竖排照片 + 上下胶带 + 一行片名",
    background: "#14181f",
    build: () => {
      const top = { ...createPhoto("", 96, 96), width: 240, height: 168 };
      const middle = { ...createPhoto("", 96, 292), width: 240, height: 168 };
      const bottom = { ...createPhoto("", 96, 488), width: 240, height: 168 };
      const capTop = { ...createTape("rgba(214,186,132,0.78)", 72, 66), width: 288, height: 26, rotation: -1 };
      const capBottom = { ...createTape("rgba(214,186,132,0.78)", 72, 686), width: 288, height: 26, rotation: 1 };
      const caption = {
        ...createText("胶片上的三格：光、影、和那天下午", 96, 730),
        fontSize: 20,
        color: "#f5f2ea",
        width: 460,
      };
      return [top, middle, bottom, capTop, capBottom, caption];
    },
  },
  {
    id: "ticket",
    name: "票根",
    description: "大字票头 + 小图 + 撕线胶带，横构图",
    background: "#f4ecdf",
    build: () => {
      const tape = { ...createTape("rgba(198,166,110,0.72)", 60, 54), width: 220, height: 32, rotation: -2 };
      const heading = { ...createText("入场券", 60, 110), fontSize: 46, width: 340 };
      const sub = { ...createText("NO. 0001 · 一次旅行", 60, 178), fontSize: 15, color: "#6b5d4a" };
      const photo = { ...createPhoto("", 420, 104), width: 230, height: 160, rotation: 3 };
      const stamp = { ...createSticker("circle", "#b8863b", 600, 70), width: 56, height: 56 };
      const divider = { ...createTape("rgba(120,90,60,0.28)", 60, 330), width: 520, height: 18 };
      const note = {
        ...createText("撕下这一半，留给下次", 60, 372),
        fontSize: 18,
        fontStyle: "italic" as const,
        color: "#6b5d4a",
        width: 420,
      };
      return [tape, heading, sub, photo, stamp, divider, note];
    },
  },
];

/** 按模板 id 生成一份文档 */
export function createTemplate(id: string): ComposeDoc {
  const template = COMPOSE_TEMPLATES.find((item) => item.id === id) || COMPOSE_TEMPLATES[0];
  const doc = emptyDoc(template.background);
  return { ...doc, elements: template.build().map((element, index) => ({ ...element, z: index })) };
}

/** 空态提示文案（画布中央） */
export const EMPTY_HINT = "从左侧拖入照片，或先加一段文字";