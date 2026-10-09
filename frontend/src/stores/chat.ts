import { create } from "zustand";

export interface ChatCandidate {
  landmark_id: number;
  name: string;
  confidence: number;
  image_url: string;
}

export interface ChatMessage {
  id?: string;
  role: "user" | "bot";
  content: string;
  /** 百科图片 */
  image_url?: string;
  /** 识别的原图（预览） */
  pending_image_url?: string;
  /** 介绍（纯图片识别时的小百科） */
  intro?: string;
  /** 图+文消息中问答引擎的回答 */
  qa_answer?: string;
  /** 识别出的地标名（兼容单主题） */
  landmark_name?: string;
  /** 关联地标（多主题场景，与 landmark_names 同下标） */
  landmark_ids?: number[];
  landmark_names?: string[];
  confidence?: number;
  /** 识别等待中（骨架屏） */
  pending?: boolean;
  /** 关联地标（点消息飞过去） */
  landmark_id?: number;
  lat?: number;
  lon?: number;
  /** 低置信度候选 */
  low_confidence?: boolean;
  candidates?: ChatCandidate[];
}

interface ChatState {
  sessionId: string;
  messages: ChatMessage[];
  addMessage: (m: ChatMessage) => void;
  updateMessage: (id: string, patch: Partial<ChatMessage>) => void;
  clear: () => void;
}

const genId = () => Math.random().toString(36).slice(2, 10);

export const useChatStore = create<ChatState>((set) => ({
  sessionId: genId(),
  messages: [],
  addMessage: (m) =>
    set((s) => ({
      messages: [...s.messages, { ...m, id: m.id || genId() }],
    })),
  updateMessage: (id, patch) =>
    set((s) => ({
      messages: s.messages.map((m) => (m.id === id ? { ...m, ...patch } : m)),
    })),
  clear: () => set({ messages: [], sessionId: genId() }),
}));
