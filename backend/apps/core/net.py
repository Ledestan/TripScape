"""
行旅识景 TripScape / apps/core/net

客户端信息来源解析。

安全口径（限流/审计共用）：
- 默认以 TCP 直连地址 REMOTE_ADDR 为准；
- 只有直连对端是受信反向代理（settings.TRUSTED_PROXY_IPS）时才采信
  X-Forwarded-For 的第一跳；
- 反之，任何人都能自带 X-Forwarded-For 伪造来源，登录限流会被逐个
  header 绕过（暴力破解防护形同虚设），审计日志也会被投毒。
"""

from django.conf import settings


def client_ip(request) -> str:
    """取客户端 IP（可安全用于限流 key 与审计）。"""
    remote = (request.META.get("REMOTE_ADDR") or "").strip()
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR") or ""
    trusted = getattr(settings, "TRUSTED_PROXY_IPS", ()) or ()
    if forwarded and remote and remote in trusted:
        first = forwarded.split(",")[0].strip()
        if first:
            return first
    return remote or "unknown"
