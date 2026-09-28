# -*- coding: utf-8 -*-

from . import controllers
from . import models
from . import wizard

def post_init_hook(env):
    """Grant admin EOL manager/approver for pilot setups."""
    admin = env.ref('base.user_admin', raise_if_not_found=False)
    if not admin:
        return
    for xmlid in (
        'ewseta_eol_asset_purchase.group_eol_asset_manager',
        'ewseta_eol_asset_purchase.group_eol_approver',
    ):
        group = env.ref(xmlid, raise_if_not_found=False)
        if group and group not in admin.group_ids:
            admin.write({'group_ids': [(4, group.id)]})
    env['ew.eol.policy.document']._migrate_legacy_settings_policies()
    if env['ir.module.module']._get('proc_cms').state == 'installed':
        env['ew.eol.purchase.request'].eol_sync_proc_cms_public_visibility()

