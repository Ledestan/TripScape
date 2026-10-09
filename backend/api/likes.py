"""行旅识景 TripScape
创建日期：2025-09-01

点赞 API：手账 / 评论。

POST /api/likes/            点赞 / 取消（toggle）
GET  /api/likes/status      批量查我是否点过赞（ids）
"""


from apps.comments.models import Comment, Like
from apps.core.auth import login_required
from apps.journals.models import Journal
from apps.notifications.models import Notification
from ninja import Router, Schema
from ninja.errors import HttpError

router = Router()


class LikeIn(Schema):
    target_type: str  # journal / comment
    target_id: int


@router.post("/", summary="点赞/取消点赞（toggle）")
@login_required
def toggle_like(request, payload: LikeIn):
    """点赞/取消点赞（toggle），给作者发通知。"""
    if payload.target_type not in ("journal", "comment"):
        raise HttpError(400, "目标类型不合法")

    Model = Journal if payload.target_type == "journal" else Comment
    if not Model.objects.filter(id=payload.target_id).exists():
        raise HttpError(404, "内容不存在")

    like = Like.objects.filter(
        user=request.auth, target_type=payload.target_type, target_id=payload.target_id
    ).first()
    if like:
        like.delete()
        liked = False
    else:
        Like.objects.create(
            user=request.auth,
            target_type=payload.target_type,
            target_id=payload.target_id,
        )
        liked = True
        # 通知作者（不通知自己）
        try:
            obj = Model.objects.select_related("user").get(id=payload.target_id)
            if obj.user_id != request.auth.id:
                what = (
                    "手账《%s》" % (getattr(obj, "title", None) or "无题")
                    if payload.target_type == "journal"
                    else "你的评论"
                )
                Notification.objects.create(
                    user=obj.user,
                    type="like",
                    title="收到新的赞",
                    content=f"{request.auth.nickname or request.auth.username} 赞了{what}",
                    link=(
                        f"/journals/{payload.target_id}"
                        if payload.target_type == "journal"
                        else ""
                    ),
                )
        except Exception:
            pass

    from django.db.models import Count

    cnt = Like.objects.filter(
        target_type=payload.target_type, target_id=payload.target_id
    ).count()
    return {"success": True, "liked": liked, "count": cnt}


@router.get("/status", summary="我是否点过赞（批量）")
@login_required
def like_status(request, target_type: str, ids: str):
    """批量查询我是否点过赞。"""
    if target_type not in ("journal", "comment"):
        raise HttpError(400, "目标类型不合法")
    id_list = [int(x) for x in ids.split(",") if x.strip().isdigit()][:100]
    liked_ids = list(
        Like.objects.filter(
            user=request.auth, target_type=target_type, target_id__in=id_list
        ).values_list("target_id", flat=True)
    )
    return {"success": True, "liked_ids": liked_ids}
