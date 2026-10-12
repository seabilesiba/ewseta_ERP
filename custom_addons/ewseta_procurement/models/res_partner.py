from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    ew_service_provider = fields.Boolean(
        string="EWSETA service provider",
        help="Registered service provider profile used for transversal RFQ matching.",
    )
    ew_service_category_ids = fields.Many2many(
        "ew.service.category",
        "res_partner_ew_service_category_rel",
        "partner_id",
        "category_id",
        string="Service categories",
        help="Used to match transversal RFQs/RFPs when EWSETA selects the same categories.",
    )
    ew_province_ids = fields.Many2many(
        "res.country.state",
        "res_partner_ew_province_rel",
        "partner_id",
        "state_id",
        string="Provinces of operation",
        domain="[('country_id.code', '=', 'ZA')]",
        help="Used with service categories to determine transversal RFQ/RFP invitations.",
    )

    def _ew_procurement_provider_active(self):
        """True when this partner is an active registered service provider."""
        self.ensure_one()
        if not self.ew_service_provider or not self.active:
            return False
        group = self.env.ref(
            "ewseta_procurement.group_service_provider",
            raise_if_not_found=False,
        )
        if not group:
            return False
        users = self.env["res.users"].sudo().search([
            ("partner_id", "=", self.id),
            ("active", "=", True),
        ])
        return any(group in u.group_ids for u in users)

    def _ew_sync_linked_users_procurement_access(self):
        users = self.env["res.users"].sudo().search([
            ("partner_id", "in", self.ids),
            ("active", "=", True),
            ("share", "=", False),
        ])
        users._ew_sync_procurement_access()

    @api.model_create_multi
    def create(self, vals_list):
        partners = super().create(vals_list)
        if any(v.get("ew_service_provider") for v in vals_list):
            partners.filtered("ew_service_provider")._ew_sync_linked_users_procurement_access()
        return partners

    @api.constrains(
        "ew_service_provider",
        "ew_service_category_ids",
        "ew_province_ids",
    )
    def _check_ew_service_provider_profile(self):
        for partner in self:
            if not partner.ew_service_provider:
                continue
            if not partner.ew_service_category_ids:
                raise ValidationError(
                    _(
                        "Registered service provider “%(name)s” needs at least one "
                        "service category so transversal RFQs/RFPs can target them."
                    )
                    % {"name": partner.display_name}
                )
            if not partner.ew_province_ids:
                raise ValidationError(
                    _(
                        "Registered service provider “%(name)s” needs at least one "
                        "province of operation for transversal matching."
                    )
                    % {"name": partner.display_name}
                )

    def write(self, vals):
        res = super().write(vals)
        if "ew_service_provider" in vals:
            self._ew_sync_linked_users_procurement_access()
        return res
