# Challenge A — Market Data Pipeline

Implement a process in **Python or Go** that maintains aggregated price-level
books for simulated exchanges, answers consolidated best-quote queries, and
publishes a recoverable, partitioned archive of those quotes on local disk.
Inputs arrive in delivery order, which can differ from exchange sequence order.
Losing synchronisation must remove a venue's quotes until a usable snapshot
arrives. Do not implement matching, individual orders, trades or networking.

## 1. Process and protocol

Build as described in the root README. Launch with
`./run.sh --data-dir /absolute/path/to/archive`. The directory exists, is writable,
and is empty or contains this submission's previous archive. It may contain
spaces. Only one process uses it at a time; all persistent files must live there.
Read UTF-8 JSON Lines from stdin, write exactly one JSON object followed by a
newline for each valid input line, and exit 0 at EOF. Flush each response without
waiting for another input line; interactive query tests use pipes. Diagnostics
go to stderr. Restore the latest published checkpoint before accepting input.
If there is no published manifest, start empty even if uncommitted files exist.

Blank lines are invalid. Each line must be a JSON object with exactly the keys
specified below; no duplicate JSON keys, comments, `null` input fields, NaN or
Infinity. Integers must be JSON integer tokens (not booleans, strings, `1.0` or
exponential notation). Object key order and whitespace do not matter. Each input
line is at most 4 MiB including its newline. The final input line may omit its
newline. Do not emit extra fields in responses.

On a fresh archive the first line must be `config`; it appears exactly once in
the logical history. After recovery, input continues **after** the committed
prefix, without another config. A schema violation,
unknown type/name, out-of-range number, repeated config, non-monotonic `t`, or
malformed JSON is a **fatal protocol error**: do not process that line, emit no
response for it, diagnose on stderr and exit 2. Outputs for preceding lines must
already have been flushed. Stop reading; no later line is processed. This error
class is distinct from valid but unusable sequence messages below.
Empty input on a fresh archive is a missing-config error (exit 2, no stdout);
empty input after recovery is valid. Config alone is valid but is not committed.
EOF does not publish a checkpoint or emit any extra response. On detected storage
I/O failure, exit 3 with a diagnostic and leave a complete recoverable generation;
never acknowledge a failed publication. A failure after publication may leave
the new generation current. There is no power-loss or corruption test.

Identifiers are case-sensitive ASCII matching `[A-Z][A-Z0-9_]{0,15}`. A configured
list must be non-empty and contain no duplicates; its input order is immaterial.

## 2. Input schemas

| Type | Exact fields and constraints |
| --- | --- |
| `config` | `type`, `venues` (1–16 identifiers), `symbols` (1–32 identifiers), `stale_ms` (integer 0–1,000,000,000), `partition_ms` (integer 1–1,000,000,000) |
| `snapshot` | `type`, `t`, `venue`, `symbol`, `seq`, `bids`, `asks` |
| `delta` | `type`, `t`, `venue`, `symbol`, `seq`, `bids`, `asks` |
| `query` | `type`, `t`, `symbol` |
| `checkpoint` | `type`, `t` |
| `history` | `type`, `t`, `symbol`, `from_t`, `to_t`, `after_line`, `limit` |

Every non-config event has integer `t` in 0–9,000,000,000,000, in simulated
milliseconds. It must be greater than or equal to the preceding non-config `t`;
the first may have any value in range. This is delivery time, **not exchange
time**. Never use wall time for freshness. Even ignored events advance delivery
time. Quote queries observe current consolidated quotes; history queries read
published rows. There is no automatic quote output when time passes.

`venue` and `symbol` must be configured. `seq` is an integer in
0–9,000,000,000,000. It is independent for every `(venue, symbol)` pair.
`bids` and `asks` are arrays of `[price, quantity]` pairs, each exactly length 2.
Price is an integer 1–1,000,000,000 in arbitrary price ticks. Snapshot quantities
are integers 1–1,000,000,000; delta quantities are 0–1,000,000,000. Arrays need
not be sorted. A price may occur at most once **within each side of a message**;
the same price on opposite sides is allowed. Empty arrays are valid. Check the
whole schema even if the event will be ignored as old or unsynchronised.

## 3. Book transitions

Each pair starts **uninitialised** with `seq = null`, no usable levels and no
last-accepted time. Sequence numbers count whole messages, not changed levels.
Process input lines serially, in file order. Never buffer or reorder messages.

For a snapshot:

1. If a sequence has been accepted and the snapshot's `seq` is smaller, return
   `ignored_old`; change nothing in that pair.
2. Otherwise replace both entire sides (including clearing levels absent from
   the snapshot), set the accepted sequence and last-accepted time to its `seq`
   and `t`, mark the pair synchronised and return `replaced`.

A snapshot with the **same** sequence is deliberately accepted: it is an
authoritative replacement and can recover a gap or refresh a stale pair. It may
have different contents. There is no requirement that it fill a detected gap's
highest observed sequence. A later arriving delta may detect a further gap.

For a delta, take the **first applicable** rule:

1. If the pair has never accepted a snapshot, return `ignored_uninitialised`.
   Do not remember the delta's sequence or mark a gap.
2. If `seq <= accepted_seq`, return `ignored_old`, even if currently in a gap.
3. If the pair is in a gap, return `ignored_gap`.
4. If `seq != accepted_seq + 1`, mark the pair in a gap and return `gap`.
   Do not advance the accepted sequence, update its time, or apply any changes.
5. Otherwise apply all changes atomically, set accepted sequence/time to this
   event's `seq`/`t`, remain synchronised and return `applied`.

