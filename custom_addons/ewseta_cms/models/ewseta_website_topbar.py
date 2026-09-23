# -*- coding: utf-8 -*-

from odoo import api, fields, models


class EwsetaWebsiteTopbar(models.Model):
    _name = 'ewseta.website.topbar'
    _description = 'EWSETA Website Top Bar'
    _inherit = ['mail.thread']

    name = fields.Char(default='Website Top Bar', required=True)
    website_id = fields.Many2one(
        'website',
        ondelete='restrict',
        default=lambda self: self.env.ref('website.default_website', raise_if_not_found=False),
    )
    is_active = fields.Boolean(default=True)
    hotline_label = fields.Char(default='Fraud Hotline')
    hotline_phone = fields.Char(default='0800 611 205')
    hotline_phone_link = fields.Char(
        default='0800611205',
        help='Digits only for tel: link, e.g. 0800611205',
    )
    hotline_meta = fields.Char(default='Toll Free')
    hours_menu_label = fields.Char(default='Opening Hours')
    hours_title = fields.Char(default='Head Office')
    hours_address = fields.Text(default='22 Wellington Road, Parktown, Johannesburg')
    hours_note = fields.Char(default='Closed on public holidays.')
    social_label = fields.Char(default='Follow us')
    link_ids = fields.One2many('ewseta.topbar.link', 'topbar_id', string='Quick Links')
    hours_line_ids = fields.One2many('ewseta.topbar.hours.line', 'topbar_id', string='Opening Hours')
    social_ids = fields.One2many('ewseta.topbar.social', 'topbar_id', string='Social Links')

    _website_uniq = models.Constraint(
        'unique(website_id)',
        'Only one top bar settings record is allowed per website.',
    )

    @api.model
    def get_for_website(self, website_id=None):
        domain = [('is_active', '=', True)]
        if website_id:
            domain.append(('website_id', '=', website_id))
        return self.sudo().search(domain, limit=1)

    @api.model
    def seed_default_content(self):
        """Create default top bar content when missing (install/upgrade)."""
        website = self.env.ref('website.default_website', raise_if_not_found=False)
        if not website or self.sudo().search_count([('website_id', '=', website.id)]):
            return
        self.sudo().create({
            'name': 'Website Top Bar',
            'website_id': website.id,
            'is_active': True,
            'hotline_label': 'Fraud Hotline',
            'hotline_phone': '0800 611 205',
            'hotline_phone_link': '0800611205',
            'hotline_meta': 'Toll Free',
            'hours_menu_label': 'Opening Hours',
            'hours_title': 'Head Office',
            'hours_address': '22 Wellington Road, Parktown, Johannesburg',
            'hours_note': 'Closed on public holidays.',
            'social_label': 'Follow us',
            'link_ids': [
                (0, 0, {
                    'sequence': 10,
                    'label': 'ewseta@thehotline.co.za',
                    'url': 'mailto:ewseta@thehotline.co.za',
                    'icon': 'fa-envelope',
                }),
                (0, 0, {
                    'sequence': 20,
                    'label': 'Contact Us',
                    'url': '/contactus',
                    'icon': 'fa-comments',
                }),
                (0, 0, {
                    'sequence': 30,
                    'label': 'EWSETA Vacancies',
                    'url': '/jobs',
                    'icon': 'fa-briefcase',
                }),
            ],
            'hours_line_ids': [
                (0, 0, {'sequence': 10, 'day_label': 'Monday – Friday', 'time_label': '8:00 AM – 4:30 PM'}),
                (0, 0, {'sequence': 20, 'day_label': 'Saturday', 'time_label': 'Closed', 'is_closed': True}),
                (0, 0, {'sequence': 30, 'day_label': 'Sunday', 'time_label': 'Closed', 'is_closed': True}),
            ],
            'social_ids': [
                (0, 0, {'sequence': 10, 'network': 'fa-facebook', 'url': 'https://www.facebook.com/ewseta', 'label': 'Facebook'}),
                (0, 0, {'sequence': 20, 'network': 'fa-twitter', 'url': 'https://twitter.com/ewseta', 'label': 'X'}),
                (0, 0, {'sequence': 30, 'network': 'fa-instagram', 'url': 'https://www.instagram.com/ewseta', 'label': 'Instagram'}),
                (0, 0, {'sequence': 40, 'network': 'fa-linkedin', 'url': 'https://www.linkedin.com/company/ewseta', 'label': 'LinkedIn'}),
                (0, 0, {'sequence': 50, 'network': 'fa-youtube-play', 'url': 'https://www.youtube.com/ewseta', 'label': 'YouTube'}),
            ],
        })


class EwsetaTopbarLink(models.Model):
    _name = 'ewseta.topbar.link'
    _description = 'EWSETA Top Bar Link'
    _order = 'sequence, id'

    topbar_id = fields.Many2one('ewseta.website.topbar', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    label = fields.Char(required=True)
    url = fields.Char(required=True, help='Use mailto:, tel:, or a page path such as /contactus')
    icon = fields.Selection(
        selection=[
            ('fa-envelope', 'Email'),
            ('fa-comments', 'Contact'),
            ('fa-briefcase', 'Vacancies'),
            ('fa-phone', 'Phone'),
            ('fa-info-circle', 'Info'),
            ('fa-external-link', 'External'),
        ],
        default='fa-comments',
        required=True,
    )
    is_published = fields.Boolean(default=True)


class EwsetaTopbarHoursLine(models.Model):
    _name = 'ewseta.topbar.hours.line'
    _description = 'EWSETA Top Bar Opening Hours Line'
    _order = 'sequence, id'

    topbar_id = fields.Many2one('ewseta.website.topbar', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    day_label = fields.Char(required=True)
    time_label = fields.Char(required=True)
    is_closed = fields.Boolean(default=False)


class EwsetaTopbarSocial(models.Model):
    _name = 'ewseta.topbar.social'
    _description = 'EWSETA Top Bar Social Link'
    _order = 'sequence, id'

    topbar_id = fields.Many2one('ewseta.website.topbar', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    network = fields.Selection(
        selection=[
            ('fa-facebook', 'Facebook'),
            ('fa-twitter', 'X / Twitter'),
            ('fa-instagram', 'Instagram'),
            ('fa-linkedin', 'LinkedIn'),
            ('fa-youtube-play', 'YouTube'),
        ],
        required=True,
    )
    url = fields.Char(required=True)
    label = fields.Char(string='Accessibility Label', required=True)
    is_published = fields.Boolean(default=True)
