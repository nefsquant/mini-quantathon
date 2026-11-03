# Challenge B — Pre-Trade Risk Engine

Implement a **C, C++ or Rust** process for one trading account. It accepts or
rejects orders, reserves capacity for open orders, processes executions and
cancellations, changes limits, and survives abrupt termination. It is a risk
gate, not an exchange: there is no matching, market feed, cash balance, fee,
short-sale rule, price improvement or P&L calculation.

## 1. Execution and protocol

Build as in the root README. Launch with exactly:

```text
./run.sh --state-dir /absolute/path/to/state
```

The directory exists, is writable and is initially empty or contains only this
submission's previous state. Do not use any other persistent location. Only one
engine uses a directory at a time. Concurrent engines, filesystem corruption,
power failure, host reboot and hostile edits to files are outside scope. SIGKILL,
including during a write, is **inside scope**. Use at most 2 GiB of persistent
storage per history, including temporary/old files at peak. Restart may use the
same build but never memory from the old process. No persistence architecture or
file format is prescribed. A state path can contain spaces.

Read UTF-8 JSON Lines from stdin and produce exactly one newline-terminated JSON
response per schema-valid line. Flush each response as soon as it is safe to
acknowledge, without needing another input line. On start/restart emit nothing
until a request arrives. Process requests in input order. A new request cannot
observe half a previous transaction. Internal batching/concurrency is allowed
only if it preserves this behaviour. Exit 0 at EOF after completing all responses.
Empty input is valid and exits 0; an empty directory remains uninitialised until
a successful `init`. There is no required request on each restart.

Each line must be an object with exactly the keys specified below, no duplicate
JSON keys, no null input fields, no NaN/Infinity. Integers must be integer JSON
tokens, not booleans, strings, `1.0` or exponential notation. Each line is at most
64 KiB including newline. The final input line need not have a newline. Blank
lines, malformed JSON, schema errors, unknown types and out-of-range primitive
values are **fatal protocol errors**: do not mutate or cache the offending event,
emit no response for it, flush the preceding valid responses, report on stderr,
and exit 2 without reading further. A valid event with an unknown symbol/order or
a failed business rule is instead a durable rejection, as defined below.

On a detected persistence/I/O failure, emit diagnostics on stderr, stop with exit
3 and do not acknowledge the failing transaction. Preserve recoverability of all
previous acknowledgements. A transaction that committed before an output error
may be present after restart. Arbitrary injected device faults are not tested.
All stdout is protocol output; no startup messages or metrics.

## 2. Data model and schemas

Identifiers `event_id` and `order_id` match `[A-Za-z0-9_-]{1,64}` and are
case-sensitive. Symbols match `[A-Z][A-Z0-9_]{0,15}`. They are ASCII. Every request
has a `type` and an `event_id`. There is no timestamp or implicit expiry.

| Type | Remaining exact fields |
| --- | --- |
| `init` | `symbols`, `limits` |
| `new` | `order_id`, `symbol`, `side`, `qty`, `price` |
| `fill` | `order_id`, `qty` |
| `cancel` | `order_id` |
| `limits` | `limits` |
| `query` | no other fields |

`symbols` is an array of 1–32 objects, each with exactly `symbol` and
`reference_price`. Symbols must be unique; input order is immaterial.
`reference_price` and order `price` are integers 1–1,000,000 in the same currency
ticks. `side` is exactly `buy` or `sell`. `qty` is an integer 1–1,000,000 whole
units. A fill quantity is an **incremental** execution quantity, not cumulative.
Limits are an object with exactly these four integer fields, each 0–10^18:

| Field | Meaning |
| --- | --- |
| `max_order_qty` | Maximum submitted quantity for one new order |
| `max_order_notional` | Maximum `qty * price` for one new order |
| `max_abs_position` | Maximum absolute worst-case position, independently for every symbol |
| `max_gross_exposure` | Account-wide filled exposure plus all open-order notional |

Reference prices are fixed by the successful `init`; they never change. All
symbols share these four limits. Zero limits are valid. Use exact integers, no
floating point. All states within the workload bounds fit signed 64-bit integers,
including intermediate sums/products defined here; do not use 32-bit arithmetic.

## 3. Quantities, reservations and risk

For each configured symbol maintain signed filled position `P`, initially 0.
A buy fill increases P, a sell fill decreases P. Let `B` and `S` be the sum of
remaining quantities on **all open buy and sell orders**, respectively, for that
symbol. No reservation is netted against an opposing open order.

For a candidate new order include its entire quantity in B or S. The symbol's
position test is:

