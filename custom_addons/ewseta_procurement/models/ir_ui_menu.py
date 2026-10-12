from odoo import api, models, tools





class IrUiMenu(models.Model):

    _inherit = "ir.ui.menu"



    def _ew_allowed_menu_ids(self):

        """Menus visible under procurement app restriction, or None if unrestricted."""

        user = self.env.user

        if not user._ew_is_procurement_app_restricted_user():

            return None

        roots = user._ew_allowed_application_root_menu_ids()

        if not roots:

            return frozenset()

        return frozenset(self.search([("id", "child_of", roots.ids)]).ids)



    @api.model

    @tools.ormcache("frozenset(self.env.user._get_group_ids())", "debug")

    def _visible_menu_ids(self, debug=False):

        visible = super()._visible_menu_ids(debug=debug)

        allowed = self._ew_allowed_menu_ids()

        if allowed is None:

            return visible

        return visible & allowed



    def _load_menus_blacklist(self):

        blacklist = list(super()._load_menus_blacklist())

        allowed = self._ew_allowed_menu_ids()

        if allowed is None:

            return blacklist

        allowed_roots = self.env.user._ew_allowed_application_root_menu_ids()

        for root in self.search([("parent_id", "=", False)]):

            if root in allowed_roots:

                continue

            blacklist.extend(self.search([("id", "child_of", root.id)]).ids)

        return blacklist



    @api.model

    def load_menus_root(self):

        root = super().load_menus_root()

        allowed_roots = self.env.user._ew_allowed_application_root_menu_ids()

        if (

            not self.env.user._ew_is_procurement_app_restricted_user()

            or not allowed_roots

        ):

            return root

        allowed_ids = set(allowed_roots.ids)

        root["children"] = [m for m in root["children"] if m["id"] in allowed_ids]

        root["all_menu_ids"] = list(allowed_ids)

        return root



    @api.model

    def get_user_roots(self):

        roots = super().get_user_roots()

        allowed_roots = self.env.user._ew_allowed_application_root_menu_ids()

        if (

            not self.env.user._ew_is_procurement_app_restricted_user()

            or not allowed_roots

        ):

            return roots

        return roots.filtered(lambda menu: menu in allowed_roots)



    @api.model

    def _ew_refresh_menu_visibility_cache(self):

        """Upgrade hook: drop cached menus so app restrictions apply immediately."""

        self.env.registry.clear_cache()

