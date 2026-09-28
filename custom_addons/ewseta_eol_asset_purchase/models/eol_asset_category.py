# -*- coding: utf-8 -*-

from odoo import fields, models


class EolAssetCategory(models.Model):
    _name = 'ew.eol.asset.category'
    _description = 'EOL Asset Sale Category (public catalogue)'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    image_128 = fields.Image(max_width=128, max_height=128)
    default_price = fields.Monetary(string='Default Sale Price (ZAR)', currency_field='currency_id')
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.ref('base.ZAR', raise_if_not_found=False)
        or self.env.company.currency_id,
    )
    purchase_limit_count = fields.Integer(
        string='Max purchases per employee (period)',
        default=1,
        help='Rolling limit per employee for this category; 0 means use global setting only.',
    )
    description = fields.Html(translate=True)
    maintenance_category_id = fields.Many2one(
        'maintenance.equipment.category',
        string='Equipment category (pool matching)',
        help='When request type is pool, eligible equipment is matched from this maintenance category.',
    )

    _code_unique = models.Constraint(
        'unique(code)',
        'Category code must be unique.',
    )
