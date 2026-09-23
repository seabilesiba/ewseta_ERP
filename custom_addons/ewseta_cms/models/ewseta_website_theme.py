# -*- coding: utf-8 -*-

import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError


BUILTIN_THEME_KEYS = {'light', 'dark', 'blue', 'green', 'orange'}

PRESET_COLOR_TEMPLATES = {
    'dark': {
        'color_bg': '#121214',
        'color_bg_elevated': '#1a1a1e',
        'color_bg_subtle': '#222228',
        'color_bg_deep': '#0e0e10',
        'color_text': '#f2f2f4',
        'color_text_muted': 'rgba(242, 242, 244, 0.68)',
        'color_border': 'rgba(255, 255, 255, 0.1)',
        'color_accent': '#F8991D',
        'use_gradient': False,
    },
    'blue': {
        'color_bg': '#0a1e35',
        'color_bg_elevated': '#123052',
        'color_bg_subtle': '#1a4568',
        'color_bg_deep': '#071525',
        'color_text': '#f2f8fc',
        'color_text_muted': 'rgba(242, 248, 252, 0.72)',
        'color_border': 'rgba(0, 174, 239, 0.18)',
        'color_accent': '#00AEEF',
        'use_gradient': True,
    },
    'green': {
        'color_bg': '#0f1f12',
        'color_bg_elevated': '#1a3320',
        'color_bg_subtle': '#234429',
        'color_bg_deep': '#0a1810',
        'color_text': '#f2faf4',
        'color_text_muted': 'rgba(242, 250, 244, 0.72)',
        'color_border': 'rgba(118, 188, 67, 0.22)',
        'color_accent': '#76BC43',
        'use_gradient': True,
    },
    'orange': {
        'color_bg': '#1a1008',
        'color_bg_elevated': '#2a180c',
        'color_bg_subtle': '#3d2410',
        'color_bg_deep': '#120a04',
        'color_text': '#fff8f0',
        'color_text_muted': 'rgba(255, 248, 240, 0.72)',
        'color_border': 'rgba(248, 153, 29, 0.28)',
        'color_accent': '#F8991D',
        'use_gradient': True,
    },
}


