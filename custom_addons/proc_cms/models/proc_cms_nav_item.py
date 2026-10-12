from odoo import _, api, fields, models
from odoo.exceptions import UserError

EOL_NAV_URL = "/employee/eol-assets/request"
EOL_NAV_NAME = "EOL asset purchase"
EOL_LANDING_URL = "/employee/eol-assets"


class ProcCmsNavItem(models.Model):
    _name = "proc.cms.nav.item"
    _inherit = "proc.cms.website.content.mixin"
    _description = "Procurement CMS Navbar Item"
    _order = "sequence, id"

    website_id = fields.Many2one(
        "website",
        required=True,
        ondelete="cascade",
        default=lambda self: self.env["website"].get_current_website(fallback=False),
    )
    name = fields.Char(required=True, translate=True)
    url = fields.Char(required=True, default="/")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    new_window = fields.Boolean(string="Open in new tab")
    is_cta = fields.Boolean(
        string="Header CTA",
        help="When set, this item controls the orange header button instead of the main menu.",
    )
    menu_id = fields.Many2one(
        "website.menu",
        string="Synced menu",
        ondelete="set null",
        copy=False,
        readonly=True,
    )

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

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_website_menu()
        return records

    def write(self, vals):
        res = super().write(vals)
        self._sync_website_menu()
        return res

    def unlink(self):
        menus = self.mapped("menu_id")
        res = super().unlink()
        menus.exists().unlink()
        return res

    def _main_menu(self):
        self.ensure_one()
        website = self.website_id
        if website.menu_id:
            return website.menu_id
        main = self.env.ref("website.main_menu", raise_if_not_found=False)
        if not main:
            return self.env["website.menu"]
        return self.env["website.menu"].search(
            [
                ("website_id", "=", website.id),
                ("url", "=", main.url),
                ("name", "=", main.name),
            ],
            limit=1,
        ) or main

    @api.model
    def sync_all_menus(self):
        self.search([])._sync_website_menu()
        for website in self.env["website"].sudo().search([]):
            self._normalize_main_menu(website)

    @api.model
    def _normalize_main_menu(self, website):
        """Keep top menu to Home + Contact Us; drop legacy EWSETA corporate nav."""
        Menu = self.env["website.menu"].sudo()
        parent = website.menu_id
        if not parent:
            return
        synced_menu_ids = set(
            self.search([("website_id", "=", website.id), ("menu_id", "!=", False)]).mapped(
                "menu_id"
            ).ids
        )
        legacy_names = {
            "About",
            "Skills Development",
            "Supply Chain",
            "Procurements",
            "Contact Us",
            "Power Up",
            "QA & Compliance",
            "News & Events",
            "Stakeholder Portal",
            "Learner Resources",
        }
        for menu in Menu.search([("parent_id", "=", parent.id)]):
            url = (menu.url or "/").rstrip("/") or "/"
            if menu.id in synced_menu_ids:
                continue
            if menu.name in legacy_names and url in ("#", "/default-main-menu"):
                menu.child_id.unlink()
                menu.unlink()
                continue
            if url == "/":
                menu.write({"name": "Home", "mega_menu_content": False, "sequence": 10})
                continue
            if url == "/contactus":
                menu.write({"name": "Contact Us", "mega_menu_content": False, "sequence": 40})
                continue
            if url == "/application/rfqs":
                menu.write({"name": "Procurements", "mega_menu_content": False, "sequence": 20})
                continue
            if url in (EOL_NAV_URL, EOL_LANDING_URL):
                if url == EOL_LANDING_URL and menu.id not in synced_menu_ids:
                    menu.child_id.unlink()
                    menu.unlink()
                    continue
                if url == EOL_NAV_URL and menu.id not in synced_menu_ids:
                    menu.write({"name": EOL_NAV_NAME, "mega_menu_content": False, "sequence": 30})
                continue
            if url == "/application/rfq-policy":
                menu.child_id.unlink()
                menu.unlink()
                continue
            menu.child_id.unlink()
            menu.unlink()

        self._ensure_standard_main_menus(website, parent)

    @api.model
    def _ensure_standard_main_menus(self, website, parent):
        Menu = self.env["website.menu"].sudo()
        home = Menu.search(
            [
                ("parent_id", "=", parent.id),
                ("website_id", "=", website.id),
                ("url", "in", ("/", "")),
            ],
            limit=1,
        )
        if not home:
            Menu.create(
                {
                    "name": "Home",
                    "url": "/",
                    "parent_id": parent.id,
                    "website_id": website.id,
                    "sequence": 10,
                }
            )
        procurements = Menu.search(
            [
                ("parent_id", "=", parent.id),
                ("website_id", "=", website.id),
                ("url", "=", "/application/rfqs"),
            ],
            limit=1,
        )
        if not procurements:
            Menu.create(
                {
                    "name": "Procurements",
                    "url": "/application/rfqs",
                    "parent_id": parent.id,
                    "website_id": website.id,
                    "sequence": 20,
                }
            )
        contact = Menu.search(
            [
                ("parent_id", "=", parent.id),
                ("website_id", "=", website.id),
                ("url", "=", "/contactus"),
            ],
            limit=1,
        )
        if not contact:
            contact_page = self.env.ref("website.contactus_page", raise_if_not_found=False)
            vals = {
                "name": "Contact Us",
                "url": "/contactus",
                "parent_id": parent.id,
                "website_id": website.id,
                "sequence": 40,
            }
            if contact_page:
                vals["page_id"] = contact_page.id
            Menu.create(vals)

    def _sync_website_menu(self):
        Menu = self.env["website.menu"].sudo()
        for item in self:
            if item.is_cta:
                if item.menu_id:
                    item.menu_id.unlink()
                    item.menu_id = False
                continue
            if not item.active:
                if item.menu_id:
                    item.menu_id.unlink()
                    item.menu_id = False
                continue
            parent = item._main_menu()
            vals = {
                "name": item.name,
                "url": item.url or "/",
                "sequence": item.sequence,
                "website_id": item.website_id.id,
                "parent_id": parent.id,
                "new_window": item.new_window,
            }
            if item.menu_id:
                item.menu_id.write(vals)
            else:
                menu = Menu.create(vals)
                item.menu_id = menu.id
