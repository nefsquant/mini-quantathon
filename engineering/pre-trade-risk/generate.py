#!/usr/bin/env python3
"""Generate deterministic request histories, without computing risk decisions."""

import argparse
from collections.abc import Iterator
from itertools import islice
import json
import random
import sys

Record = dict[str, object]
SIZES = {"small": 100, "medium": 10_000, "stress": 250_000}
NORMAL_LIMITS = {"max_order_qty": 1000, "max_order_notional": 1_000_000,
                 "max_abs_position": 500, "max_gross_exposure": 2_000_000}


def records(seed: int, scenario: str) -> Iterator[Record]:
    rng = random.Random(seed)
    symbols = [{"symbol": f"S{i:02d}", "reference_price": 100 + i * 10}
               for i in range(8)]
    yield {"type": "init", "event_id": "init", "symbols": symbols,
           "limits": NORMAL_LIMITS}
    counter = 0

    def event(kind: str, **fields: object) -> Record:
        nonlocal counter
        counter += 1
        return {"type": kind, "event_id": f"e{counter}", **fields}

    cycle = 0
    while True:
        symbol_index = rng.randrange(len(symbols))
        symbol = f"S{symbol_index:02d}"
        price = 100 + symbol_index * 10
        qty = rng.randint(2, 40)
        filled = qty // 2
        buy_id, sell_id = f"b{cycle}", f"s{cycle}"
        new = event("new", order_id=buy_id, symbol=symbol, side="buy", qty=qty, price=price)
        yield new
        if scenario != "clean":
            yield new.copy()
        before = event("query")
        yield before
        fill = event("fill", order_id=buy_id, qty=filled)
        yield fill
        if scenario != "clean":
            yield fill.copy()
            yield before.copy()
            yield {**new, "qty": qty + 1}
        if scenario == "edge":
            yield event("fill", order_id=buy_id, qty=qty)
            yield event("cancel", order_id="unknown")
            frozen = {key: 0 for key in NORMAL_LIMITS}
            yield event("limits", limits=frozen)
            rejected = event("new", order_id=f"r{cycle}", symbol=symbol,
                             side="sell", qty=1, price=1)
            yield rejected
            yield event("limits", limits=NORMAL_LIMITS)
            yield rejected.copy()
        yield event("cancel", order_id=buy_id)
        yield event("new", order_id=sell_id, symbol=symbol, side="sell",
                    qty=filled, price=price)
        yield event("fill", order_id=sell_id, qty=filled)
        if scenario != "clean":
            yield event("cancel", order_id=sell_id)
            yield event("new", order_id=buy_id, symbol=symbol, side="buy",
                        qty=1, price=price)
            yield event("new", order_id=f"large{cycle}", symbol=symbol,
                        side="buy", qty=1001, price=price)
        yield event("query")
        cycle += 1


def pressure_records(seed: int) -> Iterator[Record]:
    """Long-lived reservations, a full unwind, then new/cancel traffic."""
    rng = random.Random(seed)
    limits = {key: 10**18 for key in NORMAL_LIMITS}
    yield {"type": "init", "event_id": "p_init", "symbols": [
        {"symbol": "ALPHA", "reference_price": 100}], "limits": limits}
    for index in range(10_000):
        yield {"type": "new", "event_id": f"p_n{index}", "order_id": f"p_o{index}",
               "symbol": "ALPHA", "side": "buy" if index % 2 == 0 else "sell",
               "qty": rng.randint(1, 1000), "price": rng.randint(50, 150)}
    yield {"type": "query", "event_id": "p_q"}
    for index in range(10_000):
        yield {"type": "cancel", "event_id": f"p_c{index}", "order_id": f"p_o{index}"}
    cycle = 0
    while True:
        order_id = f"tail{cycle}"
        yield {"type": "new", "event_id": f"tail_n{cycle}", "order_id": order_id,
               "symbol": "ALPHA", "side": "buy", "qty": rng.randint(1, 1000),
               "price": 100}
        yield {"type": "cancel", "event_id": f"tail_c{cycle}", "order_id": order_id}
        if cycle % 100 == 0:
            yield {"type": "query", "event_id": f"tail_q{cycle}"}
        cycle += 1


def self_check() -> None:
    for scenario in ("clean", "mixed", "edge"):
        first = list(islice(records(7, scenario), 200))
        assert first == list(islice(records(7, scenario), 200))
        assert first != list(islice(records(8, scenario), 200))
        assert first[0]["type"] == "init"
        assert any(event["type"] == "fill" for event in first)
    pressure = list(islice(pressure_records(7), 20_003))
    assert pressure == list(islice(pressure_records(7), 20_003))
    assert pressure[10_001] == {"type": "query", "event_id": "p_q"}
    assert pressure[20_002]["type"] == "new"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--size", choices=SIZES, default="small")
    parser.add_argument("--events", type=int, help="total lines, including init and retries")
    parser.add_argument("--scenario", choices=("clean", "mixed", "edge", "pressure"),
                        default="mixed")
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        self_check()
        print("Generator self-check passed", file=sys.stderr)
        return
    count = args.events if args.events is not None else SIZES[args.size]
    maximum = {"clean": 400_000, "mixed": 800_000, "pressure": 400_000}.get(
        args.scenario, 1_000_000)
    if not 1 <= count <= maximum:
        parser.error(f"--events must be in 1..{maximum} for {args.scenario}")
    stream = pressure_records(args.seed) if args.scenario == "pressure" else records(
        args.seed, args.scenario)
    for request in islice(stream, count):
        print(json.dumps(request, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
