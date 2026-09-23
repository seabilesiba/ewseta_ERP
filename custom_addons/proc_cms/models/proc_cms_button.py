from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class ProcCmsButton(models.Model):
    _name = "proc.cms.button"
    _inherit = "proc.cms.website.content.mixin"
    _description = "Procurement CMS Button"
    _order = "sequence, id"

    website_id = fields.Many2one(
        "website",
        required=True,
        ondelete="cascade",
        default=lambda self: self.env["website"].get_current_website(fallback=False),
    )
    key = fields.Char(
        required=True,
        help="Stable identifier used in templates, e.g. home_hero_primary, header_cta.",
    )
    name = fields.Char(string="Internal name", required=True)
    label = fields.Char(string="Button label", required=True, translate=True)
    url = fields.Char(required=True, default="/")
    style = fields.Selection(
        [
            ("primary", "Primary (orange)"),
            ("ghost", "Ghost"),
            ("green", "Green"),
            ("secondary", "Secondary"),
            ("outline", "Outline"),
        ],
        default="primary",
    )
    css_class = fields.Char(string="Extra CSS classes")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    new_window = fields.Boolean(string="Open in new tab")
    css_classes_preview = fields.Char(
        string="CSS classes on site",
        compute="_compute_css_classes_preview",
    )

    @api.depends("style", "css_class")
    def _compute_css_classes_preview(self):
        mapping = {
            "primary": "ew-landing__btn ew-landing__btn--primary",
            "ghost": "ew-landing__btn ew-landing__btn--ghost",
            "green": "ew-landing__btn ew-landing__btn--green",
            "secondary": "btn btn-secondary",
            "outline": "btn btn-outline-secondary",
        }
        for button in self:
            base = mapping.get(button.style, "btn btn-primary")
            extra = (button.css_class or "").strip()
            button.css_classes_preview = f"{base} {extra}".strip() if extra else base

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

    _website_key_unique = models.Constraint(
        "unique(website_id, key)",
        "Button keys must be unique per website.",
    )

    @api.model_create_multi
    def create(self, vals_list):
        records = self.env["proc.cms.button"]
        pending = []
        for vals in vals_list:
            wid = vals.get("website_id")
            key = (vals.get("key") or "").strip()
            if wid and key:
                existing = self.with_context(active_test=False).search(
                    [("website_id", "=", wid), ("key", "=", key)],
                    limit=1,
                )
                if existing:
                    existing.write(vals)
                    records |= existing
                    continue
            if not key:
                raise ValidationError(
                    _(
                        "Each button needs a unique key. Edit existing rows — "
                        "do not add new lines on the Buttons tab."
                    )
                )
            pending.append(vals)
        if pending:
            records |= super().create(pending)
        return records

    def css_classes(self):
        """Return Bootstrap / landing classes for QWeb."""
        self.ensure_one()
        mapping = {
            "primary": "ew-landing__btn ew-landing__btn--primary",
            "ghost": "ew-landing__btn ew-landing__btn--ghost",
            "green": "ew-landing__btn ew-landing__btn--green",
            "secondary": "btn btn-secondary",
            "outline": "btn btn-outline-secondary",
        }
        base = mapping.get(self.style, "btn btn-primary")
        if self.css_class:
            return f"{base} {self.css_class}".strip()
        return base
