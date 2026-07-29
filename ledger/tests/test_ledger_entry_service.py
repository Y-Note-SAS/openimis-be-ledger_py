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
    Sequence,
    LegTag,
    AnalyticValue,
    AnalyticAxis
)
from core.test_helpers import create_test_interactive_user
from django.core.exceptions import ValidationError
from hordak.models import Leg

class LedgerEntryServiceTests(TestCase):

    def setUp(self):
        """
        Préparation des données communes utilisées par les tests.
        """

        self.test_user = create_test_interactive_user()

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

        self.sequence = Sequence(
            code="GL",
            name="General Ledger"
        )
        self.sequence.save(username=self.test_user.username)

        self.analytic_axis = AnalyticAxis(
            code="party",
            name="Party1"
        )
        self.analytic_axis.save(username=self.test_user.username)

        self.analytic_axis2 = AnalyticAxis(
            code="funder",
            name="Party2"
        )
        self.analytic_axis2.save(username=self.test_user.username)

        self.analytic = AnalyticValue(
            axis_id=self.analytic_axis.uuid,
            party_type="insuree_family",
            funder_code="Test001",
            external_reference="001",
            display_name="test"
        )
        self.analytic.save(username=self.test_user.username)

        self.analytic2 = AnalyticValue(
            axis_id=self.analytic_axis2.uuid,
            party_type="insuree_family",
            funder_code="Test002",
            external_reference="002",
            display_name="test2"
        )
        self.analytic2.save(username=self.test_user.username)

        # Création du journal
        self.journal = LedgerJournal(
            code="GENERAL",
            name="General Journal",
            sequence_id=self.sequence,
            default_credit_account_id=self.cash_account,
            default_debit_account_id=self.expense_account,
        )
        self.journal.save(username=self.test_user.username)


        # Période ouverte
        self.open_period = AccountingPeriod(
            name="2026-01",
            status=AccountingPeriod.STATUS_OPEN,
        )
        self.open_period.save(username=self.test_user.username)


        # Période verrouillée
        self.locked_period = AccountingPeriod(
            name="2026-02",
            status=AccountingPeriod.STATUS_OPEN,
        )
        self.locked_period.save(username=self.test_user.username)


        # Période fermée
        self.closed_period = AccountingPeriod(
            name="2026-03",
            status=AccountingPeriod.STATUS_OPEN,
        )
        self.closed_period.save(username=self.test_user.username)


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
            user=self.test_user
        )

        self.assertIsNotNone(result.pk)



    def test_locked_period_rejected(self):

        self.locked_period.status = (
            AccountingPeriod.STATUS_LOCKED
        )

        self.locked_period.save(username=self.test_user.username)


        with self.assertRaises(
            ClosedPeriodException
        ):

            LedgerEntryService.post(
                journal=self.journal,
                accounting_period=self.locked_period,
                source_event_type="claim_payment",
                source_event_reference="1",
                legs=self.valid_legs,
                user=self.test_user
            )



    def test_closed_period_rejected(self):

        self.closed_period.status = (
            AccountingPeriod.STATUS_CLOSED
        )

        self.closed_period.save(username=self.test_user.username)


        with self.assertRaises(
            ClosedPeriodException
        ):

            LedgerEntryService.post(
                journal=self.journal,
                accounting_period=self.closed_period,
                source_event_type="claim_payment",
                source_event_reference="1",
                legs=self.valid_legs,
                user=self.test_user
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
                user=self.test_user
            )

    def test_unbalanced_entry_rejected(self):
        with self.assertRaises(ValidationError) as ctx:

            LedgerEntryService.post(
                journal=self.journal,
                accounting_period=self.open_period,
                source_event_type="claim_payment",
                source_event_reference="CLAIM-UNBALANCED",
                legs=[
                    {
                        "account": self.cash_account,
                        "amount": 100,
                    },
                    {
                        "account": self.expense_account,
                        "amount": -50,
                    },
                ],
                user=self.test_user,
            )

        self.assertIn(
            "balanced",
            str(ctx.exception).lower(),
        )


    def test_tags_are_attached_to_legs(self):
        result = LedgerEntryService.post(
            journal=self.journal,
            accounting_period=self.open_period,
            source_event_type="claim_payment",
            source_event_reference="CLAIM-TAGS",
            legs=self.valid_legs,
            tags={
                0: [self.analytic],
                1: [self.analytic2],
            },
            user=self.test_user,
        )

        self.assertIsNotNone(result.pk)

        self.assertEqual(
            LegTag.objects.count(),
            2,
        )

        legs = Leg.objects.filter(
            transaction=result.transaction
        )

        self.assertEqual(
            LegTag.objects.filter(
                leg=legs[0]
            ).count(),
            1,
        )

        self.assertEqual(
            LegTag.objects.filter(
                leg=legs[1]
            ).count(),
            1,
        )
