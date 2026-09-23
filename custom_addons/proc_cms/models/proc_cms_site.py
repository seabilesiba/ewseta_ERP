from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ProcCmsSite(models.Model):
    _name = "proc.cms.site"
    _description = "Procurement CMS Site Settings"
    _rec_name = "website_id"

    website_id = fields.Many2one(
        "website",
        string="Website",
        required=True,
        ondelete="cascade",
        index=True,
    )
    active = fields.Boolean(default=True)
    logo = fields.Binary(string="Logo", attachment=True)
    logo_filename = fields.Char()
    favicon = fields.Binary(string="Favicon", attachment=True)
    favicon_filename = fields.Char()
    footer_tagline = fields.Text(
        string="Footer tagline",
        translate=True,
    )
    copyright_suffix = fields.Char(
        string="Copyright line",
        translate=True,
        help="Shown after the company name, e.g. “| All rights reserved”.",
    )
    header_search_enabled = fields.Boolean(
        string="Show search icon",
        default=True,
        help="Magnifying-glass search control in the top navbar (sign-in is not managed here).",
    )
    header_phone_enabled = fields.Boolean(
        string="Show phone number",
        default=True,
    )
    header_phone = fields.Char(
        string="Header phone (display)",
        help="Shown next to the phone icon in the navbar, e.g. +27 11 274-4700.",
    )
    header_phone_link = fields.Char(
        string="Phone link (tel:)",
        help="Used in the tel: href. Digits and + only, e.g. +27112744700.",
    )

    _website_id_unique = models.Constraint(
        "unique(website_id)",
        "Only one CMS site record is allowed per website.",
    )

    block_count = fields.Integer(compute="_compute_content_counts")
    button_count = fields.Integer(compute="_compute_content_counts")
    card_count = fields.Integer(compute="_compute_content_counts")
    nav_count = fields.Integer(compute="_compute_content_counts")
    footer_count = fields.Integer(compute="_compute_content_counts")

    block_ids = fields.One2many("proc.cms.block", "cms_site_id", string="Content blocks")
    button_ids = fields.One2many("proc.cms.button", "cms_site_id", string="Buttons")
    card_ids = fields.One2many("proc.cms.card", "cms_site_id", string="Content cards")
    nav_item_ids = fields.One2many("proc.cms.nav.item", "cms_site_id", string="Navbar items")
    footer_link_ids = fields.One2many("proc.cms.footer.link", "cms_site_id", string="Footer links")
    page_ids = fields.One2many("proc.cms.page", "cms_site_id", string="CMS pages")

    @api.depends("website_id")
    def _compute_content_counts(self):
        for site in self:
            wid = site.website_id.id
            site.block_count = self.env["proc.cms.block"].search_count([("website_id", "=", wid)])
            site.button_count = self.env["proc.cms.button"].search_count([("website_id", "=", wid)])
            site.card_count = self.env["proc.cms.card"].search_count([("website_id", "=", wid)])
            site.nav_count = self.env["proc.cms.nav.item"].search_count([("website_id", "=", wid)])
            site.footer_count = self.env["proc.cms.footer.link"].search_count([("website_id", "=", wid)])

    def _website_domain(self):
        self.ensure_one()
        return [("website_id", "=", self.website_id.id)]

    def action_open_blocks(self):
        self.ensure_one()
        return self._open_related("proc.cms.block", _("Content blocks"))

    def action_open_buttons(self):
        self.ensure_one()
        return self._open_related("proc.cms.button", _("Buttons"))

    def action_open_cards(self):
        self.ensure_one()
        return self._open_related("proc.cms.card", _("Content cards"))

    def action_open_nav(self):
        self.ensure_one()
        return self._open_related("proc.cms.nav.item", _("Navbar"))

    def action_open_footer(self):
        self.ensure_one()
        return self._open_related("proc.cms.footer.link", _("Footer links"))

    def action_open_pages(self):
        self.ensure_one()
        return self._open_related("proc.cms.page", _("CMS pages"))

    def _open_related(self, model, title):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": title,
            "res_model": model,
            "view_mode": "list,form",
            "domain": self._website_domain(),
            "context": {"default_website_id": self.website_id.id},
        }

    def action_preview_website(self):
        self.ensure_one()
        if not self.website_id:
            raise UserError(_("No website is linked to this CMS record."))
        return {
            "type": "ir.actions.act_url",
            "url": self.website_id.get_base_url(),
            "target": "new",
        }

    def action_load_default_content(self):
        self.ensure_one()
        self.env["proc.cms.seed"].seed_website(self.website_id, force=True)
        self._link_website_content()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Website content loaded"),
                "message": _("Current site copy, buttons, cards and links are now in the CMS."),
                "type": "success",
                "sticky": False,
            },
        }

    def _link_website_content(self):
        """Attach existing CMS rows to this site (for inline editing on the site form)."""
        self.ensure_one()
        if not self.website_id:
            return
        wid = self.website_id.id
        for model in (
            "proc.cms.block",
            "proc.cms.button",
            "proc.cms.card",
            "proc.cms.nav.item",
            "proc.cms.footer.link",
            "proc.cms.page",
        ):
            self.env[model].search(
                [("website_id", "=", wid), ("cms_site_id", "=", False)]
            ).write({"cms_site_id": self.id})

    @api.model
    def _resolve_cms_website(self):
        website = self.env["website"].get_current_website()
        if not website:
            website = self.env["website"].search([], limit=1)
        return website

    @api.model
    def action_open_website_cms(self):
        """Main menu: open (and seed if needed) the CMS for the active website."""
        website = self._resolve_cms_website()
        if not website:
            raise UserError(_("No website is configured yet."))
        seed = self.env["proc.cms.seed"]
        seed.seed_website(website, force=False)
        site = self.search([("website_id", "=", website.id)], limit=1)
        if not site:
            seed.seed_website(website, force=True)
            site = self.search([("website_id", "=", website.id)], limit=1)
        if not site:
            raise UserError(_("Could not initialize website CMS for %s.") % website.name)
        site._link_website_content()
        return {
            "type": "ir.actions.act_window",
            "name": _("Website content"),
            "res_model": "proc.cms.site",
            "res_id": site.id,
            "view_mode": "form",
            "target": "current",
            "context": {
                "default_website_id": website.id,
                "default_cms_site_id": site.id,
            },
        }
