from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools.misc import format_datetime


class EwRfqBriefingRegisterWizard(models.TransientModel):
    _name = "ew.rfq.briefing.register.wizard"
    _description = "Briefing session (service provider)"

    rfq_id = fields.Many2one("ew.rfq", string="RFQ / RFP", required=True, readonly=True)
    rfq_name = fields.Char(related="rfq_id.name", readonly=True)
    rfq_reference = fields.Char(related="rfq_id.reference", readonly=True)
    briefing_mode = fields.Selection(related="rfq_id.briefing_mode", readonly=True)
    briefing_compulsory = fields.Boolean(related="rfq_id.briefing_compulsory", readonly=True)
    briefing_at = fields.Datetime(related="rfq_id.briefing_at", readonly=True)
    briefing_end_at = fields.Datetime(related="rfq_id.briefing_end_at", readonly=True)
    briefing_virtual_link = fields.Char(compute="_compute_session_flags")
    briefing_location = fields.Text(compute="_compute_session_flags")

    registration_state = fields.Selection(
        [
            ("open", "Live"),
            ("before", "Upcoming"),
            ("after", "Ended"),
            ("unavailable", "Unavailable"),
            ("unconfigured", "Not configured"),
        ],
        compute="_compute_session_flags",
    )
    join_visible = fields.Boolean(compute="_compute_session_flags")
    already_registered = fields.Boolean(compute="_compute_already_registered")
    can_register = fields.Boolean(compute="_compute_can_register")
    status_note = fields.Char(compute="_compute_status_note")

    company_name = fields.Char(required=True)
    contact_name = fields.Char()
    contact_email = fields.Char(required=True)
    contact_phone = fields.Char()

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        user = self.env.user
        partner = user.partner_id.commercial_partner_id or user.partner_id
        res.setdefault("company_name", partner.name or "")
        res.setdefault("contact_name", user.name or partner.name or "")
        res.setdefault("contact_email", (user.email or partner.email or "").strip())
        res.setdefault("contact_phone", partner.phone or "")
        return res

    @api.depends(
        "rfq_id",
        "rfq_id.briefing_session",
        "rfq_id.briefing_mode",
        "rfq_id.briefing_at",
        "rfq_id.briefing_end_at",
        "rfq_id.briefing_virtual_link",
        "rfq_id.briefing_location",
        "rfq_id.state",
    )
    def _compute_session_flags(self):
        for wiz in self:
            rfq = wiz.rfq_id
            if not rfq:
                wiz.registration_state = "unavailable"
                wiz.join_visible = False
                wiz.briefing_virtual_link = False
                wiz.briefing_location = False
                continue
            wiz.registration_state = rfq.portal_briefing_registration_state()
            show = rfq.portal_show_briefing_join_details()
            wiz.join_visible = show
            wiz.briefing_virtual_link = (
                rfq.briefing_virtual_link if show and rfq.briefing_mode == "virtual" else False
            )
            wiz.briefing_location = (
                rfq.briefing_location if show and rfq.briefing_mode == "contact" else False
            )

    @api.depends("rfq_id", "contact_email")
    def _compute_already_registered(self):
        Attendance = self.env["ew.rfq.briefing.attendance"].sudo()
        for wiz in self:
            email = (wiz.contact_email or "").strip().lower()
            if not wiz.rfq_id or not email:
                wiz.already_registered = False
                continue
            wiz.already_registered = bool(Attendance.search_count([
                ("rfq_id", "=", wiz.rfq_id.id),
                ("email_norm", "=", email),
            ]))

    @api.depends("join_visible", "already_registered", "registration_state")
    def _compute_can_register(self):
        for wiz in self:
            wiz.can_register = (
                wiz.registration_state == "open"
                and wiz.join_visible
                and not wiz.already_registered
            )

    @api.depends("registration_state", "already_registered", "join_visible",
                 "briefing_mode", "briefing_at", "briefing_end_at")
    def _compute_status_note(self):
        for wiz in self:
            if wiz.already_registered:
                wiz.status_note = _("Your attendance is on record.")
            elif wiz.registration_state == "before":
                wiz.status_note = _(
                    "The join link, venue and attendance register appear when the briefing starts (%s)."
                ) % format_datetime(self.env, wiz.briefing_at)
            elif wiz.registration_state == "after":
                wiz.status_note = _(
                    "This briefing session has ended. The join link, venue and attendance register are closed."
                )
            elif wiz.registration_state == "unconfigured":
                wiz.status_note = _(
                    "This briefing session is not fully configured yet. Contact EWSETA SCM."
                )
            elif wiz.registration_state == "unavailable":
                wiz.status_note = _("Briefing registration is not available for this RFQ/RFP.")
            elif wiz.briefing_mode == "virtual":
                wiz.status_note = _(
                    "Sign the attendance register while the session is live. Use the same email as your application if you have already submitted."
                )
            else:
                wiz.status_note = _(
                    "Sign the attendance register while the session is live."
                )

    def action_open_virtual_briefing(self):
        self.ensure_one()
        if not self.join_visible or self.briefing_mode != "virtual":
            raise UserError(
                _("The virtual briefing link is available when the session is live.")
            )
        link = (self.briefing_virtual_link or "").strip()
        if not link:
            raise UserError(_("No virtual briefing link has been set for this session."))
        return {
            "type": "ir.actions.act_url",
            "url": link,
            "target": "new",
        }

    def action_register(self):
        self.ensure_one()
        rfq = self.rfq_id
        if not rfq:
            raise UserError(_("No RFQ/RFP on this form."))
        if self.registration_state == "before":
            raise UserError(
                _("Registration opens when the briefing starts (%s).")
                % format_datetime(self.env, rfq.briefing_at)
            )
        if self.registration_state == "after":
            raise UserError(
                _("The briefing session has ended (%s).")
                % format_datetime(self.env, rfq.briefing_end_at)
            )
        if self.registration_state != "open":
            raise UserError(_("Briefing registration is not available for this RFQ/RFP."))
        rfq._portal_trigger_briefing_start_emails_if_due()
        self.env["ew.rfq.briefing.attendance"].self_register(
            rfq,
            {
                "company_name": self.company_name,
                "contact_name": self.contact_name,
                "contact_email": self.contact_email,
                "contact_phone": self.contact_phone,
            },
            source="sp_backend",
        )
        self.invalidate_recordset(["already_registered", "can_register", "status_note"])
        return {
            "type": "ir.actions.act_window",
            "name": _("Briefing session"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": self.env.context,
        }
