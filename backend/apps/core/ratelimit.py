"""
行旅识景 TripScape / apps/core/ratelimit

内存滑窗限流（登录/注册/重接口）。

生产多副本部署时建议切换到 Redis 令牌桶；单机开发足够。

安全口径：
- key 由调用方给出，客户端 IP 必须来自 core.net.client_ip（不接受伪造的
  X-Forwarded-For），否则限流可被任意 header 绕过。
- 计数表按窗口惰性清理，避免被大量独立 key（例如换 IP 刷接口）撑爆内存。
"""

import threading
import time

# 计数表超过该规模时开始清理过期 bucket（防止内存无界增长）
_PRUNE_THRESHOLD = 4096


class RateLimiter:
    """滑动窗口限流器（进程内）。

    用法：
        limiter = RateLimiter()
        if not limiter.allow("login:1.2.3.4", limit=10, window_seconds=60):
            raise HttpError(429, "尝试过于频繁")
    """

    def __init__(self):
        self._hits: dict[str, list[float]] = {}
        self._lock = threading.Lock()
        self._last_prune = 0.0

    def allow(self, key: str, limit: int, window_seconds: int) -> bool:
        """记一次命中并判断是否放行。超限返回 False（不记入）。"""
        now = time.time()
        window = max(1, int(window_seconds))
        with self._lock:
            hits = [t for t in self._hits.get(key, []) if now - t < window]
            if len(hits) >= limit:
                self._hits[key] = hits
                return False
            hits.append(now)
            self._hits[key] = hits
            self._maybe_prune(now)
            return True

    def _maybe_prune(self, now: float) -> None:
        """计数表过大时清理过期 bucket（每 60 秒最多一次）。"""
        if len(self._hits) < _PRUNE_THRESHOLD or now - self._last_prune < 60:
            return
        self._last_prune = now
        for key, hits in list(self._hits.items()):
            if not hits or now - hits[-1] > 3600:
                self._hits.pop(key, None)

    def reset(self) -> None:
        """清空全部计数（测试与管理命令用）。"""
        with self._lock:
            self._hits.clear()
            self._last_prune = 0.0


login_limiter = RateLimiter()
register_limiter = RateLimiter()
# 重接口（问答/识别）限流：匿名也可调用，防止单机被打满
heavy_limiter = RateLimiter()
