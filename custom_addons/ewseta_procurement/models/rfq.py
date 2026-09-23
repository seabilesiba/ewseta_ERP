# models/rfq.py
from odoo import api, fields, models, _
from odoo.exceptions import UserError

class EwRfq(models.Model):
    _name = "ew.rfq"
    _description = "EWSETA RFQ/RFP"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char("Title", required=True, tracking=True)
    reference = fields.Char("Reference", required=True, default='New', tracking=True)
    type = fields.Selection([("rfq", "RFQ"), ("rfp", "RFP")], default="rfq", required=True)
    description = fields.Html()
    rfq_document = fields.Binary(string="RFQ Document", tracking=True)
    requirement_ids = fields.One2many("ew.rfq.requirement", "rfq_id", string="Required Documents")
    closing_at = fields.Datetime("Closing Date & Time", required=True, tracking=True)
    unlocked = fields.Boolean("Unlocked", default=False)
    state = fields.Selection([("draft","Draft"),("published", "Published"),("closed", "Closed")], default="draft", tracking=True)
    supplier_note = fields.Text("Supplier Instructions")
    submission_ids = fields.One2many("ew.submission", "rfq_id", string="Submissions", ondelete="cascade")
    opening_at = fields.Datetime(string="Created On", default=fields.Datetime.now, store=True)

    @api.model
    def default_get(self, fields_list):
        vals = super().default_get(fields_list)
        if "requirement_ids" in fields_list and not vals.get("requirement_ids"):
            vals["requirement_ids"] = self._default_requirements_commands()
        return vals

    def _default_requirements_commands(self):
        DEFAULT_REQS = [
            (1, "CSD Report", True),
            (2, "Tax Clearance", True),
            (3, "BBBBEE Affidavit/Certificate", False),
            (4, "CIPC Registration documents", True),
            (5, "JV Agreement", True),
            (6, "SBD 4", True),
            (7, "SBD 3.1", True),
            (8, "SBD 1", True),
            (9, "SBD 3.3", True),
            (10, "SBD 6.1", True),
            (11, "POPIA Consent Form", True),
            (12, "General Conditions of Purchase/Contract", True),
        ]
        return [(0, 0, {
            "sequence": s,
            "name": n,
            "is_mandatory": m,
            "section": "mandatory" if m else "optional",
        }) for s, n, m in DEFAULT_REQS]
    def _prefill_requirements(self):
        self.ensure_one()
        if not self.requirement_ids:
            self.write({"requirement_ids": self._default_requirements_commands()})
    #
    def action_publish(self):
        for rec in self:
            if not rec.rfq_document:
                raise UserError(_("Please upload the RFQ document before publishing."))
            rec._prefill_requirements()
            rec.state = "published"
            rec.message_post(body=_("RFQ published."), subtype_xmlid="mail.mt_note")
            rec._auto_close_if_due()


    def action_close(self):
        self.write({"state": "closed", "unlocked": True})
        for rec in self:
            rec.submission_ids.filtered(lambda s: s.state != "closed").write({"state": "closed"})
            rec.message_post(body=_("RFQ manually closed and unlocked."), subtype_xmlid="mail.mt_note")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("reference", "New") == "New":
                vals["reference"] = (
                    self.env["ir.sequence"].next_by_code("ew.rfq") or "New"
                )

        records = super().create(vals_list)
        for rec in records:
            rec._prefill_requirements()
            rec._auto_close_if_due()
        return records

    def write(self, vals):
        res = super().write(vals)
        # If closing_at/state changed, re-evaluate immediately
        if any(k in vals for k in ("closing_at", "state", "unlocked")):
            self._auto_close_if_due()
        return res

    def _auto_close_if_due(self):
        """Close RFQ (and linked submissions) immediately if deadline already passed."""
        now = fields.Datetime.now()
        for rfq in self:
            if rfq.state == "published" and rfq.closing_at and rfq.closing_at <= now and not rfq.unlocked:
                rfq.with_context(mail_post_autofollow=True).write({"unlocked": True, "state": "closed"})
                rfq.submission_ids.filtered(lambda s: s.state != "closed").write({"state": "closed"})
                rfq.message_post(
                    body=_("RFQ <b>%s</b> has closed (deadline reached). Submissions are now visible.") % (rfq.name,),
                    subtype_xmlid="mail.mt_comment",
                )

    # Safety net: cron still runs (keep just ONE definition)
    @api.model
    def cron_unlock_due_rfqs(self):
        now = fields.Datetime.now()
        rfqs = self.search([("state", "=", "published"), ("closing_at", "<=", now), ("unlocked", "=", False)])
        for rfq in rfqs:
            rfq._auto_close_if_due()

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

    @api.depends("submission_ids", "state")
    def _compute_submission_count(self):
        """Count submissions; hide from SCM UI until RFQ/RFP is closed."""
        Sub = self.env["ew.submission"].sudo()
        scm_ui = bool(self.env.context.get("ewseta_procurement_scm_ui"))
        for rfq in self:
            count = Sub.search_count([("rfq_id", "=", rfq.id)]) if rfq.id else 0
            if scm_ui and rfq.state != "closed":
                rfq.submission_count = 0
            else:
                rfq.submission_count = count

    @api.depends("state", "submission_ids")
    def _compute_scm_submission_stats(self):
        """SCM views: only expose submission counts once RFQ/RFP is closed."""
        scm_ui = bool(self.env.context.get("ewseta_procurement_scm_ui"))
        for rfq in self:
            show = scm_ui and rfq.state == "closed"
            rfq.scm_show_submission_stats = show
            if show:
                count = len(rfq.submission_ids)
                rfq.scm_submission_count = count
                rfq.scm_submissions_display = str(count) if count else ""
            else:
                rfq.scm_submission_count = 0
                rfq.scm_submissions_display = ""

    def action_open_submissions(self):
        self.ensure_one()
        user = self.env.user
        scm_ui = bool(self.env.context.get("ewseta_procurement_scm_ui"))
        is_admin = user.has_group("ewseta_procurement.group_rfq_admin")
        is_scm = user.has_group("ewseta_procurement.group_scm_owner")
        if (scm_ui or (is_scm and not is_admin)) and self.state != "closed":
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
    is_mandatory = fields.Boolean(string="Mandatory", default=True)
    section = fields.Selection(
        [("mandatory", "Mandatory"), ("optional", "Not Mandatory")],
        default="mandatory", required=True, tracking=True
    )
    help_text = fields.Char("Help")

