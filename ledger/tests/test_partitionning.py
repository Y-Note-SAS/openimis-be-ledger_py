from unittest import skip

from django.db import IntegrityError
from django.test import TestCase

from hordak.models import Transaction
from hordak.models import Leg
from django.db import connection
from ledger.models import Account
from djmoney.money import Money

class BalanceTriggerTest(TestCase):

    def setUp(self):

        self.cash_account = Account.objects.create(
            code="1004",
            name="Cash",
            full_code="1004"
        )


        self.expense_account = Account.objects.create(
            code="6002",
            name="Expense",
            full_code="6002"
        )

    def test_unbalanced_transaction_rejected(self):

        trx = Transaction.objects.create()

        Leg.objects.create(
            transaction=trx,
            account=self.cash_account,
            amount=Money(100, "EUR"),
        )

        Leg.objects.create(
            transaction=trx,
            account=self.expense_account,
            amount=Money(-50, "EUR"),
        )

        with self.assertRaises(Exception):
            # trx.save()
            connection.check_constraints()


class PartitioningTest(TestCase):

    @skip
    def test_partition_exists_for_period(self):

        with connection.cursor() as cursor:

            cursor.execute(
                """
                SELECT tablename
                FROM pg_tables
                WHERE tablename LIKE 'hordak_leg_%'
                """
            )

            rows = cursor.fetchall()

        self.assertTrue(len(rows) > 0)
