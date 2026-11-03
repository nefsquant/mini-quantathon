#!/usr/bin/env python3
"""Generate deterministic inputs; deliberately contains no quote/output oracle."""

import argparse
from itertools import islice
import json
import random
import sys
from collections.abc import Iterator

Record = dict[str, object]
SIZES = {"small": (100, 2, 2, 4), "medium": (10_000, 4, 8, 16),
         "stress": (250_000, 8, 16, 128)}


def records(seed: int, scenario: str, venue_count: int, symbol_count: int,
            depth: int) -> Iterator[Record]:
    rng = random.Random(seed)
    venues = [f"V{i:02d}" for i in range(venue_count)]
    symbols = [f"S{i:02d}" for i in range(symbol_count)]
    pairs = [(venue, symbol) for venue in venues for symbol in symbols]
    sequences = dict.fromkeys(pairs, 0)
    yield {"type": "config", "venues": venues, "symbols": symbols, "stale_ms": 50,
           "partition_ms": 10_000}
    t = 0

    def book(kind: str, pair: tuple[str, str], seq: int, *, full: bool = False,
             empty: bool = False) -> Record:
        base = 100_000 + 10_000 * int(pair[1][1:])
        if empty:
            bids: list[list[int]] = []
            asks: list[list[int]] = []
        elif full:
            bids = [[base - i, rng.randint(1, 1000)] for i in range(depth)]
            asks = [[base + 2 + i, rng.randint(1, 1000)] for i in range(depth)]
        else:
            offset = rng.randrange(depth)
            bids = [[base - offset, rng.randint(0, 1000)]]
            asks = [[base + 2 + offset, rng.randint(0, 1000)]]
        return {"type": kind, "t": t, "venue": pair[0], "symbol": pair[1],
                "seq": seq, "bids": bids, "asks": asks}

    def query(pair: tuple[str, str]) -> Record:
        return {"type": "query", "t": t, "symbol": pair[1]}

    if scenario == "edge":
        yield book("delta", pairs[0], 9, empty=True)
        yield query(pairs[0])
    for pair in pairs:
        yield book("snapshot", pair, 0, full=True)
    cycle = 0
    while True:
        pair = rng.choice(pairs)
        t += rng.randint(0, 2)
        if scenario == "clean":
            sequences[pair] += 1
            yield book("delta", pair, sequences[pair])
            if cycle % 8 == 0:
                yield query(pair)
        else:
            base_seq = sequences[pair] + 10
            yield book("snapshot", pair, base_seq, full=True)
            yield book("delta", pair, base_seq + 1)
            yield book("delta", pair, base_seq + 1, empty=True)
            yield book("delta", pair, base_seq + 3, empty=True)
            yield book("delta", pair, base_seq + 2, empty=True)
            yield query(pair)
            yield book("snapshot", pair, base_seq - 1, full=True)
            t += 51
            yield query(pair)
            yield book("snapshot", pair, base_seq + 1, full=True)
            yield query(pair)
            yield book("delta", pair, base_seq + 2, empty=True)
            sequences[pair] = base_seq + 2
            if scenario == "edge":
                # Empty replacement and a crossed book are legal exchange states.
                yield book("snapshot", pair, base_seq + 2, empty=True)
                yield query(pair)
                crossed = book("snapshot", pair, base_seq + 2, empty=True)
                crossed["bids"] = [[102, 1_000_000_000], [100, 1]]
                crossed["asks"] = [[101, 1_000_000_000]]
                yield crossed
                yield query(pair)
                t += 50
                yield query(pair)
                t += 1
            yield query(pair)
        cycle += 1


def workload(seed: int, scenario: str, venue_count: int, symbol_count: int,
             depth: int) -> Iterator[Record]:
    next_checkpoint = 32
    source = records(seed, "mixed" if scenario == "storage" else scenario,
                     venue_count, symbol_count, depth)
    for index, record in enumerate(source, 1):
        if scenario == "storage" and record["type"] == "config":
            record = {**record, "partition_ms": 1000}
        yield record
        if index == next_checkpoint:
            t = record["t"]
            assert isinstance(t, int)
            history: Record = {"type": "history", "t": t, "symbol": "S00",
                               "from_t": max(0, t - 1000), "to_t": t + 1,
                               "after_line": 0, "limit": 5}
            if scenario == "storage":
                yield history.copy()
            yield {"type": "checkpoint", "t": t}
            if scenario == "storage":
                yield history.copy()
            next_checkpoint += min(next_checkpoint, 16_384)


def self_check() -> None:
    for scenario in ("clean", "mixed", "edge", "storage"):
        first = list(islice(workload(7, scenario, 2, 2, 4), 200))
        assert first == list(islice(workload(7, scenario, 2, 2, 4), 200))
        assert first != list(islice(workload(8, scenario, 2, 2, 4), 200))
        times: list[int] = []
        for event in first:
            t = event.get("t")
            if isinstance(t, int):
                times.append(t)
        assert times == sorted(times)
        assert first[0]["type"] == "config"
        assert any(event["type"] == "query" for event in first)
        assert any(event["type"] == "checkpoint" for event in first)
        if scenario == "storage":
            assert any(event["type"] == "history" for event in first)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--size", choices=SIZES, default="small")
    parser.add_argument("--events", type=int, help="total lines, including config")
    parser.add_argument("--scenario", choices=("clean", "mixed", "edge", "storage"),
                        default="mixed")
    parser.add_argument("--depth", type=int, help="levels per side in full snapshots")
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        self_check()
        print("Generator self-check passed", file=sys.stderr)
        return
    count, venues, symbols, depth = SIZES[args.size]
    count = args.events if args.events is not None else count
    depth = args.depth if args.depth is not None else depth
    maximum = 250_000 if args.scenario == "storage" else 1_000_000
    if not 1 <= count <= maximum:
        parser.error(f"--events must be in 1..{maximum} for {args.scenario}")
    if not 1 <= depth <= min(20_000, 500_000 // (2 * venues * symbols)):
        parser.error("--depth exceeds the configured book-state bounds")
    for event in islice(workload(args.seed, args.scenario, venues, symbols, depth), count):
        print(json.dumps(event, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
