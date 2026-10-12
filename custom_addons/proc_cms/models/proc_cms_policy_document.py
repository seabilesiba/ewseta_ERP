from odoo import fields, models


class ProcCmsPolicyDocument(models.Model):
    _name = "proc.cms.policy.document"
    _inherit = "proc.cms.website.content.mixin"
    _description = "RFQ / RFP policy document (portal)"
    _order = "sequence, id"

    website_id = fields.Many2one(
        "website",
        required=True,
        ondelete="cascade",
        default=lambda self: self.env["website"].get_current_website(fallback=False),
    )
    name = fields.Char(string="Title", required=True, translate=True)
    description = fields.Html(string="Summary", translate=True, sanitize_attributes=False)
    file = fields.Binary(string="Document", required=True, attachment=True)
    file_filename = fields.Char(string="Filename")
    sequence = fields.Integer(default=10)
    is_published = fields.Boolean(string="Published on portal", default=True)
    active = fields.Boolean(default=True)

    def portal_download_url(self, download=False):
        self.ensure_one()
        url = f"/application/rfq-policy/document/{self.id}"
        if download:
            return f"{url}?download=1"
        return url

    def portal_is_visible(self):
        self.ensure_one()
        return bool(self.active and self.is_published and self.file)

    def portal_file_label(self):
        self.ensure_one()
        return (self.file_filename or "").strip() or self.name
