from decimal import Decimal

from django.test import TestCase

from core.test_helpers import create_test_interactive_user

from hordak.models import Transaction, Leg
from djmoney.money import Money
from ledger.models import (
    AccountingPeriod,
    Account,
    AccountBalanceSnapshot,
    AnalyticAxis,
    AnalyticValue,
    LegTag,
    DeploymentConfiguration
)
from djmoney.money import Money
from ledger.gql_queries import Query


class FunderActivityReportQueryTest(TestCase):

    def setUp(self):
        self.user = create_test_interactive_user()

        self.account = Account.objects.create(
            code="1003",
            full_code="1003",
            name="Cash Account",
        )

        config = DeploymentConfiguration(
            currency_code="EUR",
            retained_earnings_account=self.account
        )
        config.save(username=self.user.username)

        self.period = AccountingPeriod(
            name="2026-01",
            status=AccountingPeriod.STATUS_OPEN,
        )
        self.period.save(username=self.user.username)

        self.other_period = AccountingPeriod(
            name="2026-02",
            status=AccountingPeriod.STATUS_OPEN,
        )
        self.other_period.save(username=self.user.username)

        self.funder_axis = AnalyticAxis(
            code=AnalyticAxis.FUNDER,
            name="Funder",
        )
        self.funder_axis.save(username=self.user.username)

        self.party_axis = AnalyticAxis(
            code=AnalyticAxis.PARTY,
            name="Party",
        )
        self.party_axis.save(username=self.user.username)

        self.funder = AnalyticValue(
            axis=self.funder_axis,
            party_type="insuree_family",
            funder_code="FUND-001",
            external_reference="FUND-001",
            display_name="Funder 001",
        )
        self.funder.save(username=self.user.username)

        self.other_funder = AnalyticValue(
            axis=self.funder_axis,
            party_type="insuree_family",
            funder_code="FUND-002",
            external_reference="FUND-002",
            display_name="Funder 002",
        )
        self.other_funder.save(username=self.user.username)

        self.party = AnalyticValue(
            axis=self.party_axis,
            party_type=AnalyticValue.PARTY_HEALTH_FACILITY,
            external_reference="HF-001",
            display_name="HF 001",
        )
        self.party.save(username=self.user.username)

        self.funder_account = Account.objects.create(
            code="9001",
            full_code="9001",
            name="Funder Account",
        )

        self.other_account = Account.objects.create(
            code="9002",
            full_code="9002",
            name="Other Account",
        )

        self.transaction = Transaction.objects.create()

        self.currency_code = DeploymentConfiguration.objects.first().currency_code

        self.funder_leg = Leg.objects.create(
            transaction=self.transaction,
            account=self.funder_account,
            amount=Money(
                100,
                self.currency_code,
            ),
        )

        self.other_leg = Leg.objects.create(
            transaction=self.transaction,
            account=self.other_account,
            amount=Money(
                -100,
                self.currency_code,
            ),
        )

    def test_funder_activity_report_returns_account_totals(self):
        legtag = LegTag(
            leg=self.funder_leg,
            analytic_value=self.funder,
            accounting_period_id=self.period.uuid,
        )
        legtag.save(username=self.user.username)

        bsn = AccountBalanceSnapshot(
            accounting_period=self.period,
            account=self.funder_account,
            debit_amount=Decimal("100"),
            credit_amount=Decimal("25"),
            balance_amount=Decimal("75"),
        )
        bsn.save(username=self.user.username)

        result = Query.resolve_funder_activity_report(
            None,
            None,
            analytic_value_id=self.funder.uuid,
            accounting_period_id=self.period.uuid,
        )

        self.assertEqual(
            result.debit_amount,
            Decimal("100"),
        )

        self.assertEqual(
            result.credit_amount,
            Decimal("25"),
        )

        self.assertEqual(
            result.balance_amount,
            Decimal("75"),
        )

    def test_funder_activity_report_ignores_accounts_without_funder_tag(self):
        legtag = LegTag(
            leg=self.funder_leg,
            analytic_value=self.funder,
            accounting_period_id=self.period.uuid,
        )
        legtag.save(username=self.user.username)

        bsn = AccountBalanceSnapshot(
            accounting_period=self.period,
            account=self.funder_account,
            debit_amount=Decimal("100"),
            credit_amount=Decimal("20"),
            balance_amount=Decimal("80"),
        )
        bsn.save(username=self.user.username)

        # This account has no LegTag for the requested funder.
        bsn = AccountBalanceSnapshot(
            accounting_period=self.period,
            account=self.other_account,
            debit_amount=Decimal("999"),
            credit_amount=Decimal("999"),
            balance_amount=Decimal("999"),
        )
        bsn.save(username=self.user.username)

        result = Query.resolve_funder_activity_report(
            None,
            None,
            analytic_value_id=self.funder.uuid,
            accounting_period_id=self.period.uuid,
        )

        self.assertEqual(
            result.debit_amount,
            Decimal("100"),
        )

        self.assertEqual(
            result.credit_amount,
            Decimal("20"),
        )

        self.assertEqual(
            result.balance_amount,
            Decimal("80"),
        )

    def test_funder_activity_report_ignores_party_tags(self):
        legtag = LegTag(
            leg=self.funder_leg,
            analytic_value=self.party,
            accounting_period_id=self.period.uuid,
        )
        legtag.save(username=self.user.username)

        bsn = AccountBalanceSnapshot(
            accounting_period=self.period,
            account=self.funder_account,
            debit_amount=Decimal("100"),
            credit_amount=Decimal("10"),
            balance_amount=Decimal("90"),
        )
        bsn.save(username=self.user.username)

        result = Query.resolve_funder_activity_report(
            None,
            None,
            analytic_value_id=self.party.uuid,
            accounting_period_id=self.period.uuid,
        )

        self.assertEqual(
            result.debit_amount,
            Decimal("0"),
        )

        self.assertEqual(
            result.credit_amount,
            Decimal("0"),
        )

        self.assertEqual(
            result.balance_amount,
            Decimal("0"),
        )

    def test_funder_activity_report_is_scoped_to_accounting_period(self):
        legtag = LegTag(
            leg=self.funder_leg,
            analytic_value=self.funder,
            accounting_period_id=self.period.uuid,
        )
        legtag.save(username=self.user.username)

        bsn = AccountBalanceSnapshot(
            accounting_period=self.period,
            account=self.funder_account,
            debit_amount=Decimal("100"),
            credit_amount=Decimal("10"),
            balance_amount=Decimal("90"),
        )
        bsn.save(username=self.user.username)

        bsn = AccountBalanceSnapshot(
            accounting_period=self.other_period,
            account=self.funder_account,
            debit_amount=Decimal("500"),
            credit_amount=Decimal("50"),
            balance_amount=Decimal("450"),
        )
        bsn.save(username=self.user.username)

        result = Query.resolve_funder_activity_report(
            None,
            None,
            analytic_value_id=self.funder.uuid,
            accounting_period_id=self.period.uuid,
        )

        self.assertEqual(
            result.debit_amount,
            Decimal("100"),
        )

        self.assertEqual(
            result.credit_amount,
            Decimal("10"),
        )

        self.assertEqual(
            result.balance_amount,
            Decimal("90"),
        )

    def test_funder_activity_report_unknown_funder_returns_zero(self):
        result = Query.resolve_funder_activity_report(
            None,
            None,
            analytic_value_id=self.other_funder.uuid,
            accounting_period_id=self.period.uuid,
        )

        self.assertEqual(
            result.debit_amount,
            0,
        )

        self.assertEqual(
            result.credit_amount,
            0,
        )

        self.assertEqual(
            result.balance_amount,
            0,
        )

    def test_funder_activity_report_multiple_accounts_are_aggregated(self):
        second_account = Account.objects.create(
            code="9003",
            full_code="9003",
            name="Second Funder Account",
        )

        second_transaction = Transaction.objects.create()

        second_leg = Leg.objects.create(
            transaction=second_transaction,
            account=second_account,
            amount=Money(
                200,
                self.currency_code,
            ),
        )

        Leg.objects.create(
            transaction=second_transaction,
            account=self.other_account,
            amount=Money(
                -200,
                self.currency_code,
            ),
        )

        legtag = LegTag(
            leg=self.funder_leg,
            analytic_value=self.funder,
            accounting_period_id=self.period.uuid,
        )
        legtag.save(username=self.user.username)

        legtag = LegTag(
            leg=second_leg,
            analytic_value=self.funder,
            accounting_period_id=self.period.uuid,
        )
        legtag.save(username=self.user.username)

        acc_bal_sn = AccountBalanceSnapshot(
            accounting_period=self.period,
            account=self.funder_account,
            debit_amount=Decimal("100"),
            credit_amount=Decimal("10"),
            balance_amount=Decimal("90"),
        )
        acc_bal_sn.save(username=self.user.username)

        acc_bal_sn2 = AccountBalanceSnapshot(
            accounting_period=self.period,
            account=second_account,
            debit_amount=Decimal("200"),
            credit_amount=Decimal("50"),
            balance_amount=Decimal("150"),
        )
        acc_bal_sn2.save(username=self.user.username)

        result = Query.resolve_funder_activity_report(
            None,
            None,
            analytic_value_id=self.funder.uuid,
            accounting_period_id=self.period.uuid,
        )

        self.assertEqual(
            result.debit_amount,
            Decimal("300"),
        )

        self.assertEqual(
            result.credit_amount,
            Decimal("60"),
        )

        self.assertEqual(
            result.balance_amount,
            Decimal("240"),
        )


