"""
行旅识景 TripScape / api/comments

评论 API。

GET    /api/comments/landmark/{id}    地标下公开展示的评论（含回复树）
POST   /api/comments/                 发表评论（登录，敏感词拦截，禁言拦截）
PUT    /api/comments/{id}             修改自己的评论
DELETE /api/comments/{id}             删除（作者或管理员）
POST   /api/comments/report           举报（评论/手账，分类+说明）
"""

from apps.comments.models import Comment, CommentReport
from apps.core import sensitive
from apps.core.auth import OptionalAuth, is_any_admin, login_required
from ninja import Router, Schema
from ninja.errors import HttpError
from services import comment_service
from services.audit_service import write_audit

router = Router()


class CommentIn(Schema):
    landmark_id: int = None
    journal_id: int = None
    content: str = ""
    parent_id: int = None


class ReportIn(Schema):
    target_type: str
    target_id: int
    reason: str
    detail: str = ""


# ----------------------------------------------------------------------
# 具体路径路由（必须在参数路由 /{comment_id} 之前注册，否则会被抢占）
# ----------------------------------------------------------------------


def _tree(records, viewer=None):
    """把同一目标的评论整理成树：顶级按时间倒序，回复按时间正序。

    点赞数与我是否点过赞一次性批量查出来：逐条查会让列表变成 N+1。
    """
    from collections import defaultdict

    from apps.comments.models_like import Like
    from django.db.models import Count

    ids = [record.id for record in records]
    counts = dict(
        Like.objects.filter(target_type="comment", target_id__in=ids)
        .values("target_id")
        .annotate(total=Count("id"))
        .values_list("target_id", "total")
    )
    liked: set[int] = set()
    if getattr(viewer, "is_authenticated", False):
        liked = set(
            Like.objects.filter(
                user=viewer, target_type="comment", target_id__in=ids
            ).values_list("target_id", flat=True)
        )

    grouped = defaultdict(list)
    for record in records:
        grouped[record.parent_id].append(record)

    for children in grouped.values():
        children.sort(key=lambda item: item.created_at)

    def node_of(record):
        node = record.as_dict()
        node["like_count"] = counts.get(record.id, 0)
        node["liked"] = record.id in liked
        node["replies"] = build(record.id)
        return node

    def build(parent_id=None):
        return [node_of(record) for record in grouped.get(parent_id, [])]

    top = grouped.get(None, [])
    top.sort(key=lambda item: item.created_at, reverse=True)
    return [node_of(record) for record in top]


@router.get("/landmark/{landmark_id}", summary="地标评论（公开）", auth=OptionalAuth())
def landmark_comments(request, landmark_id: int):
    """地标下的公开评论树（任意层级回复，过滤隐藏与软删）。"""
    records = list(
        Comment.objects.filter(
            landmark_id=landmark_id,
            is_hidden=False,
            deleted_at__isnull=True,
        )
        .select_related("user", "landmark")
        .order_by("created_at")[:300]
    )
    return {"success": True, "data": _tree(records, getattr(request, "auth", None))}


@router.get(
    "/journal/{journal_id}", summary="手账评论（公开或作者）", auth=OptionalAuth()
)
def journal_comments(request, journal_id: int):
    """手账下的评论树：公开手账任何人可读，私密手账仅作者/管理员。"""
    from apps.journals.models import Journal

    journal = Journal.objects.filter(id=journal_id, deleted_at__isnull=True).first()
    if not journal:
        raise HttpError(404, "手账不存在")
    viewer = getattr(request, "auth", None)
    is_owner = (
        getattr(viewer, "is_authenticated", False) and journal.user_id == viewer.id
    )
    if not is_owner and not is_any_admin(viewer):
        if not journal.is_public:
            raise HttpError(403, "该手账未公开")
        if journal.status != "approved":
            raise HttpError(403, "该手账审核中")
    records = list(
        Comment.objects.filter(
            journal_id=journal_id,
            is_hidden=False,
            deleted_at__isnull=True,
        )
        .select_related("user", "journal")
        .order_by("created_at")[:300]
    )
    return {"success": True, "data": _tree(records, viewer)}


