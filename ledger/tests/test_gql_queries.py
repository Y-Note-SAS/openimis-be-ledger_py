# from decimal import Decimal

# from django.test import TestCase

# from core.test_helpers import create_test_interactive_user

# from hordak.models import Transaction, Leg
# from djmoney.money import Money
# from ledger.models import (
#     AccountingPeriod,
#     Account,
#     AccountBalanceSnapshot,
#     AnalyticAxis,
#     AnalyticValue,
#     LegTag,
#     DeploymentConfiguration
# )

# from ledger.gql_queries import Query


# class FunderActivityReportQueryTest(TestCase):

#     def setUp(self):
#         self.user = create_test_interactive_user()

#         self.period = AccountingPeriod(
#             name="2026-01",
#             status=AccountingPeriod.STATUS_OPEN,
#         )
#         self.period.save(username=self.user.username)

#         self.other_period = AccountingPeriod(
#             name="2026-02",
#             status=AccountingPeriod.STATUS_OPEN,
#         )
#         self.other_period.save(username=self.user.username)

#         self.funder_axis = AnalyticAxis(
#             code=AnalyticAxis.FUNDER,
#             name="Funder",
#         )
#         self.funder_axis.save(username=self.user.username)

#         self.party_axis = AnalyticAxis(
#             code=AnalyticAxis.PARTY,
#             name="Party",
#         )
#         self.party_axis.save(username=self.user.username)

#         self.funder = AnalyticValue(
#             axis=self.funder_axis,
#             party_type="insuree_family",
#             funder_code="FUND-001",
#             external_reference="FUND-001",
#             display_name="Funder 001",
#         )
#         self.funder.save(username=self.user.username)

#         self.other_funder = AnalyticValue(
#             axis=self.funder_axis,
#             party_type="insuree_family",
#             funder_code="FUND-002",
#             external_reference="FUND-002",
#             display_name="Funder 002",
#         )
#         self.other_funder.save(username=self.user.username)

#         self.party = AnalyticValue(
#             axis=self.party_axis,
#             party_type=AnalyticValue.PARTY_HEALTH_FACILITY,
#             external_reference="HF-001",
#             display_name="HF 001",
#         )
#         self.party.save(username=self.user.username)

#         self.funder_account = Account.objects.create(
#             code="9001",
#             full_code="9001",
#             name="Funder Account",
#         )

#         self.other_account = Account.objects.create(
#             code="9002",
#             full_code="9002",
#             name="Other Account",
#         )

#         self.transaction = Transaction.objects.create()

#         currency_code = DeploymentConfiguration.objects.first().currency_code

#         self.funder_leg = Leg.objects.create(
#             transaction=self.transaction,
#             account=self.funder_account,
#             amount=Money(
#                 100,
#                 currency_code,
#             ),
#         )

#         self.other_leg = Leg.objects.create(
#             transaction=self.transaction,
#             account=self.other_account,
#             amount=Money(
#                 -100,
#                 currency_code,
#             ),
#         )

#     def test_funder_activity_report_returns_account_totals(self):
#         LegTag.objects.create(
#             leg=self.funder_leg,
#             analytic_value=self.funder,
#             accounting_period_id=self.period.uuid,
#         )

#         AccountBalanceSnapshot.objects.create(
#             accounting_period=self.period,
#             account=self.funder_account,
#             debit_amount=Decimal("100"),
#             credit_amount=Decimal("25"),
#             balance_amount=Decimal("75"),
#         )

#         result = Query.resolve_funder_activity_report(
#             None,
#             None,
#             analytic_value_id=self.funder.uuid,
#             accounting_period_id=self.period.uuid,
#         )

#         self.assertEqual(
#             result.debit_amount,
#             Decimal("100"),
#         )

#         self.assertEqual(
#             result.credit_amount,
#             Decimal("25"),
#         )

#         self.assertEqual(
#             result.balance_amount,
#             Decimal("75"),
#         )

#     def test_funder_activity_report_ignores_accounts_without_funder_tag(self):
#         LegTag.objects.create(
#             leg=self.funder_leg,
#             analytic_value=self.funder,
#             accounting_period_id=self.period.uuid,
#         )

#         AccountBalanceSnapshot.objects.create(
#             accounting_period=self.period,
#             account=self.funder_account,
#             debit_amount=Decimal("100"),
#             credit_amount=Decimal("20"),
#             balance_amount=Decimal("80"),
#         )

#         # This account has no LegTag for the requested funder.
#         AccountBalanceSnapshot.objects.create(
#             accounting_period=self.period,
#             account=self.other_account,
#             debit_amount=Decimal("999"),
#             credit_amount=Decimal("999"),
#             balance_amount=Decimal("999"),
#         )

#         result = Query.resolve_funder_activity_report(
#             None,
#             None,
#             analytic_value_id=self.funder.uuid,
#             accounting_period_id=self.period.uuid,
#         )

