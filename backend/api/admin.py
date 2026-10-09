"""行旅识景 TripScape
创建日期：2025-09-01

审核中心 + 管理端 API（/api/admin）。

- 管理员登录走 /api/admin/login（与用户端分离）
- 审核中心：待审核评论 / 手账，批量隐藏、删除、恢复
- 用户管理：列表 / 角色调整 / 禁用
- 敏感词管理
- 举报处理
- 审计日志查询
"""


from apps.admin_panel.models import AuditLog, SensitiveWord
from apps.comments.models import Comment, CommentReport
from apps.core.auth import (admin_required, any_admin_required, is_admin,
                            is_any_admin)
from apps.core.ratelimit import login_limiter
from apps.core.sensitive import BUILTIN_WORDS
from apps.core.views import paginate
from apps.journals.models import Journal
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from ninja import Router, Schema
from ninja.errors import HttpError
from services import journal_service
from services.audit_service import _client_ip, write_audit

router = Router()

User = get_user_model()


class AdminLoginIn(Schema):
    username: str
    password: str


class ModerateIn(Schema):
    ids: list
    action: str  # hide / restore / delete / approve / reject
    reason: str = ""


class RoleIn(Schema):
    role: str


class SensitiveWordIn(Schema):
    word: str
    is_active: bool = True


# ----------------------------------------------------------------------
# 管理员登录（独立入口）
# ----------------------------------------------------------------------
@router.post("/login", summary="管理员登录", auth=None)
def admin_login(request, payload: AdminLoginIn):
    """管理员登录：校验角色为 admin 后签发 Token。"""
    ip = _client_ip(request)
    if not login_limiter.allow(f"admin-login:{ip}", limit=10, window_seconds=60):
        raise HttpError(429, "尝试过于频繁，请稍后再试")
    user = authenticate(username=payload.username.strip(), password=payload.password)
    if user is None or not user.is_active:
        raise HttpError(400, "用户名或密码错误")
    if user.role != "admin":
        raise HttpError(403, "该账号不是管理员")
    from apps.core.auth import make_token

    write_audit(request, "admin.login", f"user:{user.id}", user.username)
    return {
        "token": make_token(user),
        "user": {
            "id": user.id,
            "username": user.username,
            "nickname": user.nickname or user.username,
            "role": user.role,
        },
    }


@router.get("/session", summary="管理员会话信息")
@any_admin_required
def session(request):
    """管理员会话信息（前端启动时校验身份用）。"""
    u = request.auth
    return {
        "user": {
            "id": u.id,
            "username": u.username,
            "role": u.role,
        }
    }


# ----------------------------------------------------------------------
# 审核中心
# ----------------------------------------------------------------------
@router.get("/review/journals", summary="待审核/被举报手账（按地区/地标筛选）")
@any_admin_required
def review_journals(
    request,
    page: int = 1,
    page_size: int = 0,
    status: str = "pending",
    region: str = "",
    landmark_id: int = None,
):
    """待审手账列表：支持 状态/地区/地标 筛选，含二次编辑快照与风险预检标记。"""
    page_size = page_size or settings.PAGE_SIZE
    from django.db.models import Q

    qs = Journal.objects.select_related("landmark", "user").filter(
        deleted_at__isnull=True
    )
    if status == "published":
        qs = qs.filter(status="approved", is_public=True)
    elif status == "hidden":
        qs = qs.filter(status="approved", is_public=False)
    elif status == "pending":
        qs = qs.filter(Q(status="pending") | Q(edit_pending=True))
    elif status != "all":
        qs = qs.filter(status=status)
    if region:
        qs = qs.filter(landmark__region=region)
    if landmark_id:
        qs = qs.filter(landmark_id=landmark_id)
    items, meta = paginate(qs, page, page_size)
    data = []
    for j in items:
        d = j.as_dict(with_content=True)
        if j.edit_pending and j.pending_edit:
            pe = j.pending_edit
            # 待审核视图主展示新版；同时带上当前展示的旧版供对照
            d["new_title"] = pe.get("title", j.title)
            d["new_content"] = pe.get("content", j.content)
            d["new_images"] = pe.get("images", j.images)
        d["risk"] = _content_risk(j.user, "journal", j.id)
        data.append(d)
    return {"success": True, "data": data, "meta": meta}


