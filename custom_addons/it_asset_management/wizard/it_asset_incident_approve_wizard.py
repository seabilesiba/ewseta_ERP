# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ItAssetIncidentApproveWizard(models.TransientModel):
    _name = 'it.asset.incident.approve.wizard'
    _description = 'Incident Report Approval Signature'

    APPROVAL_TYPES = [
        ('line_manager', 'Line Manager'),
        ('it_manager', 'IT Manager'),
    ]

    incident_id = fields.Many2one(
        'it.asset.incident.report',
        string='Incident Report',
        required=True,
        ondelete='cascade',
    )
    approval_type = fields.Selection(
        selection=APPROVAL_TYPES,
        string='Approval Type',
        required=True,
    )
    signer_name = fields.Char(
        string='Name',
        required=True,
        help='Printed name of the person signing this approval.',
    )
    signature = fields.Binary(
        string='Signature',
        required=True,
        attachment=False,
        help='Draw or type your signature to approve this incident report.',
    )
    comment = fields.Text(
        string='Comment',
        required=True,
        help='Approval comment recorded on the incident report.',
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        incident = self.env['it.asset.incident.report'].browse(
            self.env.context.get('default_incident_id')
        )
        approval_type = res.get('approval_type') or self.env.context.get('default_approval_type')
        if approval_type == 'line_manager' and incident:
            employee = self.env.user.employee_id
            res.setdefault('signer_name', employee.name if employee else self.env.user.name)
        elif approval_type == 'it_manager':
            res.setdefault('signer_name', self.env.user.name)
        return res

    def action_confirm(self):
        self.ensure_one()
        if not self.signature:
            raise ValidationError(_('A signature is required to approve this incident report.'))
        if not self.signer_name:
            raise ValidationError(_('Please enter your name before signing.'))
        if not self.comment or not self.comment.strip():
            raise ValidationError(_('An approval comment is required.'))

        report = self.incident_id
        if self.approval_type == 'line_manager':
            if report.state != 'submitted':
                raise UserError(_('Only submitted reports can be approved by the line manager.'))
            if not report._is_line_manager():
                raise UserError(_('Only the assigned line manager or an IT Asset Manager can approve this step.'))
            report._do_manager_approve(self.signer_name, self.signature, self.comment.strip())
        elif self.approval_type == 'it_manager':
            if report.state != 'manager_approved':
                raise UserError(_('Line manager approval is required before IT approval.'))
            if not report._is_it_manager():
                raise UserError(_('Only an IT Asset Manager can perform IT approval.'))
            report._do_it_approve(self.signer_name, self.signature, self.comment.strip())
        else:
            raise UserError(_('Unknown approval type.'))
        return {'type': 'ir.actions.act_window_close'}
