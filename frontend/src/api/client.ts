import axios from "axios";
import { useAuthStore } from "@/stores/auth";

export const api = axios.create({ baseURL: "/api" });

api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (resp) => resp,
  (error) => {
    if (error.response?.status === 401) {
      // token 过期
      useAuthStore.getState().logout();
    }
    const detail =
      error.response?.data?.detail || error.message || "请求失败";
    return Promise.reject(new Error(typeof detail === "string" ? detail : JSON.stringify(detail)));
  }
);

/** 提取错误信息 */
export function errMessage(e: unknown, fallback = "操作失败"): string {
  if (e instanceof Error && e.message) return e.message;
  return fallback;
}
