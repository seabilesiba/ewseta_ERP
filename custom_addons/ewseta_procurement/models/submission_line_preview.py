import mimetypes
from urllib.parse import quote

from markupsafe import escape

from odoo import api, fields, models, _


class EwSubmissionLinePreview(models.TransientModel):
    _name = "ew.submission.line.preview"
    _description = "Submission document preview"

    line_id = fields.Many2one("ew.submission.line", required=True, ondelete="cascade")
    file_name = fields.Char(readonly=True)
    preview_html = fields.Html(compute="_compute_preview_html", sanitize=False, readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        line_id = self.env.context.get("default_line_id")
        active_model = self.env.context.get("active_model")
        active_id = self.env.context.get("active_id")
        if not line_id and active_model == "ew.submission.line" and active_id:
            line_id = active_id
        if line_id and "line_id" in fields_list:
            res["line_id"] = line_id
        return res

    @api.depends("line_id", "line_id.file", "line_id.file_filename")
    def _compute_preview_html(self):
        image_mimetypes = {
            "image/bmp",
            "image/gif",
            "image/jpeg",
            "image/png",
            "image/svg+xml",
            "image/webp",
        }
        for wizard in self:
            line = wizard.line_id
            wizard.file_name = line.file_filename or line.requirement_name or _("Document")
            if not line or not line.file:
                wizard.preview_html = "<p class='text-muted'>%s</p>" % escape(_("No file uploaded yet."))
                continue

            filename = line.file_filename or "document"
            content_url = (
                f"/web/content/ew.submission.line/{line.id}/file/"
                f"{quote(filename)}?download=0"
            )
            download_url = content_url.replace("download=0", "download=1")
            mimetype, _ = mimetypes.guess_type(filename)
            mimetype = mimetype or "application/octet-stream"
            safe_title = escape(wizard.file_name)

            if mimetype == "application/pdf" or filename.lower().endswith(".pdf"):
                viewer_url = (
                    "/web/static/lib/pdfjs/web/viewer.html?file="
                    f"{quote(content_url, safe='')}#pagemode=none"
                )
                wizard.preview_html = (
                    f'<iframe src="{viewer_url}" '
                    f'style="width:100%;min-height:75vh;border:none;" '
                    f'title="{safe_title}"></iframe>'
                )
            elif mimetype in image_mimetypes:
                wizard.preview_html = (
                    f'<img src="{content_url}" alt="{safe_title}" '
                    f'style="max-width:100%;height:auto;display:block;margin:0 auto;"/>'
                )
            else:
                wizard.preview_html = (
                    "<p class='text-muted'>%s</p>"
                    "<p><a href='%s' target='_blank' rel='noopener'>%s</a></p>"
                    % (
                        escape(_("Preview is not available for this file type.")),
                        download_url,
                        escape(_("Download file")),
                    )
                )