#         self.assertEqual(
#             result.debit_amount,
#             Decimal("100"),
#         )

#         self.assertEqual(
#             result.credit_amount,
#             Decimal("20"),
#         )

#         self.assertEqual(
#             result.balance_amount,
#             Decimal("80"),
#         )

#     def test_funder_activity_report_ignores_party_tags(self):
#         LegTag.objects.create(
#             leg=self.funder_leg,
#             analytic_value=self.party,
#             accounting_period_id=self.period.uuid,
#         )

#         AccountBalanceSnapshot.objects.create(
#             accounting_period=self.period,
#             account=self.funder_account,
#             debit_amount=Decimal("100"),
#             credit_amount=Decimal("10"),
#             balance_amount=Decimal("90"),
#         )

#         result = Query.resolve_funder_activity_report(
#             None,
#             None,
#             analytic_value_id=self.party.uuid,
#             accounting_period_id=self.period.uuid,
#         )

#         self.assertEqual(
#             result.debit_amount,
#             Decimal("0"),
#         )

#         self.assertEqual(
#             result.credit_amount,
#             Decimal("0"),
#         )

#         self.assertEqual(
#             result.balance_amount,
#             Decimal("0"),
#         )

#     def test_funder_activity_report_is_scoped_to_accounting_period(self):
#         LegTag.objects.create(
#             leg=self.funder_leg,
#             analytic_value=self.funder,
#             accounting_period_id=self.period.uuid,
#         )

#         AccountBalanceSnapshot.objects.create(
#             accounting_period=self.period,
#             account=self.funder_account,
#             debit_amount=Decimal("100"),
#             credit_amount=Decimal("10"),
#             balance_amount=Decimal("90"),
#         )

#         AccountBalanceSnapshot.objects.create(
#             accounting_period=self.other_period,
#             account=self.funder_account,
#             debit_amount=Decimal("500"),
#             credit_amount=Decimal("50"),
#             balance_amount=Decimal("450"),
#         )

#         result = Query.resolve_funder_activity_report(
#             None,
#             None,
#             analytic_value_id=self.funder.uuid,
#             accounting_period_id=self.period.uuid,
#         )

#         self.assertEqual(
#             result.debit_amount,
#             Decimal("100"),
#         )

#         self.assertEqual(
#             result.credit_amount,
#             Decimal("10"),
#         )

#         self.assertEqual(
#             result.balance_amount,
#             Decimal("90"),
#         )

#     def test_funder_activity_report_unknown_funder_returns_zero(self):
#         result = Query.resolve_funder_activity_report(
#             None,
#             None,
#             analytic_value_id=self.other_funder.uuid,
#             accounting_period_id=self.period.uuid,
#         )

#         self.assertEqual(
#             result.debit_amount,
#             0,
#         )

#         self.assertEqual(
#             result.credit_amount,
#             0,
#         )

#         self.assertEqual(
#             result.balance_amount,
#             0,
#         )

#     def test_funder_activity_report_multiple_accounts_are_aggregated(self):
#         second_account = Account.objects.create(
#             code="9003",
#             full_code="9003",
#             name="Second Funder Account",
#         )

#         second_transaction = Transaction.objects.create()

#         second_leg = Leg.objects.create(
#             transaction=second_transaction,
#             account=second_account,
#             amount=200,
#         )

#         LegTag.objects.create(
#             leg=self.funder_leg,
#             analytic_value=self.funder,
#             accounting_period_id=self.period.uuid,
#         )

#         LegTag.objects.create(
#             leg=second_leg,
#             analytic_value=self.funder,
#             accounting_period_id=self.period.uuid,
#         )

#         acc_bal_sn = AccountBalanceSnapshot(
#             accounting_period=self.period,
#             account=self.funder_account,
#             debit_amount=Decimal("100"),
#             credit_amount=Decimal("10"),
#             balance_amount=Decimal("90"),
#         )
#         acc_bal_sn.save(username=self.user.username)

#         acc_bal_sn2 = AccountBalanceSnapshot.objects.create(
#             accounting_period=self.period,
#             account=second_account,
#             debit_amount=Decimal("200"),
#             credit_amount=Decimal("50"),
#             balance_amount=Decimal("150"),
#         )
#         acc_bal_sn2.save(username=self.user.username)

#         result = Query.resolve_funder_activity_report(
#             None,
#             None,
#             analytic_value_id=self.funder.uuid,
#             accounting_period_id=self.period.uuid,
#         )

#         self.assertEqual(
#             result.debit_amount,
#             Decimal("300"),
#         )

#         self.assertEqual(
#             result.credit_amount,
#             Decimal("60"),
#         )

#         self.assertEqual(
#             result.balance_amount,
#             Decimal("240"),
#         )
