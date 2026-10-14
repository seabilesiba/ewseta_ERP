import base64
import csv
import io
import logging
import re

from odoo import Command, api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

CSV_COLUMNS = (
    "sita_no",
    "name",
    "provinces",
    "contact_name",
    "email",
    "phone",
    "street",
    "city",
    "zip",
)
# SITA panel codes → res.country.state.code for country ZA (Limpopo is LP in Odoo).
CSV_PROVINCE_TO_ODOO = {
    "GP": "GP",
    "MP": "MP",
    "L": "LP",
    "LP": "LP",
    "FS": "FS",
    "KZN": "KZN",
    "EC": "EC",
    "WC": "WC",
    "NC": "NC",
    "NW": "NW",
}
HEADER_ALIASES = {
    "sita_no": {
        "sita_no",
        "sita_number",
        "sita_rfb1183_no",
        "rfb1183_no",
        "rfb1183",
        "no",
        "number",
    },
    "name": {
        "name",
        "company",
        "company_name",
        "name_of_service_provider",
        "service_provider",
        "supplier",
        "supplier_name",
    },
    "provinces": {
        "provinces",
        "province",
        "province_codes",
        "provinces_of_operation",
    },
    "contact_name": {
        "contact_name",
        "contact",
        "contact_person",
        "contact_person_name",
    },
    "email": {"email", "e_mail", "email_address"},
    "phone": {"phone", "tel", "telephone", "contact_no", "contact_number"},
    "street": {"street", "address", "physical_address"},
    "city": {"city", "town"},
    "zip": {"zip", "postal_code", "postcode", "postal"},
}
YES_VALUES = {"y", "yes", "x", "1", "true", "t"}
NOTES_HEADER_ALIASES = {"internal_notes", "comment", "notes", "note"}
EMAIL_RE = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.I)
NOTES_ROW_RE = re.compile(r"Source row:?\s*(\d+)", re.I)
NOTES_CONTACT_RE = re.compile(r"Source contact:\s*([^;]+)", re.I)
NOTES_PROVINCES_RE = re.compile(r"Province codes:\s*(.+?)(?:;|\n|$)", re.I)
# Full names from SITA_Odoo19_Contacts_Import.csv Internal Notes.
PROVINCE_NAME_TO_SITA = {
    "GAUTENG": "GP",
    "MPUMALANGA": "MP",
    "LIMPOPO": "L",
    "FREE STATE": "FS",
    "KWAZULU NATAL": "KZN",
    "KWAZULU-NATAL": "KZN",
    "EASTERN CAPE": "EC",
    "WESTERN CAPE": "WC",
    "NORTHERN CAPE": "NC",
    "NORTH WEST": "NW",
    "NORTH-WEST": "NW",
}


