"""行旅识景 TripScape
创建日期：2025-09-01

URL 路由总入口。

- /api/...      Django Ninja API（含 /api/docs 自动文档）
- /admin/       Django admin（管理员后台）
- /healthz /readyz  健康检查（不经 Ninja，直接轻量返回）
- /media/...    上传文件
- /landmarks/.. 地标百科图片（frontend/public/landmarks，构建后 dist 内）
- 其余路径      React SPA（frontend/dist/index.html，前端路由兜底）
"""

from api import api
from django.conf import settings
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path, re_path
from django.views.static import serve as static_serve


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
    # 地标百科图片（frontend/public/landmarks -> 构建后 frontend/dist/landmarks）
    re_path(
        r"^landmarks/(?P<path>.*)$",
        static_serve,
        {"document_root": str(settings.BASE_DIR / "frontend" / "dist" / "landmarks")},
    ),
    # 前端构建产物（JS/CSS 等静态资源）
    re_path(
        r"^assets/(?P<path>.*)$",
        static_serve,
        {"document_root": str(settings.BASE_DIR / "frontend" / "dist" / "assets")},
    ),
    # 前端 public 根文件
    re_path(
        r"^(?P<path>favicon\.svg|earth\.png|manifest\.webmanifest)$",
        static_serve,
        {"document_root": str(settings.BASE_DIR / "frontend" / "dist")},
    ),
    # React SPA 兜底（前端路由）
    re_path(
        r"^(?!api/|admin/|media/|landmarks/|assets/|healthz|readyz|static/|favicon\.svg|earth\.png|manifest\.webmanifest).*$",
        spa,
    ),
]


handler404 = "apps.core.views.page_not_found"
handler500 = "apps.core.views.server_error"
