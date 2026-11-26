/**
 * 行旅识景 TripScape / tests/frontend/creation-types.test
 * 创建日期: 2026-11-26
 *
 * 覆盖旅行拼贴画布的数据层，完成:
 *     1. 空白文档固定 3:4 与元素上限
 *     2. 模板只产出合法元素，不含业务数据
 *     3. 素材 → 元素的五种类型
 *     4. 图层排序、夹取、序列化、脏数据解析
 *
 * 依赖:
 *     依赖库: vitest
 *
 * 用法:
 *     pnpm --dir frontend test
 */

import { describe, expect, it } from "vitest";
import {
  COMPOSE_H,
  COMPOSE_TEMPLATES,
  COMPOSE_W,
  MAX_ELEMENTS,
  TEXT_ASSET,
  clampElement,
  createFromAsset,
  createTemplate,
  createText,
  docSignature,
  emptyDoc,
  moveLayer,
  parseDoc,
  removeElement,
  serializeDoc,
  updateElement,
  type AssetItem,
} from "@/features/creation/types";

describe("旅行拼贴数据", () => {
  it("空白画布固定 3:4 且没有元素", () => {
    const doc = emptyDoc();
    expect(doc.width).toBe(COMPOSE_W);
    expect(doc.height).toBe(COMPOSE_H);
    expect(doc.ratio).toBe("3:4");
    expect(doc.elements).toEqual([]);
  });

  it("每套模板都产出合法元素且不含业务字段", () => {
    expect(COMPOSE_TEMPLATES.length).toBeGreaterThanOrEqual(3);
    for (const template of COMPOSE_TEMPLATES) {
      const doc = createTemplate(template.id);
      expect(doc.elements.length).toBeGreaterThan(0);
      for (const element of doc.elements) {
        expect(["photo", "fragment", "text", "sticker", "tape"]).toContain(element.kind);
        expect(element.z).toBeGreaterThanOrEqual(0);
        expect(JSON.stringify(element)).not.toContain("landmarkId");
      }
      expect(doc.background).toBe(template.background);
    }
  });

  it("素材转元素覆盖五种类型", () => {
    const assets: AssetItem[] = [
      { id: "a", label: "照片", kind: "photo", src: "/uploads/a.jpg" },
      { id: "b", label: "碎片", kind: "fragment", title: "地名", snippet: "一句", year: "2026" },
      { id: "c", label: "贴纸", kind: "sticker", variant: "heart", color: "#c05a4a" },
      { id: "d", label: "胶带", kind: "tape", color: "rgba(0,0,0,0.2)" },
      { id: "e", label: "文字", kind: "text", text: "一句" },
    ];
    expect(assets.map((asset) => createFromAsset(asset).kind)).toEqual([
      "photo",
      "fragment",
      "sticker",
      "tape",
      "text",
    ]);
    expect(TEXT_ASSET.kind).toBe("text");
  });

  it("图层排序上移/置顶生效", () => {
    const a = createText("A");
    const b = createText("B");
    const doc = { ...emptyDoc(), elements: [a, b] };
    expect(moveLayer(doc, a.id, "top").elements.map((element) => element.id)).toEqual([b.id, a.id]);
    expect(moveLayer(doc, a.id, "down").elements.map((element) => element.id)).toEqual([a.id, b.id]);
  });

  it("越界数值被夹取", () => {
    const element = clampElement({ ...createText(), x: -9999, width: 1, rotation: 999, opacity: 0 });
    expect(element.x).toBe(-300);
    expect(element.width).toBe(24);
    expect(element.rotation).toBe(180);
    expect(element.opacity).toBe(0.05);
  });

  it("序列化重排 z 并限制元素上限", () => {
    const elements = Array.from({ length: MAX_ELEMENTS + 5 }, (_, index) => ({
      ...createText(`第 ${index} 句`),
      z: 9,
    }));
    const doc = serializeDoc({ ...emptyDoc(), elements });
    expect(doc.elements).toHaveLength(MAX_ELEMENTS);
    expect(doc.elements.map((element) => element.z)).toEqual(
      Array.from({ length: MAX_ELEMENTS }, (_, index) => index)
    );
    expect(doc.ratio).toBe("3:4");
  });

  it("脏数据解析为可渲染文档", () => {
    expect(parseDoc(null).elements).toEqual([]);
    expect(parseDoc({ elements: "nope" }).elements).toEqual([]);
    const parsed = parseDoc({
      background: "not-a-color",
      elements: [{ kind: "video" }, { kind: "text", text: "保留我" }],
    });
    expect(parsed.elements).toHaveLength(1);
    expect(parsed.elements[0].kind).toBe("text");
    expect(parsed.background).toBe(emptyDoc().background);
  });

  it("签名能区分内容相同与不同", () => {
    const doc = { ...emptyDoc(), elements: [createText("同一句")] };
    const same = { ...emptyDoc(), elements: [{ ...doc.elements[0], z: 0 }] };
    expect(docSignature(doc)).toBe(docSignature(same));
    const changed = updateElement(doc, doc.elements[0].id, { rotation: 12 });
    expect(docSignature(changed)).not.toBe(docSignature(doc));
    expect(removeElement(doc, doc.elements[0].id).elements).toHaveLength(0);
  });
});
