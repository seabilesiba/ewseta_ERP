"""User-level theme preferences for company_smart_theme."""

from odoo import fields, models


class ResUsers(models.Model):
    """Extend users with an optional personal theme color override."""

    _inherit = "res.users"

    theme_color = fields.Char(string="Theme Color", default="#2C3E50")

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + ["theme_color"]

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + ["theme_color"]

    def action_reset_password(self):
        """Show signup/reset URL in the notification (works on HTTP; no form field)."""
        action = super().action_reset_password()
        if not self.env.user.has_group("base.group_erp_manager"):
            return action
        user = self[:1]
        partner = user.partner_id.sudo()
        if partner.signup_type:
            link = partner._get_signup_url()
            params = action.get("params") or {}
            msg = params.get("message") or ""
            params["message"] = f"{msg}\n\n{link}" if msg else link
            params["sticky"] = True
            action["params"] = params
        return action
