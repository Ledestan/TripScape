"""行旅识景 TripScape
创建日期：2025-09-01

看板 API（管理员）。
"""

from apps.core.auth import any_admin_required
from ninja import Router
from services import stats_service

router = Router()


@router.get("/stats", summary="运营看板（管理员）")
@any_admin_required
def stats(request, days: int = 30):
    """运营看板统计（管理员）。"""
    days = max(1, min(days, 90))
    return {"success": True, "data": stats_service.build_stats(days=days)}
