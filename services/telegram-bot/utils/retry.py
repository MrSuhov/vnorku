"""
Утилиты для повторных попыток при сетевых ошибках Telegram API.
Экспоненциальный backoff с максимальным временем ожидания 5 минут.
"""

import asyncio
import logging
import random
from functools import wraps
from typing import Callable, TypeVar, Any

logger = logging.getLogger(__name__)

# Telegram network errors that should trigger retry
RETRYABLE_ERRORS = (
    "NetworkError",
    "ConnectError",
    "TimeoutError",
    "TimedOut",
    "RetryAfter",
)

# Configuration
MAX_TOTAL_TIME = 300  # 5 minutes total
INITIAL_DELAY = 1.0   # Start with 1 second
MAX_DELAY = 60.0      # Max 60 seconds between retries
JITTER = 0.1          # 10% random jitter


def is_retryable_error(error: Exception) -> bool:
    """Check if error is a network error that should trigger retry."""
    error_str = str(type(error).__name__) + str(error)
    return any(err_type in error_str for err_type in RETRYABLE_ERRORS)


async def retry_telegram_operation(
    operation: Callable,
    *args,
    max_total_time: float = MAX_TOTAL_TIME,
    initial_delay: float = INITIAL_DELAY,
    max_delay: float = MAX_DELAY,
    **kwargs
) -> Any:
    """
    Execute a Telegram API operation with exponential backoff retry.

    Args:
        operation: Async callable to execute
        *args: Positional arguments for operation
        max_total_time: Maximum total time to retry (default 5 min)
        initial_delay: Initial delay between retries
        max_delay: Maximum delay between retries
        **kwargs: Keyword arguments for operation

    Returns:
        Result of the operation

    Raises:
        TimeoutError: If max_total_time exceeded
        Exception: Last error if all retries failed
    """
    start_time = asyncio.get_event_loop().time()
    delay = initial_delay
    attempt = 0
    last_error = None

    while True:
        elapsed = asyncio.get_event_loop().time() - start_time

        if elapsed >= max_total_time:
            logger.error(f"Retry timeout after {elapsed:.1f}s and {attempt} attempts")
            raise TimeoutError(f"Operation timed out after {max_total_time}s") from last_error

        try:
            attempt += 1
            return await operation(*args, **kwargs)

        except Exception as e:
            last_error = e

            if not is_retryable_error(e):
                # Non-retryable error, raise immediately
                logger.error(f"Non-retryable error: {type(e).__name__}: {e}")
                raise

            # Calculate remaining time
            elapsed = asyncio.get_event_loop().time() - start_time
            remaining = max_total_time - elapsed

            if remaining <= 0:
                logger.error(f"Retry timeout after {attempt} attempts: {e}")
                raise TimeoutError(f"Operation timed out after {max_total_time}s") from e

            # Add jitter to prevent thundering herd
            jittered_delay = delay * (1 + random.uniform(-JITTER, JITTER))
            actual_delay = min(jittered_delay, remaining, max_delay)

            logger.warning(
                f"Retry attempt {attempt} after {type(e).__name__}, "
                f"waiting {actual_delay:.1f}s (elapsed: {elapsed:.1f}s)"
            )

            await asyncio.sleep(actual_delay)

            # Exponential backoff
            delay = min(delay * 2, max_delay)


def with_retry(
    max_total_time: float = MAX_TOTAL_TIME,
    initial_delay: float = INITIAL_DELAY,
    max_delay: float = MAX_DELAY
):
    """
    Decorator for adding retry logic to async functions.

    Usage:
        @with_retry(max_total_time=300)
        async def send_message(...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_telegram_operation(
                func,
                *args,
                max_total_time=max_total_time,
                initial_delay=initial_delay,
                max_delay=max_delay,
                **kwargs
            )
        return wrapper
    return decorator


class RetryableBot:
    """
    Wrapper around Telegram Bot that adds retry logic to API calls.
    """

    def __init__(self, bot, max_total_time: float = MAX_TOTAL_TIME):
        self._bot = bot
        self._max_total_time = max_total_time

    async def send_message(self, *args, **kwargs):
        """Send message with retry."""
        return await retry_telegram_operation(
            self._bot.send_message,
            *args,
            max_total_time=self._max_total_time,
            **kwargs
        )

    async def edit_message_text(self, *args, **kwargs):
        """Edit message with retry."""
        return await retry_telegram_operation(
            self._bot.edit_message_text,
            *args,
            max_total_time=self._max_total_time,
            **kwargs
        )

    async def answer_callback_query(self, *args, **kwargs):
        """Answer callback query with retry."""
        return await retry_telegram_operation(
            self._bot.answer_callback_query,
            *args,
            max_total_time=self._max_total_time,
            **kwargs
        )

    def __getattr__(self, name):
        """Forward other attributes to underlying bot."""
        return getattr(self._bot, name)
