from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestTransversalPublication(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Rfq = cls.env["ew.rfq"]
        cls.Partner = cls.env["res.partner"]
        cls.Category = cls.env["ew.service.category"]
        cls.State = cls.env["res.country.state"]
        cls.za = cls.env.ref("base.za")
        cls.cat_energy = cls.env.ref("ewseta_procurement.service_category_energy")
        cls.cat_water = cls.env.ref("ewseta_procurement.service_category_water")
        cls.province = cls.State.search(
            [("country_id", "=", cls.za.id)], limit=1
        )
        if not cls.province:
            cls.province = cls.State.create({
                "name": "Gauteng",
                "code": "GP",
                "country_id": cls.za.id,
            })
        cls.sp_group = cls.env.ref("ewseta_procurement.group_service_provider")
        cls.provider_partner = cls.Partner.create({
            "name": "Transversal Provider Co",
            "email": "transversal.provider@example.com",
            "ew_service_provider": True,
            "ew_service_category_ids": [(6, 0, cls.cat_energy.ids)],
            "ew_province_ids": [(6, 0, cls.province.ids)],
        })
        cls.provider_user = cls.env["res.users"].create({
            "name": "Transversal Provider User",
            "login": "transversal_provider_test",
            "email": "transversal.provider@example.com",
            "partner_id": cls.provider_partner.id,
            "group_ids": [(6, 0, [cls.sp_group.id, cls.env.ref("base.group_user").id])],
        })
        cls.other_partner = cls.Partner.create({
            "name": "Other Provider",
            "email": "other.provider@example.com",
            "ew_service_provider": True,
            "ew_service_category_ids": [(6, 0, cls.cat_water.ids)],
            "ew_province_ids": [(6, 0, cls.province.ids)],
        })
        cls.closing = fields.Datetime.now() + timedelta(days=14)

    def _draft_rfq_vals(self, publication_type="transversal"):
        vals = {
            "name": "Test opportunity",
            "type": "rfq",
            "publication_type": publication_type,
            "closing_at": self.closing,
            "rfq_document": b"dGVzdA==",
            "rfq_document_filename": "test.pdf",
        }
        if publication_type == "transversal":
            vals.update({
                "service_category_id": self.cat_energy.id,
                "province_ids": [(6, 0, self.province.ids)],
            })
        return vals

    def test_eligible_provider_matching(self):
        rfq = self.Rfq.create(self._draft_rfq_vals())
        eligible = rfq._find_eligible_service_providers()
        self.assertIn(self.provider_partner, eligible)
        self.assertNotIn(self.other_partner, eligible)

    def test_rfq_service_must_be_on_provider_profile(self):
        ict = self.env.ref("ewseta_procurement.service_category_ict")
        self.provider_partner.write({
            "ew_service_category_ids": [(6, 0, ict.ids)],
        })
        rfq = self.Rfq.create({
            **self._draft_rfq_vals(publication_type="transversal"),
            "service_category_id": self.cat_water.id,
            "province_ids": [(5, 0, 0)],
        })
        eligible = rfq._find_eligible_service_providers()
        self.assertNotIn(self.provider_partner, eligible)

    def test_unsaved_rfq_new_matches_by_category(self):
        ict = self.env.ref("ewseta_procurement.service_category_ict")
        self.provider_partner.write({
            "ew_service_category_ids": [(6, 0, ict.ids)],
        })
        rfq = self.Rfq.new({
            "publication_type": "transversal",
            "service_category_id": ict.id,
        })
        self.assertEqual(rfq._transversal_service_category_id(), ict.id)
        self.assertIn(self.provider_partner, rfq._find_eligible_service_providers())

    def test_eligible_by_service_category_without_rfq_provinces(self):
        vals = self._draft_rfq_vals()
        vals["province_ids"] = [(5, 0, 0)]
        rfq = self.Rfq.create(vals)
        eligible = rfq._find_eligible_service_providers()
        self.assertIn(self.provider_partner, eligible)
        self.assertNotIn(self.other_partner, eligible)

    def test_province_includes_provider_with_matching_province(self):
        ict = self.env.ref("ewseta_procurement.service_category_ict")
        self.provider_partner.write({
            "ew_service_category_ids": [(6, 0, ict.ids)],
        })
        rfq = self.Rfq.create({
            **self._draft_rfq_vals(publication_type="transversal"),
            "service_category_id": ict.id,
            "province_ids": [(6, 0, self.province.ids)],
        })
        eligible = rfq._find_eligible_service_providers()
        self.assertIn(self.provider_partner, eligible)

    def test_province_excludes_provider_without_that_province(self):
        other_province = self.State.search([
            ("country_id", "=", self.za.id),
            ("id", "!=", self.province.id),
        ], limit=1)
        if not other_province:
            other_province = self.State.create({
                "name": "Western Cape",
                "code": "WC",
                "country_id": self.za.id,
            })
        rfq = self.Rfq.create({
            **self._draft_rfq_vals(),
            "province_ids": [(6, 0, other_province.ids)],
        })
        eligible = rfq._find_eligible_service_providers()
        self.assertNotIn(self.provider_partner, eligible)

    def test_province_narrows_when_sp_has_selected_province(self):
        other_province = self.State.search([
            ("country_id", "=", self.za.id),
            ("id", "!=", self.province.id),
        ], limit=1)
        if not other_province:
            other_province = self.State.create({
                "name": "Western Cape",
                "code": "WC",
                "country_id": self.za.id,
            })
        other_sp = self.Partner.create({
            "name": "WC Energy Provider",
            "email": "wc.energy@example.com",
            "ew_service_provider": True,
            "ew_service_category_ids": [(6, 0, self.cat_energy.ids)],
            "ew_province_ids": [(6, 0, other_province.ids)],
        })
        self.env["res.users"].create({
            "name": "WC Energy User",
            "login": "wc_energy_provider_test",
            "partner_id": other_sp.id,
            "group_ids": [(6, 0, [self.sp_group.id, self.env.ref("base.group_user").id])],
        })
        rfq = self.Rfq.create({
            **self._draft_rfq_vals(),
            "province_ids": [(6, 0, self.province.ids)],
        })
        eligible = rfq._find_eligible_service_providers()
        self.assertIn(self.provider_partner, eligible)
        self.assertNotIn(other_sp, eligible)

    def test_publish_transversal_snapshots_providers(self):
        rfq = self.Rfq.create(self._draft_rfq_vals())
        rfq.action_publish()
        self.assertEqual(rfq.state, "published")
        self.assertIn(self.provider_partner, rfq.transversal_eligible_partner_ids)

    def test_public_list_domain_excludes_transversal(self):
        trans = self.Rfq.create(self._draft_rfq_vals())
        trans.action_publish()
        public = self.Rfq.create(self._draft_rfq_vals(publication_type="public"))
        public.action_publish()
        listed = self.Rfq.search([
            ("state", "=", "published"),
            ("publication_type", "=", "public"),
        ])
        self.assertIn(public, listed)
        self.assertNotIn(trans, listed)

    def test_partner_matches_transversal_after_publish(self):
        rfq = self.Rfq.create(self._draft_rfq_vals())
        rfq.action_publish()
        self.assertTrue(rfq._partner_matches_transversal(self.provider_partner))
        self.assertFalse(rfq._partner_matches_transversal(self.other_partner))

    def test_submission_blocked_for_non_eligible_sp(self):
        rfq = self.Rfq.create(self._draft_rfq_vals())
        rfq.action_publish()
        with self.assertRaises(UserError):
            self.env["ew.submission"].with_user(self.provider_user.id).create({
                "rfq_id": rfq.id,
                "partner_id": self.other_partner.id,
                "company_name": "Wrong Co",
                "contact_email": "wrong@example.com",
                "contact_phone": "000",
                "state": "submitted",
            })

    def test_submission_allowed_for_eligible_sp(self):
        rfq = self.Rfq.create(self._draft_rfq_vals())
        rfq.action_publish()
        sub = self.env["ew.submission"].with_user(self.provider_user.id).create({
            "rfq_id": rfq.id,
            "partner_id": self.provider_partner.id,
            "company_name": self.provider_partner.name,
            "contact_email": self.provider_partner.email,
            "contact_phone": "0123456789",
            "state": "draft",
        })
        self.assertEqual(sub.rfq_id, rfq)

    def test_sp_user_does_not_see_public_published_rfq(self):
        public = self.Rfq.create(self._draft_rfq_vals(publication_type="public"))
        public.action_publish()
        trans = self.Rfq.create(self._draft_rfq_vals())
        trans.action_publish()
        visible = self.Rfq.with_user(self.provider_user.id).search([])
        self.assertIn(trans, visible)
        self.assertNotIn(public, visible)

    def test_provider_apply_action_opens_submission(self):
        rfq = self.Rfq.create(self._draft_rfq_vals())
        rfq.action_publish()
        action = (
            self.env["ew.submission"]
            .with_user(self.provider_user.id)
            .with_context(active_id=rfq.id)
            .action_open_provider_application_from_rfq()
        )
        self.assertEqual(action["res_model"], "ew.submission")
        ctx = action.get("context") or {}
        self.assertEqual(ctx.get("default_rfq_id"), rfq.id)

    def test_submission_lines_match_rfq_requirements(self):
        rfq = self.Rfq.create(self._draft_rfq_vals())
        rfq.action_publish()
        reqs = rfq.requirement_ids.sorted(key=lambda r: (r.section, r.sequence, r.id))
        sub = self.env["ew.submission"].create({
            "rfq_id": rfq.id,
            "partner_id": self.provider_partner.id,
            "company_name": "Test Co",
            "contact_name": "Tester",
            "contact_email": "batch-lines@test.example",
            "contact_phone": "0123456789",
        })
        Line = self.env["ew.submission.line"].sudo()
        Line.create([
            {"submission_id": sub.id} for _ in reqs
        ])
        sub._ensure_document_lines()
        self.assertEqual(len(sub.line_ids), len(reqs))
        self.assertEqual(
            sub.line_ids.sorted("id").mapped("requirement_id").ids,
            reqs.ids,
        )
        self.assertEqual(
            sub.line_ids.mapped("requirement_name"),
            reqs.mapped("name"),
        )

    def test_scm_owner_on_sp_partner_keeps_scm_and_cms_groups(self):
        scm = self.env.ref("ewseta_procurement.group_scm_owner")
        cms = self.env.ref("proc_cms.group_proc_cms_manager")
        self.provider_partner.ew_service_provider = True
        user = self.env["res.users"].create({
            "name": "SCM on SP partner",
            "login": "scm_on_sp_partner_test",
            "partner_id": self.provider_partner.id,
            "group_ids": [(6, 0, [scm.id, cms.id, self.env.ref("base.group_user").id])],
        })
        user.write({"group_ids": [(4, scm.id)]})
        user.invalidate_recordset()
        self.assertTrue(user.has_group("ewseta_procurement.group_scm_owner"))
        self.assertTrue(user.has_group("proc_cms.group_proc_cms_manager"))
        self.assertFalse(user.has_group("ewseta_procurement.group_service_provider"))

    def test_service_provider_partner_enforces_sp_and_strips_website(self):
        website = self.env.ref("website.group_website_restricted_editor")
        user = self.env["res.users"].create({
            "name": "SP portal login",
            "login": "sp_portal_access_test",
            "partner_id": self.provider_partner.id,
            "group_ids": [(6, 0, [website.id, self.env.ref("base.group_user").id])],
        })
        user.invalidate_recordset()
        self.assertTrue(user.has_group("ewseta_procurement.group_service_provider"))
        self.assertFalse(user.has_group("website.group_website_restricted_editor"))

    def test_sp_can_save_requirement_lines_on_submit_path(self):
        """SP form save may create one line per RFQ requirement (not blocked as extra rows)."""
        rfq = self.Rfq.create(self._draft_rfq_vals())
        rfq.action_publish()
        Line = self.env["ew.submission.line"].with_user(self.provider_user)
        sub = self.env["ew.submission"].with_user(self.provider_user).create({
            "rfq_id": rfq.id,
            "partner_id": self.provider_partner.id,
            "company_name": "Test Co",
            "contact_name": "Tester",
            "contact_email": "sp-lines@test.example",
            "contact_phone": "0123456789",
            "privacy_policy_accepted": True,
        })
        sub.line_ids.sudo().unlink()
        reqs = rfq.requirement_ids.sorted(key=lambda r: (r.section, r.sequence, r.id))
        Line.create([
            {
                "submission_id": sub.id,
                "requirement_id": req.id,
                "requirement_name": req.name,
            }
            for req in reqs
        ])
        self.assertEqual(len(sub.line_ids), len(reqs))

    def test_briefing_recipients_include_transversal_eligible_providers(self):
        rfq = self.Rfq.create(self._draft_rfq_vals())
        rfq.action_publish()
        recipients = rfq._briefing_start_recipient_map()
        self.assertIn(
            "transversal.provider@example.com",
            recipients,
        )

    def test_transversal_briefing_registration_during_session(self):
        now = fields.Datetime.now()
        rfq = self.Rfq.create({
            **self._draft_rfq_vals(),
            "briefing_session": True,
            "briefing_mode": "virtual",
            "briefing_virtual_link": "https://meet.example.com/briefing",
            "briefing_at": now - timedelta(minutes=2),
            "briefing_end_at": now + timedelta(minutes=13),
        })
        rfq.action_publish()
        self.assertTrue(rfq.portal_briefing_rfq_eligible())
        self.assertEqual(rfq.portal_briefing_registration_state(), "open")

    def test_scm_owner_not_limited_to_sp_app_switcher(self):
        scm = self.env.ref("ewseta_procurement.group_scm_owner")
        cms = self.env.ref("proc_cms.group_proc_cms_manager")
        user = self.env["res.users"].create({
            "name": "SCM Only User",
            "login": "scm_only_app_test",
            "group_ids": [(6, 0, [scm.id, cms.id, self.env.ref("base.group_user").id])],
        })
        self.assertFalse(user._ew_is_procurement_app_restricted_user())
        Menu = self.env["ir.ui.menu"].with_user(user)
        roots = Menu.get_user_roots()
        self.assertIn("EWSETA Procurement", roots.mapped("name"))
        self.assertIn("Website CMS", roots.mapped("name"))

    def test_sp_only_user_is_app_restricted(self):
        user = self.env["res.users"].create({
            "name": "SP Only User",
            "login": "sp_only_app_test",
            "partner_id": self.provider_partner.id,
            "group_ids": [(6, 0, [self.sp_group.id, self.env.ref("base.group_user").id])],
        })
        self.assertTrue(user._ew_is_procurement_app_restricted_user())
        roots = self.env["ir.ui.menu"].with_user(user).get_user_roots()
        self.assertEqual(roots.mapped("name"), ["EWSETA Procurement"])
