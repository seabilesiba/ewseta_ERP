u = env["res.users"].browse(12)
Menu = env["ir.ui.menu"].with_user(u)
allowed = Menu._ew_allowed_menu_ids()
print("allowed is None?", allowed is None)
if allowed is not None:
    print("allowed count", len(allowed))
visible = Menu._visible_menu_ids()
print("visible count", len(visible))
print("intersection count", len(visible & allowed) if allowed is not None else "n/a")
