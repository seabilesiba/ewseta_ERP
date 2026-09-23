# -*- coding: utf-8 -*-

from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    it_asset_count = fields.Integer(
        string='IT Assets',
        compute='_compute_it_asset_count',
        help='Number of active IT assets currently assigned to this employee (excludes disposed).',
    )
    incident_report_ids = fields.One2many(
        'it.asset.incident.report',
        'reporter_employee_id',
        string='Incident Report Records',
    )
    incident_report_count = fields.Integer(
        string='Incident Reports',
        compute='_compute_incident_report_count',
        help='Number of incident reports filed by this employee.',
    )

    @api.depends('equipment_ids', 'equipment_ids.asset_state')
    def _compute_it_asset_count(self):
        Equipment = self.env['maintenance.equipment']
        for employee in self:
            employee.it_asset_count = Equipment.search_count([
                ('employee_id', '=', employee.id),
                ('asset_state', '!=', 'disposed'),
            ])

    @api.depends('incident_report_ids')
    def _compute_incident_report_count(self):
        for employee in self:
            employee.incident_report_count = len(employee.incident_report_ids)

    def action_open_it_assets(self):
        self.ensure_one()
        return {
            'name': self.env._('IT Assets'),
            'type': 'ir.actions.act_window',
            'res_model': 'maintenance.equipment',
            'view_mode': 'kanban,list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {
                'default_employee_id': self.id,
                'default_equipment_assign_to': 'employee',
                'default_asset_state': 'assigned',
            },
        }

    def action_open_incident_reports(self):
        self.ensure_one()
        return {
            'name': self.env._('Incident Reports'),
            'type': 'ir.actions.act_window',
            'res_model': 'it.asset.incident.report',
            'view_mode': 'list,form',
            'domain': [('reporter_employee_id', '=', self.id)],
            'context': {'default_reporter_employee_id': self.id},
        }