class EwsetaWebsiteTheme(models.Model):
    _name = 'ewseta.website.theme'
    _description = 'EWSETA Custom Website Theme'
    _order = 'sequence, name'

    name = fields.Char(required=True, translate=True)
    key = fields.Char(
        string='Theme Key',
        required=True,
        index=True,
        copy=False,
        help='Used on the website. Must stay unique and start with custom_.',
    )
    settings_id = fields.Many2one(
        'ewseta.theme.settings',
        string='Theme Settings',
        required=True,
        ondelete='cascade',
    )
    website_id = fields.Many2one(
        related='settings_id.website_id',
        store=True,
        readonly=True,
    )
    sequence = fields.Integer(default=10)
    is_published = fields.Boolean(default=True)
    preset_template = fields.Selection(
        selection=[
            ('blank', 'Start Blank'),
            ('dark', 'From EWSETA Dark'),
            ('blue', 'From EWSETA Blue'),
            ('green', 'From EWSETA Green'),
            ('orange', 'From EWSETA Orange'),
        ],
        string='Start From Preset',
        default='blank',
        help='Optional starting palette based on an existing EWSETA brand theme.',
    )
    color_bg = fields.Char(string='Background', default='#121214')
    color_bg_elevated = fields.Char(string='Elevated Background', default='#1a1a1e')
    color_bg_subtle = fields.Char(string='Subtle Background', default='#222228')
    color_bg_deep = fields.Char(string='Deep Background', default='#0e0e10')
    color_text = fields.Char(string='Text', default='#f2f2f4')
    color_text_muted = fields.Char(string='Muted Text', default='rgba(242, 242, 244, 0.68)')
    color_border = fields.Char(string='Border', default='rgba(255, 255, 255, 0.1)')
    color_accent = fields.Char(string='Accent', default='#F8991D')
    use_gradient = fields.Boolean(
        string='Use Body Gradient',
        default=True,
        help='Applies a subtle vertical gradient on page backgrounds.',
    )
    toggle_icon = fields.Selection(
        selection=[
            ('paint-brush', 'Brush'),
            ('star', 'Star'),
            ('heart', 'Heart'),
            ('diamond', 'Diamond'),
            ('circle', 'Circle'),
            ('bookmark', 'Bookmark'),
        ],
        string='Toggle Icon',
        default='paint-brush',
        required=True,
    )

    _settings_key_uniq = models.Constraint(
        'unique(settings_id, key)',
        'Each custom theme key must be unique within the website theme settings.',
    )

    @api.model
    def _generate_key(self, name, settings_id=None):
        slug = re.sub(r'[^a-z0-9]+', '_', (name or 'theme').lower()).strip('_') or 'theme'
        base = f'custom_{slug}'[:50]
        key = base
        suffix = 1
        domain = [('key', '=', key)]
        if settings_id:
            domain.append(('settings_id', '=', settings_id))
        while self.search_count(domain):
            key = f'{base}_{suffix}'[:64]
            domain[0] = ('key', '=', key)
            suffix += 1
        return key

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('settings_id'):
                settings = self.env['ewseta.theme.settings']._get_or_create_for_website()
                if not settings:
                    raise ValidationError(
                        'Theme settings could not be resolved. Open Theme Settings first.'
                    )
                vals['settings_id'] = settings.id
            if not vals.get('key'):
                vals['key'] = self._generate_key(
                    vals.get('name'),
                    vals.get('settings_id'),
                )
        return super().create(vals_list)

    @api.onchange('preset_template')
    def _onchange_preset_template(self):
        template = PRESET_COLOR_TEMPLATES.get(self.preset_template)
        if not template:
            return
        for field_name, value in template.items():
            setattr(self, field_name, value)

    @api.onchange('name')
    def _onchange_name(self):
        if self.name and (not self.key or self.key.startswith('custom_theme')):
            self.key = self._generate_key(self.name, self.settings_id.id if self.settings_id else None)

    @api.constrains('key')
    def _check_key(self):
        for record in self:
            if not record.key.startswith('custom_'):
                raise ValidationError('Custom theme keys must start with "custom_".')
            if record.key in BUILTIN_THEME_KEYS:
                raise ValidationError(
                    'This theme key is reserved for a built-in EWSETA theme.'
                )

    def _body_gradient_css(self):
        self.ensure_one()
        if not self.use_gradient:
            return 'none'
        return (
            f'linear-gradient(180deg, {self.color_bg_elevated} 0%, '
            f'{self.color_bg} 45%, {self.color_bg_deep} 100%)'
        )

    def get_frontend_meta(self):
        self.ensure_one()
        return {
            'key': self.key,
            'label': str(self.name or ''),
            'type': 'custom',
            'toggleIcon': self.toggle_icon,
            'cssVars': {
                '--ewseta-dm-bg': self.color_bg,
                '--ewseta-dm-bg-elevated': self.color_bg_elevated,
                '--ewseta-dm-bg-subtle': self.color_bg_subtle,
                '--ewseta-dm-bg-deep': self.color_bg_deep,
                '--ewseta-dm-text': self.color_text,
                '--ewseta-dm-text-muted': self.color_text_muted,
                '--ewseta-dm-border': self.color_border,
                '--ewseta-dm-shadow': '0 4px 24px rgba(0, 0, 0, 0.35)',
                '--ewseta-voice-gradient-start': self.color_accent,
                '--ewseta-body-gradient': self._body_gradient_css(),
            },
        }

    @api.model
    def action_open_custom_themes(self):
        settings = self.env['ewseta.theme.settings']._get_or_create_for_website()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Custom Themes',
            'res_model': 'ewseta.website.theme',
            'view_mode': 'list,form',
            'domain': [('settings_id', '=', settings.id)],
            'context': {'default_settings_id': settings.id},
        }
