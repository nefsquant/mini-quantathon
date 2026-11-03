# Challenge A — 100 points

Automated groups use the case-based formula in [evaluation guidance](../EVALUATION.md).

| Functional correctness | Points | What is checked |
| --- | ---: | --- |
| Snapshots and independent books | 6 | Full replacement, empty/one-sided books, multiple pairs |
| Incremental updates | 6 | Absolute quantities, deletes, empty deltas, old/duplicate suppression |
| Consolidation | 8 | Best prices, ties, sums, array ordering, crossed/locked markets, null sides |
| Time and freshness | 4 | Boundary ages, ignored-event time, reactivation by valid delta |
| Protocol handling | 4 | Exact output shapes, valid boundaries, fatal schema errors and flushed prefixes |
| Partitioned archive and historical reads | 12 | Exact rows, partitions, immutable files, manifest metadata/hashes, visibility, filtering and pagination |
| **Functional subtotal** | **40** | |
| Resilience | | |
| Adverse feeds | 5 | Gap exclusion/recovery, interleaved pairs, gap/stale priority, ignored events |
| Atomic checkpoint publication | 6 | SIGKILL, complete manifest generations, no lost committed rows or published partial state |
| Restart continuity | 4 | Restored books/times/sequences, source suffixes, orphan files and repeated recovery |
| **Resilience subtotal** | **15** | |

Efficiency: **6 bulk time + 3 historical-read time + 3 recovery time + 3 peak RSS**,
calculated within language under the shared procedure. The bulk workload includes
partition-file writes and manifest publication. Correct archives and recovered
state are required for efficiency eligibility. A pipeline without persistent
storage can earn independent book/quote points, but no efficiency points.
There is no throughput cliff beyond the generous hard case limits.

Review items each receive rating 0, 1 or 2; awarded points = weight × rating / 2,
averaged across two reviewers.

| Code quality and testing | Weight |
| --- | ---: |
| Readable, proportionate code with clear state ownership and appropriate types | 5 |
| Consistent protocol/storage error handling and clear publication boundaries | 4 |
| Meaningful automated book, archive, history and crash/restart tests | 4 |
| Reproducible build/run/test instructions and dependency discipline | 2 |
| **Subtotal** | **15** |
| Technical reasoning in DESIGN.md | |
| Accurate sequencing/freshness, partitioning and checkpoint/recovery explanation | 5 |
| Credible complexity, memory/storage and historical-read analysis | 4 |
| Measured testing/performance evidence and interpretation | 3 |
| Honest trade-offs, limitations and prioritised improvements | 3 |
| **Subtotal** | **15** |

Simple code can earn every review point. Unsupported claims, unnecessary
abstraction and tests that merely repeat the implementation do not demonstrate
engineering judgement. Functional and resilience groups use separate cases;
the same failed case is never counted twice.
