Rfq = env["ew.rfq"]
Partner = env["res.partner"]
group = env.ref("ewseta_procurement.group_service_provider")

print("=== Draft transversal RFQs ===")
for rfq in Rfq.search([("publication_type", "=", "transversal"), ("state", "=", "draft")], order="id desc", limit=5):
    cats = rfq.service_category_ids.mapped("name")
    provs = rfq.province_ids.mapped("name")
    n = len(rfq._find_eligible_service_providers())
    print(f"RFQ {rfq.id} | cats={cats} | provs={provs} | matching={n}")

print("\n=== SP partners (flag + categories + provinces) ===")
users = env["res.users"].sudo().search([
    ("active", "=", True), ("share", "=", False), ("group_ids", "in", group.ids),
])
for u in users:
    p = u.partner_id
    print(
        u.login,
        "| SP flag:", p.ew_service_provider,
        "| cats:", p.ew_service_category_ids.mapped("name"),
        "| provs:", p.ew_province_ids.mapped("name"),
    )

ict = env["ew.service.category"].search([("name", "ilike", "ICT")], limit=1)
gp = env["res.country.state"].search([("name", "ilike", "Gauteng")], limit=1)
if ict and gp:
    rfq = Rfq.new({
        "publication_type": "transversal",
        "service_category_ids": [(6, 0, ict.ids)],
        "province_ids": [(6, 0, gp.ids)],
    })
    eligible = rfq._find_eligible_service_providers()
    print("\n=== Synthetic ICT + Gauteng ===")
    print("matching:", len(eligible), eligible.mapped("name"))
    rfq2 = Rfq.new({
        "publication_type": "transversal",
        "service_category_ids": [(6, 0, ict.ids)],
    })
    print("ICT no province matching:", len(rfq2._find_eligible_service_providers()))
