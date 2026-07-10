# Feature Specification: Ledger Double-Entry Accounting Module

**Feature Branch**: `001-ledger-double-entry-accounting`

**Created**: 2026-07-10

**Status**: Draft

**Input**: User description: "Build a ledger/accounting module for openIMIS (openimis-be-ledger_py) that records double-entry bookkeeping for all financial flows already handled by the system: claim payments, invoices, payroll, and payment-point reconciliation. Every financial event in openIMIS must generate a balanced double-entry ledger entry (debit = credit), grouped into journals (Sales, Purchases, Bank, Miscellaneous). Each entry line can be tagged with a party (Insuree/Family, Health Facility, Payment Point Manager) for auxiliary sub-ledger tracking, and independently with a funder (e.g. GIZ, World Bank, a programme) for profitability/reporting by funder. Accounting periods (open/locked/closed) must exist; closing a period posts a closing entry balancing P&L into retained earnings and blocks further postings. The system supports two modes per deployment: local ledger as system of record, or real-time replication to an external accounting system (Odoo or Sage) while always keeping a local audit copy. Rejected replicated entries go to a manual review queue, never silently retried with a modified entry — corrections are always new entries. The system exports a period's entries as CSV with sequential gap-free entry numbers assigned per journal at export/closing time, supporting OHADA/FEC-style and generic cloud-accounting formats. Deployments are mono-currency with a single chart of accounts. Out of scope: multi-currency, multi-entity consolidation, budget line-item tracking beyond the funder dimension."

## Clarifications

### Session 2026-07-10

- Q: How should the system handle a financial event whose amount is zero (e.g. a fully waived claim)? → A: Skip posting entirely — no ledger entry created for zero-value events
- Q: When the external accounting system is unreachable (timeout) rather than actively rejecting an entry, how should the system respond? → A: Bounded retry: a few attempts (e.g. 3) over a few minutes, then mark "unconfirmed" if still no response
- Q: Who should be able to view a party's sub-ledger or a funder's activity report? → A: No extra restriction — anyone with general ledger report access can view any party's or funder's data

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Automatic ledger posting from financial events (Priority: P1)

As the finance function of an openIMIS deployment, whenever the system processes a claim payment, invoice, payroll disbursement, or payment-point transaction, a corresponding balanced double-entry ledger entry is automatically created and posted to the correct journal, so that the general ledger always reflects an accurate, complete record of the scheme's financial activity without manual re-entry.

**Why this priority**: Without automatic, reliable posting of every financial event, there is no ledger at all — this is the foundation all other capabilities (party tracking, funder reporting, period close, export) depend on.

**Independent Test**: Can be fully tested by triggering a claim payment (or invoice, payroll run, payment-point transaction) in openIMIS and verifying that a balanced ledger entry (total debits = total credits) appears in the correct journal, referencing the source transaction.

**Acceptance Scenarios**:

1. **Given** an approved claim payment is processed, **When** the payment is finalized, **Then** a balanced ledger entry is created in the appropriate journal with debit and credit lines that net to zero.
2. **Given** an invoice is issued to a health facility, **When** the invoice is recorded, **Then** a balanced entry is posted to the Sales journal reflecting the receivable.
3. **Given** a payroll disbursement is executed, **When** the disbursement completes, **Then** a balanced entry is posted to the appropriate journal reflecting the expense and the cash/bank movement.
4. **Given** a payment-point reconciliation is performed, **When** collected funds are reconciled against expected amounts, **Then** a balanced entry is posted to the Bank journal reflecting the reconciled position (including any variance line).
5. **Given** a source financial event cannot be translated into a balanced entry (e.g. a configuration or mapping gap), **When** the event is processed, **Then** the event is rejected from automatic posting and flagged for manual attention rather than posted unbalanced.

---

### User Story 2 - Party and funder tagging for sub-ledger and profitability reporting (Priority: P2)

As a finance or programme officer, I want each ledger entry line to optionally carry a party tag (Insuree/Family, Health Facility, or Payment Point Manager) and, independently, a funder tag (e.g. GIZ, World Bank, a specific programme), so that I can produce an auxiliary statement of what any given party owes or is owed, and a profitability/activity report broken down by funder.

**Why this priority**: This is the primary reporting value the ledger adds over a simple transaction log; it depends on P1 (entries must exist) but is independently testable and deliverable once postings exist.

**Independent Test**: Can be fully tested by posting entries with various combinations of party and funder tags, then running a sub-ledger report filtered by a specific party and a profitability report filtered by a specific funder, and confirming each shows only the relevant lines and correct balances.

**Acceptance Scenarios**:

