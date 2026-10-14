import secrets

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.misc import format_datetime


class EwRfqBriefingAttendance(models.Model):
    _name = "ew.rfq.briefing.attendance"
    _description = "Briefing Session Attendance"
    _order = "attended_at desc, id desc"

    rfq_id = fields.Many2one(
        "ew.rfq",
        string="RFQ / RFP",
        required=True,
        ondelete="cascade",
        index=True,
    )
    partner_id = fields.Many2one("res.partner", string="Supplier")
    company_name = fields.Char(required=True)
    contact_name = fields.Char()
    contact_email = fields.Char(string="Contact email", required=True)
    contact_phone = fields.Char(string="Contact phone")
    email_norm = fields.Char(
        string="Email (normalized)",
        compute="_compute_email_norm",
        store=True,
        index=True,
    )
    attended_at = fields.Datetime(
        string="Registered at",
        default=lambda self: fields.Datetime.now(),
        required=True,
    )
    mode = fields.Selection(
        [
            ("virtual", "Virtual"),
            ("contact", "Contact (on-site)"),
        ],
        string="Briefing format",
        required=True,
        readonly=True,
    )
    source = fields.Selection(
        [
            ("portal", "Portal self-registration"),
            ("sp_backend", "Service provider (backend)"),
            ("scm_manual", "SCM manual"),
        ],
        string="Source",
        default="portal",
        required=True,
        readonly=True,
    )
    registered_by = fields.Many2one("res.users", string="Recorded by", readonly=True)
    notes = fields.Text()
    proof_token = fields.Char(copy=False, index=True)
    portal_proof_url = fields.Char(
        string="Portal proof link",
        compute="_compute_portal_proof_url",
        readonly=True,
    )

    _uniq_rfq_briefing_email = models.Constraint(
        "unique(rfq_id, email_norm)",
        "This email is already registered for this briefing session.",
    )

    @api.depends("contact_email")
    def _compute_email_norm(self):
        for rec in self:
            rec.email_norm = (rec.contact_email or "").strip().lower()

    @api.depends("proof_token")
    def _compute_portal_proof_url(self):
        for rec in self:
            rec.portal_proof_url = rec._portal_proof_url()

    def _ensure_proof_token(self):
        for rec in self:
            if not rec.proof_token:
                rec.sudo().write({"proof_token": secrets.token_urlsafe(32)})

    @api.model
    def find_by_proof_token(self, token):
        token = (token or "").strip()
        if not token:
            return self.browse()
        return self.sudo().search([("proof_token", "=", token)], limit=1)

    def _portal_proof_url(self):
        self.ensure_one()
        if not self.proof_token:
            return ""
        base = (self.env["ir.config_parameter"].sudo().get_param("web.base.url") or "").rstrip("/")
        if not base:
            return ""
        return f"{base}/application/briefing/attendance/{self.proof_token}"

    @api.model_create_multi
    def create(self, vals_list):
        Attendance = self.env["ew.rfq.briefing.attendance"]
        for vals in vals_list:
            rfq_id = vals.get("rfq_id")
            rfq = rfq_id and self.env["ew.rfq"].browse(rfq_id).exists()
            if rfq and not vals.get("mode"):
                vals["mode"] = rfq.briefing_mode or "virtual"
            if not vals.get("source"):
                vals["source"] = self.env.context.get("default_source") or "portal"
            if vals.get("source") == "scm_manual" and not vals.get("registered_by"):
                vals["registered_by"] = self.env.user.id
            email_norm = (vals.get("contact_email") or "").strip().lower()
            if rfq and email_norm:
                dup = Attendance.sudo().search([
                    ("rfq_id", "=", rfq.id),
                    ("email_norm", "=", email_norm),
                ], limit=1)
                if dup:
                    raise ValidationError(
                        _("This email is already registered for this briefing session.")
                    )
            if vals.get("source") in ("portal", "sp_backend") and not vals.get("proof_token"):
                vals["proof_token"] = secrets.token_urlsafe(32)
        records = super().create(vals_list)
        records.filtered(
            lambda r: r.source in ("portal", "sp_backend") and not r.proof_token
        )._ensure_proof_token()
        records._send_briefing_start_notification_if_late()
        return records

    def _send_briefing_start_notification_if_late(self):
        """Notify briefing registrants during the live session (e.g. virtual join link)."""
        for att in self:
            rfq = att.rfq_id
            if not rfq.briefing_session or rfq.state != "published":
                continue
            if rfq.portal_briefing_registration_state() != "open":
                continue
            if not rfq.briefing_start_mail_sent:
                rfq._send_briefing_start_emails()
            if not rfq._briefing_start_prerequisites_ok():
                continue
            name = att.company_name or att.contact_name or att.contact_email
            rfq._send_briefing_start_email_to(att.contact_email, name)

    @api.model
    def portal_register(self, rfq, values):
        """Create attendance from public portal during the live session window."""
        return self.self_register(rfq, values, source="portal")

    @api.model
    def self_register(self, rfq, values, source="portal"):
        """Create attendance during the live session window (portal or backend SP)."""
        rfq.ensure_one()
        state = rfq.portal_briefing_registration_state()
        if state == "before":
            raise ValidationError(
                _("Registration opens when the briefing session starts (%s).")
                % format_datetime(self.env, rfq.briefing_at)
            )
        if state == "after":
            raise ValidationError(
                _("The briefing registration window has closed (session ended %s).")
                % format_datetime(self.env, rfq.briefing_end_at)
            )
        if state != "open":
            raise ValidationError(_("Briefing registration is not open for this RFQ/RFP."))

        email = (values.get("contact_email") or "").strip()
        if not email:
            raise ValidationError(_("Contact email is required."))
        company = (values.get("company_name") or "").strip()
        if not company:
            raise ValidationError(_("Company name is required."))
        if source not in ("portal", "sp_backend"):
            source = "portal"

        existing = self.sudo().search([
            ("rfq_id", "=", rfq.id),
            ("email_norm", "=", email.lower()),
        ], limit=1)
        if existing:
            if not existing.proof_token:
                existing._ensure_proof_token()
            return existing

        partner = self.env["res.partner"].sudo().search(
            [("email", "=ilike", email)], limit=1
        )
        vals = {
            "rfq_id": rfq.id,
            "partner_id": partner.id if partner else False,
            "company_name": company,
            "contact_name": (values.get("contact_name") or "").strip(),
            "contact_email": email,
            "contact_phone": (values.get("contact_phone") or "").strip(),
            "mode": rfq.briefing_mode or "virtual",
            "source": source,
        }
        if source == "sp_backend":
            vals["registered_by"] = self.env.user.id
        return self.sudo().create(vals)
