"""行旅识景 TripScape
创建日期：2025-09-01

JWT 认证 + 权限校验。

安全底线：
- 密码使用 Django PBKDF2 哈希存储
- 登录接口限流（见 accounts/api login 的 throttle）
- Bearer Token 为 JWT（PyJWT），带过期时间
"""

import time
from functools import wraps

import jwt as pyjwt
from django.conf import settings
from django.contrib.auth import get_user_model
from ninja.security import HttpBearer

User = get_user_model()


def make_token(user):
    """为用户签发 JWT。"""
    now = int(time.time())
    payload = {
        "user_id": user.id,
        "username": user.username,
        "exp": now + settings.JWT_EXPIRE_HOURS * 3600,
        "iat": now,
    }
    return pyjwt.encode(payload, settings.JWT_SECRET, algorithm="HS256")


def decode_token(token):
    """解析并校验 JWT，返回 payload 或 None。"""
    try:
        return pyjwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except pyjwt.PyJWTError:
        return None


class GlobalAuth(HttpBearer):
    """Ninja 全局认证。

    - 未带 token：request.auth = None（匿名），由各路由自行决定是否放行
    - token 无效：401
    """

    def authenticate(self, request, token):
        payload = decode_token(token)
        if not payload:
            return None
        try:
            user = User.objects.get(id=payload["user_id"], is_active=True)
        except User.DoesNotExist:
            return None
        request.user = user
        return user


def login_required(view):
    """匿名直接 401 的路由装饰器。"""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not getattr(request, "auth", None):
            from ninja.errors import HttpError

            raise HttpError(401, "请先登录")
        return view(request, *args, **kwargs)

    return wrapper


# ----------------------------------------------------------------------
# 角色判定
# ----------------------------------------------------------------------
def is_admin(user):
    """全局管理员。"""
    return bool(user and user.is_authenticated and user.role == "admin")


def is_local_admin(user):
    """历史兼容：旧库可能残留 local_admin 角色，视同管理员处理（新注册不会产生该角色）。"""
    return bool(
        user and user.is_authenticated and user.role in ("local_admin", "admin")
    )


def is_any_admin(user):
    """任意管理员角色（admin；兼容历史 local_admin）。"""
    return is_admin(user) or is_local_admin(user)


def admin_required(view):
    """仅全局管理员。"""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        from ninja.errors import HttpError

        if not is_admin(request.auth):
            raise HttpError(403, "需要全局管理员权限")
        return view(request, *args, **kwargs)

    return wrapper


def any_admin_required(view):
    """要求任意管理员角色（admin；兼容历史 local_admin）。"""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        from ninja.errors import HttpError

        if not is_any_admin(request.auth):
            raise HttpError(403, "需要管理员权限")
        return view(request, *args, **kwargs)

    return wrapper
