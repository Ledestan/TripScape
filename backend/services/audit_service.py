"""
行旅识景 TripScape / services/audit_service

core 服务：审计日志写入。
"""

import logging

from apps.admin_panel.models import AuditLog

logger = logging.getLogger("tripscape.audit")


def write_audit(
    request, action: str, target: str, detail: str = "", level: str = "info"
):
    """记录后台/敏感操作审计。

    参数：
        request : 当前请求（取 user / ip / request_id）
        action  : 动作，如 comment.hide
        target  : 对象标识，如 comment:12
        detail  : 补充说明
        level   : info / warning
    """
    user = getattr(request, "auth", None) or getattr(request, "user", None)
    try:
        return AuditLog.objects.create(
            user=user if getattr(user, "is_authenticated", False) else None,
            username=getattr(user, "username", "") or "",
            action=action,
            target=target,
            detail=detail or "",
            level=level,
            ip=_client_ip(request),
            request_id=getattr(request, "request_id", ""),
        )
    except Exception as exc:
        logger.warning("审计写入失败：%s", exc)
        return None


def _client_ip(request):
    """审计用来源 IP（与限流同口径，不采信伪造的 X-Forwarded-For）。"""
    from apps.core.net import client_ip

    return client_ip(request)
