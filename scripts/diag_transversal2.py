Rfq = env["ew.rfq"]
ict = env["ew.service.category"].search([("name", "ilike", "ICT")], limit=1)
for rfq in Rfq.search([("state", "=", "draft"), ("publication_type", "=", "transversal")]):
    cats = rfq.service_category_ids.mapped("name")
    n = len(rfq._find_eligible_service_providers())
    print("RFQ", rfq.id, "|", (rfq.name or "")[:50], "| cats:", cats, "| count field would be:", n)
