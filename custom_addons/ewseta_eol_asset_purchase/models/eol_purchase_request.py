# -*- coding: utf-8 -*-

import hashlib
import secrets
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


def _hash_token(raw, pepper=''):
    return hashlib.sha256(f'{pepper}{raw}'.encode('utf-8')).hexdigest()


class EolPurchaseRequest(models.Model):
    _name = 'ew.eol.purchase.request'
    _description = 'EOL Asset Purchase Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc, id desc'

    STATES = [
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('pending_verification', 'Pending verification'),
        ('exception', 'Exception'),
        ('under_review', 'Under review'),
        ('awaiting_approval', 'Awaiting approval'),
        ('approved', 'Approved'),
        ('received', 'Received'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled'),
    ]
    REQUEST_TYPES = [
        ('assigned', 'My assigned device'),
        ('pool', 'From available pool'),
    ]
    CHANNELS = [
        ('public', 'Public website'),
        ('portal', 'Portal'),
        ('backend', 'Backend'),
    ]

    TERMINAL_STATES = frozenset({'approved', 'received', 'rejected', 'cancelled'})
    IN_FLIGHT_STATES = frozenset({
        'submitted', 'pending_verification', 'exception',
        'under_review', 'awaiting_approval',
    })

    name = fields.Char(
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True,
    )
    channel = fields.Selection(CHANNELS, default='public', required=True, tracking=True)
    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company,
        required=True,
        tracking=True,
    )
    currency_id = fields.Many2one(
        related='company_id.currency_id',
        store=True,
    )
    state = fields.Selection(STATES, default='draft', required=True, tracking=True, index=True)
    state_label = fields.Char(compute='_compute_state_label')
    employee_id = fields.Many2one('hr.employee', tracking=True, index=True)
    employee_name = fields.Char(required=True, tracking=True)
    employee_number = fields.Char(tracking=True)
    work_email = fields.Char(required=True, tracking=True, index=True)
    department_name = fields.Char(string='Department / team')
    site_name = fields.Char(string='Office location / site')
    manual_verification = fields.Boolean(
        string='Requires manual verification',
        tracking=True,
    )
    employee_verified = fields.Boolean(tracking=True)

    category_id = fields.Many2one('ew.eol.asset.category', required=True, tracking=True)
    request_type = fields.Selection(REQUEST_TYPES, required=True, tracking=True)
    OS_PREFERENCES = [
        ('windows', 'Windows'),
        ('macos', 'macOS'),
        ('no_preference', 'No preference'),
    ]
    os_preference = fields.Selection(
        OS_PREFERENCES,
        string='OS preference',
        help='Subject to availability.',
    )
    serial_or_tag = fields.Char(
        string='Serial / asset tag',
        help='Required when requesting your assigned device.',
    )

    ack_as_is = fields.Boolean(string='Acknowledged as-is sale and no IT support')
    ack_no_support = fields.Boolean(string='Acknowledged no IT support')
    ack_quantity_limit = fields.Boolean(string='Acknowledged purchase quantity limits')
    ack_data_software = fields.Boolean(string='Acknowledged data and software removal')
    ack_final_agreement = fields.Boolean(string='Acknowledged waiver and payment gate')
    ack_policy = fields.Boolean(string='Acknowledged policy')
    ack_policy_read = fields.Boolean(
        compute='_compute_ack_policy_read',
        inverse='_inverse_ack_policy_read',
        store=True,
    )
    ack_policy_version = fields.Char()

    equipment_id = fields.Many2one('maintenance.equipment', tracking=True, index=True)
    sale_price = fields.Monetary(currency_field='currency_id', tracking=True)

    verification_id = fields.Many2one('ew.eol.public.verification', copy=False)
    approval_line_ids = fields.One2many('ew.eol.approval.line', 'request_id')
    track_token_hash = fields.Char(copy=False, index=True)
    track_token_expires = fields.Datetime(copy=False)
    can_resend_tracking_link = fields.Boolean(
        compute='_compute_can_resend_tracking_link',
    )

    @api.depends('state')
    def _compute_state_label(self):
        labels = dict(self.STATES)
        for req in self:
            req.state_label = labels.get(req.state, req.state or '')

    def eol_public_track_display(self):
        """Structured labels for the private /track/<token> page."""
        self.ensure_one()
        state = self.state
        badge_class = {
            'submitted': 'info',
            'pending_verification': 'warning',
            'exception': 'warning',
            'under_review': 'info',
            'awaiting_approval': 'warning',
            'approved': 'success',
            'received': 'success',
            'rejected': 'danger',
            'cancelled': 'secondary',
        }.get(state, 'secondary')

        step_index = {
            'submitted': 0,
            'pending_verification': 1,
            'exception': 1,
            'under_review': 2,
            'awaiting_approval': 2,
            'approved': 3,
            'received': 4,
            'rejected': 2,
            'cancelled': 0,
        }.get(state, 0)

        steps = [
            {'label': _('Submitted'), 'icon': 'fa-paper-plane-o'},
            {'label': _('Verification'), 'icon': 'fa-envelope-o'},
            {'label': _('Approval'), 'icon': 'fa-gavel'},
            {'label': _('Handover'), 'icon': 'fa-laptop'},
        ]
        for i, step in enumerate(steps):
            if state in ('rejected', 'cancelled'):
                if i < step_index:
                    step['status'] = 'done'
                elif i == step_index:
                    step['status'] = 'cancelled'
                else:
                    step['status'] = 'muted'
            elif step_index >= 4:
                step['status'] = 'done'
            elif i < step_index:
                step['status'] = 'done'
            elif i == step_index:
                step['status'] = 'current'
            else:
                step['status'] = 'upcoming'

        messages = {
            'submitted': _('We received your request and will verify your details.'),
            'pending_verification': _('Please complete email verification if you have not already.'),
            'exception': _('ICT is reviewing your employee details manually.'),
            'under_review': _('Your request is being reviewed by ICT.'),
            'awaiting_approval': _('Waiting for approver sign-off.'),
            'approved': _('Approved. ICT will contact you about collection and payment.'),
            'received': _('Device handover is complete. Thank you.'),
            'rejected': _('This request was not approved.'),
            'cancelled': _('This request was cancelled.'),
        }
        type_labels = dict(self.REQUEST_TYPES)
        return {
            'badge_class': badge_class,
            'message': messages.get(state, ''),
            'steps': steps,
            'request_type_label': type_labels.get(self.request_type, ''),
            'is_terminal': state in self.TERMINAL_STATES,
        }

    @api.depends(
        'work_email',
        'state',
        'track_token_hash',
        'verification_id.state',
        'employee_verified',
    )
    def _compute_can_resend_tracking_link(self):
        for req in self:
            email_ok = bool((req.work_email or '').strip())
            state_ok = req.state not in ('draft', 'cancelled')
            submitted = req.state in (
                'submitted', 'pending_verification', 'exception',
                'under_review', 'awaiting_approval', 'approved', 'received', 'rejected',
            )
            otp_ok = (
                (req.verification_id and req.verification_id.state == 'verified')
                or req.employee_verified
            )
            req.can_resend_tracking_link = bool(
                email_ok and state_ok and submitted and (otp_ok or req.track_token_hash)
            )

    @api.depends('ack_policy')
    def _compute_ack_policy_read(self):
        for req in self:
            req.ack_policy_read = req.ack_policy

    def _inverse_ack_policy_read(self):
        for req in self:
            req.ack_policy = req.ack_policy_read

    @api.model
    def _config_int(self, key, default):
        return int(self.env['ir.config_parameter'].sudo().get_param(key, str(default)))

    @api.model
    def _config_str(self, key, default=''):
        return self.env['ir.config_parameter'].sudo().get_param(key, default) or default

    @api.model
    def _tracking_pepper(self):
        return self._config_str('ewseta_eol.tracking_pepper', 'ewseta_eol_track')

    @api.model
    def eol_public_site_options(self):
        raw = self._config_str('ewseta_eol.site_options', 'Office A|Office B|Remote')
        return [part.strip() for part in raw.split('|') if part.strip()]

    @api.model
    def eol_quantity_limit_ack_text(self):
        return self._config_str(
            'ewseta_eol.quantity_limit_ack_text',
            '1 laptop and 1 phone per calendar year',
        )

    @api.model
    def eol_public_policy_acknowledgements(self):
        return self.env['ew.eol.policy.document'].eol_public_policy_acknowledgements()

    @api.model
    def eol_public_policies_ready(self):
        return self.env['ew.eol.policy.document'].eol_public_policies_ready()

    @api.model
    def eol_public_policy_pages(self):
        return self.env['ew.eol.policy.document'].eol_public_policy_pages()

    @api.model
    def _normalize_email(self, email):
        return (email or '').strip().lower()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('ew.eol.purchase.request') or _('New')
            if vals.get('work_email'):
                vals['work_email'] = self._normalize_email(vals['work_email'])
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('work_email'):
            vals['work_email'] = self._normalize_email(vals['work_email'])
        if 'state' in vals:
            new_state = vals['state']
            for req in self:
                if req.state in self.TERMINAL_STATES and new_state != req.state:
                    if req.state == 'approved' and new_state == 'received':
                        continue
                    raise UserError(_('Cannot change status of a closed request.'))
        return super().write(vals)

    def _validate_submission_fields(self):
        self.ensure_one()
        missing = []
        if not self.employee_name:
            missing.append(_('full name'))
        if not (self.employee_number or '').strip():
            missing.append(_('employee ID number'))
        if not self.work_email:
            missing.append(_('corporate email'))
        if not (self.department_name or '').strip():
            missing.append(_('department / team'))
        if not (self.site_name or '').strip():
            missing.append(_('office location'))
        if not self.category_id:
            missing.append(_('device type'))
        if not self.request_type:
            missing.append(_('assigned vs pool choice'))
        if self.request_type == 'assigned' and not (self.serial_or_tag or '').strip():
            missing.append(_('serial number or asset tag'))
        required_acks = (
            self.ack_quantity_limit,
            self.ack_as_is,
            self.ack_data_software,
            self.ack_final_agreement,
        )
        if not all(required_acks):
            raise UserError(_('All policy acknowledgements must be accepted before submitting.'))
        if missing:
            raise UserError(_('Missing required fields: %s') % ', '.join(missing))

    def _validate_corporate_email(self):
        self.ensure_one()
        domain = self._config_str('ewseta_eol.corporate_email_domain')
        if domain and not self.work_email.endswith('@' + domain.lower().lstrip('@')):
            raise UserError(_('Please use your corporate email address (@%s).') % domain)

    def _match_employee(self):
        self.ensure_one()
        employee = self.env['hr.employee'].eol_find_by_work_email(self.work_email)
        if employee:
            self.write({
                'employee_id': employee.id,
                'employee_name': employee.name,
                'employee_number': employee.barcode or getattr(employee, 'identification_id', False) or self.employee_number,
                'department_name': employee.department_id.name or self.department_name,
                'manual_verification': False,
            })
            return True
        self.write({
            'employee_id': False,
            'manual_verification': True,
        })
        return False

    def _purchase_limit_for_category(self):
        self.ensure_one()
        cat_limit = self.category_id.purchase_limit_count
        global_limit = self._config_int('ewseta_eol.purchase_limit_count', 1)
        limit = cat_limit if cat_limit else global_limit
        return limit

    def _count_requests_toward_limit(self):
        self.ensure_one()
        if not self.employee_id:
            return 0
        period_days = self._config_int('ewseta_eol.purchase_limit_period_days', 365)
        since = fields.Datetime.now() - timedelta(days=period_days)
        domain = [
            ('id', '!=', self.id),
            ('employee_id', '=', self.employee_id.id),
            ('category_id', '=', self.category_id.id),
            ('create_date', '>=', since),
            ('state', 'in', list(self.IN_FLIGHT_STATES | {'approved', 'received'})),
        ]
        return self.search_count(domain)

    def _check_purchase_limit(self):
        self.ensure_one()
        limit = self._purchase_limit_for_category()
        if limit <= 0:
            return
        count = self._count_requests_toward_limit()
        if count >= limit:
            raise UserError(_(
                'You have reached the purchase limit for this category. '
                'Contact the asset manager if you need an exception.'
            ))

    def _validate_equipment_for_eol_request(self, equipment):
        self.ensure_one()
        if equipment.asset_state in ('disposed', 'lost'):
            raise UserError(_('This asset is no longer in the register.'))
        if not equipment.eol_sale_eligible:
            raise UserError(_('This asset is not marked for EOL sale.'))
        if equipment.sale_availability != 'available':
            raise UserError(_('The selected asset is no longer available. Please contact ICT.'))
        if equipment.active_eol_request_id and equipment.active_eol_request_id != self:
            raise UserError(_('This asset was just reserved by another request.'))
        if self.request_type == 'pool':
            if not equipment._is_eol_pool_eligible():
                raise UserError(_(
                    'Only ICT-deprovisioned, unassigned assets (Asset State: Available) appear in the EOL pool. '
                    'Complete the EOL deprovisioning checklist on the asset, or use Prepare for EOL pool. '
                    'Devices still assigned to employees can only be purchased via '
                    '“purchase my assigned corporate device”.'
                ))
        elif self.request_type == 'assigned':
            if not self.employee_id:
                raise UserError(_('Employee must be verified before allocating your device.'))
            if not equipment._is_eol_assigned_purchase_eligible(self.employee_id):
                raise UserError(_(
                    'No eligible assigned device matches the serial or asset tag provided, '
                    'or the device is not assigned to you for EOL sale.'
                ))
            tag = (self.serial_or_tag or '').strip()
            if tag and tag not in (equipment.asset_code or '', equipment.serial_no or ''):
                raise UserError(_('Serial or asset tag does not match the assigned device.'))

    def _resolve_equipment_candidate(self):
        """Return equipment record to reserve (not yet locked)."""
        self.ensure_one()
        Equipment = self.env['maintenance.equipment']
        if self.request_type == 'assigned':
            if not self.employee_id:
                raise UserError(_('Employee must be verified before allocating your device.'))
            tag = (self.serial_or_tag or '').strip()
            equipment = Equipment.search([
                ('eol_sale_eligible', '=', True),
                ('sale_availability', '=', 'available'),
                ('asset_state', '=', 'assigned'),
                ('employee_id', '=', self.employee_id.id),
                '|', ('asset_code', '=', tag), ('serial_no', '=', tag),
            ], limit=1)
            if not equipment:
                raise UserError(_('No eligible assigned device matches the serial or asset tag provided.'))
            self._validate_equipment_for_eol_request(equipment)
            return equipment
        cat = self.category_id.maintenance_category_id
        domain = [
            ('eol_sale_eligible', '=', True),
            ('sale_availability', '=', 'available'),
            ('asset_state', '=', 'available'),
            ('employee_id', '=', False),
            ('department_id', '=', False),
        ]
        if cat:
            domain.append(('category_id', '=', cat.id))
        equipment = Equipment.search(domain, order='id asc', limit=1)
        if not equipment:
            raise UserError(_('No eligible equipment is available in this category pool.'))
        self._validate_equipment_for_eol_request(equipment)
        return equipment

    def _reserve_equipment(self):
        self.ensure_one()
        if self.equipment_id and self.equipment_id.sale_availability == 'reserved':
            if self.equipment_id.active_eol_request_id == self:
                return
        equipment = self.equipment_id or self._resolve_equipment_candidate()
        self.env.cr.execute(
            'SELECT id FROM maintenance_equipment WHERE id = %s FOR UPDATE',
            [equipment.id],
        )
        equipment.invalidate_recordset()
        equipment = equipment.browse(equipment.id)
        self._validate_equipment_for_eol_request(equipment)
        price = equipment.eol_sale_price or self.category_id.default_price
        equipment.write({
            'sale_availability': 'reserved',
            'active_eol_request_id': self.id,
        })
        self.write({
            'equipment_id': equipment.id,
            'sale_price': price,
        })

    def _release_equipment(self):
        for req in self:
            equipment = req.equipment_id
            if not equipment:
                continue
            if equipment.sale_availability == 'sold':
                continue
            if equipment.active_eol_request_id.id == req.id:
                equipment.write({
                    'sale_availability': 'available',
                    'active_eol_request_id': False,
                })

    def _finalize_equipment_sale(self):
        self.ensure_one()
        equipment = self.equipment_id
        if not equipment:
            raise UserError(_('No asset is linked to this request.'))
        if (
            equipment.active_eol_request_id
            and equipment.active_eol_request_id != self
        ):
            raise UserError(_('This asset is linked to another active request.'))
        disposal_vals = {
            'sale_availability': 'sold',
            'active_eol_request_id': False,
            'eol_last_received_request_id': self.id,
            'employee_id': False,
            'department_id': False,
            'equipment_assign_to': 'other',
            'asset_state': 'disposed',
            'disposal_date': fields.Date.context_today(equipment),
            'disposal_reason': _('EOL employee purchase %s') % self.name,
        }
        equipment.write(disposal_vals)

    def _issue_tracking_token(self):
        self.ensure_one()
        token = secrets.token_urlsafe(32)
        days = self._config_int('ewseta_eol.tracking_token_days', 90)
        expires = fields.Datetime.now() + timedelta(days=days)
        pepper = self._tracking_pepper()
        self.write({
            'track_token_hash': _hash_token(token, pepper),
            'track_token_expires': expires,
        })
        return token

    @api.model
    def find_by_tracking_token(self, token):
        if not token:
            return self.browse()
        pepper = self._tracking_pepper()
        token_hash = _hash_token(token.strip(), pepper)
        req = self.search([
            ('track_token_hash', '=', token_hash),
            ('track_token_expires', '>=', fields.Datetime.now()),
        ], limit=1)
        return req

    def validate_tracking_token(self, token):
        self.ensure_one()
        if not token or not self.track_token_hash:
            return False
        if self.track_token_expires and self.track_token_expires < fields.Datetime.now():
            return False
        pepper = self._tracking_pepper()
        return _hash_token(token.strip(), pepper) == self.track_token_hash

    def _after_email_verified(self):
        self.ensure_one()
        if self.manual_verification:
            self.write({'state': 'exception'})
            return
        self.write({'employee_verified': True})
        self._check_purchase_limit()
        self._reserve_equipment()
        self.write({'state': 'under_review'})

    def action_public_submit(self):
        last_token = None
        for req in self:
            req._validate_submission_fields()
            req._validate_corporate_email()
            req.ack_policy_version = req._config_str('ewseta_eol.ack_policy_version', 'v1')
            req._match_employee()
            req._check_purchase_limit()
            req.write({'state': 'pending_verification'})
            verification, otp = self.env['ew.eol.public.verification'].create_otp_for_request(
                req, req.work_email,
            )
            req.verification_id = verification.id
            verification.action_send_otp_email(otp)
            last_token = req._issue_tracking_token()
            req.message_post(body=_('Public request submitted; verification email sent.'))
        return last_token

    @api.model
    def public_create_and_submit(self, vals):
        if not self.public_form_enabled():
            raise UserError(_('The public request form is not available at this time.'))
        email = vals.get('work_email')
        if not self.check_public_rate_limit(email):
            raise UserError(_('Too many requests from this email address. Try again later.'))
        vals = dict(vals)
        if vals.pop('ack_policy_read', None):
            vals['ack_policy'] = True
        if vals.get('ack_as_is'):
            vals['ack_no_support'] = True
        os_pref = vals.get('os_preference')
        if os_pref == '':
            vals['os_preference'] = False
        vals.setdefault('channel', 'public')
        request = self.create(vals)
        token = request.action_public_submit()
        return request, token

    def action_public_verify_and_continue(self, otp_plain):
        self.ensure_one()
        if self.state not in ('pending_verification',):
            raise UserError(_('This request cannot be verified in its current state.'))
        return self.action_verify_otp(otp_plain)

    def _send_confirmation_mail(self, track_token=None, email_verified=False):
        self.ensure_one()
        template = self.env.ref(
            'ewseta_eol_asset_purchase.mail_template_eol_confirmation',
            raise_if_not_found=False,
        )
        if not template:
            return
        if not self.work_email:
            return False
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url', '')
        track_url = ''
        if track_token and base_url:
            track_url = f'{base_url.rstrip("/")}/employee/eol-assets/track/{track_token}'
        return template.with_context(
            track_url=track_url,
            email_verified=email_verified,
            link_resent=bool(self.env.context.get('eol_link_resent')),
        ).send_mail(
            self.id,
            force_send=True,
            email_values={'email_to': self.work_email.strip()},
        )

    def _check_group_resend_tracking_link(self):
        if self.env.user.has_group('base.group_system'):
            return
        if (
            self.env.user.has_group('ewseta_eol_asset_purchase.group_eol_asset_manager')
            or self.env.user.has_group('ewseta_eol_asset_purchase.group_eol_approver')
            or self.env.user.has_group('it_asset_management.group_it_asset_manager')
        ):
            return
        raise UserError(_(
            'Only an EOL asset manager, EOL approver, or IT asset manager can resend the tracking link.'
        ))

    def _email_otp_verified(self):
        self.ensure_one()
        if self.verification_id and self.verification_id.state == 'verified':
            return True
        return bool(self.employee_verified)

    def action_resend_tracking_link(self):
        """Issue a new private track token and email it to the employee."""
        self._check_group_resend_tracking_link()
        icp = self.env['ir.config_parameter'].sudo()
        base_url = (icp.get_param('web.base.url') or '').strip()
        if not base_url:
            raise UserError(_(
                'Cannot send a tracking link: set the website base URL under '
                'Settings → General Settings (web.base.url).'
            ))
        for req in self:
            if not req.work_email:
                raise UserError(_('Request %s has no work email.', req.name))
            if req.state in ('draft', 'cancelled'):
                raise UserError(_('Cannot send a tracking link for request %s in state "%s".', req.name, req.state))
            token = req._issue_tracking_token()
            mail_id = req.with_context(eol_link_resent=True)._send_confirmation_mail(
                token,
                email_verified=req._email_otp_verified(),
            )
            if not mail_id:
                raise UserError(_(
                    'The tracking email could not be sent for %s. Check outgoing mail and the confirmation template.',
                    req.name,
                ))
            req.message_post(
                body=_('Private tracking link resent to %(email)s.', email=req.work_email),
                subtype_xmlid='mail.mt_note',
            )
        return True

    def action_verify_otp(self, otp_plain):
        for req in self.filtered(lambda r: r.state == 'pending_verification'):
            if not req.verification_id:
                raise UserError(_('No verification is linked to this request.'))
            req.verification_id.action_verify_otp(otp_plain)
            req._after_email_verified()
        return True

    def action_manual_verify_employee(self):
        self._check_group_asset_manager()
        for req in self:
            if not req.employee_id:
                raise UserError(_('Link an employee record before manual verification.'))
            req.write({
                'employee_verified': True,
                'manual_verification': False,
            })
            if req.state in ('exception', 'pending_verification'):
                req._check_purchase_limit()
                req._reserve_equipment()
                req.state = 'under_review'

    def action_submit_for_approval(self):
        self._check_group_asset_manager()
        for req in self:
            if req.state != 'under_review':
                raise UserError(_('Only requests under review can be sent for approval.'))
            if not req.employee_verified:
                raise UserError(_('Employee identity must be verified before approval.'))
            if not req.equipment_id:
                req._reserve_equipment()
            req.state = 'awaiting_approval'

    def _check_group_asset_manager(self):
        if not self.env.user.has_group('ewseta_eol_asset_purchase.group_eol_asset_manager'):
            raise UserError(_('Only an EOL asset manager can perform this action.'))

    def _check_approver(self):
        if not self.env.user.has_group('ewseta_eol_asset_purchase.group_eol_approver'):
            raise UserError(_('You are not allowed to approve EOL purchase requests.'))

    def _approval_gate_checks(self):
        self.ensure_one()
        if not self.employee_verified:
            raise UserError(_('Employee must be verified before approval.'))
        if self.manual_verification and self.state == 'exception':
            raise UserError(_('Complete manual verification before approval.'))
        self._check_purchase_limit()
        if not self.equipment_id:
            self._reserve_equipment()
        if self.equipment_id.sale_availability != 'reserved':
            raise UserError(_('A valid asset reservation is required before approval.'))

    def action_approve(self, comment=None):
        self._check_approver()
        for req in self:
            if req.state != 'awaiting_approval':
                raise UserError(_('Only requests awaiting approval can be approved.'))
            req._approval_gate_checks()
            self.env['ew.eol.approval.line'].create({
                'request_id': req.id,
                'approver_id': self.env.user.id,
                'decision': 'approve',
                'comment': comment,
            })
            req.state = 'approved'
            req.message_post(body=_('Request approved by %s.') % self.env.user.name)

    def _check_handover_user(self):
        if not (
            self.env.user.has_group('ewseta_eol_asset_purchase.group_eol_asset_manager')
            or self.env.user.has_group('it_asset_management.group_it_asset_manager')
        ):
            raise UserError(
                _('Only an EOL asset manager or IT asset manager can confirm handover.'),
            )

    def action_mark_asset_received(self):
        self._check_handover_user()
        for req in self:
            if req.state != 'approved':
                raise UserError(_('Only approved requests can be marked as received.'))
            req._finalize_equipment_sale()
            req.state = 'received'
            req.message_post(
                body=_('Asset marked as received (handover complete) by %s.')
                % self.env.user.name,
            )

    def action_reject(self, comment=None):
        self._check_approver()
        for req in self:
            if req.state != 'awaiting_approval':
                raise UserError(_('Only requests awaiting approval can be rejected.'))
            self.env['ew.eol.approval.line'].create({
                'request_id': req.id,
                'approver_id': self.env.user.id,
                'decision': 'reject',
                'comment': comment,
            })
            req._release_equipment()
            req.state = 'rejected'

    def action_return_for_correction(self, comment=None):
        self._check_approver()
        for req in self:
            if req.state != 'awaiting_approval':
                raise UserError(_('Only requests awaiting approval can be returned.'))
            self.env['ew.eol.approval.line'].create({
                'request_id': req.id,
                'approver_id': self.env.user.id,
                'decision': 'return',
                'comment': comment,
            })
            req.state = 'under_review'

    def action_cancel(self):
        for req in self:
            if req.state in self.TERMINAL_STATES:
                continue
            req._release_equipment()
            req.state = 'cancelled'

    @api.model
    def check_public_rate_limit(self, email):
        """Return True if submission is allowed for this email in the last hour."""
        limit = self._config_int('ewseta_eol.rate_limit_per_hour', 10)
        if limit <= 0:
            return True
        normalized = self._normalize_email(email)
        since = fields.Datetime.now() - timedelta(hours=1)
        count = self.search_count([
            ('work_email', '=', normalized),
            ('create_date', '>=', since),
        ])
        return count < limit

    @api.model
    def public_form_enabled(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            'ewseta_eol.public_form_enabled', 'True',
        ) in ('True', '1', 'true')

    @api.model
    def eol_sync_proc_cms_public_visibility(self, enabled=None):
        """Show or hide procurement CMS navbar/footer links for the EOL programme."""
        if enabled is None:
            enabled = self.public_form_enabled()
        Nav = self.env['proc.cms.nav.item'].sudo()
        for xmlid in (
            'ewseta_eol_asset_purchase.proc_cms_nav_eol_assets',
            'ewseta_eol_asset_purchase.proc_cms_footer_eol_assets',
        ):
            rec = self.env.ref(xmlid, raise_if_not_found=False)
            if rec:
                rec.write({'active': enabled})
        Nav.sync_all_menus()
