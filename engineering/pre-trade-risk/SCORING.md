# Challenge B — 100 points

Automated groups follow [evaluation guidance](../EVALUATION.md).

| Functional correctness | Points | What is checked |
| --- | ---: | --- |
| New-order decisions | 10 | Quantity/notional, exact boundaries, rejection priority and IDs |
| Positions and reservations | 10 | Both position endpoints, both sides, independent symbols, account gross |
| Lifecycle | 10 | Partial/full fills, full cancels, closed orders, exposure after executions |
| Limits, queries and protocol | 10 | Initialisation, reductions, exact sorted state, fatal schema errors |
| **Functional subtotal** | **40** | |
| Resilience | | |
| Durable idempotency | 5 | Original accepted/rejected/query replies, conflicts, semantic equality |
| Crash atomicity | 8 | No lost acknowledgements or duplicated effects, repeated SIGKILL trials |
| Recovery continuity | 2 | Long-history recovery, recovered reservations and subsequent decisions |
| **Resilience subtotal** | **15** | |

Efficiency: **3 bulk elapsed time + 3 acknowledgement latency + 4 peak RSS + 5 recovery elapsed time**,
normalised within language under the shared procedure. Recovery efficiency
requires correct recovered state and duplicate handling, not just a fast startup.
In-memory-only submissions can earn functional points but cannot qualify for B
efficiency points: every benchmark checks persisted state after restart.

Review items each receive rating 0, 1 or 2; awarded points = weight × rating / 2,
averaged across two reviewers.

| Code quality and testing | Weight |
| --- | ---: |
| Readable, proportionate code, clear ownership and appropriate integer types | 5 |
| Safe validation, persistence error paths and transaction boundaries | 4 |
| Meaningful automated risk, retry and crash/restart tests | 4 |
| Reproducible offline build/run/test instructions and dependency discipline | 2 |
| **Subtotal** | **15** |
| Technical reasoning in DESIGN.md | |
| Accurate architecture, risk invariants, commit/acknowledgement and recovery explanation | 5 |
| Credible complexity, memory/storage and durability-cost analysis | 4 |
| Measured tests/performance and crash/restart evidence | 3 |
| Honest trade-offs, known limitations and prioritised improvements | 3 |
| **Subtotal** | **15** |

Tests are judged by what they establish, not their line count. No points are
awarded merely for choosing a fashionable persistence strategy. The resilience
groups use separate cases from functional groups, avoiding double-counted cases.