class FunderActivityReportQueryTest(TestCase):

    def setUp(self):
        self.user = create_test_interactive_user()

        self.period = AccountingPeriod(
            name="2026-01",
            code="2026-01",
            status=AccountingPeriod.STATUS_OPEN,
        )
        self.period.save(username=self.user.username)

        self.funder_axis = AnalyticAxis(
            code=AnalyticAxis.FUNDER,
            name="Funder",
        )
        self.funder_axis.save(username=self.user.username)

        self.party_axis = AnalyticAxis(
            code=AnalyticAxis.PARTY,
            name="Party",
        )
        self.party_axis.save(username=self.user.username)

        self.funder = AnalyticValue(
            axis=self.funder_axis,
            funder_code="FUNDER001",
            external_reference="F001",
            display_name="Test Funder",
        )
        self.funder.save(username=self.user.username)

        self.other_funder = AnalyticValue(
            axis=self.funder_axis,
            funder_code="FUNDER002",
            external_reference="F002",
            display_name="Other Funder",
        )
        self.other_funder.save(username=self.user.username)

        self.party = AnalyticValue(
            axis=self.party_axis,
            party_type="health_facility",
            external_reference="HF001",
            display_name="Health Facility",
        )
        self.party.save(username=self.user.username)

        self.account_1 = Account.objects.create(
            code="1001",
            full_code="1001",
            name="Account 1",
        )

        self.account_2 = Account.objects.create(
            code="1002",
            full_code="1002",
            name="Account 2",
        )

        self.counterparty_account = Account.objects.create(
            code="9999",
            full_code="9999",
            name="Counterparty Account",
        )

        self.other_period = AccountingPeriod(
            name="2026-02",
            code="2026-02",
            status=AccountingPeriod.STATUS_OPEN,
        )
        self.other_period.save(username=self.user.username)

    # ------------------------------------------------------------------
    # Funder activity report
    # ------------------------------------------------------------------

    def _create_leg(self, account, amount):
        amount = Decimal(str(amount))

        transaction = Transaction.objects.create()

        leg = Leg.objects.create(
            transaction=transaction,
            account=account,
            amount=Money(amount, "EUR"),
        )

        Leg.objects.create(
            transaction=transaction,
            account=self.counterparty_account,
            amount=Money(-amount, "EUR"),
        )

        return leg

    def _create_snapshot(
        self,
        account,
        debit,
        credit,
        balance,
        period=None,
    ):
        period = period or self.period

        snapshot = AccountBalanceSnapshot(
            accounting_period=period,
            account=account,
            debit_amount=debit,
            credit_amount=credit,
            balance_amount=balance,
        )

        snapshot.save(username=self.user.username)

        return snapshot

    def _create_funder_tag(
        self,
        leg,
        funder=None,
        period=None,
    ):
        funder = funder or self.funder
        period = period or self.period

        tag = LegTag(
            leg=leg,
            analytic_value=funder,
            accounting_period_id=period.uuid,
        )

        tag.save(username=self.user.username)

        return tag

    def test_funder_activity_report_returns_aggregated_totals(self):
        """
        Le rapport doit agréger les snapshots des comptes liés
        au funder demandé.
        """

        leg_1 = self._create_leg(
            self.account_1,
            100,
        )

        leg_2 = self._create_leg(
            self.account_2,
            250,
        )

        self._create_funder_tag(leg_1)
        self._create_funder_tag(leg_2)

        self._create_snapshot(
            account=self.account_1,
            debit=Decimal("100"),
            credit=Decimal("20"),
            balance=Decimal("80"),
        )

        self._create_snapshot(
            account=self.account_2,
            debit=Decimal("250"),
            credit=Decimal("50"),
            balance=Decimal("200"),
        )

        result = Query().resolve_funder_activity_report(
            info=None,
            analytic_value_id=self.funder.uuid,
            accounting_period_id=self.period.uuid,
        )

        self.assertEqual(
            result.debit_amount,
            Decimal("350"),
        )

        self.assertEqual(
            result.credit_amount,
            Decimal("70"),
        )

        self.assertEqual(
            result.balance_amount,
            Decimal("280"),
        )

    def test_funder_activity_report_ignores_accounts_not_tagged_with_funder(self):
        """
        Un compte qui possède un snapshot mais qui n'est pas lié
        au funder demandé ne doit pas être inclus.
        """

        tagged_leg = self._create_leg(
            self.account_1,
            100,
        )

        untagged_leg = self._create_leg(
            self.account_2,
            500,
        )

        self._create_funder_tag(tagged_leg)

        self._create_snapshot(
            account=self.account_1,
            debit=Decimal("100"),
            credit=Decimal("10"),
            balance=Decimal("90"),
        )

        self._create_snapshot(
            account=self.account_2,
            debit=Decimal("500"),
            credit=Decimal("50"),
            balance=Decimal("450"),
        )

        result = Query().resolve_funder_activity_report(
            info=None,
            analytic_value_id=self.funder.uuid,
            accounting_period_id=self.period.uuid,
        )

        self.assertEqual(
            result.debit_amount,
            Decimal("100"),
        )

        self.assertEqual(
            result.credit_amount,
            Decimal("10"),
        )

        self.assertEqual(
            result.balance_amount,
            Decimal("90"),
        )

    def test_funder_activity_report_ignores_party_tags(self):
        """
        Un LegTag PARTY ne doit pas être considéré comme un tag FUNDER.
        """

        leg = self._create_leg(
            self.account_1,
            100,
        )

        party_tag = LegTag(
            leg=leg,
            analytic_value=self.party,
            accounting_period_id=self.period.uuid,
        )
        party_tag.save(username=self.user.username)

        self._create_snapshot(
            account=self.account_1,
            debit=Decimal("100"),
            credit=Decimal("0"),
            balance=Decimal("100"),
        )

        result = Query().resolve_funder_activity_report(
            info=None,
            analytic_value_id=self.funder.uuid,
            accounting_period_id=self.period.uuid,
        )

        self.assertEqual(
            result.debit_amount,
            Decimal("0"),
        )

        self.assertEqual(
            result.credit_amount,
            Decimal("0"),
        )

        self.assertEqual(
            result.balance_amount,
            Decimal("0"),
        )

    def test_funder_activity_report_ignores_other_funder(self):
        """
        Les comptes associés à un autre funder ne doivent pas être
        inclus dans le rapport du funder demandé.
        """

        leg_1 = self._create_leg(
            self.account_1,
            100,
        )

        leg_2 = self._create_leg(
            self.account_2,
            500,
        )

        self._create_funder_tag(
            leg_1,
            funder=self.funder,
        )

        self._create_funder_tag(
            leg_2,
            funder=self.other_funder,
        )

        self._create_snapshot(
            account=self.account_1,
            debit=Decimal("100"),
            credit=Decimal("10"),
            balance=Decimal("90"),
        )

        self._create_snapshot(
            account=self.account_2,
            debit=Decimal("500"),
            credit=Decimal("50"),
            balance=Decimal("450"),
        )

        result = Query().resolve_funder_activity_report(
            info=None,
            analytic_value_id=self.funder.uuid,
            accounting_period_id=self.period.uuid,
        )

        self.assertEqual(
            result.debit_amount,
            Decimal("100"),
        )

        self.assertEqual(
            result.credit_amount,
            Decimal("10"),
        )

        self.assertEqual(
            result.balance_amount,
            Decimal("90"),
        )

    def test_funder_activity_report_is_limited_to_accounting_period(self):
        """
        Un snapshot du même compte mais appartenant à une autre période
        ne doit pas être inclus.
        """

        leg = self._create_leg(
            self.account_1,
            100,
        )

        self._create_funder_tag(
            leg,
            funder=self.funder,
            period=self.period,
        )

        self._create_snapshot(
            account=self.account_1,
            debit=Decimal("100"),
            credit=Decimal("10"),
            balance=Decimal("90"),
            period=self.period,
        )

        self._create_snapshot(
            account=self.account_1,
            debit=Decimal("1000"),
            credit=Decimal("100"),
            balance=Decimal("900"),
            period=self.other_period,
        )

        result = Query().resolve_funder_activity_report(
            info=None,
            analytic_value_id=self.funder.uuid,
            accounting_period_id=self.period.uuid,
        )

        self.assertEqual(
            result.debit_amount,
            Decimal("100"),
        )

        self.assertEqual(
            result.credit_amount,
            Decimal("10"),
        )

        self.assertEqual(
            result.balance_amount,
            Decimal("90"),
        )

    def test_funder_activity_report_returns_zero_when_no_matching_data(self):
        """
        Aucun LegTag correspondant au funder => les agrégats doivent
        retourner 0 et non None.
        """

        result = Query().resolve_funder_activity_report(
            info=None,
            analytic_value_id=self.funder.uuid,
            accounting_period_id=self.period.uuid,
        )

        self.assertEqual(
            result.debit_amount,
            0,
        )

        self.assertEqual(
            result.credit_amount,
            0,
        )

        self.assertEqual(
            result.balance_amount,
            0,
        )

    def test_funder_activity_report_deduplicates_accounts(self):
        """
        Si plusieurs LegTag du même funder pointent vers le même compte,
        le snapshot du compte ne doit être compté qu'une seule fois.

        Le resolver utilise DISTINCT sur leg__account_id.
        """

        leg_1 = self._create_leg(
            self.account_1,
            100,
        )

        leg_2 = self._create_leg(
            self.account_1,
            -100,
        )

        self._create_funder_tag(leg_1)
        self._create_funder_tag(leg_2)

        self._create_snapshot(
            account=self.account_1,
            debit=Decimal("100"),
            credit=Decimal("100"),
            balance=Decimal("0"),
        )

        result = Query().resolve_funder_activity_report(
            info=None,
            analytic_value_id=self.funder.uuid,
            accounting_period_id=self.period.uuid,
        )

        self.assertEqual(
            result.debit_amount,
            Decimal("100"),
        )

        self.assertEqual(
            result.credit_amount,
            Decimal("100"),
        )

        self.assertEqual(
            result.balance_amount,
            Decimal("0"),
        )
