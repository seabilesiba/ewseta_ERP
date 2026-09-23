from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class ProcCmsBlock(models.Model):
    _name = "proc.cms.block"
    _inherit = "proc.cms.website.content.mixin"
    _description = "Procurement CMS Text Block"
    _order = "page_key, code"

    website_id = fields.Many2one(
        "website",
        required=True,
        ondelete="cascade",
        default=lambda self: self.env["website"].get_current_website(fallback=False),
    )
    code = fields.Char(
        required=True,
        help="Stable code for templates, e.g. home_hero, home_how_intro.",
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
    name = fields.Char(string="Internal name", required=True)
    eyebrow = fields.Char(translate=True)
    title = fields.Char(translate=True)
    lead = fields.Html(translate=True, sanitize_attributes=False)
    body = fields.Html(translate=True, sanitize_attributes=False)
    background_image = fields.Binary(attachment=True)
    background_image_filename = fields.Char()
    image = fields.Binary(string="Side image", attachment=True)
    image_filename = fields.Char()
    image_alt = fields.Char(translate=True)
    static_background_url = fields.Char(
        string="Background URL",
        help="Used when no background image is uploaded, e.g. /ewseta_procurement/static/src/img/landing_hero.jpg",
    )
    static_image_url = fields.Char(
        string="Image URL",
        help="Used when no side image is uploaded.",
    )
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

    _website_code_unique = models.Constraint(
        "unique(website_id, code)",
        "Block codes must be unique per website.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Avoid duplicate codes (e.g. accidental new line in the site editor list)."""
        records = self.env["proc.cms.block"]
        pending = []
        for vals in vals_list:
            wid = vals.get("website_id")
            code = (vals.get("code") or "").strip()
            if wid and code:
                existing = self.with_context(active_test=False).search(
                    [("website_id", "=", wid), ("code", "=", code)],
                    limit=1,
                )
                if existing:
                    existing.write(vals)
                    records |= existing
                    continue
            if not code:
                raise ValidationError(
                    _(
                        "Each content block needs a unique code (e.g. home_hero). "
                        "Edit existing rows — do not add new lines on the Page copy tab."
                    )
                )
            pending.append(vals)
        if pending:
            records |= super().create(pending)
        return records

    @api.constrains("website_id", "code")
    def _check_code_unique(self):
        for block in self:
            code = (block.code or "").strip()
            if not code or not block.website_id:
                continue
            if (
                self.with_context(active_test=False).search_count(
                    [
                        ("website_id", "=", block.website_id.id),
                        ("code", "=", code),
                        ("id", "!=", block.id),
                    ]
                )
                > 0
            ):
                raise ValidationError(
                    _("Block code “%s” already exists for this website. Edit the existing row instead.")
                    % code
                )
