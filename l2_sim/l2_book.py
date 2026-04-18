"""L2 book: SortedDict for O(log n) updates, O(1) best bid/ask peek."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Tuple

from sortedcontainers import SortedDict

PriceQty = Tuple[float, float]


class L2Book:
    __slots__ = ("_bids", "_asks")

    def __init__(self) -> None:
        self._bids: SortedDict[float, float] = SortedDict()
        self._asks: SortedDict[float, float] = SortedDict()

    def clear(self) -> None:
        self._bids.clear()
        self._asks.clear()

    def load_snapshot(self, bids: Iterable[Tuple[float, float]], asks: Iterable[Tuple[float, float]]) -> None:
        self.clear()
        for price, qty in bids:
            if qty > 0:
                self._bids[price] = qty
        for price, qty in asks:
            if qty > 0:
                self._asks[price] = qty

    def apply_binance_rows(self, bid_rows: List[List[str]], ask_rows: List[List[str]]) -> None:
        """Binance `b`/`a` rows; qty 0 removes the level."""
        for row in bid_rows:
            if len(row) < 2:
                continue
            price, qty = float(row[0]), float(row[1])
            if qty == 0.0:
                self._bids.pop(price, None)
            else:
                self._bids[price] = qty
        for row in ask_rows:
            if len(row) < 2:
                continue
            price, qty = float(row[0]), float(row[1])
            if qty == 0.0:
                self._asks.pop(price, None)
            else:
                self._asks[price] = qty

    def best_bid(self) -> Optional[PriceQty]:
        if not self._bids:
            return None
        price, qty = self._bids.peekitem(-1)
        return price, qty

    def best_ask(self) -> Optional[PriceQty]:
        if not self._asks:
            return None
        price, qty = self._asks.peekitem(0)
        return price, qty

    def mid(self) -> Optional[float]:
        bb = self.best_bid()
        ba = self.best_ask()
        if not bb or not ba:
            return None
        return (bb[0] + ba[0]) / 2.0

    def spread(self) -> Optional[float]:
        bb = self.best_bid()
        ba = self.best_ask()
        if not bb or not ba:
            return None
        return ba[0] - bb[0]

    def top_bid_levels(self, k: int) -> List[PriceQty]:
        if k <= 0:
            return []
        out: List[PriceQty] = []
        for price, qty in reversed(self._bids.items()):
            out.append((price, qty))
            if len(out) >= k:
                break
        return out

    def top_ask_levels(self, k: int) -> List[PriceQty]:
        if k <= 0:
            return []
        out: List[PriceQty] = []
        for price, qty in self._asks.items():
            out.append((price, qty))
            if len(out) >= k:
                break
        return out

    def depth_dicts(self) -> Tuple[Dict[float, float], Dict[float, float]]:
        return dict(self._bids), dict(self._asks)
# housekeeping: no functional change
