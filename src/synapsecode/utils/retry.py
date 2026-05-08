"""Retry with exponential backoff."""

import asyncio
import functools
from typing import Any, Callable, Optional, Tuple, Type


def retry_async(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
) -> Callable:
    """Decorator: retry an async function with exponential backoff."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Optional[Exception] = None
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt < max_attempts - 1:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        await asyncio.sleep(delay)
            raise last_exc  # type: ignore[misc]
        return wrapper
    return decorator
