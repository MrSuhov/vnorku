"""HTTP client with exponential backoff retry logic."""

import asyncio
import logging
from typing import Optional, Any
from functools import wraps

import httpx

logger = logging.getLogger(__name__)


class RetryableHTTPClient:
    """HTTP client wrapper with exponential backoff retries."""

    def __init__(
        self,
        base_url: str,
        max_retries: int = 5,
        base_delay: float = 0.5,
        max_delay: float = 30.0,
        timeout: float = 30.0
    ):
        """
        Initialize retryable HTTP client.

        Args:
            base_url: Base URL for requests
            max_retries: Maximum number of retry attempts (default: 5)
            base_delay: Initial delay between retries in seconds (default: 0.5)
            max_delay: Maximum delay between retries in seconds (default: 30)
            timeout: Request timeout in seconds (default: 30)
        """
        self.base_url = base_url.rstrip('/')
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.timeout = timeout

    async def _request_with_retry(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Optional[httpx.Response]:
        """
        Execute HTTP request with exponential backoff retry.

        Args:
            method: HTTP method (GET, POST, PATCH, PUT, DELETE)
            endpoint: API endpoint (will be appended to base_url)
            **kwargs: Additional arguments for httpx request

        Returns:
            httpx.Response on success, None on failure after all retries
        """
        url = f"{self.base_url}{endpoint}"
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await getattr(client, method.lower())(url, **kwargs)
                    return response

            except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as e:
                last_exception = e
                delay = min(self.base_delay * (2 ** attempt), self.max_delay)

                if attempt < self.max_retries - 1:
                    logger.warning(
                        f"HTTP {method} {url} failed (attempt {attempt + 1}/{self.max_retries}): {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(
                        f"HTTP {method} {url} failed after {self.max_retries} attempts: {e}"
                    )
            except Exception as e:
                logger.error(f"HTTP {method} {url} unexpected error: {e}")
                last_exception = e
                break

        return None

    async def get(self, endpoint: str, **kwargs) -> Optional[httpx.Response]:
        """GET request with retry."""
        return await self._request_with_retry("GET", endpoint, **kwargs)

    async def post(self, endpoint: str, **kwargs) -> Optional[httpx.Response]:
        """POST request with retry."""
        return await self._request_with_retry("POST", endpoint, **kwargs)

    async def patch(self, endpoint: str, **kwargs) -> Optional[httpx.Response]:
        """PATCH request with retry."""
        return await self._request_with_retry("PATCH", endpoint, **kwargs)

    async def put(self, endpoint: str, **kwargs) -> Optional[httpx.Response]:
        """PUT request with retry."""
        return await self._request_with_retry("PUT", endpoint, **kwargs)

    async def delete(self, endpoint: str, **kwargs) -> Optional[httpx.Response]:
        """DELETE request with retry."""
        return await self._request_with_retry("DELETE", endpoint, **kwargs)


# Pre-configured clients for services
def get_user_service_client() -> RetryableHTTPClient:
    """Get HTTP client for user-service."""
    from config.settings import settings
    return RetryableHTTPClient(
        base_url=f"http://localhost:{settings.user_service_port}",
        max_retries=5,
        base_delay=0.5
    )


def get_order_service_client() -> RetryableHTTPClient:
    """Get HTTP client for order-service."""
    from config.settings import settings
    return RetryableHTTPClient(
        base_url=f"http://localhost:{settings.order_service_port}",
        max_retries=5,
        base_delay=0.5
    )


def get_rpa_service_client() -> RetryableHTTPClient:
    """Get HTTP client for rpa-service."""
    from config.settings import settings
    return RetryableHTTPClient(
        base_url=f"http://localhost:{settings.rpa_service_port}",
        max_retries=5,
        base_delay=0.5
    )


def get_promotion_service_client() -> RetryableHTTPClient:
    """Get HTTP client for promotion-service."""
    from config.settings import settings
    return RetryableHTTPClient(
        base_url=f"http://localhost:{settings.promotion_service_port}",
        max_retries=5,
        base_delay=0.5
    )
