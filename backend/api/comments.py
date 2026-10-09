"""行旅识景 TripScape
创建日期：2025-09-01

评论 API。

GET    /api/comments/landmark/{id}    地标下公开展示的评论（含回复树）
POST   /api/comments/                 发表评论（登录，敏感词拦截，禁言拦截）
PUT    /api/comments/{id}             修改自己的评论
DELETE /api/comments/{id}             删除（作者或管理员）
POST   /api/comments/report           举报（评论/手账，分类+说明）
"""


from apps.comments.models import Comment, CommentReport
from apps.core import sensitive
from apps.core.auth import is_any_admin, login_required
from ninja import Router, Schema
from ninja.errors import HttpError
from services import comment_service
from services.audit_service import write_audit

router = Router()


class CommentIn(Schema):
    landmark_id: int
    content: str
    parent_id: int = None


class ReportIn(Schema):
    target_type: str
    target_id: int
    reason: str
    detail: str = ""


# ----------------------------------------------------------------------
# 具体路径路由（必须在参数路由 /{comment_id} 之前注册，否则会被抢占）
# ----------------------------------------------------------------------
@router.get("/landmark/{landmark_id}", summary="地标评论（公开）", auth=None)
def landmark_comments(request, landmark_id: int):
    """地标下的公开评论树（一级 + 回复，过滤隐藏与软删）。"""
    qs = (
        Comment.objects.filter(
            landmark_id=landmark_id,
            is_hidden=False,
            deleted_at__isnull=True,
            parent__isnull=True,
        )
        .select_related("user", "landmark")
        .order_by("-created_at")[:100]
    )
    data = []
    for c in qs:
        d = c.as_dict()
        d["replies"] = [
            r.as_dict()
            for r in c.replies.filter(is_hidden=False, deleted_at__isnull=True)
            .select_related("user", "landmark")
            .order_by("created_at")
        ]
        data.append(d)
    return {"success": True, "data": data}


@router.post("/", summary="发表评论")
@login_required
def create(request, payload: CommentIn):
    """创建手账（敏感词拦截；自动生成足迹与徽章进度）。"""
    ok, result = comment_service.create_comment(
        user=request.auth,
        landmark_id=payload.landmark_id,
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
    """举报评论或手账：7 类分类 + 补充说明。"""
    if payload.target_type not in ("comment", "journal"):
        raise HttpError(400, "目标类型不合法")
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
    """作者修改自己的评论（敏感词校验）。"""
    c = Comment.objects.filter(id=comment_id, user=request.auth).first()
    if not c:
        raise HttpError(404, "评论不存在或无权操作")
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
    """删除手账（作者或管理员）。"""
    c = Comment.objects.filter(id=comment_id).first()
    if not c:
        raise HttpError(404, "评论不存在")
    if c.user_id != request.auth.id and not is_any_admin(request.auth):
        raise HttpError(403, "无权删除")
    c.delete()
    write_audit(request, "comment.delete", f"comment:{comment_id}", c.content[:50])
    return {"success": True}
