from django.utils import timezone
from ledger.models import LedgerEntryMeta, ExternalReplicationRecord, ManualReviewQueueItem
from celery import shared_task
from ledger.replication.factory import get_adapter

MAX_ATTEMPTS = 3


@shared_task(
    bind=True,
    queue="ledger.sync.external",
    max_retries=3,
)
def replicate_entry(
    self,
    ledger_entry_id,
    target_system,
    user
):
    # Chargement
    entry = LedgerEntryMeta.objects.select_related(
        "transaction"
    ).get(
        pk=ledger_entry_id
    )

    # Idempotency

    record = ExternalReplicationRecord.objects.filter(
        idempotency_key=f"{target_system}:{entry.transaction.uuid}"
    ).first()
    if not record:
        record = ExternalReplicationRecord(
            ledger_entry=entry,
            target_system=target_system,
            idempotency_key=f"{target_system}:{entry.transaction.uuid}"
        )
        record.save(username=user.username)

    adapter = get_adapter(target_system)

    result = adapter.send(
        ledger_entry=entry,
        idempotency_key=record.idempotency_key,
    )

    # Déjà terminé
    if record.status in [
        record.STATUS_SUCCEEDED,
        record.STATUS_REJECTED,
        record.STATUS_UNCONFIRMED
    ]:
        return

    # Timeout
    if result.status == "timeout":

        if record.attempt_count < MAX_ATTEMPTS:
            record.attempt_count += 1
            record.save(
                username=user.username,
                update_fields=[
                    "attempt_count",
                ]
            )

            raise self.retry(
                countdown=60,
            )

        record.status = (
            ExternalReplicationRecord.STATUS_UNCONFIRMED
        )

        record.save(username=user.username)

        manual_revue = ManualReviewQueueItem(
            replication_record=record
        )
        manual_revue.save(username=user.username)

        return
    # Rejet
    if result.status == "rejected":

        record.status = (
            ExternalReplicationRecord.STATUS_REJECTED
        )

        record.rejection_reason = (
            result.rejection_reason
        )

        record.save(username=user.username)

        manual_revue = ManualReviewQueueItem(
            replication_record=record
        )
        manual_revue.save(username=user.username)

        return

    # succes
    record.status = (
        ExternalReplicationRecord.STATUS_SUCCEEDED
    )
    record.attempt_count += 1

    record.external_reference = (
        result.external_reference
    )
    record.last_attempted_at = timezone.now()

    record.save(username=user.username)
