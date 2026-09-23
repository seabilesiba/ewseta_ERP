# -*- coding: utf-8 -*-

from odoo import api, fields, models


class EwsetaHomeStat(models.Model):
    _name = 'ewseta.home.stat'
    _description = 'EWSETA Welcome Section Statistic'
    _order = 'sequence, id'

    welcome_id = fields.Many2one(
        'ewseta.home.welcome',
        required=True,
        ondelete='cascade',
    )
    sequence = fields.Integer(default=10)
    value = fields.Char(required=True)
    label = fields.Char(required=True)
    description = fields.Text()
    color = fields.Selection(
        selection=[
            ('orange', 'Orange'),
            ('blue', 'Blue'),
            ('green', 'Green'),
            ('dark', 'Dark'),
        ],
        default='orange',
        required=True,
    )
    display_mode = fields.Selection(
        selection=[
            ('number', 'Number'),
            ('icon', 'Icon'),
        ],
        default='number',
        required=True,
    )
    icon_class = fields.Char(string='Icon Class', default='fa-map-marker')


class EwsetaHomeWelcome(models.Model):
    _name = 'ewseta.home.welcome'
    _description = 'EWSETA Welcome Section'
    _inherit = ['mail.thread', 'website.published.multi.mixin']

    name = fields.Char(default='Welcome Section', required=True)
    eyebrow = fields.Char()
    title = fields.Char(
        required=True,
        string='Hero Title',
        help='Main heading in the hero carousel (first homepage section).',
    )
    section_title = fields.Char(
        string='About Section Title',
        default='About Us',
        help='Heading for the second homepage section (Who We Are / statistics).',
    )
    body = fields.Html(sanitize_attributes=False)
    cta_label = fields.Char(string='Button Label')
    cta_url = fields.Char(string='Button URL')
    hero_circle_image = fields.Image(string='Main Circle Image')
    hero_circle_image_url = fields.Char(
        string='Main Circle Image URL',
        help='Large centre circle. Upload an image or set a static path.',
    )
    hero_circle_web_url = fields.Char(compute='_compute_hero_image_web_urls')
    hero_overlap_image = fields.Image(string='Small Circle Image')
    hero_overlap_image_url = fields.Char(
        string='Small Circle Image URL',
        help='Southwest small circle overlapping the main hero photo. '
             'Upload an image or set a static path.',
    )
    hero_overlap_web_url = fields.Char(compute='_compute_hero_image_web_urls')
    hero_featured_portrait_image = fields.Image(string='Right Portrait Circle Image')
    hero_featured_portrait_image_url = fields.Char(
        string='Right Portrait Circle Image URL',
        help='Large circle on the right of the hero visual. '
             'Upload an image or set a static path.',
    )
    hero_featured_portrait_web_url = fields.Char(compute='_compute_hero_image_web_urls')
    hero_featured_portrait_url = fields.Char(
        string='Right Portrait Link URL',
        help='Optional link when visitors click the right portrait circle.',
    )
    stat_ids = fields.One2many('ewseta.home.stat', 'welcome_id', string='Statistics')
    website_id = fields.Many2one(
        'website',
        ondelete='restrict',
        default=lambda self: self.env.ref('website.default_website', raise_if_not_found=False),
    )

    _website_uniq = models.Constraint(
        'unique(website_id)',
        'Only one welcome section is allowed per website.',
    )

    @api.depends(
        'hero_circle_image', 'hero_circle_image_url',
        'hero_overlap_image', 'hero_overlap_image_url',
        'hero_featured_portrait_image', 'hero_featured_portrait_image_url',
    )
    def _compute_hero_image_web_urls(self):
        for welcome in self:
            if welcome.hero_circle_image:
                welcome.hero_circle_web_url = '/web/image/ewseta.home.welcome/%s/hero_circle_image' % welcome.id
            else:
                welcome.hero_circle_web_url = welcome.hero_circle_image_url or '/ewseta_web/static/img/hero_energy.jpg'
            if welcome.hero_overlap_image:
                welcome.hero_overlap_web_url = '/web/image/ewseta.home.welcome/%s/hero_overlap_image' % welcome.id
            else:
                welcome.hero_overlap_web_url = welcome.hero_overlap_image_url or '/ewseta_web/static/img/hero_water.jpg'
            if welcome.hero_featured_portrait_image:
                welcome.hero_featured_portrait_web_url = (
                    '/web/image/ewseta.home.welcome/%s/hero_featured_portrait_image' % welcome.id
                )
            else:
                welcome.hero_featured_portrait_web_url = (
                    welcome.hero_featured_portrait_image_url or '/ewseta_web/static/img/hero_sustainability.jpg'
                )

    @api.model
    def get_for_website(self, website_id=None):
        domain = [('is_published', '=', True)]
        if website_id:
            domain.append(('website_id', '=', website_id))
        return self.sudo().search(domain, limit=1)

    @api.model
    def migrate_welcome_title_revert(self):
        """Ensure the about section title is set on existing welcome records."""
        welcomes = self.sudo().search([])
        for welcome in welcomes:
            if not welcome.section_title:
                welcome.write({'section_title': 'About Us'})
        return True
