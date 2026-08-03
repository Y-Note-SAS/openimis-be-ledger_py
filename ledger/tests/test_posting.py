# ledger/tests/test_posting.py
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from ledger.models import (
AccountingPeriod,
Account,
LedgerEntryMeta,
LedgerJournal,
Sequence,
DeploymentConfiguration,
UnmappedFinancialEvent,
)

from ledger.signals import (
on_claim_valuated,
on_invoice_issued,
on_payroll_disbursed,
on_payment_point_reconciled,
)

from core.test_helpers import create_test_interactive_user
from claim.models import Claim

class PostingSignalsTest(TestCase):

    @classmethod
    def setUpTestData(cls):

        cls.user = create_test_interactive_user()

        cls.account = Account.objects.create(
            code="1008",
            full_code="1008",
            name="Test Account",
        )
        cls.exp_account = Account.objects.create(
            code="1002",
            full_code="1002",
            name="Test Account Expense",
        )

        cls.sequence = Sequence(
            code="GLA",
            name="General Ledger A"
        )
        cls.sequence.save(username=cls.user.username)

        cls.period = AccountingPeriod(
            name="2026-01",
            status=AccountingPeriod.STATUS_OPEN,
        )
        cls.period.save(username=cls.user.username)

        cls.claims_journal = LedgerJournal(
            code="Claims",
            name="Claims",
            sequence_id=cls.sequence,
            default_credit_account_id=cls.account,
            default_debit_account_id=cls.exp_account,
        )
        cls.claims_journal.save(username=cls.user.username)

        cls.sales_journal = LedgerJournal(
            code="Sales",
            name="Sales",
            sequence_id=cls.sequence,
            default_credit_account_id=cls.account,
            default_debit_account_id=cls.exp_account,
        )
        cls.sales_journal.save(username=cls.user.username)

        cls.payroll_journal = LedgerJournal(
            code="Payroll",
            name="Payroll",
            sequence_id=cls.sequence,
            default_credit_account_id=cls.account,
            default_debit_account_id=cls.exp_account,
        )
        cls.payroll_journal.save(username=cls.user.username)

        cls.bank_journal = LedgerJournal(
            code="Bank",
            name="Bank",
            sequence_id=cls.sequence,
            default_credit_account_id=cls.account,
            default_debit_account_id=cls.exp_account,
        )
        cls.bank_journal.save(username=cls.user.username)

        cfg = DeploymentConfiguration(
            currency_code="EUR",
            retained_earnings_account=cls.account,
        )
        cfg.save(username=cls.user.username)

    # ------------------------------------------------------------------
    # T020
    # ------------------------------------------------------------------

    def test_claim_valuated_posts_balanced_entry(self):

        claim = SimpleNamespace(
            uuid="claim-001",
            valuated=Decimal("100"),
            approved=Decimal("100"),
            status=Claim.STATUS_VALUATED
        )

        on_claim_valuated(
            sender=None,
            claim=claim,
            user=self.user,
        )

        self.assertEqual(
            LedgerEntryMeta.objects.count(),
            1,
        )

        meta = LedgerEntryMeta.objects.first()

        self.assertEqual(
            meta.journal.code,
            "Claims",
        )

        balance = sum(
            (
                leg.debit.amount if leg.debit else 0
            ) - (
                leg.credit.amount if leg.credit else 0
            )
            for leg in meta.transaction.legs.all()
        )

        self.assertEqual(
            balance,
            Decimal("0"),
        )

    # ------------------------------------------------------------------
    # T021
    # ------------------------------------------------------------------

    def test_invoice_issued_posts_to_sales_journal(self):

        on_invoice_issued(
            sender=None,
            result={
                "data": {
                    "id": "INV001",
                    "amount_total": "250"
                }
            },
            user=self.user,
        )

        meta = LedgerEntryMeta.objects.get()

        self.assertEqual(
            meta.journal.code,
            "Sales"
        )

    # ------------------------------------------------------------------
    # T022
    # ------------------------------------------------------------------

    def test_payroll_disbursed_posts_entry(self):

        benefits = [
            SimpleNamespace(amount=100),
            SimpleNamespace(amount=50),
        ]

        on_payroll_disbursed(
            sender=None,
            benefits=benefits,
            user=self.user,
            payroll_id="PAY001",
        )

        meta = LedgerEntryMeta.objects.get()

        self.assertEqual(
            meta.journal.code,
            "Payroll"
        )

        self.assertEqual(
            meta.transaction.legs.count(),
            2
        )

    # ------------------------------------------------------------------
    # T023
    # ------------------------------------------------------------------

    def test_payment_point_reconciled_posts_variance(self):

        benefits = [
            SimpleNamespace(amount=100)
        ]

        on_payment_point_reconciled(
            sender=None,
            benefits=benefits,
            variance=Decimal("5"),
            user=self.user,
            payroll_id="PAY001",
        )

        meta = LedgerEntryMeta.objects.get()

        self.assertEqual(
            meta.journal.code,
            "Bank"
        )

        self.assertEqual(
            meta.transaction.legs.count(),
            4
        )

    # ------------------------------------------------------------------
    # T024
    # ------------------------------------------------------------------

    def test_zero_claim_valuation_skipped(self):

        claim = SimpleNamespace(
            uuid="claim-001",
            valuated=Decimal("0"),
            approved=Decimal("0"),
            status=Claim.STATUS_VALUATED
        )

        on_claim_valuated(
            sender=None,
            claim=claim,
            user=self.user,
        )

        self.assertFalse(
            LedgerEntryMeta.objects.exists()
        )

    def test_zero_invoice_skipped(self):

        on_invoice_issued(
            sender=None,
            result={
                "data": {
                    "id": "INV001",
                    "amount_total": "0"
                }
            },
            user=self.user,
        )

        self.assertFalse(
            LedgerEntryMeta.objects.exists()
        )

    def test_zero_payroll_skipped(self):

        benefits = [
            SimpleNamespace(amount=0)
        ]

        on_payroll_disbursed(
            sender=None,
            benefits=benefits,
            user=self.user,
            payroll_id="PAY001",
        )

        self.assertFalse(
            LedgerEntryMeta.objects.exists()
        )

    def test_zero_reconciliation_skipped(self):

        benefits = [
            SimpleNamespace(amount=0)
        ]

        on_payment_point_reconciled(
            sender=None,
            benefits=benefits,
            variance=Decimal("0"),
            user=self.user,
            payroll_id="PAY001",
        )

        self.assertFalse(
            LedgerEntryMeta.objects.exists()
        )

    def test_claim_not_valuated_skipped(self):

        claim = SimpleNamespace(status=Claim.STATUS_PROCESSED)

        on_claim_valuated(
            sender=None,
            claim=claim,
            user=self.user,
        )

        self.assertFalse(
            LedgerEntryMeta.objects.exists()
        )

    # ------------------------------------------------------------------
    # T025
    # ------------------------------------------------------------------

    @patch(
        "ledger.signals.resolve_mapping",
        return_value=None,
    )
    def test_unmapped_claim_valuated_event_is_surfaced(
        self,
        _
    ):

        claim = SimpleNamespace(
            uuid="claim-001",
            valuated=Decimal("100"),
            approved=Decimal("100"),
            status=Claim.STATUS_VALUATED
        )

        on_claim_valuated(
            sender=None,
            claim=claim,
            user=self.user,
            kwargs={"claim": "claim-001"},
        )

        self.assertEqual(
            LedgerEntryMeta.objects.count(),
            0,
        )

        self.assertEqual(
            UnmappedFinancialEvent.objects.count(),
            1,
        )

        event = (
            UnmappedFinancialEvent.objects.first()
        )

        self.assertEqual(
            event.event_type,
            "claim_valuated",
        )
