import logging
import time

logger = logging.getLogger(__name__)


def with_retries(fn, *args, retries: int = 2, backoff_seconds: float = 1.0, **kwargs):
    """Module 8 deliverable: retry logic. Used around the network/inference
    call in each LLM provider's generate() -- not around streaming, since
    retrying a partially-streamed response to the client isn't a clean
    operation (documented as a scope decision, not an oversight)."""
    last_exc = None
    for attempt in range(retries + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if attempt < retries:
                logger.warning(
                    "LLM call failed (attempt %d/%d): %s", attempt + 1, retries + 1, exc
                )
                time.sleep(backoff_seconds * (attempt + 1))
    raise last_exc