```text
abs(P + B) <= max_abs_position AND abs(P - S) <= max_abs_position
```

Test both endpoints even for a one-sided candidate; only the candidate symbol
is checked. Current limits can already be breached because of fills or limit
reductions. An existing breach in a different symbol does not independently
block a new order; the account exposure test still applies.

Account gross exposure is:

```text
sum over all symbols: abs(P) * reference_price
+ sum over all open orders: remaining_qty * order_price
```

This is deliberately conservative: opposing orders and filled positions do not
offset open reservations. Filled exposure uses the fixed reference price, while
reservations use the order price. A fill removes the executed quantity's
reservation and changes filled exposure; it can **increase** gross exposure if
the reference price exceeds the order price. Fills are external facts and must
not be rejected for breaching limits. Future new orders use the current state.

Example: P = -2, B = 3, S = 4 gives endpoints 1 and -6. A buy of 2 changes the
endpoints to 3 and -6; max_abs_position = 5 rejects it even though the buy could
reduce the current short. Exact equality with any limit passes.

## 4. Business transitions and rejection priority

First validate the entire schema, then apply the event-ID rules in section 5,
then the following rules. Every rejection leaves business state unchanged; it
still creates a durable event-ID/response record unless it is an ID conflict.

If the account is uninitialised, any type other than `init` is rejected with
`not_initialised`. These rejections are cached too. A valid first `init` creates
the symbols, reference prices and limits with zero positions and no orders.
A later `init` using a new event ID is rejected with `already_initialised`, even
if its contents equal the original. No reset operation exists.

For `new`, reject using the **first** failed rule in this order:

1. `duplicate_order_id`: the order ID belongs to any previously accepted order,
   including fully filled/cancelled orders. A rejected new order does not claim
   its order ID, so it can be retried with a new event ID.
2. `unknown_symbol`: the symbol was not configured.
3. `order_qty`: qty exceeds max_order_qty.
4. `order_notional`: qty × price exceeds max_order_notional.
5. `position_limit`: either candidate-symbol endpoint exceeds max_abs_position.
6. `gross_exposure`: total exposure including the candidate exceeds
   max_gross_exposure.

Otherwise create an open order with remaining = qty, reserve its quantity and
notional, and accept. New orders never execute automatically. All risk checks
are made on the proposed whole state, with no partial acceptance. There is no
restriction that buy/sell price must be near the reference price.

For `fill`, check in order: unknown order → `unknown_order`; known but closed
order → `order_closed`; qty greater than remaining → `insufficient_remaining`.
Otherwise reduce remaining by qty and adjust P by signed qty. A zero remainder
closes the order. A partial fill leaves its remaining reservation. Fill price is
implicitly the original order price; there is no price field in a fill. Risk
limits do not apply again to fills. No overfill or negative execution is allowed.

For `cancel`, check unknown order → `unknown_order`, then closed order →
`order_closed`. Otherwise release **all remaining** reservation and close the
order. Filled position is unchanged. There are no partial cancellations or
amendments. Closed order IDs remain occupied permanently.

`limits` atomically replaces all four limits and is always accepted after init.
Do not cancel existing orders or reject reductions below current usage. The new
limits apply only to subsequent new orders; fills/cancels remain legal.
`query` is accepted after init and returns a complete current-state view below.
No accepted event changes symbol definitions or reference prices.

## 5. Idempotency and crash recovery

The event ID identifies a **request**, not an order. Keep the identity and original
response of every schema-valid, non-conflicting request, accepted **or rejected**,
for the entire history, across restarts. A retry with the same event ID and
semantically identical payload returns the **original response**, without applying
anything again. For queries this means the historical response, not current state.

Semantic equality ignores object key order and JSON whitespace, and ignores the
order of `init.symbols` (it denotes a mapping). All other field values/types must
match exactly; omitted/extra fields are schema errors, not equivalent requests.
A schema-valid reuse of an ID with different contents returns
`event_id_conflict`; it does not change the original identity/response or business
state. This conflict response follows the same safe-output rule, but needs no
new event record. Event-ID lookup takes priority over all business rules: retrying
a successful `init` must succeed even though the account is now initialised.
Retrying a rejection must return that rejection even after the limits change.

An acknowledgement is a complete newline-terminated response received by the
caller. **Before emitting any response bytes**, make its business effects and
idempotency record survive abrupt process termination. The effect and record
must recover atomically. A request may have committed even if the caller did
not receive a complete response. On retry it must return the committed response;
otherwise it may execute once from the prior state. Never duplicate a fill,
release a reservation twice, forget a rejection, or invent an acknowledgement.

