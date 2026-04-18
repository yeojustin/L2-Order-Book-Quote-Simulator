"""Virtual fills when quotes cross the touch."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable, List, Optional

from l2_sim.l2_book import L2Book
from l2_sim.quoting import Quote

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Fill:
    side: str  # "buy" / "sell"
    price: float
    size: float
    ts: float


class VirtualExecutionListener:
    """Buy if bid ≥ best ask; sell if ask ≤ best bid (crossing-only, no trade tape)."""

    def __init__(self, on_fill: Optional[Callable[[Fill], None]] = None) -> None:
        self._on_fill = on_fill
        self.fills: List[Fill] = []

    def process(self, book: L2Book, quote: Optional[Quote]) -> List[Fill]:
        if quote is None:
            return []
        new: List[Fill] = []
        bb = book.best_bid()
        ba = book.best_ask()
        if not bb or not ba:
            return new
        best_bid_px, _ = bb
        best_ask_px, _ = ba

        if quote.bid_price >= best_ask_px:
            f = Fill(side="buy", price=float(best_ask_px), size=float(quote.size_bid), ts=time.time())
            new.append(f)
        if quote.ask_price <= best_bid_px:
            f = Fill(side="sell", price=float(best_bid_px), size=float(quote.size_ask), ts=time.time())
            new.append(f)

        for fill in new:
            self.fills.append(fill)
            logger.info("virtual fill: %s", fill)
            if self._on_fill is not None:
                self._on_fill(fill)
        return new
