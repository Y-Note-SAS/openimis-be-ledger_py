from django.core.exceptions import ValidationError
from django.test import TestCase
from hordak.models import Leg
from hordak.models import Transaction
from ledger.models import (
    AnalyticAxis,
    AnalyticValue,
    LegTag,
    AccountingPeriod
)
from ledger.models import Account
from djmoney.money import Money
from core.test_helpers import create_test_interactive_user

class AnalyticAxisTest(TestCase):

    def test_code_unique(self):
        test_user = create_test_interactive_user()
        analytic_axis = AnalyticAxis(
            code="party",
            name="Party"
        )
        analytic_axis.save(username=test_user.username)

        with self.assertRaises(Exception):
            analytic_axis2 = AnalyticAxis(
                code="party",
                name="Duplicate"
            )
            analytic_axis2.save(username=test_user.username)


class AnalyticValueTest(TestCase):

    def setUp(self):
        self.test_user = create_test_interactive_user()

    def test_party_requires_party_type(self):
        axis = AnalyticAxis(
            code="party",
            name="Party"
        )
        axis.save(username=self.test_user.username)

        value = AnalyticValue(
            axis=axis,
            display_name="HF",
            external_reference="1"
        )

        with self.assertRaises(ValidationError):
            value.clean()

    def test_funder_requires_funder_code(self):
        axis = AnalyticAxis(
            code="funder",
            name="Funder"
        )
        axis.save(username=self.test_user.username)

        value = AnalyticValue(
            axis=axis,
            display_name="GIZ",
            external_reference="1"
        )

        with self.assertRaises(ValidationError):
            value.clean()


class LegTagConstraintTest(TestCase):

    def setUp(self):

        self.test_user = create_test_interactive_user()
        self.account = Account.objects.create(
            code="1002",
            full_code="1002",
            name="Cash"
        )
        self.transaction = Transaction.objects.create()

        self.expense_account = Account.objects.create(
            code="6003",
            name="Expense",
            full_code="6003"
        )

        self.open_period = AccountingPeriod(
            name="2026-01",
            status=AccountingPeriod.STATUS_OPEN,
        )
        self.open_period.save(username=self.test_user.username)

    def create_leg(self):

        Leg.objects.create(
            transaction=self.transaction,
            account=self.expense_account,
            amount=Money(-100, "EUR"),
        )
        return Leg.objects.create(
            transaction=self.transaction,
            account=self.account,
            amount=Money(100, "EUR"),
        )

    def test_single_value_per_axis(self):
        """
        One party per leg.
        """

        leg = self.create_leg()

        party_axis = AnalyticAxis(
            code="party",
            name="Party"
        )
        party_axis.save(username=self.test_user.username)

        first = AnalyticValue(
            axis=party_axis,
            party_type="health_facility",
            external_reference="1",
            display_name="HF1",
        )
        first.save(username=self.test_user.username)

        second = AnalyticValue(
            axis=party_axis,
            party_type="health_facility",
            external_reference="2",
            display_name="HF2",
        )
        second.save(username=self.test_user.username)

        legtag = LegTag(
            accounting_period_id=self.open_period.uuid,
            leg=leg,
            analytic_value=first,
        )
        legtag.save(username=self.test_user.username)

        duplicate = LegTag(
            accounting_period_id=self.open_period.uuid,
            leg=leg,
            analytic_value=second,
        )

        with self.assertRaises(ValidationError):
            duplicate.clean()
