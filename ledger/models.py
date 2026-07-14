from core import fields
from core import models as core_models
from django.db import models
from hordak.models import Account

class Sequence(core_models.VersionedModel):
    """
    This is Sequence class it all the fields needed
    """
    id = models.AutoField(db_column='SequenceID', primary_key=True)
    name = models.CharField(db_column='Name', max_length=100, blank=True, null=True, unique=True)
    code = models.CharField(db_column='Code', max_length=50, blank=True, null=True, unique=True)
    prefix = models.CharField(db_column='Prefix', max_length=50, blank=True, null=True)
    suffix = models.CharField(db_column='Suffix', max_length=50, blank=True, null=True)
    padding = models.SmallIntegerField(db_column='Padding', blank=True, null=True)

    class Meta:
        managed = True
        db_table = 'tblSequence'

class AccountPeriod(core_models.VersionedModel):
    """
    This is AccountPeriod class it all the fields needed
    """
    id = models.AutoField(db_column='AccountPeriodID', primary_key=True)
    start_date = fields.DateField(db_column='StartDate', null=True, blank=True)
    end_date = fields.DateField(db_column='EndDate', null=True, blank=True)
    name = models.CharField(db_column='Name', max_length=100, blank=True, null=True, unique=True)
    code = models.CharField(db_column='Code', max_length=50, blank=True, null=True, unique=True)
    status = models.SmallIntegerField(db_column='Status', blank=True, null=True)
    audit_user_id = models.IntegerField(db_column='AuditCreateUser', null=True, blank=True)
    audit_user_id_closed = models.IntegerField(db_column='AuditCloseUser', null=True, blank=True)

    STATUS_OPEN = 1
    STATUS_CLOSED = 2

    class Meta:
        managed = True
        db_table = 'tblAccountPeriod'

class AccountJournal(core_models.VersionedModel):
    """
    This is AccountJournal class it all the fields needed
    """
    id = models.AutoField(db_column='AccountJournalID', primary_key=True)
    name = models.CharField(db_column='Name', max_length=100, blank=True, null=True, unique=True)
    code = models.CharField(db_column='Code', max_length=50, blank=True, null=True, unique=True)
    type = models.CharField(db_column='Type', max_length=50, blank=True, null=True)
    sequence_id = models.ForeignKey(Sequence, models.DO_NOTHING, db_column='SequenceID', related_name="sequencies")
    default_credit_account_id = models.ForeignKey(Account, models.DO_NOTHING, db_column='DefaultCreditAccountId', related_name="defaultcreditaccounts")
    default_debit_account_id = models.ForeignKey(Account, models.DO_NOTHING, db_column='DefaultDebitAccountId', related_name="defaultdebitaccounts")

    class Meta:
        managed = True
        db_table = 'tblAccountJournal'
