"""
进程内滑动窗口限流（findings #6）

无外部依赖的轻量实现：按 key 记录窗口内的请求时间戳，超限返回 False。
适用于单实例部署；多实例时应换 Redis 实现。
"""

import time

from fastapi import HTTPException

# key -> 窗口内时间戳列表
_buckets: dict[str, list[float]] = {}


def enforce_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    """超限时直接抛 429"""

    now = time.monotonic()
    bucket = [t for t in _buckets.get(key, []) if now - t < window_seconds]
    if len(bucket) >= limit:
        raise HTTPException(
            status_code=429,
            detail="请求过于频繁，请稍后再试",
        )
    bucket.append(now)
    _buckets[key] = bucket

    # 防桶无限膨胀：超过 1000 个 key 时清理过期项
    if len(_buckets) > 1000:
        expired = [k for k, ts in _buckets.items() if not ts or now - ts[-1] > window_seconds]
        for k in expired:
            _buckets.pop(k, None)


def client_key(request_ip: str | None, identity: str | None) -> str:
    """限流 key：优先用登录身份，否则用客户端 IP"""

    return identity or (request_ip or "anonymous")


def is_loopback(request_ip: str | None) -> bool:
    """服务器本地回环地址（冒烟/评测脚本直连 8000，端口未对公网开放）"""

    return request_ip in ("127.0.0.1", "::1", "localhost")
