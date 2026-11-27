/**
 * 行旅识景 TripScape / 头像
 *
 * 统一的头像展示，完成:
 *     1. 有地址就显示图片，加载失败自动回落
 *     2. 没有头像 / 加载失败时显示昵称首字 + 稳定配色，不留破图
 *
 * 依赖:
 *     依赖库: react
 *
 * 用法:
 *     <Avatar src={user.avatar} name={user.nickname} size={24} />
 */

import { useEffect, useState } from "react";

const COLORS = ["#8a6d3b", "#3d6b63", "#6b4a6a", "#4a5f7a", "#7a5a3a", "#5b6b3d"];

function colorOf(name: string): string {
  let hash = 0;
  for (let index = 0; index < name.length; index += 1) {
    hash = (hash * 31 + name.charCodeAt(index)) % 997;
  }
  return COLORS[hash % COLORS.length];
}

export function Avatar({
  src,
  name,
  size = 24,
  className = "",
}: {
  src?: string | null;
  name?: string | null;
  size?: number;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    setFailed(false);
  }, [src]);

  const label = (name || "?").trim().slice(0, 1);
  const style = { width: size, height: size, fontSize: Math.max(10, Math.round(size * 0.42)) };

  if (!src || failed) {
    return (
      <span
        className={`inline-flex shrink-0 items-center justify-center rounded-full font-medium text-white ${className}`}
        style={{ ...style, backgroundColor: colorOf(name || "?") }}
        aria-label={name || "用户"}
      >
        {label}
      </span>
    );
  }

  return (
    <img
      src={src}
      alt={name || ""}
      className={`shrink-0 rounded-full object-cover ${className}`}
      style={style}
      onError={() => setFailed(true)}
    />
  );
}