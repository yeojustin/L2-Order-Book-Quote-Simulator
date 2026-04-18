# L2 depth sync + quote simulator

Binance **Spot** public data only: REST snapshot + **diff depth** websocket → local `L2Book`. Optional **simulated** quotes and **virtual** fills when those quotes cross the touch (nothing is sent to the exchange).

## Install

```bash
cd /path/to/L2-Order-Book-Quoting-Siumulator
pip install -e .
```

## Commands

Default command is **`live`** if you omit it.

| Command | What it does |
|---------|----------------|
| `python main.py live --symbol SOLUSDT` | Sync book, print touch / spread on an interval |
| `python main.py quote --symbol SOLUSDT` | Same feed + sim logs to stdout / `--log-file` |
| `python main.py tui --symbol SOLUSDT` | Same feed + sim in a Rich depth ladder + side panel |
| `python order_book.py` | Run `order_book.py` directly (symbol = `DEFAULT_SYMBOL` in that file) |

**Ctrl+C** stops any run. **`tui`** needs **`rich`** (included in `pip install -e .`).

### Sim pricing (`quote` / `tui`)

- **Formula:** `--quote-mode cross` or `sym`, plus `--cross-k`, `--half-spread`, `--inventory-gamma`, `--quote-size`, `--obi-depth`.
- **Manual:** `--bid-price` / `--ask-price` (each optional). If either is set, formula pricing for that side is not used.

### Flags

| Flag | Default | Scope | Meaning |
|------|---------|-------|---------|
| `--symbol` | `order_book.DEFAULT_SYMBOL` | all | Pair, e.g. `SOLUSDT` |
| `--depth` | `15` | `tui` | Bid/ask rows shown (clamped 1–500) |
| `--ws-depth-speed` | `100ms` | all | Diff-depth cadence: `100ms` or `1000ms` |
| `--tui-refresh-hz` | `30` | `tui` | Rich `Live` poll rate (1–60); ignored elsewhere |
| `--quote-mode` | `cross` | `quote`/`tui` | `cross` vs `sym` (ignored for manual prices) |
| `--cross-k` | `0.5001` | `quote`/`tui` | Cross-mode aggressiveness |
| `--half-spread` | `0.05` | `quote`/`tui` | Sym-mode half-width |
| `--quote-size` | `0.1` | `quote`/`tui` | Sim size per active side (base) |
| `--obi-depth` | `10` | `quote`/`tui` | Levels per side for OBI |
| `--inventory-gamma` | `0.02` | `quote`/`tui` | Inventory skew on formula quotes |
| `--bid-price` / `--ask-price` | unset | `quote`/`tui` | Fixed sim prices per side |
| `--log-file` | unset | all | Append logs |
| `--debug` | off | all | DEBUG logging |

```bash
python main.py --help
python main.py tui --symbol BTCUSDT --depth 20 --ws-depth-speed 1000ms --tui-refresh-hz 12
python main.py quote --symbol SOLUSDT --bid-price 150.12 --log-file run.log
```

## What is real vs simulated

| Real | Simulated |
|------|-----------|
| Binance REST depth snapshot, WS diff-depth updates, local book touch | `q_bid` / `q_ask`, inventory, OBI-driven formula quotes, **virtual** fills at touch when quote crosses |
| | **No** order placement, fees, queue position, or trade tape |

REST snapshot uses **`limit=1000`** (see `depth_rest_url`). Binance documents deeper books and higher limits; very deep resting liquidity may be incomplete until diffs update those prices.

## Layout

- `order_book.py` — connect, snapshot, apply diffs (stale events, final `u` before local id, are skipped)
- `main.py` — CLI
- `l2_sim/l2_book.py` — sorted price levels
- `l2_sim/simulation.py` — book → tick handler
- `l2_sim/quoting.py`, `execution.py`, `inventory.py`, `obi.py` — sim pieces
- `l2_sim/tui_depth.py` — Rich UI for `tui`

## Links

- [Manage a local order book](https://developers.binance.com/docs/binance-spot-api-docs/web-socket-streams#how-to-manage-a-local-order-book-correctly)
- [Diff depth stream](https://developers.binance.com/docs/binance-spot-api-docs/web-socket-streams#diff-depth-stream) (this project)
- [REST depth](https://developers.binance.com/docs/binance-spot-api-docs/rest-api/market-data-endpoints#order-book)
