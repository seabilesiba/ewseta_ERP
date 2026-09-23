from odoo import models


class Website(models.Model):
    _inherit = "website"

    def proc_cms_site(self):
        self.ensure_one()
        return (
            self.env["proc.cms.site"]
            .sudo()
            .search([("website_id", "=", self.id), ("active", "=", True)], limit=1)
        )

    def proc_cms_logo_url(self):
        self.ensure_one()
        site = self.proc_cms_site()
        if site and site.logo:
            return f"/web/image/proc.cms.site/{site.id}/logo"
        if self.logo:
            return f"/web/image/website/{self.id}/logo"
        return False

    def proc_cms_favicon_url(self):
        self.ensure_one()
        site = self.proc_cms_site()
        if site and site.favicon:
            return f"/web/image/proc.cms.site/{site.id}/favicon"
        return f"/web/image/website/{self.id}/favicon"

    def proc_cms_button(self, key):
        self.ensure_one()
        return (
            self.env["proc.cms.button"]
            .sudo()
            .search(
                [
                    ("website_id", "=", self.id),
                    ("key", "=", key),
                    ("active", "=", True),
                ],
                limit=1,
            )
        )

    def proc_cms_block(self, code):
        self.ensure_one()
        return (
            self.env["proc.cms.block"]
            .sudo()
            .search(
                [
                    ("website_id", "=", self.id),
                    ("code", "=", code),
                    ("active", "=", True),
                ],
                limit=1,
            )
        )

    def proc_cms_cards(self, section_key, page_key=None):
        self.ensure_one()
        domain = [
            ("website_id", "=", self.id),
            ("section_key", "=", section_key),
            ("active", "=", True),
        ]
        if page_key:
            domain.append(("page_key", "=", page_key))
        return (
            self.env["proc.cms.card"]
            .sudo()
            .search(domain, order="sequence, id")
        )

    def proc_cms_footer_links(self, column_key):
        self.ensure_one()
        return (
            self.env["proc.cms.footer.link"]
            .sudo()
            .search(
                [
                    ("website_id", "=", self.id),
                    ("column_key", "=", column_key),
                    ("active", "=", True),
                ],
                order="sequence, id",
            )
        )

    def proc_cms_footer_column_title(self, column_key, default_title):
        self.ensure_one()
        links = self.proc_cms_footer_links(column_key)
        for link in links:
            if link.column_title:
                return link.column_title
        return default_title

    def _proc_cms_header_cta_source(self):
        self.ensure_one()
        nav_cta = (
            self.env["proc.cms.nav.item"]
            .sudo()
            .search(
                [
                    ("website_id", "=", self.id),
                    ("is_cta", "=", True),
                    ("active", "=", True),
                ],
                limit=1,
            )
        )
        if nav_cta:
            return nav_cta
        return self.proc_cms_button("header_cta")

    def proc_cms_header_cta_visible(self):
        self.ensure_one()
        return bool(self._proc_cms_header_cta_source())

    def proc_cms_header_cta_label(self):
        self.ensure_one()
        src = self._proc_cms_header_cta_source()
        if not src:
            return "Contact Us"
        return src.name if src._name == "proc.cms.nav.item" else src.label

    def proc_cms_header_cta_url(self):
        self.ensure_one()
        src = self._proc_cms_header_cta_source()
        return (src.url if src else None) or "/contactus"

    def proc_cms_header_cta_new_window(self):
        self.ensure_one()
        src = self._proc_cms_header_cta_source()
        return bool(src and getattr(src, "new_window", False))

    def proc_cms_header_search_enabled(self):
        self.ensure_one()
        site = self.proc_cms_site()
        if not site:
            return True
        return site.header_search_enabled

    def proc_cms_header_phone_display(self):
        self.ensure_one()
        site = self.proc_cms_site()
        if site and site.header_phone:
            return site.header_phone
        return (self.company_id.phone or "+1 555-555-5556").strip()

    def proc_cms_header_phone_href(self):
        self.ensure_one()
        site = self.proc_cms_site()
        if site and site.header_phone_link:
            return site.header_phone_link.strip()
        display = self.proc_cms_header_phone_display()
        return "".join(ch for ch in display if ch.isdigit() or ch == "+")

    def proc_cms_header_phone_enabled(self):
        self.ensure_one()
        site = self.proc_cms_site()
        if not site:
            return bool(self.company_id.phone)
        if not site.header_phone_enabled:
            return False
        return bool(self.proc_cms_header_phone_display())

    def proc_cms_image_url(self, model, res_id, field):
        if res_id and field:
            return f"/web/image/{model}/{res_id}/{field}"
        return False

    def proc_cms_block_background_style(self, block):
        self.ensure_one()
        if block and block.background_image:
            url = self.proc_cms_image_url("proc.cms.block", block.id, "background_image")
            return f"background-image: url('{url}');"
        return False

    def proc_cms_hero_background_style(self, block, fallback_static_url):
        self.ensure_one()
        custom = self.proc_cms_block_background_style(block)
        if custom:
            return custom
        if block and block.static_background_url:
            return f"background-image: url('{block.static_background_url}');"
        return f"background-image: url('{fallback_static_url}');"

    def proc_cms_block_image_url(self, block, fallback_static_url=None):
        self.ensure_one()
        if block and block.image:
            return self.proc_cms_image_url("proc.cms.block", block.id, "image")
        if block and block.static_image_url:
            return block.static_image_url
        return fallback_static_url or False

    def proc_cms_card_image_url(self, card, fallback_static_url=None):
        self.ensure_one()
        if card and card.image:
            return self.proc_cms_image_url("proc.cms.card", card.id, "image")
        if card and card.static_image_url:
            return card.static_image_url
        return fallback_static_url or False
