import base64
import logging

from odoo import api, models
from odoo.tools import file_open

_logger = logging.getLogger(__name__)

_ASSET_PREFIX = "/ewseta_procurement/static/src/img/"


class ProcCmsSeed(models.AbstractModel):
    _name = "proc.cms.seed"
    _description = "Procurement CMS default content seeder"

    @api.model
    def _read_module_binary(self, module, relative_path):
        try:
            with file_open(f"{module}/{relative_path}", "rb") as handle:
                return base64.b64encode(handle.read())
        except FileNotFoundError:
            return False

    @api.model
    def _upsert(self, model, domain, vals, force=False):
        Model = self.env[model].sudo().with_context(active_test=False)
        record = Model.search(domain, limit=1)
        if not record and vals.get("website_id") and vals.get("code"):
            record = Model.search(
                [("website_id", "=", vals["website_id"]), ("code", "=", vals["code"])],
                limit=1,
            )
        if not record and vals.get("website_id") and vals.get("key"):
            record = Model.search(
                [("website_id", "=", vals["website_id"]), ("key", "=", vals["key"])],
                limit=1,
            )
        if record:
            if force:
                record.write(vals)
            return record
        create_vals = {
            term[0]: term[2]
            for term in domain
            if len(term) == 3 and term[1] == "="
        }
        try:
            with self.env.cr.savepoint():
                return Model.create({**create_vals, **vals})
        except Exception:
            record = Model.search(domain, limit=1)
            if not record and vals.get("website_id") and vals.get("code"):
                record = Model.search(
                    [
                        ("website_id", "=", vals["website_id"]),
                        ("code", "=", vals["code"]),
                    ],
                    limit=1,
                )
            if not record and vals.get("website_id") and vals.get("key"):
                record = Model.search(
                    [
                        ("website_id", "=", vals["website_id"]),
                        ("key", "=", vals["key"]),
                    ],
                    limit=1,
                )
            if record:
                if force:
                    record.write(vals)
                return record
            raise

    @api.model
    def seed_website(self, website, force=False):
        """Create or refresh CMS records to match the live procurement website."""
        if not website:
            return
        upsert = lambda model, domain, vals: self._upsert(model, domain, vals, force=force)

        logo = (
            self._read_module_binary("ewseta_procurement", "static/src/img/ewseta_logo.jpg")
            or self._read_module_binary("ewseta_procurement", "static/src/img/ewseta_logo.svg")
        )
        favicon = self._read_module_binary("ewseta_procurement", "static/src/img/favicon.ico")

        phone_display = (website.company_id.phone or "+1 555-555-5556").strip()
        phone_link = "".join(ch for ch in phone_display if ch.isdigit() or ch == "+") or "+15555555556"
        site_vals = {
            "footer_tagline": (
                "Public procurement for RFQs and RFPs — Energy & Water Sector "
                "Education and Training Authority."
            ),
            "copyright_suffix": "| All rights reserved",
            "active": True,
            "header_search_enabled": True,
            "header_phone_enabled": True,
            "header_phone": phone_display,
            "header_phone_link": phone_link,
        }
        if logo:
            site_vals["logo"] = logo
            site_vals["logo_filename"] = "ewseta_logo.jpg"
        if favicon:
            site_vals["favicon"] = favicon
            site_vals["favicon_filename"] = "favicon.ico"

        upsert(
            "proc.cms.site",
            [("website_id", "=", website.id)],
            {**site_vals, "website_id": website.id},
        )

        # Main menu links sync to website.menu; header CTA row (is_cta) drives the orange button only.
        nav_items = [
            {"name": "Procurements", "url": "/application/rfqs", "sequence": 50, "is_cta": False},
            {"name": "Contact us", "url": "/contactus", "sequence": 60, "is_cta": False},
            {"name": "Contact Us", "url": "/contactus", "sequence": 5, "is_cta": True},
        ]
        for item in nav_items:
            domain = [
                ("website_id", "=", website.id),
                ("name", "=", item["name"]),
                ("is_cta", "=", item["is_cta"]),
            ]
            vals = {**item, "website_id": website.id, "active": True}
            record = upsert(
                "proc.cms.nav.item",
                domain,
                vals,
            )
            if record:
                record.write({k: v for k, v in vals.items() if k != "website_id"})

        # Legacy misconfiguration: Procurements must be a menu link, not header CTA.
        self.env["proc.cms.nav.item"].sudo().search(
            [
                ("website_id", "=", website.id),
                ("name", "=", "Procurements"),
                ("is_cta", "=", True),
            ]
        ).unlink()

        buttons = [
            {
                "key": "home_hero_primary",
                "name": "Home hero — primary",
                "label": "Browse open opportunities",
                "url": "/application/rfqs",
                "style": "primary",
                "css_class": "btn-lg",
            },
            {
                "key": "home_hero_secondary",
                "name": "Home hero — secondary",
                "label": "How it works",
                "url": "#how-it-works",
                "style": "ghost",
                "css_class": "btn-lg",
            },
            {
                "key": "home_view_rfqs",
                "name": "Home — view RFQs",
                "label": "View all RFQs / RFPs",
                "url": "/application/rfqs",
                "style": "primary",
            },
            {
                "key": "home_cta_portal",
                "name": "Home bottom CTA",
                "label": "Go to opportunities portal",
                "url": "/application/rfqs",
                "style": "green",
                "css_class": "btn-lg",
            },
            {
                "key": "contact_quick_home",
                "name": "Contact — Home link",
                "label": "Home",
                "url": "/",
                "style": "outline",
                "css_class": "ew-contact__quick-btn ew-contact__quick-btn--home",
            },
            {
                "key": "contact_quick_rfq",
                "name": "Contact — RFQ link",
                "label": "RFQs / RFPs",
                "url": "/application/rfqs",
                "style": "outline",
                "css_class": "ew-contact__quick-btn ew-contact__quick-btn--rfq",
            },
        ]
        for btn in buttons:
            upsert(
                "proc.cms.button",
                [("website_id", "=", website.id), ("key", "=", btn["key"])],
                {**btn, "website_id": website.id, "active": True, "sequence": 10},
            )

        blocks = [
            {
                "code": "home_hero",
                "name": "Home hero",
                "page_key": "home",
                "title": "Procurement opportunities for energy & water",
                "lead": (
                    "Discover open RFQs and RFPs, submit compliant applications online, "
                    "and review transparent outcomes when opportunities close."
                ),
                "static_background_url": f"{_ASSET_PREFIX}landing_hero.jpg",
            },
            {
                "code": "home_how_intro",
                "name": "How it works intro",
                "page_key": "home",
                "eyebrow": "Process",
                "title": "How RFQ & RFP procurement works",
                "lead": (
                    "A clear, fair path from published opportunity to submitted proposal — "
                    "built for service providers in the energy and water sectors."
                ),
            },
            {
                "code": "home_opportunities",
                "name": "Opportunities section",
                "page_key": "home",
                "eyebrow": "For service providers",
                "title": "Built for transparent, accessible bidding",
                "lead": (
                    "EWSETA publishes procurement opportunities so qualified suppliers "
                    "can compete on merit — with equal access to information and deadlines."
                ),
                "body": (
                    '<ul class="ew-landing__checklist">'
                    "<li>Search and filter open and closed opportunities</li>"
                    "<li>Card or list views with mobile-friendly layouts</li>"
                    "<li>Secure document upload with clear requirements</li>"
                    "<li>Public register of submissions on closed RFQs/RFPs</li>"
                    "</ul>"
                ),
                "static_image_url": f"{_ASSET_PREFIX}landing_apply.jpg",
                "image_alt": "Business professionals reviewing procurement documents",
            },
            {
                "code": "home_sectors",
                "name": "Sectors section",
                "page_key": "home",
                "eyebrow": "Energy & water",
                "title": "Skills, infrastructure & sector delivery",
                "lead": (
                    "Procurement supports EWSETA’s mandate in the energy and water "
                    "education and training space — from learning programmes to essential "
                    "goods and services."
                ),
                "body": (
                    '<p class="text-muted mb-0">Whether you supply training, technology, '
                    "facilities, or professional services, register interest by applying "
                    "to relevant published RFQs and RFPs.</p>"
                ),
                "static_image_url": f"{_ASSET_PREFIX}landing_energy.jpg",
                "image_alt": "Energy infrastructure and power lines at sunset",
            },
            {
                "code": "home_cta",
                "name": "Home bottom CTA text",
                "page_key": "home",
                "title": "Ready to submit your proposal?",
                "lead": (
                    "Open the opportunities portal to apply before closing dates "
                    "or review closed procurement registers."
                ),
            },
            {
                "code": "contact_hero",
                "name": "Contact hero",
                "page_key": "contact",
                "eyebrow": "Contact",
                "title": "Get in touch",
                "lead": (
                    "Questions about procurement, RFQs/RFPs, or general enquiries — "
                    "send us a message and we will respond as soon as we can."
                ),
            },
            {
                "code": "contact_form",
                "name": "Contact form intro",
                "page_key": "contact",
                "eyebrow": "Send a message",
                "title": "How can we help?",
                "lead": "Complete the form below. Required fields are marked with an asterisk.",
            },
            {
                "code": "contact_sidebar",
                "name": "Contact sidebar intro",
                "page_key": "contact",
                "eyebrow": "Our company",
            },
        ]
        for block in blocks:
            code = block.pop("code")
            upsert(
                "proc.cms.block",
                [("website_id", "=", website.id), ("code", "=", code)],
                {**block, "website_id": website.id, "code": code, "active": True},
            )

        cards = [
            {
                "section_key": "home_how_steps",
                "page_key": "home",
                "card_type": "step",
                "sequence": 1,
                "title": "Find an opportunity",
                "body": (
                    "<p>Browse published RFQs and RFPs with closing dates, references, "
                    "and requirements listed upfront.</p>"
                ),
            },
            {
                "section_key": "home_how_steps",
                "page_key": "home",
                "card_type": "step",
                "sequence": 2,
                "title": "Prepare & apply",
                "body": (
                    "<p>Upload mandatory and optional documents through the online "
                    "application form before the closing date and time.</p>"
                ),
            },
            {
                "section_key": "home_how_steps",
                "page_key": "home",
                "card_type": "step",
                "sequence": 3,
                "title": "Track outcomes",
                "body": (
                    "<p>After closing, view the public submission register and outcomes "
                    "for completed procurements.</p>"
                ),
            },
            {
                "section_key": "home_gallery",
                "page_key": "home",
                "card_type": "gallery",
                "sequence": 1,
                "static_image_url": f"{_ASSET_PREFIX}landing_team.jpg",
                "image_alt": "Collaborative team planning procurement",
            },
            {
                "section_key": "home_gallery",
                "page_key": "home",
                "card_type": "gallery",
                "sequence": 2,
                "static_image_url": f"{_ASSET_PREFIX}landing_apply.jpg",
                "image_alt": "Professional meeting",
            },
            {
                "section_key": "home_gallery",
                "page_key": "home",
                "card_type": "gallery",
                "sequence": 3,
                "static_image_url": f"{_ASSET_PREFIX}landing_energy.jpg",
                "image_alt": "Energy sector",
            },
        ]
        for card in cards:
            section = card["section_key"]
            sequence = card["sequence"]
            upsert(
                "proc.cms.card",
                [
                    ("website_id", "=", website.id),
                    ("section_key", "=", section),
                    ("sequence", "=", sequence),
                ],
                {**card, "website_id": website.id, "active": True},
            )

        footer_links = [
            ("explore", "Explore", "Home", "/", 1),
            ("explore", None, "Procurements", "/application/rfqs", 2),
            ("explore", None, "Contact us", "/contactus", 3),
        ]
        for column_key, column_title, label, url, sequence in footer_links:
            vals = {
                "column_key": column_key,
                "label": label,
                "url": url,
                "sequence": sequence,
                "active": True,
            }
            if column_title:
                vals["column_title"] = column_title
            upsert(
                "proc.cms.footer.link",
                [
                    ("website_id", "=", website.id),
                    ("column_key", "=", column_key),
                    ("label", "=", label),
                ],
                {**vals, "website_id": website.id},
            )

        self.env["proc.cms.nav.item"].sync_all_menus()
        site = self.env["proc.cms.site"].search([("website_id", "=", website.id)], limit=1)
        if site:
            site._link_website_content()
        _logger.info("Proc CMS: seeded content for website %s", website.name)

    @api.model
    def seed_all_websites(self):
        for website in self.env["website"].sudo().search([]):
            self.seed_website(website)
        for site in self.env["proc.cms.site"].sudo().search([]):
            site._link_website_content()
