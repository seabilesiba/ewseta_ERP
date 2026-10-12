# models/rfq.py
import logging
from urllib.parse import quote

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import format_datetime

_logger = logging.getLogger(__name__)


class EwRfq(models.Model):
    _name = "ew.rfq"
    _description = "EWSETA RFQ/RFP"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char("Title", required=True, tracking=True)
    reference = fields.Char(
        "Reference",
        required=True,
        tracking=True,
        help="Example: EWSETA/RFQ/032/2026-27. Auto-generated on create; you may edit it.",
        default="New",
    )
    type = fields.Selection(
        [("rfq", "RFQ"), ("rfp", "RFP")],
        string="Type",
        required=True,
        default="rfq",
        tracking=True,
    )
    description = fields.Html()
    rfq_document = fields.Binary(string="RFQ document")
    rfq_document_filename = fields.Char(string="RFQ document filename")
    rfp_document = fields.Binary(string="RFP document")
    rfp_document_filename = fields.Char(string="RFP document filename")
    publication_type = fields.Selection(
        [
            ("public", "Public"),
            ("transversal", "Transversal"),
        ],
        string="Publication type",
        default="public",
        required=True,
        tracking=True,
    )
    service_category_id = fields.Many2one(
        "ew.service.category",
        string="Service category",
        help=(
            "The one service this transversal RFQ/RFP is for. Registered providers "
            "match when this category appears on their contact profile (they may "
            "offer other services too)."
        ),
    )
    province_ids = fields.Many2many(
        "res.country.state",
        "ew_rfq_province_rel",
        "rfq_id",
        "state_id",
        string="Provinces",
        domain="[('country_id.code', '=', 'ZA')]",
        help=(
            "Optional. When set, the provider contact must list at least one of "
            "these provinces, as well as the RFQ service category."
        ),
    )
    transversal_eligible_partner_ids = fields.Many2many(
        "res.partner",
        "ew_rfq_transversal_partner_rel",
        "rfq_id",
        "partner_id",
        string="Eligible service providers (snapshot)",
        copy=False,
        readonly=True,
    )
    transversal_eligible_count = fields.Integer(
        string="Matching providers",
        compute="_compute_transversal_eligible_count",
        inverse="_inverse_transversal_eligible_count",
        readonly=False,
    )
    provider_may_apply = fields.Boolean(
        string="Current user may apply",
        compute="_compute_provider_may_apply",
        search="_search_provider_may_apply",
    )
    requirement_ids = fields.One2many("ew.rfq.requirement", "rfq_id", string="Required Documents")
    closing_at = fields.Datetime("Closing Date & Time", required=True, tracking=True)
    unlocked = fields.Boolean("Unlocked", default=False)
    state = fields.Selection([("draft","Draft"),("published", "Published"),("closed", "Closed")], default="draft", tracking=True)
    supplier_note = fields.Text("Supplier Instructions")
    briefing_session = fields.Boolean(
        string="Briefing session",
        tracking=True,
        help="When enabled, suppliers see briefing details on the portal.",
    )
    briefing_compulsory = fields.Boolean(
        string="Briefing compulsory",
        tracking=True,
        help="Shown to suppliers as policy: attendance expected. Does not block RFQ application on the portal.",
    )
    briefing_mode = fields.Selection(
        [
            ("virtual", "Virtual"),
            ("contact", "Contact (on-site)"),
        ],
        string="Briefing format",
        tracking=True,
    )
    briefing_location = fields.Text(
        string="Briefing venue address",
        help="Physical address when the briefing is on-site.",
    )
    briefing_virtual_link = fields.Char(
        string="Virtual briefing link",
        help="Meeting URL when the briefing is virtual.",
    )
    briefing_at = fields.Datetime(
        string="Briefing starts",
        tracking=True,
        help="Suppliers may register attendance only during the session window.",
    )
    briefing_end_at = fields.Datetime(
        string="Briefing ends",
        tracking=True,
    )
    briefing_start_mail_sent = fields.Boolean(
        string="Briefing start email sent",
        copy=False,
        readonly=True,
        help="Set when the automatic briefing-start notification has been sent.",
    )
    submission_ids = fields.One2many("ew.submission", "rfq_id", string="Submissions", ondelete="cascade")
    briefing_attendance_ids = fields.One2many(
        "ew.rfq.briefing.attendance",
        "rfq_id",
        string="Briefing attendance",
    )
    briefing_attendance_count = fields.Integer(
        string="Briefing registrations",
        compute="_compute_briefing_attendance_count",
    )
    opening_at = fields.Datetime(string="Created On", default=fields.Datetime.now, store=True)

    @api.depends("briefing_attendance_ids")
    def _compute_briefing_attendance_count(self):
        for rfq in self:
            rfq.briefing_attendance_count = len(rfq.briefing_attendance_ids)

    def _portal_procurement_document(self):
        """Return (binary, filename) for the document matching this record's type."""
        self.ensure_one()
        if self.type == "rfp":
            return self.rfp_document, self.rfp_document_filename
        return self.rfq_document, self.rfq_document_filename

    def portal_has_rfq_document(self):
        self.ensure_one()
        document, _filename = self._portal_procurement_document()
        return bool(document)

    def portal_rfq_document_label(self):
        self.ensure_one()
        _document, filename = self._portal_procurement_document()
        default = _("RFP document") if self.type == "rfp" else _("RFQ document")
        return (filename or "").strip() or default

    def _validate_procurement_document_for_publish(self):
        self.ensure_one()
        if not self.type:
            raise UserError(_("Select RFQ or RFP before publishing."))
        if self.type == "rfp":
            if not self.rfp_document:
                raise UserError(_("Please upload the RFP document before publishing."))
        elif not self.rfq_document:
            raise UserError(_("Please upload the RFQ document before publishing."))

    def _validate_closing_for_publish(self):
        """Reject publish when the deadline is already past (would instant-close)."""
        self.ensure_one()
        if not self.closing_at:
            raise UserError(_("Set the closing date and time before publishing."))
        now = fields.Datetime.now()
        if self.closing_at <= now:
            raise UserError(
                _(
                    "Closing date & time must be in the future to publish. "
                    "It is currently set to %(closing)s (now: %(now)s). "
                    "Update the closing date, then publish again."
                )
                % {
                    "closing": format_datetime(self.env, self.closing_at),
                    "now": format_datetime(self.env, now),
                }
            )

    @api.model
    def _south_africa_country(self):
        return self.env.ref("base.za", raise_if_not_found=False)

    def _validate_transversal_for_publish(self):
        self.ensure_one()
        if self.publication_type != "transversal":
            return
        if not self.service_category_id:
            raise ValidationError(
                _("Select the service category for this transversal RFQ/RFP.")
            )
        eligible = self._find_eligible_service_providers()
        if not eligible:
            raise UserError(
                _(
                    "No active registered service providers offer the selected "
                    "service category(ies)%(province_hint)s. On each provider contact, "
                    "open EWSETA procurement, enable service provider, and set matching "
                    "service categories (and provinces if you filter by province here)."
                )
                % {
                    "province_hint": (
                        _(" and operate in the selected province(s)")
                        if self.province_ids
                        else ""
                    ),
                }
            )

    def _transversal_service_category_id(self):
        self.ensure_one()
        return self.service_category_id.id or 0

    def _transversal_province_ids(self):
        """Province state ids for matching (works on saved RFQs and live form edits)."""
        self.ensure_one()
        return list(self.province_ids.ids)

    def _partner_offers_rfq_service(self, partner):
        """True when the RFQ service is one of the services on the provider contact."""
        self.ensure_one()
        cat_id = self._transversal_service_category_id()
        if not cat_id:
            return False
        return cat_id in partner.sudo().ew_service_category_ids.ids

    def _domain_registered_service_provider_partners(self):
        """Active registered SP contacts linked to internal SP users."""
        self.ensure_one()
        if self.publication_type != "transversal":
            return [("id", "=", 0)]
        group = self.env.ref("ewseta_procurement.group_service_provider")
        active_user_partners = self.env["res.users"].sudo().search([
            ("active", "=", True),
            ("group_ids", "in", group.ids),
        ]).mapped("partner_id").ids
        return [
            ("ew_service_provider", "=", True),
            ("active", "=", True),
            ("id", "in", active_user_partners or [0]),
        ]

    def _filter_partners_by_service_category(self, partners):
        self.ensure_one()
        if not self._transversal_service_category_id():
            return partners.browse()
        return partners.filtered(lambda p: self._partner_offers_rfq_service(p))

    def _filter_partners_by_provinces(self, partners):
        self.ensure_one()
        province_ids = self._transversal_province_ids()
        if not province_ids:
            return partners
        rfq_provinces = self.env["res.country.state"].browse(province_ids)
        return partners.filtered(
            lambda p: bool(p.ew_province_ids & rfq_provinces)
        )

    def _find_eligible_service_providers(self):
        self.ensure_one()
        if not self._transversal_service_category_id():
            return self.env["res.partner"].browse()
        Partner = self.env["res.partner"].sudo()
        candidates = Partner.search(self._domain_registered_service_provider_partners())
        by_category = self._filter_partners_by_service_category(candidates)
        if not self._transversal_province_ids():
            return by_category
        return self._filter_partners_by_provinces(by_category)

    def _partner_matches_transversal(self, partner):
        self.ensure_one()
        if self.publication_type != "transversal":
            return False
        partner = partner.sudo()
        if not partner or not partner._ew_procurement_provider_active():
            return False
        if self.state == "published" and self.transversal_eligible_partner_ids:
            return partner in self.transversal_eligible_partner_ids
        return partner in self._find_eligible_service_providers()

    @api.depends(
        "publication_type",
        "service_category_id",
        "province_ids",
        "transversal_eligible_partner_ids",
        "state",
    )
    def _compute_transversal_eligible_count(self):
        for rfq in self:
            if rfq.publication_type != "transversal":
                rfq.transversal_eligible_count = 0
            elif rfq.state == "published" and rfq.transversal_eligible_partner_ids:
                rfq.transversal_eligible_count = len(rfq.transversal_eligible_partner_ids)
            else:
                rfq.transversal_eligible_count = len(rfq._find_eligible_service_providers())

    def _inverse_transversal_eligible_count(self):
        """Allow onchange to set a live preview before save (no persistence)."""
        return

    @api.onchange("publication_type", "service_category_id", "province_ids")
    def _onchange_transversal_matching_preview(self):
        """Refresh matching count on the form before the RFQ is saved."""
        for rfq in self:
            if rfq.publication_type != "transversal" or not rfq.service_category_id:
                rfq.transversal_eligible_count = 0
            else:
                rfq.transversal_eligible_count = len(
                    rfq._find_eligible_service_providers()
                )

    @api.depends("publication_type", "state", "transversal_eligible_partner_ids")
    def _compute_provider_may_apply(self):
        user = self.env.user
        partner = user.partner_id
        is_sp = user.has_group("ewseta_procurement.group_service_provider")
        now = fields.Datetime.now()
        for rfq in self:
            rfq.provider_may_apply = rfq._user_may_apply_rfq(
                user=user,
                partner=partner,
                is_service_provider=is_sp,
                now=now,
            )

    @api.model
    def _search_provider_may_apply(self, operator, value):
        if operator not in ("=", "!="):
            return []
        want = value if operator == "=" else not value
        if not self.env.user.has_group("ewseta_procurement.group_service_provider"):
            domain = [("publication_type", "=", "public"), ("state", "=", "published")]
        else:
            partner_id = self.env.user.partner_id.id
            domain = [
                ("state", "=", "published"),
                ("publication_type", "=", "transversal"),
                ("transversal_eligible_partner_ids", "in", [partner_id]),
            ]
        rfqs = self.search(domain)
        if want:
            return [("id", "in", rfqs.ids)]
        return [("id", "not in", rfqs.ids)]

    def _user_may_apply_rfq(self, user=None, partner=None, is_service_provider=None, now=None):
        self.ensure_one()
        now = now or fields.Datetime.now()
        if self.state != "published":
            return False
        if self.closing_at and self.closing_at <= now:
            return False
        user = user or self.env.user
        is_sp = (
            is_service_provider
            if is_service_provider is not None
            else user.has_group("ewseta_procurement.group_service_provider")
        )
        if self.publication_type == "public":
            return not is_sp or user._is_public()
        if not is_sp or user._is_public():
            return False
        partner = partner or user.partner_id
        return self._partner_matches_transversal(partner)

    def is_public_portal_rfq(self):
        """May appear on the anonymous public procurement website."""
        self.ensure_one()
        return self.publication_type == "public"

    def assert_public_portal_access(self):
        """Return False if this RFQ must not be exposed on the public website."""
        self.ensure_one()
        return self.is_public_portal_rfq()

    def _assert_provider_may_apply(self, partner=None, user=None):
        """Raise UserError if the given user/partner may not apply to this RFQ."""
        self.ensure_one()
        user = user or self.env.user
        partner = partner or user.partner_id
        if user.has_group("ewseta_procurement.group_rfq_admin") or user.has_group(
            "ewseta_procurement.group_scm_owner"
        ):
            return True
        if self.publication_type == "public":
            if user.has_group("ewseta_procurement.group_service_provider") and not user._is_public():
                raise UserError(
                    _(
                        "Public RFQs/RFPs are applied for on the EWSETA website. "
                        "In Odoo, use SP Procurement → Transversal RFQs/RFPs for "
                        "invited opportunities."
                    )
                )
            return True
        if not self._user_may_apply_rfq(user=user, partner=partner):
            raise UserError(
                _(
                    "This transversal RFQ/RFP is only available to registered "
                    "service providers who match the published categories and provinces."
                )
            )
        return True

    def _transversal_submission_action_url(self):
        """Deep link to this RFQ in the provider backend (Apply from the form)."""
        self.ensure_one()
        base = self.get_base_url()
        action = self.env.ref(
            "ewseta_procurement.action_ew_rfq_provider_transversal",
            raise_if_not_found=False,
        )
        action_id = action.id if action else ""
        return (
            f"{base}/web#id={self.id}&model=ew.rfq&view_type=form"
            f"&action={action_id}"
        )

    def _send_transversal_publication_emails(self):
        self.ensure_one()
        template = self.env.ref(
            "ewseta_procurement.mail_tmpl_transversal_rfq_published",
            raise_if_not_found=False,
        )
        if not template:
            return 0
        sent = 0
        failed = 0
        for partner in self.transversal_eligible_partner_ids:
            email = (partner.email or "").strip()
            if not email:
                continue
            try:
                template.with_context(
                    recipient_name=partner.name,
                    transversal_apply_url=self._transversal_submission_action_url(),
                ).send_mail(
                    self.id,
                    force_send=False,
                    email_values={
                        "email_to": email,
                        "partner_ids": [],
                        "recipient_ids": [(5, 0, 0)],
                    },
                )
                sent += 1
            except Exception:
                failed += 1
                _logger.exception(
                    "Transversal publish email failed for RFQ %s to %s",
                    self.id,
                    email,
                )
        if failed:
            self.message_post(
                body=_(
                    "Transversal notification could not be sent to %(failed)s "
                    "provider(s) (mail error). %(sent)s sent successfully."
                )
                % {"failed": failed, "sent": sent},
                subtype_xmlid="mail.mt_note",
            )
        return sent

    def action_view_matching_service_providers(self):
        self.ensure_one()
        if self.state == "published" and self.transversal_eligible_partner_ids:
            partners = self.transversal_eligible_partner_ids
        else:
            partners = self._find_eligible_service_providers()
        return {
            "type": "ir.actions.act_window",
            "name": _("Matching service providers"),
            "res_model": "res.partner",
            "view_mode": "list,form",
            "domain": [("id", "in", partners.ids)],
            "context": {"create": False},
        }

    def portal_briefing_rfq_eligible(self):
        """Briefing register link: published/closed public or transversal RFQs with briefing."""
        self.ensure_one()
        if not self.briefing_session or not self.briefing_mode:
            return False
        if self.state not in ("published", "closed"):
            return False
        return self.publication_type in ("public", "transversal")

    def _portal_trigger_briefing_start_emails_if_due(self):
        """Safety net when cron missed the exact briefing_at minute."""
        self.ensure_one()
        if not self.portal_briefing_rfq_eligible():
            return False
        now = fields.Datetime.now()
        if not self.briefing_at or now < self.briefing_at:
            return False
        if self.briefing_end_at and now > self.briefing_end_at:
            return False
        return self._send_briefing_start_emails()

    def portal_briefing_registration_state(self):
        """open | before | after | unavailable | unconfigured"""
        self.ensure_one()
        now = fields.Datetime.now()
        if not self.briefing_session or not self.briefing_mode:
            return "unavailable"
        if not self.portal_briefing_rfq_eligible():
            return "unavailable"
        if not self.briefing_at or not self.briefing_end_at:
            return "unconfigured"
        if now < self.briefing_at:
            return "before"
        if now > self.briefing_end_at:
            return "after"
        return "open"

    def portal_allows_briefing_registration(self):
        """Portal registration only while the live briefing session is in progress."""
        self.ensure_one()
        return self.portal_briefing_registration_state() == "open"

    def portal_has_briefing_attendance(self, contact_email):
        self.ensure_one()
        email_norm = (contact_email or "").strip().lower()
        if not email_norm:
            return False
        return bool(self.env["ew.rfq.briefing.attendance"].sudo().search_count([
            ("rfq_id", "=", self.id),
            ("email_norm", "=", email_norm),
        ]))

    def _briefing_start_recipient_map(self):
        """Unique emails: suppliers who registered for this RFQ (briefing and/or application)."""
        self.ensure_one()
        recipients = {}
        for sub in self.submission_ids:
            email = (sub.contact_email or "").strip()
            if email:
                key = email.lower()
                recipients[key] = sub.company_name or sub.contact_name or email

        for att in self.briefing_attendance_ids:
            email = (att.contact_email or "").strip()
            if email:
                key = email.lower()
                recipients[key] = att.company_name or att.contact_name or email

        Notify = self.env["ew.rfq.briefing.notify"].sudo()
        for notify in Notify.search([("rfq_id", "=", self.id)]):
            email = (notify.contact_email or "").strip()
            if email:
                key = email.lower()
                recipients.setdefault(
                    key,
                    notify.company_name or notify.contact_name or email,
                )

        if self.publication_type == "transversal":
            partners = self.transversal_eligible_partner_ids
            if not partners and self.state != "published":
                partners = self._find_eligible_service_providers()
            for partner in partners:
                email = (partner.email or "").strip()
                if email:
                    key = email.lower()
                    recipients.setdefault(key, partner.name or email)

        return recipients

    def _briefing_start_blockers(self, manual=False):
        """Human-readable reasons briefing start mail cannot be sent (empty = OK)."""
        self.ensure_one()
        blockers = []
        now = fields.Datetime.now()
        if not self.briefing_session:
            blockers.append(_("Briefing session is not enabled on this RFQ/RFP."))
        if manual:
            if self.state not in ("published", "closed"):
                blockers.append(
                    _("The RFQ/RFP must be published or closed (current state: %s).")
                    % dict(self._fields["state"].selection).get(self.state, self.state)
                )
        elif self.state not in ("published", "closed"):
            blockers.append(_("The RFQ/RFP must be published or closed for automatic sending."))
        if not self.briefing_at:
            blockers.append(_("Set the briefing start date and time."))
        elif not manual and now < self.briefing_at:
            blockers.append(
                _("The briefing has not started yet (starts %s).")
                % format_datetime(self.env, self.briefing_at)
            )
        if not self._briefing_start_mail_template():
            blockers.append(_("The briefing start email template is missing (upgrade the module)."))
        if self.briefing_mode == "virtual" and not (self.briefing_virtual_link or "").strip():
            blockers.append(_("Enter the virtual briefing link before sending."))
        if self.briefing_mode == "contact" and not (self.briefing_location or "").strip():
            blockers.append(_("Enter the on-site briefing venue before sending."))
        return blockers

    def _briefing_start_prerequisites_ok(self, manual=False):
        self.ensure_one()
        return not self._briefing_start_blockers(manual=manual)

    def _briefing_start_mail_template(self):
        return self.env.ref(
            "ewseta_procurement.mail_tmpl_briefing_session_start",
            raise_if_not_found=False,
        )

    def _submission_for_briefing_email(self, email):
        """Application (submission) for this RFQ matching the briefing recipient email."""
        self.ensure_one()
        email = (email or "").strip()
        if not email:
            return self.env["ew.submission"].browse()
        return self.env["ew.submission"].sudo().search([
            ("rfq_id", "=", self.id),
            ("contact_email", "=ilike", email),
            ("state", "in", ("submitted", "closed")),
        ], limit=1)

    def _briefing_register_url_for_email(self, email):
        """Private attendance register URL (requires a submitted application)."""
        self.ensure_one()
        base = (self.env["ir.config_parameter"].sudo().get_param("web.base.url") or "").rstrip("/")
        if not base:
            return ""
        submission = self._submission_for_briefing_email(email)
        if not submission:
            return ""
        track_token = submission._issue_tracking_token()
        safe_token = quote(track_token, safe="")
        return f"{base}/application/rfqs/{self.id}/briefing/register?token={safe_token}"

    def _briefing_start_mail_context(self, recipient_name, recipient_email=None):
        self.ensure_one()
        base = (self.env["ir.config_parameter"].sudo().get_param("web.base.url") or "").rstrip("/")
        email = (recipient_email or "").strip()
        return {
            "recipient_name": recipient_name,
            "briefing_register_url": self._briefing_register_url_for_email(email),
            "briefing_apply_url": f"{base}/application/rfqs/{self.id}/apply" if base else "",
            "briefing_start_display": format_datetime(self.env, self.briefing_at) if self.briefing_at else "",
            "briefing_end_display": format_datetime(self.env, self.briefing_end_at) if self.briefing_end_at else "",
        }

    def _send_briefing_start_email_to(self, email, name, raise_on_error=False):
        """Send one briefing-start notification (virtual link or on-site venue)."""
        self.ensure_one()
        email = (email or "").strip()
        if not email:
            return False
        template = self._briefing_start_mail_template()
        if not template:
            return False
        try:
            template.with_context(
                **self._briefing_start_mail_context(name, recipient_email=email)
            ).send_mail(
                self.id,
                force_send=True,
                email_values={"email_to": email},
            )
        except Exception as err:
            if raise_on_error:
                raise UserError(
                    _("Could not send briefing email to %(email)s: %(error)s")
                    % {"email": email, "error": err}
                ) from err
            _logger.warning(
                "Briefing start email failed for RFQ %s → %s: %s",
                self.id,
                email,
                err,
            )
            return False
        return True

    def _briefing_session_window_active(self):
        """True between briefing_at and briefing_end_at (inclusive)."""
        self.ensure_one()
        now = fields.Datetime.now()
        if not self.briefing_at or now < self.briefing_at:
            return False
        if self.briefing_end_at and now > self.briefing_end_at:
            return False
        return True

    def _send_briefing_start_to_submission(self, submission):
        """Send briefing-start mail to one applicant (e.g. after late application)."""
        self.ensure_one()
        submission = submission.sudo()
        if submission.rfq_id.id != self.id:
            return False
        if submission.state not in ("submitted", "closed"):
            return False
        if not self._briefing_start_prerequisites_ok(manual=False):
            return False
        if not self._briefing_session_window_active():
            return False
        email = (submission.contact_email or "").strip()
        if not email:
            return False
        name = submission.company_name or submission.contact_name or email
        return self._send_briefing_start_email_to(email, name, raise_on_error=False)

    def _send_briefing_start_emails(self, manual=False):
        self.ensure_one()
        if self.briefing_start_mail_sent and not manual:
            return True
        if not self._briefing_start_prerequisites_ok(manual=manual):
            return False

        now = fields.Datetime.now()
        recipients = self._briefing_start_recipient_map()
        sent = 0
        for email, name in recipients.items():
            if self._send_briefing_start_email_to(
                email, name, raise_on_error=manual
            ):
                sent += 1

        if sent > 0:
            self.sudo().write({"briefing_start_mail_sent": True})
            self.message_post(
                body=_("Briefing session start notification sent to %s recipient(s).") % sent,
                subtype_xmlid="mail.mt_note",
            )
        elif manual:
            self.sudo().write({"briefing_start_mail_sent": True})
            if recipients:
                self.message_post(
                    body=_(
                        "Briefing session started but start emails could not be sent "
                        "(check outgoing mail configuration)."
                    ),
                    subtype_xmlid="mail.mt_note",
                )
            else:
                self.message_post(
                    body=_("No briefing notification recipients were found for this RFQ/RFP."),
                    subtype_xmlid="mail.mt_note",
                )
        elif recipients:
            self.message_post(
                body=_(
                    "Briefing session started but start emails could not be sent "
                    "(check outgoing mail configuration). Will retry automatically."
                ),
                subtype_xmlid="mail.mt_note",
            )
        elif self.briefing_end_at and now > self.briefing_end_at:
            self.sudo().write({"briefing_start_mail_sent": True})
            self.message_post(
                body=_(
                    "Briefing session ended with no notification recipients; "
                    "automatic start emails were not sent."
                ),
                subtype_xmlid="mail.mt_note",
            )
        return bool(sent) or manual

    def action_send_briefing_start_emails(self):
        for rfq in self:
            blockers = rfq._briefing_start_blockers(manual=True)
            if blockers:
                raise UserError(
                    _("Cannot send briefing emails for %s:\n\n%s")
                    % (rfq.display_name, "\n".join("• %s" % b for b in blockers))
                )
            if rfq.briefing_start_mail_sent:
                rfq.sudo().write({"briefing_start_mail_sent": False})
            rfq._send_briefing_start_emails(manual=True)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Briefing emails"),
                "message": _(
                    "Briefing start notifications were sent (or queued in outgoing mail). "
                    "Check the RFQ chatter and Technical → Email → Emails if needed."
                ),
                "type": "success",
                "sticky": False,
            },
        }

    @api.model
    def _briefing_reset_stuck_mail_flags(self):
        """Allow automatic retry when flagged sent but no success was logged (legacy data)."""
        rfqs = self.sudo().search([
            ("briefing_session", "=", True),
            ("briefing_start_mail_sent", "=", True),
            ("briefing_at", "!=", False),
        ])
        for rfq in rfqs:
            if not rfq._briefing_start_recipient_map():
                continue
            success = rfq.message_ids.filtered(
                lambda m: m.body
                and "Briefing session start notification sent to" in m.body
            )
            if not success:
                rfq.write({"briefing_start_mail_sent": False})

    @api.model
    def _sync_due_briefing_emails(self):
        """Send briefing-start mail for RFQs whose start time has passed (cron + SCM UI safety net)."""
        if self.env.context.get("ewseta_rfq_skip_briefing_sync"):
            return
        now = fields.Datetime.now()
        Rfq = self.with_context(ewseta_rfq_skip_briefing_sync=True).sudo()
        rfqs = Rfq.search([
            ("briefing_session", "=", True),
            ("state", "in", ("published", "closed")),
            ("briefing_at", "!=", False),
            ("briefing_at", "<=", now),
            ("briefing_start_mail_sent", "=", False),
        ], limit=40)
        for rfq in rfqs:
            try:
                rfq._send_briefing_start_emails()
            except Exception as err:
                _logger.exception(
                    "Briefing start email sync failed for RFQ %s: %s",
                    rfq.id,
                    err,
                )

    @api.model
    def cron_send_briefing_start_emails(self):
        """Send briefing-start emails when briefing_at is reached (runs every minute)."""
        self._sync_due_briefing_emails()
        return True

    def action_open_briefing_attendance(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Briefing attendance"),
            "res_model": "ew.rfq.briefing.attendance",
            "view_mode": "list,form",
            "domain": [("rfq_id", "=", self.id)],
            "context": {
                "default_rfq_id": self.id,
                "default_mode": self.briefing_mode,
                "default_source": "scm_manual",
            },
        }

    def action_provider_open_briefing_register(self):
        """Transversal SP: open website attendance register (during live session)."""
        self.ensure_one()
        if not self.briefing_session:
            raise UserError(_("This RFQ/RFP has no briefing session."))
        submission = self.env["ew.submission"].search([
            ("rfq_id", "=", self.id),
            ("partner_id", "=", self.env.user.partner_id.id),
            ("state", "in", ("submitted", "closed")),
        ], limit=1)
        if not submission:
            raise UserError(
                _(
                    "Submit your application for this RFQ/RFP first, then sign the "
                    "briefing register during the live session."
                )
            )
        state = self.portal_briefing_registration_state()
        if state == "before":
            raise UserError(
                _("Registration opens when the briefing starts (%s).")
                % format_datetime(self.env, self.briefing_at)
            )
        if state == "after":
            raise UserError(
                _("The briefing session has ended (%s).")
                % format_datetime(self.env, self.briefing_end_at)
            )
        if state != "open":
            raise UserError(_("Briefing registration is not available for this RFQ/RFP."))
        self._portal_trigger_briefing_start_emails_if_due()
        token = submission._issue_tracking_token()
        safe_token = quote(token, safe="")
        url = f"{self.get_base_url()}/application/rfqs/{self.id}/briefing/register?token={safe_token}"
        return {
            "type": "ir.actions.act_url",
            "url": url,
            "target": "new",
        }

    @api.model
    def default_get(self, fields_list):
        # Odoo only computes defaults for requested fields; the form often omits reference/type.
        if fields_list:
            fields_list = list(fields_list)
            for fname in ("reference", "requirement_ids", "type", "state"):
                if fname not in fields_list:
                    fields_list.append(fname)
        vals = super().default_get(fields_list)
        if not vals.get("state"):
            vals["state"] = "draft"
        if not vals.get("type"):
            vals["type"] = self.env.context.get("default_type") or "rfq"
        rfq_type = vals.get("type")
        if rfq_type and self._reference_should_autogenerate(vals.get("reference")):
            vals["reference"] = self._peek_rfq_reference(rfq_type)
        if not vals.get("requirement_ids"):
            vals["requirement_ids"] = self._default_requirements_commands()
        return vals

    @api.model
    def new(self, values=None, origin=None, ref=None):
        values = dict(values or {})
        if not values.get("type"):
            values["type"] = self.env.context.get("default_type") or "rfq"
        record = super().new(values, origin, ref)
        if not record.state:
            record.state = "draft"
        if not record.type:
            record.type = self.env.context.get("default_type") or "rfq"
        if (
            not record.id
            and record.type
            and self._reference_should_autogenerate(record.reference)
        ):
            record.reference = self._peek_rfq_reference(record.type)
        return record

    @api.onchange("type")
    def _onchange_type_reference(self):
        """New records: show the correct EWSETA/RFQ/… or EWSETA/RFP/… when type changes."""
        if not self.type:
            return
        if not self.id:
            ref = (self.reference or "").strip()
            if self._reference_should_autogenerate(ref) or ref.startswith("EWSETA/"):
                self.reference = self._peek_rfq_reference(self.type)
        if self.type == "rfq":
            self.rfp_document = False
            self.rfp_document_filename = False
        elif self.type == "rfp":
            self.rfq_document = False
            self.rfq_document_filename = False

    @api.model
    def _standard_requirement_document_names(self):
        return {
            "CSD Report",
            "Tax Clearance",
            "BBBBEE Affidavit/Certificate",
            "CIPC Registration documents",
            "JV Agreement",
            "SBD 4",
            "SBD 3.1",
            "SBD 1",
            "SBD 3.3",
            "SBD 6.1",
            "POPIA Consent Form",
            "General Conditions of Purchase/Contract",
        }

    def _default_requirements_commands(self):
        DEFAULT_REQS = [
            (1, "CSD Report"),
            (2, "Tax Clearance"),
            (3, "BBBBEE Affidavit/Certificate"),
            (4, "CIPC Registration documents"),
            (5, "JV Agreement"),
            (6, "SBD 4"),
            (7, "SBD 3.1"),
            (8, "SBD 1"),
            (9, "SBD 3.3"),
            (10, "SBD 6.1"),
            (11, "POPIA Consent Form"),
            (12, "General Conditions of Purchase/Contract"),
        ]
        return [(0, 0, {
            "sequence": s,
            "name": n,
            "is_mandatory": False,
            "section": "optional",
        }) for s, n in DEFAULT_REQS]

    @api.model
    def _normalize_legacy_mandatory_requirement_commands(self, vals):
        """Drop legacy auto-mandatory prefill when saving a new RFQ from an old form."""
        names = self._standard_requirement_document_names()
        commands = vals.get("requirement_ids") or []
        template_cmds = [
            cmd for cmd in commands
            if cmd[0] == 0 and len(cmd) >= 3 and cmd[2].get("name") in names
        ]
        if not template_cmds:
            return
        mandatory_count = sum(1 for cmd in template_cmds if cmd[2].get("is_mandatory"))
        if mandatory_count < max(1, len(template_cmds) - 1):
            return
        for cmd in template_cmds:
            cmd[2]["is_mandatory"] = False
            cmd[2]["section"] = "optional"
    def _prefill_requirements(self):
        self.ensure_one()
        if not self.requirement_ids:
            self.write({"requirement_ids": self._default_requirements_commands()})
    #
    @api.constrains("briefing_at", "briefing_end_at")
    def _check_briefing_times(self):
        """Allow saving draft briefing fields step-by-step; only enforce time order."""
        for rfq in self:
            if (
                rfq.briefing_at
                and rfq.briefing_end_at
                and rfq.briefing_end_at <= rfq.briefing_at
            ):
                raise ValidationError(
                    _("Briefing end time must be after the start time.")
                )

    def _validate_briefing_for_publish(self):
        """Full briefing checks when publishing or sending start emails."""
        self.ensure_one()
        if not self.briefing_session:
            return
        if not self.briefing_mode:
            raise ValidationError(
                _("Select whether the briefing session is virtual or contact (on-site).")
            )
        if self.briefing_mode == "virtual" and not (self.briefing_virtual_link or "").strip():
            raise ValidationError(_("Provide the virtual briefing link before publishing."))
        if self.briefing_mode == "contact" and not (self.briefing_location or "").strip():
            raise ValidationError(_("Provide the briefing venue address before publishing."))
        if not self.briefing_at or not self.briefing_end_at:
            raise ValidationError(
                _("Set the briefing session start and end date/time before publishing.")
            )
        if self.briefing_end_at <= self.briefing_at:
            raise ValidationError(
                _("Briefing end time must be after the start time.")
            )

    @api.onchange("briefing_session")
    def _onchange_briefing_session(self):
        if not self.briefing_session:
            self.briefing_compulsory = False
            self.briefing_mode = False
            self.briefing_location = False
            self.briefing_virtual_link = False
            self.briefing_at = False
            self.briefing_end_at = False

    @api.onchange("briefing_mode")
    def _onchange_briefing_mode(self):
        if self.briefing_mode == "virtual":
            self.briefing_location = False
        elif self.briefing_mode == "contact":
            self.briefing_virtual_link = False

    def action_publish(self):
        for rec in self:
            rec._validate_procurement_document_for_publish()
            rec._validate_closing_for_publish()
            rec._validate_briefing_for_publish()
            rec._validate_transversal_for_publish()
            rec._prefill_requirements()
            publish_vals = {"state": "published"}
            if rec.publication_type == "transversal":
                eligible = rec._find_eligible_service_providers()
                publish_vals["transversal_eligible_partner_ids"] = [(6, 0, eligible.ids)]
            rec.write(publish_vals)
            if rec.publication_type == "transversal":
                sent = rec._send_transversal_publication_emails()
                rec.message_post(
                    body=_(
                        "Transversal RFQ/RFP published. Notifications queued for "
                        "%(count)s eligible service provider(s) (outgoing mail / cron)."
                    )
                    % {"count": sent},
                    subtype_xmlid="mail.mt_note",
                )
            else:
                rec.message_post(body=_("RFQ published."), subtype_xmlid="mail.mt_note")
            rec._auto_close_if_due()
            if (
                rec.briefing_session
                and rec.briefing_at
                and fields.Datetime.now() >= rec.briefing_at
                and not rec.briefing_start_mail_sent
            ):
                rec._send_briefing_start_emails()


    def action_close(self):
        to_notify = self.filtered(lambda r: r.state != "closed")
        self.write({"state": "closed", "unlocked": True})
        for rec in self:
            rec.submission_ids.filtered(lambda s: s.state != "closed").write({"state": "closed"})
            rec.message_post(body=_("RFQ manually closed and unlocked."), subtype_xmlid="mail.mt_note")
        to_notify._notify_scm_submissions_available()

    @api.model
    def _reference_should_autogenerate(self, ref):
        """True when the system should assign EWSETA/RFQ/… or EWSETA/RFP/…"""
        ref = (ref or "").strip()
        if not ref or ref == "New":
            return True
        legacy_prefixes = ("RGQ/RFP-", "EW-RGQ-", "RGQ/RFP/", "EW-RGQ/")
        if any(ref.startswith(prefix) for prefix in legacy_prefixes):
            return True
        return False

    @api.model
    def _reference_assign_on_create(self, ref):
        """Whether create() must consume the sequence and set the final reference."""
        if self._reference_should_autogenerate(ref):
            return True
        ref = (ref or "").strip()
        return ref.startswith("EWSETA/RFQ/") or ref.startswith("EWSETA/RFP/")

    @api.model
    def _peek_rfq_reference(self, rfq_type="rfq", when=None):
        """Next reference for the form (does not consume the sequence)."""
        type_code = "RFP" if rfq_type == "rfp" else "RFQ"
        fy = self._ewseta_financial_year_label(when=when)
        seq_code = f"ew.rfq.{rfq_type}.{fy.replace('-', '_')}"
        sequence = self.env["ir.sequence"].sudo().search([("code", "=", seq_code)], limit=1)
        padding = sequence.padding if sequence else 3
        next_num = sequence.number_next if sequence else 1
        return f"EWSETA/{type_code}/{str(next_num).zfill(padding)}/{fy}"

    @api.model
    def _deactivate_legacy_reference_sequence(self):
        """Retire RGQ/RFP-xxx sequence (replaced by EWSETA/RFQ/… per financial year)."""
        self.env["ir.sequence"].sudo().search([("code", "=", "ew.rfq")]).write({"active": False})

    @api.model
    def _reset_draft_requirement_mandatory_flags(self):
        """Clear legacy mandatory flags so users choose mandatory documents themselves."""
        Requirement = self.env["ew.rfq.requirement"].sudo()
        reqs = Requirement.search([])
        if reqs:
            reqs.write({"is_mandatory": False, "section": "optional"})

    @api.model
    def _fix_stale_references(self):
        """Assign EWSETA references to RFQs saved while the server ran stale code."""
        stale = self.sudo().search([
            "|", ("reference", "=", "New"), ("reference", "=", False),
        ])
        for rfq in stale:
            when = rfq.opening_at or fields.Datetime.now()
            rfq.reference = self._generate_rfq_reference(rfq.type or "rfq", when=when)

    @api.model
    def _ewseta_financial_year_label(self, when=None):
        """EWSETA financial year label (1 April – 31 March), e.g. 2026-27."""
        when = when or fields.Datetime.now()
        dt = fields.Datetime.to_datetime(when)
        start_year = dt.year if dt.month >= 4 else dt.year - 1
        end_short = (start_year + 1) % 100
        return f"{start_year}-{end_short:02d}"

    @api.model
    def _generate_rfq_reference(self, rfq_type="rfq", when=None):
        """Build EWSETA/RFQ/032/2026-27 (or RFP) with per-type, per-FY sequence."""
        type_code = "RFP" if rfq_type == "rfp" else "RFQ"
        fy = self._ewseta_financial_year_label(when=when)
        seq_code = f"ew.rfq.{rfq_type}.{fy.replace('-', '_')}"
        Sequence = self.env["ir.sequence"].sudo()
        sequence = Sequence.search([("code", "=", seq_code)], limit=1)
        if not sequence:
            sequence = Sequence.create({
                "name": f"EWSETA {type_code} {fy}",
                "code": seq_code,
                "padding": 3,
                "number_next": 1,
                "number_increment": 1,
            })
        number = sequence.next_by_id()
        return f"EWSETA/{type_code}/{number}/{fy}"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("type"):
                raise ValidationError(_("Select RFQ or RFP before saving."))
            self._normalize_legacy_mandatory_requirement_commands(vals)
            ref = vals.get("reference")
            if self._reference_assign_on_create(ref):
                when = vals.get("opening_at") or fields.Datetime.now()
                if isinstance(when, str):
                    when = fields.Datetime.from_string(when)
                vals["reference"] = self._generate_rfq_reference(
                    vals["type"],
                    when=when,
                )

        records = super().create(vals_list)
        for rec in records:
            rec._prefill_requirements()
            rec._auto_close_if_due()
        return records

    def write(self, vals):
        if any(
            k in vals
            for k in (
                "briefing_at",
                "briefing_end_at",
                "briefing_session",
                "briefing_mode",
                "briefing_virtual_link",
                "briefing_location",
            )
        ):
            vals = dict(vals, briefing_start_mail_sent=False)
        res = super().write(vals)
        # If closing_at/state changed, re-evaluate immediately
        if any(k in vals for k in ("closing_at", "state", "unlocked")):
            self._auto_close_if_due()
        to_notify = self.filtered(
            lambda r: r.briefing_session
            and r.state in ("published", "closed")
            and not r.briefing_start_mail_sent
            and r.briefing_at
            and fields.Datetime.now() >= r.briefing_at
        )
        for rfq in to_notify:
            rfq._send_briefing_start_emails()
        return res

    @api.model
    def _sync_due_closures(self):
        """Close published RFQs whose deadline has passed (unlock submissions for SCM)."""
        if self.env.context.get("ewseta_rfq_skip_sync_due"):
            return
        now = fields.Datetime.now()
        Rfq = self.with_context(ewseta_rfq_skip_sync_due=True).sudo()
        due = Rfq.search([
            ("state", "=", "published"),
            ("unlocked", "=", False),
            ("closing_at", "!=", False),
            ("closing_at", "<=", now),
        ])
        if due:
            due._auto_close_if_due()

    def _scm_may_view_submissions(self):
        """Whether SCM users should see submission data for this RFQ."""
        self.ensure_one()
        if self.state == "closed" or self.unlocked:
            return True
        now = fields.Datetime.now()
        return bool(
            self.state == "published"
            and self.closing_at
            and self.closing_at <= now
        )

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, *, active_test=True, bypass_access=False):
        if self.env.context.get("ewseta_procurement_scm_ui"):
            if not self.env.context.get("ewseta_rfq_skip_sync_due"):
                self._sync_due_closures()
            if not self.env.context.get("ewseta_rfq_skip_briefing_sync"):
                self._sync_due_briefing_emails()
        return super()._search(
            domain,
            offset=offset,
            limit=limit,
            order=order,
            active_test=active_test,
            bypass_access=bypass_access,
        )

    def _auto_close_if_due(self):
        """Close RFQ (and linked submissions) immediately if deadline already passed."""
        now = fields.Datetime.now()
        for rfq in self:
            if rfq.state == "published" and rfq.closing_at and rfq.closing_at <= now and not rfq.unlocked:
                rfq.with_context(mail_post_autofollow=True).write({"unlocked": True, "state": "closed"})
                rfq.submission_ids.filtered(lambda s: s.state != "closed").write({"state": "closed"})
                rfq.message_post(
                    body=_("RFQ <b>%s</b> has closed (deadline reached). Submissions are now visible.") % (rfq.name,),
                    subtype_xmlid="mail.mt_note",
                )
                rfq._notify_scm_submissions_available()

    def _notify_scm_submissions_available(self):
        """Alert SCM owners / procurement admins when submissions can be reviewed."""
        scm_group = self.env.ref("ewseta_procurement.group_scm_owner", raise_if_not_found=False)
        admin_group = self.env.ref("ewseta_procurement.group_rfq_admin", raise_if_not_found=False)
        users = self.env["res.users"]
        if scm_group:
            users |= scm_group.user_ids
        if admin_group:
            users |= admin_group.user_ids
        users = users.filtered(lambda u: u.active and u.partner_id)
        if not users:
            return

        for rfq in self:
            if rfq.state != "closed":
                continue
            count = len(rfq.submission_ids)
            summary = _("RFQ closed — review submissions")
            note = _(
                "RFQ/RFP %s (%s) has closed. %s submission(s) are now available to review."
            ) % (rfq.name, rfq.reference, count)
            rfq.message_post(
                body=note,
                subtype_xmlid="mail.mt_comment",
                partner_ids=users.partner_id.ids,
            )
            for user in users:
                rfq.activity_schedule(
                    "mail.mail_activity_data_todo",
                    user_id=user.id,
                    summary=summary,
                    note=note,
                )

    # Safety net: cron still runs (keep just ONE definition)
    @api.model
    def cron_unlock_due_rfqs(self):
        self._sync_due_closures()
        self.cron_send_briefing_start_emails()

    # Optional helper (kept if you use search domains elsewhere)
    is_past_closing = fields.Boolean(
        string="Closing Passed",
        compute="_compute_is_past_closing",
        search="_search_is_past_closing",
        store=False,
    )

    def _compute_is_past_closing(self):
        now = fields.Datetime.now()
        for r in self:
            r.is_past_closing = bool(r.closing_at and r.closing_at <= now)

    @api.model
    def _search_is_past_closing(self, operator, value):
        now = fields.Datetime.now()
        positive = (operator in ('=', '==') and bool(value)) or (operator in ('!=', '<>') and not bool(value))
        return [('closing_at', '<=', now)] if positive else [('closing_at', '>', now)]

    submission_count = fields.Integer(
        string="Submissions",
        compute="_compute_submission_count",
        store=False,          # keep it computed on the fly for now
        compute_sudo=True,
    )

    scm_show_submission_stats = fields.Boolean(
        string="SCM Show Submission Stats",
        compute="_compute_scm_submission_stats",
        compute_sudo=True,
    )
    scm_submission_count = fields.Integer(
        string="Submissions (SCM)",
        compute="_compute_scm_submission_stats",
        compute_sudo=True,
    )
    scm_submissions_display = fields.Char(
        string="Submissions",
        compute="_compute_scm_submission_stats",
        compute_sudo=True,
    )
    scm_submissions_visible = fields.Boolean(
        compute="_compute_scm_submission_stats",
        compute_sudo=True,
    )

    @api.depends("submission_ids", "state", "unlocked", "closing_at")
    def _compute_submission_count(self):
        """Count submissions; hide from SCM UI until RFQ/RFP is closed."""
        Sub = self.env["ew.submission"].sudo()
        scm_ui = bool(self.env.context.get("ewseta_procurement_scm_ui"))
        for rfq in self:
            count = Sub.search_count([("rfq_id", "=", rfq.id)]) if rfq.id else 0
            if scm_ui and not rfq._scm_may_view_submissions():
                rfq.submission_count = 0
            else:
                rfq.submission_count = count

    @api.depends("state", "submission_ids", "unlocked", "closing_at")
    def _compute_scm_submission_stats(self):
        """SCM views: expose submission counts once RFQ/RFP is closed or past closing."""
        Sub = self.env["ew.submission"].sudo()
        scm_ui = bool(self.env.context.get("ewseta_procurement_scm_ui"))
        for rfq in self:
            show = scm_ui and rfq._scm_may_view_submissions()
            rfq.scm_submissions_visible = show
            rfq.scm_show_submission_stats = show
            if show:
                count = Sub.search_count([("rfq_id", "=", rfq.id)]) if rfq.id else 0
                rfq.scm_submission_count = count
                rfq.scm_submissions_display = str(count) if count else ""
            else:
                rfq.scm_submission_count = 0
                rfq.scm_submissions_display = ""

    def action_open_submissions(self):
        self.ensure_one()
        self._auto_close_if_due()
        user = self.env.user
        scm_ui = bool(self.env.context.get("ewseta_procurement_scm_ui"))
        is_admin = user.has_group("ewseta_procurement.group_rfq_admin")
        is_scm = user.has_group("ewseta_procurement.group_scm_owner")
        if (scm_ui or (is_scm and not is_admin)) and not self._scm_may_view_submissions():
            raise UserError(
                _("Submissions can only be viewed after this RFQ/RFP is closed.")
            )
        return {
            "name": _("Submissions"),
            "type": "ir.actions.act_window",
            "res_model": "ew.submission",
            "view_mode": "list,form,kanban",
            "domain": [("rfq_id", "=", self.id)],
            "target": "current",
        }

    # is_private = fields.Boolean(
    #     string="Private RFQ",
    #     tracking=True,
    #     help="Only invited internal service providers may apply.",
    # )
    #
    # invited_provider_ids = fields.Many2many(
    #     "res.partner",
    #     "ew_rfq_partner_rel",
    #     "rfq_id",
    #     "partner_id",
    #     string="Invited Providers",
    #     domain="[('is_company','=',True)]",
    #     tracking=True,
    #     help="Select internal providers allowed to apply for this private RFQ.",
    # )
    #
    # def action_publish(self):
    #     """
    #     Publish RFQ:
    #     - Ensure RFQ document is uploaded
    #     - Prefill requirements
    #     - Set state to 'published', log it, auto-close if needed
    #     - If private RFQ, email invited internal providers with application link
    #     """
    #     for rfq in self:
    #         # 1) Basic validation
    #         if not rfq.rfq_document:
    #             raise UserError(_("Please upload the RFQ document before publishing."))
    #
    #         # 2) Prefill requirements once
    #         rfq._prefill_requirements()
    #
    #         # 3) Publish
    #         rfq.state = "published"
    #         rfq.message_post(
    #             body=_("RFQ published."),
    #             subtype_xmlid="mail.mt_note",
    #         )
    #         rfq._auto_close_if_due()
    #
    #         # 4) Private RFQ invitations
    #         if rfq.is_private and rfq.invited_provider_ids:
    #             template = rfq.env.ref(
    #                 "ewseta_procurement.mail_tmpl_private_rfq_invitation",
    #                 raise_if_not_found=False,
    #             )
    #             if template:
    #                 for provider in rfq.invited_provider_ids:
    #                     if not provider.email:
    #                         continue
    #                     # Send RFQ as object; override recipient via context
    #                     template.with_context(
    #                         lang=provider.lang or rfq.env.user.lang,
    #                         email_to=provider.email,
    #                     ).send_mail(rfq.id, force_send=True)
    #
    #             rfq.message_post(
    #                 body=_("Private RFQ invitation emails have been sent."),
    #                 subtype_xmlid="mail.mt_note",
    #             )
    #
    # private_rfq_url = fields.Char(
    #     string="Private RFQ URL",
    #     compute="_compute_private_rfq_url",
    #     store=False,
    # )
    #
    # @api.depends('submission_ids')
    # def _compute_private_rfq_url(self):
    #     base = self.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
    #     for rfq in self:
    #         rfq.private_rfq_url = f"{base}/application/rfqs/{rfq.id}/apply" if rfq.id else base
    #

    @api.model
    def _website_procurement_landing_counts(self):
        """Counts for public website homepage (RFQ landing)."""
        now = fields.Datetime.now()
        open_count = self.sudo().search_count([
            ('state', '=', 'published'),
            ('closing_at', '>', now),
        ])
        closed_count = self.sudo().search_count([
            '|',
            ('state', '=', 'closed'),
            '&',
            ('state', '=', 'published'),
            ('closing_at', '<=', now),
        ])
        return {'open_count': open_count, 'closed_count': closed_count}

