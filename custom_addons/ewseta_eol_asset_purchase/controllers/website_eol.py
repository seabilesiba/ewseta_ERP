# -*- coding: utf-8 -*-

from markupsafe import Markup

from odoo import http, _
from odoo.http import request
from odoo.exceptions import UserError, ValidationError
from odoo.tools.mail import is_html_empty

_EOL_PROGRAMME_INTRO_DEFAULT = (
    '<p>Request to purchase your end-of-life EWSETA IT asset under the official programme.</p>'
)


def _generic_error():
    return _('We could not process your request. Please check your details or try again later.')


class WebsiteEolAssetPurchase(http.Controller):

    def _public_enabled(self):
        return request.env['ir.config_parameter'].sudo().get_param(
            'ewseta_eol.public_form_enabled', 'True',
        ) == 'True'

    def _programme_intro(self):
        icp = request.env['ir.config_parameter'].sudo()
        raw = icp.get_param('ewseta_eol.programme_intro')
        if raw is None:
            raw = _EOL_PROGRAMME_INTRO_DEFAULT
        if is_html_empty(raw):
            return Markup('')
        return Markup(raw)

    def _categories(self):
        return request.env['ew.eol.asset.category'].sudo().search([
            ('active', '=', True),
        ], order='sequence, name')

    def _request_form_render(self, form=None, error=None):
        Request = request.env['ew.eol.purchase.request'].sudo()
        Policy = request.env['ew.eol.policy.document'].sudo()
        departments = request.env['hr.department'].sudo().search([], order='name')
        policy_form_sections = Policy.eol_public_form_sections()
        policies_ready = Policy.eol_public_policies_ready()
        if not error and not policies_ready:
            error = _(
                'Policy documents for Section 3 are not fully configured yet. '
                'Please contact ICT.'
            )
        return request.render('ewseta_eol_asset_purchase.eol_request_form', {
            'categories': self._categories(),
            'departments': departments,
            'site_options': Request.eol_public_site_options(),
            'policy_form_sections': policy_form_sections,
            'policies_ready': policies_ready,
            'programme_intro': self._programme_intro(),
            'form': form or {},
            'error': error,
        })

    def _parse_request_form(self, post):
        os_pref = (post.get('os_preference') or '').strip()
        if os_pref not in ('windows', 'macos', 'no_preference', ''):
            os_pref = ''
        return {
            'employee_name': (post.get('employee_name') or '').strip(),
            'employee_number': (post.get('employee_number') or '').strip(),
            'work_email': (post.get('work_email') or '').strip(),
            'department_name': (post.get('department_name') or '').strip(),
            'site_name': (post.get('site_name') or '').strip(),
            'category_id': post.get('category_id'),
            'request_type': post.get('request_type') or 'pool',
            'os_preference': os_pref or False,
            'serial_or_tag': (post.get('serial_or_tag') or '').strip(),
            'ack_quantity_limit': bool(post.get('ack_quantity_limit')),
            'ack_as_is': bool(post.get('ack_as_is')),
            'ack_data_software': bool(post.get('ack_data_software')),
            'ack_final_agreement': bool(post.get('ack_final_agreement')),
        }

    @http.route(
        ['/employee/eol-assets'],
        type='http',
        auth='public',
        website=True,
        sitemap=True,
    )
    def eol_landing(self, **kw):
        if not self._public_enabled():
            return request.render('ewseta_eol_asset_purchase.eol_public_disabled', {})
        return request.render('ewseta_eol_asset_purchase.eol_landing', {
            'programme_intro': self._programme_intro(),
            'policy_pages': request.env['ew.eol.policy.document'].sudo().eol_public_policy_pages(),
        })

    @http.route(
        ['/employee/eol-assets/request'],
        type='http',
        auth='public',
        website=True,
        methods=['GET', 'POST'],
        csrf=True,
    )
    def eol_request(self, **post):
        if not self._public_enabled():
            return request.render('ewseta_eol_asset_purchase.eol_public_disabled', {})
        if request.httprequest.method == 'GET':
            return self._request_form_render()
        form = self._parse_request_form(post)
        Request = request.env['ew.eol.purchase.request'].sudo()
        try:
            category_id = int(form['category_id'] or 0)
        except (TypeError, ValueError):
            category_id = 0
        if not category_id:
            return self._request_form_render(form, _('Please select a device type.'))
        if form['request_type'] not in ('assigned', 'pool'):
            return self._request_form_render(form, _generic_error())
        if not Request.eol_public_policies_ready():
            return self._request_form_render(form, _(
                'Each policy must have full text and a PDF uploaded under EOL Policies before you can submit.'
            ))
        if not all([
            form['ack_quantity_limit'],
            form['ack_as_is'],
            form['ack_data_software'],
            form['ack_final_agreement'],
        ]):
            return self._request_form_render(form, _(
                'You must read each policy and tick all acknowledgement boxes in Section 3.'
            ))
        vals = {
            'employee_name': form['employee_name'],
            'employee_number': form['employee_number'],
            'work_email': form['work_email'],
            'department_name': form['department_name'],
            'site_name': form['site_name'],
            'category_id': category_id,
            'request_type': form['request_type'],
            'os_preference': form['os_preference'],
            'serial_or_tag': form['serial_or_tag'],
            'ack_quantity_limit': form['ack_quantity_limit'],
            'ack_as_is': form['ack_as_is'],
            'ack_data_software': form['ack_data_software'],
            'ack_final_agreement': form['ack_final_agreement'],
        }
        try:
            req, track_token = Request.public_create_and_submit(vals)
        except UserError as exc:
            return self._request_form_render(form, str(exc.args[0]))
        except ValidationError:
            return self._request_form_render(form, _generic_error())
        return request.redirect(
            f'/employee/eol-assets/verify?request_id={req.id}&token={track_token}'
        )

    @http.route(
        ['/employee/eol-assets/verify'],
        type='http',
        auth='public',
        website=True,
        methods=['GET', 'POST'],
        csrf=True,
    )
    def eol_verify(self, request_id=None, token=None, **post):
        if not self._public_enabled():
            return request.render('ewseta_eol_asset_purchase.eol_public_disabled', {})
        try:
            rid = int(request_id or 0)
        except (TypeError, ValueError):
            rid = 0
        req = request.env['ew.eol.purchase.request'].sudo().browse(rid).exists()
        if not req or not token or not req.validate_tracking_token(token):
            return request.render('ewseta_eol_asset_purchase.eol_generic_error', {})
        if request.httprequest.method == 'GET':
            return request.render('ewseta_eol_asset_purchase.eol_verify_form', {
                'eol_request': req,
                'token': token,
                'error': None,
            })
        otp = (post.get('otp') or '').strip()
        token = post.get('token') or token
        try:
            rid = int(post.get('request_id') or request_id or 0)
        except (TypeError, ValueError):
            rid = 0
        req = request.env['ew.eol.purchase.request'].sudo().browse(rid).exists()
        if not req or not token or not req.validate_tracking_token(token):
            return request.render('ewseta_eol_asset_purchase.eol_generic_error', {})
        try:
            req.action_public_verify_and_continue(otp)
        except UserError:
            return request.render('ewseta_eol_asset_purchase.eol_verify_form', {
                'eol_request': req,
                'token': token,
                'error': _generic_error(),
            })
        req._send_confirmation_mail(token, email_verified=True)
        return request.redirect(f'/employee/eol-assets/track/{token}')

    @http.route(
        ['/employee/eol-assets/track/<string:token>'],
        type='http',
        auth='public',
        website=True,
        methods=['GET'],
    )
    def eol_track(self, token, **kw):
        Request = request.env['ew.eol.purchase.request'].sudo()
        matched = Request.find_by_tracking_token(token)
        if not matched:
            return request.render('ewseta_eol_asset_purchase.eol_generic_error', {})
        return request.render('ewseta_eol_asset_purchase.eol_track_status', {
            'eol_request': matched,
            'track': matched.eol_public_track_display(),
        })

    @http.route(
        ['/employee/eol-assets/policy/<string:doc_number>/view'],
        type='http',
        auth='public',
        website=True,
        methods=['GET'],
        sitemap=True,
    )
    def eol_policy_view(self, doc_number, **kw):
        if not self._public_enabled():
            return request.render('ewseta_eol_asset_purchase.eol_public_disabled', {})
        policy = request.env['ew.eol.policy.document'].sudo().find_public_by_form_item(doc_number)
        if not policy or not policy.is_published:
            return request.render('ewseta_eol_asset_purchase.eol_generic_error', {})
        return_url = kw.get('return_url') or '/employee/eol-assets/request'
        return request.render('ewseta_eol_asset_purchase.eol_policy_view', {
            'policy': policy,
            'policy_body_html': policy._render_policy_body_html(),
            'pdf_download_url': policy.eol_public_pdf_download_url(),
            'pdf_open_url': policy.eol_public_pdf_open_url(),
            'return_url': return_url,
        })

    @http.route(
        ['/employee/eol-assets/policy/<string:doc_number>/download'],
        type='http',
        auth='public',
        website=True,
        methods=['GET'],
    )
    def eol_policy_download(self, doc_number, **kw):
        if not self._public_enabled():
            return request.render('ewseta_eol_asset_purchase.eol_public_disabled', {})
        policy = request.env['ew.eol.policy.document'].sudo().find_public_by_form_item(doc_number)
        if not policy or not policy.has_document:
            return request.render('ewseta_eol_asset_purchase.eol_generic_error', {})
        attachment = policy._get_document_attachment()
        if not attachment:
            return request.render('ewseta_eol_asset_purchase.eol_generic_error', {})
        if not attachment.public:
            attachment.sudo().write({'public': True})
        return request.redirect(f'/web/content/{attachment.id}?download=true')

    @http.route(
        ['/employee/eol-assets/policy/<string:doc_number>'],
        type='http',
        auth='public',
        website=True,
        methods=['GET'],
    )
    def eol_policy_document(self, doc_number, **kw):
        """Legacy URL: open the readable policy page."""
        return request.redirect(f'/employee/eol-assets/policy/{doc_number}/view')
