from django.core.exceptions import ValidationError
from django.db import transaction

from core.signals import register_service_signal

from hordak.models import Transaction, Leg

from ledger.models import (
    AccountingPeriod,
    LedgerEntryMeta,
    LegTag,
    DeploymentConfiguration
)
from decimal import Decimal
from djmoney.money import Money

class MissingAccountMappingException(Exception):
    pass


class ClosedPeriodException(Exception):
    pass


class LedgerEntryService:

    @classmethod
    @register_service_signal("ledger_service.post_entry")
    def post(
        cls,
        journal,
        accounting_period,
        source_event_type,
        source_event_reference,
        legs,
        tags=None,
        user=None,
    ):

        if not user:
            raise ValidationError(
                "User is required to post ledger entries"
            )

        username = user.username

        if accounting_period.status != AccountingPeriod.STATUS_OPEN:
            raise ClosedPeriodException(
                "Cannot post into locked/closed period"
            )

        if len(legs) < 2:
            raise ValidationError(
                "At least two legs required"
            )

        for leg_data in legs:
            if not leg_data.get("account"):
                raise MissingAccountMappingException(
                    "Missing account mapping"
                )

        total = sum(
            Decimal(str(leg["amount"]))
            for leg in legs
        )

        if total != Decimal("0"):
            raise ValidationError(
                "Ledger entry must be balanced"
            )

        deployment_config = DeploymentConfiguration.objects.first()
        if deployment_config:
            currency_code = deployment_config.currency_code
        else:
            currency_code = "EUR"

        tags = tags or {}

        with transaction.atomic():

            trx = Transaction.objects.create()

            meta = LedgerEntryMeta(
                transaction=trx,
                journal=journal,
                accounting_period=accounting_period,
                source_event_type=source_event_type,
                source_event_reference=source_event_reference,
            )

            meta.save(username=username)

            created_legs = []

            for leg_data in legs:

                leg = Leg.objects.create(
                    transaction=trx,
                    account=leg_data["account"],
                    amount=Money(
                        leg_data["amount"],
                        currency_code,
                    ),
                )

                created_legs.append(leg)

            for leg_index, leg_tags in tags.items():

                if leg_index >= len(created_legs):
                    raise ValidationError(
                        f"Invalid leg index: {leg_index}"
                    )

                for analytic_value in leg_tags:

                    legtag = LegTag(
                        leg=created_legs[leg_index],
                        analytic_value=analytic_value,
                        accounting_period_id=accounting_period.uuid
                    )

                    legtag.save(username=username)

            return meta
