# Phase 0 Research: Ledger Double-Entry Accounting Module

All items below were resolved from the user-supplied architecture direction plus the survey of existing openIMIS module conventions. No `NEEDS CLARIFICATION` markers remain in the Technical Context.

## 1. Double-entry engine: django-hordak

**Decision**: Use `django-hordak`'s `Account`, `Transaction`, and `Leg` models as the core double-entry primitives, rather than hand-rolling a ledger schema.

**Rationale**: Hordak already provides a hierarchical chart-of-accounts model, a `Transaction`/`Leg` structure matching standard double-entry semantics, and — critically — enforces the debit=credit invariant at the database level via a deferrable Postgres constraint trigger (not just application validation). This directly satisfies FR-003 ("reject any entry whose debit and credit lines do not sum to the same total") at the strongest possible integrity level: even a bug in application code, a raw SQL fix, or a concurrent transaction cannot leave an unbalanced `Transaction` committed, because the trigger fires at commit time (deferred) across all `Leg` rows for that transaction.

**Alternatives considered**:
- Hand-rolled models with only application-level balance validation — rejected because it can't guarantee FR-003/SC-001 ("zero unbalanced entries ever persisted") against every code path, including future maintenance mistakes.
- `django-ledger` — a full-featured alternative accounting package, rejected as heavier than needed (it bundles its own COA/reporting/invoicing UI opinions) where openIMIS needs a lean posting engine to extend with its own journal/party/funder model.

## 2. Extending Hordak with openIMIS-specific concepts

**Decision**: Add four new first-class models — `LedgerJournal`, `AnalyticAxis`/`AnalyticValue`, `AccountingPeriod` — layered around Hordak's `Transaction`/`Leg`, rather than forking or monkey-patching Hordak itself.

**Rationale**:
- `LedgerJournal` (Sales/Purchases/Bank/Miscellaneous, FR-002) is a foreign key on `Transaction`; Hordak has no native journal concept, so this is additive.
- `AnalyticAxis`/`AnalyticValue` implements the **two independent tagging dimensions** (FR-004, FR-005): `AnalyticAxis` is a fixed enum-like table with rows `party` and `funder`; `AnalyticValue` rows point to the tagged real-world entity (Insuree/Family, Health Facility, Payment Point Manager for the `party` axis; a funder/programme record for the `funder` axis) and attach to a `Leg` via a nullable FK pair. Modeling party and funder as two rows on a shared "analytic tag" concept (rather than two hard-coded FK columns) keeps the schema open to additional axes later without a migration, while still letting each `Leg` carry at most one value per axis today (per the Assumptions in spec.md).
- `AccountingPeriod` (FR-007–FR-010) is a date-range model with `status` (open/locked/closed) that every `Transaction` FKs into; period transitions are guarded in `PeriodService`, and closing triggers a generated closing `Transaction` that zeroes P&L accounts into a configured retained-earnings `Account`.

**Alternatives considered**: Storing party/funder as plain FK columns directly on `Leg` — simpler short-term, but rejected because it hard-codes exactly two dimensions into the schema; the axis/value pattern costs one extra join and buys schema flexibility that matches the spec's explicit framing of party and funder as "two separate, independent dimensions."

## 3. Balance reporting: PartyLedgerBalance / AccountBalanceSnapshot

**Decision**: Maintain two denormalized, incrementally-updated tables — `PartyLedgerBalance` (keyed by `AnalyticValue` on the `party` axis) and `AccountBalanceSnapshot` (keyed by `Account` + `AccountingPeriod`) — updated synchronously in the same DB transaction as each `Leg` insert, rather than computing balances by aggregating `Leg` rows on every report request.

**Rationale**: SC-002 requires party/funder reports in under 5 seconds for a typical reporting period. As the `Leg` table grows across years of closed periods, live `SUM()` aggregation would degrade. This is the same problem counsyl/capone's `LedgerBalance` pattern solves for Django-based double-entry ledgers; we reimplement the pattern directly against Hordak's schema (capone is not Hordak-compatible and bundles its own transaction model) rather than taking it as a dependency, keeping the balance-maintenance logic small, auditable, and owned by this module.

**Alternatives considered**: Materialized views refreshed on a schedule — rejected because they would not reflect the most recent postings within SC-002's latency budget without frequent refresh overhead; live aggregation with heavy indexing alone — rejected as insufficient at the scale/scope target (national-scale claim volumes across many periods).

## 4. Leg table partitioning

