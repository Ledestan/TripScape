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


class AccountForbidden(Exception):
    """账号被处罚（封禁/限登/禁言到期前）拒绝访问。"""

    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


def check_account_status(user) -> None:
    """校验账号处罚状态（封禁/限登）。

    每次令牌认证调用——处罚（admin 封禁/限登）立即对旧令牌生效，
    无需等令牌自然过期（TS-01）。

    抛出：
        AccountForbidden（含中文原因）；正常返回 None。
    """
    if user.banned:
        raise AccountForbidden(
            f"账号已被封禁{('：' + user.banned_reason) if user.banned_reason else ''}"
        )
    if user.is_locked:
        until = user.locked_until.strftime("%Y-%m-%d %H:%M")
        raise AccountForbidden(f"账号被限制登录至 {until}")


def is_muted(user) -> bool:
    """禁言判定（发布/编辑评论与手账前调用，TS-13）。"""
    return bool(user.is_muted)


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
    - 账号被封禁/限登：403（处罚立即对旧令牌生效，TS-01）
    """

    def authenticate(self, request, token):
        payload = decode_token(token)
        if not payload:
            return None
        try:
            user = User.objects.get(id=payload["user_id"], is_active=True)
        except User.DoesNotExist:
            return None
        try:
            check_account_status(user)
        except AccountForbidden as exc:
            from ninja.errors import HttpError

            request.forbidden_reason = exc.reason
            raise HttpError(403, exc.reason)
        request.user = user
        return user


class OptionalAuth:
    """公开接口的可选认证（TS-04）。

    Ninja 认证器返回假值一律 401（operation 层 if result 判定），
    因此本类在匿名时返回 AnonymousUser 哨兵而非 None：
    - 无 Authorization 头 / 令牌无效：匿名（哨兵），公开数据放行；
    - 带有效令牌：解析真实用户挂到 request.auth/user；
    - 封禁/限登账号：403（公开接口不得绕过处罚）。
    """

    def __call__(self, request):
        header = request.META.get("HTTP_AUTHORIZATION", "")
        token = header[7:].strip() if header.lower().startswith("bearer ") else ""
        user = None
        if token:
            payload = decode_token(token)
            if payload:
                try:
                    user = User.objects.get(id=payload["user_id"], is_active=True)
                except User.DoesNotExist:
                    user = None
        if user is not None:
            try:
                check_account_status(user)
            except AccountForbidden as exc:
                from ninja.errors import HttpError

                raise HttpError(403, exc.reason)
            request.user = user
            return user
        # 匿名哨兵（真值对象，让 Ninja 放行）
        from django.contrib.auth.models import AnonymousUser

        anon = AnonymousUser()
        request.user = anon
        return anon


def login_required(view):
    """匿名直接 401 的路由装饰器。

    OptionalAuth 匿名时挂 AnonymousUser（Ninja 真值哨兵），
    必须用 is_authenticated 判定而非真值判断。
    """

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        user = getattr(request, "auth", None)
        if not getattr(user, "is_authenticated", False):
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
