# -*- coding: utf-8 -*-

from odoo import api, fields, models


class EwsetaPerformanceMetric(models.Model):
    _name = 'ewseta.performance.metric'
    _description = 'EWSETA Performance Overview Metric'
    _inherit = ['mail.thread', 'website.published.multi.mixin']
    _order = 'sequence, id'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    value = fields.Char(required=True, string='Metric Value')
    label = fields.Char(required=True, string='Metric Label')
    description = fields.Text(string='Supporting Text')
    progress = fields.Float(
        string='Progress (%)',
        help='Optional progress bar (0–100). Leave at 0 to hide the bar.',
    )
    progress_label = fields.Char(
        string='Progress Label',
        help='Optional caption under the progress bar, e.g. "82% of annual target".',
    )
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
    icon_class = fields.Char(string='Icon Class', default='fa-line-chart')
    website_id = fields.Many2one(
        'website',
        ondelete='restrict',
        default=lambda self: self.env.ref('website.default_website', raise_if_not_found=False),
    )

    @api.model
    def seed_default_metrics(self):
        from odoo.addons.ewseta_cms.hooks import _seed_performance_content
        website = self.env.ref('website.default_website', raise_if_not_found=False)
        if website:
            _seed_performance_content(self.env, website)
