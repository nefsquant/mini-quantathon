# Sample data and generation

From the repository root, using Python 3.11+ with no dependencies:

```sh
python3 market-data/generate.py --size small --seed 42 > /tmp/market-small.jsonl
python3 market-data/generate.py --size medium --seed 42 > /tmp/market-medium.jsonl
python3 market-data/generate.py --size stress --seed 42 > /tmp/market-stress.jsonl
python3 market-data/generate.py --size stress --scenario clean --depth 1500 --seed 7 > /tmp/market-deep.jsonl
python3 market-data/generate.py --scenario edge --events 300 --seed 9 > /tmp/market-edge.jsonl
python3 market-data/generate.py --scenario storage --events 1000 --seed 9 > /tmp/market-storage.jsonl
python3 market-data/generate.py --self-check
```

`--events` overrides total line count, **including config, checkpoints and history**,
in 1–1,000,000 (storage is capped at 250,000 to bound partition counts).
`--seed` is an integer; default 1. `--size` selects line count and book geometry:

| Size | Lines | Venues × symbols | Full-snapshot levels per side |
| --- | ---: | ---: | ---: |
| small (default) | 100 | 2 × 2 | 4 |
| medium | 10,000 | 4 × 8 | 16 |
| stress | 250,000 | 8 × 16 | 128 |

`--depth` overrides levels per side. The generator rejects depths beyond the
state bounds for the chosen geometry. Normal defaults stay within all challenge
resource/input bounds. Custom combinations of large `--events` and `--depth`
can exceed the 512 MiB input bound; check file size before treating such a file
as a conforming evaluation workload. The clean deep-book command above has a
large state without continually emitting full snapshots.

Scenarios:

- `clean`: initial snapshots for every pair, then in-sequence absolute updates,
  deletions and queries. Useful for separating state/throughput bugs from recovery.
- `mixed` (default): random pair selection, full replacements, duplicate/old
  deltas, gaps, late deltas, obsolete snapshots, equal-sequence recovery and
  51 ms quiet periods. Some books become stale while other pairs recover.
- `edge`: also includes a pre-snapshot delta, empty replacements, unsorted
  crossed books with large quantities, and queries at exactly the age limit
  followed by a query beyond it. Multi-venue sums and zero-age freshness are
  covered explicitly by the fixed boundaries fixture.
- `storage`: mixed feeds plus historical queries immediately before and after
  each checkpoint, requesting recent S00 rows with a five-row limit. It uses
  1,000 ms partitions to cross bucket boundaries in shorter datasets.

Every scenario inserts checkpoints after source-template records 32, 64, 128,
256, and so on up to 16,384, then every 16,384 records. Inserted storage events
count towards `--events` but not those source-template thresholds. This keeps
checkpoint counts under 100 even for the largest supported input. Other scenarios
use 10,000 ms partitions. Checkpoints include empty batches during long initial
snapshot sequences; they do not refresh books.

The stream is cut after exactly the requested number of lines, possibly halfway
through a scenario block. This is a valid EOF, not a protocol error. Prefixes
too short for all initial snapshots leave some books uninitialised. Queries are
not automatically added at EOF, and EOF does **not** publish a checkpoint. On
restart use the manifest's `through_line` to select the source suffix; do not
replay config if a manifest exists. The generators use only synthetic counters and
event templates; they neither maintain solution books nor calculate quotes.

With the same script version, Python version and arguments, output is byte for
byte identical. There is no clock, filesystem-state or hash-order input. To
verify this independently, run the same command to two files and use `cmp`.
`--self-check` performs small generator invariants and repeatability checks,
writes a success message to stderr and no dataset to stdout.

## Included datasets

These input-only files are ready to use; no generation step is required.

