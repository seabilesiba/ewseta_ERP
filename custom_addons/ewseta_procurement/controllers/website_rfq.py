import base64
import mimetypes
import os

from urllib.parse import quote

from werkzeug.utils import secure_filename

from odoo import http, fields, _
from odoo.exceptions import UserError, ValidationError
from odoo.http import request

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
ALLOWED_UPLOAD_EXTENSIONS = frozenset({
    ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".png", ".jpg", ".jpeg",
})


def _validate_upload(storage, label):
    """Return an error message string, or None if the upload is acceptable."""
    if not storage or not storage.filename:
        return None
    ext = os.path.splitext(storage.filename)[1].lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        return _("%(label)s: file type %(ext)s is not allowed.") % {
            "label": label,
            "ext": ext or _("(none)"),
        }
    payload = storage.read()
    storage.seek(0)
    if len(payload) > MAX_UPLOAD_BYTES:
        return _("%(label)s: file exceeds the %(mb)s MB limit.") % {
            "label": label,
            "mb": MAX_UPLOAD_BYTES // (1024 * 1024),
        }
    return None


class WebsiteRFQ(http.Controller):
    """Public RFQ listing and submission (no login required)."""

    @staticmethod
    def _public_portal_rfq_or_not_found(rfq):
        """Public RFQs, or transversal RFQs only once they have closed."""
        rfq = rfq.sudo().exists() if rfq else rfq
        if not rfq or not rfq.assert_public_portal_access():
            return None
        return rfq

    @staticmethod
    def _public_portal_apply_rfq_or_not_found(rfq):
        """Public RFQs, plus transversal RFQs via the emailed apply link (not listed while open)."""
        rfq = rfq.sudo().exists() if rfq else rfq
        if not rfq or rfq.state == "cancelled":
            return None
        if rfq.publication_type == "public":
            return rfq
        if rfq.publication_type == "transversal" and rfq.state in ("published", "closed"):
            return rfq
        return None

    @staticmethod
    def _form_checkbox_accepted(value):
        if isinstance(value, (list, tuple)):
            value = value[-1] if value else None
        return value in ("on", "true", "1", "yes", True)

    @staticmethod
    def _portal_token_from_request(token=None, **kw):
        token = (token or kw.get('token') or '').strip()
        if token:
            return token
        stash = request.session.get('ew_proc_submission_thanks') or {}
        return (stash.get('token') or '').strip()

    @staticmethod
    def _briefing_submission_from_token(rfq_id, token):
        """Resolve application for briefing register (token must match this RFQ)."""
        token = (token or '').strip()
        if not token:
            return request.env['ew.submission'].browse()
        submission = request.env['ew.submission'].sudo().find_by_tracking_token(token)
        if (
            not submission
            or submission.rfq_id.id != rfq_id
            or submission.state not in ('submitted', 'closed')
        ):
            return request.env['ew.submission'].browse()
        return submission

    @classmethod
    def _briefing_submission_for_register(cls, rfq_id, token):
        """Token link, or logged-in applicant's own submission for this RFQ (public or transversal)."""
        submission = cls._briefing_submission_from_token(rfq_id, token)
        if submission:
            return submission, (token or '').strip() or submission.track_token
        rfq = request.env['ew.rfq'].sudo().browse(rfq_id).exists()
        if not rfq:
            return request.env['ew.submission'].browse(), token
        user = request.env.user
        if not user or user._is_public() or not user.partner_id:
            return request.env['ew.submission'].browse(), token
        submission = request.env['ew.submission'].sudo().search([
            ('rfq_id', '=', rfq_id),
            ('partner_id', '=', user.partner_id.id),
            ('state', 'in', ('submitted', 'closed')),
        ], limit=1)
        if not submission:
            return request.env['ew.submission'].browse(), token
        track_token = submission._issue_tracking_token()
        return submission, track_token

    def _portal_briefing_template_extras(self, rfq, token=None):
        """Live briefing join / register links for portal templates."""
        rfq = rfq.sudo().exists() if rfq else rfq
        if not rfq or not rfq.briefing_session:
            return {}
        rfq._portal_trigger_briefing_start_emails_if_due()
        if not rfq.portal_show_briefing_join_details():
            return {}
        extras = {
            "briefing_register_url": f"/application/rfqs/{rfq.id}/briefing/register",
        }
        submission, track = self._briefing_submission_for_register(
            rfq.id,
            self._portal_token_from_request(token=token),
        )
        contact = None
        if submission:
            contact = self._portal_values_from_submission(submission)
        if submission and track:
            extras["track_token"] = track
            extras["briefing_register_url"] = (
                f"/application/rfqs/{rfq.id}/briefing/register?token={quote(track, safe='')}"
            )
        stash = request.session.get("ew_proc_briefing_registered") or {}
        if stash.get("rfq_id") == rfq.id and stash.get("attendance_id"):
            attendance = request.env["ew.rfq.briefing.attendance"].sudo().browse(
                stash["attendance_id"]
            ).exists()
            if attendance:
                extras["briefing_already_registered"] = True
                extras["briefing_attendance_proof_url"] = attendance._portal_proof_url()
                contact = {
                    "company_name": attendance.company_name or "",
                    "contact_name": attendance.contact_name or "",
                    "contact_email": attendance.contact_email or "",
                    "contact_phone": attendance.contact_phone or "",
                }
        if contact:
            extras["briefing_contact_values"] = contact
            extras.setdefault("briefing_register_values", contact)
        return extras

    @staticmethod
    def _portal_values_from_submission(submission):
        return {
            'company_name': submission.company_name or '',
            'contact_name': submission.contact_name or '',
            'contact_email': submission.contact_email or '',
            'contact_phone': submission.contact_phone or '',
        }

    @staticmethod
    def _merge_contact_into_apply_values(values, extras):
        values = dict(values or {})
        contact = (extras or {}).get("briefing_contact_values") or {}
        for key in ("company_name", "contact_name", "contact_email", "contact_phone"):
            if not (values.get(key) or "").strip() and (contact.get(key) or "").strip():
                values[key] = contact[key]
        return values

    def _render_rfq_apply_form(self, rfq, errors, values, extra=None, portal_token=None):
        mand = rfq.requirement_ids.filtered(lambda r: r.is_mandatory)
        opti = rfq.requirement_ids.filtered(lambda r: not r.is_mandatory)
        extras = self._portal_briefing_template_extras(rfq, token=portal_token)
        if extra:
            extras.update(extra)
        ctx = {
            'rfq': rfq,
            'req_mand': mand,
            'req_opt': opti,
            'errors': errors,
            'values': self._merge_contact_into_apply_values(values, extras),
        }
        ctx.update(extras)
        return request.render('ewseta_procurement.rfq_apply_form', ctx)

    @http.route(
        ['/application/procurement', '/application'],
        type='http',
        auth='public',
        website=True,
        sitemap=False,
    )
    def procurement_landing_redirect(self, **kw):
        """Legacy URLs → website homepage (procurement landing)."""
        return request.redirect('/')

    @staticmethod
    def _rfq_portal_document_visible(rfq):
        """Spec download: public RFQs, plus transversal via the emailed apply form."""
        rfq = WebsiteRFQ._public_portal_apply_rfq_or_not_found(rfq)
        if not rfq or not rfq.portal_has_rfq_document():
            return False
        return rfq.state in ("published", "closed")

    @staticmethod
    def _policy_document_portal_visible(doc):
        if not doc:
            return False
        if doc.website_id and request.website and doc.website_id != request.website:
            return False
        return doc.portal_is_visible()

    @http.route(
        ['/application/rfq-policy'],
        type='http',
        auth='public',
        website=True,
        methods=['GET'],
        sitemap=True,
    )
    def rfq_policy_public_page(self, **kw):
        return request.render('ewseta_procurement.rfq_policy_public_page', {})

    @http.route(
        ['/application/rfq-policy/document/<int:doc_id>'],
        type='http',
        auth='public',
        website=True,
        methods=['GET'],
        sitemap=False,
    )
    def rfq_policy_public_document(self, doc_id, download=None, **kw):
        doc = request.env['proc.cms.policy.document'].sudo().browse(doc_id).exists()
        if not self._policy_document_portal_visible(doc):
            return request.not_found()

        filename = secure_filename(doc.portal_file_label()) or 'policy-document.pdf'
        ext = os.path.splitext(filename)[1].lower()
        is_pdf = ext == '.pdf'
        force_download = download in ('1', 'true', 'yes') or not is_pdf

        content = base64.b64decode(doc.file)
        content_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'

        headers = [
            ('Content-Type', content_type),
            ('Content-Length', len(content)),
            ('X-Content-Type-Options', 'nosniff'),
        ]
        disposition = 'attachment' if force_download else 'inline'
        headers.append((
            'Content-Disposition',
            f'{disposition}; filename="{filename}"',
        ))
        return request.make_response(content, headers=headers)

    @staticmethod
    def _rfq_is_closed(rfq, now):
        if not rfq:
            return True
        if rfq.state == "closed":
            return True
        return (
            rfq.state == "published"
            and rfq.closing_at
            and rfq.closing_at <= now
        )

    @http.route(['/application/rfqs'], type='http', auth='public', website=True, sitemap=True)
    def rfq_public_list(self, **kw):
        now = fields.Datetime.now()
        RFQ = request.env['ew.rfq'].sudo()

        open_rfqs = RFQ.search(
            RFQ._portal_open_domain(now),
            order='closing_at asc, create_date desc',
        )
        closed_rfqs = RFQ.search(
            RFQ._portal_closed_domain(now),
            order='closing_at desc, create_date desc',
        )
        closed_transversal_rfqs = RFQ.search(
            RFQ._portal_closed_transversal_domain(now),
            order='closing_at desc, create_date desc',
        )

        return request.render('ewseta_procurement.rfq_public_list', {
            'open_rfqs': open_rfqs,
            'closed_rfqs': closed_rfqs,
            'closed_transversal_rfqs': closed_transversal_rfqs,
            'now': now,
        })

    @http.route(
        [
            '/application/rfqs/<int:rfq_id>/submissions',
            '/application/rfqs/<int:rfq_id>',  # legacy; prefer /submissions
        ],
        type='http',
        auth='public',
        website=True,
        sitemap=False,
        methods=['GET'],
    )
    def rfq_public_detail(self, rfq_id, **kw):
        """Closed RFQ/RFP: public summary and list of received submissions."""
        now = fields.Datetime.now()
        rfq = request.env['ew.rfq'].sudo().browse(rfq_id).exists()
        rfq = self._public_portal_rfq_or_not_found(rfq)
        if not rfq:
            return request.not_found()

        if not self._rfq_is_closed(rfq, now):
            return request.redirect(f'/application/rfqs/{rfq_id}/apply')

        submissions = request.env['ew.submission'].sudo().search([
            ('rfq_id', '=', rfq.id),
            ('state', 'in', ['submitted', 'closed']),
        ], order='submitted_at desc, id desc')

        return request.render('ewseta_procurement.rfq_public_detail', {
            'rfq': rfq,
            'submissions': submissions,
        })

    @http.route(['/application/rfqs/<int:rfq_id>/apply'], type='http', auth='public', website=True, sitemap=False, methods=['GET'])
    def rfq_apply_form(self, rfq_id, **kw):
        RFQ = request.env['ew.rfq'].sudo()
        rfq = self._public_portal_apply_rfq_or_not_found(RFQ.browse(rfq_id))
        now = fields.Datetime.now()
        if not rfq or rfq.state != 'published' or not rfq.closing_at or rfq.closing_at <= now:
            return request.not_found() if not rfq else request.render(
                'ewseta_procurement.rfq_closed_or_missing', {'rfq': rfq}
            )

        return self._render_rfq_apply_form(
            rfq, {}, {}, portal_token=kw.get("token"),
        )

    @http.route(['/application/rfqs/<int:rfq_id>/apply/submit'], type='http', auth='public',
                website=True, csrf=True, methods=['POST'])
    def rfq_apply_submit(self, rfq_id, **post):
        env = request.env
        RFQ = env['ew.rfq'].sudo()
        now = fields.Datetime.now()
        rfq = self._public_portal_apply_rfq_or_not_found(RFQ.browse(rfq_id))
        if not rfq:
            return request.not_found()

        # # PRIVATE RFQ VALIDATION
        # if rfq.is_private:
        #     # Identify current provider by email
        #     provider_email = (post.get("contact_email") or "").strip()
        #     provider = request.env["res.partner"].sudo().search(
        #         [('email', '=ilike', provider_email)], limit=1
        #     )
        #
        #     if not provider or provider not in rfq.invited_provider_ids:
        #         return request.render("ewseta_procurement.rfq_closed_or_missing", {
        #             'rfq': rfq,
        #             'error_msg': "You are not authorized to apply for this private RFQ."
        #         })
        #
        # if not rfq or rfq.state != 'published' or not rfq.closing_at or rfq.closing_at <= now:
        #     return request.render('ewseta_procurement.rfq_closed_or_missing', {'rfq': rfq})

        # -------------------------------
        #  BASIC FORM FIELDS
        # -------------------------------
        company_name  = (post.get('company_name') or '').strip()
        contact_name  = (post.get('contact_name') or '').strip()
        contact_phone = (post.get('contact_phone') or '').strip()
        contact_email = (post.get('contact_email') or '').strip()
        privacy_accepted = self._form_checkbox_accepted(post.get('accept_privacy_policy'))

        form_values = {
            'company_name': company_name,
            'contact_name': contact_name,
            'contact_phone': contact_phone,
            'contact_email': contact_email,
            'accept_privacy_policy': privacy_accepted,
        }

        errors = {}
        if not company_name:
            errors['company_name'] = _("Company name is required.")
        if not contact_email:
            errors['contact_email'] = _("Email is required.")
        if not privacy_accepted:
            errors['privacy_policy'] = _(
                "You must accept the RFQ privacy policy before you can submit your application."
            )

        files = request.httprequest.files
        missing_docs = []
        upload_errors = []
        for req in rfq.requirement_ids:
            storage = files.get(f"file_req_{req.id}")
            if req.is_mandatory and (not storage or not storage.filename):
                missing_docs.append(req.name)
                continue
            if storage and storage.filename:
                err = _validate_upload(storage, req.name)
                if err:
                    upload_errors.append(err)
        if missing_docs:
            errors['files'] = _("Missing files for mandatory documents: %s") % ", ".join(missing_docs)
        if upload_errors:
            errors['files'] = (errors.get('files', '') + ' ' if errors.get('files') else '') + ' '.join(upload_errors)

        if errors:
            return self._render_rfq_apply_form(
                rfq, errors, form_values, portal_token=post.get("token"),
            )

        # -------------------------------
        #  CREATE OR REUSE PARTNER
        # -------------------------------
        Partner = env['res.partner'].sudo()
        partner = Partner.search([
            ('email', '=ilike', contact_email),
            ('ew_service_provider', '=', True),
        ], limit=1)
        if not partner:
            by_email = Partner.search([('email', '=ilike', contact_email)], limit=1)
            if by_email and by_email.parent_id and by_email.parent_id.ew_service_provider:
                partner = by_email.parent_id
            else:
                partner = by_email
        if not partner:
            partner = Partner.create({
                'name': company_name or contact_name or contact_email,
                'email': contact_email,
                'company_type': 'company',
            })

        # -------------------------------
        #  PREVENT DUPLICATE SUBMISSION
        # -------------------------------
        existing_submission = env['ew.submission'].sudo().search([
            ('rfq_id', '=', rfq.id),
            ('partner_id', '=', partner.id),
        ], limit=1)
        if existing_submission:
            dup_token = existing_submission._issue_tracking_token()
            if rfq.portal_applications_open():
                safe_token = quote(dup_token, safe='')
                return request.redirect(
                    f'/application/submissions/track/{safe_token}'
                )
            return self._render_rfq_apply_form(
                rfq,
                {'duplicate': _("You have already submitted an application for this RFQ.")},
                form_values,
                portal_token=dup_token,
            )

        # -------------------------------
        #  CREATE SUBMISSION
        # -------------------------------
        accepted_at = fields.Datetime.now()
        submission = env['ew.submission'].sudo().with_context(
            ew_public_website_apply=True,
        ).create({
            'rfq_id': rfq.id,
            'partner_id': partner.id,
            'company_name': company_name or partner.name,
            'contact_name': contact_name,
            'contact_phone': contact_phone,
            'contact_email': contact_email,
            'state': 'submitted',
            'submitted_at': accepted_at,
            'privacy_policy_accepted': True,
            'privacy_policy_accepted_at': accepted_at,
        })

        submission.sudo().message_post(
            body=_("Application submitted via the website (SCM is notified when the RFQ closes)."),
            subtype_xmlid="mail.mt_note",
        )

        # -------------------------------
        #  CREATE LINES AND ATTACH FILES
        # -------------------------------
        existing_lines = {l.requirement_id.id: l for l in submission.sudo().line_ids}
        for req in rfq.requirement_ids:
            storage = files.get(f"file_req_{req.id}")
            line = existing_lines.get(req.id)
            if not line:
                line = env['ew.submission.line'].sudo().create({
                    'submission_id': submission.id,
                    'requirement_id': req.id,
                })
                existing_lines[req.id] = line

            if storage and storage.filename:
                filename = secure_filename(storage.filename) or (req.name or 'document')
                content = base64.b64encode(storage.read())
                line.write({
                    'file': content,
                    'file_filename': filename,
                })

        track_token = submission._issue_tracking_token()
        request.env.flush_all()
        request.session['ew_proc_submission_thanks'] = {
            'submission_id': submission.id,
            'token': track_token,
        }
        submission._send_portal_application_received(track_token)

        safe_token = quote(track_token, safe='')
        return request.redirect(
            f'/application/submissions/thanks/{safe_token}'
        )

    @http.route(
        [
            '/application/submissions/thanks',
            '/application/submissions/thanks/<string:token>',
        ],
        type='http',
        auth='public',
        website=True,
        sitemap=False,
        methods=['GET'],
    )
    def submission_apply_thanks(self, token=None, **kw):
        token = self._portal_token_from_request(token, **kw)
        stash = request.session.get('ew_proc_submission_thanks') or {}
        submission = request.env['ew.submission'].portal_resolve_submission(
            token,
            trusted_submission_id=stash.get('submission_id'),
        )
        track_token = token if submission else None
        rfq = submission.rfq_id if submission else None
        ctx = {
            'submission': submission,
            'rfq': rfq,
            'track_token': track_token,
            'track_url': submission._portal_track_url(track_token) if submission and track_token else '',
        }
        if rfq:
            ctx.update(self._portal_briefing_template_extras(rfq, token=track_token))
        return request.render('ewseta_procurement.rfq_apply_thanks', ctx)

    def _render_submission_track(self, token, errors=None, values=None, updated=False):
        submission = request.env['ew.submission'].find_by_tracking_token(token)
        if not submission:
            return request.render('ewseta_procurement.submission_track_missing', {})
        rfq = submission.rfq_id.sudo()
        rfq._auto_close_if_due()
        reference = submission.portal_track_reference_rows()
        can_update = submission.portal_may_update()
        existing_lines = {line.requirement_id.id: line for line in submission.sudo().line_ids}
        ctx = {
            'submission': submission,
            'rfq': rfq,
            'track_token': token,
            'track_url': submission._portal_track_url(token),
            'supplier_rows': reference['supplier'],
            'application_rows': reference['application'],
            'can_update': can_update,
            'errors': errors or {},
            'values': values or self._portal_values_from_submission(submission),
            'briefing_portal_readonly': not can_update,
            'updated': updated,
            'update_docs': [
                {'req': req, 'line': existing_lines.get(req.id)}
                for req in rfq.requirement_ids
            ],
        }
        ctx.update(self._portal_briefing_template_extras(rfq, token=token))
        ctx['briefing_portal_readonly'] = not can_update
        return request.render('ewseta_procurement.submission_public_track', ctx)

    @http.route(
        ['/application/submissions/track/<string:token>'],
        type='http',
        auth='public',
        website=True,
        sitemap=False,
        methods=['GET'],
    )
    def submission_public_track(self, token, **kw):
        return self._render_submission_track(
            token,
            updated=kw.get('updated') in ('1', 'true', 'yes'),
        )

    @http.route(
        ['/application/submissions/track/<string:token>/update'],
        type='http',
        auth='public',
        website=True,
        csrf=True,
        methods=['POST'],
    )
    def submission_public_track_update(self, token, **post):
        submission = request.env['ew.submission'].find_by_tracking_token(token)
        if not submission:
            return request.render('ewseta_procurement.submission_track_missing', {})
        rfq = submission.rfq_id.sudo()
        rfq._auto_close_if_due()
        if not submission.portal_may_update():
            return self._render_submission_track(
                token,
                errors={'closed': _("This RFQ/RFP is closed. You cannot update your application.")},
            )

        company_name = (post.get('company_name') or '').strip()
        contact_name = (post.get('contact_name') or '').strip()
        contact_phone = (post.get('contact_phone') or '').strip()
        contact_email = (post.get('contact_email') or '').strip()
        form_values = {
            'company_name': company_name,
            'contact_name': contact_name,
            'contact_phone': contact_phone,
            'contact_email': contact_email,
        }
        errors = {}
        if not company_name:
            errors['company_name'] = _("Company name is required.")
        if not contact_email:
            errors['contact_email'] = _("Email is required.")
        if not contact_phone:
            errors['contact_phone'] = _("Contact phone is required.")

        files = request.httprequest.files
        file_payloads = {}
        upload_errors = []
        existing_lines = {line.requirement_id.id: line for line in submission.sudo().line_ids}
        for req in rfq.requirement_ids:
            storage = files.get(f"file_req_{req.id}")
            has_existing = bool(
                existing_lines.get(req.id)
                and (existing_lines[req.id].file or existing_lines[req.id].file_filename)
            )
            if req.is_mandatory and not has_existing and (not storage or not storage.filename):
                upload_errors.append(_("Missing file for mandatory document: %s") % req.name)
                continue
            if storage and storage.filename:
                err = _validate_upload(storage, req.name)
                if err:
                    upload_errors.append(err)
                    continue
                filename = secure_filename(storage.filename) or (req.name or 'document')
                file_payloads[req.id] = (base64.b64encode(storage.read()), filename)
        if upload_errors:
            errors['files'] = ' '.join(upload_errors)
        if errors:
            return self._render_submission_track(token, errors=errors, values=form_values)

        try:
            submission.sudo().with_context(ew_public_website_apply=True).portal_update_application(
                form_values,
                files=file_payloads,
            )
        except (UserError, ValidationError) as err:
            return self._render_submission_track(
                token,
                errors={'form': str(err.args[0] if err.args else err)},
                values=form_values,
            )
        return request.redirect(f'/application/submissions/track/{quote(token, safe="")}?updated=1')

    @http.route(
        ['/application/submissions/file/<int:line_id>'],
        type='http',
        auth='public',
        website=True,
        methods=['GET'],
        sitemap=False,
    )
    def submission_public_file(self, line_id, token=None, download=None, **kw):
        """Download or inline-view a submitted document (token required)."""
        submission = request.env['ew.submission'].find_by_tracking_token(token or '')
        line = request.env['ew.submission.line'].sudo().browse(line_id).exists()
        if (
            not submission
            or not line
            or line.submission_id.id != submission.id
        ):
            return request.not_found()

        raw_b64 = line.file
        if not raw_b64 and line.attachment_id:
            raw_b64 = line.attachment_id.datas
        if not raw_b64:
            return request.not_found()

        filename = secure_filename(line.file_filename or 'document') or 'document'
        ext = os.path.splitext(filename)[1].lower()
        is_pdf = ext == '.pdf'
        force_download = download in ('1', 'true', 'yes') or not is_pdf

        content = base64.b64decode(raw_b64)
        content_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'

        headers = [
            ('Content-Type', content_type),
            ('Content-Length', len(content)),
            ('X-Content-Type-Options', 'nosniff'),
        ]
        disposition = 'attachment' if force_download else 'inline'
        headers.append((
            'Content-Disposition',
            f'{disposition}; filename="{filename}"',
        ))
        return request.make_response(content, headers=headers)

    @http.route(
        ['/application/rfqs/<int:rfq_id>/document'],
        type='http',
        auth='public',
        website=True,
        methods=['GET'],
        sitemap=False,
    )
    def rfq_public_document(self, rfq_id, download=None, **kw):
        """Download or view the RFQ/RFP document uploaded by SCM (published/closed only)."""
        rfq = request.env['ew.rfq'].sudo().browse(rfq_id).exists()
        if not self._rfq_portal_document_visible(rfq):
            return request.not_found()

        document, doc_filename = rfq._portal_procurement_document()
        default_name = 'RFP-document.pdf' if rfq.type == 'rfp' else 'RFQ-document.pdf'
        filename = secure_filename(doc_filename or default_name) or default_name
        ext = os.path.splitext(filename)[1].lower()
        is_pdf = ext == '.pdf'
        force_download = download in ('1', 'true', 'yes') or not is_pdf

        content = base64.b64decode(document)
        content_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'

        headers = [
            ('Content-Type', content_type),
            ('Content-Length', len(content)),
            ('X-Content-Type-Options', 'nosniff'),
        ]
        disposition = 'attachment' if force_download else 'inline'
        headers.append((
            'Content-Disposition',
            f'{disposition}; filename="{filename}"',
        ))
        return request.make_response(content, headers=headers)

    @http.route(
        ['/application/rfqs/<int:rfq_id>/briefing/register'],
        type='http',
        auth='public',
        website=True,
        sitemap=False,
        methods=['GET'],
    )
    def briefing_register_form(self, rfq_id, token=None, **kw):
        rfq = request.env['ew.rfq'].sudo().browse(rfq_id).exists()
        token = self._portal_token_from_request(token, **kw)
        submission, token = self._briefing_submission_for_register(rfq_id, token)
        if not submission:
            if rfq and rfq.briefing_session:
                return request.render('ewseta_procurement.briefing_register_closed', {
                    'rfq': rfq,
                    'registration_state': 'no_application',
                })
            return request.render('ewseta_procurement.briefing_register_invalid_link', {
                'rfq': rfq,
            })
        if rfq:
            rfq._portal_trigger_briefing_start_emails_if_due()
        if not rfq or not rfq.briefing_session or not rfq.portal_briefing_rfq_eligible():
            return request.render('ewseta_procurement.briefing_register_closed', {
                'rfq': rfq,
                'registration_state': 'unavailable',
            })
        if not rfq.portal_applications_open():
            return request.render('ewseta_procurement.briefing_register_closed', {
                'rfq': rfq,
                'registration_state': 'after',
            })
        registration_state = rfq.portal_briefing_registration_state()
        if registration_state != 'open':
            return request.render('ewseta_procurement.briefing_register_closed', {
                'rfq': rfq,
                'registration_state': registration_state,
            })
        return request.render('ewseta_procurement.briefing_register_form', {
            'rfq': rfq,
            'errors': {},
            'values': self._portal_values_from_submission(submission),
            'registration_state': registration_state,
            'track_token': token,
            'submission': submission,
        })

    @http.route(
        ['/application/rfqs/<int:rfq_id>/briefing/register/submit'],
        type='http',
        auth='public',
        website=True,
        csrf=True,
        methods=['POST'],
    )
    def briefing_register_submit(self, rfq_id, **post):
        rfq = request.env['ew.rfq'].sudo().browse(rfq_id).exists()
        Attendance = request.env['ew.rfq.briefing.attendance']
        token = (post.get('token') or '').strip()
        return_to = (post.get('return_to') or '').strip()
        submission = self._briefing_submission_from_token(rfq_id, token)
        if not submission and token:
            submission, token = self._briefing_submission_for_register(rfq_id, token)

        if submission:
            company_name = (post.get('company_name') or submission.company_name or '').strip()
            contact_email = (post.get('contact_email') or submission.contact_email or '').strip()
            contact_name = (post.get('contact_name') or submission.contact_name or '').strip()
            contact_phone = (post.get('contact_phone') or submission.contact_phone or '').strip()
        else:
            company_name = (post.get('company_name') or '').strip()
            contact_email = (post.get('contact_email') or '').strip()
            contact_name = (post.get('contact_name') or '').strip()
            contact_phone = (post.get('contact_phone') or '').strip()

        errors = {}
        if not company_name:
            errors['company_name'] = _("Company name is required.")
        if not contact_email:
            errors['contact_email'] = _("Email is required.")

        values = {
            'company_name': company_name,
            'contact_name': contact_name,
            'contact_phone': contact_phone,
            'contact_email': contact_email,
        }

        def _render_apply_with_register_errors():
            return self._render_rfq_apply_form(
                rfq,
                {},
                values,
                extra={
                    'briefing_register_errors': errors,
                    'briefing_register_values': values,
                    'track_token': token,
                },
                portal_token=token,
            )

        if not rfq:
            return request.render('ewseta_procurement.briefing_register_invalid_link', {'rfq': rfq})
        if not rfq.portal_applications_open():
            errors['form'] = _("This RFQ/RFP is closed. You cannot update your application.")

        if errors:
            if return_to == 'apply':
                return _render_apply_with_register_errors()
            if not submission:
                return request.render('ewseta_procurement.briefing_register_invalid_link', {'rfq': rfq})
            return request.render('ewseta_procurement.briefing_register_form', {
                'rfq': rfq,
                'errors': errors,
                'values': values,
                'track_token': token,
                'submission': submission,
            })

        try:
            attendance = Attendance.portal_register(rfq, values)
        except ValidationError as err:
            errors['form'] = str(err.args[0])
            if return_to == 'apply':
                return _render_apply_with_register_errors()
            return request.render('ewseta_procurement.briefing_register_form', {
                'rfq': rfq,
                'errors': errors,
                'values': values,
                'track_token': token,
                'submission': submission,
            })

        request.session['ew_proc_briefing_registered'] = {
            'rfq_id': rfq.id,
            'attendance_id': attendance.id,
        }
        if return_to == 'apply':
            return request.redirect(f'/application/rfqs/{rfq.id}/apply#briefing-register')
        proof_url = attendance._portal_proof_url()
        if proof_url:
            return request.redirect(proof_url)
        return request.redirect(f'/application/rfqs/{rfq.id}/briefing/thanks')

    @http.route(
        ['/application/briefing/attendance/<string:token>'],
        type='http',
        auth='public',
        website=True,
        sitemap=False,
        methods=['GET'],
    )
    def briefing_attendance_proof(self, token, **kw):
        attendance = request.env['ew.rfq.briefing.attendance'].find_by_proof_token(token)
        if not attendance:
            return request.render('ewseta_procurement.briefing_attendance_missing', {})
        rfq = attendance.rfq_id
        return request.render('ewseta_procurement.briefing_attendance_proof', {
            'attendance': attendance,
            'rfq': rfq,
            'proof_url': attendance._portal_proof_url(),
        })

    @http.route(
        ['/application/rfqs/<int:rfq_id>/briefing/thanks'],
        type='http',
        auth='public',
        website=True,
        sitemap=False,
        methods=['GET'],
    )
    def briefing_register_thanks(self, rfq_id, **kw):
        rfq = request.env['ew.rfq'].sudo().browse(rfq_id).exists()
        stash = request.session.get('ew_proc_briefing_registered') or {}
        attendance = request.env['ew.rfq.briefing.attendance'].browse()
        if stash.get('rfq_id') == rfq_id and stash.get('attendance_id'):
            attendance = request.env['ew.rfq.briefing.attendance'].sudo().browse(
                int(stash['attendance_id'])
            ).exists()
        return request.render('ewseta_procurement.briefing_register_thanks', {
            'rfq': rfq,
            'attendance': attendance,
        })

    @http.route(['/application/rfqs/<int:rfq_id>/apply/thanks'], type='http', auth='public', website=True, sitemap=False)
    def rfq_apply_thanks(self, rfq_id, **kw):
        """Legacy thank-you URL; prefer /application/submissions/thanks?token=."""
        token = kw.get('token')
        if token:
            return request.redirect(
                f'/application/submissions/thanks/{quote(token, safe="")}'
            )
        rfq = request.env['ew.rfq'].sudo().browse(rfq_id).exists()
        sub = None
        if kw.get('sub'):
            sub = request.env['ew.submission'].sudo().browse(int(kw['sub'])).exists()
        return request.render('ewseta_procurement.rfq_apply_thanks', {
            'rfq': rfq,
            'submission': sub,
            'track_token': None,
            'track_url': '',
        })

