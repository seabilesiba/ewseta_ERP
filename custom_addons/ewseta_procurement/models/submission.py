import hashlib
import secrets
from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError, AccessError
from odoo.tools.misc import format_datetime
from werkzeug.urls import url_quote


def _hash_submission_track_token(raw, pepper=''):
    return hashlib.sha256(f'{pepper}{raw}'.encode('utf-8')).hexdigest()


class EwSubmission(models.Model):
    _name = "ew.submission"
    _description = "Supplier Submission"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Sub Ref', required=True, readonly=True, default='New', tracking=True)
    rfq_id = fields.Many2one("ew.rfq", required=True, ondelete="cascade", tracking=True)
    partner_id = fields.Many2one("res.partner", string="Supplier", required=True,
                                 default=lambda self: self.env.user.partner_id.id, tracking=True)
    company_name = fields.Char(required=True)
    contact_name = fields.Char()
    contact_email = fields.Char(required=True)
    contact_phone = fields.Char(string="Contact Phone", required=True)
    submitted_at = fields.Datetime(readonly=True, copy=False)
    privacy_policy_accepted = fields.Boolean(
        string="RFQ privacy policy accepted",
        copy=False,
        default=False,
    )
    privacy_policy_accepted_at = fields.Datetime(
        string="Privacy policy accepted at",
        readonly=True,
        copy=False,
    )
    line_ids = fields.One2many("ew.submission.line", "submission_id", string="Documents", ondelete='cascade')
    closing_at = fields.Datetime("Closing Date & Time", related="rfq_id.closing_at", tracking=True, )
    rfq_state = fields.Selection([("draft","Draft"),("published", "Published"),("closed", "Closed")], related="rfq_id.state", default="draft", tracking=True, store=True)
    rfq_publication_type = fields.Selection(
        related="rfq_id.publication_type",
        string="RFQ publication",
        store=True,
        readonly=True,
    )
    rdq_rfp_ref = fields.Char("RFQ/RFP Ref",related="rfq_id.reference",  default='New', tracking=True,)

    # closing_at = fields.Datetime(default=lambda self: fields.Datetime.now())

    # Related helpers for Kanban
    # rfq_closing_at = fields.Datetime(related="rfq_id.closing_at", string="Closing")
    # rfq_submission_count = fields.Integer(related="rfq_id.submission_count", string="Submissions", store=False)
    #
    # def action_open_rfq_submissions(self):
    #     """From a submission, jump to all submissions for its RFQ."""
    #     self.ensure_one()
    #     return self.rfq_id.action_open_submissions()

    state = fields.Selection(
        [("draft", "Draft"), ("submitted", "Submitted"), ("closed", "Closed")],
        default="draft", tracking=True, required=True,
    )
    track_token = fields.Char(
        string="Portal track token",
        copy=False,
        index=True,
        help="Secret token embedded in the supplier proof / status URL. Issued once and not rotated.",
    )
    track_token_hash = fields.Char(copy=False, index=True)
    track_token_expires = fields.Datetime(
        copy=False,
        help="Optional expiry for portal links. Empty means the link does not expire.",
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
    )

    # ✅ Stored normalized email for DB constraint (case/space-insensitive)
    email_norm = fields.Char(
        string="Email (norm)",
        compute="_compute_email_norm",
        store=True,
        index=True,
    )

    @api.depends("contact_email")
    def _compute_email_norm(self):
        for r in self:
            r.email_norm = (r.contact_email or "").strip().lower()

    _uniq_rfq_partner = models.Constraint(
        "unique(rfq_id, partner_id)",
        "This supplier already has a submission for this RFQ.",
    )
    _uniq_rfq_email_norm = models.Constraint(
        "unique(rfq_id, email_norm)",
        "A submission with this email already exists for this RFQ.",
    )
    @api.model
    def _migrate_submission_name_rgq_to_rfq(self):
        """One-time fix: EW-RGQ-xxx → EW-RFQ-xxx (sequence prefix typo)."""
        subs = self.sudo().search([("name", "like", "EW-RGQ-%")])
        for sub in subs:
            sub.name = sub.name.replace("EW-RGQ-", "EW-RFQ-", 1)
        seq = self.env.ref(
            "ewseta_procurement.seq_ew_submission_rfq",
            raise_if_not_found=False,
        )
        if seq and (seq.prefix or "").strip() != "EW-RFQ-":
            seq.sudo().write({"prefix": "EW-RFQ-"})
        return True

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        user = self.env.user
        if user.has_group("ewseta_procurement.group_service_provider") and not user._is_public():
            partner = user.partner_id
            if partner:
                vals.setdefault("partner_id", partner.id)
                vals.setdefault(
                    "company_name",
                    partner.commercial_company_name or partner.name or "",
                )
                vals.setdefault("contact_email", partner.email or user.email or "")
                vals.setdefault(
                    "contact_phone",
                    partner.phone or getattr(partner, "mobile", None) or "",
                )
                if not vals.get("contact_name"):
                    vals["contact_name"] = (
                        user.name if partner.is_company else partner.name
                    )
        return vals

    @api.model
    def _provider_application_context_defaults(self, rfq, partner):
        partner = partner or self.env.user.partner_id
        return {
            "default_rfq_id": rfq.id,
            "default_partner_id": partner.id,
            "default_company_name": partner.commercial_company_name or partner.name,
            "default_contact_name": self.env.user.name,
            "default_contact_email": partner.email or self.env.user.email,
            "default_contact_phone": partner.phone or getattr(partner, "mobile", None) or "",
        }

    @api.model
    def action_open_provider_application_from_rfq(self):
        """Open draft application or create one (service provider backend, transversal/public)."""
        rfq_id = self.env.context.get("active_id") or self.env.context.get("active_ids", [None])[0]
        rfq = self.env["ew.rfq"].browse(rfq_id).exists()
        if not rfq:
            raise UserError(_("RFQ/RFP not found."))
        partner = self.env.user.partner_id
        if not partner:
            raise UserError(
                _("Your user has no linked contact. Ask an administrator to link your account.")
            )
        rfq._assert_provider_may_apply(partner=partner, user=self.env.user)
        existing = self.search(
            [
                ("rfq_id", "=", rfq.id),
                ("partner_id", "=", partner.id),
            ],
            limit=1,
        )
        action = {
            "type": "ir.actions.act_window",
            "name": _("Application"),
            "res_model": "ew.submission",
            "view_mode": "form",
            "target": "current",
            "context": dict(
                self.env.context,
                **self._provider_application_context_defaults(rfq, partner),
            ),
        }
        if existing:
            existing._ensure_document_lines()
            action["res_id"] = existing.id
            return action
        action["context"]["form_view_initial_mode"] = "edit"
        return action

    def _validate_mandatory_documents(self):
        self.ensure_one()
        missing = []
        by_req = {line.requirement_id.id: line for line in self.line_ids}
        for req in self.rfq_id.requirement_ids:
            if not req.is_mandatory:
                continue
            line = by_req.get(req.id)
            if not line or not line.file:
                missing.append(req.name or _("(Unnamed requirement)"))
        if missing:
            raise ValidationError(
                _("Missing files for mandatory documents:\n- %s") % "\n- ".join(missing)
            )

    def _validate_contact_for_submit(self):
        self.ensure_one()
        if not (self.company_name or "").strip():
            raise UserError(_("Company name is required."))
        if not (self.contact_email or "").strip():
            raise UserError(_("Email is required."))
        if not (self.contact_phone or "").strip():
            raise UserError(_("Contact phone is required."))

    # ---------- HARDENED SEEDING ----------
    def _rfq_requirements_ordered(self, rfq):
        rfq = rfq.sudo()
        if not rfq.requirement_ids:
            if hasattr(rfq, "_prefill_requirements"):
                rfq._prefill_requirements()
            elif hasattr(rfq, "_default_requirements_commands"):
                rfq.write({"requirement_ids": rfq._default_requirements_commands()})
        return rfq.requirement_ids.sorted(key=lambda r: (r.section, r.sequence, r.id))

    def _document_lines_match_rfq(self, lines, reqs):
        if len(lines) != len(reqs):
            return False
        if not reqs:
            return True
        actual = lines.mapped("requirement_id").ids
        expected = reqs.ids
        return len(set(actual)) == len(reqs) and set(actual) == set(expected)

    def _ensure_document_lines(self):
        """One line per RFQ requirement, each linked to the correct requirement."""
        Line = self.env["ew.submission.line"].sudo()
        for sub in self:
            if not sub.rfq_id:
                continue
            reqs = self._rfq_requirements_ordered(sub.rfq_id)
            if not reqs:
                continue
            lines = sub.line_ids.sorted("id")
            if self._document_lines_match_rfq(lines, reqs):
                for line, req in zip(lines, reqs):
                    if line.requirement_name != req.name:
                        line.requirement_name = req.name
                continue

            if len(lines) == len(reqs):
                for line, req in zip(lines, reqs):
                    line.write({
                        "requirement_id": req.id,
                        "requirement_name": req.name,
                    })
                continue

            if sub.state != "draft":
                continue

            preserved = [
                (line.file, line.file_filename)
                for line in lines
            ]
            lines.unlink()
            for idx, req in enumerate(reqs):
                vals = {
                    "submission_id": sub.id,
                    "requirement_id": req.id,
                    "requirement_name": req.name,
                }
                if idx < len(preserved) and preserved[idx][0]:
                    vals["file"] = preserved[idx][0]
                    vals["file_filename"] = preserved[idx][1]
                Line.with_context(ew_allow_submission_line_create=True).create(vals)

    def _seed_lines_from_rfq(self):
        self._ensure_document_lines()

    @api.model_create_multi
    def create(self, vals_list):
        now = fields.Datetime.now()
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("ew.submission") or "New"
                )

            if not vals.get("partner_id"):
                partner = self.env.user.partner_id
                if not partner:
                    raise UserError(
                        _("Your user has no linked Contact/Partner; ask admin to set one.")
                    )
                vals["partner_id"] = partner.id

            rfq_id = vals.get("rfq_id")
            partner_id = vals.get("partner_id")
            email_norm = (vals.get("contact_email") or "").strip().lower()

            if rfq_id and partner_id:
                if self.search_count([
                    ("rfq_id", "=", rfq_id),
                    ("partner_id", "=", partner_id),
                ]):
                    raise ValidationError(
                        _("You have already submitted an application for this RFQ.")
                    )

            if rfq_id and email_norm:
                if self.search_count([
                    ("rfq_id", "=", rfq_id),
                    ("email_norm", "=", email_norm),
                ]):
                    raise ValidationError(
                        _("A submission with this email already exists for this RFQ.")
                    )

            rfq = rfq_id and self.env["ew.rfq"].browse(rfq_id).sudo()
            if rfq:
                partner = self.env["res.partner"].browse(partner_id).exists()
                rfq._assert_provider_may_apply(partner=partner, user=self.env.user)
            if rfq and rfq.closing_at and rfq.closing_at <= now:
                vals["state"] = "closed"

        records = super().create(vals_list)

        for rec in records:
            rec._seed_lines_from_rfq()
            rfq = rec.rfq_id.sudo()
            if rfq and rfq.closing_at and rfq.closing_at <= now:
                if hasattr(rfq, "_auto_close_if_due"):
                    rfq._auto_close_if_due()
                else:
                    rfq.write({"unlocked": True, "state": "closed"})
            rec._briefing_send_start_email_if_due()

        return records

    def _briefing_send_start_email_if_due(self):
        """If briefing is live, ensure this applicant gets the start notification."""
        for rec in self:
            if rec.state not in ("submitted", "closed"):
                continue
            rfq = rec.rfq_id.sudo()
            if not rfq or not rfq.briefing_session:
                continue
            if rfq.briefing_start_mail_sent:
                rfq._send_briefing_start_to_submission(rec)
            else:
                rfq._send_briefing_start_emails()

    # Keep your existing onchange for UI niceness (not relied upon)
    @api.onchange("rfq_id")
    def _onchange_rfq_id_seed_lines(self):
        """UI hint only — persisted lines come from create()/write() + _ensure_document_lines."""
        if not self.rfq_id or self._origin.id:
            return
        if self.line_ids:
            return
        for req in self._rfq_requirements_ordered(self.rfq_id):
            self.line_ids += self.env["ew.submission.line"].new({
                "requirement_id": req.id,
                "requirement_name": req.name,
            })

    def _ew_filter_sp_line_commands(self, commands):
        """Service providers may update files on existing lines, not add/remove rows."""
        if not commands:
            return commands
        kept = []
        for cmd in commands:
            if not isinstance(cmd, (list, tuple)):
                kept.append(cmd)
                continue
            if cmd[0] == 1:
                kept.append(cmd)
            elif cmd[0] == 4:
                kept.append(cmd)
        return kept

    def write(self, vals):
        if (
            not self.env.su
            and self.env.user.has_group("ewseta_procurement.group_service_provider")
            and "line_ids" in vals
            and not self.env.context.get("ew_skip_line_ids_write")
        ):
            vals = dict(vals)
            vals["line_ids"] = self._ew_filter_sp_line_commands(vals["line_ids"])
        res = super().write(vals)
        drafts = self.filtered(lambda s: s.state == "draft")
        if vals.get("rfq_id") or (
            "line_ids" in vals
            and self.env.user.has_group("ewseta_procurement.group_service_provider")
        ):
            drafts.with_context(ew_allow_submission_line_create=True).sudo()._ensure_document_lines()
        return res

    @api.model
    def _fix_document_line_requirements(self):
        """Upgrade hook: realign draft submission lines with RFQ requirements."""
        subs = self.search([("rfq_id", "!=", False)])
        subs._ensure_document_lines()

    @api.model
    def _tracking_pepper(self):
        return self.env['ir.config_parameter'].sudo().get_param(
            'ewseta_procurement.submission_track_pepper',
            'ewseta_submission_track',
        )

    @api.model
    def _tracking_token_days(self):
        """Days until link expiry; 0 or negative = never expires."""
        try:
            return int(self.env['ir.config_parameter'].sudo().get_param(
                'ewseta_procurement.submission_track_days', '0',
            ))
        except (TypeError, ValueError):
            return 0

    @api.model
    def _track_token_validity_domain(self):
        """Domain clause: token not expired (empty expiry = permanent)."""
        now = fields.Datetime.now()
        return ['|', ('track_token_expires', '=', False), ('track_token_expires', '>=', now)]

    def _issue_tracking_token(self, force_new=False):
        """Return the supplier proof URL token. By default issued once and kept forever."""
        self.ensure_one()
        if self.track_token and not force_new:
            return self.track_token

        token = secrets.token_urlsafe(32)
        days = self._tracking_token_days()
        expires = (
            False
            if days <= 0
            else fields.Datetime.now() + timedelta(days=days)
        )
        pepper = self._tracking_pepper()
        self.sudo().write({
            'track_token': token,
            'track_token_hash': _hash_submission_track_token(token, pepper),
            'track_token_expires': expires,
        })
        return token

    def _portal_token_matches_submission(self, submission, token):
        token = (token or '').strip()
        if not token or not submission:
            return False
        if submission.track_token == token:
            return True
        pepper = self._tracking_pepper()
        return submission.track_token_hash == _hash_submission_track_token(token, pepper)

    @api.model
    def find_by_tracking_token(self, token):
        if not token:
            return self.browse()
        token = token.strip()
        validity = self._track_token_validity_domain()
        found = self.sudo().search(
            [('track_token', '=', token)] + validity,
            limit=1,
        )
        if found:
            return found
        pepper = self._tracking_pepper()
        token_hash = _hash_submission_track_token(token, pepper)
        return self.sudo().search(
            [('track_token_hash', '=', token_hash)] + validity,
            limit=1,
        )

    @api.model
    def portal_resolve_submission(self, token, trusted_submission_id=None):
        """Resolve submission for public thanks/track pages (token + optional session id)."""
        token = (token or '').strip()
        if token:
            found = self.find_by_tracking_token(token)
            if found:
                return found
        if trusted_submission_id and token:
            sub = self.sudo().browse(int(trusted_submission_id)).exists()
            if sub and sub.state in ('submitted', 'closed'):
                if self._portal_token_matches_submission(sub, token):
                    return sub
        return self.browse()

    def action_resend_portal_track_link(self):
        """Re-email the same private status link (does not invalidate existing URLs)."""
        for rec in self:
            track_token = rec._issue_tracking_token()
            rec._send_portal_application_received(track_token)
        return True

    def action_regenerate_portal_track_link(self):
        """Issue a new link (invalidates previous URLs). SCM/Admin only."""
        if not (
            self.env.user.has_group('ewseta_procurement.group_scm_owner')
            or self.env.user.has_group('ewseta_procurement.group_rfq_admin')
        ):
            raise AccessError(_("Only SCM or RFQ administrators can regenerate portal links."))
        for rec in self:
            track_token = rec._issue_tracking_token(force_new=True)
            rec._send_portal_application_received(track_token)
        return True

    def portal_may_update(self, now=None):
        """Applicants may change contact details and documents while the RFQ/RFP is open."""
        self.ensure_one()
        if self.state not in ("draft", "submitted"):
            return False
        return bool(self.rfq_id.sudo().portal_applications_open(now=now))

    def portal_update_application(self, values, files=None):
        """Update a public/transversal application from the tracking page."""
        self.ensure_one()
        if not self.portal_may_update():
            raise UserError(
                _("This RFQ/RFP is closed. You cannot update your application.")
            )
        company_name = (values.get("company_name") or "").strip()
        contact_email = (values.get("contact_email") or "").strip()
        contact_phone = (values.get("contact_phone") or "").strip()
        contact_name = (values.get("contact_name") or "").strip()
        if not company_name:
            raise UserError(_("Company name is required."))
        if not contact_email:
            raise UserError(_("Email is required."))
        if not contact_phone:
            raise UserError(_("Contact phone is required."))
        self.sudo().write({
            "company_name": company_name,
            "contact_name": contact_name,
            "contact_email": contact_email,
            "contact_phone": contact_phone,
        })
        files = files or {}
        existing_lines = {line.requirement_id.id: line for line in self.sudo().line_ids}
        Line = self.env["ew.submission.line"].sudo()
        for req in self.rfq_id.sudo().requirement_ids:
            payload = files.get(req.id)
            if not payload:
                continue
            content, filename = payload
            line = existing_lines.get(req.id)
            if not line:
                line = Line.create({
                    "submission_id": self.id,
                    "requirement_id": req.id,
                })
                existing_lines[req.id] = line
            line.write({
                "file": content,
                "file_filename": filename,
            })
        self.sudo().message_post(
            body=_("Application updated via the website."),
            subtype_xmlid="mail.mt_note",
        )
        return True

    def _portal_track_url(self, track_token):
        self.ensure_one()
        base = (self.env['ir.config_parameter'].sudo().get_param('web.base.url') or '').rstrip('/')
        if not base or not track_token:
            return ''
        return f'{base}/application/submissions/track/{track_token}'

    def portal_track_reference_rows(self):
        """Label/value rows for the public track page (supplier + application)."""
        self.ensure_one()
        rfq = self.rfq_id
        supplier = [
            {'label': _('Company / trading name'), 'value': self.company_name or '—'},
            {'label': _('Contact person'), 'value': self.contact_name or '—'},
            {'label': _('Contact email'), 'value': self.contact_email or '—', 'kind': 'email'},
            {'label': _('Contact phone'), 'value': self.contact_phone or '—'},
        ]
        if self.partner_id:
            supplier.append({
                'label': _('Supplier partner (Odoo)'),
                'value': self.partner_id.display_name,
            })
        application = [
            {'label': _('Submission reference'), 'value': self.name or '—', 'kind': 'code'},
            {'label': _('Submission status'), 'value': dict(self._fields['state'].selection).get(self.state, self.state)},
            {'label': _('Submitted on'), 'value': self.submitted_at and format_datetime(self.env, self.submitted_at) or '—'},
            {'label': _('RFQ / RFP title'), 'value': rfq.name or '—'},
            {'label': _('RFQ / RFP reference'), 'value': rfq.reference or '—'},
            {'label': _('Type'), 'value': (rfq.type or 'rfq').upper()},
            {'label': _('RFQ closing date'), 'value': self.closing_at and format_datetime(self.env, self.closing_at) or '—'},
            {'label': _('RFQ status'), 'value': dict(rfq._fields['state'].selection).get(rfq.state, rfq.state)},
        ]
        return {'supplier': supplier, 'application': application}

    def _send_portal_application_received(self, track_token):
        """Email the supplier their reference and private status link."""
        self.ensure_one()
        if not (self.contact_email or '').strip():
            return False
        template = self.env.ref(
            'ewseta_procurement.mail_tmpl_submission_portal_received',
            raise_if_not_found=False,
        )
        if not template:
            return False
        track_url = self._portal_track_url(track_token)
        contact = self.contact_email.strip()
        # use_default_to must be off on the template; also clear thread default
        # partners so Odoo does not SMTP-send once per partner and once for email_to.
        return template.with_context(
            track_url=track_url,
        ).send_mail(
            self.id,
            force_send=True,
            email_values={
                'email_to': contact,
                'partner_ids': [],
                'recipient_ids': [(5, 0, 0)],
            },
        )

    def action_submit(self):
        """Draft → submitted with the same checks as the public portal (documents + contact)."""
        now = fields.Datetime.now()
        for rec in self:
            if rec.state != "draft":
                continue
            rec.rfq_id._assert_provider_may_apply(
                partner=rec.partner_id,
                user=self.env.user,
            )
            if rec.rfq_id.closing_at and rec.rfq_id.closing_at <= now:
                raise UserError(_("This RFQ/RFP is past the closing date."))
            rec._validate_contact_for_submit()
            if not rec.privacy_policy_accepted:
                raise UserError(
                    _("You must accept the RFQ privacy policy before submitting.")
                )
            rec.with_context(ew_allow_submission_line_create=True).sudo()._ensure_document_lines()
            if not self.env.user.has_group(
                "ewseta_procurement.group_service_provider"
            ):
                rec._validate_mandatory_documents()
            rec.write({
                "state": "submitted",
                "submitted_at": now,
            })
            rec.message_post(
                body=_("Application submitted via the service provider portal."),
                subtype_xmlid="mail.mt_note",
            )
            track_token = rec._issue_tracking_token()
            rec._send_portal_application_received(track_token)
            rec._briefing_send_start_email_if_due()
            if rec.rfq_id.closing_at and rec.rfq_id.closing_at <= now:
                rec.state = "closed"
                rec.rfq_id._auto_close_if_due()

    def send_mail(self):
        template = self.env.ref("ewseta_procurement.mail_tmpl_submission_receipt")
        for rec in self:
            template.send_mail(rec.id)



    @api.model
    def _sync_scm_submission_access(self):
        """Ensure past-deadline RFQs are closed/unlocked so SCM record rules allow access."""
        user = self.env.user
        if user._is_public():
            return
        if not user.has_group("ewseta_procurement.group_scm_owner"):
            return
        if user.has_group("ewseta_procurement.group_rfq_admin"):
            return
        self.env["ew.rfq"]._sync_due_closures()

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, *, active_test=True, bypass_access=False):
        self._sync_scm_submission_access()
        return super()._search(
            domain,
            offset=offset,
            limit=limit,
            order=order,
            active_test=active_test,
            bypass_access=bypass_access,
        )

    @api.model
    def cron_close_submissions_past_deadline(self):
        """Safety cron: close submissions when RFQ deadline has passed."""
        now = fields.Datetime.now()
        subs = self.search([("state", "!=", "closed"), ("rfq_id.closing_at", "<=", now)])
        subs.write({"state": "closed"})
        self.env["ew.rfq"]._sync_due_closures()


    @api.constrains("rfq_id", "partner_id")
    def _check_unique_supplier_per_rfq(self):
        for rec in self:
            if not rec.rfq_id or not rec.partner_id:
                continue
            dup = self.search([
                ("id", "!=", rec.id),
                ("rfq_id", "=", rec.rfq_id.id),
                ("partner_id", "=", rec.partner_id.id),
            ], limit=1)
            if dup:
                raise ValidationError(_("This supplier already has a submission for this RFQ."))



    # # show the RFQ closing on the card
    # rfq_closing_at = fields.Datetime(
    #     related="rfq_id.closing_at",
    #     store=True, index=True, readonly=True,
    # )
    #
    # # how many submissions for this RFQ (for the tile badge)
    # rfq_submission_count = fields.Integer(
    #     compute="_compute_rfq_submission_count",
    #     store=False,
    # )

    # pick ONE representative record per RFQ to display as the "tile"
    is_rfq_representative = fields.Boolean(
        compute="_compute_is_rfq_representative",
        store=True, index=True, readonly=True,
        help="True on exactly one submission per RFQ; used to show one tile per RFQ.",
    )



    # show the RFQ’s count on each submission (read-only, no compute here)
    rfq_submission_count = fields.Integer(
        string="Submissions for RFQ",
        related="rfq_id.submission_count",
        store=False,
        readonly=True,
    )

    # if you need closing shown in kanban, keep this:
    rfq_closing_at = fields.Datetime(related="rfq_id.closing_at", store=True)

    @api.depends('rfq_id')
    def _compute_rfq_submission_count(self):
        # group by RFQ and count submissions
        rfq_ids = [r.rfq_id.id for r in self if r.rfq_id]
        counts = {}
        if rfq_ids:
            data = self.env['ew.submission'].sudo().read_group(
                [('rfq_id', 'in', rfq_ids)],
                ['rfq_id', 'id:count'],  # <-- creates key 'id_count'
                ['rfq_id']
            )
            # Be defensive: some Odoo versions also expose '__count'
            for d in data:
                if not d.get('rfq_id'):
                    continue
                rfq = d['rfq_id'][0]
                cnt = d.get('id_count', d.get('__count', 0))
                counts[rfq] = cnt or 0

        for rec in self:
            rec.rfq_submission_count = counts.get(rec.rfq_id.id, 0)

    @api.depends('rfq_id', 'create_date')
    def _compute_is_rfq_representative(self):
        """
        Mark exactly ONE submission per RFQ as representative.
        We choose the earliest-created submission as the representative.
        """
        # default all False
        for rec in self:
            rec.is_rfq_representative = False

        # group by rfq and pick earliest create_date
        by_rfq = {}
        for rec in self.sorted(key=lambda r: (r.rfq_id.id or 0, r.create_date or fields.Datetime.now())):
            rid = rec.rfq_id.id
            if rid and rid not in by_rfq:
                by_rfq[rid] = rec

        for rep in by_rfq.values():
            rep.is_rfq_representative = True

    def action_open_rfq_submissions(self):
        """Open all submissions of this card's RFQ."""
        self.ensure_one()
        return {
            'name': _("Submissions"),
            'type': 'ir.actions.act_window',
            'res_model': 'ew.submission',
            'view_mode': 'list,kanban,form',
            'domain': [('rfq_id', '=', self.rfq_id.id)],
            'context': {'default_rfq_id': self.rfq_id.id},
            'target': 'current',
        }