1. **Given** ledger entries exist with a mix of party tags, **When** a user requests the sub-ledger for a specific Health Facility, **Then** only lines tagged with that facility are shown, with a running balance.
2. **Given** ledger entries exist with a mix of funder tags, **When** a user requests a report for a specific funder, **Then** only lines tagged with that funder are shown, regardless of which party is tagged on the same line.
3. **Given** a single entry line, **When** it is tagged with both a party and a funder, **Then** both tags are stored and queryable independently of one another.
4. **Given** an entry line has no party tag, funder tag, or neither, **When** reports are generated, **Then** the line is correctly excluded from party/funder-filtered reports but still included in the general ledger totals.

---

### User Story 3 - Accounting period lifecycle and closing (Priority: P2)

As a finance administrator, I want to open, lock, and close accounting periods, so that once a period is closed no further entries can be posted into it and its profit-and-loss position is formally rolled into retained earnings, preserving the integrity of historical reporting.

**Why this priority**: Period control is essential for audit integrity and is a natural evolution once entries are being posted (P1); it is independently testable via period-management operations without needing funder/party tagging.

**Independent Test**: Can be fully tested by opening a period, posting entries, locking it, attempting a new posting (expect rejection), closing it, and verifying a closing entry balances P&L accounts to retained earnings.

**Acceptance Scenarios**:

1. **Given** an open accounting period, **When** a financial event occurs within its date range, **Then** the resulting entry posts successfully into that period.
2. **Given** a locked accounting period, **When** a new entry is attempted for that period, **Then** the posting is rejected with a clear reason.
3. **Given** an open or locked period being closed, **When** the close operation runs, **Then** a closing entry is generated that zeroes out P&L (income/expense) account balances into retained earnings, and the period status becomes closed.
4. **Given** a closed accounting period, **When** any attempt is made to post, edit, or delete an entry within it, **Then** the system rejects the action and preserves the existing entries unchanged.
5. **Given** an error is discovered in a closed period, **When** a correction is needed, **Then** the correction is recorded as a new entry in a currently open period, never as a modification to the closed period's entries.

---

### User Story 4 - External accounting system replication with manual review queue (Priority: P3)

As a deployment operator using an external accounting system (Odoo or Sage) as the system of record, I want every locally posted ledger entry to be replicated to that external system in real time, and any entry the external system rejects to land in a manual review queue rather than being silently retried or altered, so that the local ledger and the external system stay reconcilable and no entry is ever quietly changed.

**Why this priority**: This is an optional, deployment-specific configuration that only some schemes will enable; it depends on entries already being posted locally (P1) and is independently testable in isolation using a test/mock external endpoint.

**Independent Test**: Can be fully tested by configuring replication mode, posting an entry that the external system accepts (verify it appears in both systems), and posting an entry that the external system rejects (verify it appears in the manual review queue and is not silently retried).

**Acceptance Scenarios**:

1. **Given** a deployment is configured in replication mode, **When** a ledger entry is posted locally, **Then** the entry is also sent to the external accounting system and the local copy is retained regardless of outcome.
2. **Given** the external system accepts a replicated entry, **When** the replication completes, **Then** the local entry is marked as successfully replicated with a reference to the external record.
3. **Given** the external system rejects a replicated entry, **When** the rejection is received, **Then** the entry is placed into a manual review queue with the rejection reason, and no automatic modified retry occurs.
4. **Given** an entry sits in the manual review queue, **When** a finance administrator resolves it, **Then** the resolution is achieved by posting a new, separate correcting entry — never by altering the original rejected entry.
5. **Given** a deployment is configured in local-only mode, **When** entries are posted, **Then** no replication attempt is made and the local ledger is the sole system of record.

---

### User Story 5 - Period export for external audit and accounting use (Priority: P3)

As a finance administrator or auditor, I want to export a closed (or closing) period's entries as a flat CSV file with sequential, gap-free entry numbers assigned per journal at export time, in both an OHADA/FEC-compliant format and a generic format usable by common cloud accounting software, so that external auditors or accountants can review or import the period's books.

**Why this priority**: Export is the final step in the reporting lifecycle, valuable once periods can be closed (depends on User Story 3) but independently testable against a fixed set of entries.

**Independent Test**: Can be fully tested by exporting a period with a known set of entries and verifying the CSV contains all entries, correct running debit/credit totals, and per-journal entry numbers that are sequential with no gaps.

**Acceptance Scenarios**:

1. **Given** a period ready for export, **When** the export is run, **Then** each journal's entries receive sequential, gap-free numbers assigned at that moment (not reflecting posting order/time).
2. **Given** an export is run a second time for the same already-numbered period, **When** no new entries have been added, **Then** the previously assigned entry numbers are reused rather than reassigned.
3. **Given** a period is exported in the OHADA/FEC format, **When** the file is produced, **Then** it includes all fields required by that standard (journal code, entry number, date, account, party/auxiliary reference, debit, credit, description, validation date).
4. **Given** a period is exported in the generic format, **When** the file is produced, **Then** it includes the core double-entry fields in a structure importable by common cloud accounting software.
5. **Given** a period that is still open, **When** an export is attempted, **Then** the system allows the export but clearly marks the numbering as provisional, since additional entries could still be posted before the period is closed.

