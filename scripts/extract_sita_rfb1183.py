#!/usr/bin/env python3
"""Extract SITA RFB1183 approved-provider PDF tables to a cleaned CSV.

The SITA landscape matrix extracts poorly (merged cells, split headers). Treat
this as a starter: review the CSV in Excel before uploading it to the Odoo
wizard ``ew.sita.sp.import``.

CSV columns (what the wizard accepts):

  sita_no       PDF "No" — stable upsert key
  name          Company name
  provinces     Semicolon codes, e.g. GP;KZN;WC
                GP, MP, L, FS, KZN, EC, WC, NC, NW  (L = Limpopo)
  contact_name  Named person
  email
  phone
  street
  city
  zip

SITA ICT service tick columns are not imported (v1). All rows get EWSETA
category ICT & systems in the wizard.

Usage:
  python scripts/extract_sita_rfb1183.py INPUT.pdf OUTPUT.csv
  python scripts/extract_sita_rfb1183.py --template OUTPUT.csv
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

CSV_COLUMNS = [
    "sita_no",
    "name",
    "provinces",
    "contact_name",
    "email",
    "phone",
    "street",
    "city",
    "zip",
]
PROVINCE_CODES = ["GP", "MP", "L", "FS", "KZN", "EC", "WC", "NC", "NW"]
PROVINCE_ALIASES = {
    "GP": "GP",
    "GAUTENG": "GP",
    "MP": "MP",
    "MPUMALANGA": "MP",
    "L": "L",
    "LP": "L",
    "LIMPOPO": "L",
    "FS": "FS",
    "FREE STATE": "FS",
    "KZN": "KZN",
    "KWAZULU-NATAL": "KZN",
    "KWAZULU NATAL": "KZN",
    "EC": "EC",
    "EASTERN CAPE": "EC",
    "WC": "WC",
    "WESTERN CAPE": "WC",
    "NC": "NC",
    "NORTHERN CAPE": "NC",
    "NW": "NW",
    "NORTH WEST": "NW",
    "NORTH-WEST": "NW",
}
EMAIL_RE = re.compile(r"[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}", re.I)
PHONE_RE = re.compile(r"(?:\+?27|0)\s*\d[\d\s\-()]{6,}")
YES_RE = re.compile(r"^(Y|YES|X|1)$", re.I)


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({col: (row.get(col) or "").strip() for col in CSV_COLUMNS})


def write_template(path: Path) -> None:
    write_csv(
        path,
        [
            {
                "sita_no": "1",
                "name": "Example ICT (Pty) Ltd",
                "provinces": "GP;WC",
                "contact_name": "Jane Doe",
                "email": "jane@example.test",
                "phone": "011 000 0000",
                "street": "1 Main Rd",
                "city": "Johannesburg",
                "zip": "2000",
            }
        ],
    )


def _cell(value) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _norm_header(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", " ", (value or "").upper()).strip()


def _province_code(header: str) -> str | None:
    token = _norm_header(header)
    if not token:
        return None
    if token in PROVINCE_ALIASES:
        return PROVINCE_ALIASES[token]
    first = token.split()[0]
    return PROVINCE_ALIASES.get(first)


def _is_yes(value: str) -> bool:
    return bool(YES_RE.match(_cell(value)))


def _looks_header(row: list[str]) -> bool:
    joined = " ".join(_norm_header(c) for c in row if c)
    return "NO" in joined.split() and any(
        code in joined.split() or code in joined for code in ("GP", "KZN", "WC")
    )


def _split_address(text: str) -> tuple[str, str, str]:
    text = _cell(text)
    if not text:
        return "", "", ""
    parts = [p.strip() for p in re.split(r"[,|\n]", text) if p.strip()]
    zip_code = ""
    city = ""
    street = text
    if parts:
        last = parts[-1]
        zip_match = re.search(r"\b(\d{4})\b", last)
        if zip_match:
            zip_code = zip_match.group(1)
            last = last.replace(zip_code, "").strip(" ,")
        if last:
            city = last
        street = ", ".join(parts[:-1]) if len(parts) > 1 else (parts[0] if not city else "")
        if not street and city and city != parts[0]:
            street = parts[0]
    return street, city, zip_code


def _classify_headers(row: list[str]) -> dict[str, object]:
    mapping: dict[str, object] = {"provinces": {}}
    for idx, raw in enumerate(row):
        header = _norm_header(raw)
        province = _province_code(raw)
        if province:
            mapping["provinces"][idx] = province  # type: ignore[index]
            continue
        if header in {"NO", "N O"} or header.startswith("NO "):
            mapping["sita_no"] = idx
        elif "SERVICE PROVIDER" in header or header in {"NAME", "COMPANY", "COMPANY NAME"}:
            mapping.setdefault("name", idx)
        elif "CONTACT" in header and "EMAIL" not in header:
            mapping.setdefault("contact_name", idx)
        elif "EMAIL" in header or "E MAIL" in header:
            mapping.setdefault("email", idx)
        elif header in {"TEL", "TELEPHONE", "PHONE", "CONTACT NO"} or "TEL" in header:
            mapping.setdefault("phone", idx)
        elif "ADDRESS" in header or header in {"PHYSICAL", "PHYSICAL ADDRESS"}:
            mapping.setdefault("address", idx)
    return mapping


def _row_provinces(row: list[str], province_idx: dict[int, str]) -> str:
    found: list[str] = []
    seen: set[str] = set()
    for idx, code in province_idx.items():
        if idx < len(row) and _is_yes(row[idx]) and code not in seen:
            seen.add(code)
            found.append(code)
    if found:
        return ";".join(found)
    # Fallback: scan leftover Y next to known codes in concatenated text.
    joined = " ".join(row)
    for code in PROVINCE_CODES:
        if re.search(rf"\b{re.escape(code)}\b\s*[YyXx]", joined) and code not in seen:
            found.append(code)
    return ";".join(found)


def _row_email(row: list[str], idx: int | None) -> str:
    if idx is not None and idx < len(row):
        match = EMAIL_RE.search(row[idx] or "")
        if match:
            return match.group(0)
    for cell in row:
        match = EMAIL_RE.search(cell or "")
        if match:
            return match.group(0)
    return ""


def _row_phone(row: list[str], idx: int | None) -> str:
    if idx is not None and idx < len(row):
        match = PHONE_RE.search(row[idx] or "")
        if match:
            return re.sub(r"\s+", " ", match.group(0)).strip()
    for cell in row:
        match = PHONE_RE.search(cell or "")
        if match:
            return re.sub(r"\s+", " ", match.group(0)).strip()
    return ""


def tables_to_rows(tables: list[list[list]]) -> list[dict]:
    mapping: dict[str, object] | None = None
    records: list[dict] = []
    seen_nos: set[str] = set()
    for table in tables:
        for raw_row in table or []:
            row = [_cell(c) for c in raw_row]
            if not any(row):
                continue
            if _looks_header(row):
                mapping = _classify_headers(row)
                continue
            if not mapping:
                continue
            sita_idx = mapping.get("sita_no")
            sita_no = _cell(row[sita_idx]) if isinstance(sita_idx, int) and sita_idx < len(row) else ""
            if not re.match(r"^\d+[A-Z]?$", sita_no):
                # First numeric-looking cell.
                for cell in row[:3]:
                    if re.match(r"^\d+[A-Z]?$", cell):
                        sita_no = cell
                        break
            name_idx = mapping.get("name")
            name = _cell(row[name_idx]) if isinstance(name_idx, int) and name_idx < len(row) else ""
            if not name:
                for cell in row:
                    if cell and not re.match(r"^\d+[A-Z]?$", cell) and "@" not in cell and len(cell) > 3:
                        name = cell
                        break
            if not sita_no and not name:
                continue
            key = sita_no or name
            if key in seen_nos:
                continue
            seen_nos.add(key)
            contact_idx = mapping.get("contact_name")
            address_idx = mapping.get("address")
            street, city, zip_code = _split_address(
                row[address_idx] if isinstance(address_idx, int) and address_idx < len(row) else ""
            )
            records.append(
                {
                    "sita_no": sita_no,
                    "name": name,
                    "provinces": _row_provinces(row, mapping.get("provinces") or {}),  # type: ignore[arg-type]
                    "contact_name": _cell(row[contact_idx]) if isinstance(contact_idx, int) and contact_idx < len(row) else "",
                    "email": _row_email(row, mapping.get("email") if isinstance(mapping.get("email"), int) else None),
                    "phone": _row_phone(row, mapping.get("phone") if isinstance(mapping.get("phone"), int) else None),
                    "street": street,
                    "city": city,
                    "zip": zip_code,
                }
            )
    return records


def extract_pdfplumber(pdf_path: Path) -> list[dict]:
    try:
        import pdfplumber  # type: ignore
    except ImportError as err:
        raise SystemExit(
            "pdfplumber is not installed. pip install pdfplumber\n"
            "Or build the CSV in Excel and upload it to the Odoo wizard."
        ) from err

    tables: list[list[list]] = []
    with pdfplumber.open(str(pdf_path)) as pdf:
        for page in pdf.pages:
            extracted = page.extract_tables() or []
            tables.extend(extracted)
    rows = tables_to_rows(tables)
    if len(rows) >= 10:
        return rows

    # Second pass: looser line strategy when table lines are missing.
    try:
        import camelot  # type: ignore
    except ImportError:
        return rows
    try:
        camelot_tables = camelot.read_pdf(str(pdf_path), pages="all", flavor="lattice")
        extra = [t.data.tolist() for t in camelot_tables]
        merged = tables_to_rows(extra)
        return merged if len(merged) > len(rows) else rows
    except Exception as exc:  # noqa: BLE001 — best-effort optional backend
        print(f"camelot fallback skipped: {exc}", file=sys.stderr)
        return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", nargs="?", help="SITA RFB1183 PDF path")
    parser.add_argument("csv", nargs="?", help="Output CSV path")
    parser.add_argument("--template", metavar="CSV", help="Write a one-row example CSV and exit")
    args = parser.parse_args(argv)

    if args.template:
        out = Path(args.template)
        write_template(out)
        print(f"Wrote template {out}")
        return 0
    if not args.pdf or not args.csv:
        parser.error("Provide INPUT.pdf OUTPUT.csv, or --template OUTPUT.csv")

    pdf_path = Path(args.pdf)
    csv_path = Path(args.csv)
    if not pdf_path.is_file():
        raise SystemExit(f"PDF not found: {pdf_path}")

    rows = extract_pdfplumber(pdf_path)
    write_csv(csv_path, rows)
    print(f"Wrote {len(rows)} rows to {csv_path}")
    if len(rows) < 50:
        print(
            "Warning: extraction looks incomplete. The SITA table often needs a "
            "manual Excel pass before the Odoo wizard import.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
