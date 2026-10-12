"""Visible procurement menus per user (uses ir.ui.menu visibility)."""
User = env["res.users"].sudo()
Menu = env["ir.ui.menu"]
sp_root = env.ref("ewseta_procurement.menu_ew_sp_root", raise_if_not_found=False)
scm_root = env.ref("ewseta_procurement.menu_ew_root", raise_if_not_found=False)

logins = [
    "lesibas@ewseta.org.za",
    "lesibaseabi88@gmail.com",
    "sup1@gmail.com",
    "ncina@gmail.com",
]

for login in logins:
    u = User.search([("login", "=", login)], limit=1)
    if not u:
        continue
    Mu = Menu.with_user(u)
    visible = Mu._visible_menu_ids()
    print("===", u.login, "id", u.id)
    print("  groups:", u.group_ids.mapped("name"))
    print("  app roots:", Mu.get_user_roots().mapped("name"))
    for label, root in [("SCM tree", scm_root), ("SP tree", sp_root)]:
        if not root:
            continue
        ids = Menu.search([("id", "child_of", root.id)]).ids
        names = Menu.browse([i for i in ids if i in visible]).mapped("name")
        print("  visible under %s:" % label, names)

env["ir.ui.menu"]._ew_refresh_menu_visibility_cache()
print("=== Menu visibility cache cleared ===")
