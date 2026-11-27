/**
 * 行旅识景 TripScape / src/components/ui/badge-icon
 *
 * 徽章图标：把后端返回的图标名映射成 lucide 图标，完成:
 *     1. 语义化名称（footprints / compass / trophy…）→ 对应 lucide 组件
 *     2. 兼容老数据：库里的 emoji 先翻译成名称，再渲染
 *     3. 未知名称回落 Award，不会出现空白
 *
 * 依赖:
 *     依赖库: lucide-react
 *
 * 用法:
 *     <BadgeIcon icon={badge.icon} className="h-5 w-5" />
 *
 * 注意:
 *     成就系统不再使用 emoji：新增徽章请在 seed_badges.sql 里写名称，不要写表情。
 */

import {
  Award,
  BookOpen,
  Compass,
  Footprints,
  Map,
  MapPinned,
  MessageSquare,
  MessagesSquare,
  NotebookPen,
  PenLine,
  Trophy,
  type LucideIcon,
} from "lucide-react";

const ICONS: Record<string, LucideIcon> = {
  footprints: Footprints,
  compass: Compass,
  "map-pinned": MapPinned,
  map: Map,
  "message-square": MessageSquare,
  "messages-square": MessagesSquare,
  trophy: Trophy,
  "notebook-pen": NotebookPen,
  "pen-line": PenLine,
  "book-open": BookOpen,
  award: Award,
};

/** 老数据里的 emoji → 名称（只覆盖历史用过的几个） */
const LEGACY: Record<string, string> = {
  "👣": "footprints",
  "🧭": "compass",
  "🗺️": "map-pinned",
  "🌍": "map",
  "🌏": "map",
  "🌐": "map",
  "💬": "message-square",
  "🗣️": "messages-square",
  "🏆": "trophy",
  "🏅": "award",
  "🎉": "award",
  "📔": "notebook-pen",
  "📓": "notebook-pen",
  "✍️": "pen-line",
  "📚": "book-open",
};

export function BadgeIcon({ icon, className }: { icon: string; className?: string }) {
  const name = LEGACY[icon] || icon;
  const Component = ICONS[name] || Award;
  return <Component className={className} aria-hidden />;
}