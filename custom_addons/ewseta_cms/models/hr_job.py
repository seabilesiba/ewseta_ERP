# -*- coding: utf-8 -*-

from odoo import fields, models


class HrJob(models.Model):
    _inherit = 'hr.job'

    closing_date = fields.Date(string='Closing Date')
