# -*- coding: utf-8 -*-

from odoo import api, fields, models


class HrDepartment(models.Model):
    _inherit = 'hr.department'

    it_asset_count = fields.Integer(
        string='IT Assets',
        compute='_compute_it_asset_count',
        help='Number of active IT assets assigned to this department (excludes disposed).',
    )

    @api.depends('member_ids')
    def _compute_it_asset_count(self):
        Equipment = self.env['maintenance.equipment']
        for department in self:
            department.it_asset_count = Equipment.search_count([
                ('department_id', '=', department.id),
                ('asset_state', '!=', 'disposed'),
            ])

    def action_open_it_assets(self):
        self.ensure_one()
        return {
            'name': self.env._('IT Assets'),
            'type': 'ir.actions.act_window',
            'res_model': 'maintenance.equipment',
            'view_mode': 'kanban,list,form',
            'domain': [('department_id', '=', self.id)],
            'context': {
                'default_department_id': self.id,
                'default_equipment_assign_to': 'department',
                'default_asset_state': 'assigned',
            },
        }