Recovery must produce a state consistent with processing a prefix of the input
history exactly once, including every observed acknowledgement and possibly
additional complete transactions whose response was not observed. Partial
persistent writes are not transactions. A retry of an old request must not roll
back newer state. Recovery must also be safe if killed again before completing.
Normal EOF is not a substitute for durability: the evaluator uses SIGKILL without
graceful shutdown. Only process-crash durability is required; a particular `fsync`
policy, journal, snapshot scheme or storage library is **not** mandated.

Restart on the same state directory and send requests normally; there is no
special recovery event, checkpoint request or replay flag. Inputs may retry old
IDs arbitrarily. An initialisation retry is legal; reinitialisation is not.

## 6. Outputs

Accepted non-query events, including successful init:

```json
{"event_id":"e1","status":"accepted"}
```

Rejected events, including conflicts and rejected queries:

```json
{"event_id":"e2","status":"rejected","reason":"position_limit"}
```

Accepted queries have exactly `event_id`, `status` and `state`:

```json
{"event_id":"q1","status":"accepted","state":{"limits":{"max_order_qty":10,"max_order_notional":1000,"max_abs_position":10,"max_gross_exposure":2000},"gross_exposure":400,"positions":[{"symbol":"ALPHA","position":2,"buy_remaining":2,"sell_remaining":0}],"orders":[{"order_id":"o1","symbol":"ALPHA","side":"buy","remaining":2,"price":100}]}}
```

State contains exactly `limits`, `gross_exposure`, `positions`, `orders`. Limits
echo the current four fields. Positions include **every** configured symbol,
sorted by ascending ASCII symbol name, with exactly `symbol`, `position`,
`buy_remaining`, `sell_remaining`. Orders include **only open orders**, sorted
by ascending ASCII order ID, with exactly the five fields shown. No terminal
orders, reference prices, request log or other metadata are output. Empty orders
is `[]`. All numeric outputs are integer JSON tokens, no floats.

## 7. Worked examples

[basic.input.jsonl](samples/basic.input.jsonl) and
[basic.expected.jsonl](samples/basic.expected.jsonl) show a buy of 6 at 100,
partial execution of 2 (P = 2, buy remaining = 4, gross = 600), a rejected buy
that would push the endpoint to 11, and a sell reservation of 3 at 90. Gross is
then 870. Cancelling the buy leaves P = 2 and gross = 470. Filling the sell
leaves P = -1 and gross = 100. Reducing max_abs_position to 0 blocks new risk
but does not change positions. Replaying the earlier fill returns its original
acceptance without another execution; a fresh query sees P = -1.

[idempotency.input.jsonl](samples/idempotency.input.jsonl) and matching expected
output demonstrate rejected-request caching after limits change, historical
query replies, conflicts and permanently occupied order IDs. Treat the prefix
through `f1` as an acknowledged history, kill, restart with the same directory,
then send the remaining lines: concatenated complete outputs must match the same
expected file. This is a manual recovery example, not a crash testing harness.

[exposure.input.jsonl](samples/exposure.input.jsonl) shows a low-price buy whose
fill raises gross exposure from 40 to 220 because the reference price is 100.
The fill still succeeds. Cancelling the remainder releases only 20. A sell to
reduce position can still fail the conservative gross test. The fixture also
covers exact limits, excess fill size, a zero-limit reduction and closed orders.

## 8. Bounds and acceptance

One complete persisted history contains at most 1,000,000 request lines (including
retries) and 256 MiB of input, at most 200,000 accepted distinct order IDs and at
most 10,000 simultaneously open orders. Across all non-retried query responses,
the total number of position and order entries is at most 1,000,000. Inputs and
outputs remain within 1 GiB each, including retried responses. These are workload
bounds, not new rejection rules. Primitive/schema error tests stay within size
bounds. Individual tests and public defaults are generally much smaller.

The process-tree memory limit is 1 GiB, the state-directory peak limit 2 GiB,
and the shared invocation/recovery ceiling 120 seconds. No fixed microsecond
latency target is imposed on a two-hour implementation; measure and explain
your costs. Hidden cases include long histories, many closed orders, rejected
requests, retries after limit changes and repeated interruption at transaction
boundaries. There are no surprise event types or unstated risk rules.

Full conformance means exact decisions/state, safe responses and successful
recovery within bounds. Partial implementations can earn independent group
credit; clearly document missing durability or features. See [SCORING.md](SCORING.md)
and [DATA.md](DATA.md). Do not sacrifice data integrity to improve a benchmark.
