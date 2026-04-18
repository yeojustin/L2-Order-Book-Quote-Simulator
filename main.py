"""CLI: live book or book + sim."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from typing import Optional

from order_book import DEFAULT_SYMBOL, run_live_book

from l2_sim.logging_util import setup_logging
from l2_sim.simulation import make_book_tick_handler


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Binance spot L2: live or quote sim.")
    p.add_argument(
        "command",
        nargs="?",
        default="live",
        choices=("live", "quote", "tui"),
        help="live = depth only; quote = depth + sim; tui = live depth table (Rich)",
    )
    p.add_argument("--symbol", default=DEFAULT_SYMBOL, help="e.g. SOLUSDT")
    p.add_argument(
        "--depth",
        type=int,
        default=15,
        metavar="N",
        help="tui: number of bid/ask rows to show (default 15)",
    )
    p.add_argument(
        "--quote-mode",
        choices=("cross", "sym"),
        default="cross",
        help="cross = quotes can cross touch (fills); sym = mid +/- half_spread",
    )
    p.add_argument(
        "--cross-k",
        type=float,
        default=0.5001,
        help="cross mode: bid=mid+k*spread ask=mid-k*spread; k>0.5 crosses",
    )
    p.add_argument(
        "--half-spread",
        type=float,
        default=0.05,
        help="sym mode only: half distance from mid",
    )
    p.add_argument("--quote-size", type=float, default=0.1, help="fake order size (base)")
    p.add_argument("--obi-depth", type=int, default=10, help="levels per side for OBI")
    p.add_argument(
        "--inventory-gamma",
        type=float,
        default=0.02,
        help="skew quotes by gamma * position",
    )
    p.add_argument("--log-file", default=None, help="append logs to this path (optional)")
    p.add_argument("--debug", action="store_true", help="DEBUG log level")
    p.add_argument(
        "--bid-price",
        type=float,
        default=None,
        help="fixed fake bid only (optional; overrides bid from quote-mode)",
    )
    p.add_argument(
        "--ask-price",
        type=float,
        default=None,
        help="fixed fake ask only (optional; overrides ask from quote-mode)",
    )
    return p


def _maybe_setup_logging(*, quote: bool, log_file: Optional[str], debug: bool) -> None:
    if quote or log_file or debug:
        setup_logging(logging.DEBUG if debug else logging.INFO, log_file=log_file)


def main() -> None:
    args = _parser().parse_args()
    quote = args.command == "quote"
    tui = args.command == "tui"
    if not quote and not tui and (args.bid_price is not None or args.ask_price is not None):
        raise SystemExit("error: --bid-price / --ask-price only apply to `quote`")
    _maybe_setup_logging(quote=quote, log_file=args.log_file, debug=args.debug)

    if tui:
        try:
            from l2_sim.tui_depth import run_depth_tui
        except ImportError as exc:
            raise SystemExit(
                "error: `tui` needs the `rich` package. Run: pip install -e ."
            ) from exc
        try:
            run_depth_tui(args.symbol, args.depth)
        except KeyboardInterrupt:
            print("\n[!] Stopped by user.", file=sys.stderr)
            raise SystemExit(0) from None
    elif quote:
        tick = make_book_tick_handler(
            obi_depth=args.obi_depth,
            half_spread=args.half_spread,
            quote_size=args.quote_size,
            inventory_gamma=args.inventory_gamma,
            quote_mode=args.quote_mode,
            cross_k=args.cross_k,
            manual_bid=args.bid_price,
            manual_ask=args.ask_price,
        )
        asyncio.run(run_live_book(args.symbol, on_book_event=tick))
    else:
        try:
            asyncio.run(run_live_book(args.symbol))
        except KeyboardInterrupt:
            print("\n[!] Stopped by user.", file=sys.stderr)
            raise SystemExit(0) from None


if __name__ == "__main__":
    main()
