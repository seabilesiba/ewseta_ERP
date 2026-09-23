# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MaintenanceEquipment(models.Model):
    _inherit = 'maintenance.equipment'

    ASSET_STATES = [
        ('available', 'Available'),
        ('assigned', 'Assigned'),
        ('in_repair', 'In Repair'),
        ('disposed', 'Disposed'),
        ('lost', 'Lost'),
    ]
    ASSET_TYPES = [
        ('hardware', 'Hardware'),
        ('software', 'Software'),
        ('peripheral', 'Peripheral'),
    ]

    asset_code = fields.Char(
        string='Asset Tag',
        copy=False,
        readonly=True,
        index=True,
        default=lambda self: _('New'),
    )
    asset_state = fields.Selection(
        selection=ASSET_STATES,
        string='Asset State',
        default='available',
        tracking=True,
        index=True,
    )
    asset_type = fields.Selection(
        selection=ASSET_TYPES,
        string='Asset Type',
        default='hardware',
        tracking=True,
    )
    purchase_date = fields.Date(string='Purchase Date', tracking=True)
    purchase_value = fields.Monetary(
        string='Purchase Value',
        currency_field='company_currency_id',
        tracking=True,
    )
    company_currency_id = fields.Many2one(
        related='company_id.currency_id',
        string='Company Currency',
    )
    location_note = fields.Char(string='Location', tracking=True)
    manufacturer_id = fields.Many2one(
        'it.asset.manufacturer',
        string='Manufacturer',
        tracking=True,
        help='IT asset manufacturer (e.g. Dell, HP, Lenovo).',
    )
    disposal_date = fields.Date(string='Disposal Date', tracking=True)
    disposal_reason = fields.Text(string='Disposal Reason')

    hostname = fields.Char(string='Hostname', tracking=True, index=True)
    mac_address = fields.Char(string='MAC Address', tracking=True)
    ip_address = fields.Char(string='IP Address')
    operating_system = fields.Char(string='Operating System', tracking=True)
    os_version = fields.Char(string='OS Version')
    cpu = fields.Char(string='CPU')
    ram_gb = fields.Integer(string='RAM (GB)')
    storage_gb = fields.Integer(string='Storage (GB)')
    license_key = fields.Char(string='License Key')
    license_expiry = fields.Date(string='License Expiry')
    image_1920 = fields.Image(string='Asset Image', max_width=1920, max_height=1920)
    image_128 = fields.Image(
        string='Asset Image (128)',
        related='image_1920',
        max_width=128,
        max_height=128,
        store=True,
    )

    assignment_history_ids = fields.One2many(
        'it.asset.assignment.history',
        'equipment_id',
        string='Assignment History',
    )
    assignment_history_count = fields.Integer(
        compute='_compute_assignment_history_count',
        string='Assignment History Count',
    )
    incident_report_ids = fields.One2many(
        'it.asset.incident.report',
        'equipment_id',
        string='Incident Reports',
    )
    incident_report_count = fields.Integer(
        compute='_compute_incident_report_count',
        string='Incident Report Count',
    )

    @api.depends('assignment_history_ids')
    def _compute_assignment_history_count(self):
        for equipment in self:
            equipment.assignment_history_count = len(equipment.assignment_history_ids)

    @api.depends('incident_report_ids')
    def _compute_incident_report_count(self):
        for equipment in self:
            equipment.incident_report_count = len(equipment.incident_report_ids)

    @api.constrains('hostname', 'company_id')
    def _check_hostname_unique(self):
        for equipment in self.filtered('hostname'):
            duplicate = self.search([
                ('id', '!=', equipment.id),
                ('hostname', '=', equipment.hostname),
                ('company_id', '=', equipment.company_id.id),
            ], limit=1)
            if duplicate:
                raise UserError(_(
                    'Hostname "%(hostname)s" is already used by asset %(asset)s.',
                    hostname=equipment.hostname,
                    asset=duplicate.display_name,
                ))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('asset_code', _('New')) == _('New'):
                vals['asset_code'] = self.env['ir.sequence'].next_by_code('it.asset.management') or _('New')
        equipments = super().create(vals_list)
        for equipment in equipments:
            equipment._sync_asset_state_from_assignment()
            if equipment.employee_id or equipment.department_id:
                equipment._create_assignment_history()
        return equipments

    def write(self, vals):
        track_assignment = 'employee_id' in vals or 'department_id' in vals or 'equipment_assign_to' in vals
        before = {}
        if track_assignment:
            before = {
                equipment.id: {
                    'employee_id': equipment.employee_id.id,
                    'department_id': equipment.department_id.id,
                }
                for equipment in self
            }

        if vals.get('asset_state') in ('disposed', 'lost'):
            vals.setdefault('employee_id', False)
            vals.setdefault('department_id', False)

        if 'employee_id' in vals or 'department_id' in vals:
            if not vals.get('asset_state'):
                new_employee = vals.get('employee_id')
                new_department = vals.get('department_id')
                if new_employee or new_department:
                    vals['asset_state'] = 'assigned'
                elif new_employee is False and new_department is False:
                    vals['asset_state'] = 'available'

        result = super().write(vals)

        if track_assignment:
            for equipment in self:
                previous = before.get(equipment.id, {})
                if (
                    previous.get('employee_id') != equipment.employee_id.id
                    or previous.get('department_id') != equipment.department_id.id
                ):
                    equipment._close_open_assignment_history()
                    if equipment.employee_id or equipment.department_id:
                        equipment._create_assignment_history()
                    elif equipment.asset_state not in ('disposed', 'lost', 'in_repair'):
                        equipment.asset_state = 'available'

        if vals.get('asset_state') == 'disposed' and 'disposal_date' not in vals:
            self.filtered(lambda e: not e.disposal_date).write({
                'disposal_date': fields.Date.context_today(self),
            })

        return result

    def _sync_asset_state_from_assignment(self):
        for equipment in self:
            if equipment.asset_state in ('disposed', 'lost', 'in_repair'):
                continue
            if equipment.employee_id or equipment.department_id:
                equipment.asset_state = 'assigned'
            else:
                equipment.asset_state = 'available'

    def _close_open_assignment_history(self):
        open_history = self.env['it.asset.assignment.history'].search([
            ('equipment_id', 'in', self.ids),
            ('return_date', '=', False),
        ])
        open_history.write({'return_date': fields.Date.context_today(self)})

    def _create_assignment_history(self):
        History = self.env['it.asset.assignment.history']
        for equipment in self:
            if not equipment.employee_id and not equipment.department_id:
                continue
            History.create({
                'equipment_id': equipment.id,
                'employee_id': equipment.employee_id.id,
                'department_id': equipment.department_id.id,
                'assign_date': equipment.assign_date or fields.Date.context_today(equipment),
                'assigned_by': self.env.user.id,
            })

    def action_return_asset(self):
        self.ensure_one()
        if self.asset_state in ('disposed', 'lost'):
            raise UserError(_('Cannot return a disposed or lost asset.'))
        self.write({
            'employee_id': False,
            'department_id': False,
            'equipment_assign_to': 'other',
            'asset_state': 'available',
        })

    def action_mark_in_repair(self):
        self.write({'asset_state': 'in_repair'})

    def action_mark_disposed(self):
        self.write({
            'asset_state': 'disposed',
            'employee_id': False,
            'department_id': False,
            'disposal_date': fields.Date.context_today(self),
        })

    def action_open_assignment_history(self):
        self.ensure_one()
        return {
            'name': _('Assignment History'),
            'type': 'ir.actions.act_window',
            'res_model': 'it.asset.assignment.history',
            'view_mode': 'list,form',
            'domain': [('equipment_id', '=', self.id)],
            'context': {'default_equipment_id': self.id},
        }
