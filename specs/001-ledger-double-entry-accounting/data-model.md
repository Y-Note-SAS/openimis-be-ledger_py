# Phase 1 Data Model: Ledger Double-Entry Accounting Module

Entities marked **(Hordak)** are provided by the `django-hordak` dependency and referenced, not redefined. Entities marked **(new)** are added by this module. Field lists are conceptual (types/constraints), not a migration.

## Hordak-provided entities (referenced)

### Account (Hordak)
The chart-of-accounts node. Hierarchical (parent/child), typed (asset/liability/income/expense/equity). This module's single deployment-wide chart of accounts (FR-020) lives entirely as `Account` rows; `AccountBalanceSnapshot` (below) references it.

### Transaction (Hordak)
A double-entry transaction: a container for two-or-more `Leg` rows. Hordak enforces (via deferrable Postgres trigger) that all `Leg`s belonging to a `Transaction` net to zero. This module's **Ledger Entry** (spec.md Key Entities) *is* a Hordak `Transaction`, extended via a one-to-one `LedgerEntryMeta` link (below) carrying openIMIS-specific fields.

### Leg (Hordak)
A single debit or credit line within a `Transaction`: references an `Account`, an amount, and a debit/credit sign. This module's **Ledger Entry Line** *is* a Hordak `Leg`, extended via `LegTag` (below) to carry party/funder analytic tags. The `Leg` table is declarative-range-partitioned by `AccountingPeriod` (see research.md §4).

## New entities

### LedgerJournal
Named grouping used to organize and number entries (FR-002).
- `code` (unique, e.g. `SALES`, `PURCHASES`, `BANK`, `MISC`)
- `name`
- Relationship: one `LedgerJournal` has many `LedgerEntryMeta` (below)

### LedgerEntryMeta
One-to-one extension of a Hordak `Transaction`, carrying openIMIS-specific fields not native to Hordak (FR-021).
- `transaction` (OneToOne → Hordak `Transaction`)
- `journal` (FK → `LedgerJournal`)
- `accounting_period` (FK → `AccountingPeriod`)
- `source_event_type` (enum: `claim_payment`, `invoice`, `payroll_disbursement`, `payment_point_reconciliation`, `closing_entry`, `correction`)
- `source_event_reference` (opaque reference/UUID back to the originating openIMIS record — FR-021)
- `posted_at` (timestamp)
- Validation: `accounting_period.status == 'open'` at creation time (FR-008); creation is rejected otherwise.

### AccountingPeriod
Date range with a lifecycle state (FR-007–FR-010).
- `start_date`, `end_date` (non-overlapping across periods, chronologically ordered)
- `status` (enum: `open`, `locked`, `closed`)
- `closing_transaction` (nullable FK → Hordak `Transaction`, set once when the period is closed — the closing entry that zeroes P&L into retained earnings)
- `locked_at`, `closed_at`, `closed_by` (audit fields)
- State transitions: `open → locked` (reversible by an authorized finance administrator, per spec.md Assumptions) `→ closed` (terminal in normal flow); `open → closed` directly is also permitted. Periods MUST be locked/closed in chronological order (spec.md Edge Cases).
- Invariant: no `LedgerEntryMeta` may reference a period whose `status != 'open'`, except the system-generated closing transaction itself, which is written as part of the same close operation that flips the status.

### AnalyticAxis
Fixed small table naming the independent tagging dimensions (FR-004, FR-005).
- `code` (unique: `party`, `funder`)
- `name`

### AnalyticValue
The concrete taggable entity within an axis.
- `axis` (FK → `AnalyticAxis`)
- `party_type` (nullable enum, only set when `axis.code == 'party'`: `insuree_family`, `health_facility`, `payment_point_manager`)
- `funder_code` (nullable, only set when `axis.code == 'funder'`, e.g. `GIZ`, `WORLD_BANK`, or a programme code)
- `external_reference` (points to the underlying openIMIS/domain record — e.g. an Insuree/Family id, Health Facility id, Payment Point Manager id, or a funder/programme record id)
- `display_name`

### LegTag
Attaches zero-or-one `AnalyticValue` per axis to a single Hordak `Leg` (FR-004, FR-005: independent, optional, single-valued per axis per line).
- `leg` (FK → Hordak `Leg`)
- `analytic_value` (FK → `AnalyticValue`)
- Constraint: unique on `(leg, analytic_value.axis)` — a `Leg` can carry at most one `party`-axis tag and at most one `funder`-axis tag, never two values on the same axis.

### PartyLedgerBalance
Denormalized, incrementally-updated running balance per party `AnalyticValue`, updated synchronously with each tagged `Leg` insert (research.md §3; SC-002).
- `analytic_value` (FK → `AnalyticValue` where `axis.code == 'party'`)
- `accounting_period` (FK → `AccountingPeriod`)
- `debit_total`, `credit_total`, `balance` (computed/maintained, not recomputed by aggregation on read)
- `last_updated_leg` (FK → Hordak `Leg`, the last line folded into this balance — for reconciliation/debugging)

