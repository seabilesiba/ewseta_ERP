# -*- coding: utf-8 -*-

from odoo import fields, models


class ItAssetAssignmentHistory(models.Model):
    _name = 'it.asset.assignment.history'
    _description = 'IT Asset Assignment History'
    _inherit = ['mail.thread']
    _order = 'assign_date desc, id desc'

    equipment_id = fields.Many2one(
        'maintenance.equipment',
        string='IT Asset',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True,
        help='The asset that was assigned or returned.',
    )
    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        index=True,
        tracking=True,
        help='Employee who received the asset during this assignment period.',
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        index=True,
        tracking=True,
        help='Department that held the asset during this assignment period.',
    )
    assign_date = fields.Date(
        string='Assigned On',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
        help='Date the asset was handed over to the employee or department.',
    )
    return_date = fields.Date(
        string='Returned On',
        tracking=True,
        help='Date the asset was collected back. Empty while still assigned.',
    )
    assigned_by = fields.Many2one(
        'res.users',
        string='Assigned By',
        default=lambda self: self.env.user,
        tracking=True,
        help='User who performed the assignment.',
    )
    notes = fields.Text(
        string='Notes',
        tracking=True,
        help='Optional comments about this assignment (e.g. condition at handover).',
    )
    company_id = fields.Many2one(
        related='equipment_id.company_id',
        store=True,
        readonly=True,
        help='Company that owns the asset.',
    )
