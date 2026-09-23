# -*- coding: utf-8 -*-

from odoo import fields, models


class ItAssetManufacturer(models.Model):
    _name = 'it.asset.manufacturer'
    _description = 'IT Asset Manufacturer'
    _inherit = ['mail.thread']
    _order = 'name'

    name = fields.Char(
        required=True,
        translate=True,
        tracking=True,
        help='Display name of the manufacturer (e.g. Dell, HP, Apple).',
    )
    code = fields.Char(
        string='Code',
        tracking=True,
        help='Short internal code for reports and imports (e.g. DELL, HP).',
    )
    active = fields.Boolean(
        default=True,
        tracking=True,
        help='Uncheck to archive this manufacturer without deleting it.',
    )
    website = fields.Char(
        string='Website',
        tracking=True,
        help='Manufacturer website URL for support or product lookup.',
    )
    image_1920 = fields.Image(
        string='Logo',
        max_width=1920,
        max_height=1920,
        tracking=True,
        help='Manufacturer logo displayed on forms and lists.',
    )
    image_128 = fields.Image(
        string='Logo (128)',
        related='image_1920',
        max_width=128,
        max_height=128,
        store=True,
        help='Small thumbnail of the manufacturer logo.',
    )
    equipment_count = fields.Integer(
        compute='_compute_equipment_count',
        string='Assets',
        help='Number of IT assets linked to this manufacturer.',
    )

    _sql_constraints = [
        ('name_uniq', 'unique(name)', 'Manufacturer name must be unique.'),
    ]

    def _compute_equipment_count(self):
        grouped = self.env['maintenance.equipment']._read_group(
            [('manufacturer_id', 'in', self.ids)],
            ['manufacturer_id'],
            ['__count'],
        )
        counts = {manufacturer.id: count for manufacturer, count in grouped}
        for manufacturer in self:
            manufacturer.equipment_count = counts.get(manufacturer.id, 0)