@router.get("/review/comments", summary="评论列表（按地区/地标筛选）")
@any_admin_required
def review_comments(
    request,
    page: int = 1,
    page_size: int = 0,
    hidden: str = "false",
    region: str = "",
    landmark_id: int = None,
):
    """评论列表：支持 展示/隐藏/全部 与 地区/地标 筛选，含风险预检。"""
    page_size = page_size or settings.PAGE_SIZE
    qs = Comment.objects.select_related("landmark", "user").filter(
        deleted_at__isnull=True
    )
    if hidden == "true":
        qs = qs.filter(is_hidden=True)
    elif hidden == "false":
        qs = qs.filter(is_hidden=False)
    # hidden == "all" 不过滤
    if region:
        qs = qs.filter(landmark__region=region)
    if landmark_id:
        qs = qs.filter(landmark_id=landmark_id)
    items, meta = paginate(qs, page, page_size)
    data = []
    for c in items:
        d = c.as_dict()
        d["landmark"] = (
            {"name": c.landmark.name, "region": c.landmark.region}
            if c.landmark_id
            else None
        )
        d["risk"] = _content_risk(c.user, "comment", c.id)
        data.append(d)
    return {"success": True, "data": data, "meta": meta}


def _content_risk(user, target_type, target_id) -> list:
    """审核风险预检：新用户 / 历史驳回 / 被举报。"""
    from django.utils import timezone

    risks = []
    try:
        if user.date_joined and user.date_joined > timezone.now() - timezone.timedelta(
            days=7
        ):
            risks.append("新用户")
        if target_type == "journal":
            from apps.journals.models import Journal

            if (
                Journal.objects.filter(user=user, status="rejected")
                .exclude(id=target_id)
                .count()
                >= 2
            ):
                risks.append("多次被驳回")
        from apps.comments.models import CommentReport

        if CommentReport.objects.filter(
            target_type=target_type, target_id=target_id
        ).exists():
            risks.append("被举报过")
    except Exception:
        pass
    return risks


@router.post("/review/journals/moderate", summary="批量审核手账（delete=软删进回收站）")
@any_admin_required
def moderate_journals(request, payload: ModerateIn):
    """批量审核手账：approve 应用快照 / reject 保留旧版 / delete 软删进回收站。"""
    if payload.action not in ("approve", "reject", "hide", "restore", "delete"):
        raise HttpError(400, "不支持的审核动作")
    from django.utils import timezone

    done = 0
    for jid in payload.ids or []:
        j = Journal.objects.filter(id=jid).first()
        if not j:
            continue
        if payload.action == "delete":
            j.deleted_at = timezone.now()
            j.is_public = False
            j.save(update_fields=["deleted_at", "is_public"])
        else:
            journal_service.moderate(j, payload.action, request.auth, payload.reason)
        write_audit(request, f"journal.{payload.action}", f"journal:{jid}", j.title)
        done += 1
    return {"success": True, "processed": done}


@router.post("/review/comments/moderate", summary="批量审核评论（delete=软删进回收站）")
@any_admin_required
def moderate_comments(request, payload: ModerateIn):
    """批量审核评论：hide 隐藏 / restore 恢复 / delete 软删。"""
    if payload.action not in ("hide", "restore", "delete"):
        raise HttpError(400, "不支持的审核动作")
    from django.utils import timezone

    if payload.action == "hide":
        done = Comment.objects.filter(id__in=payload.ids or []).update(is_hidden=True)
    elif payload.action == "restore":
        done = Comment.objects.filter(id__in=payload.ids or []).update(
            is_hidden=False, deleted_at=None
        )
    else:
        done = Comment.objects.filter(id__in=payload.ids or []).update(
            deleted_at=timezone.now(), is_hidden=True
        )
    write_audit(request, f"comment.{payload.action}", f"comments:{payload.ids}", "")
    return {"success": True, "processed": done}


