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
    def apply_nav_layout(self):
        """Main menu: Home, Procurements, CMS nav links (e.g. EOL), Contact. Header CTA: Procurement."""
        Nav = self.env["proc.cms.nav.item"].sudo()
        for website in self.env["website"].sudo().search([]):
            self._apply_nav_layout(website)
            self._ensure_eol_nav_item(website)
            self._ensure_footer_eol_link(website)
        Nav.search(
            [
                ("is_cta", "=", False),
                ("url", "=", "/employee/eol-assets"),
            ]
        ).unlink()
        self.env["proc.cms.nav.item"].sync_all_menus()

    @api.model
    def _apply_nav_layout(self, website):
        from .proc_cms_nav_item import EOL_NAV_URL

        Nav = self.env["proc.cms.nav.item"].sudo()
        Nav.search(
            [
                ("website_id", "=", website.id),
                ("is_cta", "=", False),
                ("url", "!=", EOL_NAV_URL),
            ]
        ).unlink()
        Nav.search(
            [
                ("website_id", "=", website.id),
                ("is_cta", "=", True),
                ("url", "in", ("/contactus", "/contact-us")),
            ]
        ).unlink()
        cta = Nav.search(
            [
                ("website_id", "=", website.id),
                ("is_cta", "=", True),
                ("url", "=", "/application/rfqs"),
            ],
            limit=1,
        )
        vals = {
            "name": "Procurement",
            "url": "/application/rfqs",
            "sequence": 5,
            "is_cta": True,
            "website_id": website.id,
            "active": True,
        }
        if cta:
            cta.write(vals)
        else:
            Nav.create(vals)

    @api.model
    def _ensure_eol_nav_item(self, website):
        """Default CMS navbar row for EOL request form (toggle via Website CMS → Navbar)."""
        from .proc_cms_nav_item import EOL_LANDING_URL, EOL_NAV_NAME, EOL_NAV_URL

        Nav = self.env["proc.cms.nav.item"].sudo()
        legacy = Nav.search(
            [
                ("website_id", "=", website.id),
                ("url", "=", EOL_LANDING_URL),
                ("is_cta", "=", False),
            ],
            limit=1,
        )
        if legacy:
            legacy.write({"url": EOL_NAV_URL, "name": EOL_NAV_NAME})
            return
        eol = Nav.search(
            [
                ("website_id", "=", website.id),
                ("url", "=", EOL_NAV_URL),
                ("is_cta", "=", False),
            ],
            limit=1,
        )
        if eol:
            return
        Nav.create(
            {
                "website_id": website.id,
                "name": EOL_NAV_NAME,
                "url": EOL_NAV_URL,
                "sequence": 30,
                "is_cta": False,
                "active": True,
            }
        )

    @api.model
    def _ensure_footer_eol_link(self, website):
        """Explore footer: EOL asset purchase (existing sites on upgrade)."""
        from .proc_cms_nav_item import EOL_NAV_NAME, EOL_NAV_URL

        Link = self.env["proc.cms.footer.link"].sudo()
        Link.search(
            [
                ("website_id", "=", website.id),
                ("url", "=", "/employee/eol-assets"),
            ]
        ).write({"url": EOL_NAV_URL, "label": EOL_NAV_NAME})
        if Link.search([("website_id", "=", website.id), ("url", "=", EOL_NAV_URL)], limit=1):
            return
        for label, seq in (("RFQ policy", 4), ("Contact us", 5)):
            for link in Link.search(
                [
                    ("website_id", "=", website.id),
                    ("column_key", "=", "explore"),
                    ("label", "=", label),
                ]
            ):
                if link.sequence < seq:
                    link.sequence = seq
        Link.create(
            {
                "website_id": website.id,
                "column_key": "explore",
                "label": EOL_NAV_NAME,
                "url": EOL_NAV_URL,
                "sequence": 3,
                "active": True,
            }
        )

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

        self._apply_nav_layout(website)

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
            {
                "code": "rfq_apply_privacy_policy",
                "name": "RFQ application — privacy checkbox",
                "page_key": "global",
                "body": (
                    "I confirm that I have read and accept the "
                    '<a href="/application/rfq-policy" target="_blank" rel="noopener noreferrer">'
                    "RFQ privacy policy</a>."
                ),
            },
            {
                "code": "rfq_policy_intro",
                "name": "RFQ policy page intro",
                "page_key": "rfq_policy",
                "eyebrow": "Policy",
                "title": "RFQ & RFP procurement policy",
                "lead": (
                    "Review EWSETA’s procurement policies and supporting documents "
                    "before you prepare or submit an application."
                ),
                "body": (
                    '<p class="text-muted mb-0">Download each document below or open PDFs '
                    "in your browser. Contact us if you need clarification on any requirement.</p>"
                ),
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
            ("explore", None, "EOL asset purchase", "/employee/eol-assets/request", 3),
            ("explore", None, "RFQ policy", "/application/rfq-policy", 4),
            ("explore", None, "Contact us", "/contactus", 5),
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
