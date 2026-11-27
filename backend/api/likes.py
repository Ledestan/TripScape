"""
行旅识景 TripScape / api/likes

点赞 API：手账 / 评论 / 文章（地标详情）。

POST /api/likes/            点赞 / 取消（可显式指定目标状态，幂等）
GET  /api/likes/status      批量查我是否点过赞（ids）
GET  /api/likes/stats       批量点赞数（+ 我是否点过）
"""

from apps.comments.models import Comment, Like
from apps.core.auth import login_required
from apps.journals.models import Journal
from apps.notifications.models import Notification
from ninja import Router, Schema
from ninja.errors import HttpError

router = Router()


class LikeIn(Schema):
    target_type: str  # journal / comment / article
    target_id: int
    # 显式目标状态（推荐）：True=点赞 / False=取消；不传=切换（兼容旧前端）。
    # 双击或网络重试时两次请求带同一个目标状态，不会再把点赞互相抵消。
    liked: bool = None


@router.post("/", summary="点赞/取消点赞（可显式指定目标状态）")
@login_required
def toggle_like(request, payload: LikeIn):
    """点赞/取消点赞（幂等），给作者发通知。

    目标可见性校验（TS-20）：私密/软删/隐藏内容不可点赞——
    点赞数与通知都是公开信号，不得泄露不可见对象的存在。
    """
    if payload.target_type not in ("journal", "comment", "article"):
        raise HttpError(400, "目标类型不合法")

    if payload.target_type == "article":
        from apps.landmarks.models import Landmark

        obj = Landmark.objects.filter(id=payload.target_id).first()
    elif payload.target_type == "journal":
        obj = Journal.objects.filter(
            id=payload.target_id,
            deleted_at__isnull=True,
            is_public=True,
            status="approved",
        ).first()
    else:
        obj = (
            Comment.objects.filter(
                id=payload.target_id,
                deleted_at__isnull=True,
                is_hidden=False,
            )
            .select_related("journal")
            .first()
        )
        # 评论可见性：地标评论，或公开且已通过手账下的评论才可点赞
        if obj is not None and obj.journal_id is not None:
            journal = obj.journal
            if not (
                journal
                and journal.is_public
                and journal.status == "approved"
                and journal.deleted_at is None
            ):
                obj = None
    if not obj:
        raise HttpError(404, "内容不存在或不可见")

    from services.like_service import set_like

    liked, count = set_like(
        request.auth, payload.target_type, payload.target_id, payload.liked
    )

    # 只在"真正点上了"时通知作者（取消点赞不发通知；文章没有作者，不通知）
    if liked and payload.liked is not False:
        try:
            author = getattr(obj, "user", None)
            if author is not None and author.id != request.auth.id:
                what = (
                    "手账《%s》" % (getattr(obj, "title", None) or "无题")
                    if payload.target_type == "journal"
                    else (
                        "地标《%s》的文章" % (getattr(obj, "name", None) or "")
                        if payload.target_type == "article"
                        else "你的评论"
                    )
                )
                Notification.objects.create(
                    user=author,
                    type="like",
                    title="收到新的赞",
                    content=f"{request.auth.nickname or request.auth.username} 赞了{what}",
                    link=(
                        f"/journals/{payload.target_id}"
                        if payload.target_type == "journal"
                        else (
                            f"/landmarks/{payload.target_id}"
                            if payload.target_type == "article"
                            else ""
                        )
                    ),
                )
        except Exception:
            pass

    return {"success": True, "liked": liked, "count": count}


@router.get("/status", summary="我是否点过赞（批量）")
@login_required
def like_status(request, target_type: str, ids: str):
    """批量查询我是否点过赞。"""
    if target_type not in ("journal", "comment", "article"):
        raise HttpError(400, "目标类型不合法")
    id_list = [int(x) for x in ids.split(",") if x.strip().isdigit()][:100]
    liked_ids = list(
        Like.objects.filter(
            user=request.auth, target_type=target_type, target_id__in=id_list
        ).values_list("target_id", flat=True)
    )
    return {"success": True, "liked_ids": liked_ids}


@router.get("/stats", summary="点赞数 + 我是否点过（批量，计数公开）", auth=None)
def like_stats_api(request, target_type: str, ids: str):
    """批量点赞统计：返回计数；登录时额外返回我点过的 id。

    供只拿到目标 id 的前端组件（如文章点赞）显示既有赞数；
    计数本身是公开信号，不包含任何用户身份。
    """
    from apps.core.auth import OptionalAuth
    from services.like_service import like_stats, normalize_ids

    if target_type not in ("journal", "comment", "article"):
        raise HttpError(400, "目标类型不合法")
    # 计数公开、liked_ids 需要登录：匿名统一走 OptionalAuth（无效令牌不报错）
    viewer = OptionalAuth()(request)
    id_list = normalize_ids(ids.split(","))[:100]
    counts, liked = like_stats(target_type, id_list, viewer=viewer)
    return {
        "success": True,
        "counts": {str(k): v for k, v in counts.items()},
        "liked_ids": sorted(liked),
    }
