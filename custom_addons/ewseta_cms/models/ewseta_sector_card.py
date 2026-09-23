# -*- coding: utf-8 -*-

from odoo import fields, models


class EwsetaSectorCard(models.Model):
    _name = 'ewseta.sector.card'
    _description = 'EWSETA Sector Card'
    _inherit = ['mail.thread', 'website.published.multi.mixin']
    _order = 'sequence, id'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    title = fields.Char(required=True)
    description = fields.Text()
    image = fields.Image(string='Background Image')
    image_url = fields.Char(
        string='Background Image URL',
        help='Static image path when no uploaded image is set.',
    )
    icon = fields.Selection(
        selection=[
            ('fa-bolt', 'Energy'),
            ('fa-tint', 'Water'),
            ('fa-leaf', 'Sustainability'),
            ('fa-sun-o', 'Sun'),
            ('fa-recycle', 'Recycle'),
        ],
        default='fa-bolt',
        required=True,
    )
    css_class = fields.Char(
        string='Theme Class',
        help='CSS modifier class, e.g. ewseta-sector-energy',
    )
    link_label = fields.Char(string='Link Label')
    link_url = fields.Char(string='Link URL')
    website_id = fields.Many2one(
        'website',
        ondelete='restrict',
        default=lambda self: self.env.ref('website.default_website', raise_if_not_found=False),
    )

    def _image_web_url(self):
        self.ensure_one()
        if self.image:
            return '/web/image/ewseta.sector.card/%s/image' % self.id
        return self.image_url or False

    def _background_image_style(self):
        self.ensure_one()
        url = self._image_web_url()
        if not url:
            return ''
        return "background-image: url('%s');" % url

    def _card_css_class(self):
        self.ensure_one()
        return 'ewseta-sector-card %s' % (self.css_class or 'ewseta-sector-energy')