---

### Edge Cases

- What happens when a source financial event is reversed or voided in openIMIS after its ledger entry has already posted (and possibly already replicated or exported)? The reversal must be recorded as a new, offsetting entry, never as a deletion or edit of the original.
- How does the system handle a financial event whose amount is zero (e.g. a fully waived claim)? No ledger entry is created for a zero-value event; the source event's own record in openIMIS remains the audit trail for the waived/zero transaction.
- What happens if the external accounting system is unreachable (timeout) rather than actively rejecting the entry? This is treated distinctly from an explicit rejection: the entry is automatically retried a bounded number of times (e.g. 3 attempts) over a short window (a few minutes), and if it still receives no acknowledgment, it falls into the manual review queue as "unconfirmed," not auto-marked as a rejection.
- How does the system handle two financial events that would post to the same journal/account/party/funder combination on the same day? Each remains a distinct entry; no automatic aggregation occurs.
- What happens if a chart-of-accounts mapping is missing for a given transaction type at the moment it needs to post? The event fails to post automatically and is surfaced for manual mapping/resolution rather than posted to a default or suspense account silently.
- What happens when a period is closed but an in-flight financial event (e.g. a claim payment initiated just before cutoff) completes after the close? The event is posted into the next open period, tagged with its true transaction date, and does not force the closed period to reopen.
- How does the system handle attempts to lock or close a period that is not the earliest currently-open period? Periods must be locked/closed in chronological order to keep retained-earnings roll-forward consistent.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST automatically generate a balanced double-entry ledger entry (sum of debit lines equals sum of credit lines) for every claim payment, invoice, payroll disbursement, and payment-point reconciliation event processed by openIMIS that has a non-zero amount; zero-value events MUST NOT generate a ledger entry.
- **FR-002**: System MUST group every ledger entry into exactly one of the defined journals: Sales, Purchases, Bank, or Miscellaneous.
- **FR-003**: System MUST reject and refuse to post any entry whose debit and credit lines do not sum to the same total.
- **FR-004**: System MUST allow each ledger entry line to optionally be tagged with a single party (Insuree/Family, Health Facility, or Payment Point Manager) for auxiliary sub-ledger tracking.
- **FR-005**: System MUST allow each ledger entry line to independently and optionally be tagged with a single funder (e.g. programme or donor), regardless of whether a party tag is present on the same line.
- **FR-006**: System MUST support querying/reporting ledger activity filtered by party (to show what a given party owes or is owed) and, separately, filtered by funder (for profitability/activity reporting); any user holding general ledger reporting permission MAY view any party's or funder's data — no additional per-party or per-funder access restriction applies in this iteration.
- **FR-007**: System MUST support accounting periods with three states: open, locked, and closed.
- **FR-008**: System MUST reject any attempt to post a new entry into a locked or closed period.
- **FR-009**: System MUST, when a period is closed, generate a closing entry that balances all profit-and-loss (income and expense) account balances into a retained earnings account.
- **FR-010**: System MUST prevent modification or deletion of any entry once its period is closed; corrections MUST be recorded as new entries in a currently open period.
- **FR-011**: System MUST support two configurable operating modes per deployment: (a) local ledger as sole system of record, or (b) real-time replication of every posted entry to an external accounting system (Odoo or Sage).
- **FR-012**: System MUST always retain a local copy of every ledger entry for audit purposes regardless of operating mode.
- **FR-013**: System MUST, when in replication mode, place any entry rejected by the external system into a manual review queue, and MUST NOT automatically modify and resubmit the rejected entry.
- **FR-013a**: System MUST, when a replication attempt times out without a response from the external system, automatically retry a bounded number of times (e.g. 3 attempts) over a short window (a few minutes); if still unconfirmed after that window, the entry MUST be placed into the manual review queue marked "unconfirmed," distinct from an explicit rejection.
- **FR-014**: System MUST ensure that corrections to entries in the manual review queue are made only via new, separate entries, never by altering the original entry's content.
- **FR-015**: System MUST be able to export a given period's entries as a CSV flat file.
- **FR-016**: System MUST assign sequential, gap-free entry numbers per journal at the moment of export or period closing, not at the moment of original posting.
- **FR-017**: System MUST preserve previously assigned export entry numbers on repeat exports of the same period when no new entries have been added since the last numbering pass.
- **FR-018**: System MUST support an OHADA/FEC-compliant CSV export format including journal code, sequential entry number, date, account, auxiliary (party) reference, debit amount, credit amount, description, and validation date.
- **FR-019**: System MUST support a generic CSV export format usable by common cloud accounting software, containing at minimum date, journal, account, debit, credit, and description.
- **FR-020**: System MUST operate against a single, deployment-wide chart of accounts and a single deployment-wide currency; no entry may reference more than one currency.
- **FR-021**: System MUST record, for every ledger entry, a reference back to the originating openIMIS source event (claim payment, invoice, payroll disbursement, or payment-point reconciliation).
- **FR-022**: System MUST surface financial events that cannot be automatically translated into a balanced entry (e.g. missing account mapping) for manual resolution rather than posting them unbalanced or to an unreviewed default account.

