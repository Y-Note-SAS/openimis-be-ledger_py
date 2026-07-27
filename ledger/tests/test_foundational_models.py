from django.core.exceptions import ValidationError
from django.test import TestCase
from hordak.models import Leg
from hordak.models import Transaction
from ledger.models import (
    AnalyticAxis,
    AnalyticValue,
    LegTag,
)
from ledger.models import Account
from djmoney.money import Money

class AnalyticAxisTest(TestCase):

    def test_code_unique(self):
        AnalyticAxis.objects.create(
            code="party",
            name="Party"
        )

        with self.assertRaises(Exception):
            AnalyticAxis.objects.create(
                code="party",
                name="Duplicate"
            )


class AnalyticValueTest(TestCase):

    def test_party_requires_party_type(self):
        axis = AnalyticAxis.objects.create(
            code="party",
            name="Party"
        )

        value = AnalyticValue(
            axis=axis,
            display_name="HF",
            external_reference="1"
        )

        with self.assertRaises(ValidationError):
            value.clean()

    def test_funder_requires_funder_code(self):
        axis = AnalyticAxis.objects.create(
            code="funder",
            name="Funder"
        )

        value = AnalyticValue(
            axis=axis,
            display_name="GIZ",
            external_reference="1"
        )

        with self.assertRaises(ValidationError):
            value.clean()


class LegTagConstraintTest(TestCase):

    def setUp(self):

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

        party_axis = AnalyticAxis.objects.create(
            code="party",
            name="Party"
        )

        first = AnalyticValue.objects.create(
            axis=party_axis,
            party_type="health_facility",
            external_reference="1",
            display_name="HF1",
        )

        second = AnalyticValue.objects.create(
            axis=party_axis,
            party_type="health_facility",
            external_reference="2",
            display_name="HF2",
        )

        LegTag.objects.create(
            leg=leg,
            analytic_value=first,
        )

        duplicate = LegTag(
            leg=leg,
            analytic_value=second,
        )

        with self.assertRaises(ValidationError):
            duplicate.clean()
