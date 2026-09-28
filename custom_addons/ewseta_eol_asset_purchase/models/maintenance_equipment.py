# -*- coding: utf-8 -*-



from odoo import _, api, fields, models

from odoo.exceptions import UserError





class MaintenanceEquipment(models.Model):

    _inherit = 'maintenance.equipment'



    EOL_DEPROVISION_CHECKLIST_FIELDS = (

        'eol_deprov_user_profiles',

        'eol_deprov_licenses',

        'eol_deprov_antivirus',

        'eol_deprov_vpn',

        'eol_deprov_monitoring',

        'eol_deprov_email',

        'eol_deprov_certificates',

        'eol_deprov_other_apps',

    )



    SALE_AVAILABILITY = [

        ('available', 'Available for EOL sale'),

        ('reserved', 'Reserved'),

        ('on_hold', 'On hold'),

        ('sold', 'Sold'),

        ('withdrawn', 'Withdrawn'),

    ]



    eol_sale_eligible = fields.Boolean(

        string='EOL sale eligible',

        tracking=True,

        index=True,

    )

    sale_availability = fields.Selection(

        selection=SALE_AVAILABILITY,

        string='EOL sale availability',

        default='available',

        tracking=True,

        index=True,

    )

    eol_sale_price = fields.Monetary(

        string='EOL sale price override',

        currency_field='company_currency_id',

        tracking=True,

    )

    active_eol_request_id = fields.Many2one(

        'ew.eol.purchase.request',

        string='Active EOL request',

        copy=False,

        index=True,

    )

    eol_request_ids = fields.One2many(

        'ew.eol.purchase.request',

        'equipment_id',

        string='EOL purchase requests',

    )
    eol_last_received_request_id = fields.Many2one(
        'ew.eol.purchase.request',
        string='EOL handover (received)',
        copy=False,
        readonly=True,
        help='Latest EOL purchase request marked as asset received by ICT.',
    )
    eol_request_count = fields.Integer(
        compute='_compute_eol_request_count',
        string='EOL requests',
    )
    eol_handover_received = fields.Boolean(
        compute='_compute_eol_handover_received',
        string='EOL received by employee',
        help='True after ICT confirms handover on the EOL purchase request (EOL sale availability = Sold).',
    )

    @api.depends('eol_request_ids')
    def _compute_eol_request_count(self):
        for equipment in self:
            equipment.eol_request_count = len(equipment.eol_request_ids)

    @api.depends('sale_availability', 'eol_last_received_request_id.state')
    def _compute_eol_handover_received(self):
        for equipment in self:
            equipment.eol_handover_received = equipment.sale_availability == 'sold'

    def action_open_eol_purchase_requests(self):
        self.ensure_one()
        return {
            'name': _('EOL purchase requests'),
            'type': 'ir.actions.act_window',
            'res_model': 'ew.eol.purchase.request',
            'view_mode': 'list,form',
            'domain': [('equipment_id', '=', self.id)],
            'context': {'default_equipment_id': self.id},
        }

    eol_pool_eligible = fields.Boolean(

        compute='_compute_eol_pool_eligible',

        string='In EOL pool',

        help='Unassigned, ICT deprovisioned, and marked for EOL sale.',

    )



    eol_deprov_user_profiles = fields.Boolean(

        string='EWSETA files / user profiles removed',

        tracking=True,

    )

    eol_deprov_licenses = fields.Boolean(

        string='Microsoft / enterprise licences removed',

        tracking=True,

    )

    eol_deprov_antivirus = fields.Boolean(

        string='Antivirus / security management removed',

        tracking=True,

    )

    eol_deprov_vpn = fields.Boolean(string='VPN configurations removed', tracking=True)

    eol_deprov_monitoring = fields.Boolean(string='Monitoring tools removed', tracking=True)

    eol_deprov_email = fields.Boolean(string='Corporate email removed', tracking=True)

    eol_deprov_certificates = fields.Boolean(

        string='Certificates / credentials removed',

        tracking=True,

    )

    eol_deprov_other_apps = fields.Boolean(

        string='Other EWSETA apps / config removed',

        tracking=True,

    )

    eol_deprovision_notes = fields.Text(string='ICT deprovisioning notes')

    eol_deprovision_done = fields.Boolean(

        string='ICT deprovisioning complete',

        tracking=True,

        index=True,

    )

    eol_deprovision_date = fields.Datetime(string='Deprovisioned on', readonly=True)

    eol_deprovision_user_id = fields.Many2one(

        'res.users',

        string='Deprovisioned by',

        readonly=True,

    )



    @api.depends(

        'eol_sale_eligible',

        'sale_availability',

        'asset_state',

        'employee_id',

        'department_id',

        'eol_deprovision_done',

    )

    def _compute_eol_pool_eligible(self):

        for equipment in self:

            equipment.eol_pool_eligible = equipment._is_eol_pool_eligible()



    def _eol_deprovision_checks_complete(self):

        self.ensure_one()

        return all(self[field] for field in self.EOL_DEPROVISION_CHECKLIST_FIELDS)



    def _is_eol_pool_eligible(self):

        self.ensure_one()

        if self.asset_state in ('disposed', 'lost', 'in_repair'):

            return False

        return bool(

            self.eol_deprovision_done

            and self.eol_sale_eligible

            and self.sale_availability == 'available'

            and self.asset_state == 'available'

            and not self.employee_id

            and not self.department_id

        )



    def _is_eol_assigned_purchase_eligible(self, employee):

        """Employee may buy this device only when it is assigned to them."""

        self.ensure_one()

        if not employee:

            return False

        if self.asset_state in ('disposed', 'lost', 'in_repair'):

            return False

        return bool(

            self.eol_sale_eligible

            and self.sale_availability == 'available'

            and self.asset_state == 'assigned'

            and self.employee_id == employee

        )



    def _eol_reset_deprovision(self):

        reset_vals = {field: False for field in self.EOL_DEPROVISION_CHECKLIST_FIELDS}

        reset_vals.update({

            'eol_deprovision_done': False,

            'eol_deprovision_date': False,

            'eol_deprovision_user_id': False,

        })

        self.write(reset_vals)



    def write(self, vals):

        res = super().write(vals)

        if 'employee_id' in vals or 'department_id' in vals:

            for equipment in self:

                if equipment.employee_id or equipment.department_id:

                    equipment._eol_reset_deprovision()

        return res



    def _eol_check_can_release_to_pool(self):

        self.ensure_one()

        if self.asset_state in ('disposed', 'lost'):

            raise UserError(_('Disposed or lost assets cannot join the EOL pool.'))

        if self.sale_availability in ('reserved', 'sold'):

            raise UserError(_('This asset has an active EOL reservation or is already sold.'))

        if self.active_eol_request_id:

            raise UserError(_('Resolve the active EOL purchase request before releasing this asset.'))



    def _eol_release_to_pool(

        self,

        set_eol_sale_eligible=True,

        clear_network_identity=True,

        notes=None,

    ):

        self.ensure_one()

        self._eol_check_can_release_to_pool()

        if not self._eol_deprovision_checks_complete():

            raise UserError(_('Complete all ICT deprovisioning checklist items first.'))



        if self.employee_id or self.department_id or self.asset_state == 'assigned':

            self.action_return_asset()

        elif self.asset_state not in ('available', 'in_repair'):

            self.write({'asset_state': 'available'})



        release_vals = {

            'eol_deprovision_done': True,

            'eol_deprovision_date': fields.Datetime.now(),

            'eol_deprovision_user_id': self.env.user.id,

            'sale_availability': 'available',

        }

        if notes is not None:

            release_vals['eol_deprovision_notes'] = notes

        if set_eol_sale_eligible:

            release_vals['eol_sale_eligible'] = True

        if clear_network_identity:

            release_vals.update({

                'hostname': False,

                'ip_address': False,

                'license_key': False,

                'license_expiry': False,

            })

        self.write(release_vals)

        self.message_post(

            body=_(

                'ICT deprovisioning recorded and asset released to the EOL pool '

                '(unassigned, Asset State Available). Asset tag %(tag)s retained.',

                tag=self.asset_code or self.display_name,

            ),

        )



    def action_open_eol_prepare_pool_wizard(self):

        self.ensure_one()

        self._eol_check_can_release_to_pool()

        return {

            'name': _('Prepare for EOL pool'),

            'type': 'ir.actions.act_window',

            'res_model': 'ew.eol.prepare.pool.wizard',

            'view_mode': 'form',

            'target': 'new',

            'context': {

                'default_equipment_id': self.id,

                'default_deprov_user_profiles': self.eol_deprov_user_profiles,

                'default_deprov_licenses': self.eol_deprov_licenses,

                'default_deprov_antivirus': self.eol_deprov_antivirus,

                'default_deprov_vpn': self.eol_deprov_vpn,

                'default_deprov_monitoring': self.eol_deprov_monitoring,

                'default_deprov_email': self.eol_deprov_email,

                'default_deprov_certificates': self.eol_deprov_certificates,

                'default_deprov_other_apps': self.eol_deprov_other_apps,

                'default_notes': self.eol_deprovision_notes,

            },

        }



    def action_confirm_eol_deprovision_manual(self):

        """Use when ICT ticks checklist items directly on the asset form."""

        for equipment in self:

            equipment._eol_release_to_pool(

                set_eol_sale_eligible=equipment.eol_sale_eligible,

                clear_network_identity=False,

                notes=equipment.eol_deprovision_notes,

            )

        return True


