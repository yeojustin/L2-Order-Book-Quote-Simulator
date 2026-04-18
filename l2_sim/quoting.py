"""Fake quotes: sym (mid +/- half) or cross (offset from spread)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from l2_sim.l2_book import L2Book


@dataclass(frozen=True)
class Quote:
    bid_price: float
    ask_price: float
    size_bid: float
    size_ask: float


class VirtualQuoter:
    def __init__(
        self,
        half_spread: float = 0.05,
        base_size: float = 0.1,
        inventory_skew_gamma: float = 0.0,
        *,
        quote_mode: str = "cross",
        cross_k: float = 0.5001,
    ) -> None:
        self.half_spread = half_spread
        self.base_size = base_size
        self.inventory_skew_gamma = inventory_skew_gamma
        if quote_mode not in ("sym", "cross"):
            raise ValueError('quote_mode must be "sym" or "cross"')
        self.quote_mode = quote_mode
        self.cross_k = cross_k

    def compute(self, book: L2Book, inventory_base: float) -> Optional[Quote]:
        mid = book.mid()
        if mid is None:
            return None
        shift = self.inventory_skew_gamma * inventory_base
        if self.quote_mode == "sym":
            bid_px = mid - self.half_spread - shift
            ask_px = mid + self.half_spread - shift
        else:
            spread = book.spread()
            if spread is None or spread <= 0.0:
                return None
            bid_px = mid + self.cross_k * spread - shift
            ask_px = mid - self.cross_k * spread - shift
        return Quote(
            bid_price=bid_px,
            ask_price=ask_px,
            size_bid=self.base_size,
            size_ask=self.base_size,
        )
