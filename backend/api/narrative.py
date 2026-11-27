"""
行旅识景 TripScape / 叙事

叙事层的六个 HTTP 端点（TripScape 2.0 本体，无特性开关），完成:
    1. 取地标卡片（无卡时按真实种子数据现建）
    2. 卡片收进手记（只读持久化，幂等）
    3. 读回我的手记
    4. 卡片匿名投递到地标（同用户同地标上限 3）
    5. 随机拾取一条未拾取过的碎片
    6. 按 ID 拾取（重复拾取返回 409）

依赖:
    需求文件: requirements.txt
    依赖库:
        Django==5.2
        django-ninja

用法:
    由 backend/api/__init__.py 挂载到 /api/narrative

注意:
    1. 错误语义必须稳定：第 4 次投递 409、重复拾取 409、无可用碎片 404。
    2. 匿名性由 service 层的序列化保证，API 层不额外拼接投递者信息。
"""

from apps.core.auth import OptionalAuth, login_required
from apps.landmarks.models import Landmark
from ninja import Router, Schema
from ninja.errors import HttpError
from services import landmark_pages
from services import narrative_service as narrative

router = Router()


def _landmark_or_404(landmark_id: int) -> Landmark:
    lm = Landmark.objects.filter(id=landmark_id).first()
    if lm is None:
        raise HttpError(404, "地标不存在")
    return lm


class AddCardIn(Schema):
    card_id: int


@router.get("/card/{landmark_id}", summary="地标叙事卡片", auth=OptionalAuth())
def get_card(request, landmark_id: int):
    """取该地标最新卡片；没有则按真实种子数据现建一张（source=landmark）。"""
    lm = _landmark_or_404(landmark_id)
    card = narrative.latest_card(lm)
    return {"success": True, "data": card.as_card()}


@router.get(
    "/story/{landmark_id}",
    summary="地标故事（整体介绍 + 时间轴 + 分节材料）",
    auth=OptionalAuth(),
)
def get_story(request, landmark_id: int):
    """读预置的地标页面文件；没有预置时返回 404，不现场分词拼内容。"""
    lm = _landmark_or_404(landmark_id)
    payload = landmark_pages.story_payload(lm)
    if payload is None:
        raise HttpError(404, "该地标还没有预置内容，请运行 seed_landmark_pages")
    return {"success": True, "data": payload}


@router.post("/journal/cards", summary="叙事卡片加入手账")
@login_required
def add_card(request, payload: AddCardIn):
    """把卡片加入手账（幂等；卡片以只读快照持久化）。"""
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
    return {"success": True, "data": narrative.journal_cards(request.auth)}
