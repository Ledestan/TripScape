"""行旅识景 TripScape
创建日期：2025-09-01

足迹 API —— 从手账自动生成，取消手动打卡。

GET /api/footprints/mine      我的足迹（去重地标 + 次数 + 首访时间）
GET /api/footprints/public    公开足迹聚合（地球光点高亮展示全球热门）
POST /api/footprints/refresh  手动触发重算（通常不需要，手账保存时自动算）
"""


from apps.core.auth import login_required
from ninja import Router
from ninja.errors import HttpError
from services import footprint_service

router = Router()


@router.get("/mine", summary="我的足迹（手账自动生成）")
@login_required
def my_footprints(request):
    """我的足迹列表（手账自动聚合）。"""
    data = footprint_service.get_user_footprints(request.auth)
    return {"success": True, "data": data}


@router.get("/public", summary="公开足迹热度（全球光点热度）", auth=None)
def public_footprints(request):
    """公开足迹热度（全球光点渲染用）。"""
    data = footprint_service.get_public_heat()
    return {"success": True, "data": data}


@router.post("/refresh", summary="重算我的足迹")
@login_required
def refresh(request):
    """重算我的足迹（通常无需手动）。"""
    count = footprint_service.rebuild_user_footprints(request.auth)
    return {"success": True, "footprints": count}


@router.post("/{landmark_id}/visibility", summary="隐藏/显示我的某个足迹")
@login_required
def toggle_visibility(request, landmark_id: int):
    """隐藏/显示我的某个足迹（隐藏后不计入公开热度）。"""
    from apps.journals.models import Footprint

    fp = Footprint.objects.filter(user=request.auth, landmark_id=landmark_id).first()
    if not fp:
        raise HttpError(404, "足迹不存在")
    fp.hidden = not fp.hidden
    fp.save(update_fields=["hidden"])
    return {"success": True, "hidden": fp.hidden}
