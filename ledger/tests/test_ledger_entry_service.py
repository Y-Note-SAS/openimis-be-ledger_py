from django.test import TestCase

from ledger.services import (
    LedgerEntryService,
    ClosedPeriodException,
    MissingAccountMappingException,
)

from ledger.models import (
    AccountingPeriod,
    Account,
    LedgerJournal,
    Sequence
)

class LedgerEntryServiceTests(TestCase):

    def setUp(self):
        """
        Préparation des données communes utilisées par les tests.
        """

        # Création des comptes
        self.cash_account = Account.objects.create(
            code="1003",
            full_code="1003",
            name="Cash Account",
        )

        self.expense_account = Account.objects.create(
            code="6001",
            full_code="6001",
            name="Expense Account",
        )

        self.sequence = Sequence.objects.create(
            code="GL",
            name="General Ledger"
        )


        # Création du journal
        self.journal = LedgerJournal.objects.create(
            code="GENERAL",
            name="General Journal",
            sequence_id=self.sequence,
            default_credit_account_id=self.cash_account,
            default_debit_account_id=self.expense_account,
        )


        # Période ouverte
        self.open_period = AccountingPeriod.objects.create(
            name="2026-01",
            status=AccountingPeriod.STATUS_OPEN,
        )


        # Période verrouillée
        self.locked_period = AccountingPeriod.objects.create(
            name="2026-02",
            status=AccountingPeriod.STATUS_OPEN,
        )


        # Période fermée
        self.closed_period = AccountingPeriod.objects.create(
            name="2026-03",
            status=AccountingPeriod.STATUS_OPEN,
        )


        # Legs équilibrés réutilisables
        self.valid_legs = [
            {
                "account": self.cash_account,
                "amount": 100,
            },
            {
                "account": self.expense_account,
                "amount": -100,
            },
        ]



    def test_successful_balanced_post(self):

        result = LedgerEntryService.post(
            journal=self.journal,
            accounting_period=self.open_period,
            source_event_type="claim_payment",
            source_event_reference="CLAIM-1",
            legs=self.valid_legs,
        )

        self.assertIsNotNone(result.pk)



    def test_locked_period_rejected(self):

        self.locked_period.status = (
            AccountingPeriod.STATUS_LOCKED
        )

        self.locked_period.save()


        with self.assertRaises(
            ClosedPeriodException
        ):

            LedgerEntryService.post(
                journal=self.journal,
                accounting_period=self.locked_period,
                source_event_type="claim_payment",
                source_event_reference="1",
                legs=self.valid_legs,
            )



    def test_closed_period_rejected(self):

        self.closed_period.status = (
            AccountingPeriod.STATUS_CLOSED
        )

        self.closed_period.save()


        with self.assertRaises(
            ClosedPeriodException
        ):

            LedgerEntryService.post(
                journal=self.journal,
                accounting_period=self.closed_period,
                source_event_type="claim_payment",
                source_event_reference="1",
                legs=self.valid_legs,
            )


    def test_missing_account_mapping(self):

        with self.assertRaises(
            MissingAccountMappingException
        ):

            LedgerEntryService.post(
                journal=self.journal,
                accounting_period=self.open_period,
                source_event_type="claim_payment",
                source_event_reference="1",
                legs=[
                    {
                        "account": None,
                        "amount": 100,
                    },
                    {
                        "account": self.cash_account,
                        "amount": -100,
                    },
                ],
            )
