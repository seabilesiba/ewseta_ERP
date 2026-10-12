"""Audit procurement users and menu roots. Run via odoo shell stdin."""
User = env["res.users"].sudo()
Menu = env["ir.ui.menu"]
sp = env.ref("ewseta_procurement.group_service_provider", raise_if_not_found=False)
scm = env.ref("ewseta_procurement.group_scm_owner", raise_if_not_found=False)
cms = env.ref("proc_cms.group_proc_cms_manager", raise_if_not_found=False)
admin = env.ref("ewseta_procurement.group_rfq_admin", raise_if_not_found=False)
proc_groups = (sp | scm | cms | admin).ids if sp else []

users = User.search([
    ("active", "=", True),
    ("share", "=", False),
    ("group_ids", "in", proc_groups),
], order="login")
print("=== Active internal users with procurement/CMS groups ===")
for u in users:
    gnames = u.group_ids.mapped("name")
    print("---", u.login, "| id", u.id)
    print("  groups:", gnames)
    print("  ew_service_provider on contact:", u.partner_id.ew_service_provider)
    print("  restricted app switcher:", u._ew_is_procurement_app_restricted_user())
    print("  SP-only:", u._ew_is_service_provider_only_user())
    Mu = Menu.with_user(u)
    roots = Mu.get_user_roots()
    print("  app roots:", roots.mapped("name"))
    visible = Mu._visible_menu_ids()
    for xmlid, label in (
        ("ewseta_procurement.menu_ew_root", "SCM procurement"),
        ("ewseta_procurement.menu_ew_sp_root", "SP portal"),
    ):
        root = env.ref(xmlid, raise_if_not_found=False)
        if not root:
            continue
        tree_ids = Menu.search([("id", "child_of", root.id)]).ids
        names = Menu.browse([i for i in tree_ids if i in visible]).mapped("name")
        if names:
            print("  visible %s:" % label, names)
