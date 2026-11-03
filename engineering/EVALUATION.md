# Published evaluation procedure

This document is also the organisers' operating guidance. It contains no hidden
datasets or seeds. All weights, failure rules and resource limits are public.

## Functional and resilience cases

The per-challenge rubrics partition the 55 automated correctness/resilience
points into groups. Each group contains one or more independent cases. A case
passes only if its complete output, exit behaviour and (where applicable)
recovered behaviour match the specification. Its point value is the group's
points divided by the number of cases in that group. Sum the values of passing
cases; do not deduct points twice for a failure. Every submission receives the
same cases and case weights. A group always has at least one case. Publish group
pass counts with results; keep hidden inputs private.

Use fresh processes and fresh state directories between independent cases. A
single-case timeout, crash, excess output or resource breach fails that case,
not every other case. Unless a case intentionally terminates a process or
expects a fatal protocol error, it must exit 0 on EOF. Compare parsed JSON with
exact keys and ordered arrays; reject floats in integer output fields. Expected
fatal-input cases compare the valid prefix, exit code and absence of an output
for the invalid line. Diagnostic wording is unscored.

Cases have a generous **120-second wall-time ceiling per invocation**, 1 GiB
process-tree peak RSS and the input bounds in the specifications. A crash trial's
recovery plus replay must finish within 120 seconds of restart. No minimum
throughput is required to receive functional points. Fixture matching alone is
not enough: use boundary values and combinations of documented behaviours.
Organisers must independently verify expected results before using any case.

## Efficiency: 15 points

Use three fixed, valid benchmark workloads per challenge, within the published
bounds and ceiling. Publish their byte counts, event counts and scenario
descriptions with results, but not the hidden data. Benchmark on the same
machine/core class with no competing contestant processes. Record CPU model,
OS, compiler/interpreter versions and any CPU pinning. Include JSON parsing and
output, launchers and child processes. Exclude build time and generator time.
Use files on local storage for bulk I/O; consume all output. Both challenges use
a local filesystem with normal buffered I/O, not a RAM disk; record its type and
device. Measure persistent-directory peak usage, including temporary files,
against each challenge's 2 GiB limit.

Run each benchmark three times in a fresh process and fresh persistent directory.
Use median wall time and maximum peak process-tree RSS across the three runs.
Do not drop an outlier manually. A benchmark is eligible only if all runs produce
fully correct output within all limits. An ineligible trial earns zero for its
metrics. Eligibility is assessed separately for A bulk/read/recovery and B
bulk/latency/recovery trials; all three repetitions of that trial must pass. No estimated
speed from incorrect output earns credit.
For every B bulk run, restart on its state directory after timing and check a
fresh state query and selected accepted/rejected/query retries. This correctness
check is untimed, but failing it makes that run ineligible for bulk time/memory
points too. In-memory-only engines cannot qualify for B efficiency points.
Every A bulk workload ends with a checkpoint and contains published quote rows.
Validate the manifest's exact schema, partition keys, row contents/order/counts,
file sizes and SHA-256 hashes, then restart and check book state using a fresh
query and appropriate next-sequence updates. These checks are untimed, but
failure makes the bulk time/memory trial ineligible. Pipeline stdout alone does
not establish archive correctness or efficiency eligibility.

For each metric, let `best` be the lowest eligible measurement among submissions
in the **same language**, and `value` the submission's measurement. Its metric
fraction is `min(1, max(best, epsilon) / max(value, epsilon))`, with epsilon =
0.000000001 seconds for time and 1 byte for memory. A sole eligible submission
in a language gets 1.
If none are eligible, all get zero. Use equal-weight averages across the three
workloads. C, C++, Rust, Go and Python are separate language groups. A language
group's score is a within-group comparison, not a claim of equal absolute speed;
publish absolute measurements too. This prevents language choice alone deciding
the efficiency score while retaining a common functional time ceiling.

- A: 6 points × average bulk-time fraction + 3 × average historical-read-time
  fraction + 3 × average recovery-time fraction + 3 × average memory fraction.
  Bulk time is end-to-end elapsed time, including archive publication, process
  start-up and EOF shutdown. In-memory-only pipelines earn no efficiency points.
- B: 3 points × average bulk-time fraction + 3 × average acknowledgement-latency
  fraction + 4 × average memory fraction + 5 ×
  average recovery-time fraction. Bulk time includes persistence and shutdown.
  For recovery time, prepare identical acknowledged histories for each team,
  kill the idle engine after the final complete acknowledgement, then start it
  with that state and send a fresh query. Measure from process launch to the
  complete durable query response. Check the recovered state and duplicate
  responses before eligibility. Repeat three times using independently prepared
  directories; use the median. Preparation is untimed. The three histories have
  the event counts of the three bulk workloads. They use distinct fresh query IDs.

