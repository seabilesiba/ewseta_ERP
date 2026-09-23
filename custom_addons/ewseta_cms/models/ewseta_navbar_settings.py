# -*- coding: utf-8 -*-

from urllib.parse import quote

from odoo import api, fields, models


class EwsetaNavbarSettings(models.Model):
    _name = 'ewseta.navbar.settings'
    _description = 'EWSETA Navbar Settings'
    _inherit = ['mail.thread']

    name = fields.Char(default='Navbar Settings', required=True)
    website_id = fields.Many2one(
        'website',
        ondelete='restrict',
        default=lambda self: self.env.ref('website.default_website', raise_if_not_found=False),
    )
    is_active = fields.Boolean(default=True)
    logo = fields.Binary(string='Logo Image')
    logo_filename = fields.Char()
    logo_alt = fields.Char(default='Energy & Water SETA')
    logo_width = fields.Integer(default=220)
    logo_height = fields.Integer(default=55)
    logo_static_url = fields.Char(
        default='/ewseta_web/static/img/ewseta_logo.png',
        help='Fallback logo path when no image is uploaded.',
    )
    cta_enabled = fields.Boolean(default=True, string='Show Contact Button')
    cta_label = fields.Char(default='Contact Us')
    cta_url = fields.Char(default='/contactus')
    search_enabled = fields.Boolean(default=True, string='Show Search Icon')
    header_phone_enabled = fields.Boolean(default=True, string='Show Header Phone')
    header_phone = fields.Char(default='+27 11 274-4700', string='Header Phone Display')
    header_phone_link = fields.Char(
        default='+27112744700',
        string='Header Phone Link',
        help='Used in tel: link, e.g. +27112744700',
    )
    whatsapp_enabled = fields.Boolean(default=True, string='Show WhatsApp Button')
    whatsapp_phone = fields.Char(
        string='WhatsApp Number',
        default='27112744700',
        help='International number, digits only (no + or spaces), e.g. 27112744700',
    )
    whatsapp_message = fields.Char(
        string='WhatsApp Pre-filled Message',
        default='Hello EWSETA, I would like to enquire about...',
    )

    _website_uniq = models.Constraint(
        'unique(website_id)',
        'Only one navbar settings record is allowed per website.',
    )

    @api.model
    def get_for_website(self, website_id=None):
        domain = [('is_active', '=', True)]
        if website_id:
            domain.append(('website_id', '=', website_id))
        return self.sudo().search(domain, limit=1)

    def _logo_web_url(self):
        self.ensure_one()
        if self.logo:
            return f'/web/image/ewseta.navbar.settings/{self.id}/logo'
        return self.logo_static_url or '/ewseta_web/static/img/ewseta_logo.png'

    def whatsapp_phone_digits(self):
        self.ensure_one()
        if not self.whatsapp_phone:
            return ''
        return ''.join(ch for ch in self.whatsapp_phone if ch.isdigit())

    def whatsapp_url(self):
        self.ensure_one()
        phone = self.whatsapp_phone_digits()
        if not phone:
            return '#'
        url = f'https://wa.me/{phone}'
        if self.whatsapp_message:
            url = f'{url}?text={quote(self.whatsapp_message)}'
        return url

    @api.model
    def seed_default_content(self):
        website = self.env.ref('website.default_website', raise_if_not_found=False)
        if not website:
            return
        existing = self.sudo().search([('website_id', '=', website.id)], limit=1)
        whatsapp_defaults = {
            'whatsapp_enabled': True,
            'whatsapp_phone': '27112744700',
            'whatsapp_message': 'Hello EWSETA, I would like to enquire about...',
        }
        if existing:
            to_write = {
                key: val
                for key, val in whatsapp_defaults.items()
                if not existing[key]
            }
            if to_write:
                existing.write(to_write)
            return
        self.sudo().create({
            'name': 'Navbar Settings',
            'website_id': website.id,
            'is_active': True,
            'logo_alt': 'Energy & Water SETA',
            'logo_static_url': '/ewseta_web/static/img/ewseta_logo.png',
            'cta_enabled': True,
            'cta_label': 'Contact Us',
            'cta_url': '/contactus',
            'search_enabled': True,
            'header_phone_enabled': True,
            'header_phone': '+27 11 274-4700',
            'header_phone_link': '+27112744700',
            **whatsapp_defaults,
        })
