# -*- coding: utf-8 -*-

from odoo import api, models


class ReportItIncidentDocument(models.AbstractModel):
    _name = 'report.it_asset_management.report_it_incident_document'
    _description = 'IT Incident Report PDF'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['it.asset.incident.report'].browse(docids)
        company = docs.company_id[:1] if docs else self.env.company
        return {
            'doc_ids': docids,
            'doc_model': 'it.asset.incident.report',
            'docs': docs,
            'company': company,
        }
