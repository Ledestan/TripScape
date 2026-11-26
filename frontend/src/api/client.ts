/**
 * 行旅识景 TripScape / HTTP 客户端
 * 创建日期: 2025-09-01
 *
 * 统一的 axios 实例与错误文案，提供:
 *     1. api：自动附带登录 token 的请求实例
 *     2. errMessage：把后端/网络异常翻译成用户能懂的一句话
 *
 * 依赖:
 *     依赖库: axios, zustand
 *
 * 用法:
 *     import { api, errMessage } from "@/api/client";
 *     await api.get("/narrative/journal");
 *
 * 注意:
 *     1. 401 只有在「本地本来有 token」时才登出，否则会把刚打开的登录态误清掉。
 *     2. 所有非 2xx 响应都在这里转成中文短句，业务代码不再各自拼错误文案。
 */

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

/** 把后端 detail 字段（字符串或列表）压成一行可读文本 */
function readDetail(data: unknown): string {
  if (!data || typeof data !== "object") return "";
  const detail = (data as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) =>
        typeof item === "string" ? item : (item as { msg?: string })?.msg || ""
      )
      .filter(Boolean)
      .join("；");
  }
  return "";
}

api.interceptors.response.use(
  (resp) => resp,
  (error) => {
    const status: number | undefined = error.response?.status;
    const detail = readDetail(error.response?.data);
    const hadToken = !!useAuthStore.getState().token;

    // token 过期才登出；本来就没登录的请求不该清掉别人的会话
    if (status === 401 && hadToken) {
      useAuthStore.getState().logout();
    }

    let message: string;
    if (!error.response) {
      message = "网络连接失败：请确认后端已启动（或稍后再试）";
    } else if (status === 401) {
      message = hadToken ? "登录状态已失效，请重新登录" : "请先登录后再操作";
    } else if (status === 403) {
      message = detail || "没有权限执行这个操作";
    } else if (status === 404) {
      message = detail || "要找的内容不存在";
    } else if (status === 422) {
      message = detail ? `提交的数据不完整：${detail}` : "提交的数据不完整或格式不对";
    } else if (status && status >= 500) {
      message = detail ? `服务出错了：${detail}` : "服务临时不可用，请稍后再试";
    } else {
      message = detail || error.message || "请求失败";
    }

    return Promise.reject(new Error(message));
  }
);

/** 提取错误信息：优先用拦截器翻译后的中文短句 */
export function errMessage(e: unknown, fallback = "操作失败"): string {
  if (e instanceof Error && e.message) return e.message;
  if (typeof e === "string" && e) return e;
  return fallback;
}
