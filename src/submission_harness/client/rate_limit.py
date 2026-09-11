"""Simple token-bucket style request rate limiter."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class RateLimiter:
    """Limit to ``rpm`` requests per rolling 60-second window."""

    rpm: int
    _timestamps: list[float] = field(default_factory=list, repr=False)
    _lock: Lock = field(default_factory=Lock, repr=False)

    def wait(self) -> None:
        if self.rpm <= 0:
            return
        while True:
            with self._lock:
                now = time.monotonic()
                cutoff = now - 60.0
                self._timestamps = [t for t in self._timestamps if t > cutoff]
                if len(self._timestamps) < self.rpm:
                    self._timestamps.append(now)
                    return
                sleep_for = 60.0 - (now - self._timestamps[0]) + 0.01
            time.sleep(max(sleep_for, 0.01))
