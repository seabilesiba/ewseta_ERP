# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ItAssetIncidentReport(models.Model):
    _name = 'it.asset.incident.report'
    _description = 'IT Asset Incident Report'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'discovered_datetime desc, id desc'

    STATES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('manager_approved', 'Line Manager Approved'),
        ('it_approved', 'IT Manager Approved'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled'),
    ]
    DATA_SENSITIVITY = [
        ('public', 'Public'),
        ('internal', 'Internal'),
        ('restricted', 'Restricted / Confidential'),
        ('unknown', 'Unknown'),
    ]
    ASSET_ACTIONS = [
        ('none', 'No Change'),
        ('in_repair', 'Mark Asset In Repair'),
        ('lost', 'Mark Asset Lost'),
    ]

    name = fields.Char(
        string='Reference',
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True,
        help='Unique incident reference (e.g. INC/2026/0001).',
    )
    state = fields.Selection(
        selection=STATES,
        string='Status',
        default='draft',
        tracking=True,
        index=True,
        copy=False,
        help='Current stage in the incident reporting and approval workflow.',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True,
        index=True,
        tracking=True,
    )

    # --- Contact ---
    reporter_employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        tracking=True,
        help='Employee reporting the incident. Defaults to the current user\'s employee record.',
    )
    reporter_name = fields.Char(
        string='Name',
        required=True,
        tracking=True,
        help='Full name of the person reporting the incident.',
    )
    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        tracking=True,
        help='Department of the person reporting the incident.',
    )
    work_phone = fields.Char(
        string='Work Phone',
        tracking=True,
        help='Work telephone number for follow-up.',
    )
    mobile_phone = fields.Char(
        string='Mobile Phone',
        tracking=True,
        help='Mobile telephone number for follow-up.',
    )
    email = fields.Char(
        string='Email',
        tracking=True,
        help='Email address for follow-up on this incident.',
    )

    # --- Asset ---
    equipment_id = fields.Many2one(
        'maintenance.equipment',
        string='IT Asset',
        tracking=True,
        index=True,
        help='Linked IT asset involved in the incident, if applicable.',
    )
    asset_description = fields.Char(
        related='equipment_id.name',
        string='Asset Description',
        readonly=True,
    )
    serial_no = fields.Char(
        related='equipment_id.serial_no',
        string='Serial Number',
        readonly=True,
    )
    asset_code = fields.Char(
        related='equipment_id.asset_code',
        string='EWSETA Asset Tag',
        readonly=True,
    )

    # --- Impact ---
    impact_data_loss = fields.Boolean(string='Data Loss', tracking=True)
    impact_system_damage = fields.Boolean(string='System Damage', tracking=True)
    impact_downtime = fields.Boolean(string='Downtime', tracking=True)
    impact_financial = fields.Boolean(string='Financial Loss', tracking=True)
    impact_other_orgs = fields.Boolean(string='Other Organisations Affected', tracking=True)
    impact_critical_services = fields.Boolean(string='Critical Services Affected', tracking=True)
    impact_legislation = fields.Boolean(string='Legislation Violation', tracking=True)
    impact_unknown = fields.Boolean(string='Impact Unknown', tracking=True)
    impact_description = fields.Text(
        string='Impact Description',
        tracking=True,
        help='Brief description of the impact caused by the incident.',
    )

    # --- Data sensitivity ---
    data_sensitivity = fields.Selection(
        selection=DATA_SENSITIVITY,
        string='Data Sensitivity',
        tracking=True,
        help='Classification of data involved in the incident.',
    )
    compromised_data_description = fields.Text(
        string='Compromised Data Description',
        tracking=True,
        help='Description of any data that may have been compromised.',
    )

    # --- Notifications ---
    notified_person = fields.Char(
        string='Person Notified',
        tracking=True,
        help='Name of any other person notified about this incident.',
    )
    notified_title = fields.Char(
        string='Title of Person Notified',
        tracking=True,
        help='Job title of the person notified.',
    )
    notification_notes = fields.Text(
        string='Additional Notifications',
        tracking=True,
        help='Other people or parties notified about the incident.',
    )

    # --- Steps taken ---
    step_no_action = fields.Boolean(string='No Action Taken', tracking=True)
    step_disconnected = fields.Boolean(string='Disconnected from Network', tracking=True)
    step_virus_scan = fields.Boolean(string='Virus Scan Performed', tracking=True)
    step_backup_restored = fields.Boolean(string='Backup Restored', tracking=True)
    step_logs_examined = fields.Boolean(string='Logs Examined', tracking=True)
    step_other = fields.Boolean(string='Other Steps', tracking=True)
    steps_description = fields.Text(
        string='Steps Description',
        tracking=True,
        help='Description of actions taken in response to the incident.',
    )

    # --- Incident details ---
    discovered_datetime = fields.Datetime(
        string='Date/Time Discovered',
        required=True,
        default=fields.Datetime.now,
        tracking=True,
        help='When the incident was first discovered.',
    )
    is_resolved = fields.Boolean(
        string='Incident Resolved',
        tracking=True,
        help='Whether the incident has been resolved at the time of reporting.',
    )
    location = fields.Char(
        string='Location',
        tracking=True,
        help='Physical location where the incident occurred or was discovered.',
    )
    sites_systems_users_affected = fields.Text(
        string='Sites / Systems / Users Affected',
        tracking=True,
        help='List of sites, systems, or users affected by the incident.',
    )
    additional_info = fields.Text(
        string='Additional Information',
        tracking=True,
        help='Any other relevant information about the incident.',
    )

    # --- Asset outcome ---
    asset_action = fields.Selection(
        selection=ASSET_ACTIONS,
        string='Asset Action',
        default='none',
        tracking=True,
        help='Action to apply to the linked asset when IT approves the report.',
    )

    # --- Signatures ---
    initiator_name = fields.Char(string='Initiator Name', readonly=True, copy=False, tracking=True)
    initiator_sign_date = fields.Datetime(string='Initiator Sign Date', readonly=True, copy=False, tracking=True)
    initiator_signature = fields.Image(
        string='Initiator Signature',
        max_width=1024,
        max_height=512,
        copy=False,
        attachment=True,
        readonly=True,
        help='Signature captured when the report was submitted to ICT Support.',
    )
    line_manager_id = fields.Many2one(
        'hr.employee',
        string='Line Manager',
        tracking=True,
        help='Line manager responsible for approving this report.',
    )
    line_manager_sign_date = fields.Datetime(string='Line Manager Sign Date', readonly=True, copy=False, tracking=True)
    line_manager_sign_name = fields.Char(string='Line Manager Sign Name', readonly=True, copy=False, tracking=True)
    line_manager_comment = fields.Text(
        string='Line Manager Comment',
        readonly=True,
        copy=False,
        tracking=True,
        help='Comment provided by the line manager when approving this report.',
    )
    line_manager_signature = fields.Image(
        string='Line Manager Signature',
        max_width=1024,
        max_height=512,
        copy=False,
        attachment=True,
        help='Signature captured when the line manager approved this report.',
    )
    it_manager_id = fields.Many2one(
        'res.users',
        string='IT Manager',
        readonly=True,
        copy=False,
        tracking=True,
        help='IT manager who approved this report.',
    )
    it_manager_sign_date = fields.Datetime(string='IT Manager Sign Date', readonly=True, copy=False, tracking=True)
    it_manager_sign_name = fields.Char(string='IT Manager Sign Name', readonly=True, copy=False, tracking=True)
    it_manager_comment = fields.Text(
        string='IT Manager Comment',
        readonly=True,
        copy=False,
        tracking=True,
        help='Comment provided by the IT manager when approving this report.',
    )
    it_manager_signature = fields.Image(
        string='IT Manager Signature',
        max_width=1024,
        max_height=512,
        copy=False,
        attachment=True,
        help='Signature captured when the IT manager approved this report.',
    )

    support_email = fields.Char(compute='_compute_support_email')

    @api.depends()
    def _compute_support_email(self):
        email = self.env['ir.config_parameter'].sudo().get_param(
            'it_asset_management.incident_support_email',
            'ictsupport@ewseta.org.za',
        )
        for report in self:
            report.support_email = email

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        employee = self.env.user.employee_id
        if employee and 'reporter_employee_id' in fields_list and not res.get('reporter_employee_id'):
            res['reporter_employee_id'] = employee.id
            res.update(self._contact_values_from_employee(employee))
        return res

    @api.model
    def _contact_values_from_employee(self, employee):
        return {
            'reporter_name': employee.name,
            'department_id': employee.department_id.id,
            'work_phone': employee.work_phone,
            'mobile_phone': employee.mobile_phone,
            'email': employee.work_email,
            'line_manager_id': employee.parent_id.id if employee.parent_id else False,
        }

    @api.onchange('reporter_employee_id')
    def _onchange_reporter_employee_id(self):
        if self.reporter_employee_id:
            self.update(self._contact_values_from_employee(self.reporter_employee_id))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('it.asset.incident.report') or _('New')
                )
        return super().create(vals_list)

    def _is_it_manager(self):
        self.ensure_one()
        return self.env.user.has_group('it_asset_management.group_it_asset_manager')

    def _is_line_manager(self):
        self.ensure_one()
        if self._is_it_manager():
            return True
        manager_user = self.line_manager_id.user_id
        return manager_user and manager_user == self.env.user

    def _check_reporter_or_manager(self):
        self.ensure_one()
        if self._is_it_manager():
            return
        if self.create_uid != self.env.user and self.state == 'draft':
            raise UserError(_('You can only edit your own draft incident reports.'))

    def _validate_submission(self):
        self.ensure_one()
        if not self.reporter_name:
            raise ValidationError(_('Reporter name is required before submitting.'))
        if not self.discovered_datetime:
            raise ValidationError(_('Date/time discovered is required before submitting.'))
        if not self.impact_description and not any([
            self.impact_data_loss, self.impact_system_damage, self.impact_downtime,
            self.impact_financial, self.impact_other_orgs, self.impact_critical_services,
            self.impact_legislation, self.impact_unknown,
        ]):
            raise ValidationError(_(
                'Select at least one impact type or provide an impact description.'
            ))

    def _schedule_manager_activity(self):
        self.ensure_one()
        if not self.line_manager_id or not self.line_manager_id.user_id:
            return
        self.activity_schedule(
            'mail.mail_activity_data_todo',
            user_id=self.line_manager_id.user_id.id,
            summary=_('Approve incident report %s', self.name),
        )

    def _schedule_it_activity(self):
        self.ensure_one()
        managers = self.env.ref('it_asset_management.group_it_asset_manager').user_ids
        if not managers:
            return
        self.activity_schedule(
            'mail.mail_activity_data_todo',
            user_id=managers[0].id,
            summary=_('IT approval required for incident %s', self.name),
        )

    def _apply_asset_action(self):
        self.ensure_one()
        if not self.equipment_id or self.asset_action == 'none':
            return
        equipment = self.equipment_id
        if self.asset_action == 'in_repair':
            equipment.action_mark_in_repair()
            message = _('Asset marked In Repair following incident %s.', self.name)
        elif self.asset_action == 'lost':
            equipment.action_mark_lost()
            message = _('Asset marked Lost following incident %s.', self.name)
        else:
            return
        equipment.message_post(body=message)
        self.message_post(body=_('Asset action applied: %s', dict(self.ASSET_ACTIONS)[self.asset_action]))

    def _send_support_email(self, report):
        template = self.env.ref(
            'it_asset_management.mail_template_it_incident_report',
            raise_if_not_found=False,
        )
        if not template:
            return
        try:
            template.send_mail(report.id, force_send=True)
        except UserError as err:
            if 'Wkhtmltopdf' not in str(err):
                raise
            generated = template._generate_template(
                [report.id],
                ['subject', 'body_html', 'email_to', 'email_from', 'model', 'res_id'],
            )
            values = generated[report.id]
            values['body'] = values.get('body_html', '')
            self.env['mail.mail'].sudo().create(values).send()
            report.message_post(body=_(
                'Incident report submitted to ICT Support. '
                'PDF attachment skipped (wkhtmltopdf not installed).'
            ))
        else:
            report.message_post(body=_('Incident report submitted to ICT Support.'))

    def action_submit(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Only draft reports can be submitted.'))
        self._check_reporter_or_manager()
        self._validate_submission()
        employee = self.env.user.employee_id
        return {
            'name': _('Submit to ICT Support'),
            'type': 'ir.actions.act_window',
            'res_model': 'it.asset.incident.submit.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_incident_id': self.id,
                'default_signer_name': self.reporter_name or (employee.name if employee else self.env.user.name),
            },
        }

    def _do_submit(self, signer_name, signature):
        self.ensure_one()
        if self.reporter_employee_id and self.reporter_employee_id.parent_id:
            self.line_manager_id = self.reporter_employee_id.parent_id
        self.write({
            'state': 'submitted',
            'initiator_name': signer_name,
            'initiator_signature': signature,
            'initiator_sign_date': fields.Datetime.now(),
        })
        self._send_support_email(self)
        self._schedule_manager_activity()
        self.message_post(body=_('Submitted and signed by: %s', signer_name))

    def action_manager_approve(self):
        self.ensure_one()
        if self.state != 'submitted':
            raise UserError(_('Only submitted reports can be approved by the line manager.'))
        if not self._is_line_manager():
            raise UserError(_('Only the assigned line manager or an IT Asset Manager can approve this step.'))
        employee = self.env.user.employee_id
        return {
            'name': _('Line Manager Approval'),
            'type': 'ir.actions.act_window',
            'res_model': 'it.asset.incident.approve.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_incident_id': self.id,
                'default_approval_type': 'line_manager',
                'default_signer_name': employee.name if employee else self.env.user.name,
            },
        }

    def _do_manager_approve(self, signer_name, signature, comment):
        self.ensure_one()
        if not self.line_manager_id and self.reporter_employee_id.parent_id:
            self.line_manager_id = self.reporter_employee_id.parent_id
        self.write({
            'state': 'manager_approved',
            'line_manager_sign_name': signer_name,
            'line_manager_signature': signature,
            'line_manager_comment': comment,
            'line_manager_sign_date': fields.Datetime.now(),
        })
        self.message_post(body=_(
            'Approved and signed by line manager: %(name)s<br/>Comment: %(comment)s',
            name=signer_name,
            comment=comment,
        ))
        self._schedule_it_activity()

    def action_it_approve(self):
        self.ensure_one()
        if self.state != 'manager_approved':
            raise UserError(_('Line manager approval is required before IT approval.'))
        if not self._is_it_manager():
            raise UserError(_('Only an IT Asset Manager can perform IT approval.'))
        return {
            'name': _('IT Manager Approval'),
            'type': 'ir.actions.act_window',
            'res_model': 'it.asset.incident.approve.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_incident_id': self.id,
                'default_approval_type': 'it_manager',
                'default_signer_name': self.env.user.name,
            },
        }

    def _do_it_approve(self, signer_name, signature, comment):
        self.ensure_one()
        self.write({
            'state': 'it_approved',
            'it_manager_id': self.env.user.id,
            'it_manager_sign_name': signer_name,
            'it_manager_signature': signature,
            'it_manager_comment': comment,
            'it_manager_sign_date': fields.Datetime.now(),
        })
        self._apply_asset_action()
        self.message_post(body=_(
            'Approved and signed by IT manager: %(name)s<br/>Comment: %(comment)s',
            name=signer_name,
            comment=comment,
        ))

    def action_resolve(self):
        for report in self:
            if report.state != 'it_approved':
                raise UserError(_('IT approval is required before resolving the incident.'))
            if not report._is_it_manager():
                raise UserError(_('Only an IT Asset Manager can mark the incident as resolved.'))
            report.write({'state': 'resolved', 'is_resolved': True})
            report.message_post(body=_('Incident marked as resolved.'))
        return True

    def action_close(self):
        for report in self:
            if report.state not in ('resolved', 'it_approved'):
                raise UserError(_('The incident must be resolved or IT-approved before closing.'))
            if not report._is_it_manager():
                raise UserError(_('Only an IT Asset Manager can close the incident.'))
            report.write({'state': 'closed'})
            report.message_post(body=_('Incident report closed.'))
        return True

    def action_cancel(self):
        for report in self:
            if report.state in ('closed', 'cancelled'):
                raise UserError(_('This incident report is already finished.'))
            if report.state != 'draft' and not report._is_it_manager():
                raise UserError(_('Only an IT Asset Manager can cancel a submitted report.'))
            report.write({'state': 'cancelled'})
            report.message_post(body=_('Incident report cancelled.'))
        return True

    def action_reset_draft(self):
        for report in self:
            if report.state != 'draft' and not report._is_it_manager():
                raise UserError(_('Only an IT Asset Manager can reset a report to draft.'))
            report.write({
                'state': 'draft',
                'initiator_name': False,
                'initiator_sign_date': False,
                'initiator_signature': False,
                'line_manager_sign_name': False,
                'line_manager_signature': False,
                'line_manager_comment': False,
                'line_manager_sign_date': False,
                'it_manager_id': False,
                'it_manager_sign_name': False,
                'it_manager_signature': False,
                'it_manager_comment': False,
                'it_manager_sign_date': False,
            })
        return True
