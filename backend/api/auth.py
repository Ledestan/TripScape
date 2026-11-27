"""
行旅识景 TripScape / api/auth

认证 API：注册 / 登录 / 当前用户 / 个人主页。

POST /api/auth/register   注册
POST /api/auth/login      登录（限流 10/min/IP）
GET  /api/auth/me         当前用户信息
GET  /api/auth/profile    个人主页聚合
PUT  /api/auth/profile    更新昵称 / 头像 / 签名
"""

from apps.core.auth import login_required, make_token
from apps.core.net import client_ip
from apps.core.ratelimit import login_limiter, register_limiter
from django.contrib.auth import get_user_model
from ninja import Router, Schema
from ninja.errors import HttpError
from services import user_service
from services.audit_service import write_audit

router = Router()

User = get_user_model()

# 头像只允许站内相对路径或 http(s) 绝对地址（防 javascript:/data: 之类危险 scheme）
_ALLOWED_AVATAR_PREFIXES = ("http://", "https://")


def _clean_avatar(value) -> str:
    """校验并归一化头像地址；非法 scheme 抛 400。"""
    raw = (value or "").strip() if isinstance(value, str) else ""
    if not raw:
        return ""
    if len(raw) > 512:
        raise HttpError(400, "头像地址过长（最多 512 字符）")
    lowered = raw.lower()
    if raw.startswith("/") and not raw.startswith("//"):
        return raw
    if lowered.startswith(_ALLOWED_AVATAR_PREFIXES):
        return raw
    raise HttpError(400, "头像地址只支持站内路径或 http(s) 链接")


class RegisterIn(Schema):
    username: str
    password: str
    nickname: str = ""


class LoginIn(Schema):
    username: str
    password: str


class ProfileUpdateIn(Schema):
    # 部分更新语义（TS-17）：仅显式提交的字段被更新；
    # Optional 默认 None = 未提交，空字符串 = 显式清空
    nickname: str = None
    avatar: str = None
    bio: str = None


class PrivacyUpdateIn(Schema):
    public_footprints: bool = None
    public_journals: bool = None
    public_comments: bool = None
    public_favorites: bool = None
    public_badges: bool = None


class TokenOut(Schema):
    token: str
    user: dict


@router.post("/register", response=TokenOut, auth=None, summary="用户注册")
def register(request, payload: RegisterIn):
    """用户注册：用户名限英文/数字/下划线，密码≥6位且含字母数字。"""
    ip = client_ip(request)
    # 注册刷号防护（每 IP 5 次/分钟）
    if not register_limiter.allow(f"register:{ip}", limit=5, window_seconds=60):
        raise HttpError(429, "注册过于频繁，请稍后再试")
    ok, result = user_service.register_user(
        username=payload.username.strip(),
        password=payload.password,
        nickname=payload.nickname.strip(),
    )
    if not ok:
        raise HttpError(400, str(result))
    return {"token": make_token(result), "user": _user_dict(result)}


@router.post("/login", response=TokenOut, auth=None, summary="用户登录（限流）")
def login(request, payload: LoginIn):
    """账号密码登录（IP + 账号双限流），返回 JWT Token 与用户信息。"""
    ip = client_ip(request)
    username = payload.username.strip()
    # IP 维度：拦同一来源的批量尝试
    if not login_limiter.allow(f"login:ip:{ip}", limit=10, window_seconds=60):
        raise HttpError(429, "尝试过于频繁，请稍后再试")
    # 账号维度：拦换 IP 的定向爆破（阈值放宽，避免误伤正常重试）
    if username and not login_limiter.allow(
        f"login:user:{username.lower()}", limit=20, window_seconds=60
    ):
        raise HttpError(429, "尝试过于频繁，请稍后再试")
    user, msg = user_service.login_user(username, payload.password)
    if user is None:
        raise HttpError(400, msg)
    return {"token": make_token(user), "user": _user_dict(user)}


@router.get("/me", summary="当前用户")
@login_required
def me(request):
    """当前登录用户信息。"""
    return _user_dict(request.auth)


@router.get("/profile", summary="个人主页：足迹/手账/评论/收藏")
@login_required
def profile(request):
    """个人主页聚合：五类内容的计数与列表（含坐标供前端飞行）。"""
    return user_service.user_profile(request.auth)


@router.put("/profile", summary="更新个人资料")
@login_required
def update_profile(request, payload: ProfileUpdateIn):
    """更新昵称/头像/签名（只改显式提交的字段，TS-17）。"""
    user = request.auth
    fields = payload.dict(exclude_unset=True)
    update_fields = []
    if "nickname" in fields and fields["nickname"]:
        nickname = fields["nickname"].strip()
        if not nickname:
            raise HttpError(400, "昵称不能为空")
        if len(nickname) > 64:
            raise HttpError(400, "昵称最多 64 个字符")
        user.nickname = nickname
        update_fields.append("nickname")
    if "avatar" in fields:
        user.avatar = _clean_avatar(fields["avatar"])
        update_fields.append("avatar")
    if "bio" in fields:
        user.bio = (fields["bio"] or "").strip()[:255]
        update_fields.append("bio")
    if update_fields:
        user.save(update_fields=update_fields)
    return _user_dict(user)


