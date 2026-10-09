"""行旅识景 TripScape
创建日期：2025-09-01

用户服务：注册 / 登录 / 个人资料。
"""

import re

from apps.accounts.models import User
from django.contrib.auth import authenticate
from django.db import IntegrityError
from django.utils import timezone

# 用户名：仅英文字母/数字/下划线，3-30 位
_USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,30}$")
# 密码：至少 6 位，且同时包含字母与数字（允许特殊符号）
_PASSWORD_LETTER = re.compile(r"[A-Za-z]")
_PASSWORD_DIGIT = re.compile(r"[0-9]")


def register_user(username: str, password: str, nickname: str = ""):
    """注册新用户。

    用户名仅限英文字母/数字/下划线；密码至少 6 位且需含字母与数字。

    返回：
        (ok, user_or_message)
    """
    if not username or not _USERNAME_RE.match(username):
        return False, "用户名仅限英文字母、数字、下划线，3-30 位"
    if not password or len(password) < 6:
        return False, "密码至少 6 位"
    if not _PASSWORD_LETTER.search(password) or not _PASSWORD_DIGIT.search(password):
        return False, "密码需同时包含字母和数字"
    if User.objects.filter(username=username).exists():
        return False, "用户名已存在"
    try:
        user = User.objects.create_user(
            username=username,
            password=password,
            nickname=nickname or username,
        )
        return True, user
    except IntegrityError:
        return False, "用户名已存在"


def login_user(username: str, password: str):
    """校验用户名密码。

    返回：
        (user 或 None, message)
    """
    user = authenticate(username=username, password=password)
    if user is None:
        return None, "用户名或密码错误"
    if user.banned:
        return None, f"账号已被封禁：{user.banned_reason or '违反社区规范'}"
    if not user.is_active:
        return None, "账号已被禁用"
    if user.locked_until:
        if user.locked_until > timezone.now():
            return None, f"账号被限制登录至 {user.locked_until:%Y-%m-%d %H:%M}"
        # 到期自动解锁
        user.locked_until = None
        user.save(update_fields=["locked_until"])
    return user, "ok"


def user_profile(user: User) -> dict:
    """个人主页聚合数据：足迹 / 手账 / 评论 / 收藏 数量与列表入口。"""
    from apps.comments.models import Comment
    from apps.journals.models import Footprint, Journal
    from apps.landmarks.models import Landmark

    journals_qs = Journal.objects.filter(
        user=user, status="approved", deleted_at__isnull=True
    )
    footprints = Footprint.objects.filter(user=user).select_related("landmark")
    comments_qs = Comment.objects.filter(
        user=user, is_hidden=False, deleted_at__isnull=True
    )
    favorites = user.favorite_landmarks.all()

    return {
        "user": {
            "id": user.id,
            "username": user.username,
            "nickname": user.nickname or user.username,
            "avatar": user.avatar,
            "bio": user.bio,
            "role": user.role,
            "banned": user.banned,
            "muted_until": user.muted_until.isoformat() if user.muted_until else None,
            "locked_until": (
                user.locked_until.isoformat() if user.locked_until else None
            ),
            "created_at": user.created_at.isoformat(),
        },
        "counts": {
            # MySQL 不支持 DISTINCT ON，用 values 去重计数
            "footprints": footprints.values("landmark_id").distinct().count(),
            "journals": journals_qs.count(),
            "comments": comments_qs.count(),
            "favorites": favorites.count(),
        },
        "footprints": [
            {
                "landmark_id": f.landmark_id,
                "name": f.landmark.name,
                "lat": float(f.landmark.lat),
                "lon": float(f.landmark.lon),
                "first_visited_at": f.first_visited_at.isoformat(),
                "visits": f.visits,
                "hidden": f.hidden,
            }
            for f in footprints.order_by("-first_visited_at")[:50]
        ],
        "journals": [
            {
                "id": j.id,
                "title": j.title,
                "landmark": j.landmark.name,
                "landmark_id": j.landmark_id,
                "lat": float(j.landmark.lat),
                "lon": float(j.landmark.lon),
                "visited_at": j.visited_at.isoformat() if j.visited_at else None,
                "is_public": j.is_public,
                "status": j.status,
            }
            for j in journals_qs.order_by("-visited_at")[:50]
        ],
        "comments": [
            {
                "id": c.id,
                "landmark": c.landmark.name,
                "landmark_id": c.landmark_id,
                "lat": float(c.landmark.lat),
                "lon": float(c.landmark.lon),
                "content": c.content,
                "created_at": c.created_at.isoformat(),
            }
            for c in comments_qs.order_by("-created_at")[:50]
        ],
        "favorites": [
            {
                "id": f.landmark.id,
                "name": f.landmark.name,
                "target_id": f.landmark.target_id,
                "lat": float(f.landmark.lat),
                "lon": float(f.landmark.lon),
            }
            for f in favorites.select_related("landmark")[:50]
        ],
    }
