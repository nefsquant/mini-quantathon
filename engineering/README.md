# NEFS Quant Warm-Up Competition

A two-hour, team-based quantitative finance competition at the University of
Nottingham. Build one or both independent systems from scratch. You are judged
on correct behaviour, engineering decisions and the evidence behind them.

| Challenge | Languages | Main problem |
| --- | --- | --- |
| [A: Market Data Pipeline](market-data/SPEC.md) | Python or Go | Consolidate imperfect feeds and publish a recoverable partitioned quote archive |
| [B: Pre-Trade Risk Engine](pre-trade-risk/SPEC.md) | C, C++ or Rust | Make stateful risk decisions that survive process termination |

Each challenge is worth 100 points; the team total is the sum, out of 200.
There is no bonus for attempting both. A carefully tested single challenge can
outscore two unreliable implementations. Partial implementations receive credit
for the published behaviours they pass. Read the scoring rubrics before choosing
where to spend your time.

## Rules and timing

- The implementation window is exactly 120 minutes from the announced start.
  All submitted changes must be saved by the deadline.
- Work with your registered team. Do not exchange implementations with other teams.
- LLMs, documentation, search engines, IDEs and development tools are allowed.
  You remain responsible for understanding and testing your submission. Summarise
  substantial generated or adapted code and its source in your `DESIGN.md`.
- Standard libraries and third-party libraries are allowed. Respect licences and
  declare and vendor any dependencies needed at runtime or build time. Evaluation
  has no network access. Do not submit an existing complete solution to either
  challenge as your own implementation.
- Do not modify the specifications or expected results to match your program.
  No database, cloud service, container daemon or external process is required.
- The published rules are the complete behavioural contract. Hidden tests combine
  these rules at greater scale; they introduce no new event types or semantics.

Both problems deliberately leave optimisation opportunities. Aim first for a
working end-to-end submission, then test edge conditions, recovery and scale.
You choose the algorithms, data structures, persistence format and architecture.
The repository contains no implementation or executable judge.

## What is included

Each challenge directory contains `SPEC.md`, `SCORING.md`, `DATA.md`, a
standard-library-only Python input generator, and `samples/*.input.jsonl` with
matching `*.expected.jsonl`. Each also includes ready-to-use small, medium and
stress-oriented inputs under `datasets/`, with reproduction commands in `DATA.md`.
The small fixtures are hand-worked examples, not complete test suites. Generated
workloads have **no supplied output oracle**.
Generators do not implement the systems or compute their decisions.
Challenge A also has a required [storage contract](market-data/STORAGE.md)
covering partitions, manifests, checkpoints and historical reads.

Run generators using Python 3.11 or newer; each has `--help`. They write only
JSON Lines to stdout. Keep large generated datasets outside your submission.

## Submission and execution

Submit a repository/archive containing a `submission/` directory. Within it,
include `market-data/`, `pre-trade-risk/`, or both. Each submitted challenge must
contain:

- Source code and a `DESIGN.md` of **approximately 750 words** (500–750 is a
  useful target; a small diagram or table is welcome).
- Executable `build.sh` and `run.sh` launchers. Shell launchers are part of your
  implementation, not supplied starter code. `build.sh` takes no arguments and
  succeeds offline; for Python it can simply validate the environment.
- Any dependency files, vendored dependencies and a brief `README.md` with exact
  build, run and test commands. Include your own tests and explain how to run them.

The evaluator changes into the submitted challenge directory and runs
`./build.sh` once, then invokes `./run.sh` as specified in that challenge.
Launchers must preserve exit codes and signals (for example, by replacing the
launcher process with the engine). Builds must finish within five minutes.
No root access, network access or interactive setup is available.

The supported baseline is Linux x86-64, Ubuntu 24.04, one allocated CPU core,
1 GiB process-tree RSS, Python 3.12, Go 1.22, GCC/G++ 13 (C17/C++20), and Rust
1.75 (edition 2021). Choose one permitted language for each engine; scripts may
build or launch it. Newer language features require a compatible vendored
toolchain within the same build/resource limits. Portability beyond this
environment is welcome but unscored. Do not rely on the host's time zone,
locale, wall clock, hash iteration order or internet access.

For challenge A:

```text
./run.sh --data-dir /absolute/path/to/team-archive < input.jsonl > actual.jsonl
```

For challenge B:

```text
./run.sh --state-dir /absolute/path/to/team-state < input.jsonl > actual.jsonl
```

Output comparison parses JSON: object key order and insignificant whitespace do
not matter; array order, JSON types, integer values and the exact set of keys do.
No extra stdout is allowed. Diagnostics belong on stderr. All files use UTF-8.

`DESIGN.md` must explain architecture and state ownership; main data structures;
time and space complexity; correctness invariants; important trade-offs; testing
and measurements (including environment); known limitations; and the next
improvement you would make. For B, explain the acknowledgement/commit boundary,
duplicate handling and recovery evidence. For A, explain sequencing, freshness
consolidation, partition layout, manifest publication, historical reads and
checkpoint recovery. Honest incomplete work is more useful than unsupported claims.

Do not commit secrets, generated build products or large datasets. Submit the
repository/archive through the competition's announced submission channel by the
deadline. If no upload service is available, hand the organisers an archive named
`TEAM_NAME.zip` containing `submission/`; this is the offline fallback. Include
team name and member names in `submission/README.md`. Organisers will record its
receipt time. No post-deadline changes are used for scoring.

## Assessment

Each [A rubric](market-data/SCORING.md) and [B rubric](pre-trade-risk/SCORING.md)
allocates 40 points to functional correctness, 15 to resilience, 15 to measured
efficiency, 15 to code quality/testing and 15 to technical reasoning. The same
limits apply to every language; performance is normalised within each submitted
language. Durability and correctness requirements are identical across languages.
See [evaluation guidance](EVALUATION.md) for measurement and review procedures.