@router.put("/privacy", summary="更新隐私设置（各内容是否公开）")
@login_required
def update_privacy(request, payload: PrivacyUpdateIn):
    """更新隐私开关（足迹/手账/评论/收藏/徽章是否公开）。"""
    user = request.auth
    fields = []
    for f in (
        "public_footprints",
        "public_journals",
        "public_comments",
        "public_favorites",
        "public_badges",
    ):
        v = getattr(payload, f)
        if v is not None:
            setattr(user, f, v)
            fields.append(f)
    if fields:
        user.save(update_fields=fields)
    return {"success": True, "privacy": {f: getattr(user, f) for f in fields}}


@router.get(
    "/{user_id}/public", summary="用户公开主页（五 Tab，按隐私设置过滤）", auth=None
)
def public_profile(request, user_id: int):
    """用户公开主页：五类内容按隐私开关过滤，含坐标供前端飞行。"""
    try:
        u = User.objects.get(id=user_id, is_active=True)
    except User.DoesNotExist:
        raise HttpError(404, "用户不存在")

    from apps.comments.models import Comment
    from apps.journals.models import Footprint, Journal
    from django.db.models import Q
    from services import badge_service

    # 公开主页口径：列表与计数必须同源，且不得泄露私密/待审/软删内容
    journals_qs = Journal.objects.filter(
        user=u,
        status="approved",
        is_public=True,
        edit_pending=False,
        deleted_at__isnull=True,
    )
    footprints_qs = Footprint.objects.filter(user=u, hidden=False)
    # 评论可见性：地标评论，或公开且已通过、未软删的手账下的评论
    comments_qs = Comment.objects.filter(
        user=u, is_hidden=False, deleted_at__isnull=True
    ).filter(
        Q(landmark__isnull=False)
        | Q(
            journal__is_public=True,
            journal__status="approved",
            journal__deleted_at__isnull=True,
        )
    )

    counts = {
        "footprints": (
            footprints_qs.values("landmark_id").distinct().count()
            if u.public_footprints
            else 0
        ),
        "journals": journals_qs.count() if u.public_journals else 0,
        "comments": comments_qs.count() if u.public_comments else 0,
        "favorites": u.favorite_landmarks.count() if u.public_favorites else 0,
    }

    footprints = []
    if u.public_footprints:
        footprints = [
            {
                "landmark_id": f.landmark_id,
                "name": f.landmark.name,
                "lat": float(f.landmark.lat),
                "lon": float(f.landmark.lon),
                "visits": f.visits,
            }
            for f in footprints_qs.select_related("landmark")[:50]
        ]

    journals = []
    if u.public_journals:
        journals = [
            {
                "id": j.id,
                "title": j.title,
                "content": j.content,
                "images": (j.images or [])[:6],
                "landmark": j.landmark.name,
                "landmark_id": j.landmark_id,
                "lat": float(j.landmark.lat),
                "lon": float(j.landmark.lon),
                "visited_at": j.visited_at.isoformat() if j.visited_at else None,
                "created_at": j.created_at.isoformat(),
            }
            for j in journals_qs.select_related("landmark")[:50]
        ]

    comments = []
    if u.public_comments:
        comments = [
            {
                "id": c.id,
                "landmark": c.landmark.name if c.landmark_id else "",
                "landmark_id": c.landmark_id,
                "journal_id": c.journal_id,
                "journal_title": c.journal.title if c.journal_id else "",
                "lat": float(c.landmark.lat) if c.landmark_id else None,
                "lon": float(c.landmark.lon) if c.landmark_id else None,
                "content": c.content,
                "created_at": c.created_at.isoformat(),
            }
            for c in comments_qs.select_related("landmark", "journal")[:50]
        ]

    favorites = []
    if u.public_favorites:
        favorites = [
            {
                "id": f.landmark.id,
                "name": f.landmark.name,
                "country": f.landmark.country or "",
                "photo": f.landmark.image_url or "",
                "lat": float(f.landmark.lat),
                "lon": float(f.landmark.lon),
                "favorited_at": f.created_at.isoformat(),
            }
            for f in u.favorite_landmarks.select_related("landmark")[:50]
        ]

    badges = []
    if u.public_badges:
        # 只给"已获得"的徽章，且不带 current/progress——
        # 这两个值来自私密内容计数（私密手账/评论），不应向他人暴露
        badges = [
            {
                "code": b["code"],
                "name": b["name"],
                "description": b["description"],
                "icon": b["icon"],
                "category": b["category"],
                "awarded_at": b["awarded_at"],
            }
            for b in badge_service.user_badges(u)
            if b["owned"]
        ]

    return {
        "user": _user_dict(u),
        "privacy": {
            "footprints": u.public_footprints,
            "journals": u.public_journals,
            "comments": u.public_comments,
            "favorites": u.public_favorites,
            "badges": u.public_badges,
        },
        "counts": counts,
        "footprints": footprints,
        "journals": journals,
        "comments": comments,
        "favorites": favorites,
        "badges": badges,
    }


def _user_dict(user):
    return {
        "id": user.id,
        "username": user.username,
        "nickname": user.nickname or user.username,
        "avatar": user.avatar,
        "bio": user.bio,
        "role": user.role,
        "created_at": user.created_at.isoformat(),
    }
