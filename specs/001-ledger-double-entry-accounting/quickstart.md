# Quickstart: Validating the Ledger Module

Prerequisites: an openIMIS backend dev environment with `ledger` installed alongside `openimis-be-core`, `claim` (or another source module wired via `contracts/service-signals.md`), a running Postgres instance (matching the umbrella project's `docker-compose.yml` Postgres service), and Celery workers consuming the `ledger.sync.external` and `ledger.export` queues if replication/export scenarios are being exercised.

## Setup

1. Install the module into the umbrella project's environment (editable install of this repo, or via `openimis.json` in a full umbrella checkout).
2. Run migrations — this includes Hordak's own migrations, this module's migrations, and the declarative-partitioning + balance-trigger migrations described in `research.md` §1/§4.
3. Seed a minimal chart of accounts (`Account` rows) sufficient for at least one asset/bank account, one income account, one expense account, and a `retained_earnings` account; configure `DeploymentConfiguration.retained_earnings_account` to point at it.
4. Create an `AccountingPeriod` covering "today" via the `openAccountingPeriod` mutation (or a management command / fixture) so it is `open`.

## Scenario 1 — Automatic posting (User Story 1)

1. Trigger a claim payment (or invoice/payroll/payment-point event) through the source module's normal flow, or directly fire its underlying service-signal-decorated service method in a test.
2. Query `ledgerEntries(sourceEventType: "claim_payment")` and confirm exactly one new `LedgerEntryMeta` exists, referencing the source event, in the correct `journal`.
3. Confirm its Hordak `Transaction`'s `Leg`s sum to zero (this should be true by construction, enforced by the DB trigger — attempting to violate it in a test, e.g. via a raw unbalanced insert, should raise at commit).
4. Trigger a zero-amount version of the same event and confirm **no** `LedgerEntryMeta` is created (Clarification 2026-07-10).

**Expected outcome**: every non-zero financial event produces exactly one balanced entry; zero-value events produce none.

## Scenario 2 — Party/funder tagging (User Story 2)

1. Post two or more entries with different party tags (e.g. two different Health Facilities) and different funder tags.
2. Query `partyLedgerBalance` for one Health Facility and confirm only its own lines are reflected in the balance.
3. Query `funderActivityReport` for one funder and confirm it aggregates lines regardless of which party is tagged on the same line.

**Expected outcome**: party and funder filtering behave independently, per FR-004/FR-005/FR-006.

## Scenario 3 — Period lifecycle (User Story 3)

1. With the period from Setup step 4 still `open`, post an entry — succeeds.
2. Call `lockAccountingPeriod` — then attempt another posting into that period — must be rejected (FR-008).
3. Call `closeAccountingPeriod` — confirm a closing `Transaction` now exists and `AccountBalanceSnapshot` for P&L accounts is zeroed with the offset landing in the retained earnings account (FR-009).
4. Attempt to post, edit, or delete anything in the now-closed period — must be rejected (FR-010).
5. Open a new period and post a "correction" there referencing the closed period's issue — confirm the closed period's original rows are unchanged.

**Expected outcome**: locked/closed periods block new postings; closing produces a correct closing entry; corrections only ever land in an open period.

## Scenario 4 — External replication + manual review (User Story 4)

1. Configure `DeploymentConfiguration.operatingMode = replicated` with a test/mock adapter standing in for Odoo/Sage.
2. Post an entry the mock adapter accepts — confirm `ExternalReplicationRecord.status == succeeded` with an `external_reference`.
3. Post an entry the mock adapter explicitly rejects — confirm a `ManualReviewQueueItem` is created with the rejection reason, and confirm no automated retry alters the original entry.
4. Post an entry the mock adapter times out on — confirm the bounded retry (~3 attempts over a few minutes) runs, then confirm it lands in the manual review queue as `unconfirmed`, distinct from `rejected` (Clarification 2026-07-10, FR-013a).
5. Resolve a review item via `resolveManualReviewItem`, pointing at a newly-posted correcting entry — confirm the original entry's content is untouched.

**Expected outcome**: replication succeeds/fails/times-out are distinguishable outcomes, and the only path to "fixing" a bad entry is a new entry.

## Scenario 5 — Period export (User Story 5)

1. With Scenario 3's closed period (or a fresh one with a few entries), call `exportAccountingPeriod(format: ohada_fec)`.
2. Once the async export completes, confirm each journal's entries in the CSV carry sequential, gap-free numbers.
3. Re-run the export for the same period with no new entries — confirm identical numbering (FR-017).
4. Repeat with `format: generic` and confirm the reduced field set is present and importable-shaped.
5. Run an export against a still-`open` period and confirm entries are marked `provisional` (via `exportSequences` query) rather than finalized.

**Expected outcome**: export numbering is deterministic, idempotent per unchanged period, and format-correct for both OHADA/FEC and generic consumers.
