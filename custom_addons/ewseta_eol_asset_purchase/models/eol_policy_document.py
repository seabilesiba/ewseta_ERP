# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

REQUIRED_FORM_ITEMS = ('10', '11', '12', '13')

ACK_FIELD_BY_FORM_ITEM = {
    '10': 'ack_quantity_limit',
    '11': 'ack_as_is',
    '12': 'ack_data_software',
    '13': 'ack_final_agreement',
}

LEGACY_ATTACHMENT_PARAMS = {
    '10': 'ewseta_eol.policy_attachment_id_10',
    '11': 'ewseta_eol.policy_attachment_id_11',
    '12': 'ewseta_eol.policy_attachment_id_12',
    '13': 'ewseta_eol.policy_attachment_id_13',
}

LEGACY_LABEL_PARAMS = {
    '10': 'ewseta_eol.policy_10_link_label',
    '11': 'ewseta_eol.policy_11_link_label',
    '12': 'ewseta_eol.policy_12_link_label',
    '13': 'ewseta_eol.policy_13_link_label',
}

LEGACY_PREFIX_PARAMS = {
    '10': 'ewseta_eol.policy_10_prefix',
    '11': 'ewseta_eol.policy_11_prefix',
    '12': 'ewseta_eol.policy_12_prefix',
    '13': 'ewseta_eol.policy_13_prefix',
}


