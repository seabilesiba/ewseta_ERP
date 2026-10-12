from odoo import api, models

# Backend / frontend editor menus — not for service-provider accounts.
_EW_WEBSITE_GROUP_XMLIDS = (
    "website.group_website_restricted_editor",
    "website.group_website_designer",
)

_EW_PROCUREMENT_GROUP_XMLIDS = (
    "ewseta_procurement.group_service_provider",
    "ewseta_procurement.group_scm_owner",
    "ewseta_procurement.group_rfq_admin",
)

_EW_PARTNER_SP_STRIP_GROUP_XMLIDS = _EW_PROCUREMENT_GROUP_XMLIDS[1:] + (
    "proc_cms.group_proc_cms_manager",
) + _EW_WEBSITE_GROUP_XMLIDS


class ResUsers(models.Model):
    _inherit = "res.users"

    # ------------------------------------------------------------------ roles
    def _ew_is_service_provider_only_user(self):
        self.ensure_one()
        return self.has_group("ewseta_procurement.group_service_provider") and not (
            self.has_group("ewseta_procurement.group_scm_owner")
            or self.has_group("ewseta_procurement.group_rfq_admin")
        )

    def _ew_is_procurement_app_restricted_user(self):
        """Limit app switcher to the SP portal app only (not SCM / admin staff)."""
        self.ensure_one()
        if self.has_group("base.group_system"):
            return False
        return self._ew_is_service_provider_only_user()

    def _ew_allowed_application_root_menu_ids(self):
        """Menu roots this user may open as apps (empty recordset = none)."""
        self.ensure_one()
        Menu = self.env["ir.ui.menu"]
        if not self._ew_is_procurement_app_restricted_user():
            return Menu
        roots = Menu
        if self._ew_is_service_provider_only_user():
            roots |= self.env.ref(
                "ewseta_procurement.menu_ew_sp_root", raise_if_not_found=False
            )
        elif self.has_group("ewseta_procurement.group_rfq_admin"):
            roots |= self.env.ref(
                "ewseta_procurement.menu_ew_root", raise_if_not_found=False
            )
            if self.has_group("proc_cms.group_proc_cms_manager"):
                roots |= self.env.ref(
                    "proc_cms.menu_proc_cms_root", raise_if_not_found=False
                )
        elif self.has_group("ewseta_procurement.group_scm_owner"):
            roots |= self.env.ref(
                "ewseta_procurement.menu_ew_root", raise_if_not_found=False
            )
            if self.has_group("proc_cms.group_proc_cms_manager"):
                roots |= self.env.ref(
                    "proc_cms.menu_proc_cms_root", raise_if_not_found=False
                )
        elif self.has_group("ewseta_procurement.group_service_provider"):
            roots |= self.env.ref(
                "ewseta_procurement.menu_ew_sp_root", raise_if_not_found=False
            )
        return roots

    @api.model
    def _ew_groups_from_xmlids(self, xmlids):
        groups = self.env["res.groups"]
        for xmlid in xmlids:
            group = self.env.ref(xmlid, raise_if_not_found=False)
            if group:
                groups |= group
        return groups

    @api.model
    def _ew_website_backend_groups(self):
        return self._ew_groups_from_xmlids(_EW_WEBSITE_GROUP_XMLIDS)

    # -------------------------------------------------------- partner SP sync
    def _ew_enforce_service_provider_partner_access(self):
        """Registered SP partners: user may only hold Service Provider (+ User)."""
        if self.env.context.get("ew_skip_procurement_access_sync"):
            return
        sp_group = self.env.ref(
            "ewseta_procurement.group_service_provider", raise_if_not_found=False
        )
        if not sp_group:
            return
        strip_groups = self._ew_groups_from_xmlids(_EW_PARTNER_SP_STRIP_GROUP_XMLIDS)
        base_user = self.env.ref("base.group_user", raise_if_not_found=False)
        for user in self:
            if user.share or not user.partner_id.ew_service_provider:
                continue
            if user.has_group("base.group_system"):
                continue
            if user.has_group("ewseta_procurement.group_scm_owner") or user.has_group(
                "ewseta_procurement.group_rfq_admin"
            ):
                continue
            cmds = []
            for group in strip_groups:
                if group in user.group_ids:
                    cmds.append((3, group.id))
            if sp_group not in user.group_ids:
                cmds.append((4, sp_group.id))
            if base_user and base_user not in user.group_ids:
                cmds.append((4, base_user.id))
            if cmds:
                user.with_context(ew_skip_procurement_access_sync=True).write(
                    {"group_ids": cmds}
                )

    def _ew_strip_website_backend_groups_for_restricted(self):
        """SP and SCM internal users must not keep website editor groups."""
        website_groups = self._ew_website_backend_groups()
        if not website_groups:
            return
        for user in self:
            if not user._ew_is_procurement_app_restricted_user():
                continue
            if user.has_group("base.group_system"):
                continue
            if user.has_group("ewseta_procurement.group_rfq_admin"):
                continue
            to_remove = user.group_ids & website_groups
            if to_remove:
                user.with_context(ew_skip_procurement_access_sync=True).write(
                    {"group_ids": [(3, gid) for gid in to_remove.ids]}
                )

    def _ew_sync_procurement_access(self):
        self._ew_enforce_service_provider_partner_access()
        self._ew_strip_website_backend_groups_for_restricted()

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        users._ew_sync_procurement_access()
        return users

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get("ew_skip_procurement_access_sync"):
            return res
        if {"group_ids", "partner_id"} & set(vals):
            self._ew_sync_procurement_access()
        return res

    @api.model
    def _ew_strip_website_groups_from_sp_only_users(self):
        """Upgrade hook: remove website editor groups from SP-only internal users."""
        sp_group = self.env.ref(
            "ewseta_procurement.group_service_provider", raise_if_not_found=False
        )
        if not sp_group:
            return True
        candidates = self.search([
            ("share", "=", False),
            ("group_ids", "in", sp_group.id),
        ])
        candidates._ew_strip_website_backend_groups_for_restricted()
        return True

    @api.model
    def _ew_strip_website_from_procurement_restricted_users(self):
        """Upgrade hook: drop website groups from SP/SCM users (not procurement admin)."""
        users = self.search([("share", "=", False)])
        users._ew_strip_website_backend_groups_for_restricted()
        return True

    @api.model
    def _ew_enforce_service_provider_partner_users(self):
        """Upgrade hook: align all registered SP partner logins to SP-only access."""
        partners = self.env["res.partner"].sudo().search([
            ("ew_service_provider", "=", True),
        ])
        users = self.sudo().search([
            ("partner_id", "in", partners.ids),
            ("active", "=", True),
            ("share", "=", False),
        ])
        users._ew_enforce_service_provider_partner_access()
        users._ew_strip_website_backend_groups_for_restricted()
        self.env["ir.ui.menu"]._ew_refresh_menu_visibility_cache()
        return True
