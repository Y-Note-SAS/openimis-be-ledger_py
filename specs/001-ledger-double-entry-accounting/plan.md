# Implementation Plan: Ledger Double-Entry Accounting Module

**Branch**: `001-ledger-double-entry-accounting` | **Date**: 2026-07-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-ledger-double-entry-accounting/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Build `openimis-be-ledger_py`, a new openIMIS Django module that automatically generates balanced double-entry ledger entries for claim payments, invoices, payroll, and payment-point reconciliation events, using `django-hordak` as the core double-entry engine (Transaction/Leg/Account, DB-enforced balance via a deferrable Postgres trigger). The module extends Hordak with openIMIS-specific concepts — Journals, an independent Analytic (funder) tagging dimension, Accounting Periods with open/locked/closed lifecycle and closing entries, and denormalized balance snapshots for fast party/funder reporting. It supports two deployment modes (local system-of-record vs. real-time replication to Odoo/Sage via Celery, with a manual review queue for failures) and a period-export pipeline that assigns sequential per-journal entry numbers at export/close time and streams OHADA/FEC and generic CSV output. Financial events are captured via openIMIS's existing `register_service_signal` / `bind_service_signal` mechanism, listening to claim, invoice, payroll, and payment-point modules rather than being invoked synchronously by them.

## Technical Context