### Key Entities *(include if feature involves data)*

- **Ledger Entry**: A balanced double-entry accounting transaction posted to a single journal within a single accounting period; composed of two or more lines whose debit and credit amounts net to zero; references the originating source event and, once exported, carries a sequential per-journal export number.
- **Ledger Entry Line**: A single debit or credit line within a ledger entry; references a chart-of-accounts account; may independently carry a party tag and/or a funder tag.
- **Journal**: A named grouping for ledger entries (Sales, Purchases, Bank, Miscellaneous) used to organize and number entries.
- **Chart of Accounts**: The single, deployment-wide list of accounts (including P&L and balance-sheet accounts, and a retained earnings account) that ledger entry lines post against.
- **Accounting Period**: A date range with a lifecycle state (open, locked, closed) that entries are posted into; closing a period generates a closing entry and blocks further postings.
- **Party**: An auxiliary sub-ledger tag identifying who a ledger line pertains to for owed/receivable tracking — Insuree/Family, Health Facility, or Payment Point Manager.
- **Funder**: An independent reporting tag identifying the programme or funding source (e.g. GIZ, World Bank) associated with a ledger line, used for profitability/activity reporting.
- **External Replication Record**: The record of an attempt to replicate a local ledger entry to an external accounting system (Odoo/Sage), including its outcome (succeeded, rejected, unconfirmed) and any external reference.
- **Manual Review Queue Item**: A rejected or unconfirmed replication attempt awaiting human resolution via a new correcting entry.
- **Deployment Configuration**: The per-deployment settings governing operating mode (local vs. replicated), the target external system, currency, and chart of accounts in use.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of claim payment, invoice, payroll, and payment-point reconciliation events processed by openIMIS produce a balanced ledger entry (debit total equals credit total) with zero unbalanced entries ever persisted.
- **SC-002**: Finance staff can retrieve a party's full sub-ledger (all entries owed/owing) and a funder's full activity report in under 5 seconds for a typical reporting period.
- **SC-003**: Once a period is closed, 0% of historical entries in that period can be altered or deleted through any system pathway, and 100% of subsequent corrections appear as new entries in an open period.
- **SC-004**: In replication mode, 100% of entries rejected by the external accounting system are visible in the manual review queue within 1 minute of rejection, with none silently retried in modified form.
- **SC-005**: A period export produces entry numbers that are sequential and gap-free per journal in 100% of export runs, and re-exporting an unchanged period yields identical numbering.
- **SC-006**: Auditors/accountants can successfully import or review an exported period's CSV file in an external OHADA/FEC-compliant tool or common cloud accounting software without manual reformatting.
- **SC-007**: Deployments can switch between local-only and replicated operating modes via configuration alone, with no loss of historical local ledger data.

## Assumptions

- "Party" and "funder" are each single-valued per ledger entry line (one party, one funder, or none) for this iteration; multi-party or multi-funder splits on a single line are out of scope and would require splitting into additional lines.
- The chart of accounts is configured per deployment (not hard-coded) but is seeded with a reasonable default template reflecting standard openIMIS financial flows; account setup/configuration workflows are assumed to exist or be provided alongside this feature.
- "Locked" periods behave like closed periods for new postings (no new entries) but remain reversible to open by an authorized finance administrator, whereas "closed" periods are terminal and only reversible through an explicit, audited reopening procedure treated as an exceptional administrative action outside normal flow.
- Role-based access control already present in openIMIS is reused to restrict who can post corrections, lock/close periods, resolve the manual review queue, and configure replication mode; this feature defines the required permissions but not a new permission framework.
- Real-time replication targets (Odoo, Sage) expose an integration mechanism (API) capable of accepting a double-entry journal entry and returning a clear accept/reject outcome; this feature assumes such connectivity is configured per deployment.
- Export is available on demand for any period (open or closed), but entry numbering is only guaranteed final/stable once the period is closed; provisional numbering on an open period may be superseded by a later export if new entries are added.
- Reconciliation for payment points is assumed to already produce a determinable reconciled amount (and variance, if any) upstream; this feature is responsible for turning that outcome into a ledger entry, not for performing the reconciliation matching itself.
