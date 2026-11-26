/**
 * 行旅识景 TripScape / src/features/journal/canvas-map
 * 创建日期: 2026-11-26
 *
 * 在「编辑器文档」与「后端画布文档」之间做映射，完成:
 *     1. composeToJournalCanvas：把创作画布（kind 字段）转成 /api/journals 的 canvas（type 字段）
 *     2. journalCanvasToCompose：把已保存的画布转回编辑器文档（编辑已有手账）
 *     3. scale 折叠：编辑器没有 scale，读取时把 scale 乘进宽高，避免尺寸丢失
 *     4. 手账只收照片/文字/贴纸/胶带；文章摘录不进画布
 *
 * 依赖:
 *     依赖库: 无（纯 TS）
 *
 * 用法:
 *     const canvas = composeToJournalCanvas(doc);
 *     const doc = journalCanvasToCompose(journal.canvas);
 *
 * 注意:
 *     1. 后端只认 type / photo / text / fragment / sticker / tape 这套字段，映射必须严格对齐。
 *     2. 颜色字段名两边不同：editor 用 accent，后端用 color（fragment）。
 */

import { emptyCanvas, parseCanvas, type CanvasDoc as JournalCanvasDoc, type CanvasElement } from "@/features/narrative/canvas-types";
import {
  emptyDoc,
  type ComposeDoc,
  type ComposeElement,
} from "@/features/creation/types";

/** 编辑器文档 → 后端画布 */
export function composeToJournalCanvas(doc: ComposeDoc): JournalCanvasDoc {
  const base = emptyCanvas();
  const elements: CanvasElement[] = doc.elements.map((element, index) => {
    const common = {
      id: element.id,
      x: element.x,
      y: element.y,
      width: element.width,
      height: element.height,
      rotation: element.rotation,
      scale: 1,
      opacity: element.opacity,
      z: index,
      cornerRadius: element.cornerRadius,
      shadow: element.shadow,
      borderWidth: element.borderWidth,
      borderColor: element.borderColor,
    };

    if (element.kind === "text") {
      return {
        ...common,
        type: "text",
        text: element.text,
        fontSize: element.fontSize,
        color: element.color,
        align: element.align,
        fontFamily: element.fontFamily,
        fontStyle: element.fontStyle,
      };
    }
    if (element.kind === "photo") {
      return { ...common, type: "photo", src: element.src };
    }
    if (element.kind === "sticker") {
      return { ...common, type: "sticker", variant: element.variant, color: element.color };
    }
    return { ...common, type: "tape", color: element.color, pattern: element.pattern };
  });

  return { ...base, background: doc.background, elements };
}

/** 后端画布 → 编辑器文档（编辑已有手账时回填） */
export function journalCanvasToCompose(raw: unknown): ComposeDoc {
  const canvas = parseCanvas(raw);
  const base = emptyDoc(canvas.background);
  if (canvas.elements.length === 0) return base;

  const elements: ComposeElement[] = canvas.elements.map((element) => {
    // 编辑器没有 scale：把缩放折进宽高，避免读入后尺寸变小
    const width = Math.round(element.width * element.scale);
    const height = Math.round(element.height * element.scale);
    const common = {
      id: element.id,
      x: element.x,
      y: element.y,
      width,
      height,
      rotation: element.rotation,
      opacity: element.opacity,
      z: element.z,
      cornerRadius: element.cornerRadius,
      shadow: element.shadow,
      borderWidth: element.borderWidth,
      borderColor: element.borderColor,
    };

    if (element.type === "text") {
      return {
        ...common,
        kind: "text",
        text: element.text,
        fontSize: element.fontSize,
        color: element.color,
        fontFamily: element.fontFamily || "serif",
        fontStyle: element.fontStyle || "normal",
        align: element.align || "left",
      };
    }
    if (element.type === "photo") {
      return { ...common, kind: "photo", src: element.src };
    }
    if (element.type === "sticker") {
      return { ...common, kind: "sticker", variant: element.variant, color: element.color };
    }
    return {
      ...common,
      kind: "tape",
      color: element.color,
      pattern: element.pattern,
    };
  });

  return { ...base, elements };
}
