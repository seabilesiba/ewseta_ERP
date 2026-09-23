import base64

from odoo.tools import file_open


def post_init_hook(env):
    env["website"].ewseta_apply_favicon()
    legacy_menu = env.ref("ewseta_procurement.application_manu_rfq", raise_if_not_found=False)
    if legacy_menu:
        legacy_menu.unlink()
    env["proc.cms.seed"].seed_all_websites()
