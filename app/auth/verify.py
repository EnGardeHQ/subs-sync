"""Service-to-service authentication verification"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def verify_service_token(authorization_header: Optional[str]) -> bool:
    """
    Verify service-to-service authentication token.

    Uses a shared secret between EnGarde backend and this sync service.
    In production, this should use JWT tokens or OAuth2.

    Args:
        authorization_header: Authorization header value (e.g., "Bearer <token>")

    Returns:
        True if token is valid, False otherwise
    """
    if not authorization_header:
        logger.warning("No authorization header provided")
        return False

    # Extract token from "Bearer <token>" format
    parts = authorization_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        logger.warning(f"Invalid authorization header format: {authorization_header}")
        return False

    token = parts[1]

    # Get expected token from environment
    expected_token = os.getenv("SUBS_SYNC_SERVICE_TOKEN")

    if not expected_token:
        logger.error("SUBS_SYNC_SERVICE_TOKEN not configured - authentication disabled!")
        # In development, allow requests without token if not configured
        return os.getenv("ENV", "production") == "development"

    # Verify token matches
    is_valid = token == expected_token

    if not is_valid:
        logger.warning("Invalid service token provided")

    return is_valid