class EwSubmissionLineDownloadLog(models.Model):
    _name = "ew.submission.line.download.log"
    _description = "Submission Line Download Log"
    _order = "create_date desc, id desc"

    line_id = fields.Many2one("ew.submission.line", required=True, ondelete="cascade")
    user_id = fields.Many2one("res.users", string="Downloaded By")
    ip_address = fields.Char("IP Address")
    downloaded_at = fields.Datetime("Downloaded At", default=lambda self: fields.Datetime.now(), readonly=True)



class EwSubmissionLine(models.Model):
    _name = "ew.submission.line"
    _description = "Supplier Submission Document Line"

    submission_id = fields.Many2one("ew.submission", required=True, ondelete="cascade")
    requirement_id = fields.Many2one("ew.rfq.requirement", string="Requirement", required=True)
    requirement_name = fields.Char(
        string="Requirement label",
        readonly=True,
        help="Copy of the RFQ document name at line creation (stable in the UI).",
    )
    is_mandatory = fields.Boolean(
        string="Mandatory",
        related="requirement_id.is_mandatory",
        store=False,
        readonly=True,
        tracking=True

    )
    file = fields.Binary("File", attachment=True)
    file_filename = fields.Char("Filename")
    attachment_id = fields.Many2one("ir.attachment", string="Stored Attachment", readonly=True)

    name = fields.Char("Label", compute="_compute_name", store=False, tracking=True)

    # NEW: verification fields
    verification_state = fields.Selection(
        [
            ("pending", "Pending"),
            ("accepted", "Accepted"),
            ("rejected", "Rejected"),
        ],
        default="pending",
        string="Verification",
        tracking=False,
    )
    verification_comment = fields.Text("Verification Comment")
    verified_by = fields.Many2one("res.users", string="Verified By", readonly=True)
    verified_on = fields.Datetime("Verified On", readonly=True)



    @api.depends("requirement_id", "requirement_name")
    def _compute_name(self):
        for rec in self:
            rec.name = rec.requirement_name or rec.requirement_id.name or ""

    # @api.model
    # def create(self, vals):
    #     rec = super().create(vals)
    #     rec._sync_attachment()
    #     return rec
    #
    # def write(self, vals):
    #     res = super().write(vals)
    #     if "file" in vals or "file_filename" in vals:
    #         for rec in self:
    #             rec._sync_attachment()
    #     return res

    def write(self, vals):
        # Protect verification fields from non-SCM/Admin users
        protected = {"verification_state", "verification_comment"}
        if protected & set(vals.keys()):
            user = self.env.user
            if not (user.has_group("ewseta_procurement.group_scm_owner") or
                    user.has_group("ewseta_procurement.group_rfq_admin")):
                raise UserError("You are not allowed to verify documents.")

        # If state changes to accepted/rejected, stamp who/when
        if "verification_state" in vals:
            new_state = vals.get("verification_state")
            if new_state in ("accepted", "rejected"):
                vals.setdefault("verified_by", self.env.user.id)
                vals.setdefault("verified_on", fields.Datetime.now())
            elif new_state == "pending":
                vals.setdefault("verified_by", False)
                vals.setdefault("verified_on", False)

            # If rejecting, require a comment
            if new_state == "rejected":
                incoming_comment = vals.get("verification_comment")
                # If not in vals, check existing value (single-record validation below)
                if incoming_comment is None:
                    for rec in self:
                        if not rec.verification_comment:
                            raise UserError("Please provide a verification comment when rejecting.")
                elif not (incoming_comment or "").strip():
                    raise UserError("Please provide a verification comment when rejecting.")

        if "requirement_id" in vals and "requirement_name" not in vals:
            req = self.env["ew.rfq.requirement"].sudo().browse(vals["requirement_id"])
            vals["requirement_name"] = req.name or ""

        res = super().write(vals)
        # If file changed, resync attachment
        if {"file", "file_filename"} & set(vals.keys()):
            for rec in self:
                if rec.file:
                    rec._sync_attachment()
        return res

    def action_verify_accept(self):
        self.write({"verification_state": "accepted"})

    def action_verify_reject(self):
        # Ensure at least one has comment; write() will enforce per-record
        self.write({"verification_state": "rejected"})
    def _sync_attachment(self):
        for rec in self.filtered(lambda r: r.file and r.submission_id):
            att_vals = {
                "name": rec.file_filename or rec.requirement_id.name or _("Document"),
                "datas": rec.file,
                "res_model": "ew.submission",
                "res_id": rec.submission_id.id,
                "type": "binary",
            }
            if rec.attachment_id:
                rec.attachment_id.write(att_vals)
            else:
                rec.attachment_id = self.env["ir.attachment"].create(att_vals).id

    def _stamp_requirement_name(self, vals):
        req_id = vals.get("requirement_id")
        if req_id and not vals.get("requirement_name"):
            req = self.env["ew.rfq.requirement"].sudo().browse(req_id)
            vals["requirement_name"] = req.name or ""

    @api.model
    def _ew_filter_submission_line_vals(self, vals_list):
        """Keep one create per requirement; ignore duplicate/extra rows from form save."""
        kept = []
        pending_req_by_sub = {}
        for vals in vals_list:
            sub_id = vals.get("submission_id")
            if not sub_id:
                kept.append(vals)
                continue
            sub = self.env["ew.submission"].browse(sub_id).sudo()
            if not sub.exists():
                continue
            req_id = vals.get("requirement_id")
            if not req_id and sub.rfq_id:
                used = (
                    set(sub.line_ids.mapped("requirement_id").ids)
                    | pending_req_by_sub.get(sub_id, set())
                )
                missing = sub.rfq_id.requirement_ids.filtered(
                    lambda r: r.id not in used
                )[:1]
                if not missing:
                    continue
                req_id = missing.id
                vals = dict(vals, requirement_id=req_id)
                pending_req_by_sub.setdefault(sub_id, set()).add(req_id)
            if not req_id:
                continue
            seen = pending_req_by_sub.setdefault(sub_id, set())
            seen |= set(sub.line_ids.mapped("requirement_id").ids)
            if req_id in seen:
                continue
            seen.add(req_id)
            kept.append(vals)
        return kept

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = self._ew_filter_submission_line_vals(vals_list)
        for vals in vals_list:
            self._stamp_requirement_name(vals)
        if not vals_list:
            return self.browse()

        records = super(
            EwSubmissionLine,
            self.sudo().with_context(ew_allow_submission_line_create=True),
        ).create(vals_list)
        for rec in records:
            rec._sync_attachment()
        return records


    def portal_file_is_pdf(self):
        self.ensure_one()
        return (self.file_filename or '').lower().endswith('.pdf')

    def action_preview_file(self):
        self.ensure_one()
        if not self.file:
            raise UserError(_("No file uploaded yet."))
        wizard = self.env["ew.submission.line.preview"].create({"line_id": self.id})
        title = self.file_filename or self.requirement_name or _("Document preview")
        return {
            "type": "ir.actions.act_window",
            "name": title,
            "res_model": "ew.submission.line.preview",
            "res_id": wizard.id,
            "view_mode": "form",
            "views": [(False, "form")],
            "target": "new",
            "context": {"dialog_size": "extra-large"},
        }

