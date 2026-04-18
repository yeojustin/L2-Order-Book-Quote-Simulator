"""Hook: OBI, quotes, crossing fills, inventory on each book update."""

from __future__ import annotations

import logging
from typing import Any, Callable

from l2_sim.execution import VirtualExecutionListener
from l2_sim.inventory import InventoryState
from l2_sim.obi import order_book_imbalance
from l2_sim.quoting import VirtualQuoter

logger = logging.getLogger(__name__)


def make_book_tick_handler(
    *,
    obi_depth: int = 10,
    half_spread: float = 0.05,
    quote_size: float = 0.1,
    inventory_gamma: float = 0.02,
    quote_mode: str = "cross",
    cross_k: float = 0.5001,
    manual_bid: float | None = None,
    manual_ask: float | None = None,
) -> Callable[[Any], None]:
    """Returns a fn(book) for run_live_book(..., on_book_event=...)."""
    inv = InventoryState()
    quoter = VirtualQuoter(
        half_spread=half_spread,
        base_size=quote_size,
        inventory_skew_gamma=inventory_gamma,
        quote_mode=quote_mode,
        cross_k=cross_k,
        manual_bid=manual_bid,
        manual_ask=manual_ask,
    )
    engine = VirtualExecutionListener()

    def on_book(book: Any) -> None:
        levels = book.levels
        mid = levels.mid()
        inv.on_mid_tick(mid)
        obi = order_book_imbalance(levels, depth=obi_depth)
        quote = quoter.compute(levels, inv.position_base)
        fills = engine.process(levels, quote)
        for fill in fills:
            inv.on_fill(fill.side, fill.size, mid)
        if obi is not None and mid is not None:
            bb = levels.best_bid()
            ba = levels.best_ask()
            qbp = qap = None
            if quote is not None:
                qbp, qap = quote.bid_price, quote.ask_price
            logger.info(
                "mid=%.4f obi=%+.3f inv=%.4f adverse=%d total_fills=%d tick_fills=%d "
                "bb=%s ba=%s q_bid=%s q_ask=%s",
                mid,
                obi,
                inv.position_base,
                inv.adverse_events,
                len(engine.fills),
                len(fills),
                f"{bb[0]:.4f}" if bb else None,
                f"{ba[0]:.4f}" if ba else None,
                f"{qbp:.4f}" if qbp is not None else None,
                f"{qap:.4f}" if qap is not None else None,
            )

    return on_book
