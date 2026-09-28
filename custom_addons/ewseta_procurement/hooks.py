import base64

from odoo.tools import file_open

# Created by ewseta_web post_init_hook when that module is installed by mistake.
_EWSETA_WEB_LEGACY_TOP_MENUS = (
    "About",
    "Skills Development",
    "Supply Chain",
)


def _cleanup_ewseta_web_top_menus(env):
    website = env.ref("website.default_website", raise_if_not_found=False)
    if not website or not website.menu_id:
        return
    Menu = env["website.menu"].sudo()
    main = website.menu_id
    for name in _EWSETA_WEB_LEGACY_TOP_MENUS:
        Menu.search(
            [
                ("parent_id", "=", main.id),
                ("website_id", "=", website.id),
                ("name", "=", name),
            ]
        ).unlink()
    homes = Menu.search(
        [
            ("parent_id", "=", main.id),
            ("website_id", "=", website.id),
            ("name", "=", "Home"),
        ],
        order="id asc",
    )
    if len(homes) > 1:
        canonical = homes.filtered(
            lambda m: (m.url or "/").replace(env["website"].get_base_url(), "").rstrip("/") in ("", "/")
        )
        keep = canonical[:1] if canonical else homes[:1]
        (homes - keep).unlink()
    # ewseta_web adds a top-level "Contact Us" menu; procurement uses CMS navbar + header CTA instead.
    Menu.search(
        [
            ("parent_id", "=", main.id),
            ("website_id", "=", website.id),
            ("name", "=", "Contact Us"),
            ("url", "=", "/contactus"),
        ]
    ).unlink()


def post_init_hook(env):
    env["website"].ewseta_apply_favicon()
    legacy_menu = env.ref("ewseta_procurement.application_manu_rfq", raise_if_not_found=False)
    if legacy_menu:
        legacy_menu.unlink()
    _cleanup_ewseta_web_top_menus(env)
    env["proc.cms.seed"].seed_all_websites()
