from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class EwRfqBriefingNotify(models.Model):
    _name = "ew.rfq.briefing.notify"
    _description = "Briefing session email notification (pre-start signup)"
    _order = "subscribed_at desc, id desc"

    rfq_id = fields.Many2one(
        "ew.rfq",
        string="RFQ / RFP",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_name = fields.Char(required=True)
    contact_name = fields.Char()
    contact_email = fields.Char(string="Contact email", required=True)
    email_norm = fields.Char(
        compute="_compute_email_norm",
        store=True,
        index=True,
    )
    subscribed_at = fields.Datetime(
        default=lambda self: fields.Datetime.now(),
        required=True,
    )

    _uniq_rfq_briefing_notify_email = models.Constraint(
        "unique(rfq_id, email_norm)",
        "This email is already registered for briefing notifications on this RFQ.",
    )

    @api.depends("contact_email")
    def _compute_email_norm(self):
        for rec in self:
            rec.email_norm = (rec.contact_email or "").strip().lower()

    @api.model
    def portal_subscribe(self, rfq, values):
        """Register an email before the briefing starts (virtual join link at start time)."""
        rfq.ensure_one()
        if not rfq.briefing_session or rfq.state != "published":
            raise ValidationError(_("Briefing notifications are not available for this RFQ/RFP."))
        if rfq.portal_briefing_registration_state() != "before":
            raise ValidationError(_("Briefing notification signup is only available before the session starts."))

        email = (values.get("contact_email") or "").strip()
        if not email:
            raise ValidationError(_("Contact email is required."))
        company = (values.get("company_name") or "").strip()
        if not company:
            raise ValidationError(_("Company name is required."))

        existing = self.sudo().search([
            ("rfq_id", "=", rfq.id),
            ("email_norm", "=", email.lower()),
        ], limit=1)
        if existing:
            existing.write({
                "company_name": company,
                "contact_name": (values.get("contact_name") or "").strip(),
            })
            return existing

        return self.sudo().create({
            "rfq_id": rfq.id,
            "company_name": company,
            "contact_name": (values.get("contact_name") or "").strip(),
            "contact_email": email,
        })
