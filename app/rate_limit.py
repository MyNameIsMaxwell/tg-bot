"""Rate limiting configuration using slowapi."""

import logging
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def get_user_identifier(request: Request) -> str:
    """Extract user identifier from request for rate limiting.
    
    Uses Telegram user ID from initData header if available,
    otherwise falls back to IP address.
    """
    # Try to get Telegram user ID from header
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    if init_data:
        # Parse user ID from initData (simplified - actual parsing is in auth.py)
        import json
        from urllib.parse import parse_qsl
        try:
            parsed = dict(parse_qsl(init_data, keep_blank_values=True))
            user_json = parsed.get("user", "")
            if user_json:
                user_data = json.loads(user_json)
                user_id = user_data.get("id")
                if user_id:
                    logger.debug("Rate limit key: tg:%s", user_id)
                    return f"tg:{user_id}"
        except (json.JSONDecodeError, KeyError, Exception) as e:
            logger.warning("Failed to parse initData for rate limiting: %s", e)
    
    # Fallback to IP address - but use a more lenient approach
    ip = get_remote_address(request)
    logger.warning("Rate limit falling back to IP: %s (no valid Telegram user ID)", ip)
    return f"ip:{ip}"


# Create limiter instance with custom key function
limiter = Limiter(key_func=get_user_identifier)


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Custom handler for rate limit exceeded errors."""
    # Log every rate limit hit for debugging
    logger.warning(
        "Rate limit exceeded: %s %s (limit: %s)",
        request.method,
        request.url.path,
        exc.detail,
    )
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Слишком много запросов. Пожалуйста, подождите.",
            "retry_after": exc.detail,
        },
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
        },
    )



