# pylint: disable=invalid-name


def migrate(cr, version):
    cr.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'ew_rfq' AND column_name = 'service_category_id'
        """
    )
    if not cr.fetchone():
        cr.execute(
            """
            ALTER TABLE ew_rfq
            ADD COLUMN service_category_id INTEGER
            """
        )
    cr.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_name = 'ew_rfq_service_category_rel'
        )
        """
    )
    if not cr.fetchone()[0]:
        return
    cr.execute(
        """
        UPDATE ew_rfq AS r
        SET service_category_id = sub.category_id
        FROM (
            SELECT DISTINCT ON (rfq_id) rfq_id, category_id
            FROM ew_rfq_service_category_rel
            ORDER BY rfq_id, category_id
        ) AS sub
        WHERE r.id = sub.rfq_id
          AND (r.service_category_id IS NULL OR r.service_category_id = 0)
        """
    )
