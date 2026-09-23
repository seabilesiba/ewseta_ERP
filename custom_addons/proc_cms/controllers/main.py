from odoo import http
from odoo.http import request
from odoo.addons.website.controllers.main import Website


class ProcCmsWebsite(Website):

    @http.route(
        [
            "/proc/page/<string:slug>",
            "/proc/page/<string:slug>/",
        ],
        type="http",
        auth="public",
        website=True,
        sitemap=True,
    )
    def proc_cms_page(self, slug, **kwargs):
        slug = (slug or "").strip().strip("/")
        page = (
            request.env["proc.cms.page"]
            .sudo()
            .search(
                [
                    ("website_id", "=", request.website.id),
                    ("slug", "=", slug),
                    ("active", "=", True),
                    ("is_published", "=", True),
                ],
                limit=1,
            )
        )
        if not page:
            return request.not_found()
        values = {
            "cms_page": page,
            "main_object": page,
        }
        return request.render("proc_cms.proc_cms_page_layout", values)
