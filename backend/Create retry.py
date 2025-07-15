import asyncio
import random
import logging
from functools import wraps

logger = logging.getLogger(__name__)

def retry_with_backoff(max_retries: int, base_delay: float = 1.0, max_delay: float = 10.0):
    """
    Decorator to retry an async function with exponential backoff and jitter.

    :param max_retries: Maximum number of retries before giving up.
    :param base_delay: Initial delay in seconds.
    :param max_delay: Maximum delay cap in seconds.
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    # If we've exhausted all retries, re-raise
                    if attempt >= max_retries:
                        logger.error(
                            f"[{func.__name__}] Failed after {attempt} attempts: {e}"
                        )
                        raise

                    # Exponential backoff with jitter
                    exp_delay = base_delay * (2 ** attempt)
                    delay = min(exp_delay, max_delay)
                    jitter = random.uniform(0, delay)
                    logger.warning(
                        f"[{func.__name__}] Attempt {attempt+1}/{max_retries} failed "
                        f"with error: {e!r}. Retrying in {jitter:.2f}s."
                    )
                    await asyncio.sleep(jitter)

        return wrapper
    return decorator
