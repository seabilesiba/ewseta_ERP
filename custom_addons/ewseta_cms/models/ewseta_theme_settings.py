# -*- coding: utf-8 -*-

import json

from odoo import api, fields, models
from odoo.exceptions import ValidationError


BUILTIN_THEME_META = {
    'light': {'type': 'builtin', 'label': 'White (Light)', 'toggleIcon': 'sun-o'},
    'dark': {'type': 'builtin', 'label': 'Dark', 'toggleIcon': 'moon-o'},
    'blue': {'type': 'builtin', 'label': 'Blue', 'toggleIcon': 'tint'},
    'green': {'type': 'builtin', 'label': 'Green', 'toggleIcon': 'leaf'},
    'orange': {'type': 'builtin', 'label': 'Orange', 'toggleIcon': 'fire'},
}


class EwsetaThemeSettings(models.Model):
    _name = 'ewseta.theme.settings'
    _description = 'EWSETA Website Theme Settings'
    _inherit = ['mail.thread']

    name = fields.Char(default='Theme Settings', required=True)
    website_id = fields.Many2one(
        'website',
        ondelete='restrict',
        default=lambda self: self.env.ref('website.default_website', raise_if_not_found=False),
    )
    is_active = fields.Boolean(default=True)
    theme_toggle_enabled = fields.Boolean(
        string='Show Theme Toggle Button',
        default=True,
        help='Display the theme cycle button in the website header.',
    )
    remember_user_choice = fields.Boolean(
        string='Remember Visitor Choice',
        default=True,
        help='When enabled, the visitor\'s last selected theme is stored in the browser.',
    )
    default_theme_mode = fields.Selection(
        selection=[
            ('preset', 'Built-in Theme'),
            ('custom', 'Custom Theme'),
        ],
        string='Default Theme Type',
        default='preset',
        required=True,
    )
    default_preset_theme = fields.Selection(
        selection=[
            ('light', 'White (Light)'),
            ('dark', 'Dark'),
            ('blue', 'Blue'),
            ('green', 'Green'),
            ('orange', 'Orange'),
        ],
        string='Default Built-in Theme',
        default='light',
        required=True,
    )
    default_custom_theme_id = fields.Many2one(
        'ewseta.website.theme',
        string='Default Custom Theme',
        domain="[('settings_id', '=', id), ('is_published', '=', True)]",
        ondelete='set null',
    )
    enable_dark_theme = fields.Boolean(string='Enable Dark Theme', default=True)
    enable_blue_theme = fields.Boolean(string='Enable Blue Theme', default=True)
    enable_green_theme = fields.Boolean(string='Enable Green Theme', default=True)
    enable_orange_theme = fields.Boolean(string='Enable Orange Theme', default=True)
    custom_theme_ids = fields.One2many(
        'ewseta.website.theme',
        'settings_id',
        string='Custom Themes',
    )
    custom_theme_count = fields.Integer(compute='_compute_custom_theme_count')

    _website_uniq = models.Constraint(
        'unique(website_id)',
        'Only one theme settings record is allowed per website.',
    )

    @api.depends('custom_theme_ids')
    def _compute_custom_theme_count(self):
        for record in self:
            record.custom_theme_count = len(record.custom_theme_ids)

    @api.model_create_multi
    def create(self, vals_list):
        """Reuse the existing website record and apply incoming values."""
        records = self.browse()
        pending = []
        for vals in vals_list:
            vals = dict(vals)
            website_id = vals.get('website_id')
            if not website_id:
                website = self.env.ref('website.default_website', raise_if_not_found=False)
                website_id = website.id if website else False
                if website_id:
                    vals['website_id'] = website_id
            if website_id:
                existing = self.search([('website_id', '=', website_id)], limit=1)
                if existing:
                    write_vals = {
                        key: value
                        for key, value in vals.items()
                        if key not in ('website_id', 'name')
                    }
                    if write_vals:
                        existing.write(write_vals)
                    records |= existing
                    continue
            pending.append(vals)
        if pending:
            records |= super().create(pending)
        return records

    @api.model
    def get_for_website(self, website_id=None):
        domain = [('is_active', '=', True)]
        if website_id:
            domain.append(('website_id', '=', website_id))
        return self.sudo().search(domain, limit=1)

    @api.model
    def _get_or_create_for_website(self, website=None):
        website = website or self.env['website'].get_current_website()
        if not website:
            website = self.env.ref('website.default_website', raise_if_not_found=False)
        if not website:
            return self.browse()
        settings = self.sudo().search([('website_id', '=', website.id)], limit=1)
        if not settings:
            settings = self.sudo().create({
                'name': 'Theme Settings',
                'website_id': website.id,
            })
        return settings

    @api.model
    def action_open_theme_settings(self):
        settings = self._get_or_create_for_website()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Theme Settings',
            'res_model': 'ewseta.theme.settings',
            'view_mode': 'form',
            'res_id': settings.id,
            'target': 'current',
        }

    def action_view_custom_themes(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Custom Themes',
            'res_model': 'ewseta.website.theme',
            'view_mode': 'list,form',
            'domain': [('settings_id', '=', self.id)],
            'context': {'default_settings_id': self.id},
        }

    def _resolve_default_theme_key(self):
        self.ensure_one()
        if self.default_theme_mode == 'custom' and self.default_custom_theme_id:
            return self.default_custom_theme_id.key
        return self.default_preset_theme or 'light'

    def _available_themes(self):
        self.ensure_one()
        themes = ['light']
        if self.enable_dark_theme:
            themes.append('dark')
        if self.enable_blue_theme:
            themes.append('blue')
        if self.enable_green_theme:
            themes.append('green')
        if self.enable_orange_theme:
            themes.append('orange')
        for custom_theme in self.custom_theme_ids.filtered('is_published').sorted('sequence'):
            if custom_theme.key not in themes:
                themes.append(custom_theme.key)
        return themes

    def _build_theme_meta(self):
        self.ensure_one()
        meta = dict(BUILTIN_THEME_META)
        for custom_theme in self.custom_theme_ids.filtered('is_published'):
            meta[custom_theme.key] = custom_theme.get_frontend_meta()
        return meta

    def get_frontend_config(self):
        self.ensure_one()
        themes = self._available_themes()
        default_theme = self._resolve_default_theme_key()
        if default_theme not in themes:
            default_theme = 'light'
        toggle_enabled = self.theme_toggle_enabled and len(themes) > 1
        return {
            'toggleEnabled': toggle_enabled,
            'defaultTheme': default_theme,
            'rememberUserChoice': self.remember_user_choice,
            'themes': themes,
            'themeMeta': self._build_theme_meta(),
        }

    @api.model
    def _default_frontend_config(self):
        return {
            'toggleEnabled': True,
            'defaultTheme': 'light',
            'rememberUserChoice': True,
            'themes': ['light', 'dark', 'blue', 'green', 'orange'],
            'themeMeta': BUILTIN_THEME_META,
        }

    @api.model
    def get_frontend_config_json(self, website_id=None):
        settings = self.get_for_website(website_id)
        config = settings.get_frontend_config() if settings else self._default_frontend_config()
        return json.dumps(config)

    @api.model
    def is_toggle_enabled_for_website(self, website_id=None):
        settings = self.get_for_website(website_id)
        config = settings.get_frontend_config() if settings else self._default_frontend_config()
        return config['toggleEnabled']

    @api.constrains(
        'default_theme_mode',
        'default_preset_theme',
        'default_custom_theme_id',
        'enable_dark_theme',
        'enable_blue_theme',
        'enable_green_theme',
        'enable_orange_theme',
        'custom_theme_ids',
    )
    def _check_default_theme(self):
        for record in self:
            available = record._available_themes()
            default_key = record._resolve_default_theme_key()
            if default_key not in available:
                raise ValidationError(
                    'The default theme must be one of the enabled built-in or published custom themes.'
                )
            if (
                record.default_theme_mode == 'custom'
                and record.default_custom_theme_id
                and record.default_custom_theme_id.settings_id != record
            ):
                raise ValidationError(
                    'The default custom theme must belong to this theme settings record.'
                )

    @api.model
    def seed_default_content(self):
        website = self.env.ref('website.default_website', raise_if_not_found=False)
        if not website:
            return
        self._get_or_create_for_website(website)
