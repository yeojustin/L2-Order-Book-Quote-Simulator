"""CLI: live book or book + sim."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from typing import Any, Optional

from order_book import DEFAULT_SYMBOL, run_live_book

from l2_sim.logging_util import setup_logging
from l2_sim.simulation import make_book_tick_handler


def _sim_tick_kwargs(namespace: argparse.Namespace) -> dict[str, Any]:
    return {
        "obi_depth": namespace.obi_depth,
        "half_spread": namespace.half_spread,
        "quote_size": namespace.quote_size,
        "inventory_gamma": namespace.inventory_gamma,
        "quote_mode": namespace.quote_mode,
        "cross_k": namespace.cross_k,
        "manual_bid": namespace.bid_price,
        "manual_ask": namespace.ask_price,
    }


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Binance spot L2: live or quote sim.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "command",
        nargs="?",
        default="live",
        choices=("live", "quote", "tui"),
        help="live = depth only; quote = depth + sim logs; tui = depth + sim in Rich",
    )
    p.add_argument("--symbol", default=DEFAULT_SYMBOL, help="e.g. SOLUSDT")
    p.add_argument(
        "--depth",
        type=int,
        default=15,
        metavar="N",
        help="tui: number of bid/ask rows to show",
    )
    opt_feed = p.add_argument_group("optional feed tuning")
    opt_feed.add_argument(
        "--ws-depth-speed",
        choices=("100ms", "1000ms"),
        default="100ms",
        help="Binance diff-depth stream cadence @depth@… (omit = default)",
    )
    opt_tui = p.add_argument_group("optional tui display")
    opt_tui.add_argument(
        "--tui-refresh-hz",
        type=float,
        default=30.0,
        metavar="HZ",
        help="Rich Live poll rate 1–60 Hz (tui only; omit = default)",
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
    p.add_argument("--quote-size", type=float, default=0.1, help="sim order size per side (base)")
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
        help="fixed sim bid only (optional; overrides bid from quote-mode)",
    )
    p.add_argument(
        "--ask-price",
        type=float,
        default=None,
        help="fixed sim ask only (optional; overrides ask from quote-mode)",
    )
    return p


def _maybe_setup_logging(
    *, quote: bool, tui: bool, log_file: Optional[str], debug: bool
) -> None:
    if quote or tui or log_file or debug:
        setup_logging(logging.DEBUG if debug else logging.INFO, log_file=log_file)


def main() -> None:
    args = _parser().parse_args()
    quote = args.command == "quote"
    tui = args.command == "tui"
    if args.command == "live" and (args.bid_price is not None or args.ask_price is not None):
        raise SystemExit("error: --bid-price / --ask-price only apply to `quote` or `tui`")
    _maybe_setup_logging(
        quote=quote, tui=tui, log_file=args.log_file, debug=args.debug
    )

    if tui:
        try:
            from l2_sim.tui_depth import run_depth_tui
        except ImportError as exc:
            raise SystemExit(
                "error: `tui` needs the `rich` package. Run: pip install -e ."
            ) from exc
        try:
            run_depth_tui(
                args.symbol,
                args.depth,
                sim_kwargs=_sim_tick_kwargs(args),
                depth_speed=args.ws_depth_speed,
                refresh_hz=args.tui_refresh_hz,
            )
        except KeyboardInterrupt:
            print("\n[!] Stopped by user.", file=sys.stderr)
            raise SystemExit(0) from None
    elif quote:
        tick = make_book_tick_handler(**_sim_tick_kwargs(args))
        asyncio.run(
            run_live_book(
                args.symbol,
                on_book_event=tick,
                depth_speed=args.ws_depth_speed,
            )
        )
    else:
        try:
            asyncio.run(
                run_live_book(args.symbol, depth_speed=args.ws_depth_speed)
            )
        except KeyboardInterrupt:
            print("\n[!] Stopped by user.", file=sys.stderr)
            raise SystemExit(0) from None


if __name__ == "__main__":
    main()
