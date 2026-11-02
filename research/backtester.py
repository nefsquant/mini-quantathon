#!/usr/bin/env python3
import argparse
import csv
import importlib.util
import math
import pathlib
import statistics
from collections import defaultdict
from typing import Dict, List, Tuple

from datamodel import Order, OrderDepth, Symbol, Trade, TradingState

POSITION_LIMIT = 20


def load_trader(path: str):
    spec = importlib.util.spec_from_file_location("submission", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.Trader()


def load_day(data_dir: pathlib.Path, day: int):
    prices_path = data_dir / "prices" / f"prices_day_{day}.csv"
    trades_path = data_dir / "trades" / f"trades_day_{day}.csv"
    if not prices_path.exists():
        raise FileNotFoundError(f"Missing {prices_path}")

    # shortcut: in-memory dict keyed by timestamp for single-day replay, switch to streaming if >1M rows/day
    book_by_ts: Dict[int, Dict[str, Tuple[OrderDepth, float]]] = defaultdict(dict)
    with prices_path.open("r", newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            ts = int(r["timestamp"])
            sym = r["product"]
            buys: Dict[int, int] = {}
            sells: Dict[int, int] = {}
            for i in (1, 2, 3):
                bp, bv = r[f"bid_price_{i}"], r[f"bid_volume_{i}"]
                if bp and bv:
                    buys[int(bp)] = int(bv)
                ap, av = r[f"ask_price_{i}"], r[f"ask_volume_{i}"]
                if ap and av:
                    sells[int(ap)] = -int(av)
            book_by_ts[ts][sym] = (OrderDepth(buys, sells), float(r["mid_price"]))

    trades_by_ts: Dict[int, Dict[str, List[Trade]]] = defaultdict(lambda: defaultdict(list))
    if trades_path.exists():
        with trades_path.open("r", newline="") as f:
            for r in csv.DictReader(f, delimiter=";"):
                ts = int(r["timestamp"])
                sym = r["symbol"]
                trades_by_ts[ts][sym].append(Trade(sym, int(float(r["price"])), int(r["quantity"]), ts))
    return sorted(book_by_ts.keys()), book_by_ts, trades_by_ts


def run_strategy(trader_path: str, data_dir: pathlib.Path, days: List[int], limit: int = POSITION_LIMIT) -> dict:
    trader = load_trader(trader_path)
    cash: Dict[str, float] = defaultdict(float)
    position: Dict[str, int] = defaultdict(int)
    last_mid: Dict[str, float] = defaultdict(float)

    orders_sent = 0
    qty_requested = 0
    qty_filled = 0
    fill_events = 0
    total_ticks = 0
    equity_curve: List[float] = []

    for day in days:
        timestamps, book_by_ts, trades_by_ts = load_day(data_dir, day)
        own_trades: Dict[str, List[Trade]] = {}
        market_trades: Dict[str, List[Trade]] = {}

        for ts in timestamps:
            total_ticks += 1
            ts_books = book_by_ts[ts]
            order_depths: Dict[str, OrderDepth] = {}
            for sym, (od, mid) in ts_books.items():
                order_depths[sym] = OrderDepth(dict(od.buy_orders), dict(od.sell_orders))
                last_mid[sym] = mid

            state = TradingState(
                timestamp=ts,
                order_depths=order_depths,
                own_trades=own_trades,
                market_trades=market_trades,
                position=dict(position),
            )

            out = trader.run(state)
            orders: Dict[Symbol, List[Order]] = out[0] if isinstance(out, tuple) else out

            own_trades = {}
            market_trades = {}
            ts_mtrades = trades_by_ts.get(ts, {})

            for sym, sym_orders in orders.items():
                if sym not in order_depths or not sym_orders:
                    continue
                pos = position[sym]
                long_req = sum(o.quantity for o in sym_orders if o.quantity > 0)
                short_req = sum(-o.quantity for o in sym_orders if o.quantity < 0)
                if pos + long_req > limit or pos - short_req < -limit:
                    continue

                od = order_depths[sym]
                m_rem = [[t, t.quantity, t.quantity] for t in ts_mtrades.get(sym, [])]
                sym_fills: List[Trade] = []

                for o in sym_orders:
                    if o.quantity == 0:
                        continue
                    orders_sent += 1
                    qty_requested += abs(o.quantity)
                    rem = int(o.quantity)
                    price = int(o.price)

                    if rem > 0:
                        for ask_p in sorted(p for p in od.sell_orders if p <= price):
                            avail = -od.sell_orders[ask_p]
                            fill = min(rem, avail)
                            if fill > 0:
                                position[sym] += fill
                                cash[sym] -= ask_p * fill
                                od.sell_orders[ask_p] += fill
                                if od.sell_orders[ask_p] == 0:
                                    del od.sell_orders[ask_p]
                                rem -= fill
                                qty_filled += fill
                                fill_events += 1
                                sym_fills.append(Trade(sym, ask_p, fill, ts))
                            if rem == 0:
                                break
                        if rem > 0:
                            for mt in m_rem:
                                if mt[2] > 0 and mt[0].price <= price:
                                    fill = min(rem, mt[2])
                                    position[sym] += fill
                                    cash[sym] -= price * fill
                                    mt[2] -= fill
                                    rem -= fill
                                    qty_filled += fill
                                    fill_events += 1
                                    sym_fills.append(Trade(sym, price, fill, ts))
                                    if rem == 0:
                                        break
                    else:
                        need = -rem
                        for bid_p in sorted((p for p in od.buy_orders if p >= price), reverse=True):
                            avail = od.buy_orders[bid_p]
                            fill = min(need, avail)
                            if fill > 0:
                                position[sym] -= fill
                                cash[sym] += bid_p * fill
                                od.buy_orders[bid_p] -= fill
                                if od.buy_orders[bid_p] == 0:
                                    del od.buy_orders[bid_p]
                                need -= fill
                                qty_filled += fill
                                fill_events += 1
                                sym_fills.append(Trade(sym, bid_p, fill, ts))
                            if need == 0:
                                break
                        if need > 0:
                            for mt in m_rem:
                                if mt[1] > 0 and mt[0].price >= price:
                                    fill = min(need, mt[1])
                                    position[sym] -= fill
                                    cash[sym] += price * fill
                                    mt[1] -= fill
                                    need -= fill
                                    qty_filled += fill
                                    fill_events += 1
                                    sym_fills.append(Trade(sym, price, fill, ts))
                                    if need == 0:
                                        break
                if sym_fills:
                    own_trades[sym] = sym_fills

            for sym, t_list in ts_mtrades.items():
                market_trades[sym] = list(t_list)

            total_eq = sum(cash[s] + position[s] * last_mid[s] for s in last_mid)
            equity_curve.append(total_eq)

    returns = [equity_curve[i] - equity_curve[i - 1] for i in range(1, len(equity_curve))] if len(equity_curve) > 1 else [0.0]
    mean_r = statistics.fmean(returns) if returns else 0.0
    std_r = statistics.pstdev(returns) if len(returns) > 1 else 0.0
    downside = [min(0.0, r) for r in returns]
    down_std = math.sqrt(statistics.fmean([d * d for d in downside])) if downside else 0.0

    ann = math.sqrt(max(1, len(returns)))
    sharpe = (mean_r / std_r * ann) if std_r > 1e-12 else 0.0
    sortino = (mean_r / down_std * ann) if down_std > 1e-12 else 0.0

    peak = 0.0
    max_dd = 0.0
    for eq in equity_curve:
        if eq > peak:
            peak = eq
        dd = peak - eq
        if dd > max_dd:
            max_dd = dd

    ticker_pnl = {s: cash[s] + position[s] * last_mid[s] for s in last_mid}
    total_pnl = sum(ticker_pnl.values())
    fill_rate = (qty_filled / qty_requested * 100.0) if qty_requested > 0 else 0.0
    trading_rate = fill_events / max(1, total_ticks)
    composite = total_pnl * (1.0 + 0.15 * max(-5.0, min(10.0, sharpe))) - 0.25 * max_dd

    return {
        "strategy": trader_path,
        "total_pnl": total_pnl,
        "sharpe": sharpe,
        "sortino": sortino,
        "max_dd": max_dd,
        "fill_rate": fill_rate,
        "trading_rate": trading_rate,
        "qty_filled": qty_filled,
        "orders_sent": orders_sent,
        "composite": composite,
        "ticker_pnl": ticker_pnl,
    }


def main():
    p = argparse.ArgumentParser(description="NEFS Prosperity-Style L2 Backtester")
    p.add_argument("strategies", nargs="+", help="Path(s) to Trader python file(s)")
    p.add_argument("--data-dir", default=str(pathlib.Path(__file__).resolve().parent / "data"), help="Directory containing prices/ and trades/")
    p.add_argument("--days", nargs="+", type=int, default=[1], help="Day numbers to run (e.g. 1 2 3)")
    args = p.parse_args()

    results = []
    for s_path in args.strategies:
        res = run_strategy(s_path, pathlib.Path(args.data_dir), args.days)
        results.append(res)
        print(f"\n=== Backtest Tear Sheet: {s_path} (Days {args.days}) ===")
        print(f"Total PnL      : {res['total_pnl']:,.2f}")
        print(f"Sharpe Ratio   : {res['sharpe']:.3f}")
        print(f"Sortino Ratio  : {res['sortino']:.3f}")
        print(f"Max Drawdown   : {res['max_dd']:,.2f}")
        print(f"Fill Rate      : {res['fill_rate']:.1f}% ({res['qty_filled']} filled / {res['orders_sent']} orders)")
        print(f"Trading Rate   : {res['trading_rate']:.3f} fills/tick")
        print(f"Composite Score: {res['composite']:,.2f}")
        ranked_syms = sorted(res["ticker_pnl"].items(), key=lambda kv: kv[1], reverse=True)
        active = [(k, v) for k, v in ranked_syms if abs(v) > 1e-6]
        if active:
            print("Top/Bottom Active Tickers:")
            for k, v in active[:5]:
                print(f"  + {k}: {v:,.2f}")
            if len(active) > 5:
                for k, v in active[-3:]:
                    print(f"  - {k}: {v:,.2f}")

    if len(results) > 1:
        print("\n=== Multi-Strategy Leaderboard ===")
        for rank, r in enumerate(sorted(results, key=lambda x: x["composite"], reverse=True), 1):
            print(
                f"{rank}. {r['strategy']:25s} | Score: {r['composite']:10,.2f} | "
                f"PnL: {r['total_pnl']:10,.2f} | Sharpe: {r['sharpe']:6.2f} | "
                f"Sortino: {r['sortino']:6.2f} | MaxDD: {r['max_dd']:8,.2f}"
            )


if __name__ == "__main__":
    main()
