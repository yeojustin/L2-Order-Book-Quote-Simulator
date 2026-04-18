"""Binance spot L2: REST snapshot + websocket diffs; resync with backoff on errors."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import requests
import websockets

from l2_sim.l2_book import L2Book

logger = logging.getLogger(__name__)

REST_BASE = "https://api.binance.com"
WS_BASE = "wss://stream.binance.com:9443/ws"
DEFAULT_SYMBOL = "SOLUSDT"
HTTP_TIMEOUT = 10.0

WS_OPEN_TIMEOUT = 15.0
WS_PING_INTERVAL = 20.0
WS_PING_TIMEOUT = 20.0

RESYNC_DELAY_START = 1.0
RESYNC_DELAY_MAX = 60.0


def depth_rest_url(symbol: str, limit: int = 1000) -> str:
    return f"{REST_BASE}/api/v3/depth?symbol={symbol.upper()}&limit={limit}"


def depth_stream_url(symbol: str, speed: str = "100ms") -> str:
    return f"{WS_BASE}/{symbol.lower()}@depth@{speed}"


def ping_depth(symbol: str = DEFAULT_SYMBOL, limit: int = 5) -> None:
    url = depth_rest_url(symbol, limit=limit)
    print(f"Pinging Binance depth for {symbol.upper()}...")
    res = requests.get(url, timeout=HTTP_TIMEOUT)
    res.raise_for_status()
    print(json.dumps(res.json(), indent=2)[:2000])


def _overlap_first_event(U: int, u: int, snapshot_id: int) -> bool:
    return U <= snapshot_id + 1 and u >= snapshot_id + 1


def _continues_stream(U: int, last_update_id: int) -> bool:
    return U == last_update_id + 1


def _drain_queue_nowait(queue: "asyncio.Queue[Dict[str, Any]]") -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    while True:
        try:
            out.append(queue.get_nowait())
        except asyncio.QueueEmpty:
            return out


def _is_depth_diff_message(msg: Any) -> bool:
    """True if message looks like a Binance partial depth diff."""
    if not isinstance(msg, dict):
        return False
    if "b" not in msg or "a" not in msg or "U" not in msg or "u" not in msg:
        return False
    if not isinstance(msg["b"], list) or not isinstance(msg["a"], list):
        return False
    return True


class BinanceOrderBook:
    """Local L2 + last Binance u."""

    def __init__(self, symbol: str) -> None:
        self.symbol = symbol.upper()
        self.levels = L2Book()
        self.last_update_id: int = 0

    def fetch_snapshot(self) -> None:
        response = requests.get(depth_rest_url(self.symbol), timeout=HTTP_TIMEOUT)
        response.raise_for_status()
        body = response.json()
        if not isinstance(body, dict):
            raise ValueError("Snapshot JSON was not an object.")
        if "lastUpdateId" not in body or "bids" not in body or "asks" not in body:
            raise ValueError(f"Snapshot missing keys: {list(body.keys())[:20]}")
        if not isinstance(body["bids"], list) or not isinstance(body["asks"], list):
            raise ValueError("Snapshot bids/asks must be lists.")

        self.last_update_id = int(body["lastUpdateId"])
        bid_pairs = ((float(p), float(q)) for p, q in body["bids"])
        ask_pairs = ((float(p), float(q)) for p, q in body["asks"])
        self.levels.load_snapshot(bid_pairs, ask_pairs)
        print(f"[*] Snapshot fetched. lastUpdateId={self.last_update_id}")

    def apply_depth_event(self, event: Dict[str, Any]) -> None:
        if not _is_depth_diff_message(event):
            raise ValueError("Malformed depth diff (expected b, a, U, u lists/fields).")
        self.levels.apply_binance_rows(event["b"], event["a"])
        self.last_update_id = int(event["u"])

    def get_best_quote(self) -> Optional[Tuple[float, float]]:
        bb = self.levels.best_bid()
        ba = self.levels.best_ask()
        if not bb or not ba:
            return None
        return bb[0], ba[0]

    def display_status(self) -> None:
        q = self.get_best_quote()
        if not q:
            return
        bid, ask = q
        print(
            f"ID: {self.last_update_id} | Bid: {bid:.2f} | Ask: {ask:.2f} | "
            f"Spread: {ask - bid:.2f}"
        )


def _replay_buffered_events(book: BinanceOrderBook, snapshot_id: int, pending: List[Dict[str, Any]]) -> None:
    need_overlap = True
    for event in pending:
        if not _is_depth_diff_message(event):
            continue
        u = int(event["u"])
        if u <= snapshot_id:
            continue
        U = int(event["U"])
        if need_overlap:
            if not _overlap_first_event(U, u, snapshot_id):
                raise RuntimeError(
                    f"Buffered align failed: U={U} u={u} snapshot_id={snapshot_id}. Will resync."
                )
            need_overlap = False
        elif not _continues_stream(U, book.last_update_id):
            raise RuntimeError(
                f"Buffered gap: expected U={book.last_update_id + 1}, got U={U}. Will resync."
            )
        book.apply_depth_event(event)


def _live_event_ok(book: BinanceOrderBook, event: Dict[str, Any], snapshot_id: int) -> bool:
    if not _is_depth_diff_message(event):
        return False
    U, u = int(event["U"]), int(event["u"])
    if book.last_update_id == snapshot_id:
        return _overlap_first_event(U, u, snapshot_id)
    return _continues_stream(U, book.last_update_id)


async def _pump_depth_json(ws: Any, queue: "asyncio.Queue[Dict[str, Any]]") -> None:
    """Parse WS text frames; skip bad JSON; enqueue valid depth dicts."""
    async for raw in ws:
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if _is_depth_diff_message(msg):
            await queue.put(msg)


async def _run_single_connection(
    book: BinanceOrderBook,
    symbol: str,
    on_book_event: Optional[Callable[..., None]] = None,
) -> None:
    """One WS session: snapshot, merge buffer, then live apply loop."""
    queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()
    uri = depth_stream_url(symbol)

    async with websockets.connect(
        uri,
        open_timeout=WS_OPEN_TIMEOUT,
        ping_interval=WS_PING_INTERVAL,
        ping_timeout=WS_PING_TIMEOUT,
    ) as ws:
        reader = asyncio.create_task(_pump_depth_json(ws, queue))
        try:
            await asyncio.to_thread(book.fetch_snapshot)
            snapshot_id = book.last_update_id

            pending = _drain_queue_nowait(queue)
            await asyncio.sleep(0.05)
            pending.extend(_drain_queue_nowait(queue))

            _replay_buffered_events(book, snapshot_id, pending)
            if on_book_event is not None:
                try:
                    on_book_event(book)
                except Exception:
                    logger.exception("on_book_event after buffered replay failed")

            last_print = time.monotonic()
            while True:
                if reader.done():
                    exc = reader.exception()
                    if exc is not None:
                        raise exc
                    raise ConnectionError("Websocket reader stopped without an exception.")

                try:
                    event = await asyncio.wait_for(queue.get(), timeout=WS_PING_TIMEOUT + 5.0)
                except asyncio.TimeoutError as exc:
                    raise TimeoutError("No depth messages for too long; connection may be dead.") from exc

                if not _live_event_ok(book, event, snapshot_id):
                    U, u = int(event["U"]), int(event["u"])
                    raise RuntimeError(
                        f"Live sequence error: last={book.last_update_id} snap={snapshot_id} U={U} u={u}"
                    )
                book.apply_depth_event(event)
                if on_book_event is not None:
                    try:
                        on_book_event(book)
                    except Exception:
                        logger.exception("on_book_event callback failed")
                now = time.monotonic()
                if now - last_print >= 1.0:
                    book.display_status()
                    last_print = now
        finally:
            reader.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await reader


async def run_live_book(
    symbol: str = DEFAULT_SYMBOL,
    *,
    on_book_event: Optional[Callable[..., None]] = None,
) -> None:
    """Reconnect forever; optional callback after each depth apply."""
    delay = RESYNC_DELAY_START
    while True:
        book = BinanceOrderBook(symbol)
        try:
            await _run_single_connection(book, symbol, on_book_event=on_book_event)
            delay = RESYNC_DELAY_START
        except asyncio.CancelledError:
            raise
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            print(f"[!] Session ended: {exc!r}. Resync in {delay:.1f}s…")
            await asyncio.sleep(delay)
            delay = min(delay * 2.0, RESYNC_DELAY_MAX)


def test_fetch_snapshot(symbol: str = DEFAULT_SYMBOL) -> None:
    book = BinanceOrderBook(symbol)
    try:
        book.fetch_snapshot()
    except (requests.RequestException, ValueError) as exc:
        print(f"Snapshot failed: {exc}")
        return
    q = book.get_best_quote()
    if not q:
        print("Book missing one side after snapshot.")
        return
    bid, ask = q
    print(f"\nTop of book: bid={bid:.3f} ask={ask:.3f} spread={ask - bid:.3f}")


if __name__ == "__main__":
    def run_asyncio_main() -> None:
        try:
            asyncio.run(run_live_book(DEFAULT_SYMBOL))
        except KeyboardInterrupt:
            print("\n[!] Stopped by user.")
            sys.exit(0)

    # ping_depth(DEFAULT_SYMBOL)
    # test_fetch_snapshot(DEFAULT_SYMBOL)
    run_asyncio_main()
