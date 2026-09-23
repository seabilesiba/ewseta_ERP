from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class ProcCmsPage(models.Model):
    _name = "proc.cms.page"
    _inherit = "proc.cms.website.content.mixin"
    _description = "Procurement CMS Page"
    _order = "sequence, name"

    website_id = fields.Many2one(
        "website",
        required=True,
        ondelete="cascade",
        default=lambda self: self.env["website"].get_current_website(fallback=False),
    )
    name = fields.Char(required=True, translate=True)
    slug = fields.Char(
        required=True,
        help="URL path without leading slash, e.g. about-procurement",
    )
    page_title = fields.Char(string="Page title", translate=True)
    subtitle = fields.Char(translate=True)
    content = fields.Html(translate=True, sanitize=False)
    sequence = fields.Integer(default=10)
    is_published = fields.Boolean(default=True)
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

    _website_slug_unique = models.Constraint(
        "unique(website_id, slug)",
        "Page slugs must be unique per website.",
    )

    @api.constrains("slug")
    def _check_slug(self):
        for page in self:
            slug = (page.slug or "").strip().strip("/")
            if not slug or " " in slug:
                raise ValidationError("Page slug must be a single path segment without spaces.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("slug"):
                vals["slug"] = vals["slug"].strip().strip("/")
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("slug"):
            vals["slug"] = vals["slug"].strip().strip("/")
        return super().write(vals)

    def get_url(self):
        self.ensure_one()
        return f"/proc/page/{self.slug}"
