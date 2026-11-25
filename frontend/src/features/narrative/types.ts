/**
 * 叙事层数据类型（与后端 SPEC §2 S2 固定字段集一一对应）。
 *
 * 随 2.0 默认渲染；字段名与 /api/narrative/* 响应完全一致，
 * 不做本地改名，避免与 A2 快照产生第二套口径。
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