**Language/Version**: Python 3.10, Django 4.2 (matches the openIMIS umbrella project's current pin, `django~=4.2.22`)

**Primary Dependencies**: `django-hordak` (double-entry ledger engine: Account/Transaction/Leg models + Postgres trigger-enforced balance constraint), `openimis-be-core` (service signal registry, GraphQL test/query helpers, RBAC), `django-db-signals`, `djangorestframework`, `graphene-django` (GraphQL query/mutation surface, per openIMIS module convention), `celery` + `kombu` (async replication/export tasks over the existing RabbitMQ broker), `psycopg2` (Postgres, required for declarative partitioning and the Hordak trigger)

**Storage**: PostgreSQL (shared with the rest of the openIMIS deployment); the `Leg` table (from Hordak, holding every ledger line) is declarative-range-partitioned by accounting period for write/query performance at high transaction volume; two denormalized read-optimized tables (`PartyLedgerBalance`, `AccountBalanceSnapshot`) are maintained incrementally to avoid re-aggregating the full Leg history on every report

**Testing**: Django `TestCase` / `openIMISGraphQLTestCase` (per openIMIS convention), run against the project's standard Postgres docker-compose service; contract-level tests for service-signal handlers (claim/invoice/payroll/payment-point → ledger entry), integration tests for period close/export/replication flows, and a dedicated migration test verifying the Postgres partitioning and balance-trigger behavior

**Target Platform**: Linux server, deployed as an installable Django app inside the openIMIS backend (`openimis-be_py` umbrella project), consistent with all other `openimis-be-*_py` modules

**Project Type**: Single Django app module (backend library) — no standalone frontend in this iteration; GraphQL API surface only, per openIMIS backend module convention

**Performance Goals**: Party/funder sub-ledger and activity reports return in <5s for a typical reporting period (SC-002), sustained via the incremental balance-snapshot tables rather than live aggregation; ledger posting must keep pace with claim/payroll processing throughput without introducing user-visible latency (posting happens asynchronously off the request path via signal handlers)

**Constraints**: Every entry must be DB-enforced balanced (Hordak's deferrable trigger, not just application-level validation); no posting permitted into locked/closed periods; external-system corrections are always new entries, never edits (FR-010, FR-014); export numbering must be idempotent and gap-free per journal (FR-016, FR-017); mono-currency, single chart of accounts per deployment (FR-020)

**Scale/Scope**: National-scale openIMIS deployments processing large daily volumes of claims/invoices/payroll lines; Leg-table partitioning by accounting period and the balance-snapshot pattern (inspired by counsyl/capone's `LedgerBalance`, reimplemented directly on Hordak's schema rather than taken as a dependency) are the specific mechanisms chosen to keep reporting fast as history grows across many closed periods

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The project constitution (`.specify/memory/constitution.md`) is an unpopulated template with no ratified principles for this repository — there are no project-specific gates to evaluate against. No violations to record; this check is a pass by default. If a constitution is ratified later, this plan should be re-checked against it before implementation begins.

## Project Structure

### Documentation (this feature)

```text
specs/001-ledger-double-entry-accounting/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md         # Phase 1 output (/speckit-plan command)
├── quickstart.md         # Phase 1 output (/speckit-plan command)
├── contracts/            # Phase 1 output (/speckit-plan command)
│   ├── graphql-api.md
│   └── service-signals.md
└── tasks.md              # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
openimis-be-ledger_py/                  # this repository — installable Django app "ledger"
├── setup.py                            # package metadata; depends on django-hordak, openimis-be-core, celery
├── ledger/                             # the Django app package (app_label = "ledger")
│   ├── apps.py                         # AppConfig + DEFAULT_CFG (permissions, mode config keys)
│   ├── models.py                       # LedgerJournal, AnalyticAxis, AnalyticValue, AccountingPeriod,
│   │                                    # PartyLedgerBalance, AccountBalanceSnapshot, ExternalReplicationRecord,
│   │                                    # ManualReviewQueueItem, ExportSequence — built on top of hordak's
│   │                                    # Account/Transaction/Leg models (installed as a dependency app)
│   ├── migrations/                     # includes the declarative-partitioning migration for hordak's Leg table
│   │                                    # and the deferrable balance-check trigger migration
│   ├── services.py                     # LedgerEntryService (post/reverse), PeriodService (open/lock/close),
│   │                                    # ExportService — decorated with @register_service_signal
│   ├── signals/
│   │   └── __init__.py                 # bind_service_signals(): listens to claim/invoice/payroll/
│   │                                    # payment-point service signals and posts ledger entries
│   ├── replication/
│   │   ├── base.py                     # ExternalLedgerAdapter interface
│   │   ├── odoo.py, sage.py            # adapter implementations
│   │   └── tasks.py                    # Celery tasks on the "ledger.sync.external" queue, idempotency keys
│   ├── export/
│   │   ├── numbering.py                # per-journal sequential/gap-free numbering at export/close time
│   │   ├── formats.py                  # OHADA/FEC and generic CSV writers (streamed, cursor-based)
│   │   └── tasks.py                    # Celery tasks on the "ledger.export" queue
│   ├── gql_queries.py / gql_mutations.py / schema.py   # GraphQL surface + bind_signals() for mutation hooks
│   ├── admin.py
│   └── tests/
│       ├── test_posting.py             # Story 1: signal → balanced entry
│       ├── test_tagging.py             # Story 2: party/funder independent tagging + reports
│       ├── test_periods.py             # Story 3: open/lock/close, closing entry, immutability
│       ├── test_replication.py         # Story 4: adapter success/reject/timeout → review queue
│       ├── test_export.py              # Story 5: numbering idempotency, OHADA/FEC + generic formats
│       └── test_partitioning.py        # DB-level: partition creation, trigger-enforced balance
└── README.md
```

**Structure Decision**: Single-project structure — this repository is one installable Django app module (`ledger`), following the same layout convention as sibling openIMIS backend modules (`openimis-be-individual_py`, `openimis-be-insuree_py`): `apps.py` + `models.py` + `services.py` + `signals/` + `schema.py` + `tests/` at the top of the app package, registered into the umbrella project via `openimis-be_py/openimis.json`. No separate frontend/backend split is needed since this iteration exposes only a GraphQL/service-signal surface, consistent with other backend-only openIMIS modules.

## Complexity Tracking

*No constitution violations to justify — table intentionally omitted.*
