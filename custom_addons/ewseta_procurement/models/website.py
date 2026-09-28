import base64

from odoo import api, fields, models
from odoo.tools import file_open


class Website(models.Model):
    _inherit = "website"

    @api.model
    def ewseta_apply_favicon(self):
        """Load EWSETA favicon (from logo) into all websites — runs on module upgrade."""
        with file_open("ewseta_procurement/static/src/img/favicon.ico", "rb") as favicon:
            data = base64.b64encode(favicon.read())
        self.sudo().search([]).write({"favicon": data})
        return True

    @api.model
    def ewseta_restore_procurement_public_menus(self):
        """Undo ewseta_web menu takeover; re-sync proc_cms navigation."""
        from odoo.addons.ewseta_procurement.hooks import _cleanup_ewseta_web_top_menus

        _cleanup_ewseta_web_top_menus(self.env)
        self.env["proc.cms.seed"].seed_all_websites()
        return True

    def ewseta_procurement_landing_counts(self):
        """Open/closed RFQ counts for the public homepage template."""
        rfq = self.env["ew.rfq"].sudo()
        now = fields.Datetime.now()
        return {
            "open_count": rfq.search_count([
                ("state", "=", "published"),
                ("closing_at", ">", now),
            ]),
            "closed_count": rfq.search_count([
                "|",
                ("state", "=", "closed"),
                "&",
                ("state", "=", "published"),
                ("closing_at", "<=", now),
            ]),
        }
