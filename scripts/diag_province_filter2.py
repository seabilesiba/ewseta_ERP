ict = env["ew.service.category"].search([("name", "ilike", "ICT")], limit=1)
gp = env["res.country.state"].search([("name", "ilike", "Gauteng")], limit=1)
print("ICT id", ict.id, "GP id", gp.id)
u = env["res.users"].sudo().search([("login", "=", "lesibaseabi88@gmail.com")], limit=1)
p = u.partner_id
print("Partner", p.id, p.name)
print("Partner cats ids", p.ew_service_category_ids.ids)
print("Partner prov ids", p.ew_province_ids.ids)
print("Partner prov names", p.ew_province_ids.mapped("name"))
print("GP in partner provs?", gp.id in p.ew_province_ids.ids)
print("_ew_procurement_provider_active?", p._ew_procurement_provider_active())

rfq = env["ew.rfq"].new({
    "publication_type": "transversal",
    "service_category_ids": [(6, 0, ict.ids)],
    "province_ids": [(6, 0, gp.ids)],
})
domain = rfq._domain_eligible_service_providers()
print("domain", domain)
partners = env["res.partner"].sudo().search(domain)
print("after domain", partners.mapped("name"))
if rfq.province_ids:
    rfq_provinces = rfq.province_ids
    print("rfq province ids", rfq_provinces.ids)
    for p in partners:
        inter = p.ew_province_ids & rfq_provinces
        print("  intersect", p.name, inter.ids)
    partners = partners.filtered(lambda p: bool(p.ew_province_ids & rfq_provinces))
print("final", partners.mapped("name"))