# # models/submission.py (only the line model & seeding/validation parts shown)
# # models/submission.py
# from odoo import api, fields, models, _
# from odoo.exceptions import ValidationError
#
# class EwSubmission(models.Model):
#     _name = "ew.submission"
#     _description = "Supplier Submission"
#     _inherit = ["mail.thread"]
#     # ... fields ...
#     rfq_id = fields.Many2one("ew.rfq", required=True, ondelete="cascade", tracking=True)
#
#     partner_id = fields.Many2one("res.partner", string="Supplier", required=True, tracking=True)
#     company_name = fields.Char(required=True)
#     contact_name = fields.Char()
#     contact_email = fields.Char(required=True)
#     submitted_at = fields.Datetime(default=lambda self: fields.Datetime.now(), readonly=True)
#     line_ids = fields.One2many("ew.submission.line", "submission_id", string="Documents")
#     state = fields.Selection([("submitted", "Submitted")], default="submitted")
#     rfq_unlocked = fields.Boolean(related="rfq_id.unlocked", store=False)
#
#     @api.model
#     def create(self, vals):
#         submission = super().create(vals)
#         if not submission.line_ids and submission.rfq_id and submission.rfq_id.requirement_ids:
#             lines = [(0, 0, {"requirement_id": req.id}) for req in submission.rfq_id.requirement_ids]
#             submission.write({"line_ids": lines})
#         return submission
#
#     @api.constrains("line_ids", "line_ids.file")
#     def _check_required_documents_uploaded(self):
#         for sub in self:
#             by_req = {l.requirement_id.id: l for l in sub.line_ids}
#             missing = []
#             for req in sub.rfq_id.requirement_ids:
#                 if req.is_mandatory:
#                     line = by_req.get(req.id)
#                     if not line or not line.file:
#                         missing.append(req.name or _("(Unnamed requirement)"))
#             if missing:
#                 raise ValidationError(_("Missing files for mandatory documents:\n- %s") % "\n- ".join(missing))
#
# class EwSubmissionLine(models.Model):
#     _name = "ew.submission.line"
#     _description = "Supplier Submission Document Line"
#
#     submission_id = fields.Many2one("ew.submission", required=True, ondelete="cascade")
#     requirement_id = fields.Many2one("ew.rfq.requirement", string="Requirement", required=True)
#     file = fields.Binary("File", attachment=True)
#     file_filename = fields.Char("Filename")
#     attachment_id = fields.Many2one("ir.attachment", string="Stored Attachment", readonly=True)
#
#     name = fields.Char("Label", compute="_compute_name", store=False)
#
#     @api.depends("requirement_id")
#     def _compute_name(self):
#         for rec in self:
#             rec.name = rec.requirement_id.name or ""
#
#     @api.model
#     def create(self, vals):
#         rec = super().create(vals)
#         rec._sync_attachment()
#         return rec
#
#     def write(self, vals):
#         res = super().write(vals)
#         if "file" in vals or "file_filename" in vals:
#             for rec in self:
#                 rec._sync_attachment()
#         return res
#
#     def _sync_attachment(self):
#         for rec in self.filtered(lambda r: r.file and r.submission_id):
#             att_vals = {
#                 "name": rec.file_filename or rec.requirement_id.name or _("Document"),
#                 "datas": rec.file,
#                 "res_model": "ew.submission",
#                 "res_id": rec.submission_id.id,
#                 "type": "binary",
#             }
#             if rec.attachment_id:
#                 rec.attachment_id.write(att_vals)
#             else:
#                 rec.attachment_id = self.env["ir.attachment"].create(att_vals).id
#
#
# # # models/submission.py
# # from odoo import api, fields, models, _
# # from odoo.exceptions import ValidationError
# #
# # class EwSubmission(models.Model):
# #     _name = "ew.submission"
# #     _description = "Supplier Submission"
# #     _inherit = ["mail.thread"]
# #
# #     rfq_id = fields.Many2one("ew.rfq", required=True, ondelete="cascade", tracking=True)
# #     partner_id = fields.Many2one("res.partner", string="Supplier", required=True, tracking=True)
# #     company_name = fields.Char(required=True)
# #     contact_name = fields.Char()
# #     contact_email = fields.Char(required=True)
# #     submitted_at = fields.Datetime(default=lambda self: fields.Datetime.now(), readonly=True)
# #     line_ids = fields.One2many("ew.submission.line", "submission_id", string="Documents")
# #     state = fields.Selection([("submitted", "Submitted")], default="submitted")
# #     rfq_unlocked = fields.Boolean(related="rfq_id.unlocked", store=False)
# #
# #     @api.constrains("rfq_id")
# #     def _check_not_after_close(self):
# #         for rec in self:
# #             if fields.Datetime.now() > rec.rfq_id.closing_at:
# #                 raise ValidationError(_("Submissions are closed for this RFQ."))
# #
# # class EwSubmissionLine(models.Model):
# #     _name = "ew.submission.line"
# #     _description = "Supplier Submission Document Line"
# #
# #     submission_id = fields.Many2one("ew.submission", required=True, ondelete="cascade")
# #     requirement_id = fields.Many2one("ew.rfq.requirement", string="Requirement")
# #     name = fields.Char("Label", required=True)
# #
# #     # NEW: actual upload control (stored as attachment in filestore)
# #     file = fields.Binary("File", attachment=True)
# #     file_filename = fields.Char("Filename")
# #
# #     # Keep linkage to created attachment for traceability
# #     attachment_id = fields.Many2one("ir.attachment", string="Stored Attachment", readonly=True)
# #
# #     @api.model
# #     def create(self, vals):
# #         rec = super().create(vals)
# #         rec._ensure_attachment()
# #         return rec
# #
# #     def write(self, vals):
# #         res = super().write(vals)
# #         # If file changed on any line, (re)create attachment
# #         changed = any(k in vals for k in ("file", "file_filename"))
# #         if changed:
# #             for rec in self:
# #                 rec._ensure_attachment()
# #         return res
# #
# #     def _ensure_attachment(self):
# #         """Create/update ir.attachment from file/file_filename when present."""
# #         for rec in self.filtered(lambda r: r.file and r.submission_id):
# #             name = rec.file_filename or rec.name or _("Document")
# #             att_vals = {
# #                 "name": name,
# #                 "datas": rec.file,  # already base64 from the Binary field
# #                 "res_model": "ew.submission",
# #                 "res_id": rec.submission_id.id,
# #                 "type": "binary",
# #             }
# #             if rec.attachment_id:
# #                 rec.attachment_id.write(att_vals)
# #             else:
# #                 rec.attachment_id = self.env["ir.attachment"].create(att_vals).id
#
#
# # from odoo import api, fields, models, _
# # from odoo.exceptions import ValidationError
# #
# # class EwSubmission(models.Model):
# #     _name = "ew.submission"
# #     _description = "Supplier Submission"
# #     _inherit = ["mail.thread"]
# #
# #     rfq_id = fields.Many2one("ew.rfq", required=True, ondelete="cascade", tracking=True)
# #     partner_id = fields.Many2one("res.partner", string="Supplier", required=True, tracking=True)
# #     company_name = fields.Char(required=True)
# #     contact_name = fields.Char()
# #     contact_email = fields.Char(required=True)
# #     submitted_at = fields.Datetime(default=lambda self: fields.Datetime.now(), readonly=True)
# #     line_ids = fields.One2many("ew.submission.line", "submission_id", string="Documents")
# #     state = fields.Selection([("submitted", "Submitted")], default="submitted")
# #     rfq_unlocked = fields.Boolean(related="rfq_id.unlocked", store=False)
# #
# #     @api.constrains("rfq_id")
# #     def _check_not_after_close(self):
# #         for rec in self:
# #             if fields.Datetime.now() > rec.rfq_id.closing_at:
# #                 raise ValidationError(_("Submissions are closed for this RFQ."))
# #
# # class EwSubmissionLine(models.Model):
# #     _name = "ew.submission.line"
# #     _description = "Supplier Submission Document Line"
# #
# #     submission_id = fields.Many2one("ew.submission", required=True, ondelete="cascade")
# #     requirement_id = fields.Many2one("ew.rfq.requirement", string="Requirement")
# #     name = fields.Char("Label", required=True)
# #     attachment_id = fields.Many2one("ir.attachment", required=True)


  # # Tracking
    # download_count = fields.Integer("Download Count", default=0, readonly=True)
    # last_downloaded_at = fields.Datetime("Last Downloaded At", readonly=True)
    # last_downloaded_by_id = fields.Many2one("res.users", string="Last Downloaded By", readonly=True)
    #
    # def action_download_document(self):
    #     """
    #     Backend button: sends the browser to a route that logs + streams the file.
    #     This does NOT itself increment counters; the controller does that to ensure
    #     the log is only created when the file is actually served.
    #     """
    #     self.ensure_one()
    #     # Only show/allow for SCM/Admin (extra safety; view also hides it)
    #     if not (self.env.user.has_group('ewseta_procurement.group_scm_owner') or
    #             self.env.user.has_group('ewseta_procurement.group_rfq_admin')):
    #         raise AccessError(_("Only SCM or Admin can download submissions here."))
    #     # Don’t allow if no file
    #     if not self.file and not self.attachment_id:
    #         raise AccessError(_("No file to download."))
    #
    #     return {
    #         'type': 'ir.actions.act_url',
    #         'url': f"/submission/line/{self.id}/download",
    #         'target': 'self',
    #     }
    #
    # # models/submission.py (append inside EwSubmission)
    # def action_view_download_logs(self):
    #     self.ensure_one()
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'name': _("Download Logs"),
    #         'res_model': 'ew.submission.line.download.log',
    #         'view_mode': 'tree,form',
    #         'domain': [('line_id', 'in', self.line_ids.ids)],
    #         'target': 'current',
    #     }




