# retry_utils.py
import time
import asyncio
import json
from config import MAX_RETRIES, BASE_WAIT, CAP


def is_transistent_api_error(e: Exception) -> bool:
    msg = str(e).lower()
    return (
        "429" in msg
        or "500" in msg
        or "rate limit" in msg
        or "internal server" in msg
        or isinstance(e, json.JSONDecodeError)
    )


def retry_sync(fn, *args, max_retries=MAX_RETRIES, base_wait=BASE_WAIT,
                cap=180, retryable=is_transient_api_error, label="", **kwargs):
    for attempt in range(1, max_retries + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as e:
            if attempt < max_retries and retryable(e):
                wait = min(base_wait * attempt, cap)
                print(f"  ⟳ {label} Retry {attempt}/{max_retries} "
                      f"({type(e).__name__}: {e}) – warte {wait}s")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError(f"[{label}] Retries erschöpft nach {max_retries} Versuchen.")


async def retry_async(fn, *args, max_retries=MAX_RETRIES, base_wait=BASE_WAIT,
                       cap=180, retryable=is_transient_api_error, label="", **kwargs):
    for attempt in range(1, max_retries + 1):
        try:
            return await fn(*args, **kwargs)
        except Exception as e:
            if attempt < max_retries and retryable(e):
                wait = min(base_wait * attempt, cap)
                print(f"  ⟳ {label} Retry {attempt}/{max_retries} "
                      f"({type(e).__name__}: {e}) – warte {wait}s")
                await asyncio.sleep(wait)
            else:
                raise
    raise RuntimeError(f"[{label}] Retries erschöpft nach {max_retries} Versuchen.")