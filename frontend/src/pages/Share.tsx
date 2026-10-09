import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { MapPin, CalendarDays, Globe2 } from "lucide-react";

import { api } from "@/api/client";
import LoadingScreen from "@/components/LoadingScreen";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

/** 公开分享页：不登录也能看 */
export default function SharePage() {
  const { token } = useParams()

  const { data, isLoading, isError } = useQuery({
    queryKey: ["share", token],
    queryFn: async () => {
      const r = await api.get(`/shares/${token}`)
      return r.data.data as {
        user: { nickname: string; username: string; avatar: string }
        landmark: { name: string }
        title: string
        content: string
        images: string[]
        visited_at: string | null
        created_at: string
      }
    },
    retry: false,
  })

  if (isLoading) return <LoadingScreen text="打开分享…" />
  if (isError || !data)
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-gradient-to-br from-[#9bb7d7] to-[#6a8caf] text-white">
        <div className="text-5xl">️</div>
        <div className="text-lg font-medium">分享链接不存在或已失效</div>
        <Button variant="secondary" asChild>
          <Link to="/">去行旅识景逛逛</Link>
        </Button>
      </div>
    )

  return (
    <div className="min-h-screen bg-gradient-to-br from-accent/60 via-background to-background">
      <div className="mx-auto max-w-2xl p-4 md:p-8">
        {/* 分享头 */}
        <div className="mb-6 flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Globe2 className="h-4 w-4" />
            来自「行旅识景」的公开分享
          </div>
          <Button size="sm" variant="outline" asChild>
            <Link to="/">打开行旅识景</Link>
          </Button>
        </div>

        <article className="rounded-2xl border bg-card p-6 shadow-sm md:p-8">
          <h1 className="text-2xl font-bold">{data.title}</h1>

          <div className="mt-3 flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
            <span className="flex items-center gap-1.5">
              {data.user.avatar ? (
                <img src={data.user.avatar} className="h-5 w-5 rounded-full object-cover" alt="" />
              ) : (
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-accent text-[10px]">
                  {data.user.nickname[0]}
                </span>
              )}
              {data.user.nickname}
            </span>
            <span className="flex items-center gap-1">
              <MapPin className="h-3.5 w-3.5 text-primary" />
              {data.landmark.name}
            </span>
            {data.visited_at && (
              <span className="flex items-center gap-1">
                <CalendarDays className="h-3.5 w-3.5" />
                {data.visited_at}
              </span>
            )}
            <Badge variant="secondary">公开手账</Badge>
          </div>

          {data.images?.length > 0 && (
            <div className="mt-5 grid gap-2 sm:grid-cols-2">
              {data.images.slice(0, 6).map((url, i) => (
                <img key={i} src={url} alt="" className="h-48 w-full rounded-xl object-cover" />
              ))}
            </div>
          )}

          <div className="mt-5 whitespace-pre-wrap leading-relaxed">
            {data.content || "（作者没有留下文字）"}
          </div>
        </article>

        <p className="mt-6 text-center text-xs text-muted-foreground">
          想记录自己的旅行？来 <Link to="/" className="text-primary hover:underline">行旅识景</Link> 写手账吧
        </p>
      </div>
    </div>
  )
}
