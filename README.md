# NEFS Quant Warm-Up Competition

Welcome to the NEFS Quant Competition. This repository contains both parallel competition tracks:

| Track | Directory | Description | Languages / Tooling |
| :--- | :--- | :--- | :--- |
| **Quantitative Research (QR)** | [`research/`](research/) | Uncover statistical relationships across 50 assets and develop an algorithmic strategy evaluated on unseen market days. | Python 3 (`uv run`) |
| **Software Engineering (DEV)** | [`engineering/`](engineering/) | Build high-performance financial systems: [Market Data Pipeline](engineering/market-data/SPEC.md) and/or [Pre-Trade Risk Engine](engineering/pre-trade-risk/SPEC.md). | Python, Go, C, C++, Rust |

---

## Repository Structure

```text
.
├── README.md
├── pyproject.toml
├── uv.lock
├── research/                        # Quantitative Research Track
│   ├── datamodel.py                 # Core data structures (Do not modify)
│   ├── template.py                  # Starter strategy file (Trader class)
│   ├── backtester.py                # Local L2 orderbook backtester & tear sheet
│   └── data/
│       ├── prices/                  # 3-level L2 snapshots (Days 1–5)
│       └── trades/                  # Historical market trades (Days 1–5)
└── engineering/                     # Software Engineering Track
    ├── README.md, EVALUATION.md     # DEV track rules, environment & rubrics
    ├── market-data/                 # Challenge A: Market Data Pipeline
    │   ├── SPEC.md, SCORING.md, DATA.md, STORAGE.md
    │   ├── generate.py, datasets/, samples/
    └── pre-trade-risk/              # Challenge B: Pre-Trade Risk Engine
        ├── SPEC.md, SCORING.md, DATA.md
        ├── generate.py, datasets/, samples/
```

---

# Track 1: Quantitative Research (QR) Trading Challenge

Discover statistical relationships and microstructure signals across **50 assets** (`NEFS`, `QUNT`, etc.) over **5 historical days** (`10,000` timestamps per day) and implement an algorithmic trading strategy in Python.

At the end of the competition, your submitted `Trader` class will be evaluated on **unseen future days** drawn from the same market environment.

### Quick Start

Run `research/backtester.py` using `uv run` on one or more days:

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

### Writing Your Strategy (`research/template.py`)
Your strategy file must define a `Trader` class with a `run(self, state: TradingState) -> Dict[Symbol, List[Order]]` method. The `Trader` instance persists in memory across timestamps, allowing you to store rolling state on `self`.

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

### Market & Execution Rules

1. **Position Limits**: Every ticker has a hard position limit of **`±20` units**. If all orders submitted for a symbol on a single timestamp could breach `[-20, +20]` when added to your current position, that symbol's orders for that timestamp are rejected.
2. **Order Lifecycle**: Unfilled orders do not carry over to the next timestamp; emit desired orders on each call to `run(state)`.
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

### QR Dataset Schema

- **`research/data/prices/prices_day_X.csv`** (Semicolon-delimited `;`):
  `day`, `timestamp` (0–999,900 in steps of 100), `product`, `bid_price_1..3`, `bid_volume_1..3`, `ask_price_1..3`, `ask_volume_1..3`, `mid_price`.
- **`research/data/trades/trades_day_X.csv`** (Semicolon-delimited `;`):
  `timestamp`, `symbol`, `price`, `quantity`.

---

# Track 2: Software Engineering (DEV) Challenges

Build one or both independent systems from scratch. You are judged on correct behaviour, engineering decisions, and the evidence behind them. Full details, environment baselines, and rubrics are located in [`engineering/README.md`](engineering/README.md) and [`engineering/EVALUATION.md`](engineering/EVALUATION.md).

| Challenge | Languages | Main Problem | Specification |
| :--- | :--- | :--- | :--- |
| **A: Market Data Pipeline** | Python or Go | Consolidate imperfect feeds and publish a recoverable partitioned quote archive | [`SPEC.md`](engineering/market-data/SPEC.md), [`STORAGE.md`](engineering/market-data/STORAGE.md) |
| **B: Pre-Trade Risk Engine** | C, C++, or Rust | Make stateful risk decisions that survive process termination | [`SPEC.md`](engineering/pre-trade-risk/SPEC.md) |

### Engineering Rules & Submission

- **Scoring**: Each challenge is worth 100 points (team total out of 200). A carefully tested single challenge can outscore two unreliable implementations.
- **Timing**: 120-minute implementation window. All changes must be saved by the deadline.
- **Baseline Environment**: Linux x86-64, Ubuntu 24.04, 1 allocated CPU core, 1 GiB process-tree RSS. Toolchains: Python 3.12, Go 1.22, GCC/G++ 13 (C17/C++20), Rust 1.75 (edition 2021).
- **Deliverables**: Submissions must include:
  - Source code and a `DESIGN.md` (~500–750 words).
  - Executable offline `build.sh` and `run.sh` launchers.
  - Standard JSON Lines I/O contracts:
    - Challenge A: `./run.sh --data-dir /path/to/archive < input.jsonl > actual.jsonl`
    - Challenge B: `./run.sh --state-dir /path/to/state < input.jsonl > actual.jsonl`