# from odoo import api, fields, models, _
# from odoo.exceptions import ValidationError, UserError
# from werkzeug.urls import url_quote
#
#
# class EwSubmission(models.Model):
#     _name = "ew.submission"
#     _description = "Supplier Submission"
#     _inherit = ['mail.thread', 'mail.activity.mixin']
#
#     name = fields.Char(string='Sub Ref', required=True, readonly=True, default='New', tracking=True)
#     rfq_id = fields.Many2one("ew.rfq", required=True, ondelete="cascade", tracking=True)
#     partner_id = fields.Many2one("res.partner", string="Supplier", required=True,
#                                  default=lambda self: self.env.user.partner_id.id, tracking=True)
#     company_name = fields.Char(required=True)
#     contact_name = fields.Char()
#     contact_email = fields.Char(required=True)
#     submitted_at = fields.Datetime(default=lambda self: fields.Datetime.now(), readonly=True)
#     line_ids = fields.One2many("ew.submission.line", "submission_id", string="Documents", ondelete='cascade')
#     email_norm = fields.Char(index=True, readonly=True)
#
#     state = fields.Selection(
#         [("draft", "Draft"), ("submitted", "Submitted"), ("closed", "Closed")],
#         default="draft", tracking=True, required=True,
#     )
#
#     _sql_constraints = [
#         ("uniq_rfq_partner", "unique(rfq_id, partner_id)", "This supplier already has a submission for this RFQ."),
#     ]
#
#     # ---------- HARDENED SEEDING ----------
#     def _seed_lines_from_rfq(self):
#         """Ensure this submission has one line per RFQ requirement.
#         Also self-heals RFQs missing default requirements."""
#         for sub in self:
#             rfq = sub.rfq_id.sudo()
#             # If RFQ somehow has no requirements, prefill them now (self-heal)
#             if not rfq.requirement_ids:
#                 if hasattr(rfq, "_prefill_requirements"):
#                     rfq._prefill_requirements()
#                 elif hasattr(rfq, "_default_requirements_commands"):
#                     rfq.write({"requirement_ids": rfq._default_requirements_commands()})
#             if not sub.line_ids and rfq.requirement_ids:
#                 sub.write({
#                     "line_ids": [(0, 0, {"requirement_id": r.id}) for r in rfq.requirement_ids]
#                 })
#
#     def _normalize_email(self, val):
#         return (val or "").strip().lower()
#
#     @api.model
#     def create(self, vals):
#         # 1) Sequence
#         if vals.get("name", "New") == "New":
#             seq = self.env["ir.sequence"].next_by_code("ew.submission")
#             vals["name"] = seq or "New"
#
#         # 2) Default partner (public flow safety)
#         if not vals.get("partner_id"):
#             partner = self.env.user.partner_id
#             if not partner:
#                 raise UserError(_("Your user has no linked Contact/Partner; ask admin to set one."))
#             vals["partner_id"] = partner.id
#
#         # 3) Friendly uniqueness check
#         rfq_id, partner_id = vals.get("rfq_id"), vals.get("partner_id")
#         if rfq_id and partner_id:
#             if self.search_count([("rfq_id", "=", rfq_id), ("partner_id", "=", partner_id)]):
#                 raise ValidationError(_("You have already submitted an application for this RFQ."))
#
#         # 3) Friendly uniqueness pre-checks (partner + email)
#         rfq_id = vals.get("rfq_id")
#         partner_id = vals.get("partner_id")
#         email_norm = self._normalize_email(vals.get("contact_email"))
#
#         if rfq_id and partner_id:
#             if self.search_count([("rfq_id", "=", rfq_id), ("partner_id", "=", partner_id)]):
#                 raise ValidationError(_("You have already submitted an application for this RFQ."))
#
#         if rfq_id and email_norm:
#             if self.search_count([
#                 ("rfq_id", "=", rfq_id),
#                 ("contact_email", "ilike", email_norm)  # case-insensitive compare
#             ]):
#                 raise ValidationError(_("A submission with this email already exists for this RFQ."))
#
#         # 4) Pre-close if created after deadline
#         rfq = rfq_id and self.env["ew.rfq"].browse(rfq_id).sudo()
#         now = fields.Datetime.now()
#         if rfq and rfq.closing_at and rfq.closing_at <= now:
#             vals["state"] = "closed"
#
#         # 5) Create
#         rec = super().create(vals)
#
#         # 6) Seed lines (bullet-proof)
#         rec._seed_lines_from_rfq()
#
#         # 7) If deadline passed, ensure RFQ is closed instantly (no cron delay)
#         if rfq and rfq.closing_at and rfq.closing_at <= now:
#             if hasattr(rfq, "_auto_close_if_due"):
#                 rfq._auto_close_if_due()
#             else:
#                 rfq.write({"unlocked": True, "state": "closed"})
#
#         return rec
#
#     # Keep your existing onchange for UI niceness (not relied upon)
#     @api.onchange("rfq_id")
#     def _onchange_rfq_id_seed_lines(self):
#         if self.rfq_id and not self.line_ids:
#             self.line_ids = [(0, 0, {"requirement_id": r.id}) for r in self.rfq_id.requirement_ids]
#
#     # replace your constraint with this stronger version
#     @api.constrains("rfq_id", "partner_id", "contact_email")
#     def _check_unique_supplier_per_rfq(self):
#         """
#         Enforce one submission per supplier per RFQ.
#         - by partner (exact)
#         - by email (case/space-insensitive) to catch duplicate partner records
#         """
#         for rec in self:
#             if not rec.rfq_id:
#                 continue
#
#             # 1) Partner-based duplicate
#             if rec.partner_id:
#                 dup_partner = self.search([
#                     ("id", "!=", rec.id),
#                     ("rfq_id", "=", rec.rfq_id.id),
#                     ("partner_id", "=", rec.partner_id.id),
#                 ], limit=1)
#                 if dup_partner:
#                     raise ValidationError(_("This supplier already has a submission for this RFQ."))
#
#             # 2) Email-based duplicate (normalized)
#             email_norm = self._normalize_email(rec.contact_email)
#             if email_norm:
#                 dup_email = self.search([
#                     ("id", "!=", rec.id),
#                     ("rfq_id", "=", rec.rfq_id.id),
#                     ("contact_email", "ilike", email_norm),
#                 ], limit=1)
#                 if dup_email:
#                     raise ValidationError(_("A submission with this email already exists for this RFQ."))


