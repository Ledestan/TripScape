"""
行旅识景 TripScape / apps/core/checks

启动期安全配置校验，提供:
    1. validate_secrets：生产环境拒绝仓库默认密钥
    2. resolve_debug：DEBUG 开关的推导（冻结包/生产强制关闭）

依赖:
    依赖库: 仅 Django

用法:
    from apps.core.checks import validate_secrets, resolve_debug
    validate_secrets(settings.SECRET_KEY, settings.JWT_SECRET, settings.DEBUG)

注意:
    默认密钥写在仓库里（dev 默认值与打包分发包），一旦进生产，任何人都能
    伪造 JWT（alg=HS256 共用密钥）或伪造签名 Cookie，因此必须启动即失败。
"""

from django.core.exceptions import ImproperlyConfigured

# 仓库内出现过的默认值（不得用于任何对外环境）
DEFAULT_SECRETS = {
    "",
    "change-me-in-production",
    "django-insecure-tripscape-dev-key-change-me",
    "tripscape-jwt-dev-secret",
}

MIN_SECRET_LENGTH = 32


def validate_secrets(secret_key: str, jwt_secret: str, debug: bool) -> None:
    """校验密钥强度；DEBUG 环境放行（本机开发不应被卡住）。

    抛出：
        ImproperlyConfigured：非 DEBUG 环境使用默认/过短密钥。
    """
    if debug:
        return
    for label, value in (("DJANGO_SECRET_KEY", secret_key), ("JWT_SECRET", jwt_secret)):
        secret = (value or "").strip()
        if secret in DEFAULT_SECRETS:
            raise ImproperlyConfigured(
                f"{label} 仍是仓库默认值，请在 .env 中改为随机长串后再启动"
            )
        if len(secret) < MIN_SECRET_LENGTH:
            raise ImproperlyConfigured(f"{label} 长度不足 {MIN_SECRET_LENGTH} 位")


def resolve_debug(env_debug: bool, frozen: bool) -> bool:
    """推导 DEBUG：冻结（分发包）强制关闭，否则以环境变量为准。"""
    return bool(env_debug) and not frozen
