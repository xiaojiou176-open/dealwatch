from __future__ import annotations

from dataclasses import dataclass


#########################################################
# Retry Budget
#########################################################
@dataclass(slots=True)
class RetryBudget:
    total: int
    remaining: int

    def __init__(self, total: int) -> None:
        safe_total = max(int(total), 0)
        self.total = safe_total
        self.remaining = safe_total

    def consume(self, amount: int = 1) -> bool:
        if self.remaining <= 0:
            return False
        step = max(int(amount), 1)
        if self.remaining - step < 0:
            return False
        self.remaining -= step
        return True

    def used(self) -> int:
        return max(self.total - self.remaining, 0)