class EwSitaSpImport(models.TransientModel):
    _name = "ew.sita.sp.import"
    _description = "Import SITA RFB1183 service providers"

    csv_file = fields.Binary(string="CSV file", attachment=False)
    csv_filename = fields.Char(string="Filename")
    line_ids = fields.One2many("ew.sita.sp.import.line", "wizard_id", string="Rows")
    count_create = fields.Integer(compute="_compute_counts")
    count_update = fields.Integer(compute="_compute_counts")
    count_skip = fields.Integer(compute="_compute_counts")
    count_error = fields.Integer(compute="_compute_counts")
    summary = fields.Text(readonly=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("preview", "Preview"),
            ("done", "Done"),
        ],
        default="draft",
        required=True,
    )

    @api.depends("line_ids.status")
    def _compute_counts(self):
        for wizard in self:
            statuses = wizard.line_ids.mapped("status")
            wizard.count_create = statuses.count("create")
            wizard.count_update = statuses.count("update")
            wizard.count_skip = statuses.count("skip")
            wizard.count_error = statuses.count("error")

    def _reload(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Import SITA RFB1183 providers"),
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def _csv_bytes(self):
        self.ensure_one()
        data = self.csv_file
        if not data:
            raise UserError(_("Please upload a CSV file."))
        if isinstance(data, str):
            data = data.encode("ascii")
        try:
            return base64.b64decode(data, validate=False)
        except Exception as exc:
            raise UserError(_("Could not read the CSV file.")) from exc

    def _csv_text(self):
        filename = (self.csv_filename or "").lower()
        if filename.endswith((".xlsx", ".xls")):
            raise UserError(_("Please save the file as CSV, not Excel (.xlsx)."))
        raw = self._csv_bytes()
        if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
            return raw.decode("utf-16")
        for encoding in ("utf-8-sig", "cp1252", "latin-1"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        raise UserError(_("Could not decode the CSV file. Save it as CSV UTF-8."))

    @staticmethod
    def _norm_header(name):
        return re.sub(r"[^a-z0-9]+", "_", (name or "").strip().lower()).strip("_")

    def _detect_delimiter(self, header_line):
        counts = {
            ",": header_line.count(","),
            ";": header_line.count(";"),
            "\t": header_line.count("\t"),
        }
        return max(counts, key=counts.get) if max(counts.values()) else ","

    def _map_headers(self, fieldnames):
        canonical = {}
        province_flags = {}
        notes_field = None
        for raw in fieldnames or []:
            if raw is None:
                continue
            key = self._norm_header(str(raw).lstrip("\ufeff"))
            if not key:
                continue
            if key in NOTES_HEADER_ALIASES and not notes_field:
                notes_field = raw
                continue
            province_code = CSV_PROVINCE_TO_ODOO.get(key.upper())
            if province_code and key.upper() in CSV_PROVINCE_TO_ODOO:
                sita_code = "L" if key.upper() in ("L", "LP") else key.upper()
                province_flags.setdefault(sita_code, raw)
                continue
            for target, aliases in HEADER_ALIASES.items():
                if key in aliases and target not in canonical:
                    canonical[target] = raw
                    break
        return canonical, province_flags, notes_field

    def _provinces_from_flags(self, row, province_flags):
        codes = []
        for sita_code, raw_name in province_flags.items():
            value = (row.get(raw_name) or "").strip().lower()
            if value in YES_VALUES and sita_code not in codes:
                codes.append(sita_code)
        return ";".join(codes)

    def _iter_csv_rows(self):
        text = self._csv_text()
        lines = [
            line
            for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        if not lines:
            raise UserError(_("The CSV file is empty."))
        delimiter = self._detect_delimiter(lines[0])
        reader = csv.DictReader(io.StringIO("\n".join(lines)), delimiter=delimiter)
        if not reader.fieldnames:
            raise UserError(_("The CSV file has no header row."))
        found = [str(name).strip() for name in reader.fieldnames if name]
        canonical, province_flags, notes_field = self._map_headers(reader.fieldnames)
        if "name" not in canonical:
            raise UserError(
                _(
                    "CSV needs a company name column (name, company, or "
                    "name of service provider).\nFound columns: %s"
                )
                % ", ".join(found) or _("(none)")
            )
        if "provinces" not in canonical and not province_flags and not notes_field:
            raise UserError(self._missing_provinces_error(found))
        for row in reader:
            values = {
                col: (row.get(canonical[col]) or "").strip() if col in canonical else ""
                for col in CSV_COLUMNS
            }
            flag_provinces = self._provinces_from_flags(row, province_flags)
            if flag_provinces:
                existing = [
                    code
                    for code in values["provinces"].replace(",", ";").split(";")
                    if code.strip()
                ]
                for code in flag_provinces.split(";"):
                    if code not in existing:
                        existing.append(code)
                values["provinces"] = ";".join(existing)
            notes = (row.get(notes_field) or "").strip() if notes_field else ""
            extracted = self._parse_sita_notes(notes)
            if not values["sita_no"] and extracted["sita_no"]:
                values["sita_no"] = extracted["sita_no"]
            if not values["contact_name"] and extracted["contact_name"]:
                values["contact_name"] = extracted["contact_name"]
            if not values["provinces"] and extracted["provinces"]:
                values["provinces"] = extracted["provinces"]
            values["email"] = self._first_email(values["email"])
            yield values

    def _first_email(self, raw):
        match = EMAIL_RE.search(raw or "")
        return match.group(0) if match else (raw or "").strip()

    def _parse_sita_notes(self, notes):
        result = {"sita_no": "", "contact_name": "", "provinces": ""}
        if not notes:
            return result
        row_match = NOTES_ROW_RE.search(notes)
        if row_match:
            result["sita_no"] = row_match.group(1)
        contact_match = NOTES_CONTACT_RE.search(notes)
        if contact_match:
            contact = contact_match.group(1).strip()
            if contact and contact != "-":
                result["contact_name"] = contact
        provinces_match = NOTES_PROVINCES_RE.search(notes)
        if provinces_match:
            result["provinces"] = provinces_match.group(1).strip()
        return result

    def _sita_code_from_token(self, token):
        raw = (token or "").strip()
        if not raw:
            return None
        upper = re.sub(r"\s+", " ", raw.upper())
        if upper in CSV_PROVINCE_TO_ODOO:
            return upper if upper != "LP" else "L"
        name_key = upper.replace("-", " ")
        return PROVINCE_NAME_TO_SITA.get(upper) or PROVINCE_NAME_TO_SITA.get(name_key)

    def _missing_provinces_error(self, found):
        found_norm = {self._norm_header(name) for name in found}
        odoo_export = {"is_a_company", "internal_notes", "display_name"} & found_norm
        if odoo_export:
            return _(
                "This looks like an Odoo Contacts export, not the SITA RFB1183 list. "
                "Contacts exports have no province codes, so they cannot be imported as "
                "service providers.\n\n"
                "Use a SITA CSV with columns sita_no, name, provinces "
                "(GP;KZN;WC) — or Y/N columns GP, MP, L, FS, KZN, EC, WC, NC, NW. "
                "Click “Download example CSV” on this wizard.\n\n"
                "Found columns: %s"
            ) % ", ".join(found)
        return _(
            "CSV needs provinces: either a provinces column "
            "(GP;KZN;WC) or Y/N columns GP, MP, L, FS, KZN, EC, WC, NC, NW.\n"
            "Found columns: %s"
        ) % ", ".join(found)

    def action_download_template(self):
        return {
            "type": "ir.actions.act_url",
            "url": "/ewseta_procurement/static/csv/sita_rfb1183_template.csv",
            "target": "new",
        }

    def _za_states_by_code(self):
        za = self.env.ref("base.za")
        states = self.env["res.country.state"].search([("country_id", "=", za.id)])
        return {state.code.upper(): state for state in states if state.code}

    def _parse_provinces(self, raw, states_by_code):
        unknown = []
        states = self.env["res.country.state"]
        seen = set()
        for token in (raw or "").replace(",", ";").split(";"):
            if not token.strip():
                continue
            sita_code = self._sita_code_from_token(token)
            odoo_code = CSV_PROVINCE_TO_ODOO.get(sita_code) if sita_code else None
            if not odoo_code:
                unknown.append(token.strip())
                continue
            state = states_by_code.get(odoo_code)
            if not state:
                unknown.append(token.strip())
                continue
            if state.id not in seen:
                seen.add(state.id)
                states |= state
        return states, unknown

    def _match_company(self, sita_no, email, name):
        Partner = self.env["res.partner"].sudo()
        if sita_no:
            partner = Partner.search(
                [
                    ("is_company", "=", True),
                    ("ew_sita_rfb1183_no", "=", sita_no),
                ],
                limit=1,
            )
            if partner:
                return partner
        if email:
            partner = Partner.search(
                [
                    ("is_company", "=", True),
                    ("email", "=ilike", email),
                ],
                limit=1,
            )
            if partner:
                return partner
        if name:
            partner = Partner.search(
                [
                    ("is_company", "=", True),
                    ("name", "=", name),
                ],
                limit=1,
            )
            if partner:
                return partner
        return Partner.browse()

    def action_preview(self):
        self.ensure_one()
        self.line_ids.unlink()
        states_by_code = self._za_states_by_code()
        seen_sita = {}
        vals_list = []
        for index, row in enumerate(self._iter_csv_rows(), start=2):
            sita_no = row["sita_no"]
            name = row["name"]
            email = row["email"]
            line_vals = {
                "sita_no": sita_no,
                "name": name,
                "provinces": row["provinces"],
                "contact_name": row["contact_name"],
                "email": email,
                "phone": row["phone"],
                "street": row["street"],
                "city": row["city"],
                "zip": row["zip"],
                "row_number": index,
            }
            if sita_no and sita_no in seen_sita:
                line_vals.update(
                    {
                        "status": "error",
                        "note": _("Duplicate sita_no already on row %s.")
                        % seen_sita[sita_no],
                    }
                )
                vals_list.append(line_vals)
                continue
            if sita_no:
                seen_sita[sita_no] = index
            if not name:
                line_vals.update(
                    {
                        "status": "skip",
                        "note": _("Skipped: company name is required."),
                    }
                )
                vals_list.append(line_vals)
                continue
            states, unknown = self._parse_provinces(row["provinces"], states_by_code)
            if not states:
                note = _("Skipped: at least one province Y/code is required.")
                if unknown:
                    note = "%s %s" % (
                        note,
                        _("Unknown province codes: %s") % ", ".join(unknown),
                    )
                line_vals.update({"status": "skip", "note": note})
                vals_list.append(line_vals)
                continue
            partner = self._match_company(sita_no, email, name)
            note_parts = []
            if unknown:
                note_parts.append(
                    _("Ignored unknown province codes: %s") % ", ".join(unknown)
                )
            extra = " ".join(note_parts)
            if partner:
                line_vals.update(
                    {
                        "status": "update",
                        "partner_id": partner.id,
                        "note": extra or _("Will update existing company."),
                    }
                )
            else:
                line_vals.update(
                    {
                        "status": "create",
                        "note": extra or _("Will create company (no login)."),
                    }
                )
            vals_list.append(line_vals)
        self.write(
            {
                "line_ids": [Command.create(vals) for vals in vals_list],
                "state": "preview",
                "summary": False,
            }
        )
        return self._reload()

    def _company_vals(self, line, states):
        za = self.env.ref("base.za")
        ict = self.env.ref("ewseta_procurement.service_category_ict")
        vals = {
            "is_company": True,
            "company_type": "company",
            "name": line.name,
            "ew_service_provider": True,
            "ew_province_ids": [Command.set(states.ids)],
            "country_id": za.id,
        }
        if line.sita_no:
            vals["ew_sita_rfb1183_no"] = line.sita_no
        if line.email:
            vals["email"] = line.email
        if line.phone:
            vals["phone"] = line.phone
        if line.street:
            vals["street"] = line.street
        if line.city:
            vals["city"] = line.city
        if line.zip:
            vals["zip"] = line.zip
        if line.status == "create":
            vals["ew_service_category_ids"] = [Command.set(ict.ids)]
        else:
            vals["ew_service_category_ids"] = [Command.link(ict.id)]
        return vals

    def _upsert_child_contact(self, company, line):
        contact_name = (line.contact_name or "").strip()
        email = (line.email or "").strip()
        phone = (line.phone or "").strip()
        if not contact_name and not email and not phone:
            return self.env["res.partner"]
        Partner = self.env["res.partner"].sudo()
        child = Partner.browse()
        children = Partner.search([("parent_id", "=", company.id)])
        if email:
            child = children.filtered(
                lambda p: (p.email or "").strip().lower() == email.lower()
            )[:1]
        if not child and contact_name:
            child = children.filtered(lambda p: (p.name or "").strip() == contact_name)[:1]
        values = {
            "type": "contact",
            "is_company": False,
            "parent_id": company.id,
        }
        if contact_name:
            values["name"] = contact_name
        elif email:
            values["name"] = email
        else:
            values["name"] = company.name
        if email:
            values["email"] = email
        if phone:
            values["phone"] = phone
        if child:
            child.write(values)
            return child
        return Partner.create(values)

    def action_import(self):
        self.ensure_one()
        if self.state != "preview" or not self.line_ids:
            self.action_preview()
        states_by_code = self._za_states_by_code()
        Partner = self.env["res.partner"].sudo()
        created = Partner.browse()
        updated = Partner.browse()
        skipped = 0
        errors = 0
        for line in self.line_ids:
            if line.status in ("skip", "error"):
                if line.status == "skip":
                    skipped += 1
                else:
                    errors += 1
                continue
            states, _unknown = self._parse_provinces(line.provinces, states_by_code)
            if not states or not line.name:
                line.write(
                    {
                        "status": "skip",
                        "note": line.note or _("Skipped: name and provinces are required."),
                    }
                )
                skipped += 1
                continue
            try:
                vals = self._company_vals(line, states)
                if line.status == "update" and line.partner_id:
                    partner = line.partner_id.sudo()
                    partner.write(vals)
                    updated |= partner
                else:
                    partner = Partner.create(vals)
                    created |= partner
                self._upsert_child_contact(partner, line)
                line.write({"partner_id": partner.id})
            except Exception as exc:
                _logger.exception("SITA RFB1183 import failed on row %s", line.row_number)
                line.write(
                    {
                        "status": "error",
                        "note": _("Import failed: %s") % exc,
                    }
                )
                errors += 1
        summary = _(
            "Created %(created)s, updated %(updated)s, skipped %(skipped)s, errors %(errors)s. "
            "No user logins were created. Matching RFQs/RFPs notify them by email with the public application form."
        ) % {
            "created": len(created),
            "updated": len(updated),
            "skipped": skipped,
            "errors": errors,
        }
        self.write({"state": "done", "summary": summary})
        return self._reload()


class EwSitaSpImportLine(models.TransientModel):
    _name = "ew.sita.sp.import.line"
    _description = "SITA RFB1183 import row"
    _order = "row_number, id"

    wizard_id = fields.Many2one(
        "ew.sita.sp.import",
        required=True,
        ondelete="cascade",
    )
    row_number = fields.Integer()
    sita_no = fields.Char(string="SITA no.")
    name = fields.Char(string="Company")
    provinces = fields.Char()
    contact_name = fields.Char()
    email = fields.Char()
    phone = fields.Char()
    street = fields.Char()
    city = fields.Char()
    zip = fields.Char()
    status = fields.Selection(
        [
            ("create", "Create"),
            ("update", "Update"),
            ("skip", "Skip"),
            ("error", "Error"),
        ],
        required=True,
        default="create",
    )
    note = fields.Char()
    partner_id = fields.Many2one("res.partner", string="Matched company")
