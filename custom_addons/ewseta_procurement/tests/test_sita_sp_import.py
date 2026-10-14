import base64
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools import file_open


@tagged("post_install", "-at_install")
class TestSitaSpImport(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Partner = cls.env["res.partner"]
        cls.Users = cls.env["res.users"]
        cls.Rfq = cls.env["ew.rfq"]
        cls.za = cls.env.ref("base.za")
        cls.ict = cls.env.ref("ewseta_procurement.service_category_ict")
        cls.sp_group = cls.env.ref("ewseta_procurement.group_service_provider")
        cls.gp = cls.env.ref("base.state_za_gt", raise_if_not_found=False)
        cls.kzn = cls.env.ref("base.state_za_nl", raise_if_not_found=False)
        cls.wc = cls.env.ref("base.state_za_wc", raise_if_not_found=False)
        if not cls.gp:
            cls.gp = cls.env["res.country.state"].search(
                [("country_id", "=", cls.za.id), ("code", "=", "GP")], limit=1
            ) or cls.env["res.country.state"].create({
                "name": "Gauteng",
                "code": "GP",
                "country_id": cls.za.id,
            })
        if not cls.kzn:
            cls.kzn = cls.env["res.country.state"].search(
                [("country_id", "=", cls.za.id), ("code", "=", "KZN")], limit=1
            ) or cls.env["res.country.state"].create({
                "name": "KwaZulu-Natal",
                "code": "KZN",
                "country_id": cls.za.id,
            })
        if not cls.wc:
            cls.wc = cls.env["res.country.state"].search(
                [("country_id", "=", cls.za.id), ("code", "=", "WC")], limit=1
            ) or cls.env["res.country.state"].create({
                "name": "Western Cape",
                "code": "WC",
                "country_id": cls.za.id,
            })

    def _fixture_b64(self):
        with file_open(
            "ewseta_procurement/tests/data/sita_rfb1183_fixture.csv", "rb"
        ) as handle:
            return base64.b64encode(handle.read())

    def _wizard(self, csv_b64=None, filename="sita_rfb1183_fixture.csv"):
        return self.env["ew.sita.sp.import"].create({
            "csv_file": csv_b64 or self._fixture_b64(),
            "csv_filename": filename,
        })

    def _csv_b64(self, text):
        return base64.b64encode(text.encode("utf-8"))

    def _imported_companies(self):
        return self.Partner.search([
            ("is_company", "=", True),
            ("ew_sita_rfb1183_no", "in", ["TEST-SITA-1", "TEST-SITA-2"]),
        ])

    def test_import_fixture_creates_companies_without_users(self):
        wizard = self._wizard()
        wizard.action_preview()
        self.assertEqual(wizard.count_create, 2)
        self.assertEqual(wizard.count_skip, 2)
        skip_no_province = wizard.line_ids.filtered(
            lambda line: line.sita_no == "TEST-SITA-3"
        )
        self.assertEqual(skip_no_province.status, "skip")
        self.assertTrue(skip_no_province.note)
        self.assertIn("province", (skip_no_province.note or "").lower())
        skip_no_name = wizard.line_ids.filtered(
            lambda line: line.sita_no == "TEST-SITA-4"
        )
        self.assertEqual(skip_no_name.status, "skip")

        wizard.action_import()
        companies = self._imported_companies()
        self.assertEqual(len(companies), 2)

        acme = companies.filtered(lambda p: p.ew_sita_rfb1183_no == "TEST-SITA-1")
        cape = companies.filtered(lambda p: p.ew_sita_rfb1183_no == "TEST-SITA-2")
        self.assertTrue(acme.ew_service_provider)
        self.assertTrue(cape.ew_service_provider)
        self.assertIn(self.ict, acme.ew_service_category_ids)
        self.assertIn(self.ict, cape.ew_service_category_ids)
        self.assertEqual(acme.ew_province_ids, self.gp | self.kzn)
        self.assertEqual(cape.ew_province_ids, self.wc)
        self.assertEqual(acme.country_id, self.za)
        self.assertEqual(acme.email, "jane.sita.import@example.test")

        acme_contacts = self.Partner.search([("parent_id", "=", acme.id)])
        self.assertTrue(acme_contacts.filtered(lambda c: c.name == "Jane Doe"))
        self.assertTrue(
            acme_contacts.filtered(lambda c: c.email == "jane.sita.import@example.test")
        )
        cape_contacts = self.Partner.search([("parent_id", "=", cape.id)])
        self.assertTrue(cape_contacts.filtered(lambda c: c.name == "John Smith"))

        related = companies | acme_contacts | cape_contacts
        users = self.Users.search([("partner_id", "in", related.ids)])
        self.assertFalse(users, "SITA import must not create logins")
        self.assertFalse(
            self.Partner.search([("ew_sita_rfb1183_no", "=", "TEST-SITA-3")])
        )

    def test_reimport_same_sita_no_updates_without_duplicate(self):
        first = self._wizard()
        first.action_preview()
        first.action_import()
        acme = self.Partner.search(
            [("ew_sita_rfb1183_no", "=", "TEST-SITA-1"), ("is_company", "=", True)]
        )
        self.assertEqual(len(acme), 1)
        original_id = acme.id

        updated_csv = """sita_no,name,provinces,contact_name,email,phone,street,city,zip
TEST-SITA-1,SITA Test Acme ICT (Pty) Ltd,GP;KZN,Jane Doe,jane.new.sita.import@example.test,011 999 0001,1 Main Rd,Johannesburg,2000
"""
        second = self._wizard(self._csv_b64(updated_csv), "update.csv")
        second.action_preview()
        update_line = second.line_ids.filtered(lambda line: line.sita_no == "TEST-SITA-1")
        self.assertEqual(update_line.status, "update")
        self.assertEqual(update_line.partner_id, acme)
        second.action_import()

        companies = self.Partner.search(
            [("ew_sita_rfb1183_no", "=", "TEST-SITA-1"), ("is_company", "=", True)]
        )
        self.assertEqual(len(companies), 1)
        self.assertEqual(companies.id, original_id)
        self.assertEqual(companies.email, "jane.new.sita.import@example.test")
        self.assertEqual(companies.phone, "011 999 0001")
        child = self.Partner.search([
            ("parent_id", "=", companies.id),
            ("name", "=", "Jane Doe"),
        ], limit=1)
        self.assertEqual(child.email, "jane.new.sita.import@example.test")
        self.assertEqual(child.phone, "011 999 0001")
        self.assertFalse(
            self.Users.search([("partner_id", "in", (companies | child).ids)])
        )

    def test_empty_provinces_row_is_skipped(self):
        wizard = self._wizard()
        wizard.action_preview()
        line = wizard.line_ids.filtered(lambda rec: rec.sita_no == "TEST-SITA-3")
        self.assertEqual(line.status, "skip")
        self.assertTrue(line.note)
        wizard.action_import()
        self.assertFalse(
            self.Partner.search([
                ("name", "=", "SITA Test No Province Ltd"),
                ("is_company", "=", True),
            ])
        )

    def test_imported_partner_is_transversal_eligible_without_sp_user(self):
        wizard = self._wizard()
        wizard.action_preview()
        wizard.action_import()
        acme = self.Partner.search(
            [("ew_sita_rfb1183_no", "=", "TEST-SITA-1"), ("is_company", "=", True)],
            limit=1,
        )
        self.assertTrue(acme)
        self.assertTrue(acme.ew_service_provider)
        self.assertFalse(acme._ew_procurement_provider_active())

        rfq = self.Rfq.create({
            "name": "SITA import transversal ICT",
            "type": "rfq",
            "publication_type": "transversal",
            "closing_at": fields.Datetime.now() + timedelta(days=14),
            "rfq_document": b"dGVzdA==",
            "rfq_document_filename": "test.pdf",
            "service_category_id": self.ict.id,
            "province_ids": [(6, 0, self.gp.ids)],
        })
        eligible = rfq._find_eligible_service_providers()
        self.assertIn(acme, eligible)
        apply_url = rfq._portal_apply_url()
        self.assertIn(f"/application/rfqs/{rfq.id}/apply", apply_url)
        emails = rfq._partner_notification_emails(acme)
        self.assertTrue(any("jane.sita.import@example.test" == e.lower() for e in emails))

    def test_excel_style_headers_and_province_flags(self):
        csv_text = (
            "No,name,email,GP,KZN,WC\n"
            "X1,SITA Flag Co,flag.sita@example.test,Y,N,Y\n"
        )
        wizard = self._wizard(self._csv_b64(csv_text), "excel_style.csv")
        wizard.action_preview()
        line = wizard.line_ids.filtered(lambda rec: rec.sita_no == "X1")
        self.assertEqual(line.status, "create")
        self.assertEqual(line.provinces, "GP;WC")
        wizard.action_import()
        partner = self.Partner.search(
            [("ew_sita_rfb1183_no", "=", "X1"), ("is_company", "=", True)],
            limit=1,
        )
        self.assertTrue(partner)
        self.assertEqual(partner.ew_province_ids, self.gp | self.wc)

    def test_semicolon_delimiter(self):
        csv_text = "sita_no;name;provinces\nSEMI-1;SITA Semi Co;GP\n"
        wizard = self._wizard(self._csv_b64(csv_text), "semi.csv")
        wizard.action_preview()
        line = wizard.line_ids.filtered(lambda rec: rec.sita_no == "SEMI-1")
        self.assertEqual(line.status, "create")
        self.assertEqual(line.provinces, "GP")

    def test_missing_name_column_lists_found_headers(self):
        csv_text = "foo,bar\n1,2\n"
        wizard = self._wizard(self._csv_b64(csv_text), "bad.csv")
        with self.assertRaises(UserError) as err:
            wizard.action_preview()
        self.assertIn("foo", str(err.exception))
        self.assertIn("bar", str(err.exception))

    def test_odoo_contacts_export_without_provinces_is_skipped(self):
        csv_text = (
            "Name,Is a Company,Email,Phone,Street,Internal Notes\n"
            "Acme No Provinces,TRUE,a@b.test,011,1 Main Rd,\n"
        )
        wizard = self._wizard(self._csv_b64(csv_text), "contacts.csv")
        wizard.action_preview()
        line = wizard.line_ids.filtered(lambda rec: rec.name == "Acme No Provinces")
        self.assertEqual(line.status, "skip")

    def test_sita_odoo19_contacts_import_notes(self):
        with file_open(
            "ewseta_procurement/tests/data/sita_odoo19_contacts_fixture.csv", "rb"
        ) as handle:
            wizard = self._wizard(
                base64.b64encode(handle.read()),
                "SITA_Odoo19_Contacts_Import.csv",
            )
        wizard.action_preview()
        thuzen = wizard.line_ids.filtered(lambda rec: rec.sita_no == "1")
        accenture = wizard.line_ids.filtered(lambda rec: rec.sita_no == "4")
        self.assertIn(thuzen.status, ("create", "update"))
        self.assertEqual(thuzen.contact_name, "Zanele Ndlovu")
        self.assertEqual(thuzen.provinces, "Gauteng")
        self.assertIn(accenture.status, ("create", "update"))
        self.assertEqual(accenture.email, "publicsector@accenture.com")
        wizard.action_import()
        partner = self.Partner.search(
            [("ew_sita_rfb1183_no", "=", "1"), ("is_company", "=", True)],
            limit=1,
        )
        self.assertTrue(partner)
        self.assertEqual(partner.ew_province_ids, self.gp)
        self.assertIn(self.ict, partner.ew_service_category_ids)
        accenture_p = self.Partner.search(
            [("ew_sita_rfb1183_no", "=", "4"), ("is_company", "=", True)],
            limit=1,
        )
        self.assertEqual(accenture_p.ew_province_ids, self.gp | self.wc)
        self.assertEqual(accenture_p.email, "publicsector@accenture.com")
