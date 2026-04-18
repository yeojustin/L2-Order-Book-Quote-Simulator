"""Live Rich TUI: bid/ask depth columns for BinanceOrderBook."""

from __future__ import annotations

import asyncio

from rich import box
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from order_book import BinanceOrderBook, run_live_book


def _fmt_num(x: float, decimals: int = 6) -> str:
    s = f"{x:.{decimals}f}"
    s = s.rstrip("0").rstrip(".")
    return s or "0"


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
    return Panel(
        table,
        title=title,
        title_align="left",
        subtitle=sub + "  —  Ctrl+C to quit" if sub else "Ctrl+C to quit",
        subtitle_align="left",
        border_style="cyan",
    )


def run_depth_tui(symbol: str, rows: int = 15) -> None:
    """Block until disconnect or Ctrl+C; refreshes a Rich Live panel on each depth apply."""
    console = Console()
    rows = max(1, min(rows, 500))
    boot = Panel(
        "Connecting to Binance depth…",
        title=symbol.upper(),
        border_style="cyan",
    )
    with Live(boot, console=console, refresh_per_second=24, transient=False) as live:

        def on_book(book: BinanceOrderBook) -> None:
            live.update(depth_panel(book, rows))

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
            console.print("\n[dim]Stopped.[/dim]")
