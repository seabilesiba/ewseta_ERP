# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class EwsetaNewsArticle(models.Model):
    _name = 'ewseta.news.article'
    _description = 'EWSETA News Article'
    _inherit = ['mail.thread', 'website.seo.metadata', 'website.published.multi.mixin']
    _order = 'publish_date desc, id desc'

    name = fields.Char(string='Title', required=True, tracking=True)
    subtitle = fields.Char()
    body = fields.Html(sanitize_attributes=False)
    featured_image = fields.Image(string='Featured Image')
    featured_image_url = fields.Char(
        string='Featured Image URL',
        help='Static image path when no uploaded image is set.',
    )
    publish_date = fields.Date(default=fields.Date.context_today, required=True)
    is_featured = fields.Boolean(string='Featured on Homepage')
    slug = fields.Char(copy=False, index=True)
    website_id = fields.Many2one(
        'website',
        ondelete='restrict',
        default=lambda self: self.env.ref('website.default_website', raise_if_not_found=False),
    )
    website_url = fields.Char(compute='_compute_website_url', store=False)

    _slug_website_uniq = models.Constraint(
        'unique(slug, website_id)',
        'The news article slug must be unique per website.',
    )

    @api.depends('slug', 'website_id')
    def _compute_website_url(self):
        for article in self:
            if article.slug:
                article.website_url = '/news/%s' % article.slug
            else:
                article.website_url = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('slug') and vals.get('name'):
                vals['slug'] = self._generate_slug(vals['name'], vals.get('website_id'))
        return super().create(vals_list)

    def write(self, vals):
        if 'name' in vals and 'slug' not in vals:
            for record in self:
                if not record.slug:
                    vals['slug'] = self._generate_slug(vals['name'], record.website_id.id)
                    break
        return super().write(vals)

    @api.model
    def _generate_slug(self, name, website_id=None):
        slug = self.env['ir.http']._slugify(name or '')
        if not slug:
            raise ValidationError('Could not generate a URL slug from the title.')
        base_slug = slug
        counter = 1
        while self.search_count([('slug', '=', slug), ('website_id', '=', website_id)]):
            slug = '%s-%s' % (base_slug, counter)
            counter += 1
        return slug

    def _featured_image_web_url(self):
        self.ensure_one()
        if self.featured_image:
            return '/web/image/ewseta.news.article/%s/featured_image' % self.id
        return self.featured_image_url or False

    def _featured_image_style(self):
        self.ensure_one()
        url = self._featured_image_web_url()
        if not url:
            return ''
        return "background-image: url('%s'); background-size: cover; background-position: center;" % url
