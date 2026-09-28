# -*- coding: utf-8 -*-

from odoo import api, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    @api.model
    def eol_find_by_work_email(self, email):
        """Return a single active employee matching normalized work email, or empty recordset."""
        normalized = (email or '').strip().lower()
        if not normalized:
            return self.browse()
        candidates = self.search([
            ('active', '=', True),
            ('work_email', '!=', False),
        ])
        matched = candidates.filtered(
            lambda e: (e.work_email or '').strip().lower() == normalized
        )
        if len(matched) == 1:
            return matched
        return self.browse()
