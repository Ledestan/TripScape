/**
 * 叙事层数据类型（与后端字段一一对应，不做本地改名）
 * 创建日期: 2026-11-25
 *
 * 定义叙事接口返回的卡片、手记、碎片与故事结构，提供:
 *     1. NarrativeCardData：地标卡片（九字段 + createdAt）
 *     2. JournalEntry / PickedFragment：手记条目与碎片
 *     3. LandmarkStoryData：预设故事（整体介绍 → 时间轴 → 分节材料）
 *
 * 依赖:
 *     依赖库: 无
 *
 * 用法:
 *     import type { LandmarkStoryData } from "./types";
 *
 * 注意:
 *     字段名必须与 /api/narrative/* 响应完全一致，避免出现第二套口径。
 */

export interface NarrativeGeo {
  lat: number;
  lon: number;
  place: string;
  country: string;
  region: string;
}

export interface TimeFragment {
  text: string;
  year: number | null;
  section: string;
  targetId: string;
  source: string;
}

export interface RagSnippet {
  text: string;
  section: string;
  targetId: string;
  score: number | null;
  source: string;
}

export interface NarrativeCardData {
  id: number;
  landmarkId: number;
  photo: string;
  title: string;
  geo: NarrativeGeo;
  timeFragments: TimeFragment[];
  ragSnippets: RagSnippet[];
  confidence: number;
  source: string;
  createdAt?: string;
}

export interface JournalEntry {
  card: NarrativeCardData;
  addedAt: string;
}

export interface SourceCardSummary {
  id: number;
  title: string;
  photo: string;
  landmarkId: number;
  confidence: number;
  snippet: string;
}

export interface PickedFragment {
  id: number;
  landmarkId: number;
  createdAt: string;
  anonymous: boolean;
  sourceCard: SourceCardSummary;
}

/** globe 层地标入口（复用 GET /api/landmarks/spots） */
export interface NarrativeSpot {
  id: number;
  name: string;
  country: string;
  region: string;
  image_url: string;
  lat: number;
  lon: number;
}

/** 预设故事（GET /api/narrative/story/{id}）：整体介绍 -> 时间轴 -> 分节材料 */
export interface LandmarkStoryData {
  landmarkId: number;
  title: string;
  intro: string;
  timeline: { year: number | null; text: string }[];
  sections: { heading: string; items: string[] }[];
  source: string;
  updatedAt?: string;
}
