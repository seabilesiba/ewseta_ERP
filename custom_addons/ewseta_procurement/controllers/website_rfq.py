import base64
import os

from werkzeug.utils import secure_filename

from odoo import http, fields, _
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

        # 🔹 Open RFQs: published and still before closing time
        open_rfqs = RFQ.search([
            ('state', '=', 'published'),
            ('closing_at', '>', now),
        ], order='closing_at asc, create_date desc')

        # 🔹 Closed RFQs: either explicitly closed OR published but past closing time
        closed_rfqs = RFQ.search([
            '|',
            ('state', '=', 'closed'),
            '&',
            ('state', '=', 'published'),
            ('closing_at', '<=', now),
        ], order='closing_at desc, create_date desc')

        return request.render('ewseta_procurement.rfq_public_list', {
            'open_rfqs': open_rfqs,
            'closed_rfqs': closed_rfqs,
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
        if not rfq:
            return request.render('ewseta_procurement.rfq_closed_or_missing', {'rfq': rfq})

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
        rfq = RFQ.browse(rfq_id).exists()
        now = fields.Datetime.now()
        if not rfq or rfq.state != 'published' or not rfq.closing_at or rfq.closing_at <= now:
            return request.render('ewseta_procurement.rfq_closed_or_missing', {'rfq': rfq})

        mand = rfq.requirement_ids.filtered(lambda r: r.is_mandatory)
        opti = rfq.requirement_ids.filtered(lambda r: not r.is_mandatory)

        return request.render('ewseta_procurement.rfq_apply_form', {
            'rfq': rfq,
            'req_mand': mand,
            'req_opt': opti,
            'errors': {},
            'values': {},
        })

    @http.route(['/application/rfqs/<int:rfq_id>/apply/submit'], type='http', auth='public',
                website=True, csrf=True, methods=['POST'])
    def rfq_apply_submit(self, rfq_id, **post):
        env = request.env
        RFQ = env['ew.rfq'].sudo()
        now = fields.Datetime.now()
        rfq = RFQ.browse(rfq_id).exists()

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

        errors = {}
        if not company_name:
            errors['company_name'] = _("Company name is required.")
        if not contact_email:
            errors['contact_email'] = _("Email is required.")

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
            mand = rfq.requirement_ids.filtered(lambda r: r.is_mandatory)
            opti = rfq.requirement_ids.filtered(lambda r: not r.is_mandatory)
            return request.render('ewseta_procurement.rfq_apply_form', {
                'rfq': rfq,
                'req_mand': mand,
                'req_opt': opti,
                'errors': errors,
                'values': {
                    'company_name': company_name,
                    'contact_name': contact_name,
                    'contact_phone': contact_phone,
                    'contact_email': contact_email,
                },
            })

        # -------------------------------
        #  CREATE OR REUSE PARTNER
        # -------------------------------
        Partner = env['res.partner'].sudo()
        partner = Partner.search([('email', '=ilike', contact_email)], limit=1)
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
            mand = rfq.requirement_ids.filtered(lambda r: r.is_mandatory)
            opti = rfq.requirement_ids.filtered(lambda r: not r.is_mandatory)
            return request.render('ewseta_procurement.rfq_apply_form', {
                'rfq': rfq,
                'req_mand': mand,
                'req_opt': opti,
                'errors': {'duplicate': _("You have already submitted an application for this RFQ.")},
                'values': {
                    'company_name': company_name,
                    'contact_name': contact_name,
                    'contact_phone': contact_phone,
                    'contact_email': contact_email,
                },
            })

        # -------------------------------
        #  CREATE SUBMISSION
        # -------------------------------
        submission = env['ew.submission'].sudo().create({
            'rfq_id': rfq.id,
            'partner_id': partner.id,
            'company_name': company_name or partner.name,
            'contact_name': contact_name,
            'contact_phone': contact_phone,
            'contact_email': contact_email,
            'state': 'submitted',
        })

        # Send email template (audit trail will show it)
        template = env.ref("ewseta_procurement.mail_tmpl_submission_sender", raise_if_not_found=False)
        if template:
            template.sudo().send_mail(submission.id, force_send=True)
            submission.sudo().message_post(
                body=_("RFQ submission email sent automatically."),
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

        # -------------------------------
        #  REDIRECT TO THANK YOU PAGE
        # -------------------------------
        return request.redirect(f"/application/rfqs/{rfq.id}/apply/thanks?sub={submission.id}")

    @http.route(['/application/rfqs/<int:rfq_id>/apply/thanks'], type='http', auth='public', website=True, sitemap=False)
    def rfq_apply_thanks(self, rfq_id, **kw):
        rfq = request.env['ew.rfq'].sudo().browse(rfq_id).exists()
        sub = None
        if kw.get('sub'):
            sub = request.env['ew.submission'].sudo().browse(int(kw['sub'])).exists()
        return request.render('ewseta_procurement.rfq_apply_thanks', {
            'rfq': rfq,
            'submission': sub,
        })

