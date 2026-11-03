# Partitioned quote archive — required contract

This document is a normative part of [SPEC.md](SPEC.md). Produce ordinary local
files, with no external service. No particular journal, storage library or
persistence algorithm is required. You choose staging, recovery encoding and
segment sizes; the public archive and behaviour must match this contract.

## Archived rows and partition keys

Every successful `query` stages exactly one archive row, even if both sides are
null. Its exact fields are `line`, `t`, `symbol`, `bid`, `ask`, `spread`: copy
these quote values from the response and the query's `t`; omit `result` and
`books`. Snapshots, deltas, config, history and checkpoints do not produce rows.
An ignored feed event therefore never creates a row by itself.

Partition by `(symbol, bucket)`, where `bucket = t // partition_ms`. Buckets are
half-open intervals `[bucket * partition_ms, (bucket + 1) * partition_ms)`.
Use delivery time, not sequence number or wall time. No empty partition is listed.
Each data file contains newline-terminated UTF-8 JSON Lines with this row schema,
one partition only, in strictly increasing logical-line order. No compression is
required or permitted for these public files. File names and segment sizes are
your choice. Multiple immutable files may belong to the same partition.

Rows become visible **only** when published by a checkpoint. A quote response is
provisional until then. After a crash, unpublished quotes and feed updates may
disappear, even if their individual responses were received. This differs from
challenge B's per-request durability.

## Checkpoint transition and response

`checkpoint` has exactly `type`, `t`. It publishes all staged rows since the
previous checkpoint and a recoverable state at the end of its own logical line.
This includes config, every book's levels, accepted sequence, gap/initialisation
status, last-accepted times, global delivery time and logical-line position.
Restore **all** of these, including stale/unsynchronised books: their later updates
must behave exactly as before. A checkpoint does not refresh any book. Its `t`
advances global delivery time under the same rule as every non-config event.

Generation starts at 0 with no committed rows. Each checkpoint publishes the
next integer generation, even if there are no new rows. Before emitting any
checkpoint response bytes, the new manifest, referenced data, and recovery state
must survive SIGKILL. Respond with exactly:

```json
{"line":6,"result":"checkpointed","generation":1,"through_line":6,"rows":2}
```

`rows` is the **total** number of published quote rows over all generations, not
just this checkpoint's batch. A checkpoint publishes an atomic prefix: a crash
during publication leaves either the complete old generation or the complete new
one, never a mixture. The new generation may exist even if its response was lost.
An empty publication is still a new generation. Do not duplicate previously
published rows when publishing another checkpoint or continuing after restart.

## Manifest contract

The sole public head is `manifest.json`, a UTF-8 JSON object with exactly:

| Field | Value |
| --- | --- |
| `version` | integer 1 |
| `generation` | positive checkpoint generation |
| `through_line` | logical line number of that checkpoint |
| `t` | its delivery time |
| `config` | exactly `venues`, `symbols`, `stale_ms`, `partition_ms`; identifier arrays sorted in ASCII order |
| `row_count` | total published rows |
| `partitions` | partition objects sorted first by ASCII symbol, then numeric bucket |
| `recovery` | non-empty array of recovery-file descriptors sorted by path |

A partition has exactly `symbol`, `bucket`, `files`. Its non-empty `files` array
is sorted by `first_line`. Each data-file descriptor has exactly `path`, `rows`,
`bytes`, `sha256`, `first_line`, `last_line`. `rows` and `bytes` are positive
integers. First/last are the actual first/last row line numbers. File ranges in
one partition must not overlap. Every published row occurs exactly once across
all referenced data files, and no unpublished row occurs in them. File row
counts must sum to `row_count`. The manifest lists the entire current archive,
not just newly added files. All rows and file ranges are within `through_line`;
all row times are no later than manifest `t`.

A recovery-file descriptor has exactly `path`, `bytes`, `sha256`; bytes may be 0.
Its format is private, but the listed files, public data and manifest must be
sufficient for recovery. Do not depend on unlisted persistent files. You may use
one or several recovery files and may reconstruct state if you prefer. Recovery
files do not have to contain JSON. A data file cannot also be a recovery file.

`bytes` always means exact file length in bytes; `sha256` is the lowercase
64-character hexadecimal SHA-256 of the **actual file bytes**, including newlines.
Public data-file paths begin `data/`; recovery-file paths begin `private/`.
They are relative to the archive root and consist of non-empty ASCII path
components matching `[A-Za-z0-9_-][A-Za-z0-9_.-]*`, separated by `/`. No absolute
paths, `.`/`..` components or symbolic links. Every referenced path is unique.
No other top-level manifest fields are allowed. Manifest whitespace/key order
and names/layout of referenced files are unscored.

Once referenced by the current manifest, a file is immutable while that manifest
is current. You may replace/merge segments in a later generation if the logical
rows stay identical. Old/unreferenced files must not affect reads or recovery;
you may delete them. No concurrent readers or processes are tested. All files,
including temporary and obsolete ones, count towards the storage limit. There
must be no manifest before the first completed publication. Recovery must retain
the valid published head even if terminated again during recovery or cleanup.

## Historical queries

`history` has exactly `type`, `t`, `symbol`, `from_t`, `to_t`, `after_line`, `limit`.
It reads only the latest published generation; it must not expose staged rows or
inspect unreferenced files as committed data. `symbol` must be configured.
`from_t` is an integer in 0–9,000,000,000,000; `to_t` is an integer in
1–9,000,000,000,001, and `from_t < to_t`. `after_line` is an integer in
0–1,000,000; `limit` is an integer in 1–1,000. Schema/range violations are fatal
protocol errors, even when no rows would match.

Select rows of this symbol where `from_t <= row.t < to_t` and
`row.line > after_line`. Return the first `limit` matches in ascending logical-line
order. `t` on the history request is current delivery time and is independent of
the requested historical range. Before the first checkpoint return generation
0 and `[]`. The exact response fields are:

```json
{"line":8,"result":"history","generation":1,"rows":[{"line":3,"t":9,"symbol":"ALPHA","bid":null,"ask":null,"spread":null}]}
```

There is no extra cursor: paginate by using the last returned row's line as the
next `after_line`. Asking again with the same filter returns the same rows unless
a checkpoint publishes more matches. History does not stage another quote row
or refresh books. Its logical line and current time are saved by the next
checkpoint, just like other input events.

## Restart and source continuation

On restart restore the current manifest before reading stdin; emit no startup
response. Continue at `through_line + 1`, with the restored config and delivery
time. The caller reads the public manifest to choose the source suffix. If no
manifest exists, replay the complete source from config. A lost checkpoint reply
can therefore be resolved by inspecting the published generation/prefix.

Do **not** resend committed source lines. This protocol deliberately does not
deduplicate arbitrary source replays or cache historical stdout responses. Feed
duplicates inside the uncommitted source suffix still follow SPEC section 3.
EOF and protocol errors leave the last published checkpoint unchanged. After a
normal exit, a restart also rolls back unpublished work; EOF never auto-publishes.
Power failures, host reboots, manual file corruption and multiple concurrent
writers are excluded. SIGKILL at any processing/publication/recovery step is in
scope. Internal persistence choices remain open; correctness is judged through
responses, public files/manifests and resumed behaviour.
