import redis

from app.config import get_settings

_client: redis.Redis | None = None
PROCESSING_KEY = "risk:review_processing"


def _connect(ssl: bool) -> redis.Redis:
    settings = get_settings()
    return redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        username=settings.redis_username,
        password=settings.redis_password,
        decode_responses=True,
        ssl=ssl,
        socket_connect_timeout=8,
        socket_timeout=8,
    )


def reset_redis() -> None:
    global _client
    if _client is not None:
        try:
            _client.close()
        except Exception:
            pass
    _client = None


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        settings = get_settings()
        attempts = [settings.redis_ssl, not settings.redis_ssl]
        last_error: Exception | None = None
        for ssl in attempts:
            client = _connect(ssl)
            try:
                client.ping()
                _client = client
                break
            except Exception as exc:
                last_error = exc
                try:
                    client.close()
                except Exception:
                    pass
        if _client is None:
            raise last_error or RuntimeError("Redis connection failed")
    return _client


def _queue_key() -> str:
    return get_settings().redis_queue_key


def enqueue_review(review_id: str) -> None:
    get_redis().lpush(_queue_key(), review_id)


def claim_review(timeout: int = 2) -> str | None:
    """Move a job to a processing list so a crash does not drop it."""
    result = get_redis().brpoplpush(_queue_key(), PROCESSING_KEY, timeout=timeout)
    return result


def ack_review(review_id: str) -> None:
    get_redis().lrem(PROCESSING_KEY, 1, review_id)


def requeue_inflight() -> int:
    """Put in-flight jobs back on the main queue after a restart."""
    client = get_redis()
    moved = 0
    while True:
        review_id = client.rpoplpush(PROCESSING_KEY, _queue_key())
        if not review_id:
            break
        moved += 1
        if moved > 1000:
            break
    return moved


def dequeue_review(timeout: int = 2) -> str | None:
    return claim_review(timeout=timeout)


def queue_depth() -> int:
    client = get_redis()
    return int(client.llen(_queue_key())) + int(client.llen(PROCESSING_KEY))


def ping_redis() -> bool:
    try:
        return bool(get_redis().ping())
    except Exception:
        reset_redis()
        return False
