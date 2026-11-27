"""
行旅识景 TripScape / config/settings/prod

生产环境覆盖：DEBUG 关闭 + 安全头 + 启动期密钥校验（密钥从 .env 注入）。

安全底线：
- DEBUG 恒为 False（异常只回 JSON 短句，不回堆栈）
- SECRET_KEY / JWT_SECRET 仍是仓库默认值时启动直接失败——
  否则任何人都能用公开默认值伪造 JWT 与签名 Cookie
"""

from apps.core.checks import validate_secrets

DEBUG = False

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# 生产关闭接口文档（少暴露一份完整的接口清单与参数结构）
API_DOCS_ENABLED = False

# 启动即校验（配置错误直接拒绝启动，而不是"带病上线"）
validate_secrets(SECRET_KEY, JWT_SECRET, DEBUG)  # noqa: F405
