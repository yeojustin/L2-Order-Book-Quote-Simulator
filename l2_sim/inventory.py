"""Simulated position and a simple post-fill mid move counter."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class InventoryState:
    position_base: float = 0.0
    adverse_events: int = 0
    _last_fill_mid: Optional[float] = None
    _last_fill_side: Optional[str] = None  # "buy" / "sell"
    _mid_history: List[float] = field(default_factory=list)

    def on_mid_tick(self, mid: Optional[float]) -> None:
        if mid is None:
            return
        self._mid_history.append(mid)
        if len(self._mid_history) > 5000:
            self._mid_history = self._mid_history[-2000:]

        if self._last_fill_mid is None or self._last_fill_side is None:
            return
        if self._last_fill_side == "buy" and mid < self._last_fill_mid:
            self.adverse_events += 1
            self._last_fill_mid = None
            self._last_fill_side = None
        elif self._last_fill_side == "sell" and mid > self._last_fill_mid:
            self.adverse_events += 1
            self._last_fill_mid = None
            self._last_fill_side = None

    def on_fill(self, side: str, size_base: float, mid_at_fill: Optional[float]) -> None:
        if side == "buy":
            self.position_base += size_base
        elif side == "sell":
            self.position_base -= size_base
        self._last_fill_side = side
        self._last_fill_mid = mid_at_fill
# housekeeping: no functional change
