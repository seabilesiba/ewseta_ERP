# -*- coding: utf-8 -*-

from odoo import _, fields, models
from odoo.exceptions import UserError


class EolPreparePoolWizard(models.TransientModel):
    _name = 'ew.eol.prepare.pool.wizard'
    _description = 'ICT deprovisioning — release asset to EOL pool'

    equipment_id = fields.Many2one(
        'maintenance.equipment',
        required=True,
        readonly=True,
    )
    deprov_user_profiles = fields.Boolean(
        string='EWSETA files and user profiles removed',
    )
    deprov_licenses = fields.Boolean(
        string='Microsoft / enterprise licences (EWSETA) removed',
    )
    deprov_antivirus = fields.Boolean(
        string='Antivirus / security management removed',
    )
    deprov_vpn = fields.Boolean(string='VPN configurations removed')
    deprov_monitoring = fields.Boolean(string='Monitoring tools removed')
    deprov_email = fields.Boolean(string='Corporate email accounts removed')
    deprov_certificates = fields.Boolean(
        string='Certificates and credentials removed',
    )
    deprov_other_apps = fields.Boolean(
        string='Other EWSETA applications and configurations removed',
    )
    notes = fields.Text(string='ICT notes')
    set_eol_sale_eligible = fields.Boolean(
        string='Mark EOL sale eligible',
        default=True,
        help='Allow this unit in the employee EOL purchase pool after release.',
    )
    clear_network_identity = fields.Boolean(
        string='Clear hostname / IP / licence fields in register',
        default=True,
        help='Clears corporate network and licence metadata on the asset record (asset tag is kept).',
    )

    def _checklist_vals(self):
        self.ensure_one()
        return {
            'eol_deprov_user_profiles': self.deprov_user_profiles,
            'eol_deprov_licenses': self.deprov_licenses,
            'eol_deprov_antivirus': self.deprov_antivirus,
            'eol_deprov_vpn': self.deprov_vpn,
            'eol_deprov_monitoring': self.deprov_monitoring,
            'eol_deprov_email': self.deprov_email,
            'eol_deprov_certificates': self.deprov_certificates,
            'eol_deprov_other_apps': self.deprov_other_apps,
            'eol_deprovision_notes': self.notes,
        }

    def action_apply(self):
        self.ensure_one()
        equipment = self.equipment_id
        checklist = self._checklist_vals()
        if not all(checklist[k] for k in checklist if k.startswith('eol_deprov_')):
            raise UserError(_(
                'Tick every deprovisioning item before releasing the asset to the EOL pool, '
                'or complete the checklist manually on the asset form.'
            ))
        equipment.write(checklist)
        equipment._eol_release_to_pool(
            set_eol_sale_eligible=self.set_eol_sale_eligible,
            clear_network_identity=self.clear_network_identity,
            notes=self.notes,
        )
        return {'type': 'ir.actions.act_window_close'}
