from odoo import api, fields, models


class ProcCmsWebsiteContentMixin(models.AbstractModel):
    _name = "proc.cms.website.content.mixin"
    _description = "CMS rows linked to a site record for inline editing"

    cms_site_id = fields.Many2one(
        "proc.cms.site",
        string="CMS site",
        ondelete="cascade",
        index=True,
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        site_id = self.env.context.get("default_cms_site_id")
        if site_id and not res.get("website_id"):
            site = self.env["proc.cms.site"].browse(site_id)
            if site.website_id:
                res["website_id"] = site.website_id.id
        if site_id and not res.get("cms_site_id"):
            res["cms_site_id"] = site_id
        return res

    @api.model_create_multi
    def create(self, vals_list):
        Site = self.env["proc.cms.site"]
        for vals in vals_list:
            if vals.get("cms_site_id") and not vals.get("website_id"):
                site = Site.browse(vals["cms_site_id"])
                vals["website_id"] = site.website_id.id
            elif vals.get("website_id") and not vals.get("cms_site_id"):
                site = Site.search([("website_id", "=", vals["website_id"])], limit=1)
                if site:
                    vals["cms_site_id"] = site.id
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("website_id") and "cms_site_id" not in vals:
            site = self.env["proc.cms.site"].search(
                [("website_id", "=", vals["website_id"])], limit=1
            )
            if site:
                vals["cms_site_id"] = site.id
        return super().write(vals)
