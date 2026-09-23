# -*- coding: utf-8 -*-

from odoo import api, fields, models


class WebsiteMenu(models.Model):
    _inherit = 'website.menu'

    is_published = fields.Boolean(default=True, string='Published')

    @api.depends('page_id', 'controller_page_id', 'is_published')
    def _compute_visible(self):
        super()._compute_visible()
        for menu in self:
            if not menu.is_published:
                menu.is_visible = False

    def _is_active(self):
        """Placeholder menu URLs must not highlight on the current page."""
        self.ensure_one()
        if not self.child_id and not self.is_mega_menu:
            url = (self.url or '').strip()
            if url in ('#', '#top', '#bottom'):
                return False
        return super()._is_active()

    @api.model
    def ewseta_fix_menu_urls(self):
        """Restore real URLs for menu items saved as placeholder '#'."""
        website = self.env.ref('website.default_website', raise_if_not_found=False)
        if not website:
            return
        url_map = {
            'Power Up': '/power-up',
        }
        for name, url in url_map.items():
            menus = self.sudo().search([
                ('website_id', '=', website.id),
                ('name', '=', name),
                ('url', '=', '#'),
            ])
            menus.write({'url': url})

    @api.model
    def ewseta_restructure_nav_menus(self):
        """Consolidate navbar to five top-level items with card mega menus."""
        from odoo.addons.ewseta_web.hooks import (
            MEGA_MENU_CONTENT,
            NAV_MENU_SEQUENCE,
            REMOVED_TOP_LEVEL_MENUS,
        )

        website = self.env.ref('website.default_website', raise_if_not_found=False)
        if not website or not website.menu_id:
            return

        Menu = self.sudo()
        main_menu = website.menu_id
        allowed_names = set(NAV_MENU_SEQUENCE)

        for name in REMOVED_TOP_LEVEL_MENUS:
            menus = Menu.search([
                ('parent_id', '=', main_menu.id),
                ('website_id', '=', website.id),
                ('name', '=', name),
            ])
            for menu in menus:
                menu.child_id.unlink()
                menu.unlink()

        extra_menus = Menu.search([
            ('parent_id', '=', main_menu.id),
            ('website_id', '=', website.id),
            ('name', 'not in', list(allowed_names)),
        ])
        for menu in extra_menus:
            menu.child_id.unlink()
            menu.unlink()

        top_level = Menu.search([
            ('parent_id', '=', main_menu.id),
            ('website_id', '=', website.id),
        ])

        for name, sequence in NAV_MENU_SEQUENCE.items():
            menu = top_level.filtered(lambda item: item.name == name)[:1]
            if not menu:
                continue
            vals = {'sequence': sequence, 'is_published': True}
            if name == 'Home':
                vals['url'] = '/'
            elif name == 'Contact Us':
                vals['url'] = '/contactus'
            elif name in MEGA_MENU_CONTENT:
                vals['mega_menu_content'] = MEGA_MENU_CONTENT[name]
            menu.write(vals)
