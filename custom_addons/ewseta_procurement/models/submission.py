from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError, AccessError
from werkzeug.urls import url_quote


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
    submitted_at = fields.Datetime(default=lambda self: fields.Datetime.now(), readonly=True)
    line_ids = fields.One2many("ew.submission.line", "submission_id", string="Documents", ondelete='cascade')
    closing_at = fields.Datetime("Closing Date & Time", related="rfq_id.closing_at", tracking=True, )
    rfq_state = fields.Selection([("draft","Draft"),("published", "Published"),("closed", "Closed")], related="rfq_id.state", default="draft", tracking=True, store=True)
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
    # ---------- HARDENED SEEDING ----------
    def _seed_lines_from_rfq(self):
        """Ensure this submission has one line per RFQ requirement.
        Also self-heals RFQs missing default requirements."""
        for sub in self:
            rfq = sub.rfq_id.sudo()
            # If RFQ somehow has no requirements, prefill them now (self-heal)
            if not rfq.requirement_ids:
                if hasattr(rfq, "_prefill_requirements"):
                    rfq._prefill_requirements()
                elif hasattr(rfq, "_default_requirements_commands"):
                    rfq.write({"requirement_ids": rfq._default_requirements_commands()})
            if not sub.line_ids and rfq.requirement_ids:
                sub.write({
                    "line_ids": [(0, 0, {"requirement_id": r.id}) for r in rfq.requirement_ids]
                })

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

        return records

    # Keep your existing onchange for UI niceness (not relied upon)
    @api.onchange("rfq_id")
    def _onchange_rfq_id_seed_lines(self):
        if self.rfq_id and not self.line_ids:
            self.line_ids = [(0, 0, {"requirement_id": r.id}) for r in self.rfq_id.requirement_ids]

    def action_submit(self):
        """If a button submits from draft → submitted; close immediately if past deadline."""
        now = fields.Datetime.now()
        for rec in self:
            if rec.state == "draft":
                rec.state = "submitted"
            # close instantly if RFQ deadline reached
            if rec.rfq_id.closing_at and rec.rfq_id.closing_at <= now:
                rec.state = "closed"
                rec.rfq_id._auto_close_if_due()

        template = self.env.ref(
            "ewseta_procurement.mail_tmpl_submission_sender",
            raise_if_not_found=False,
        )
        if template:
            for rec in self:
                template.send_mail(rec.id)

    def send_mail(self):
        template = self.env.ref("ewseta_procurement.mail_tmpl_submission_receipt")
        for rec in self:
            template.send_mail(rec.id)



    @api.model
    def cron_close_submissions_past_deadline(self):
        """Safety cron: close submissions when RFQ deadline has passed."""
        now = fields.Datetime.now()
        subs = self.search([("state", "!=", "closed"), ("rfq_id.closing_at", "<=", now)])
        subs.write({"state": "closed"})


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
    # NEW: reflect mandatory from the requirement
    is_mandatory = fields.Boolean(
        string="Mandatory",
        related="requirement_id.is_mandatory",
        store=False,  # set to True if you want to search/group by it
        readonly=True,
        tracking=True

    )
    file = fields.Binary("File", attachment=True, tracking=True)
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



    @api.depends("requirement_id")
    def _compute_name(self):
        for rec in self:
            rec.name = rec.requirement_id.name or ""

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

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("requirement_id") and vals.get("submission_id"):
                sub = self.env["ew.submission"].browse(vals["submission_id"])
                if sub and sub.rfq_id:
                    used_req_ids = set(sub.line_ids.mapped("requirement_id").ids)
                    missing_req = (
                        sub.rfq_id.requirement_ids
                        - sub.rfq_id.requirement_ids.browse(list(used_req_ids))
                    )[:1]
                    if missing_req:
                        vals["requirement_id"] = missing_req.id
                    else:
                        raise ValidationError(
                            _("All RFQ requirements already have lines; cannot create extra lines.")
                        )
                else:
                    raise ValidationError(
                        _("Cannot create a document line without a requirement on this submission.")
                    )

        records = super().create(vals_list)
        for rec in records:
            rec._sync_attachment()
        return records


    def action_preview_file(self):
        self.ensure_one()
        if not self.file:
            raise UserError(_("No file uploaded yet."))
        filename = url_quote(self.file_filename or "document")
        url = f"/web/content/ew.submission.line/{self.id}/file/{filename}?download=0"
        return {"type": "ir.actions.act_url", "url": url, "target": "new"}

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
