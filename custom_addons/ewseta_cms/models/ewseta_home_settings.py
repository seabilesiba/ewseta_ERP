# -*- coding: utf-8 -*-

from odoo import api, fields, models


class EwsetaHomeSettings(models.Model):
    _name = 'ewseta.home.settings'
    _description = 'EWSETA Homepage Section Headers'
    _inherit = ['mail.thread']

    name = fields.Char(default='Homepage Settings', required=True)
    website_id = fields.Many2one(
        'website',
        ondelete='restrict',
        default=lambda self: self.env.ref('website.default_website', raise_if_not_found=False),
    )
    programme_eyebrow = fields.Char(default='What We Offer')
    programme_title = fields.Char(default='Learning Programmes & Services')
    programme_lead = fields.Text()
    sector_eyebrow = fields.Char(default='Our Focus Areas')
    sector_title = fields.Char(default="Powering South Africa's Future")
    sector_lead = fields.Text()
    news_eyebrow = fields.Char(default='Stay Informed')
    news_title = fields.Char(default='Latest News')
    performance_eyebrow = fields.Char(default='Our Impact')
    performance_title = fields.Char(default='Performance Overview')
    performance_lead = fields.Text()
    performance_cta_label = fields.Char(string='Performance CTA Label')
    performance_cta_url = fields.Char(string='Performance CTA URL')

    _website_uniq = models.Constraint(
        'unique(website_id)',
        'Only one homepage settings record is allowed per website.',
    )

    @api.model
    def get_for_website(self, website_id=None):
        domain = []
        if website_id:
            domain.append(('website_id', '=', website_id))
        return self.sudo().search(domain, limit=1)
