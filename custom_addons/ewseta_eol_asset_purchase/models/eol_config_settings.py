# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.tools.mail import is_html_empty

_EOL_PROGRAMME_INTRO_KEY = 'ewseta_eol.programme_intro'


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    eol_public_form_enabled = fields.Boolean(
        string='Public EOL request form enabled',
        config_parameter='ewseta_eol.public_form_enabled',
        default=True,
    )
    eol_programme_intro = fields.Html(
        string='Programme introduction (public page)',
        sanitize=False,
    )
    eol_otp_ttl_minutes = fields.Integer(
        string='OTP validity (minutes)',
        config_parameter='ewseta_eol.otp_ttl_minutes',
        default=15,
    )
    eol_otp_max_attempts = fields.Integer(
        string='OTP max attempts',
        config_parameter='ewseta_eol.otp_max_attempts',
        default=5,
    )
    eol_rate_limit_per_hour = fields.Integer(
        string='Public submissions per email per hour',
        config_parameter='ewseta_eol.rate_limit_per_hour',
        default=10,
    )
    eol_ack_policy_version = fields.Char(
        string='Acknowledgement policy version id',
        config_parameter='ewseta_eol.ack_policy_version',
        default='v1',
    )
    eol_purchase_limit_period_days = fields.Integer(
        string='Purchase limit rolling period (days)',
        config_parameter='ewseta_eol.purchase_limit_period_days',
        default=365,
    )
    eol_purchase_limit_count = fields.Integer(
        string='Default max in-flight + approved requests per employee',
        config_parameter='ewseta_eol.purchase_limit_count',
        default=1,
    )
    eol_tracking_token_days = fields.Integer(
        string='Tracking link validity (days)',
        config_parameter='ewseta_eol.tracking_token_days',
        default=90,
    )
    eol_corporate_email_domain = fields.Char(
        string='Corporate email domain (optional)',
        config_parameter='ewseta_eol.corporate_email_domain',
        help='If set, public work email must use this domain (e.g. ewseta.org.za).',
    )
    eol_site_options = fields.Char(
        string='Office location options (public form)',
        config_parameter='ewseta_eol.site_options',
        default='Office A|Office B|Remote',
        help='Pipe-separated list shown on the public request form.',
    )
    eol_quantity_limit_ack_text = fields.Char(
        string='Quantity limit text ({limit} placeholder)',
        config_parameter='ewseta_eol.quantity_limit_ack_text',
        default='1 laptop and 1 phone per calendar year',
    )

    @api.model
    def get_values(self):
        res = super().get_values()
        icp = self.env['ir.config_parameter'].sudo()
        res['eol_programme_intro'] = icp.get_param(_EOL_PROGRAMME_INTRO_KEY) or ''
        return res

    def set_values(self):
        super().set_values()
        intro = self.eol_programme_intro or ''
        if is_html_empty(intro):
            intro = ''
        self.env['ir.config_parameter'].sudo().set_param(
            _EOL_PROGRAMME_INTRO_KEY,
            intro,
        )
        self.env['ew.eol.purchase.request'].eol_sync_proc_cms_public_visibility(
            self.eol_public_form_enabled,
        )
