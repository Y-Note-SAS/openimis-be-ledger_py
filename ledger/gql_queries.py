from graphene_django import DjangoObjectType
import graphene
from core.schema import OrderedDjangoFilterConnectionField
from .models import (
    LedgerEntryMeta,
    PartyLedgerBalance,
    AccountingPeriod,
    LegTag,
    AccountBalanceSnapshot,
    AnalyticAxis
)
from core import prefix_filterset, ExtendedConnection
from django.db.models import Sum

class LedgerEntryGQLType(DjangoObjectType):

    client_mutation_id = graphene.String()

    class Meta:
        model = LedgerEntryMeta
        interfaces = (graphene.relay.Node,)
        filter_fields = {
            # "id": ["exact"],
            # "mission_code": ["exact", "istartswith", "icontains", "iexact"],
            # "status": ["exact", "gt"],
            # "start_date": ["exact", "lt", "lte", "gt", "gte"],
            # "end_date": ["exact", "lt", "lte", "gt", "gte"],
            # **prefix_filterset("region__", LocationGQLType._meta.filter_fields),
            # **prefix_filterset("district__", LocationGQLType._meta.filter_fields),
            # **prefix_filterset("user__", UserGQLType._meta.filter_fields),
        }
        connection_class = ExtendedConnection


class PartyLedgerBalanceGQLType(DjangoObjectType):

    client_mutation_id = graphene.String()

    class Meta:
        model = PartyLedgerBalance
        interfaces = (graphene.relay.Node,)
        filter_fields = {
        }
        connection_class = ExtendedConnection

class AccountingPeriodGQLType(DjangoObjectType):

    client_mutation_id = graphene.String()

    class Meta:
        model = AccountingPeriod
        interfaces = (graphene.relay.Node,)
        filter_fields = {
        }
        connection_class = ExtendedConnection

class FunderActivityReportGQLType(graphene.ObjectType):
    debit_amount = graphene.Decimal()
    credit_amount = graphene.Decimal()
    balance_amount = graphene.Decimal()

class Query(graphene.ObjectType):

    party_ledger_balance = OrderedDjangoFilterConnectionField(
        PartyLedgerBalanceGQLType
    )

    ledger_entries = OrderedDjangoFilterConnectionField(
        LedgerEntryGQLType
    )

    funder_activity_report = graphene.Field(
        FunderActivityReportGQLType,
        analytic_value_id=graphene.UUID(required=True),
        accounting_period_id=graphene.UUID(required=True),
    )

    def resolve_funder_activity_report(
        self,
        info,
        analytic_value_id,
        accounting_period_id,
    ):
        funder_account_ids = (
            LegTag.objects
            .filter(
                analytic_value_id=analytic_value_id,
                accounting_period_id=accounting_period_id,
                analytic_value__axis__code=AnalyticAxis.FUNDER,
            )
            .values_list(
                "leg__account_id",
                flat=True,
            )
            .distinct()
        )

        totals = (
            AccountBalanceSnapshot.objects
            .filter(
                accounting_period_id=accounting_period_id,
                account_id__in=funder_account_ids,
            )
            .aggregate(
                debit_amount=Sum("debit_amount"),
                credit_amount=Sum("credit_amount"),
                balance_amount=Sum("balance_amount"),
            )
        )

        return FunderActivityReportGQLType(
            debit_amount=totals["debit_amount"] or 0,
            credit_amount=totals["credit_amount"] or 0,
            balance_amount=totals["balance_amount"] or 0,
        )
