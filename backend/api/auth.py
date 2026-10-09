"""行旅识景 TripScape
创建日期：2025-09-01

认证 API：注册 / 登录 / 当前用户 / 个人主页。

POST /api/auth/register   注册
POST /api/auth/login      登录（限流 10/min/IP）
GET  /api/auth/me         当前用户信息
GET  /api/auth/profile    个人主页聚合
PUT  /api/auth/profile    更新昵称 / 头像 / 签名
"""


from apps.core.auth import login_required, make_token
from apps.core.ratelimit import login_limiter
from django.contrib.auth import get_user_model
from ninja import Router, Schema
from ninja.errors import HttpError
from services import user_service
from services.audit_service import _client_ip, write_audit

router = Router()

User = get_user_model()


class RegisterIn(Schema):
    username: str
    password: str
    nickname: str = ""


class LoginIn(Schema):
    username: str
    password: str


class ProfileUpdateIn(Schema):
    nickname: str = ""
    avatar: str = ""
    bio: str = ""


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
    """账号密码登录（IP 限流），返回 JWT Token 与用户信息。"""
    ip = _client_ip(request)
    if not login_limiter.allow(f"login:{ip}", limit=10, window_seconds=60):
        raise HttpError(429, "尝试过于频繁，请稍后再试")
    user, msg = user_service.login_user(payload.username.strip(), payload.password)
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
    """更新昵称/头像/签名。"""
    user = request.auth
    if payload.nickname:
        user.nickname = payload.nickname.strip()[:64]
    if payload.avatar is not None:
        user.avatar = payload.avatar[:512]
    if payload.bio is not None:
        user.bio = payload.bio.strip()[:255]
    user.save(update_fields=["nickname", "avatar", "bio"])
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
    from services import badge_service

    counts = {
        "footprints": (
            Footprint.objects.filter(user=u).values("landmark_id").distinct().count()
            if u.public_footprints
            else 0
        ),
        "journals": (
            Journal.objects.filter(user=u, status="approved", is_public=True).count()
            if u.public_journals
            else 0
        ),
        "comments": (
            Comment.objects.filter(
                user=u, is_hidden=False, deleted_at__isnull=True
            ).count()
            if u.public_comments
            else 0
        ),
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
            for f in Footprint.objects.filter(user=u, hidden=False).select_related(
                "landmark"
            )[:50]
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
            for j in Journal.objects.filter(
                user=u,
                status="approved",
                is_public=True,
                edit_pending=False,
                deleted_at__isnull=True,
            ).select_related("landmark")[:50]
        ]

    comments = []
    if u.public_comments:
        comments = [
            {
                "id": c.id,
                "landmark": c.landmark.name,
                "landmark_id": c.landmark_id,
                "lat": float(c.landmark.lat),
                "lon": float(c.landmark.lon),
                "content": c.content,
                "created_at": c.created_at.isoformat(),
            }
            for c in Comment.objects.filter(
                user=u, is_hidden=False, deleted_at__isnull=True
            ).select_related("landmark")[:50]
        ]

    favorites = []
    if u.public_favorites:
        favorites = [
            {
                "id": f.landmark.id,
                "name": f.landmark.name,
                "lat": float(f.landmark.lat),
                "lon": float(f.landmark.lon),
            }
            for f in u.favorite_landmarks.select_related("landmark")[:50]
        ]

    badges = []
    if u.public_badges:
        badges = [b for b in badge_service.user_badges(u) if b["owned"]]

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
