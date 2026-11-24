import { create } from "zustand";

/**
 * 三层空间状态机（SPEC §2 S1）。
 *
 * 三层不是 UI 结构，而是叙事的三个时间尺度：
 *   globe   —— 尚未被讲述的空间
 *   landmark—— 正在被讲述的地点
 *   journal —— 已被沉淀的个人叙事
 *
 * 状态只在前端会话内维护（刷新后回到 globe 层），
 * **手账内容**不在这里——它持久化在服务端（/api/narrative/journal），
 * 刷新后由服务端取回，因此"刷新不丢失"证明的是持久化而非内存。
 */
export type NarrativeLayer = "globe" | "landmark" | "journal";

interface NarrativeState {
  layer: NarrativeLayer;
  landmarkId: number | null;
  landmarkName: string;
  enterLandmark: (landmarkId: number, landmarkName: string) => void;
  showJournal: () => void;
  back: () => void;
  reset: () => void;
}

export const useNarrativeStore = create<NarrativeState>((set, get) => ({
  layer: "globe",
  landmarkId: null,
  landmarkName: "",

  /** globe → landmark */
  enterLandmark: (landmarkId, landmarkName) =>
    set({ layer: "landmark", landmarkId, landmarkName }),

  /** → journal（有地标时可返回地标层） */
  showJournal: () => set({ layer: "journal" }),

  /** 返回上一层：journal → landmark → globe（无地标时直接回 globe） */
  back: () => {
    const { layer, landmarkId } = get();
    if (layer === "journal" && landmarkId !== null) {
      set({ layer: "landmark" });
      return;
    }
    set({ layer: "globe" });
  },

  reset: () => set({ layer: "globe", landmarkId: null, landmarkName: "" }),
}));
