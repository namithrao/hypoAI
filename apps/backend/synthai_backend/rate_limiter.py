"""
Rate limiter for Anthropic API calls.

Prevents 429 errors by tracking tokens and requests per minute.
"""

import asyncio
import logging
import time
from collections import deque
from typing import Deque, Tuple

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Sliding window rate limiter for API calls.

    Tracks tokens and requests per minute to stay within API limits.
    """

    def __init__(
        self,
        max_tokens_per_minute: int = 40000,
        max_requests_per_minute: int = 50,
        window_seconds: int = 60
    ):
        """
        Initialize rate limiter.

        Args:
            max_tokens_per_minute: Maximum tokens per minute (Claude 3.5 Sonnet: 40k)
            max_requests_per_minute: Maximum requests per minute (Claude 3.5 Sonnet: 50)
            window_seconds: Time window in seconds (default 60)
        """
        self.max_tokens_per_minute = max_tokens_per_minute
        self.max_requests_per_minute = max_requests_per_minute
        self.window_seconds = window_seconds

        # Store (timestamp, token_count) tuples
        self.token_history: Deque[Tuple[float, int]] = deque()
        self.request_history: Deque[float] = deque()

    def _clean_old_entries(self, current_time: float) -> None:
        """Remove entries older than the time window."""
        cutoff_time = current_time - self.window_seconds

        # Clean token history
        while self.token_history and self.token_history[0][0] < cutoff_time:
            self.token_history.popleft()

        # Clean request history
        while self.request_history and self.request_history[0] < cutoff_time:
            self.request_history.popleft()

    def _get_current_usage(self) -> Tuple[int, int]:
        """
        Get current token and request usage.

        Returns:
            (total_tokens, total_requests) in current window
        """
        current_time = time.time()
        self._clean_old_entries(current_time)

        total_tokens = sum(tokens for _, tokens in self.token_history)
        total_requests = len(self.request_history)

        return total_tokens, total_requests

    def _calculate_wait_time(self, token_count: int) -> float:
        """
        Calculate how long to wait before making request.

        Args:
            token_count: Estimated tokens for the next request

        Returns:
            Wait time in seconds (0 if no wait needed)
        """
        current_time = time.time()
        self._clean_old_entries(current_time)

        total_tokens, total_requests = self._get_current_usage()

        wait_times = []

        # Check token limit
        if total_tokens + token_count > self.max_tokens_per_minute:
            if self.token_history:
                oldest_timestamp = self.token_history[0][0]
                wait_until = oldest_timestamp + self.window_seconds
                wait_times.append(wait_until - current_time)

        # Check request limit
        if total_requests + 1 > self.max_requests_per_minute:
            if self.request_history:
                oldest_timestamp = self.request_history[0]
                wait_until = oldest_timestamp + self.window_seconds
                wait_times.append(wait_until - current_time)

        return max(wait_times) if wait_times else 0.0

    async def acquire(self, estimated_tokens: int = 1000) -> None:
        """
        Acquire permission to make an API call.

        Waits if necessary to stay within rate limits.

        Args:
            estimated_tokens: Estimated token count for the request
        """
        wait_time = self._calculate_wait_time(estimated_tokens)

        if wait_time > 0:
            logger.warning(
                f"Rate limit approaching. Waiting {wait_time:.2f}s before next request. "
                f"Current usage: {self._get_current_usage()}"
            )
            await asyncio.sleep(wait_time + 0.1)  # Add small buffer

        # Record this request
        current_time = time.time()
        self.token_history.append((current_time, estimated_tokens))
        self.request_history.append(current_time)

        current_tokens, current_requests = self._get_current_usage()
        logger.debug(
            f"Rate limiter: {current_tokens}/{self.max_tokens_per_minute} tokens, "
            f"{current_requests}/{self.max_requests_per_minute} requests"
        )

    def record_actual_usage(self, actual_tokens: int) -> None:
        """
        Update the last recorded request with actual token usage.

        Args:
            actual_tokens: Actual tokens used by the API call
        """
        if self.token_history:
            timestamp, estimated_tokens = self.token_history.pop()
            self.token_history.append((timestamp, actual_tokens))

            logger.debug(
                f"Updated token usage: estimated={estimated_tokens}, actual={actual_tokens}"
            )

    def get_usage_stats(self) -> dict:
        """
        Get current usage statistics.

        Returns:
            Dictionary with usage stats
        """
        total_tokens, total_requests = self._get_current_usage()

        return {
            "tokens_used": total_tokens,
            "tokens_limit": self.max_tokens_per_minute,
            "tokens_remaining": self.max_tokens_per_minute - total_tokens,
            "requests_used": total_requests,
            "requests_limit": self.max_requests_per_minute,
            "requests_remaining": self.max_requests_per_minute - total_requests,
            "window_seconds": self.window_seconds
        }
