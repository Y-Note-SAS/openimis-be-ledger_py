from django.core.exceptions import ValidationError
from django.db import transaction

from core.signals import register_service_signal

from hordak.models import Transaction, Leg

from ledger.models import (
    AccountingPeriod,
    LedgerEntryMeta,
    LegTag,
)
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
        if accounting_period.status != AccountingPeriod.STATUS_OPEN:
            raise ClosedPeriodException(
                "Cannot post into locked/closed period"
            )

        if not legs:
            raise ValidationError("At least two legs required")

        for leg_data in legs:
            if not leg_data.get("account"):
                raise MissingAccountMappingException(
                    "Missing account mapping"
                )

        tags = tags or {}

        with transaction.atomic():

            trx = Transaction.objects.create()

            created_legs = []

            for leg_data in legs:
                leg = Leg.objects.create(
                    transaction=trx,
                    account=leg_data["account"],
                    amount=Money(leg_data["amount"], "EUR"),
                )
                created_legs.append(leg)

            meta = LedgerEntryMeta(
                transaction=trx,
                journal=journal,
                accounting_period=accounting_period,
                source_event_type=source_event_type,
                source_event_reference=source_event_reference,
            )
            meta.save(username=user.username)

            for leg, leg_tags in tags.items():

                for analytic_value in leg_tags:

                    legtag = LegTag(
                        leg=created_legs[leg],
                        analytic_value=analytic_value,
                    )
                    legtag.save(username=user.username)

            return meta
