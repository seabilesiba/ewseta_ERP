# -*- coding: utf-8 -*-

from odoo import models


class Website(models.Model):
    _inherit = 'website'

    def ewseta_nav_menu_ids(self):
        self.ensure_one()
        return self.menu_id.child_id.filtered('is_published')