@router.post("/", summary="发表评论")
@login_required
def create(request, payload: CommentIn):
    """创建手账（敏感词拦截；自动生成足迹与徽章进度）。"""
    ok, result = comment_service.create_comment(
        user=request.auth,
        landmark_id=payload.landmark_id,
        journal_id=payload.journal_id,
        content=payload.content,
        parent_id=payload.parent_id,
    )
    if not ok:
        raise HttpError(400, str(result))
    try:
        from services import badge_service

        badge_service.on_comment_created(request.auth)
    except Exception:
        pass
    return {"success": True, "data": result.as_dict()}


@router.post("/report", summary="举报评论或手账（分类 + 补充说明）")
@login_required
def report(request, payload: ReportIn):
    """举报评论或手账：7 类分类 + 补充说明。

    目标存在性校验（TS-20）：不存在的对象不进举报队列；
    重复举报同一目标幂等返回，不重复入库。
    """
    if payload.target_type not in ("comment", "journal"):
        raise HttpError(400, "目标类型不合法")

    from django.db.models import Q

    # 目标存在且对举报人可见（软删/隐藏内容不可举报；
    # 私密手账及其评论只有作者本人能举报，避免拿 ID 探测他人私密内容）
    if payload.target_type == "comment":
        from apps.comments.models import Comment

        exists = (
            Comment.objects.filter(
                id=payload.target_id, deleted_at__isnull=True, is_hidden=False
            )
            .filter(
                Q(landmark__isnull=False)
                | Q(
                    journal__is_public=True,
                    journal__status="approved",
                    journal__deleted_at__isnull=True,
                )
                | Q(user=request.auth)
            )
            .exists()
        )
    else:
        from apps.journals.models import Journal

        exists = (
            Journal.objects.filter(id=payload.target_id, deleted_at__isnull=True)
            .filter(Q(is_public=True, status="approved") | Q(user=request.auth))
            .exists()
        )
    if not exists:
        raise HttpError(404, "举报目标不存在")

    # 重复举报幂等
    if CommentReport.objects.filter(
        reporter=request.auth,
        target_type=payload.target_type,
        target_id=payload.target_id,
        status="pending",
    ).exists():
        return {"success": True, "message": "你已举报过该内容，管理员会尽快处理"}

    valid_reasons = {c[0] for c in CommentReport.REASONS}
    reason = payload.reason if payload.reason in valid_reasons else "other"
    CommentReport.objects.create(
        reporter=request.auth,
        target_type=payload.target_type,
        target_id=payload.target_id,
        reason=reason,
        detail=(payload.detail or "").strip()[:255],
    )
    return {"success": True, "message": "举报已提交，管理员会尽快处理"}


# ----------------------------------------------------------------------
# 参数路由（/{comment_id} 放最后）
# ----------------------------------------------------------------------
@router.put("/{comment_id}", summary="修改自己的评论")
@login_required
def update(request, comment_id: int, payload: CommentIn):
    """作者修改自己的评论（敏感词校验；禁言期间同样受限，TS-13）。"""
    c = Comment.objects.filter(
        id=comment_id, user=request.auth, deleted_at__isnull=True
    ).first()
    if not c:
        raise HttpError(404, "评论不存在或无权操作")
    from apps.core.auth import is_muted

    if is_muted(request.auth):
        until = request.auth.muted_until.strftime("%Y-%m-%d %H:%M")
        raise HttpError(403, f"你已被禁言至 {until}，暂时无法修改评论")
    content = (payload.content or "").strip()
    if not content:
        raise HttpError(400, "评论内容不能为空")
    ok, hit = sensitive.check_text(content)
    if not ok:
        raise HttpError(400, f"评论包含敏感词「{hit}」")
    c.content = content[:2000]
    c.save(update_fields=["content"])
    return {"success": True, "data": c.as_dict()}


@router.delete("/{comment_id}", summary="删除评论")
@login_required
def delete(request, comment_id: int):
    """删除评论（作者或管理员）。"""
    c = Comment.objects.filter(id=comment_id, deleted_at__isnull=True).first()
    if not c:
        raise HttpError(404, "评论不存在")
    if c.user_id != request.auth.id and not is_any_admin(request.auth):
        raise HttpError(403, "无权删除")
    c.delete()
    write_audit(request, "comment.delete", f"comment:{comment_id}", c.content[:50])
    return {"success": True}
