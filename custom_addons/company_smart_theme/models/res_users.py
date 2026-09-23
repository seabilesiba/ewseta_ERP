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
