"""行旅识景 TripScape
创建日期：2025-09-01

通用视图（404/500 JSON 响应）与分页助手。
"""

import math

from django.http import JsonResponse


def page_not_found(request, exception=None):
    return JsonResponse({"detail": "资源未找到"}, status=404)


def server_error(request):
    return JsonResponse({"detail": "服务器内部错误"}, status=500)


def paginate(qs, page: int, page_size: int):
    """对 queryset 做分页。

    返回：
        (items, meta)  meta 含 page/page_size/total/total_pages
    """
    page = max(1, page)
    page_size = max(1, min(page_size, 200))
    total = qs.count()
    total_pages = max(1, math.ceil(total / page_size))
    page = min(page, total_pages)
    items = list(qs[(page - 1) * page_size : page * page_size])
    meta = {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
    }
    return items, meta
