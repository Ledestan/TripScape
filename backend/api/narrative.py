"""行旅识景 TripScape
创建日期：2025-11-24

叙事 API（TripScape 2.0 专属，挂载在 /api/narrative）。

端点（全部由 settings.TRIPSCAPE2_ENABLED 门控；关闭时一律 404，不改变现有行为）：

GET    /api/narrative/card/{landmark_id}   取该地标最新叙事卡片（无则现建）
POST   /api/narrative/journal/cards        把卡片加入手账（只读持久化）
GET    /api/narrative/journal              我的手账卡片（刷新后取回）
POST   /api/narrative/fragments            卡片匿名投递到地标（同地标上限 3）
GET    /api/narrative/fragments/pick       拾取一条未拾取过的碎片
POST   /api/narrative/fragments/{id}/pick  按 ID 拾取（重复拾取 409）

错误语义（SPEC §3.5）：
    第 4 次投递 -> 409 + 明确额度消息
    重复拾取    -> 409 + 明确消息
    碎片不存在/已无可拾取 -> 404
"""

from django.conf import settings
from ninja import Router, Schema
from ninja.errors import HttpError

from apps.core.auth import login_required, OptionalAuth
from apps.landmarks.models import Landmark
from services import narrative_service as narrative

router = Router()


def _gate():
    """开关门控：未开启时按"不存在"处理（不泄露功能形态）。"""
    if not getattr(settings, "TRIPSCAPE2_ENABLED", False):
        raise HttpError(404, "TripScape 2.0 叙事层未开启（tripScape2=false）")


def _landmark_or_404(landmark_id: int) -> Landmark:
    lm = Landmark.objects.filter(id=landmark_id).first()
    if lm is None:
        raise HttpError(404, "地标不存在")
    return lm


class AddCardIn(Schema):
    card_id: int


class DeliverIn(Schema):
    card_id: int
    landmark_id: int


@router.get("/card/{landmark_id}", summary="地标叙事卡片", auth=OptionalAuth())
def get_card(request, landmark_id: int):
    """取该地标最新卡片；没有则按真实种子数据现建一张（source=landmark）。"""
    _gate()
    lm = _landmark_or_404(landmark_id)
    card = narrative.latest_card(lm)
    return {"success": True, "data": card.as_card()}


@router.post("/journal/cards", summary="叙事卡片加入手账")
@login_required
def add_card(request, payload: AddCardIn):
    """把卡片加入手账（幂等；卡片以只读快照持久化）。"""
    _gate()
    try:
        result = narrative.add_card_to_journal(request.auth, payload.card_id)
    except narrative.NarrativeError as exc:
        raise HttpError(exc.status, exc.message)
    return {
        "success": True,
        "created": result["created"],
        "data": result["entry"],
    }


@router.get("/journal", summary="我的手账卡片")
@login_required
def my_journal(request):
    """我的手账卡片列表（服务端持久化，刷新不丢失）。"""
    _gate()
    return {"success": True, "data": narrative.journal_cards(request.auth)}


@router.post("/fragments", summary="匿名投递叙事碎片")
@login_required
def deliver(request, payload: DeliverIn):
    """把手账卡片匿名投递到地标（同一地标最多 3 条；第 4 条 409）。"""
    _gate()
    try:
        data = narrative.deliver_fragment(request.auth, payload.card_id, payload.landmark_id)
    except narrative.NarrativeError as exc:
        raise HttpError(exc.status, exc.message)
    return {
        "success": True,
        "data": data,
        "message": f"碎片已匿名投递，该地标还剩 {data['remaining']} 个投递名额",
    }


@router.get("/fragments/pick", summary="拾取一条未被拾取过的碎片")
@login_required
def pick(request, landmark_id: int):
    """随机序（按投递时间）拾取一条未被本人拾取过的碎片。"""
    _gate()
    try:
        data = narrative.pick_fragment(request.auth, landmark_id)
    except narrative.NarrativeError as exc:
        raise HttpError(exc.status, exc.message)
    return {"success": True, "data": data}


@router.post("/fragments/{fragment_id}/pick", summary="按 ID 拾取碎片")
@login_required
def pick_by_id(request, fragment_id: int):
    """按 ID 拾取：同一碎片对同一用户第二次拾取返回 409。"""
    _gate()
    try:
        data = narrative.pick_fragment_by_id(request.auth, fragment_id)
    except narrative.NarrativeError as exc:
        raise HttpError(exc.status, exc.message)
    return {"success": True, "data": data}
