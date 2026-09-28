# -*- coding: utf-8 -*-

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


@tagged('post_install', '-at_install')
class TestEolAssetPurchaseMvp(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.category = cls.env['ew.eol.asset.category'].create({
            'name': 'Laptop pool',
            'code': 'LAP',
            'default_price': 1500.0,
            'purchase_limit_count': 1,
        })
        cls.employee = cls.env['hr.employee'].create({
            'name': 'EOL Test Employee',
            'work_email': 'eol.test@example.com',
        })
        cls.equipment = cls.env['maintenance.equipment'].create({
            'name': 'Pool laptop',
            'eol_sale_eligible': True,
            'sale_availability': 'available',
            'asset_state': 'available',
            'eol_deprovision_done': True,
        })
        cls.approver = cls.env['res.users'].create({
            'name': 'EOL Approver',
            'login': 'eol_approver_test',
            'group_ids': [(6, 0, [
                cls.env.ref('ewseta_eol_asset_purchase.group_eol_approver').id,
                cls.env.ref('ewseta_eol_asset_purchase.group_eol_asset_manager').id,
            ])],
        })

    def _submit_vals(self, **extra):
        vals = {
            'employee_name': self.employee.name,
            'work_email': 'eol.test@example.com',
            'category_id': self.category.id,
            'request_type': 'pool',
            'ack_as_is': True,
            'ack_no_support': True,
            'ack_policy': True,
        }
        vals.update(extra)
        return vals

    def test_ac01_public_submit_and_verify(self):
        req, token = self.env['ew.eol.purchase.request'].public_create_and_submit(
            self._submit_vals(),
        )
        self.assertEqual(req.state, 'pending_verification')
        self.assertTrue(token)
        self.assertTrue(req.validate_tracking_token(token))
        verification = req.verification_id
        self.assertTrue(verification)
        otp = '123456'
        from odoo.addons.ewseta_eol_asset_purchase.models.eol_public_verification import _hash_value
        pepper = self.env['ew.eol.public.verification']._get_pepper()
        verification.otp_hash = _hash_value(otp, pepper)
        req.action_public_verify_and_continue(otp)
        self.assertIn(req.state, ('under_review', 'exception'))

    def test_ac02_purchase_limit(self):
        first, _t = self.env['ew.eol.purchase.request'].public_create_and_submit(
            self._submit_vals(),
        )
        first.write({'state': 'approved', 'employee_id': self.employee.id})
        with self.assertRaises(UserError):
            self.env['ew.eol.purchase.request'].public_create_and_submit(
                self._submit_vals(),
            )

    def test_ac03_concurrent_reservation(self):
        eq2 = self.env['maintenance.equipment'].create({
            'name': 'Single pool unit',
            'eol_sale_eligible': True,
            'sale_availability': 'available',
            'asset_state': 'available',
            'eol_deprovision_done': True,
        })
        self.equipment.write({'sale_availability': 'withdrawn'})
        req1 = self.env['ew.eol.purchase.request'].create(self._submit_vals())
        req1.write({
            'employee_id': self.employee.id,
            'employee_verified': True,
            'state': 'under_review',
            'equipment_id': eq2.id,
        })
        req1._reserve_equipment()
        req2 = self.env['ew.eol.purchase.request'].create(self._submit_vals())
        req2.write({
            'employee_id': self.employee.id,
            'employee_verified': True,
            'state': 'under_review',
            'equipment_id': eq2.id,
        })
        with self.assertRaises(UserError):
            req2._reserve_equipment()

    def test_ac04_approve_requires_verification(self):
        req = self.env['ew.eol.purchase.request'].create(self._submit_vals())
        req.write({
            'state': 'awaiting_approval',
            'employee_verified': False,
            'equipment_id': self.equipment.id,
        })
        self.equipment.write({
            'sale_availability': 'reserved',
            'active_eol_request_id': req.id,
        })
        with self.assertRaises(UserError):
            req.with_user(self.approver).action_approve()

    def test_ict_prepare_pool_wizard_releases_assigned_asset(self):
        assigned = self.env['maintenance.equipment'].create({
            'name': 'Handback laptop',
            'asset_state': 'assigned',
            'employee_id': self.employee.id,
            'hostname': 'corp-laptop-01',
            'eol_sale_eligible': False,
        })
        wizard = self.env['ew.eol.prepare.pool.wizard'].create({
            'equipment_id': assigned.id,
            'deprov_user_profiles': True,
            'deprov_licenses': True,
            'deprov_antivirus': True,
            'deprov_vpn': True,
            'deprov_monitoring': True,
            'deprov_email': True,
            'deprov_certificates': True,
            'deprov_other_apps': True,
            'set_eol_sale_eligible': True,
            'clear_network_identity': True,
        })
        wizard.action_apply()
        self.assertEqual(assigned.asset_state, 'available')
        self.assertFalse(assigned.employee_id)
        self.assertTrue(assigned.eol_deprovision_done)
        self.assertTrue(assigned.eol_sale_eligible)
        self.assertTrue(assigned.eol_pool_eligible)
        self.assertFalse(assigned.hostname)

    def test_pool_requires_ict_deprovision(self):
        raw_pool = self.env['maintenance.equipment'].create({
            'name': 'Not deprovisioned',
            'eol_sale_eligible': True,
            'sale_availability': 'available',
            'asset_state': 'available',
            'eol_deprovision_done': False,
        })
        self.assertFalse(raw_pool.eol_pool_eligible)
        req = self.env['ew.eol.purchase.request'].create(self._submit_vals())
        req.write({
            'employee_id': self.employee.id,
            'employee_verified': True,
            'state': 'under_review',
            'equipment_id': raw_pool.id,
        })
        with self.assertRaises(UserError):
            req._reserve_equipment()

    def test_pool_excludes_assigned_eol_eligible_assets(self):
        assigned_laptop = self.env['maintenance.equipment'].create({
            'name': 'Assigned laptop',
            'eol_sale_eligible': True,
            'sale_availability': 'available',
            'asset_state': 'assigned',
            'employee_id': self.employee.id,
            'serial_no': 'SN-ASSIGNED-1',
        })
        self.assertFalse(assigned_laptop.eol_pool_eligible)
        req = self.env['ew.eol.purchase.request'].create(self._submit_vals())
        req.write({
            'employee_id': self.employee.id,
            'employee_verified': True,
            'state': 'under_review',
            'equipment_id': assigned_laptop.id,
        })
        with self.assertRaises(UserError):
            req._reserve_equipment()

    def test_assigned_request_finds_employee_device(self):
        assigned_laptop = self.env['maintenance.equipment'].create({
            'name': 'My laptop',
            'eol_sale_eligible': True,
            'sale_availability': 'available',
            'asset_state': 'assigned',
            'employee_id': self.employee.id,
            'asset_code': 'TAG-100',
            'serial_no': 'SN-100',
        })
        req = self.env['ew.eol.purchase.request'].create(
            self._submit_vals(request_type='assigned', serial_or_tag='TAG-100'),
        )
        req.write({
            'employee_id': self.employee.id,
            'employee_verified': True,
            'state': 'under_review',
        })
        req._reserve_equipment()
        self.assertEqual(req.equipment_id, assigned_laptop)
        self.assertEqual(assigned_laptop.sale_availability, 'reserved')

    def test_mark_received_sets_equipment_sold(self):
        req = self.env['ew.eol.purchase.request'].create(self._submit_vals())
        req.write({
            'employee_id': self.employee.id,
            'employee_verified': True,
            'state': 'approved',
            'equipment_id': self.equipment.id,
            'sale_price': 1500.0,
        })
        self.equipment.write({
            'sale_availability': 'reserved',
            'active_eol_request_id': req.id,
        })
        manager = self.env['res.users'].create({
            'name': 'EOL Manager Handover',
            'login': 'eol_manager_handover_test',
            'group_ids': [(6, 0, [
                self.env.ref('ewseta_eol_asset_purchase.group_eol_asset_manager').id,
            ])],
        })
        req.with_user(manager).action_mark_asset_received()
        self.assertEqual(req.state, 'received')
        self.assertEqual(self.equipment.sale_availability, 'sold')
        self.assertEqual(req, self.equipment.eol_last_received_request_id)
        self.assertTrue(self.equipment.eol_handover_received)
        self.assertEqual(self.equipment.asset_state, 'disposed')
        self.assertFalse(self.equipment.active_eol_request_id)

    def test_ac19_tracking_token_isolation(self):
        req1, token1 = self.env['ew.eol.purchase.request'].public_create_and_submit(
            self._submit_vals(work_email='eol.test@example.com'),
        )
        req2, token2 = self.env['ew.eol.purchase.request'].public_create_and_submit(
            self._submit_vals(work_email='eol.other@example.com'),
        )
        self.assertEqual(self.env['ew.eol.purchase.request'].find_by_tracking_token(token1), req1)
        self.assertEqual(self.env['ew.eol.purchase.request'].find_by_tracking_token(token2), req2)
        self.assertFalse(req1.validate_tracking_token(token2))
