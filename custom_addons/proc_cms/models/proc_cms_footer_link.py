from odoo import _, fields, models
from odoo.exceptions import UserError


class ProcCmsFooterLink(models.Model):
    _name = "proc.cms.footer.link"
    _inherit = "proc.cms.website.content.mixin"
    _description = "Procurement CMS Footer Link"
    _order = "column_key, sequence, id"

    website_id = fields.Many2one(
        "website",
        required=True,
        ondelete="cascade",
        default=lambda self: self.env["website"].get_current_website(fallback=False),
    )
    column_key = fields.Selection(
        [
            ("explore", "Explore"),
            ("resources", "Resources"),
            ("legal", "Legal"),
        ],
        default="explore",
        required=True,
    )
    column_title = fields.Char(
        string="Column heading",
        translate=True,
        help="Leave empty to use the default heading for the column.",
    )
    label = fields.Char(required=True, translate=True)
    url = fields.Char(required=True, default="/")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    new_window = fields.Boolean(string="Open in new tab")

    def action_open_website_content(self):
        self.ensure_one()
        site = self.env["proc.cms.site"].search(
            [("website_id", "=", self.website_id.id)], limit=1
        )
        if not site:
            raise UserError(_("No CMS site record exists for %s.") % self.website_id.name)
        return {
            "type": "ir.actions.act_window",
            "name": _("Website content"),
            "res_model": "proc.cms.site",
            "res_id": site.id,
            "view_mode": "form",
            "target": "current",
        }
