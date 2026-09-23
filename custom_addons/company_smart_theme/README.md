Company Smart Theme (Odoo 19)
===================================

What it does
- Extracts a dominant color from the company logo.
- Lets companies pick a palette swatch or keep auto-from-logo.
- Lets users optionally override with a personal theme color.
- Injects per-session backend CSS so navbar, forms, lists and chatter match the brand color.

Requirements
- Pillow and colorthief: `pip install Pillow colorthief`
- Restart Odoo after installing the module.

Install
1. Module is in `custom_addons/company_smart_theme`.
2. Restart Odoo.
3. Update apps list and install **Company Smart Theme**.
4. Set the company logo: Settings → Companies → Backend Theme.
5. Optionally refresh from logo, pick a palette color, or set a personal color in Preferences.
6. Hard-refresh the backend.

Debug
- Logged in, open `/web/dynamic_theme.css` — it should return CSS with your color.