| File | Lines | Bytes | Reproduce with generator arguments |
| --- | ---: | ---: | --- |
| `datasets/small.jsonl` | 100 | 9,933 | `--size small --seed 42` |
| `datasets/medium.jsonl` | 10,000 | 1,766,681 | `--size medium --seed 42` |
| `datasets/stress.jsonl` | 25,000 | 7,464,177 | `--size stress --scenario clean --depth 1500 --events 25000 --seed 7` |
| `datasets/storage.jsonl` | 1,000 | 97,322 | `--scenario storage --events 1000 --seed 9` |

The included stress file concentrates on **state size**: 128 pairs initially
hold 384,000 levels. The 250,000-line stress preset in the earlier command
instead exercises more traffic and recovery; it is intentionally generated on
demand to keep the repository compact. Both are within the evaluation bounds.

## Fixed fixtures

| Prefix under `samples/` | Expected exit | Purpose |
| --- | ---: | --- |
| `basic` | 0 | Tied bid, updates, duplicate suppression, freshness boundaries |
| `recovery` | 0 | Initial delta, gap priority, snapshot recovery, crossed/empty books |
| `boundaries` | 0 | 64-bit aggregation, sorting, multiple symbols, one-sided and zero-age books |
| `protocol-error` | 2 | Backwards delivery time; only the valid prefix receives replies |
| `storage` | 0 | Partition boundaries, publication, visibility, history filters and pagination |

Each prefix has `.input.jsonl` and `.expected.jsonl`. Expected files describe
parsed JSON, not a required byte formatting style. For example:

```sh
mkdir /tmp/market-basic-archive
./run.sh --data-dir /tmp/market-basic-archive < /path/to/market-data/samples/basic.input.jsonl > /tmp/actual.jsonl
```

Compare every parsed response against the expected file. A plain textual diff
may differ solely because of key order/whitespace. For the protocol-error fixture
also check exit code 2; the final valid-looking query must never be processed.
Use a fresh empty archive for each independent fixture. The four original feed
fixtures have no checkpoints, so their quote rows remain unpublished and no
manifest may be present at EOF.
Generated datasets have no expected outputs; use your own tests/invariants and
the published rules to assess them. Public seeds are examples only; hidden seeds
and datasets are not included.

## Worked storage and restart fixture

Run `storage.input.jsonl` on a fresh archive and compare `storage.expected.jsonl`.
Its three checkpoints publish these heads:

| Checkpoint logical line | Generation | Manifest `t` | Total rows | Partition contents (quote line numbers) |
| --- | ---: | ---: | ---: | --- |
| 6 | 1 | 10 | 2 | ALPHA/0: 3; ALPHA/1: 5 |
| 12 | 2 | 11 | 4 | ALPHA/0: 3; ALPHA/1: 5, 9; BETA/1: 11 |
| 15 | 3 | 12 | 4 | Same four rows; an empty publication still advances generation |

At EOF the manifest must still have generation 3 and `through_line = 15`.
The uncommitted gap on line 16 and quote on line 17 must not be recovered.
`storage.archive.expected.jsonl` is the union of all **published** rows, sorted
by logical line. It is not a prescribed single output segment: rows must be
separated into the three partitions listed above. Check manifest row counts,
first/last line numbers, exact byte lengths and SHA-256 against the actual files;
file names and recovery bytes depend on your implementation.

Restart on the same directory and send `storage.resume.jsonl` (no config). Compare
with `storage.resume.expected.jsonl`, whose logical lines are 16–20. The resumed
delta must apply at sequence 3: the unpublished gap was rolled back. Its quote
on logical line 17 has a real bid/ask and is published by generation 4 at line
19; the earlier, unpublished null quote with that same logical line must not
appear. The resumed head is generation 4, `through_line = 19`, `t = 13`, five
rows. Then repeat the exercise with SIGKILL after a complete checkpoint reply,
and with termination during publication; before a reply the old or complete new
head is legal. Select the continuation from whichever head was actually published.
There is no executable recovery runner or prescribed checkpoint encoding.
