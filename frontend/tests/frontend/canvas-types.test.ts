/**
 * 行旅识景 TripScape / tests/frontend/canvas-types.test
 * 创建日期: 2026-11-26
 *
 * 覆盖画布数据层的纯函数，完成:
 *     1. 工厂函数产出合法元素
 *     2. 图层排序（上移 / 下移 / 置顶 / 置底）
 *     3. 序列化时的夹取与 z 重排
 *     4. 容错解析：空对象、脏元素、超量元素
 *
 * 依赖:
 *     依赖库: vitest
 *
 * 用法:
 *     pnpm --dir frontend test
 */

import { describe, expect, it } from "vitest";
import {
  CANVAS_H,
  CANVAS_W,
  MAX_ELEMENTS,
  clampElement,
  createFragment,
  createPhoto,
  createText,
  emptyCanvas,
  moveLayer,
  parseCanvas,
  removeElement,
  serializeCanvas,
  updateElement,
} from "@/features/narrative/canvas-types";

describe("画布数据", () => {
  it("空画布固定 3:4", () => {
    const doc = emptyCanvas();
    expect(doc.width).toBe(CANVAS_W);
    expect(doc.height).toBe(CANVAS_H);
    expect(doc.ratio).toBe("3:4");
    expect(doc.elements).toEqual([]);
  });

  it("三种元素的 type 与默认尺寸正确", () => {
    expect(createText().type).toBe("text");
    expect(createPhoto("/uploads/a.jpg").type).toBe("photo");
    expect(createFragment({ title: "阿布辛贝神庙" }).type).toBe("fragment");
    expect(createText().fontSize).toBeGreaterThan(0);
  });

  it("更新元素只改目标", () => {
    const doc = { ...emptyCanvas(), elements: [createText("甲"), createText("乙")] };
    const next = updateElement(doc, doc.elements[0].id, { x: 200 });
    expect(next.elements[0].x).toBe(200);
    expect(next.elements[1].x).toBe(doc.elements[1].x);
  });

  it("删除元素", () => {
    const doc = { ...emptyCanvas(), elements: [createText("甲"), createText("乙")] };
    const next = removeElement(doc, doc.elements[0].id);
    expect(next.elements).toHaveLength(1);
  });

  it("图层上移 / 下移 / 置顶 / 置底", () => {
    const a = createText("A");
    const b = createText("B");
    const c = createText("C");
    const doc = { ...emptyCanvas(), elements: [a, b, c] };

    expect(moveLayer(doc, b.id, "up").elements.map((e) => e.id)).toEqual([a.id, c.id, b.id]);
    expect(moveLayer(doc, b.id, "down").elements.map((e) => e.id)).toEqual([b.id, a.id, c.id]);
    expect(moveLayer(doc, b.id, "top").elements.map((e) => e.id)).toEqual([a.id, c.id, b.id]);
    expect(moveLayer(doc, b.id, "bottom").elements.map((e) => e.id)).toEqual([b.id, a.id, c.id]);
  });

  it("越界数值被夹回安全区间", () => {
    const element = createText();
    const clamped = clampElement({
      ...element,
      x: -1e6,
      width: 1,
      scale: 99,
      rotation: 999,
      opacity: 0,
    });
    expect(clamped.x).toBe(-2000);
    expect(clamped.width).toBe(16);
    expect(clamped.scale).toBe(4);
    expect(clamped.rotation).toBe(180);
    expect(clamped.opacity).toBe(0.1);
  });

  it("序列化按数组顺序重排 z", () => {
    const a = { ...createText("A"), z: 9 };
    const b = { ...createText("B"), z: 9 };
    const doc = serializeCanvas({ ...emptyCanvas(), elements: [a, b] });
    expect(doc.elements.map((e) => e.z)).toEqual([0, 1]);
    expect(doc.ratio).toBe("3:4");
  });

  it("解析空值与脏数据返回可渲染空画布", () => {
    expect(parseCanvas(null).elements).toEqual([]);
    expect(parseCanvas({ elements: "nope" }).elements).toEqual([]);
    const dirty = parseCanvas({
      background: "not-a-color",
      elements: [{ type: "video" }, { type: "text", text: "保留我" }],
    });
    expect(dirty.elements).toHaveLength(1);
    expect(dirty.elements[0].type).toBe("text");
    expect(dirty.background).toBe(emptyCanvas().background);
  });

  it("超量元素被截断到上限", () => {
    const elements = Array.from({ length: MAX_ELEMENTS + 8 }, (_, i) =>
      createText(`第 ${i} 句`)
    );
    expect(parseCanvas({ elements }).elements).toHaveLength(MAX_ELEMENTS);
  });
});