# ----------------------------------------------------------------------
# 举报处理
# ----------------------------------------------------------------------
@router.get("/reports", summary="举报列表（按类型/地区/地标筛选）")
@any_admin_required
def reports(
    request,
    status: str = "pending",  # pending / resolved(已下架) / dismissed(仅标记) / rejected(已驳回) / done(全部已处理)
    page: int = 1,
    page_size: int = 0,
    target_type: str = "",
    region: str = "",
    landmark_id: int = None,
):
    """举报列表：状态四态筛选（待处理/已下架/仅标记/已驳回/全部）+ 类型/地区/地标。"""
    page_size = page_size or settings.PAGE_SIZE
    from django.db.models import Q

    if status == "done":
        qs = CommentReport.objects.exclude(status="pending")
    elif status in ("resolved", "dismissed", "rejected"):
        qs = CommentReport.objects.filter(status=status)
    else:
        qs = CommentReport.objects.filter(status="pending")
    qs = qs.select_related("reporter", "handled_by")
    if target_type in ("comment", "journal"):
        qs = qs.filter(target_type=target_type)
    if region or landmark_id:
        from apps.comments.models import Comment
        from apps.journals.models import Journal

        if target_type == "comment":
            base = Comment.objects.all()
        elif target_type == "journal":
            base = Journal.objects.all()
        else:
            base = None
        if base is not None:
            if region:
                base = base.filter(landmark__region=region)
            if landmark_id:
                base = base.filter(landmark_id=landmark_id)
            qs = qs.filter(target_id__in=list(base.values_list("id", flat=True)))
    items, meta = paginate(qs, page, page_size)
    return {
        "success": True,
        "data": [
            {
                "id": r.id,
                "reporter": r.reporter.username,
                "target_type": r.target_type,
                "target_id": r.target_id,
                "reason": r.reason,
                "reason_label": dict(CommentReport.REASONS).get(r.reason, r.reason),
                "detail": r.detail,
                "status": r.status,
                "status_label": dict(CommentReport.STATUS).get(r.status, r.status),
                "resolution": r.resolution,
                "handled_by": r.handled_by.username if r.handled_by_id else "",
                "handled": r.status != "pending",
                "target_excerpt": _report_target_excerpt(r),
                "created_at": r.created_at.isoformat(),
            }
            for r in items
        ],
        "meta": meta,
    }


def _report_target_excerpt(r):
    """被举报内容的原文 + 所属地标（dict），供查看原文与定位。"""
    try:
        if r.target_type == "comment":
            from apps.comments.models import Comment

            c = (
                Comment.objects.select_related("landmark")
                .filter(id=r.target_id)
                .first()
            )
            if c:
                return {
                    "text": c.content[:200],
                    "landmark_id": c.landmark_id,
                    "landmark_name": c.landmark.name if c.landmark_id else "",
                    "region": c.landmark.region if c.landmark_id else "",
                }
        elif r.target_type == "journal":
            from apps.journals.models import Journal

            j = (
                Journal.objects.select_related("landmark")
                .filter(id=r.target_id)
                .first()
            )
            if j:
                return {
                    "text": f"《{j.title}》\n{(j.content or '')[:150]}",
                    "landmark_id": j.landmark_id,
                    "landmark_name": j.landmark.name,
                    "region": j.landmark.region,
                }
    except Exception:
        pass
    return {"text": "", "landmark_id": None, "landmark_name": "", "region": ""}


class ReportHandleIn(Schema):
    action: str  # resolve=下架内容 / dismiss=仅标记 / reject=驳回
    resolution: str = ""


