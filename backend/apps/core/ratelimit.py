"""行旅识景 TripScape
创建日期：2025-09-01

内存滑窗限流（登录等敏感接口）。

生产多副本部署时建议切换到 Redis 令牌桶；单机开发足够。
"""

import time


class RateLimiter:
    def __init__(self):
        self._hits = {}  # key -> list[timestamp]

    def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        now = time.time()
        hits = [t for t in self._hits.get(key, []) if now - t < window_seconds]
        if len(hits) >= limit:
            self._hits[key] = hits
            return False
        hits.append(now)
        self._hits[key] = hits
        return True


login_limiter = RateLimiter()
