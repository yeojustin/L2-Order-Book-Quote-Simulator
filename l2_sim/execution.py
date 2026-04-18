"""Virtual fills when quotes cross the touch."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import List, Optional

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

    def __init__(self) -> None:
        self.total_fills: int = 0

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

        bp = quote.bid_price
        ap = quote.ask_price
        if bp is not None and quote.size_bid > 0 and bp >= best_ask_px:
            f = Fill(side="buy", price=float(best_ask_px), size=float(quote.size_bid), ts=time.time())
            new.append(f)
        if ap is not None and quote.size_ask > 0 and ap <= best_bid_px:
            f = Fill(side="sell", price=float(best_bid_px), size=float(quote.size_ask), ts=time.time())
            new.append(f)

        for fill in new:
            self.total_fills += 1
            logger.info("virtual fill: %s", fill)
        return new
