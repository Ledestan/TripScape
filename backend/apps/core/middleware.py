"""行旅识景 TripScape
创建日期：2025-09-01

请求日志中间件：request_id + 耗时 + 用户 + 路径。
"""

import logging
import time
import uuid

logger = logging.getLogger("tripscape.request")


class RequestLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = uuid.uuid4().hex[:12]
        request._start = time.time()
        response = self.get_response(request)
        elapsed_ms = (time.time() - request._start) * 1000
        user = getattr(request, "user", None)
        username = (
            getattr(user, "username", "-")
            if user and user.is_authenticated
            else "anonymous"
        )
        logger.info(
            "[%s] %s %s -> %s %.1fms user=%s",
            request.request_id,
            request.method,
            request.path,
            response.status_code,
            elapsed_ms,
            username,
        )
        response["X-Request-ID"] = request.request_id
        return response
