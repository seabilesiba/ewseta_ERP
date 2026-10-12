from odoo import fields, models


class EwServiceCategory(models.Model):
    _name = "ew.service.category"
    _description = "Service provider category"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
