"""Ensure SP login partners are flagged for transversal matching."""
group = env.ref("ewseta_procurement.group_service_provider")
users = env["res.users"].sudo().search([
    ("active", "=", True),
    ("share", "=", False),
    ("group_ids", "in", group.ids),
])
fixed = 0
for u in users:
    p = u.partner_id.sudo()
    if not p.ew_service_provider:
        p.write({"ew_service_provider": True})
        fixed += 1
        print("Flagged ew_service_provider:", u.login)
env.cr.commit()
print("Done. Partners fixed:", fixed, "SP users:", len(users))
