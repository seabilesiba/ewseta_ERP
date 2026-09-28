# -*- coding: utf-8 -*-

from odoo import fields, models


class EolApprovalLine(models.Model):
    _name = 'ew.eol.approval.line'
    _description = 'EOL Purchase Request Approval Decision'
    _order = 'decision_date desc, id desc'

    request_id = fields.Many2one(
        'ew.eol.purchase.request',
        required=True,
        ondelete='cascade',
        index=True,
    )
    approver_id = fields.Many2one(
        'res.users',
        string='Approver',
        required=True,
        default=lambda self: self.env.user,
        index=True,
    )
    decision = fields.Selection(
        [
            ('approve', 'Approved'),
            ('reject', 'Rejected'),
            ('return', 'Returned for correction'),
        ],
        required=True,
    )
    comment = fields.Text()
    decision_date = fields.Datetime(default=fields.Datetime.now, required=True)
