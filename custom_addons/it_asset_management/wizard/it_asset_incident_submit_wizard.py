# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class ItAssetIncidentSubmitWizard(models.TransientModel):
    _name = 'it.asset.incident.submit.wizard'
    _description = 'Incident Report Submit Signature'

    incident_id = fields.Many2one(
        'it.asset.incident.report',
        string='Incident Report',
        required=True,
        ondelete='cascade',
    )
    signer_name = fields.Char(
        string='Name',
        required=True,
        help='Printed name of the person submitting this report.',
    )
    signature = fields.Binary(
        string='Signature',
        required=True,
        attachment=False,
        help='Draw or type your signature to submit this incident report to ICT Support.',
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        incident = self.env['it.asset.incident.report'].browse(
            self.env.context.get('default_incident_id')
        )
        if incident:
            employee = self.env.user.employee_id
            res.setdefault(
                'signer_name',
                incident.reporter_name or (employee.name if employee else self.env.user.name),
            )
        return res

    def action_confirm(self):
        self.ensure_one()
        if not self.signature:
            raise ValidationError(_('A signature is required to submit this incident report.'))
        if not self.signer_name:
            raise ValidationError(_('Please enter your name before signing.'))

        report = self.incident_id
        if report.state != 'draft':
            raise UserError(_('Only draft reports can be submitted.'))
        report._check_reporter_or_manager()
        report._validate_submission()
        report._do_submit(self.signer_name, self.signature)
        return {'type': 'ir.actions.act_window_close'}