@router.post("/reports/{report_id}/handle", summary="处理举报（下架/标记/驳回）")
@any_admin_required
def handle_report(request, report_id: int, payload: ReportHandleIn):
    """处理举报：resolve 下架 / dismiss 仅标记 / reject 驳回 / reopen 重开。"""
    from django.utils import timezone

    r = CommentReport.objects.filter(id=report_id).first()
    if not r:
        raise HttpError(404, "举报不存在")
    if payload.action not in ("resolve", "dismiss", "reject", "reopen"):
        raise HttpError(400, "action 必须是 resolve/dismiss/reject")

    if payload.action == "reopen":
        r.handled_by = None
        r.resolution = ""
        r.handled_at = None
        r.handled = False
        r.status = "pending"
        r.save()
        write_audit(request, "report.reopen", f"report:{report_id}", "")
        return {"success": True}

    r.handled_by = request.auth
    r.resolution = (payload.resolution or "")[:255]
    r.handled_at = timezone.now()
    r.handled = True
    r.status = {"reject": "rejected", "dismiss": "dismissed"}.get(
        payload.action, "resolved"
    )

    if payload.action == "resolve":
        if r.target_type == "comment":
            from apps.comments.models import Comment

            Comment.objects.filter(id=r.target_id).update(is_hidden=True)
        elif r.target_type == "journal":
            from apps.journals.models import Journal

            Journal.objects.filter(id=r.target_id).update(
                is_public=False, status="rejected"
            )
    r.save()
    write_audit(
        request, f"report.{payload.action}", f"report:{report_id}", r.resolution
    )
    return {"success": True}


# ----------------------------------------------------------------------
# 用户管理（全局管理员）
# ----------------------------------------------------------------------
@router.get("/users", summary="用户列表")
@admin_required
def users(request, page: int = 1, page_size: int = 0, q: str = ""):
    """用户列表（管理端）：搜索 + 封禁/禁言/限登状态展示。"""
    page_size = page_size or settings.PAGE_SIZE
    qs = User.objects.all().order_by("-id")
    if q:
        qs = qs.filter(username__icontains=q) | User.objects.filter(
            nickname__icontains=q
        ).order_by("-id")
    items, meta = paginate(qs, page, page_size)
    return {
        "success": True,
        "data": [
            {
                "id": u.id,
                "username": u.username,
                "nickname": u.nickname or u.username,
                "role": u.role,
                "is_active": u.is_active,
                "banned": u.banned,
                "banned_reason": u.banned_reason,
                "muted_until": u.muted_until.isoformat() if u.muted_until else None,
                "is_muted": u.is_muted,
                "locked_until": u.locked_until.isoformat() if u.locked_until else None,
                "created_at": u.created_at.isoformat(),
            }
            for u in items
        ],
        "meta": meta,
    }


@router.put("/users/{user_id}/role", summary="调整用户角色")
@admin_required
def set_role(request, user_id: int, payload: RoleIn):
    """调整用户角色（user/admin）。"""
    if payload.role not in ("user", "admin"):
        raise HttpError(400, "角色不合法")
    u = User.objects.filter(id=user_id).first()
    if not u:
        raise HttpError(404, "用户不存在")
    u.role = payload.role
    u.save(update_fields=["role"])
    write_audit(
        request,
        "user.set_role",
        f"user:{user_id}",
        payload.role,
    )
    return {"success": True}


class AccountActionIn(Schema):
    action: str  # ban/unban/mute/unmute/lock/unlock
    reason: str = ""
    days: int = 7  # 天数；999=永久


