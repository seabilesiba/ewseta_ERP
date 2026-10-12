"""Run: odoo-bin shell -c odoo.conf -d proc_db < scripts/diag_transversal.py"""
mod = env["ir.module.module"].search([("name", "=", "ewseta_procurement")], limit=1)
print("Module version (DB):", mod.latest_version, "state:", mod.state)

Cat = env["ew.service.category"]
ict = Cat.search([("name", "ilike", "ICT")], limit=1)
print("ICT category id:", ict.id, ict.name)

group = env.ref("ewseta_procurement.group_service_provider")
users = env["res.users"].sudo().search([
    ("active", "=", True),
    ("share", "=", False),
    ("group_ids", "in", group.ids),
])
print("Active internal SP-group users:", len(users))

Rfq = env["ew.rfq"]
draft = Rfq.search([
    ("publication_type", "=", "transversal"),
    ("state", "=", "draft"),
], order="id desc", limit=3)
for rfq in draft:
    n = len(rfq._find_eligible_service_providers())
    print(
        "Draft RFQ",
        rfq.id,
        rfq.name[:40] if rfq.name else "",
        "cats:",
        rfq.service_category_ids.mapped("name"),
        "provs:",
        rfq.province_ids.mapped("name"),
        "matching:",
        n,
    )

if ict:
    rfq_test = Rfq.new({
        "publication_type": "transversal",
        "service_category_ids": [(6, 0, ict.ids)],
    })
    eligible = rfq_test._find_eligible_service_providers()
    print("Synthetic ICT-only RFQ matching:", len(eligible))

print("--- SP users detail ---")
for u in users:
    p = u.partner_id.sudo()
    print(
        u.login,
        "| ew_service_provider:",
        p.ew_service_provider,
        "| categories:",
        p.ew_service_category_ids.mapped("name"),
        "| provinces:",
        p.ew_province_ids.mapped("name"),
    )

partners_flagged = env["res.partner"].sudo().search([("ew_service_provider", "=", True)])
print("Partners with ew_service_provider=True:", len(partners_flagged))
