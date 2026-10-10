"""行旅识景 TripScape
创建日期：2025-09-01

手账 API。

GET    /api/journals/mine              我的手账
POST   /api/journals/                  创建手账
GET    /api/journals/{id}              手账详情（公开可见或作者）
PUT    /api/journals/{id}              更新（作者）
DELETE /api/journals/{id}              删除（作者或管理员）
GET    /api/journals/landmark/{id}     地标下的公开手账
POST   /api/journals/{id}/share        生成公开分享链接
"""


from datetime import date
from typing import Optional

from apps.core.auth import is_any_admin, login_required, OptionalAuth
from apps.journals.models import Journal
from ninja import Router, Schema
from ninja.errors import HttpError
from services import journal_service, share_service
from services.audit_service import write_audit

router = Router()


def _parse_date(v):
    """宽松解析日期：接受 date / 'YYYY-MM-DD' / 空串 / None / 显式清除标记。

    非法日期抛 HttpError 422（TS-11：不升级为 500）。
    """
    if v is None or v == "":
        return None
    if isinstance(v, date):
        return v
    s = str(v).strip()
    if not s:
        return None
    try:
        # 只取日期部分（兼容带时间的字符串）
        return date.fromisoformat(s[:10])
    except ValueError:
        raise HttpError(422, f"旅行日期格式不合法：{s[:10]}（应为 YYYY-MM-DD）")


class JournalIn(Schema):
    landmark_id: int
    title: str
    content: str = ""
    images: list = None
    visited_at: Optional[str] = None  # 可空（TS-06：日期非必填）
    is_public: bool = True


class JournalUpdateIn(Schema):
    title: str = None
    content: str = None
    images: list = None
    visited_at: Optional[str] = None  # None=未修改或清除，用 exclude_unset 区分
    is_public: bool = None


@router.get("/mine", summary="我的手账")
@login_required
def my_journals(request):
    """我的手账列表。"""
    qs = (
        Journal.objects.filter(user=request.auth, deleted_at__isnull=True)
        .select_related("landmark", "user")
        .order_by("-created_at")
    )
    return {"success": True, "data": [j.as_dict(with_content=True) for j in qs]}


@router.post("/", summary="创建手账（自动生成足迹）")
@login_required
def create(request, payload: JournalIn):
    """创建手账（敏感词拦截；自动生成足迹与徽章进度）。"""
    ok, result = journal_service.create_journal(
        user=request.auth,
        landmark_id=payload.landmark_id,
        title=payload.title,
        content=payload.content,
        images=payload.images or [],
        visited_at=_parse_date(payload.visited_at),
        is_public=payload.is_public,
    )
    if not ok:
        raise HttpError(400, str(result))
    # 徽章进度
    try:
        from services import badge_service

        badge_service.on_journal_created(request.auth)
    except Exception:
        pass
    return {"success": True, "data": result.as_dict(with_content=True)}


@router.get("/landmark/{landmark_id}", summary="地标下的公开手账", auth=OptionalAuth())
def landmark_journals(request, landmark_id: int):
    """地标下的公开手账列表（排除软删，TS-03）。"""
    viewer = getattr(request, "auth", None)
    qs = (
        Journal.objects.filter(
            landmark_id=landmark_id,
            is_public=True,
            status="approved",
            deleted_at__isnull=True,
        )
        .select_related("landmark", "user")
        .order_by("-created_at")
    )
    return {"success": True, "data": [j.as_dict(viewer=viewer) for j in qs[:50]]}


@router.get("/{journal_id}", summary="手账详情", auth=OptionalAuth())
def detail(request, journal_id: int):
    """手账详情（公开可见或作者；软删对象 404，TS-03/04）。"""
    j = (
        Journal.objects.filter(id=journal_id, deleted_at__isnull=True)
        .select_related("landmark", "user")
        .first()
    )
    if not j:
        raise HttpError(404, "手账不存在")
    user = getattr(request, "auth", None)
    is_owner = getattr(user, "is_authenticated", False) and j.user_id == user.id
    is_admin = is_any_admin(user)
    if not j.is_public and not is_owner and not is_admin:
        raise HttpError(403, "该手账未公开")
    if j.status != "approved" and not is_owner and not is_admin:
        raise HttpError(403, "该手账审核中")
    return {"success": True, "data": j.as_dict(with_content=True, viewer=user)}


@router.put("/{journal_id}", summary="更新手账（作者）")
@login_required
def update(request, journal_id: int, payload: JournalUpdateIn):
    """作者修改自己的手账（敏感词校验；软删对象拒绝，TS-03）。"""
    j = Journal.objects.filter(
        id=journal_id, user=request.auth, deleted_at__isnull=True
    ).first()
    if not j:
        raise HttpError(404, "手账不存在或无权操作")
    # 禁言期间禁止修改公开内容（TS-13 同口径）
    from apps.core.auth import is_muted

    if is_muted(request.auth):
        raise HttpError(403, "账号禁言中，暂不能修改手账")
    # 只提交显式给出的字段（TS-06：区分未修改与显式清空）
    fields = payload.dict(exclude_unset=True)
    if "visited_at" in fields:
        fields["visited_at"] = _parse_date(fields["visited_at"])
    ok, result = journal_service.update_journal(j, fields)
    if not ok:
        raise HttpError(400, str(result))
    return {
        "success": True,
        "data": result.as_dict(with_content=True, viewer=request.auth),
        "message": "修改已提交，审核通过后展示" if result.edit_pending else "已保存",
    }


@router.delete("/{journal_id}", summary="删除手账")
@login_required
def delete(request, journal_id: int):
    """删除手账（作者或管理员）。"""
    j = Journal.objects.filter(id=journal_id, deleted_at__isnull=True).first()
    if not j:
        raise HttpError(404, "手账不存在")
    if j.user_id != request.auth.id and not is_any_admin(request.auth):
        raise HttpError(403, "无权删除")
    from services.footprint_service import rebuild_user_footprints

    owner = j.user
    j.delete()
    rebuild_user_footprints(owner)
    write_audit(request, "journal.delete", f"journal:{journal_id}", j.title)
    return {"success": True}


@router.post("/{journal_id}/share", summary="生成公开分享链接")
@login_required
def share(request, journal_id: int):
    """生成手账公开分享链接（作者）。"""
    j = Journal.objects.filter(id=journal_id, deleted_at__isnull=True).first()
    if not j:
        raise HttpError(404, "手账不存在")
    if j.user_id != request.auth.id and not is_any_admin(request.auth):
        raise HttpError(403, "无权分享")
    token = share_service.create_share_token("journal", j.id)
    return {"success": True, "share_url": f"/share/{token}", "token": token}