**Decision**: Apply Postgres declarative range partitioning to the `Leg` table, partitioned by `accounting_period_id` (or the period's date range), created per `AccountingPeriod` as periods are opened.

**Rationale**: Partitioning bounds both write and query costs to the active/recent partitions for day-to-day operation, while historical (closed) partitions can be queried for export/audit without impacting current posting performance — directly serving the "Scale/Scope" target of sustained high-volume posting plus fast reporting (SC-002).

**Alternatives considered**: Unpartitioned table with only composite indexes — viable at smaller deployment scale but rejected as the default given the explicit "high volume" performance requirement in the architecture direction; index-only optimization doesn't bound table bloat the way partitioning does for a permanently-append-only ledger.

## 5. External replication: Odoo/Sage via Celery, dedicated queues, idempotency

**Decision**: Run external-system replication (FR-011–FR-014, FR-013a) as Celery tasks dispatched on a dedicated `ledger.sync.external` RabbitMQ queue (separate from `ledger.export`), with each replication message carrying an idempotency key (derived from the local `Transaction`'s UUID) so retried/duplicate delivery cannot double-post to the external system.

**Rationale**: Using dedicated queues isolates replication throughput/backpressure from export jobs and from the rest of the openIMIS Celery workload, and lets each queue be scaled or paused independently (e.g. if Odoo is down, `ledger.sync.external` backs up without affecting exports). The idempotency key satisfies the "never silently retried with a modified entry" requirement (FR-013) at the transport level: a network-level redelivery of the same message is a no-op on the external system rather than a duplicate or altered posting; genuine corrections are new `Transaction` rows with their own new idempotency keys (FR-014), never re-sends of a mutated payload.

**Alternatives considered**: Synchronous replication inline with the posting request — rejected, would couple ledger posting latency (and openIMIS request latency generally, since posting happens via signal handlers) to third-party system availability; single shared queue for sync+export — rejected per the explicit dedicated-queue direction and because export jobs (large, bursty, at period-close time) would otherwise contend with the latency-sensitive per-entry replication stream.

**Timeout handling**: Per the spec's Clarifications (2026-07-10), a replication attempt that times out (rather than being actively rejected) is retried a bounded number of times (~3) over a short window (a few minutes) using Celery's built-in task retry/backoff; if still unconfirmed, the `ExternalReplicationRecord` is marked `unconfirmed` and surfaced in the manual review queue, distinctly from an explicit `rejected` outcome (FR-013a).

## 6. Manual review queue

**Decision**: `ManualReviewQueueItem` is a queryable model (not just a log) referencing the `ExternalReplicationRecord` that failed, with a `resolved_by_transaction` nullable FK that is only ever set to a *new* `Transaction`, never to an edit of the original.

**Rationale**: Directly implements FR-013/FR-014's "never silently retried with a modified entry; corrections are always new, separate entries" as a schema-level constraint rather than a process convention — the model has no mutable fields that would allow altering the original entry's content, only a pointer to whatever new correcting entry (if any) resolves it.

## 7. Period export: numbering and streaming CSV

**Decision**: Entry numbering (FR-016, FR-017) is implemented via an `ExportSequence` model keyed by `(journal, accounting_period)`, incremented only when a `Transaction` is first included in an export/close pass; re-exporting reuses the stored number. CSV generation (FR-018, FR-019) is a Celery task on the `ledger.export` queue that streams rows via a server-side cursor over the (partitioned) `Leg`/`Transaction` tables rather than materializing the full export in memory.

**Rationale**: Assigning numbers at export/close time (not posting time) is an explicit requirement (FR-016) because entries can post in any order and must be numbered gap-free per journal only once the set is final for that pass; storing the assignment (rather than recomputing) is what makes FR-017's idempotent re-export possible. Cursor-based streaming keeps memory bounded regardless of period size, consistent with the partitioning decision's high-volume assumption.

**Alternatives considered**: Assigning numbers at posting time — explicitly rejected by the spec (numbers must reflect export/close-time finality, not posting order); loading the full period into memory before writing CSV — rejected for the same scale reasons as partitioning.

## 8. Financial event capture: service signals

**Decision**: `ledger` does not get called synchronously by `claim`, `invoice`/`payment`, `payroll`, or payment-point modules. Instead, `ledger/signals/__init__.py` defines `bind_service_signals()`, which binds `ServiceSignalBindType.AFTER` handlers to each source module's existing `@register_service_signal`-decorated service methods (e.g. a claim payment finalization signal), following the exact pattern already used in `openimis-be-individual_py/individual/signals/__init__.py` for binding to `tasks_management`'s signals.

**Rationale**: This is the established openIMIS cross-module integration convention (confirmed via `core.signals.register_service_signal`/`bind_service_signal` and its real usage in the `individual` module), keeps `ledger` decoupled from the internals of claim/payroll/payment-point modules (only their signal contracts), and matches the umbrella project's auto-discovery of `bind_service_signals()` after all modules load.

**Alternatives considered**: Direct method calls from claim/payroll modules into `ledger` — rejected as a tighter, backwards coupling that would require every source module to take `ledger` as a dependency, whereas the signal approach lets `ledger` depend on them instead (the correct dependency direction for an add-on accounting module).
