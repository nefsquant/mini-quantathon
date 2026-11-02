# NEFS Quant Division — QR Trading Challenge

Welcome to the NEFS Quantitative Research 2-hour trading challenge. Your objective is to discover statistical relationships and microstructure signals across **50 assets** (`NEFS`, `QUNT`, etc.) over **5 historical days** (`10,000` timestamps per day) and implement an algorithmic trading strategy in Python.

At the end of the 2 hours, your submitted `Trader` class will be evaluated on **unseen future days** drawn from the same market environment.

---

## Repository Structure

- `research/datamodel.py` — Core data structures (`TradingState`, `Order`, `OrderDepth`, `Trade`). **Do not modify.**
- `research/template.py` — Starter strategy file containing the `Trader` class.
- `research/backtester.py` — Local L2 orderbook + trade-print backtester and tear-sheet generator.
- `research/data/prices/prices_day_1..5.csv` — 3-level L2 orderbook snapshots (`500,000` rows/day).
- `research/data/trades/trades_day_1..5.csv` — Historical market trades executed each day.

---

## Quick Start

### 1. Run the Backtester
Run `backtester.py` on one or more days using `uv run`:

```bash
# Run on Day 1:
uv run research/backtester.py research/template.py --days 1

# Train on Days 1–3:
uv run research/backtester.py research/template.py --days 1 2 3

# Validate out-of-sample on Days 4–5:
uv run research/backtester.py research/template.py --days 4 5

# Compare multiple strategy files side-by-side:
uv run research/backtester.py research/strat_v1.py research/strat_v2.py --days 4 5
```

### 2. Writing Your Strategy (`template.py`)
Your strategy file must define a `Trader` class with a `run(self, state: TradingState) -> Dict[Symbol, List[Order]]` method. The `Trader` instance persists in memory across timestamps, so you can store rolling state on `self`.

```python
from typing import Dict, List
from datamodel import Order, Symbol, TradingState


class Trader:
    def __init__(self):
        self.spread_history: List[float] = []

    def run(self, state: TradingState) -> Dict[Symbol, List[Order]]:
        orders: Dict[Symbol, List[Order]] = {}

        depth = state.order_depths.get("NEFS")
        if depth and depth.buy_orders and depth.sell_orders:
            best_bid = max(depth.buy_orders.keys())
            best_ask = min(depth.sell_orders.keys())
            pos = state.position.get("NEFS", 0)

            # Positive quantity = BUY, Negative quantity = SELL
            if pos < 20:
                orders["NEFS"] = [Order("NEFS", best_bid + 1, 5)]

        return orders
```

---

## Market & Execution Rules

1. **Position Limits**: Every ticker has a hard position limit of **`±20` units**. If all orders submitted for a symbol on a single timestamp could breach `[-20, +20]` when added to your current position, that symbol's orders for that timestamp are rejected.
2. **Order Lifecycle**: Unfilled orders do not carry over to the next timestamp; emit your desired orders on each call to `run(state)`.
3. **Order Matching (Zero Fees)**:
   - **Taker Fills**: Buy orders with `price >= best_ask` (or sell orders with `price <= best_bid`) fill immediately against available volume in `state.order_depths[symbol]`.
   - **Maker Fills**: Remaining resting limit orders fill against `market_trades` at that timestamp whose trade price crosses or touches your order price.
4. **Evaluation Metrics**:
   - **Total PnL**: Final mark-to-market profit and loss across all 50 tickers.
   - **Sharpe & Sortino Ratios**: Annualized over the simulation ticks.
   - **Max Drawdown**: Largest peak-to-trough equity drop.
   - **Fill Rate & Trading Rate**: Percentage of requested volume filled and fills per tick.
   - **Composite Score**: Risk-adjusted score used for the final unseen-data leaderboard:
     $$\text{Score} = \text{PnL} \times (1 + 0.15 \times \text{clip}(\text{Sharpe}, -5, 10)) - 0.25 \times \text{MaxDD}$$

---

## Dataset Schema

### `data/prices/prices_day_X.csv` (Semicolon-delimited `;`)
| Column | Description |
| :--- | :--- |
| `day` | Day number (`1` to `5`) |
| `timestamp` | Tick timestamp (`0` to `999,900` in steps of `100`) |
| `product` | 4-letter ticker symbol (`50` unique symbols) |
| `bid_price_1..3` | Top 3 bid price levels (empty if level has no liquidity) |
| `bid_volume_1..3` | Volume available at each bid level (positive integer) |
| `ask_price_1..3` | Top 3 ask price levels (empty if level has no liquidity) |
| `ask_volume_1..3` | Volume available at each ask level (positive integer in CSV; negative in `OrderDepth.sell_orders`) |
| `mid_price` | Reference mid-price for mark-to-market valuation |

### `data/trades/trades_day_X.csv` (Semicolon-delimited `;`)
| Column | Description |
| :--- | :--- |
| `timestamp` | Tick timestamp (`0` to `999,900`) |
| `symbol` | 4-letter ticker symbol |
| `price` | Execution price |
| `quantity` | Trade size |
