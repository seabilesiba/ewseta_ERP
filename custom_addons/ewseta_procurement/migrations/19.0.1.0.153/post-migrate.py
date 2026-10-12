# pylint: disable=invalid-name


def migrate(cr, version):
    cr.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_name = 'ew_rfq_province_migrate'
        )
        """
    )
    if not cr.fetchone()[0]:
        return
    cr.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_name = 'ew_rfq_province_rel'
        )
        """
    )
    if cr.fetchone()[0]:
        cr.execute(
            """
            INSERT INTO ew_rfq_province_rel (rfq_id, state_id)
            SELECT m.rfq_id, m.state_id
            FROM ew_rfq_province_migrate m
            WHERE NOT EXISTS (
                SELECT 1
                FROM ew_rfq_province_rel r
                WHERE r.rfq_id = m.rfq_id AND r.state_id = m.state_id
            )
            """
        )
    cr.execute("DROP TABLE IF EXISTS ew_rfq_province_migrate")
