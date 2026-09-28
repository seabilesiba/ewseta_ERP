# -*- coding: utf-8 -*-

import hashlib
import secrets

from odoo import _, api, fields, models
from odoo.exceptions import UserError


def _hash_value(raw, pepper=''):
    payload = f'{pepper}{raw}'.encode('utf-8')
    return hashlib.sha256(payload).hexdigest()


class EolPublicVerification(models.Model):
    _name = 'ew.eol.public.verification'
    _description = 'EOL Public Email OTP Verification'
    _order = 'create_date desc'

    request_id = fields.Many2one(
        'ew.eol.purchase.request',
        required=True,
        ondelete='cascade',
        index=True,
    )
    email = fields.Char(required=True, index=True)
    otp_hash = fields.Char(required=True, copy=False)
    expires_at = fields.Datetime(required=True, index=True)
    attempt_count = fields.Integer(default=0)
    state = fields.Selection(
        [
            ('pending', 'Pending'),
            ('verified', 'Verified'),
            ('failed', 'Failed'),
        ],
        default='pending',
        required=True,
        index=True,
    )
    verified_at = fields.Datetime()
    company_id = fields.Many2one(related='request_id.company_id', store=True)

    @api.model
    def _get_pepper(self):
        param = self.env['ir.config_parameter'].sudo().get_param(
            'ewseta_eol.otp_pepper',
            default='ewseta_eol_otp',
        )
        return param

    @api.model
    def _otp_ttl_minutes(self):
        return int(
            self.env['ir.config_parameter'].sudo().get_param(
                'ewseta_eol.otp_ttl_minutes', '15',
            )
        )

    @api.model
    def _max_attempts(self):
        return int(
            self.env['ir.config_parameter'].sudo().get_param(
                'ewseta_eol.otp_max_attempts', '5',
            )
        )

    @api.model
    def create_otp_for_request(self, request, email):
        """Create verification record and return plaintext OTP (for email only)."""
        request.ensure_one()
        otp = ''.join(secrets.choice('0123456789') for _ in range(6))
        pepper = self._get_pepper()
        ttl = self._otp_ttl_minutes()
        expires = fields.Datetime.add(fields.Datetime.now(), minutes=ttl)
        verification = self.create({
            'request_id': request.id,
            'email': email.strip().lower(),
            'otp_hash': _hash_value(otp, pepper),
            'expires_at': expires,
        })
        return verification, otp

    def _check_otp(self, otp_plain):
        self.ensure_one()
        pepper = self._get_pepper()
        return _hash_value(otp_plain.strip(), pepper) == self.otp_hash

    def action_verify_otp(self, otp_plain):
        self.ensure_one()
        if self.state != 'pending':
            raise UserError(_('This verification is no longer active.'))
        now = fields.Datetime.now()
        if self.expires_at < now:
            self.state = 'failed'
            raise UserError(_('Verification code has expired. Please request a new code.'))
        max_attempts = self._max_attempts()
        if self.attempt_count >= max_attempts:
            self.state = 'failed'
            raise UserError(_('Too many failed attempts. Contact ICT for assistance.'))
        if not self._check_otp(otp_plain):
            self.attempt_count += 1
            if self.attempt_count >= max_attempts:
                self.state = 'failed'
            raise UserError(_('Invalid verification code.'))
        self.write({
            'state': 'verified',
            'verified_at': now,
        })
        return True

    def action_send_otp_email(self, otp_plain):
        self.ensure_one()
        template = self.env.ref(
            'ewseta_eol_asset_purchase.mail_template_eol_otp',
            raise_if_not_found=False,
        )
        if not template:
            return
        template.with_context(otp_plain=otp_plain).send_mail(
            self.id,
            force_send=True,
        )