# # models/submission.py
# from odoo import api, fields, models, _
# from odoo.exceptions import ValidationError, UserError
# from werkzeug.urls import url_quote
#
#
# class EwSubmission(models.Model):
#     _name = "ew.submission"
#     _description = "Supplier Submission"
#     _inherit = ['mail.thread', 'mail.activity.mixin']
#
#     name = fields.Char(
#         string='Sub Ref',
#         required=True,
#         # copy=False,
#         readonly=True,
#         default='New')
#
#     # @api.model
#     # def create(self, vals):
#     #     if vals.get('name', 'New') == 'New':
#     #         vals['name'] = self.env['ir.sequence'].next_by_code('ew.submission') or 'New'
#     #     return super().create(vals)
#
#     rfq_id = fields.Many2one("ew.rfq", required=True, ondelete="cascade", tracking=True)
#     # partner_id = fields.Many2one("res.partner", string="Supplier", required=True, tracking=True)
#     company_name = fields.Char(required=True)
#     contact_name = fields.Char()
#     contact_email = fields.Char(required=True)
#     submitted_at = fields.Datetime(default=lambda self: fields.Datetime.now(), readonly=True)
#     line_ids = fields.One2many("ew.submission.line", "submission_id", string="Documents", ondelete='cascade')
#     # state = fields.Selection([("draft", "Draft"), ("submitted", "Submitted")], default="draft",  tracking=True,)
#     rfq_unlocked = fields.Boolean(related="rfq_id.unlocked", store=False)
#
#     state = fields.Selection(
#         [
#             ("draft", "Draft"),
#             ("submitted", "Submitted"),
#             ("closed", "Closed"),
#         ],
#         default="submitted",  # supplier creates as submitted (public or portal flow)
#         tracking=True,
#         required=True,
#     )
#
#     partner_id = fields.Many2one(
#         "res.partner",
#         string="Supplier",
#         required=True,
#         tracking=True,
#         default=lambda self: self.env.user.partner_id.id,
#     )
#
#     _sql_constraints = [
#         (
#             "uniq_rfq_partner",
#             "unique(rfq_id, partner_id)",
#             "This supplier already has a submission for this RFQ."
#         ),
#     ]
#
#     @api.model
#     def create(self, vals):
#         # 1) Sequence (set BEFORE super)
#         if vals.get("name", "New") == "New":
#             seq = self.env["ir.sequence"].next_by_code("ew.submission")
#             vals["name"] = seq or "New"
#
#         # 2) Default partner (set BEFORE super)
#         if not vals.get("partner_id"):
#             partner = self.env.user.partner_id
#             if not partner:
#                 raise UserError("Your user has no linked Contact/Partner; ask admin to set one.")
#             vals["partner_id"] = partner.id
#
#         rfq_id = vals.get("rfq_id")
#         partner_id = vals.get("partner_id")
#          # ✅ Friendly pre-check (avoids raw SQL error message)
#
#         if rfq_id and partner_id:
#             exists = self.search_count([("rfq_id", "=", rfq_id), ("partner_id", "=", partner_id)])
#             if exists:
#                 raise ValidationError(_("You have already submitted an application for this RFQ."))
#
#         # 3) Create record
#         rec = super().create(vals)
#
#         # 4) Seed document lines from RFQ requirements (AFTER create)
#         if not rec.line_ids and rec.rfq_id and rec.rfq_id.requirement_ids:
#             rec.write({
#                 "line_ids": [(0, 0, {"requirement_id": r.id}) for r in rec.rfq_id.requirement_ids]
#             })
#
#         return rec
#
#     @api.model
#     def cron_close_submissions_past_deadline(self):
#         """Close submissions whose RFQ is past closing but submission.state != closed."""
#         now = fields.Datetime.now()
#         # Find submissions where related RFQ deadline passed but state isn't closed
#         subs = self.search([
#             ("state", "!=", "closed"),
#             ("rfq_id.closing_at", "<=", now),
#         ])
#         for s in subs:
#             s.write({"state": "closed"})
#
#     @api.constrains("rfq_id", "partner_id")
#     def _check_unique_supplier_per_rfq(self):
#         """Extra guard in case of concurrent writes or manual edits."""
#         for rec in self:
#             if not rec.rfq_id or not rec.partner_id:
#                 continue
#             dup = self.search([
#                 ("id", "!=", rec.id),
#                 ("rfq_id", "=", rec.rfq_id.id),
#                 ("partner_id", "=", rec.partner_id.id),
#             ], limit=1)
#             if dup:
#                 raise ValidationError(_("This supplier already has a submission for this RFQ."))
#
#     @api.onchange("rfq_id")
#     def _onchange_rfq_id_seed_lines(self):
#         if self.rfq_id and not self.line_ids:
#             self.line_ids = [(0, 0, {"requirement_id": req.id}) for req in self.rfq_id.requirement_ids]
#
#     def action_draft(self):
#         self.state = "draft"
#
#     def action_submit(self):
#         self.state = "submitted"
#
#     # @api.model
#     # def create(self, vals):
#     #     rec = super().create(vals)
#     #     if not rec.line_ids and rec.rfq_id and rec.rfq_id.requirement_ids:
#     #         rec.write({"line_ids": [(0, 0, {"requirement_id": r.id}) for r in rec.rfq_id.requirement_ids]})
#     #     return rec
#
#     @api.constrains("line_ids", "line_ids.file")
#     def _check_required_documents_uploaded(self):
#         for sub in self:
#             by_req = {l.requirement_id.id: l for l in sub.line_ids}
#             missing = []
#             for req in sub.rfq_id.requirement_ids:
#                 if req.is_mandatory:
#                     line = by_req.get(req.id)
#                     if not line or not line.file:
#                         missing.append(req.name or _("(Unnamed requirement)"))
#             if missing:
#                 raise ValidationError(_("Missing files for mandatory documents:\n- %s") % "\n- ".join(missing))