class EwRfqRequirement(models.Model):
    _name = "ew.rfq.requirement"
    _description = "RFQ Required Document"
    _order = "section, sequence, id"

    rfq_id = fields.Many2one("ew.rfq", required=True, ondelete="cascade", tracking=True)
    sequence = fields.Integer(default=10)
    name = fields.Char("Document Name", required=True,tracking=True)
    code = fields.Char("Code")
    is_mandatory = fields.Boolean(string="Mandatory", default=False)
    section = fields.Selection(
        [("mandatory", "Mandatory"), ("optional", "Not Mandatory")],
        default="optional",
        required=True,
        tracking=True,
    )
    help_text = fields.Char("Help")

    @api.onchange("is_mandatory")
    def _onchange_is_mandatory(self):
        self.section = "mandatory" if self.is_mandatory else "optional"

    @api.onchange("section")
    def _onchange_section(self):
        self.is_mandatory = self.section == "mandatory"

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._sync_requirement_mandatory_fields(vals)
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        self._sync_requirement_mandatory_fields(vals)
        return super().write(vals)

    @api.model
    def _sync_requirement_mandatory_fields(self, vals):
        if "is_mandatory" in vals and "section" not in vals:
            vals["section"] = "mandatory" if vals["is_mandatory"] else "optional"
        elif "section" in vals and "is_mandatory" not in vals:
            vals["is_mandatory"] = vals["section"] == "mandatory"

