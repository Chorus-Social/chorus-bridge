from __future__ import annotations

import time
from collections import defaultdict
from typing import Dict, Optional

from fastapi import Header, HTTPException, status

from chorus_bridge.core.settings import BridgeSettings


class RateLimiter:
    """
    Anonymity-preserving rate limiter using X-Chorus-Instance-Id.
    Uses a fixed window counter for simplicity.
    """

    def __init__(self, settings: BridgeSettings):
        """Initializes the RateLimiter with Bridge settings.

        Args:
            settings: The BridgeSettings instance containing rate limit configurations.
        """
        self.settings = settings
        # {instance_id: {timestamp_window: count}}
        self.requests: Dict[str, Dict[int, int]] = defaultdict(lambda: defaultdict(int))
        self.window_size = 1  # 1 second window for RPS

    async def __call__(
        self,
        x_chorus_instance_id: str = Header(..., alias="X-Chorus-Instance-Id"),
    ):
        """Applies rate limiting based on the X-Chorus-Instance-Id header.

        Args:
            x_chorus_instance_id: The ID of the Chorus instance from the request header.

        Raises:
            HTTPException: If the rate limit or burst limit is exceeded.
        """
        current_time = int(time.time())
        current_window = current_time // self.window_size

        # Clean up old windows (optional, but good for memory)
        for instance_id in list(self.requests.keys()):
            for window in list(self.requests[instance_id].keys()):
                if window < current_window - 1:  # Keep current and previous window
                    del self.requests[instance_id][window]
            if not self.requests[instance_id]:
                del self.requests[instance_id]

        self.requests[x_chorus_instance_id][current_window] += 1
        current_count = self.requests[x_chorus_instance_id][current_window]

        # Simple fixed window check for default_rps
        if current_count > self.settings.federation_rate_limits_default_rps:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded for this instance.",
            )

        # Burst limit check (across current and previous window for a smoother burst)
        # This is a simplified burst check. A true token bucket would be more accurate.
        total_recent_requests = sum(
            self.requests[x_chorus_instance_id][w]
            for w in [current_window, current_window - 1]
            if w in self.requests[x_chorus_instance_id]
        )
        if total_recent_requests > self.settings.federation_rate_limits_burst:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Burst rate limit exceeded for this instance.",
            )


# Global instance of the rate limiter, initialized in app.py
rate_limiter: Optional[RateLimiter] = None
