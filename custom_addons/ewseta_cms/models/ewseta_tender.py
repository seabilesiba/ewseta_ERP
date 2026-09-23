# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class EwsetaTender(models.Model):
    _name = 'ewseta.tender'
    _description = 'EWSETA Tender'
    _inherit = ['mail.thread', 'website.seo.metadata', 'website.published.multi.mixin']
    _order = 'closing_date desc, id desc'

    reference = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: self.env['ir.sequence'].next_by_code('ewseta.tender') or 'NEW',
    )
    name = fields.Char(required=True, tracking=True)
    description = fields.Html(sanitize_attributes=False)
    closing_date = fields.Date(required=True)
    state = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('published', 'Published'),
            ('closed', 'Closed'),
        ],
        default='draft',
        required=True,
        tracking=True,
    )
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'ewseta_tender_attachment_rel',
        'tender_id',
        'attachment_id',
        string='Documents',
    )
    slug = fields.Char(copy=False, index=True)
    website_id = fields.Many2one(
        'website',
        ondelete='restrict',
        default=lambda self: self.env.ref('website.default_website', raise_if_not_found=False),
    )
    website_url = fields.Char(compute='_compute_website_url', store=False)

    _slug_website_uniq = models.Constraint(
        'unique(slug, website_id)',
        'The tender slug must be unique per website.',
    )

    @api.depends('slug')
    def _compute_website_url(self):
        for tender in self:
            tender.website_url = '/tenders/%s' % tender.slug if tender.slug else False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('slug') and vals.get('name'):
                vals['slug'] = self._generate_slug(vals['name'], vals.get('website_id'))
        records = super().create(vals_list)
        for record, vals in zip(records, vals_list):
            if vals.get('state') == 'published':
                record.is_published = True
        return records

    def write(self, vals):
        if 'name' in vals and 'slug' not in vals:
            for record in self:
                if not record.slug:
                    vals['slug'] = self._generate_slug(vals['name'], record.website_id.id)
                    break
        res = super().write(vals)
        if 'state' in vals:
            for record in self:
                record.is_published = record.state == 'published'
        return res

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

    def action_publish(self):
        self.write({'state': 'published', 'is_published': True})

    def action_close(self):
        self.write({'state': 'closed', 'is_published': False})

    def action_draft(self):
        self.write({'state': 'draft', 'is_published': False})
