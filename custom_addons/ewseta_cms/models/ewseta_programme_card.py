# -*- coding: utf-8 -*-

from odoo import fields, models


class EwsetaProgrammeCard(models.Model):
    _name = 'ewseta.programme.card'
    _description = 'EWSETA Programme Card'
    _inherit = ['mail.thread', 'website.published.multi.mixin']
    _order = 'sequence, id'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    icon = fields.Selection(
        selection=[
            ('fa-graduation-cap', 'Graduation Cap'),
            ('fa-handshake-o', 'Handshake'),
            ('fa-users', 'Users'),
            ('fa-certificate', 'Certificate'),
            ('fa-book', 'Book'),
            ('fa-lightbulb-o', 'Lightbulb'),
            ('fa-line-chart', 'Chart'),
            ('fa-cogs', 'Cogs'),
            ('fa-money', 'Money'),
        ],
        default='fa-graduation-cap',
        required=True,
    )
    icon_color = fields.Selection(
        selection=[
            ('orange', 'Orange'),
            ('blue', 'Blue'),
            ('green', 'Green'),
        ],
        default='orange',
        required=True,
    )
    title = fields.Char(required=True)
    description = fields.Html(sanitize_attributes=False)
    link_label = fields.Char(string='Link Label')
    link_url = fields.Char(string='Link URL')
    website_id = fields.Many2one(
        'website',
        ondelete='restrict',
        default=lambda self: self.env.ref('website.default_website', raise_if_not_found=False),
    )
