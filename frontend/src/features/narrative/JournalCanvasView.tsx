/**
 * 行旅识景 TripScape / 手账画布只读渲染
 *
 * 把已保存的 3:4 手账画布渲染成只读的一页，完成:
 *     1. 五类元素：照片 / 文字 / 贴纸 / 胶带（含圆角、投影、边框）
 *     2. 按容器宽度等比缩放，永远保持 3:4
 *     3. 不响应拖拽与缩放，只用于查看/分享
 *
 * 依赖:
 *     依赖库: react-konva, konva
 *
 * 用法:
 *     <JournalCanvasView canvas={journal.canvas} />
 *
 * 注意:
 *     元素极少（≤40），这里不做虚拟化；容器宽度变化时整体重算 scale。
 */

import { useEffect, useRef, useState } from "react";
import {
  Circle,
  Group,
  Image as KonvaImage,
  Layer,
  Line,
  Path,
  Rect,
  Star,
  Stage,
  Text,
} from "react-konva";

import {
  CANVAS_H,
  CANVAS_W,
  parseCanvas,
  type CanvasElement,
  type PhotoElement,
  type StickerElement,
  type TapeElement,
  type TextElement,
} from "./canvas-types";

function useImage(src: string): HTMLImageElement | null {
  const [image, setImage] = useState<HTMLImageElement | null>(null);
  useEffect(() => {
    if (!src) {
      setImage(null);
      return;
    }
    const img = new window.Image();
    img.crossOrigin = "anonymous";
    let alive = true;
    img.onload = () => {
      if (alive) setImage(img);
    };
    img.src = src;
    return () => {
      alive = false;
      img.onload = null;
    };
  }, [src]);
  return image;
}

function PhotoNode({ element }: { element: PhotoElement }) {
  const image = useImage(element.src);
  return (
    <Group clipX={0} clipY={0} clipWidth={element.width} clipHeight={element.height}>
      <Rect
        width={element.width}
        height={element.height}
        cornerRadius={element.cornerRadius}
        fill="#1b1b1b"
        stroke={element.borderWidth ? element.borderColor : undefined}
        strokeWidth={element.borderWidth}
      />
      {image && (
        <KonvaImage
          image={image}
          width={element.width}
          height={element.height}
          cornerRadius={element.cornerRadius}
        />
      )}
    </Group>
  );
}

function TextNode({ element }: { element: TextElement }) {
  return (
    <Text
      text={element.text}
      width={element.width}
      fontSize={element.fontSize}
      fontFamily={element.fontFamily || "serif"}
      fontStyle={element.fontStyle || "normal"}
      fill={element.color}
      align={element.align || "left"}
      lineHeight={1.5}
      wrap="word"
    />
  );
}

function StickerNode({ element }: { element: StickerElement }) {
  const size = Math.min(element.width, element.height);
  const half = size / 2;
  if (element.variant === "circle") {
    return <Circle x={half} y={half} radius={half} fill={element.color} opacity={0.92} />;
  }
  if (element.variant === "heart") {
    return (
      <Path
        data="M20 34 C6 24 4 12 12 9 C16 7 19 10 20 13 C21 10 24 7 28 9 C36 12 34 24 20 34 Z"
        scaleX={size / 40}
        scaleY={size / 40}
        fill={element.color}
      />
    );
  }
  if (element.variant === "pin") {
    return (
      <>
        <Path
          data="M20 3 C13 3 8 8 8 15 C8 24 20 37 20 37 C20 37 32 24 32 15 C32 8 27 3 20 3 Z"
          scaleX={size / 40}
          scaleY={size / 40}
          fill={element.color}
        />
        <Circle x={half} y={(14 * size) / 40} radius={(4 * size) / 40} fill="rgba(255,255,255,0.85)" />
      </>
    );
  }
  const points = element.variant === "burst" ? 12 : 5;
  return (
    <Star
      x={half}
      y={half}
      numPoints={points}
      innerRadius={points > 6 ? half * 0.72 : half * 0.46}
      outerRadius={half}
      fill={element.color}
      opacity={0.94}
    />
  );
}
function TapeNode({ element }: { element: TapeElement }) {
  const stripes = element.pattern === "plain" ? 0 : Math.max(2, Math.floor(element.width / 26));
  return (
    <>
      <Rect
        width={element.width}
        height={element.height}
        fill={element.color}
        cornerRadius={element.cornerRadius}
        opacity={0.85}
      />
      {Array.from({ length: stripes }).map((_, index) => (
        <Line
          key={index}
          points={
            element.pattern === "stripe"
              ? [8 + index * 26, 0, 24 + index * 26, element.height]
              : [10 + index * 26, element.height / 2, 16 + index * 26, element.height / 2]
          }
          stroke="rgba(255,255,255,0.35)"
          strokeWidth={element.pattern === "stripe" ? 4 : 3}
          dash={element.pattern === "dot" ? [2, 6] : undefined}
        />
      ))}
    </>
  );
}

export function ElementNode({ element }: { element: CanvasElement }) {
  if (element.type === "photo") return <PhotoNode element={element} />;
  if (element.type === "text") return <TextNode element={element} />;
  if (element.type === "sticker") return <StickerNode element={element} />;
  return <TapeNode element={element} />;
}

export default function JournalCanvasView({
  canvas,
  width = 420,
  maxHeight,
}: {
  canvas: unknown;
  width?: number;
  /** 缩略图场景按高度再收一次，避免 3:4 在矮容器里被裁 */
  maxHeight?: number;
}) {
  const container = useRef<HTMLDivElement | null>(null);
  const [boxWidth, setBoxWidth] = useState(width);
  const doc = parseCanvas(canvas);

  useEffect(() => {
    const element = container.current;
    if (!element) return;
    const observer = new ResizeObserver((entries) => {
      setBoxWidth(Math.max(160, entries[0]?.contentRect.width ?? width));
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [width]);

  if (doc.elements.length === 0) return null;

  const scale = Math.min(boxWidth / CANVAS_W, maxHeight ? maxHeight / CANVAS_H : Infinity);
  return (
    <div ref={container} className="w-full">
      <div className="overflow-hidden rounded-card border border-border/60">
        <Stage width={CANVAS_W * scale} height={CANVAS_H * scale} scaleX={scale} scaleY={scale}>
          <Layer>
            <Rect width={CANVAS_W} height={CANVAS_H} fill={doc.background} />
          </Layer>
          <Layer>
            {doc.elements.map((element) => (
              <Group
                key={element.id}
                x={element.x}
                y={element.y}
                rotation={element.rotation}
                scaleX={element.scale}
                scaleY={element.scale}
                opacity={element.opacity}
              >
                <ElementNode element={element} />
              </Group>
            ))}
          </Layer>
        </Stage>
      </div>
    </div>
  );
}