@router.post(
    "/users/{user_id}/account", summary="账号管理（封禁/禁言/限制登录，可设时长）"
)
@admin_required
def account_action(request, user_id: int, payload: AccountActionIn):
    """账号管理：封禁/禁言/限制登录（可设天数，999=永久），并发站内通知。"""
    from django.utils import timezone as tz

    u = User.objects.filter(id=user_id).first()
    if not u:
        raise HttpError(404, "用户不存在")
    if u.id == request.auth.id:
        raise HttpError(400, "不能操作自己的账号")
    if u.role == "admin":
        raise HttpError(400, "不能对管理员执行该操作")

    note = (payload.reason or "").strip()[:255]
    days = max(1, min(payload.days, 999))

    if payload.action == "ban":
        u.banned = True
        u.banned_reason = note or "违反社区规范"
        u.save(update_fields=["banned", "banned_reason"])
    elif payload.action == "unban":
        u.banned = False
        u.banned_reason = ""
        u.save(update_fields=["banned", "banned_reason"])
    elif payload.action == "mute":
        if days >= 999:
            import datetime as _dt

            u.muted_until = _dt.datetime(9999, 1, 1, tzinfo=tz.get_current_timezone())
            note = "永久禁言" + (f"：{note}" if note else "")
        else:
            u.muted_until = tz.now() + tz.timedelta(days=days)
            note = f"禁言{days}天至 {u.muted_until:%Y-%m-%d %H:%M}" + (
                f"：{note}" if note else ""
            )
        u.save(update_fields=["muted_until"])
    elif payload.action == "unmute":
        u.muted_until = None
        u.save(update_fields=["muted_until"])
    elif payload.action == "lock":
        if days >= 999:
            u.is_active = False
            u.locked_until = None
            u.save(update_fields=["is_active", "locked_until"])
            note = "永久限制登录" + (f"：{note}" if note else "")
        else:
            u.locked_until = tz.now() + tz.timedelta(days=days)
            u.save(update_fields=["locked_until"])
            note = f"限制登录{days}天至 {u.locked_until:%Y-%m-%d %H:%M}" + (
                f"：{note}" if note else ""
            )
    elif payload.action == "unlock":
        u.locked_until = None
        u.is_active = True
        u.save(update_fields=["locked_until", "is_active"])
    else:
        raise HttpError(400, "未知操作")

    write_audit(request, f"user.{payload.action}", f"user:{user_id}:{u.username}", note)

    # 站内通知用户（账号状态变化可见）
    try:
        from apps.notifications.models import Notification

        action_names = {
            "ban": "封禁",
            "unban": "解除封禁",
            "mute": "禁言",
            "unmute": "解除禁言",
            "lock": "限制登录",
            "unlock": "恢复登录",
        }
        Notification.objects.create(
            user=u,
            type="account",
            title=f"账号状态：{action_names.get(payload.action, payload.action)}",
            content=note or "如有疑问请联系管理员申诉",
        )
    except Exception:
        pass

    return {
        "success": True,
        "banned": u.banned,
        "muted_until": u.muted_until.isoformat() if u.muted_until else None,
        "locked_until": u.locked_until.isoformat() if u.locked_until else None,
        "is_active": u.is_active,
    }


# ----------------------------------------------------------------------
# 敏感词管理
# ----------------------------------------------------------------------
@router.get("/sensitive-words", summary="敏感词列表")
@any_admin_required
def sensitive_words(request):
    """敏感词列表（内置基线 + 后台动态词表）。"""
    words = list(
        SensitiveWord.objects.filter(is_active=True).values_list("word", flat=True)
    )
    return {"success": True, "data": sorted(set(words) | set(BUILTIN_WORDS))}


@router.post("/sensitive-words", summary="新增敏感词")
@any_admin_required
def add_sensitive_word(request, payload: SensitiveWordIn):
    """新增敏感词。"""
    obj, created = SensitiveWord.objects.get_or_create(word=payload.word.strip())
    obj.is_active = payload.is_active
    obj.save(update_fields=["is_active"])
    write_audit(request, "sensitive_word.add", payload.word, "")
    return {"success": True, "created": created}


@router.delete("/sensitive-words/{word}", summary="删除敏感词")
@any_admin_required
def delete_sensitive_word(request, word: str):
    """删除敏感词。"""
    SensitiveWord.objects.filter(word=word).delete()
    write_audit(request, "sensitive_word.delete", word, "")
    return {"success": True}


