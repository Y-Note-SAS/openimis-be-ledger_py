# Contract: GraphQL API Surface

Following the openIMIS module convention (`gql_queries.py` / `gql_mutations.py` / `schema.py`), `ledger` exposes the following GraphQL types, queries, and mutations. This is the external interface contract for the module — field-level types are indicative, to be finalized during implementation against openIMIS's `graphene-django` conventions.

## Queries

### `ledgerEntries(journal, accountingPeriod, party, funder, sourceEventType, first, after)`
Paginated list of `LedgerEntryMeta` (+ nested Hordak `Transaction`/`Leg`s), filterable by journal, period, and — independently — by party or funder tag (FR-006). Backing implementation reads from the partitioned `Leg` table filtered by `accounting_period`, not from the balance-snapshot tables (this is the raw ledger view, not the aggregate view below).

### `partyLedgerBalance(analyticValueId, accountingPeriod)`
Returns the running balance for a party (Insuree/Family, Health Facility, or Payment Point Manager) — sourced from `PartyLedgerBalance`, satisfying SC-002's sub-5-second latency by reading the pre-aggregated table rather than summing `Leg` rows live.

### `funderActivityReport(analyticValueId, accountingPeriod)`
Returns aggregated debit/credit/balance totals for a funder, sourced by joining `LegTag`(funder axis) against `AccountBalanceSnapshot`/`PartyLedgerBalance`-equivalent aggregation for the funder axis (mirrors the party query's performance approach).

### `accountingPeriods(status)`
List periods and their lifecycle status (open/locked/closed).

### `manualReviewQueue(status: pending|resolved)`
List `ManualReviewQueueItem`s, for the finance administrator resolution workflow (User Story 4).

### `exportSequences(accountingPeriod, journal)`
Inspect currently-assigned export numbers for a period/journal, including `provisional` flag for still-open periods (User Story 5, Acceptance Scenario 5).

## Mutations

### `openAccountingPeriod(startDate, endDate)`
Creates a new `AccountingPeriod` in `open` status. Rejected if it overlaps an existing period or breaks chronological ordering.

### `lockAccountingPeriod(accountingPeriodId)`
Transitions `open → locked`. Rejected (FR per Edge Cases) if this is not the earliest open period.

### `closeAccountingPeriod(accountingPeriodId)`
Transitions `open|locked → closed`; generates the closing `Transaction` balancing P&L into retained earnings (FR-009). Rejected if this is not the earliest open/locked period, or if a `retained_earnings_account` is not configured (`DeploymentConfiguration`).

### `reopenAccountingPeriod(accountingPeriodId)` *(locked periods only)*
Transitions `locked → open`. Not available for `closed` periods in normal flow (spec.md Assumptions: closed reopening is an exceptional, separately-audited administrative action, out of scope for the standard mutation surface in this iteration).

### `resolveManualReviewItem(reviewItemId, correctingTransactionId, resolutionNote)`
Marks a `ManualReviewQueueItem` resolved by linking to an already-posted new correcting `Transaction` (FR-014) — this mutation does **not** itself create the correcting entry (that happens via the normal posting path so it goes through the same balance/period validation); it only records the linkage and note.

### `exportAccountingPeriod(accountingPeriodId, format: ohada_fec|generic)`
Enqueues `ledger.export.tasks.export_period` (see `contracts/service-signals.md`'s Celery task contract) and returns a job/export reference the caller can poll or receive a completion notification for; the CSV file itself is produced by the async task, not synchronously in the mutation response, per the streamed/cursor-based export design (research.md §7).

### `configureDeployment(operatingMode, externalSystem, currencyCode, retainedEarningsAccountId)`
Admin-only mutation to set `DeploymentConfiguration` (FR-011, FR-020). Switching `operatingMode` does not retroactively replicate or un-replicate historical entries (SC-007: no loss of historical local ledger data; replication starts/stops going forward only).

## Access control

Per the spec's Clarifications (2026-07-10): any user holding the module's general ledger reporting permission may query any party's or funder's data — no additional per-party/per-funder row-level restriction is implemented in this iteration. Mutations that change period state, resolve the review queue, or configure the deployment are restricted to a finance-administrator-level permission, reusing openIMIS's existing RBAC framework (`ledger/apps.py DEFAULT_CFG`), consistent with other openIMIS modules' permission-declaration convention.
