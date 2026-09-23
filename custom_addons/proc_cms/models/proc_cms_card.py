from odoo import _, fields, models
from odoo.exceptions import UserError


class ProcCmsCard(models.Model):
    _name = "proc.cms.card"
    _inherit = "proc.cms.website.content.mixin"
    _description = "Procurement CMS Content Card"
    _order = "section_key, sequence, id"

    website_id = fields.Many2one(
        "website",
        required=True,
        ondelete="cascade",
        default=lambda self: self.env["website"].get_current_website(fallback=False),
    )
    page_key = fields.Selection(
        [
            ("home", "Home"),
            ("contact", "Contact"),
            ("global", "Global"),
        ],
        default="home",
        required=True,
    )
    section_key = fields.Char(
        required=True,
        index=True,
        help="Template section identifier, e.g. home_how_steps, home_gallery.",
    )
    card_type = fields.Selection(
        [
            ("step", "Process step"),
            ("gallery", "Gallery image"),
            ("feature", "Feature"),
            ("generic", "Generic card"),
        ],
        default="generic",
    )
    title = fields.Char(translate=True)
    subtitle = fields.Char(translate=True)
    body = fields.Html(translate=True, sanitize_attributes=False)
    image = fields.Binary(attachment=True)
    image_filename = fields.Char()
    image_alt = fields.Char(translate=True)
    static_image_url = fields.Char(
        string="Image URL",
        help="Used when no image is uploaded, e.g. module static path.",
    )
    link_url = fields.Char(string="Link URL")
    link_label = fields.Char(string="Link label", translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

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