# ----------------------------------------------------------------------
# 审计日志
# ----------------------------------------------------------------------
@router.get("/audit-logs/export", summary="审计日志导出 CSV（全局管理员）")
@admin_required
def audit_logs_export(request, username: str = "", action: str = ""):
    """审计日志导出 CSV（最多 5000 条）。"""
    import csv
    import io

    from django.http import HttpResponse

    qs = AuditLog.objects.all().order_by("-created_at")
    if username:
        qs = qs.filter(username__icontains=username)
    if action:
        qs = qs.filter(action__icontains=action)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["时间", "操作者", "动作", "对象", "详情", "级别", "IP"])
    for a in qs[:5000]:
        writer.writerow(
            [
                a.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                a.username,
                a.action,
                a.target,
                a.detail,
                a.level,
                a.ip,
            ]
        )
    resp = HttpResponse(buf.getvalue(), content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="audit_logs.csv"'
    write_audit(request, "audit.export", "audit-logs", f"{qs.count()} rows")
    return resp


@router.get("/audit-logs", summary="审计日志（全局管理员，可按操作者/动作筛选）")
@admin_required
def audit_logs(
    request, page: int = 1, page_size: int = 0, username: str = "", action: str = ""
):
    """审计日志列表：按操作者/动作筛选，分页。"""
    page_size = page_size or settings.PAGE_SIZE
    qs = AuditLog.objects.all()
    if username:
        qs = qs.filter(username__icontains=username)
    if action:
        qs = qs.filter(action__icontains=action)
    items, meta = paginate(qs, page, page_size)
    return {
        "success": True,
        "data": [
            {
                "id": a.id,
                "username": a.username,
                "action": a.action,
                "target": a.target,
                "detail": a.detail,
                "level": a.level,
                "ip": a.ip,
                "created_at": a.created_at.isoformat(),
            }
            for a in items
        ],
        "meta": meta,
    }


# ----------------------------------------------------------------------
# 回收站（软删除内容，30 天后可物理清理）
# ----------------------------------------------------------------------
@router.get("/trash", summary="回收站列表（软删除的手账/评论）")
@any_admin_required
def trash_list(request, kind: str = "journal"):
    """回收站列表（软删除的手账/评论）。"""
    from django.utils import timezone

    if kind == "journal":
        qs = (
            Journal.objects.filter(deleted_at__isnull=False)
            .select_related("user", "landmark")
            .order_by("-deleted_at")[:100]
        )
        data = [
            {
                "id": j.id,
                "kind": "journal",
                "title": j.title,
                "content": (j.content or "")[:120],
                "user": j.user.nickname or j.user.username,
                "landmark": j.landmark.name,
                "deleted_at": j.deleted_at.isoformat(),
            }
            for j in qs
        ]
    else:
        from apps.comments.models import Comment as C

        qs = (
            C.objects.filter(deleted_at__isnull=False)
            .select_related("user", "landmark")
            .order_by("-deleted_at")[:100]
        )
        data = [
            {
                "id": c.id,
                "kind": "comment",
                "title": "",
                "content": c.content[:120],
                "user": c.user.nickname or c.user.username,
                "landmark": c.landmark.name if c.landmark_id else "",
                "deleted_at": c.deleted_at.isoformat(),
            }
            for c in qs
        ]
    return {"success": True, "data": data}


@router.post("/trash/{kind}/{item_id}/restore", summary="从回收站恢复")
@any_admin_required
def trash_restore(request, kind: str, item_id: int):
    """从回收站恢复单条内容。"""
    if kind == "journal":
        obj = Journal.objects.filter(id=item_id).first()
        if not obj:
            raise HttpError(404, "手账不存在")
        obj.deleted_at = None
        obj.is_public = True
        obj.save(update_fields=["deleted_at", "is_public"])
        write_audit(request, "journal.trash_restore", f"journal:{item_id}", obj.title)
    else:
        from apps.comments.models import Comment as C

        obj = C.objects.filter(id=item_id).first()
        if not obj:
            raise HttpError(404, "评论不存在")
        obj.deleted_at = None
        obj.is_hidden = False
        obj.save(update_fields=["deleted_at", "is_hidden"])
        write_audit(
            request, "comment.trash_restore", f"comment:{item_id}", obj.content[:50]
        )
    return {"success": True}


@router.post("/trash/purge", summary="物理清理 30 天前的回收站内容")
@any_admin_required
def trash_purge(request):
    """物理清理 30 天前的回收站内容。"""
    from django.utils import timezone

    cutoff = timezone.now() - timezone.timedelta(days=30)
    j, cj = Journal.objects.filter(deleted_at__lt=cutoff).delete()
    c, cc = Comment.objects.filter(deleted_at__lt=cutoff).delete()
    total = cj + cc
    write_audit(request, "trash.purge", "trash", f"{total} items")
    return {"success": True, "purged": total}

# ----------------------------------------------------------------------
# 地标管理（路由函数定义在 admin_landmarks.py，挂在本 router 的 /landmarks/* 下；
# import 即注册。放在文件尾避免循环导入。）
# ----------------------------------------------------------------------
from api import admin_landmarks  # noqa: E402,F401
