# Contract: Service Signal Bindings

Defines the boundary between `ledger` and the source openIMIS modules it listens to, using the existing `register_service_signal` / `bind_service_signal` mechanism (`openimis-be-core_py/core/signals.py`). `ledger` never calls into `claim`, `invoice`/`payment`, `payroll`, or payment-point modules directly; it only binds `AFTER` handlers to their already-registered service signals.

## Inbound signals consumed by `ledger`

`ledger/signals/__init__.py::bind_service_signals()` binds the following, following the pattern in `openimis-be-individual_py/individual/signals/__init__.py`:

| Source module | Signal name (indicative) | Bind type | Handler | Ledger action |
|---|---|---|---|---|
| `claim` | `claim_service.pay_claim` (or equivalent claim-payment finalization signal) | AFTER | `on_claim_payment(sender, **kwargs)` | Post a balanced entry to the appropriate journal (Purchases/Bank depending on flow), tagged with the paying Health Facility as `party` and the claim's funder/programme as `funder`, if resolvable |
| `invoice`/billing module | `invoice_service.create_invoice` (or equivalent) | AFTER | `on_invoice_issued(sender, **kwargs)` | Post a balanced entry to the Sales journal, tagged with the invoiced Health Facility/Insuree as `party` |
| `payroll` module | `payroll_service.disburse` (or equivalent) | AFTER | `on_payroll_disbursed(sender, **kwargs)` | Post a balanced entry (expense + bank/cash movement), tagged with the Payment Point Manager as `party` where applicable |
| payment-point module | `payment_point_service.reconcile` (or equivalent) | AFTER | `on_payment_point_reconciled(sender, **kwargs)` | Post a balanced entry to the Bank journal reflecting the reconciled position (with a variance line if applicable), tagged with the Payment Point Manager as `party` |

**Exact signal names** are resolved at implementation time against each source module's actual `@register_service_signal(...)` decorations (per research.md §8) — this table is the integration contract's shape, not the final string literals.

### Handler contract (all four)

Each handler MUST:
1. Read the amount from the signal payload; if zero, return without creating any ledger records (Clarification 2026-07-10).
2. Resolve the target `AccountingPeriod` from the event's transaction date; if no `open` period covers that date, raise/log and surface the event for manual mapping resolution (FR-022) rather than posting.
3. Resolve the chart-of-accounts mapping for the event type; if missing, surface for manual resolution (FR-022) rather than posting to a default/suspense account.
4. Construct a Hordak `Transaction` + `Leg`s that net to zero, wrapped in a `LedgerEntryMeta` referencing the `LedgerJournal`, `AccountingPeriod`, `source_event_type`, and `source_event_reference`.
5. Attach `LegTag`s for the resolvable `party` and/or `funder` `AnalyticValue`s, independently.
6. Let Hordak's DB trigger be the final authority on balance — the handler does not need to (and should not) duplicate that check in Python beyond constructing correct debit/credit legs.
7. If `DeploymentConfiguration.operating_mode == 'replicated'`, enqueue a replication task (see `contracts/graphql-api.md`'s sibling doc is not applicable here — see Celery task contract below) after the local commit succeeds.

## Outbound: signals `ledger` itself registers

`ledger/services.py` decorates its own mutating operations with `@register_service_signal`, so other modules (e.g. a future reporting or notification module) can react to ledger activity without a direct dependency:

- `ledger_service.post_entry` — fired around `LedgerEntryService.post()`
- `ledger_service.close_period` — fired around `PeriodService.close()`
- `ledger_service.resolve_review_item` — fired around the manual review queue resolution operation

## Celery task contract (replication & export)

Not a Django signal, but the equivalent async boundary for the other two subsystems:

- **`ledger.replication.tasks.replicate_entry(ledger_entry_id, target_system)`** — queue: `ledger.sync.external`. Idempotency key = `f"{ledger_entry.transaction.uuid}:{target_system}"`. On success: creates/updates `ExternalReplicationRecord(status='succeeded')`. On explicit rejection: `status='rejected'`, creates a `ManualReviewQueueItem`. On timeout: Celery retry policy bounded to ~3 attempts over a few minutes (`max_retries=3`, short backoff); if still unresolved, `status='unconfirmed'`, creates a `ManualReviewQueueItem`.
- **`ledger.export.tasks.export_period(accounting_period_id, format)`** — queue: `ledger.export`. `format` ∈ `{ohada_fec, generic}`. Assigns/reuses `ExportSequence` rows per journal (FR-016/FR-017), then streams CSV rows via a server-side DB cursor.