Delta quantities **replace** the quantity at a price; they are not increments.
Zero deletes the level; deleting an absent price is a no-op. An empty delta
still advances sequence and refreshes time. A stale but synchronised pair can
apply its next delta and become fresh again. Ignored messages never refresh time.
There is no checksum, sequence reset, end-of-session reset or other recovery type.

The bid side's best price is its maximum; the ask side's best is its minimum.
Empty and one-sided books are legitimate. Crossed/locked books and crossed/locked
consolidated markets are legitimate too; do not reject, uncross or match them.

## 4. Queries and freshness

At query time `t`, classify every venue for the requested symbol in this priority:

1. `uninitialised` if it has never accepted a snapshot;
2. `gap` if it is unsynchronised;
3. `stale` if `t - last_accepted_t > stale_ms`;
4. `live` otherwise.

Only `live` books contribute. At exactly the age limit a book is live. Empty
live books still have status `live`. Staleness does not discard levels or change
sequence synchronisation. A query does not refresh any book.

The consolidated bid is the maximum bid price across eligible books. Sum the
quantities **at that exact best price** over all tied venues. Report those venues
in ascending ASCII order. The ask is analogous using the minimum ask price.
Each side is independent: a venue can contribute on only one side. If no eligible
venue has a level on a side, that side is `null`. `spread` is ask price minus bid
price if both exist, including zero or negative values; otherwise it is `null`.
Use exact integer arithmetic; aggregate quantities can exceed 32 bits.

## 5. Output schemas

`line` is the 1-based position in the **logical history**, including config and
storage events. After restart it resumes at `manifest.through_line + 1`, rather
than restarting at 1. Config responds:

```json
{"line":1,"result":"configured"}
```

Every snapshot/delta responds with exactly `line` and `result`. The result is one
of `replaced`, `applied`, `ignored_old`, `ignored_uninitialised`, `gap`,
`ignored_gap`, according to section 3. It describes that event, not book freshness.

A query responds with exactly:

```json
{"line":4,"result":"quote","symbol":"ALPHA","bid":{"price":100,"qty":7,"venues":["X"]},"ask":null,"spread":null,"books":[{"venue":"X","status":"live","seq":2}]}
```

`bid` and `ask` are either `null` or objects with exactly `price`, `qty`,
`venues`. `books` contains every configured venue, sorted by ascending ASCII
venue name, each with exactly `venue`, `status`, `seq`. Here `seq` is the last
accepted sequence, or `null`; it remains unchanged when a gap is detected.
`symbol` echoes the query's symbol. Output integers use integer JSON tokens.

## 6. Storage contract

[STORAGE.md](STORAGE.md) is a normative part of this specification. It defines
partitioned quote files, the public manifest schema, checkpoint publication,
historical query I/O and exact restart semantics. These behaviours are required;
storage is not an optional extension. The public archive format is an output
contract; internal book structures and checkpoint encoding remain your choice.

## 7. Worked examples

See [basic.input.jsonl](samples/basic.input.jsonl) and its
[expected output](samples/basic.expected.jsonl). The two snapshots initially
produce bid 100 with quantity 7 from X and Y, ask 102 from Y, spread 2. X's delta
deletes its bid 100, adds bid 101 and replaces ask 103. X's repeated sequence is
ignored despite different contents. At `t = 10`, Y is exactly at the freshness
boundary and remains live. At `t = 11`, Y is stale; X is still live. At `t = 16`
both are stale and the consolidated sides are null.

[recovery.input.jsonl](samples/recovery.input.jsonl) exercises an initial delta,
a missing sequence, an old delta while in a gap, a later ignored delta, an old
snapshot, and an equal-sequence recovery snapshot. Recovery creates a crossed
market (bid 12, ask 11, spread -1). A deleting delta leaves an empty live book.

[boundaries.input.jsonl](samples/boundaries.input.jsonl) demonstrates unsorted
levels, one-sided books, quantities above 32-bit range after aggregation, and
freshness with `stale_ms = 0`. Every expected output is explicit in these files.

[storage.input.jsonl](samples/storage.input.jsonl) and its expected output exercise
a time-bucket boundary across three partitions, uncommitted-row invisibility, successive
manifests, pagination and an empty publication. See [DATA.md](DATA.md) for the
matching archive rows and restart suffix, which checks restored book state
and logical-line continuation without another config.

## 8. Scale, acceptance and freedom

Evaluation inputs have at most 1,000,000 lines including config and at most
512 MiB of input. At any accepted state there are at most 500,000 total stored
price levels across all pairs/sides, at most 20,000 per side of a pair, and at
most 20,000 entries on either side of any message. These are workload bounds,
not extra conditions to reject. Schema-error tests stay within these size bounds.
One history contains at most 100 checkpoints, 50,000 non-empty archive partitions,
and 1,000,000 total rows returned by history queries. Input bounds cover the
entire logical history, including all resumed suffixes; replayed uncommitted
prefix attempts do not increase its logical length. Many tests are much smaller.
Stress tests include concentrated updates, sparse quotes, repeated gaps, old
messages, many instruments, long quiet periods and selective historical reads.

The shared 1 GiB RSS and 120-second per-case ceiling apply. No specific events per
second target is required; efficiency is measured comparatively. Use at most
2 GiB of local archive storage, including private and temporary files at peak.
There is no external clock or exchange connection. You may retain or discard
stale data internally if all subsequent transitions and checkpoint recovery remain
correct. Internal layout, sorting, indexing and concurrency are your choice.
An implementation is fully conformant when its responses, public archive,
publication/recovery behaviour and fatal exits satisfy every rule within bounds.
See [SCORING.md](SCORING.md) for partial-credit groups and
[DATA.md](DATA.md) for reproducible workloads.
