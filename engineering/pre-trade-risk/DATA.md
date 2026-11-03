# Sample data and generation

Run from the repository root with Python 3.11+ and no third-party packages:

```sh
python3 pre-trade-risk/generate.py --size small --seed 42 > /tmp/risk-small.jsonl
python3 pre-trade-risk/generate.py --size medium --seed 42 > /tmp/risk-medium.jsonl
python3 pre-trade-risk/generate.py --size stress --seed 42 > /tmp/risk-stress.jsonl
python3 pre-trade-risk/generate.py --size stress --scenario pressure --seed 7 > /tmp/risk-pressure.jsonl
python3 pre-trade-risk/generate.py --scenario edge --events 300 --seed 9 > /tmp/risk-edge.jsonl
python3 pre-trade-risk/generate.py --self-check
```

`--size small|medium|stress` means 100 / 10,000 / 250,000 total input lines.
Default is small. `--events N` overrides that count, including init and retries.
The upper override bound is 400,000 for clean/pressure, 800,000 for mixed, and
1,000,000 for edge, keeping order counts and query-state volume within the bounds.
`--seed` is an integer, default 1. Use a fresh empty state directory for a new
dataset; to resume/retry a dataset use the same state directory and IDs.

Scenarios:

- `clean`: buy, partial execution, cancel remaining, sell the executed quantity,
  execute the sell, with queries before and after. Cycles use one of eight
  instruments and do not accumulate positions or open orders.
- `mixed` (default): also retries accepted new/fill requests and historical
  queries, conflicts on payload, reuses closed IDs, and submits over-limit orders.
- `edge`: also sends overfills, unknown-order cancellations, freezes all limits
  at zero, restores limits, and retries the frozen-limit rejection. The fixed
  exposure fixture covers executions increasing gross exposure.
- `pressure`: first opens 10,000 orders under generous limits, queries all
  reservations, cancels them, then emits unique new/cancel pairs and occasional
  queries. This exercises large active state and long terminal-order history.
  Small/short prefixes intentionally stop during the initial build-up.

The generator constructs request templates and IDs, not risk decisions. There
is no embedded engine, expected-output computation or crash runner. Input is
schema-valid but deliberately contains business rejections/conflicts. At exactly
N lines the stream stops, including if there are still open reservations. EOF
does not cancel orders. Default presets and supported overrides respect workload
bounds. Replaying a generated file against an already completed history returns
historical replies without executing again.

The same script version, Python version, seed and options produce identical
bytes. Compare two generated files using `cmp`. `--self-check` verifies small
generator properties and repeatability, writes only a diagnostic to stderr and
does not grade participant implementations.

## Included datasets

These files are input-only and ready to run.

| File | Lines | Bytes | Reproduce with generator arguments |
| --- | ---: | ---: | --- |
| `datasets/small.jsonl` | 100 | 7,288 | `--size small --seed 42` |
| `datasets/medium.jsonl` | 10,000 | 721,645 | `--size medium --seed 42` |
| `datasets/stress.jsonl` | 25,000 | 2,121,275 | `--size stress --scenario pressure --events 25000 --seed 7` |

The included stress workload reaches 10,000 concurrent open reservations before
unwinding them, then grows closed-order history. Generate the 250,000-line stress
preset for a longer throughput/history exercise. The shorter checked-in file
keeps distribution practical while reaching the maximum active-order count.

## Fixed fixtures and recovery exercise

| Prefix under `samples/` | Expected exit | Purpose |
| --- | ---: | --- |
| `basic` | 0 | Reservations, partial fills, both sides, limit reduction, retry |
| `idempotency` | 0 | Cached rejection/query, conflicts, closed IDs, reordered init mapping |
| `exposure` | 0 | Reference/limit-price difference, limit equality, overfill and closed order |
| `protocol-error` | 2 | Out-of-range zero quantity; only init receives a reply |

Each prefix has `.input.jsonl` and `.expected.jsonl`. Query arrays are sorted;
object keys need not be. Compare parsed JSON, response count and exit code.
Use a fresh empty directory for each independent fixture:

```sh
mkdir /tmp/risk-basic-state
./run.sh --state-dir /tmp/risk-basic-state < /path/to/pre-trade-risk/samples/basic.input.jsonl > /tmp/risk-actual.jsonl
```

For a recovery exercise, use `idempotency`: the first fill `f1` is line 7.
Deliver lines 1–7 interactively, wait for all seven complete replies, terminate
the process with SIGKILL, and restart on the same directory. Deliver lines 8–14;
the combined complete replies must equal the expected file. Retrying earlier
lines must return their original replies. A fresh query ID must show the latest
state, not a replayed query's historical view. Also test interruption before a
reply and during state-file writes; the commit boundary is your responsibility.
No executable recovery harness is supplied.

The protocol-error fixture expects exit 2 and no responses after init. For an
additional manual check, restart that directory and send a fresh query: it must
show zero positions and no orders. Invalid schema must not create a transaction.
Public examples are deliberately small and are not evidence of complete crash
safety. Hidden histories and their seeds are not distributed.
