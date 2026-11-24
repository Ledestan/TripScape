import { useQuery } from "@tanstack/react-query";

import { api } from "@/api/client";

/**
 * 运行期读取后端特性开关（GET /api/features）。
 *
 * 为什么不在构建期注入：
 *   开关必须"默认关闭、可被同一份产物打开"（SPEC §5 硬边界），
 *   构建期注入会让关闭版与开启版变成两份 dist，无法用同一份证据链复核。
 *
 * 后端不可达或旧版本没有该端点时返回 false（不影响既有功能）。
 */
export function useFeatureFlag(name: "tripScape2"): boolean {
  const { data } = useQuery({
    queryKey: ["features"],
    queryFn: async () => (await api.get("/features")).data as Record<string, unknown>,
    staleTime: 5 * 60_000,
    retry: 0,
  });
  return Boolean(data?.[name]);
}
