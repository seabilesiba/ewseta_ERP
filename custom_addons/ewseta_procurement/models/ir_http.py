from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    def session_info(self):
        info = super().session_info()
        user = self.env.user
        info["ew_procurement_only_apps"] = bool(
            user._is_internal()
            and user._ew_is_procurement_app_restricted_user()
        )
        return info