### AccountBalanceSnapshot
Denormalized, incrementally-updated running balance per `Account` per `AccountingPeriod` (research.md §3; also the basis for the closing-entry calculation in FR-009).
- `account` (FK → Hordak `Account`)
- `accounting_period` (FK → `AccountingPeriod`)
- `debit_total`, `credit_total`, `balance`

### ExternalReplicationRecord
One row per replication attempt of a `LedgerEntryMeta`/`Transaction` to an external system (FR-011–FR-013a).
- `ledger_entry` (FK → `LedgerEntryMeta`)
- `target_system` (enum: `odoo`, `sage`)
- `idempotency_key` (unique per `(ledger_entry, target_system)`, derived from the `Transaction` UUID — research.md §5)
- `status` (enum: `pending`, `succeeded`, `rejected`, `unconfirmed`)
- `external_reference` (set on `succeeded`)
- `rejection_reason` (set on `rejected`)
- `attempt_count`, `last_attempted_at`
- Invariant: once `status` is `succeeded`, `rejected`, or `unconfirmed`, the record's `ledger_entry` and payload-defining fields are immutable — only a new `ExternalReplicationRecord` (for a new correcting `Transaction`) can follow it (FR-014).

### ManualReviewQueueItem
Rejected or unconfirmed replication attempts awaiting human resolution (FR-013, FR-013a, FR-014).
- `replication_record` (FK → `ExternalReplicationRecord`, must have `status in {rejected, unconfirmed}`)
- `created_at`
- `resolved_at` (nullable)
- `resolved_by_transaction` (nullable FK → Hordak `Transaction` — the *new*, separate correcting entry that resolves this item; never a reference back to an edit of the original)
- `resolution_note` (free text, who/why)
- Invariant: no field on this model or on `ExternalReplicationRecord`/`LedgerEntryMeta`/`Transaction`/`Leg` allows retroactively changing the original entry's debit/credit content — resolution is exclusively via `resolved_by_transaction` pointing at a brand-new `Transaction`.

### ExportSequence
Per-journal, per-period sequential gap-free numbering assigned at export/close time, not posting time (FR-016, FR-017).
- `journal` (FK → `LedgerJournal`)
- `accounting_period` (FK → `AccountingPeriod`)
- `ledger_entry` (FK → `LedgerEntryMeta`, unique together with `journal`+`accounting_period` scope)
- `sequence_number` (assigned once, monotonically increasing per `(journal, accounting_period)`, never reassigned or reused once written — satisfies idempotent re-export)
- `assigned_at`
- `provisional` (boolean — true if assigned while `accounting_period.status == 'open'`, per spec.md Acceptance Scenario 5 of User Story 5; may be superseded by a later export pass while still open)

### DeploymentConfiguration
Per-deployment settings (FR-011, FR-020) — likely a singleton/config-table row per openIMIS convention (`apps.py DEFAULT_CFG`), listed here for completeness of the data model.
- `operating_mode` (enum: `local_only`, `replicated`)
- `external_system` (nullable enum: `odoo`, `sage` — set only when `operating_mode == 'replicated'`)
- `currency_code` (single, deployment-wide — FR-020)
- `retained_earnings_account` (FK → Hordak `Account`, used by the period-closing routine — FR-009)

## Relationships summary

```text
LedgerJournal 1───* LedgerEntryMeta 1───1 Transaction(Hordak) 1───* Leg(Hordak)
AccountingPeriod 1───* LedgerEntryMeta
AccountingPeriod 1───(0..1) Transaction(Hordak)   [closing_transaction]
Leg(Hordak) 1───* LegTag *───1 AnalyticValue *───1 AnalyticAxis
AnalyticValue(party axis) 1───* PartyLedgerBalance
Account(Hordak) 1───* AccountBalanceSnapshot
LedgerEntryMeta 1───* ExternalReplicationRecord 1───(0..1) ManualReviewQueueItem
LedgerJournal + AccountingPeriod + LedgerEntryMeta ─── ExportSequence (one row per entry once numbered)
```

## Key validation rules (cross-cutting)

- **Balance invariant** (FR-003): enforced by Hordak's deferrable Postgres trigger on `Leg`/`Transaction` — not re-implemented in application code, only relied upon.
- **Period-closed immutability** (FR-010): `LedgerEntryMeta`, `Leg`, `LegTag` rows have no application code path for UPDATE/DELETE once `accounting_period.status == 'closed'`; enforced both at the service layer and, for defense in depth, via a Postgres rule/trigger rejecting writes against closed-period partitions.
- **Zero-value events** (Clarification 2026-07-10): the signal handler in `ledger/signals/__init__.py` short-circuits before creating any `Transaction`/`Leg` rows when the source event's amount is zero — no `LedgerEntryMeta` is ever created for it.
- **Chronological period transitions**: `PeriodService.lock()`/`.close()` reject the operation unless the target period is the earliest currently-open (or locked, for close) period.
