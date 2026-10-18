from django.core.cache import cache
import logging

logger = logging.getLogger('stylora.security')


class RateLimiter:
    """
    Lightweight, thread-safe rate limiter backed by Django's cache framework.
    Prevents API quota exhaustion, denial-of-wallet, and automated scraping.
    """

    @staticmethod
    def is_rate_limited(identifier: str, action: str, max_requests: int = 15, window_seconds: int = 60) -> bool:
        """
        Checks whether a user or IP has exceeded the allowed request threshold.

        Args:
            identifier: Unique user ID or IP string.
            action: Endpoint or action identifier (e.g. 'stylist_chat', 'suggest_metadata').
            max_requests: Maximum allowed calls in the time window.
            window_seconds: Window duration in seconds.

        Returns:
            True if rate limited (should be blocked with HTTP 429), False otherwise.
        """
        cache_key = f"ratelimit:{action}:{identifier}"
        try:
            current = cache.get(cache_key)
            if current is None:
                cache.set(cache_key, 1, timeout=window_seconds)
                return False

            if current >= max_requests:
                logger.warning(
                    "Rate limit exceeded: %s on action '%s' (count=%d, max=%d)",
                    identifier, action, current, max_requests
                )
                return True

            try:
                cache.incr(cache_key)
            except ValueError:
                cache.set(cache_key, current + 1, timeout=window_seconds)
            return False
        except Exception as e:
            # Fail open if cache backend encounters an error, to avoid blocking legitimate users
            logger.error("RateLimiter cache error: %s", str(e))
            return False
