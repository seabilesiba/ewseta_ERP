# pylint: disable=invalid-name


def migrate(cr, version):
    cr.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'ew_rfq' AND column_name = 'province_id'
        """
    )
    if not cr.fetchone():
        return
    cr.execute(
        """
        CREATE TABLE IF NOT EXISTS ew_rfq_province_migrate (
            rfq_id INTEGER NOT NULL,
            state_id INTEGER NOT NULL
        )
        """
    )
    cr.execute("DELETE FROM ew_rfq_province_migrate")
    cr.execute(
        """
        INSERT INTO ew_rfq_province_migrate (rfq_id, state_id)
        SELECT id, province_id
        FROM ew_rfq
        WHERE province_id IS NOT NULL
        """
    )
