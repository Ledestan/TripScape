"""行旅识景 TripScape
创建日期：2025-09-01

徽章 API。

GET /api/badges/mine   我的徽章墙（含进度）
"""


from apps.core.auth import login_required
from ninja import Router
from services import badge_service

router = Router()


@router.get("/mine", summary="我的徽章墙")
@login_required
def my_badges(request):
    """我的徽章墙（含未获得徽章的进度）。"""
    return {"success": True, "data": badge_service.user_badges(request.auth)}