For A historical reads, prepare the complete published archive of each bulk
workload outside timing. In each trial, launch on an independent copy and send
100 fixed `history` requests, one outstanding at a time, then EOF. Include narrow
and wide time ranges, early and recent buckets, several symbols and pagination;
all requests and returned rows remain within the history bounds. Measure elapsed
time from launch to normal EOF shutdown. Repeat three times on independent copies
and use median time. Check every response and manifest/reference integrity.
Reading fewer files is an engineering opportunity, not an undisclosed rule.

For A recovery time, prepare the same published histories outside timing. Kill
the idle process after its final checkpoint acknowledgement, restart and send
one fresh `query` with `t` equal to manifest `t`. Measure launch to its complete
response. Validate the restored quote/status/sequence, historical reads and a
subsequent book update before eligibility. Repeat three times on independently
prepared directories and use median recovery time. Recovery must not need the
original source input file. Recovered quote responses are provisional until a
later checkpoint, as in the A contract; this timing does not require them durable.

For B acknowledgement latency, run the first `min(10000, line_count)` requests
of each bulk workload interactively in a fresh directory, one request outstanding
at a time. For each request measure monotonic elapsed time from immediately
before writing its line to receipt of its complete response. Include pipe I/O
and durable processing; exclude process startup before the first write. Sort the
N samples and use sample `ceil(0.95 * N)` (1-based) as p95. Repeat three times
with fresh directories; the metric is the median p95. Validate every reply and
recovered prefix state; use the same ceiling/resources and within-language
fraction formula as the other metrics. No fixed latency threshold is imposed.
Run this from the same local evaluator process/machine configuration for every
team. Publish p95 in milliseconds alongside bulk time, RSS and recovery time.

Round only the final challenge score to two decimal places. A runtime or storage
failure can make a particular benchmark ineligible, but does not erase review or
functional points earned elsewhere.

## Review: 30 points

Two reviewers independently award each item in the challenge rubric: 0 for
absent/incorrect evidence, 1 for partial evidence and 2 for clear, convincing
evidence. Multiply each item's published weight by `rating / 2`; average the two
reviewers' scores. Review source, tests and `DESIGN.md`, not code volume. Reviewers
must note evidence for each rating and reconcile factual disagreements before
publication. A short readable implementation can earn full marks. No live pitch
or additional explanation is required.

## Crash and error trials for A

Use one request outstanding at a time. Kill the process group with SIGKILL during
feed processing, publication or recovery, and after complete checkpoint replies.
Inspect `manifest.json`: if absent, restart from config; otherwise resume the
source strictly after `through_line`. A publication interrupted before its reply
may have installed either complete generation. Any received checkpoint reply
must be present after restart, unless a later complete generation supersedes it.
Validate all referenced file hashes/counts/rows and restore books before testing
the next source suffix. Earlier non-checkpoint replies do not promise durability.

Exercise several checkpoints in the same partition, multiple symbols/buckets,
empty publications, stale/gapped books, unpublished rows at EOF and abandoned
staging files left by killed processes. Test history invisibility before commit
and no duplicated rows after restart. Only files naturally left by interrupted
execution may be present; do not invent external corruption. Kill again during
recovery to check that cleanup never destroys the valid published generation.
Do not require a particular checkpoint format or segment-compaction strategy.

## Crash and error trials for B

Use one request outstanding at a time over pipes. A complete newline-terminated
response is an acknowledgement; a truncated response is discarded. Exercise
termination both during request processing and after acknowledgements, including
new orders, fills, cancellations, rejected requests, queries and limit changes.
Use SIGKILL on the entire process group, not a graceful signal. Restart on the
same directory. Replay the possibly unacknowledged request with the same ID and
payload; compare all previously acknowledged retries to their original responses,
then use a fresh query to inspect current state. A transaction that committed
before its acknowledgement was observed is legal; duplicate execution is not.
Run repeated crashes/restarts within the same trial. Never inject a power failure,
edit a state file, or corrupt the filesystem: those are outside the contract.

For output-in-flight trials, retain only complete lines observed before the kill.
Do not expect the same original response for an event-ID conflict as for the
original event; conflicts are deliberately different requests. Disk-limit failure
tests must leave previously acknowledged history recoverable; arbitrary device
faults are excluded. Do not impose an undocumented persistence architecture.

## Overall results

Team score = A + B, with an unsubmitted challenge scoring zero. Ties are broken
by combined functional/resilience points, then combined review points, then shared
placing. Do not use raw cross-language speed as a tie-break. Return group scores,
review notes and benchmark measurements to teams.