class EolPolicyDocument(models.Model):
    _name = 'ew.eol.policy.document'
    _description = 'EOL programme policy document'
    _order = 'sequence, form_item'

    name = fields.Char(required=True, translate=True)
    form_item = fields.Selection(
        selection=[
            ('10', 'Form item 10 — quantity limits'),
            ('11', 'Form item 11 — as-is / no support'),
            ('12', 'Form item 12 — data and software'),
            ('13', 'Form item 13 — waiver and payment'),
        ],
        required=True,
        index=True,
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    link_label = fields.Char(
        string='Portal link title',
        required=True,
        translate=True,
        help='Short title shown as the downloadable link on the public form.',
    )
    prefix_text = fields.Char(
        string='Text before link',
        translate=True,
        help='Shown before the link on the acknowledgement line. Item 10 may use {limit}.',
    )
    page_summary = fields.Html(
        string='Summary on public pages',
        sanitize=True,
        help='Short teaser shown in the policy list on the landing and request pages.',
    )
    policy_body = fields.Html(
        string='Policy text (public page)',
        sanitize=True,
        translate=True,
        help='Full policy wording shown on the public policy page. Item 10 may use {limit}.',
    )
    version = fields.Char(string='Document version', help='e.g. v2026-01')
    document = fields.Binary(string='Policy file', attachment=True, required=False)
    document_filename = fields.Char(string='Filename')
    has_document = fields.Boolean(compute='_compute_has_document')
    has_policy_body = fields.Boolean(compute='_compute_has_policy_body')
    is_published = fields.Boolean(compute='_compute_is_published')
    ack_field_name = fields.Char(compute='_compute_ack_field_name', store=True)

    _sql_constraints = [
        (
            'form_item_unique',
            'unique(form_item)',
            'Each form item (10–13) can only have one policy record.',
        ),
    ]

    @api.depends('document')
    def _compute_has_document(self):
        Attachment = self.env['ir.attachment'].sudo()
        for policy in self:
            att = policy._get_document_attachment()
            if not att and policy.document:
                att = Attachment.search([
                    ('res_model', '=', policy._name),
                    ('res_id', '=', policy.id),
                    ('res_field', '=', 'document'),
                ], limit=1)
            policy.has_document = bool(att)

    @api.depends('policy_body')
    def _compute_has_policy_body(self):
        for policy in self:
            body = policy._render_policy_body_html()
            policy.has_policy_body = bool(body)

    @api.depends('has_document', 'has_policy_body')
    def _compute_is_published(self):
        for policy in self:
            policy.is_published = policy.has_document and policy.has_policy_body

    @api.depends('form_item')
    def _compute_ack_field_name(self):
        for policy in self:
            policy.ack_field_name = ACK_FIELD_BY_FORM_ITEM.get(policy.form_item or '', '')

    @api.constrains('form_item', 'active')
    def _check_required_items(self):
        for policy in self:
            if policy.active and policy.form_item not in REQUIRED_FORM_ITEMS:
                raise ValidationError(_('Invalid form item for EOL policies.'))

    def _get_document_attachment(self):
        self.ensure_one()
        return self.env['ir.attachment'].sudo().search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('res_field', '=', 'document'),
        ], limit=1, order='id desc')

    def _mark_attachment_public(self):
        for policy in self:
            att = policy._get_document_attachment()
            if att and not att.public:
                att.sudo().write({'public': True})

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._mark_attachment_public()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'document' in vals or 'document_filename' in vals:
            self._mark_attachment_public()
        return res

    @api.model
    def _quantity_limit_text(self):
        return self.env['ew.eol.purchase.request'].eol_quantity_limit_ack_text()

    @api.model
    def _public_domain(self):
        return [
            ('active', '=', True),
            ('form_item', 'in', list(REQUIRED_FORM_ITEMS)),
        ]

    @api.model
    def eol_public_policies(self):
        return self.sudo().search(self._public_domain(), order='sequence, form_item')

    @api.model
    def eol_public_policies_ready(self):
        policies = self.eol_public_policies()
        if len(policies) != len(REQUIRED_FORM_ITEMS):
            return False
        return all(policy.is_published for policy in policies)

    def _render_policy_body_html(self):
        self.ensure_one()
        from odoo.tools import html2plaintext

        limit = self._quantity_limit_text()
        body = (self.policy_body or '').replace('{limit}', limit)
        if not html2plaintext(body or '').strip():
            return ''
        return body

    def eol_public_view_url(self):
        self.ensure_one()
        return f'/employee/eol-assets/policy/{self.form_item}/view'

    def eol_public_pdf_download_url(self):
        self.ensure_one()
        return f'/employee/eol-assets/policy/{self.form_item}/download'

    def eol_public_pdf_open_url(self):
        self.ensure_one()
        att = self._get_document_attachment()
        if not att:
            return False
        return f'/web/content/{att.id}'

    @api.model
    def eol_public_policy_pages(self):
        """Policies listed on landing / request pages (download links)."""
        pages = []
        for policy in self.eol_public_policies():
            pages.append({
                'id': policy.id,
                'form_item': policy.form_item,
                'name': policy.name,
                'link_label': policy.link_label,
                'summary': policy.page_summary,
                'view_url': policy.eol_public_view_url(),
                'pdf_download_url': policy.eol_public_pdf_download_url(),
                'pdf_open_url': policy.eol_public_pdf_open_url(),
                'is_published': policy.is_published,
            })
        return pages

    @api.model
    def eol_public_form_sections(self):
        """Policy rows on the request form: actions + mandatory acknowledgement checkbox."""
        limit = self._quantity_limit_text()
        sections = []
        for form_item in REQUIRED_FORM_ITEMS:
            policy = self.sudo().search([('form_item', '=', form_item)], limit=1)
            if not policy:
                sections.append({
                    'form_item': form_item,
                    'name': _('Policy item %s') % form_item,
                    'link_label': _('Policy document'),
                    'summary': False,
                    'view_url': False,
                    'pdf_download_url': False,
                    'pdf_open_url': False,
                    'is_published': False,
                    'field_name': ACK_FIELD_BY_FORM_ITEM.get(form_item, ''),
                    'prefix': _('I have read and accept the'),
                    'ack_url': False,
                })
                continue
            prefix = (policy.prefix_text or '').replace('{limit}', limit).strip()
            if not prefix:
                prefix = _('I have read and accept the')
            sections.append({
                'form_item': policy.form_item,
                'name': policy.name,
                'link_label': policy.link_label,
                'summary': policy.page_summary,
                'view_url': policy.eol_public_view_url(),
                'pdf_download_url': policy.eol_public_pdf_download_url(),
                'pdf_open_url': policy.eol_public_pdf_open_url(),
                'is_published': policy.is_published,
                'field_name': policy.ack_field_name,
                'prefix': prefix,
                'ack_url': policy.eol_public_view_url() if policy.is_published else False,
            })
        return sections

    @api.model
    def eol_public_policy_acknowledgements(self):
        limit = self._quantity_limit_text()
        acknowledgements = []
        for policy in self.eol_public_policies():
            prefix = (policy.prefix_text or '').replace('{limit}', limit).strip()
            acknowledgements.append({
                'number': policy.form_item,
                'field_name': policy.ack_field_name,
                'prefix': prefix,
                'link_label': policy.link_label,
                'url': policy.eol_public_view_url() if policy.is_published else False,
                'configured': policy.is_published,
            })
        return acknowledgements

    def eol_public_download_url(self):
        """Backward-compatible alias for PDF download route."""
        self.ensure_one()
        return self.eol_public_pdf_download_url()

    @api.model
    def find_public_by_form_item(self, form_item):
        return self.sudo().search([
            ('active', '=', True),
            ('form_item', '=', str(form_item)),
        ], limit=1)

    @api.model
    def _ensure_policy_body_from_summary(self):
        from odoo.tools import html2plaintext

        for policy in self.search([]):
            if html2plaintext(policy.policy_body or '').strip():
                continue
            summary = html2plaintext(policy.page_summary or '').strip()
            if summary:
                policy.policy_body = f'<p>{summary}</p>'

    @api.model
    def _migrate_legacy_settings_policies(self):
        """One-time import from old EOL settings attachments (if any)."""
        icp = self.env['ir.config_parameter'].sudo()
        Attachment = self.env['ir.attachment'].sudo()
        for form_item in REQUIRED_FORM_ITEMS:
            policy = self.search([('form_item', '=', form_item)], limit=1)
            if not policy:
                continue
            updates = {}
            label_key = LEGACY_LABEL_PARAMS.get(form_item)
            prefix_key = LEGACY_PREFIX_PARAMS.get(form_item)
            if label_key:
                label = icp.get_param(label_key)
                if label and not policy.link_label:
                    updates['link_label'] = label
            if prefix_key:
                prefix = icp.get_param(prefix_key)
                if prefix and not policy.prefix_text:
                    updates['prefix_text'] = prefix
            if updates:
                policy.write(updates)
            if policy.has_document:
                continue
            att_param = LEGACY_ATTACHMENT_PARAMS.get(form_item)
            if not att_param:
                continue
            att_id = int(icp.get_param(att_param, '0') or '0')
            legacy = Attachment.browse(att_id).exists()
            if not legacy or not legacy.datas:
                continue
            policy.write({
                'document': legacy.datas,
                'document_filename': legacy.name or f'eol-policy-{form_item}.pdf',
            })
        self._ensure_policy_body_from_summary()
