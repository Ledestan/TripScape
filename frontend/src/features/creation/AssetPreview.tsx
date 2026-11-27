/**
 * 行旅识景 TripScape / 素材预览
 *
 * 素材栏与图层列表的缩略图，完成:
 *     1. 贴纸按真实形状（星/心/圆/定位/爆炸）与颜色绘制，不再统一画一颗星
 *     2. 胶带按真实纹理（纯色/条纹/点纹）与颜色绘制
 *     3. 照片直接显示缩略图，背景显示色块，文字显示字形
 *
 * 依赖:
 *     依赖库: lucide-react
 *
 * 用法:
 *     <AssetThumb asset={asset} />        // 素材栏
 *     <AssetMini element={element} />     // 图层列表
 *
 * 注意:
 *     预览必须和画布上渲染的样式同源（同一套 variant / pattern / color），
 *     否则会出现"预览和放上去的不一样"的问题。
 */

import { ImagePlus, Type } from "lucide-react";

import type { AssetItem, ComposeElement, StickerVariant } from "./types";

/** 生成星形多边形顶点 */
function starPoints(count: number, innerRatio: number, radius = 18, center = 20): string {
  const points: string[] = [];
  for (let index = 0; index < count * 2; index += 1) {
    const radiusPoint = index % 2 === 0 ? radius : radius * innerRatio;
    const angle = (Math.PI / count) * index - Math.PI / 2;
    points.push(`${(center + radiusPoint * Math.cos(angle)).toFixed(2)},${(center + radiusPoint * Math.sin(angle)).toFixed(2)}`);
  }
  return points.join(" ");
}

/** 贴纸形状：和画布上的 StickerNode 对应 */
export function StickerGlyph({
  variant,
  color,
  size = 32,
}: {
  variant: StickerVariant;
  color: string;
  size?: number;
}) {
  const shape = (() => {
    if (variant === "circle") {
      return <circle cx={20} cy={20} r={17} fill={color} opacity={0.92} />;
    }
    if (variant === "heart") {
      return (
        <path
          d="M20 34 C6 24 4 12 12 9 C16 7 19 10 20 13 C21 10 24 7 28 9 C36 12 34 24 20 34 Z"
          fill={color}
        />
      );
    }
    if (variant === "pin") {
      return (
        <>
          <path
            d="M20 3 C13 3 8 8 8 15 C8 24 20 37 20 37 C20 37 32 24 32 15 C32 8 27 3 20 3 Z"
            fill={color}
          />
          <circle cx={20} cy={14} r={4} fill="rgba(255,255,255,0.85)" />
        </>
      );
    }
    if (variant === "burst") {
      return <polygon points={starPoints(12, 0.72)} fill={color} />;
    }
    return <polygon points={starPoints(5, 0.46)} fill={color} />;
  })();

  return (
    <svg width={size} height={size} viewBox="0 0 40 40" aria-hidden>
      {shape}
    </svg>
  );
}

/** 胶带纹理：和画布上的 TapeNode 对应 */
export function TapeSwatch({
  color,
  pattern,
  className = "",
}: {
  color: string;
  pattern: "plain" | "stripe" | "dot";
  className?: string;
}) {
  return (
    <span
      className={`relative block overflow-hidden rounded-sm ${className}`}
      style={{ backgroundColor: color }}
    >
      {pattern === "stripe" && (
        <span
          className="absolute inset-0"
          style={{
            backgroundImage:
              "repeating-linear-gradient(90deg, transparent 0 7px, rgba(255,255,255,0.4) 7px 11px)",
          }}
        />
      )}
      {pattern === "dot" && (
        <span
          className="absolute inset-0"
          style={{
            backgroundImage:
              "radial-gradient(rgba(255,255,255,0.55) 1.4px, transparent 1.5px)",
            backgroundSize: "7px 7px",
          }}
        />
      )}
    </span>
  );
}

/** 素材缩略图（素材栏用） */
export function AssetThumb({ asset }: { asset: AssetItem }) {
  if (asset.kind === "photo") {
    return asset.src ? (
      <img src={asset.src} alt="" className="h-full w-full object-cover" />
    ) : (
      <ImagePlus className="h-4 w-4 text-muted-foreground" />
    );
  }
  if (asset.kind === "background") {
    return (
      <span
        className="h-full w-full"
        style={{ backgroundColor: asset.color || "#f3ece1" }}
        aria-label={`底色 ${asset.color || ""}`}
      />
    );
  }
  if (asset.kind === "sticker") {
    return <StickerGlyph variant={asset.variant || "star"} color={asset.color || "#d9a441"} />;
  }
  if (asset.kind === "tape") {
    return (
      <TapeSwatch
        color={asset.color || "#d6ba84"}
        pattern={asset.pattern || "plain"}
        className="h-4 w-14"
      />
    );
  }
  return <Type className="h-4 w-4 text-muted-foreground" />;
}

/** 图层行缩略（图层列表用） */
export function AssetMini({ element }: { element: ComposeElement }) {
  if (element.kind === "photo") {
    return element.src ? (
      <img src={element.src} alt="" className="h-4 w-4 shrink-0 rounded-sm object-cover" />
    ) : (
      <span className="h-4 w-4 shrink-0 rounded-sm bg-muted" />
    );
  }
  if (element.kind === "sticker") {
    return <StickerGlyph variant={element.variant} color={element.color} size={16} />;
  }
  if (element.kind === "tape") {
    return <TapeSwatch color={element.color} pattern={element.pattern} className="h-2.5 w-4" />;
  }
  return <span className="shrink-0 text-[10px] text-muted-foreground">T</span>;
}