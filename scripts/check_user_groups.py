login = "lesibaseabi88@gmail.com"
u = env["res.users"].sudo().search([("login", "=", login)], limit=1)
print("User:", u.login, u.id)
print("Groups:", u.group_ids.mapped("name"))
print("SP partner flag:", u.partner_id.ew_service_provider)
print("restricted?", u._ew_is_procurement_app_restricted_user())
print("SP only?", u._ew_is_service_provider_only_user())
roots = env["ir.ui.menu"].with_user(u).get_user_roots()
print("App roots:", roots.mapped("name"))
