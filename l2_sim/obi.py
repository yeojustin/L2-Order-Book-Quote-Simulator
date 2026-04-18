"""OBI from top-K displayed size."""

from __future__ import annotations

from typing import Optional

from l2_sim.l2_book import L2Book


def order_book_imbalance(book: L2Book, depth: int = 10) -> Optional[float]:
    """(bid_vol - ask_vol) / (bid_vol + ask_vol) on top `depth` levels; None if total size is 0."""
    bid_vol = sum(q for _, q in book.top_bid_levels(depth))
    ask_vol = sum(q for _, q in book.top_ask_levels(depth))
    total = bid_vol + ask_vol
    if total <= 0:
        return None
    return (bid_vol - ask_vol) / total
# housekeeping: no functional change
