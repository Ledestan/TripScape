"""行旅识景 TripScape
创建日期：2025-09-01

URL 路由总入口。

- /api/...      Django Ninja API（含 /api/docs 自动文档）
- /admin/       Django admin（管理员后台）
- /healthz /readyz  健康检查（不经 Ninja，直接轻量返回）
- /media/...    上传文件
- /lmimg/...    地标百科图片（frontend/public/landmarks）
- 其余路径      React SPA（frontend/dist/index.html，前端路由兜底）

公共静态资源（earth.png / stars.jpg / earth-arc.jpg / favicon 等）
优先从 frontend/public/ 读取：改图后无需重新构建即可生效，
打包后也不会拿到 dist 里的旧副本。
"""

import mimetypes
from pathlib import Path

from api import api
from django.conf import settings
from django.contrib import admin
from django.http import FileResponse, Http404, JsonResponse
from django.urls import path, re_path
from django.views.static import serve as static_serve


def _resolve_public(rel: str, subdir: str = "") -> Path:
    """定位公共静态资源：frontend/public 优先，dist 兜底。

    参数：
        rel    : str，资源相对路径（如 "earth.png"）
        subdir : str，资源子目录（landmarks 图用）

    返回：
        Path，命中文件路径；未命中抛 Http404（含目录穿越防护）。
    """
    base = Path(settings.BASE_DIR) / "frontend"
    safe = Path(rel).as_posix().lstrip("/")
    if ".." in safe.split("/"):
        raise Http404("非法路径")
    for root in ("public", "dist"):
        root_dir = (base / root / subdir if subdir else base / root).resolve()
        candidate = (root_dir / safe).resolve()
        # 目录穿越防护：解析后必须仍在该 root 之下
        if candidate != root_dir and root_dir not in candidate.parents:
            continue
        if candidate.is_file():
            return candidate
    raise Http404("资源不存在")


def serve_public(request, path, subdir=""):
    """提供公共静态资源（开发态禁缓存，避免换图后看到旧内容）。"""
    f = _resolve_public(path, subdir)
    ctype = mimetypes.guess_type(str(f))[0] or "application/octet-stream"
    resp = FileResponse(open(f, "rb"), content_type=ctype)
    resp["Cache-Control"] = "no-store" if settings.DEBUG else "public, max-age=86400"
    return resp


def healthz(request):
    """存活探针：进程活着即返回 200。"""
    return JsonResponse({"status": "ok"})


def readyz(request):
    """就绪探针：检查 MySQL 连接可用。"""
    from django.db import connection

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        return JsonResponse({"status": "ready", "checks": {"mysql": "ok"}})
    except Exception as exc:  # noqa: BLE001
        return JsonResponse(
            {"status": "error", "checks": {"mysql": str(exc)}}, status=503
        )


def spa(request, **kwargs):
    """React SPA 入口（前端路由兜底）。"""
    from django.http import FileResponse

    index = settings.BASE_DIR / "frontend" / "dist" / "index.html"
    if not index.exists():
        return JsonResponse(
            {
                "detail": "前端未构建，请先执行 cd frontend && pnpm install && pnpm build"
            },
            status=503,
        )
    return FileResponse(open(index, "rb"), content_type="text/html")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz", healthz),
    path("readyz", readyz),
    path("api/", api.urls),
    # 开发态 media 服务（生产由 Nginx 直接提供）
    path("media/<path:path>", static_serve, {"document_root": settings.MEDIA_ROOT}),
    # 地标百科图片：独立前缀 /lmimg/（public/landmarks 优先，dist 兜底）。
    # 不用 /landmarks/ 的原因：该前缀是前端路由 /landmarks/:id，
    # 静态服务会抢占深链导致刷新 404（TS-07/TS-19）。
    re_path(r"^lmimg/(?P<path>.*)$", serve_public, {"subdir": "landmarks"}),
    # 前端构建产物（JS/CSS 等带哈希的静态资源，只能来自 dist）
    re_path(
        r"^assets/(?P<path>.*)$",
        static_serve,
        {"document_root": str(settings.BASE_DIR / "frontend" / "dist" / "assets")},
    ),
    # 公共根文件（earth.png 贴图 / 启动背景 / 图标）：
    # public 优先——换图后源码运行与打包都立即取新文件
    re_path(
        r"^(?P<path>favicon\.svg|earth\.png|earth3\.png|earth4\.png|stars\.jpg|earth-arc\.jpg|manifest\.webmanifest)$",
        serve_public,
    ),
    # React SPA 兜底（前端路由；/landmarks/:id 深链正常进入 SPA）
    re_path(
        r"^(?!api/|admin/|media/|lmimg/|assets/|healthz|readyz|static/|favicon\.svg|earth[0-9]*\.png|stars\.jpg|earth-arc\.jpg|manifest\.webmanifest).*$",
        spa,
    ),
]


handler404 = "apps.core.views.page_not_found"
handler500 = "apps.core.views.server_error"
