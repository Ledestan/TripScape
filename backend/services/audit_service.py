"""行旅识景 TripScape
创建日期：2025-09-01

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
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")
