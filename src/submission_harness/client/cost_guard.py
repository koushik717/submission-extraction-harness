"""Hard spend cap that aborts a run when exceeded."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock


class SpendCapExceeded(RuntimeError):
    def __init__(self, spent: float, cap: float):
        self.spent = spent
        self.cap = cap
        super().__init__(
            f"Spend cap exceeded: ${spent:.4f} >= ${cap:.4f}. Aborting run."
        )


@dataclass
class CostGuard:
    """Track cumulative USD spend and abort when the hard cap is hit."""

    cap_usd: float
    spent_usd: float = 0.0
    _lock: Lock = field(default_factory=Lock, repr=False)

    def charge(self, amount_usd: float) -> None:
        if amount_usd < 0:
            raise ValueError("charge amount must be non-negative")
        with self._lock:
            projected = self.spent_usd + amount_usd
            if projected > self.cap_usd + 1e-12:
                self.spent_usd = projected
                raise SpendCapExceeded(self.spent_usd, self.cap_usd)
            self.spent_usd = projected

    def ensure_under_cap(self) -> None:
        with self._lock:
            if self.spent_usd > self.cap_usd + 1e-12:
                raise SpendCapExceeded(self.spent_usd, self.cap_usd)

    def snapshot(self) -> dict[str, float]:
        with self._lock:
            return {"spent_usd": self.spent_usd, "cap_usd": self.cap_usd}
