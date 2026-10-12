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
        cr.execute(
            """
            ALTER TABLE ew_rfq
            ADD COLUMN province_id INTEGER
            """
        )
    cr.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_name = 'ew_rfq_province_rel'
        )
        """
    )
    if not cr.fetchone()[0]:
        return
    cr.execute(
        """
        UPDATE ew_rfq AS r
        SET province_id = sub.state_id
        FROM (
            SELECT DISTINCT ON (rfq_id) rfq_id, state_id
            FROM ew_rfq_province_rel
            ORDER BY rfq_id, state_id
        ) AS sub
        WHERE r.id = sub.rfq_id
          AND (r.province_id IS NULL OR r.province_id = 0)
        """
    )
