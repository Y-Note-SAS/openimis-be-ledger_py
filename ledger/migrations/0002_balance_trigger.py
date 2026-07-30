from django.db import migrations

SQL_CREATE_FUNCTION = """
CREATE OR REPLACE FUNCTION ledger_prevent_closed_period_write()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_status varchar;
BEGIN

    SELECT ap."Status"
      INTO v_status
      FROM "tblLedgerEntryMeta" lem
      JOIN "tblAccountingPeriod" ap
        ON ap."UUID" = lem."AccountingPeriodID"
     WHERE lem."TransactionID" = NEW.transaction_id;

    IF v_status IN ('LOCKED', 'CLOSED') THEN
        RAISE EXCEPTION
        'Cannot modify transaction in locked/closed accounting period';
    END IF;

    RETURN NEW;
END;
$$;
"""

SQL_CREATE_TRIGGER = """
DROP TRIGGER IF EXISTS trg_closed_period_leg
ON hordak_leg;

CREATE TRIGGER trg_closed_period_leg
BEFORE INSERT OR UPDATE OR DELETE
ON hordak_leg
FOR EACH ROW
EXECUTE FUNCTION ledger_prevent_closed_period_write();
"""

SQL_DROP = """
DROP TRIGGER IF EXISTS trg_closed_period_leg
ON hordak_leg;

DROP FUNCTION IF EXISTS
ledger_prevent_closed_period_write();
"""


class Migration(migrations.Migration):

    dependencies = [
        ("ledger", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql=SQL_CREATE_FUNCTION,
            reverse_sql=SQL_DROP,
        ),
        migrations.RunSQL(
            sql=SQL_CREATE_TRIGGER,
            reverse_sql="DROP TRIGGER IF EXISTS trg_closed_period_leg ON hordak_leg;",
        ),
    ]
