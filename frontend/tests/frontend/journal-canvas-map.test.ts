/**
 * 行旅识景 TripScape / tests/frontend/journal-canvas-map.test
 * 创建日期: 2026-11-26
 *
 * 覆盖写手账的文档映射，完成:
 *     1. 编辑器文档 → 后端 canvas：kind 变 type、fragment 的 accent 变 color
 *     2. 后端 canvas → 编辑器文档：scale 折进宽高、颜色字段换回 accent
 *     3. 空画布与脏数据不崩
 *
 * 依赖:
 *     依赖库: vitest
 *
 * 用法:
 *     pnpm --dir frontend test
 */

import { describe, expect, it } from "vitest";
import {
  composeToJournalCanvas,
  journalCanvasToCompose,
} from "@/features/journal/canvas-map";
import {
  createFragment,
  createPhoto,
  createSticker,
  createTape,
  createText,
  emptyDoc,
} from "@/features/creation/types";
import { parseCanvas } from "@/features/narrative/canvas-types";

describe("写手账文档映射", () => {
  it("编辑器文档转后端 canvas：字段名对齐", () => {
    const doc = {
      ...emptyDoc("#f3ece1"),
      elements: [
        { ...createText("一句话"), id: "t1" },
        { ...createPhoto("/uploads/a.jpg"), id: "p1" },
        { ...createFragment({ title: "地名", snippet: "摘录", year: "2026" }), id: "f1" },
        { ...createSticker("heart", "#c05a4a"), id: "s1" },
        { ...createTape("#d6ba84"), id: "tp1" },
      ],
    };
    const canvas = composeToJournalCanvas(doc);
    expect(canvas.ratio).toBe("3:4");
    expect(canvas.elements.map((element) => element.type)).toEqual([
      "text",
      "photo",
      "fragment",
      "sticker",
      "tape",
    ]);
    const fragment = canvas.elements.find((element) => element.type === "fragment");
    expect(fragment && "color" in fragment ? fragment.color : "").toBe("#b8863b");
    // 后端不认识 kind 字段
    expect(JSON.stringify(canvas)).not.toContain('"kind"');
  });

  it("后端 canvas 转编辑器文档：scale 折进宽高", () => {
    const journal = {
      version: 1,
      ratio: "3:4",
      width: 720,
      height: 960,
      background: "#12161d",
      elements: [
        {
          id: "p1",
          type: "photo",
          src: "/uploads/b.jpg",
          x: 10,
          y: 20,
          width: 300,
          height: 200,
          rotation: 0,
          scale: 1.5,
          opacity: 1,
          z: 0,
          cornerRadius: 8,
          shadow: true,
          borderWidth: 0,
          borderColor: "#00000000",
        },
      ],
    };
    const doc = journalCanvasToCompose(journal);
    expect(doc.elements).toHaveLength(1);
    expect(doc.elements[0].width).toBe(450);
    expect(doc.elements[0].height).toBe(300);
    expect(doc.background).toBe("#12161d");
  });

  it("往返一轮不丢元素数量与类型", () => {
    const doc = {
      ...emptyDoc(),
      elements: [
        { ...createText("往返"), id: "t1" },
        { ...createSticker("star"), id: "s1" },
      ],
    };
    const back = journalCanvasToCompose(composeToJournalCanvas(doc));
    expect(back.elements.map((element) => element.kind)).toEqual(["text", "sticker"]);
  });

  it("空画布与脏数据不崩", () => {
    expect(journalCanvasToCompose(null).elements).toEqual([]);
    expect(parseCanvas(null).elements).toEqual([]);
    expect(journalCanvasToCompose({ elements: [{ type: "video" }] }).elements).toEqual([]);
  });
});
