"""Live Rich TUI: bid/ask depth + same quote sim as `main.py quote`."""

from __future__ import annotations

import asyncio
import logging
import sys
import threading
from typing import Any, Dict, Optional

from rich import box
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from l2_sim.simulation import SimTickSnapshot, make_book_tick_handler
from order_book import BinanceOrderBook, run_live_book


def _fmt_num(x: float, decimals: int = 6) -> str:
    s = f"{x:.{decimals}f}"
    s = s.rstrip("0").rstrip(".")
    return s or "0"


def _fmt_opt_px(x: Optional[float], decimals: int = 6) -> str:
    if x is None:
        return "—"
    return _fmt_num(x, decimals)


def depth_panel(book: BinanceOrderBook, rows: int) -> Panel:
    rows = max(1, rows)
    lv = book.levels
    bids = lv.top_bid_levels(rows)
    asks = lv.top_ask_levels(rows)

    table = Table(box=box.ROUNDED, show_edge=False, padding=(0, 1), expand=True)
    table.add_column(Text("Bid size", style="green"), justify="right", no_wrap=True)
    table.add_column(Text("Bid", style="bold green"), justify="right", no_wrap=True)
    table.add_column(Text("Ask", style="bold red"), justify="left", no_wrap=True)
    table.add_column(Text("Ask size", style="red"), justify="left", no_wrap=True)

    for i in range(rows):
        if i < len(bids):
            bp, bq = bids[i]
            bs, bpx = _fmt_num(bq, 5), _fmt_num(bp, 8)
        else:
            bs, bpx = "—", "—"
        if i < len(asks):
            ap, aq = asks[i]
            apx, aqs = _fmt_num(ap, 8), _fmt_num(aq, 5)
        else:
            apx, aqs = "—", "—"
        table.add_row(bs, bpx, apx, aqs)

    bb = lv.best_bid()
    ba = lv.best_ask()
    subtitle_parts: list[str] = []
    if bb and ba:
        mid = (bb[0] + ba[0]) / 2.0
        sp = ba[0] - bb[0]
        subtitle_parts.append(f"mid {_fmt_num(mid, 8)}")
        subtitle_parts.append(f"spread {_fmt_num(sp, 8)}")
    sub = "  ·  ".join(subtitle_parts) if subtitle_parts else ""
    title = f"{book.symbol}  lastUpdateId={book.last_update_id}"
    footer = sub + "  —  Ctrl+C to quit" if sub else "Ctrl+C to quit"
    return Panel(
        table,
        title=title,
        title_align="left",
        subtitle=footer,
        subtitle_align="left",
        border_style="cyan",
    )


def _sim_panel(snap: Optional[SimTickSnapshot]) -> Panel:
    t = Table(box=box.ROUNDED, show_edge=False, padding=(0, 1), expand=True)
    t.add_column("Field", style="dim", no_wrap=True)
    t.add_column("Value", no_wrap=True)
    if snap is None:
        t.add_row("status", "waiting for book…")
        return Panel(t, title="Quote sim", border_style="magenta")

    t.add_row("mid", _fmt_opt_px(snap.mid, 8))
    t.add_row("obi", f"{snap.obi:+.3f}" if snap.obi is not None else "—")
    t.add_row("inv", _fmt_num(snap.position_base, 6))
    t.add_row("adverse", str(snap.adverse_events))
    t.add_row("total_fills", str(snap.total_fills))
    t.add_row("tick_fills", str(snap.tick_fills))
    t.add_row("bb", _fmt_opt_px(snap.best_bid_px, 4))
    t.add_row("ba", _fmt_opt_px(snap.best_ask_px, 4))
    t.add_row("q_bid", _fmt_opt_px(snap.q_bid, 4))
    t.add_row("q_ask", _fmt_opt_px(snap.q_ask, 4))
    return Panel(t, title="Quote sim", border_style="magenta")


def run_depth_tui(symbol: str, rows: int = 15, *, sim_kwargs: Optional[Dict[str, Any]] = None) -> None:
    """Depth ladder + virtual quote sim; ``sim_kwargs`` → ``make_book_tick_handler``."""
    logging.getLogger("l2_sim.execution").setLevel(logging.WARNING)
    logging.getLogger("l2_sim.simulation").setLevel(logging.WARNING)

    console = Console(force_terminal=True)
    rows = max(1, min(rows, 500))
    boot = Panel("Connecting…", title=symbol.upper(), border_style="cyan")
    sim_kwargs = dict(sim_kwargs or {})
    sim_kwargs.pop("on_tick", None)
    sim_kwargs.pop("log_ticks", None)

    last_snap: list[Optional[SimTickSnapshot]] = [None]

    def on_snap(s: SimTickSnapshot) -> None:
        last_snap[0] = s

    sim_on_book = make_book_tick_handler(
        **sim_kwargs,
        on_tick=on_snap,
        log_ticks=False,
    )

    disp_lock = threading.Lock()
    root: dict[str, Any] = {"g": boot}

    def get_renderable() -> Any:
        with disp_lock:
            return root["g"]

    with Live(
        boot,
        console=console,
        screen=True,
        transient=True,
        auto_refresh=True,
        refresh_per_second=30,
        vertical_overflow="visible",
        get_renderable=get_renderable,
        redirect_stdout=True,
        redirect_stderr=True,
    ) as live:

        def on_book(book: BinanceOrderBook) -> None:
            sim_on_book(book)
            g = Group(depth_panel(book, rows), _sim_panel(last_snap[0]))
            with disp_lock:
                root["g"] = g
            live.refresh()

        try:
            asyncio.run(
                run_live_book(
                    symbol,
                    on_book_event=on_book,
                    status_interval=None,
                    echo_snapshot=False,
                )
            )
        except KeyboardInterrupt:
            pass
        finally:
            if sys.stderr.isatty():
                print("\nStopped.", file=sys.stderr)
