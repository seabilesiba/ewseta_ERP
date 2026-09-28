# EWSETA EOL Asset Purchase (Odoo 19 Community MVP)

## Install

1. Ensure `it_asset_management` is installed.
2. Update apps list and install **EWSETA EOL Asset Purchase**.
3. Settings → EOL Asset Sales (or configure `ir.config_parameter` keys under `ewseta_eol.*`).

## Public URLs

| Path | Purpose |
|------|---------|
| `/employee/eol-assets` | Programme intro |
| `/employee/eol-assets/request` | Submit request |
| `/employee/eol-assets/verify?request_id=&token=` | OTP verification |
| `/employee/eol-assets/track/<token>` | Private status |

## Procurement website navigation

When this module is installed, **Procurement CMS** adds:

- **Navbar:** “EOL asset purchase” → `/employee/eol-assets/request` (before “Procurements”)
- **Footer (Explore):** same link

Records: `proc.cms.nav.item` / `proc.cms.footer.link` (editable under **Website content → Navbar / Footer** in `proc_cms`). They are hidden when **Public EOL request form enabled** is turned off in EOL programme settings.

Direct link (same site as RFQs): `https://<your-host>/employee/eol-assets/request`

**Staff:** On a verified request, use **Resend tracking link** (EOL Asset Manager or Approver) to email a new private status URL; older links stop working.

## MVP scope

Included: public form, email OTP, HR match / manual verification queue, purchase limits, atomic reservation, manual approval, secure tracking token.

Not included (Phase 2+): finance payment, waiver PDF/e-sign, full portal dashboard, operational reports.

## ICT deprovisioning (EOL pool)

Before a device appears in the employee **pool**, ICT must record corporate data removal on the asset form (**EOL deprovisioning** tab) or use **Prepare for EOL pool** (guided checklist). That flow:

- Confirms removal of EWSETA data, licences, AV, VPN, monitoring, email, certificates, and other corporate configuration (on the physical device).
- **Unassigns** the employee/department and sets **Asset State = Available** (the **asset tag** stays on the record).
- Optionally clears hostname/IP/licence fields in the register and marks **EOL sale eligible**.

Employees buying **their assigned** laptop use the separate public form path; pool stock must be deprovisioned and unassigned first.

## Configuration checklist

- Create **EOL categories** linked to maintenance equipment categories for pool matching.
- Mark equipment **EOL sale eligible** and set **EOL sale availability** to *Available for EOL sale*.
- **Pool stock** must have IT **Asset State = Available**, **ICT deprovisioning complete**, and **EOL sale eligible**.
- Assign **EOL Approver** and **EOL Asset Manager** groups.
- Set corporate email domain, OTP TTL, and purchase limits in settings.

## Reservation timing

After successful email verification (and manual verification when HR cannot auto-match), the service reserves one eligible `maintenance.equipment` row using `SELECT … FOR UPDATE` to prevent double booking.

## UAT script (SRD acceptance subset)

| ID | Steps | Expected |
|----|-------|----------|
| AC-01 | Submit public form with all acknowledgements; complete OTP | Request moves to under review or exception; confirmation email |
| AC-02 | Submit second in-flight/approved request same employee+category over limit | Blocked with limit error |
| AC-03 | Two requests reserve same pool asset concurrently | Second reservation fails |
| AC-04 | Approver approves unverified request | Blocked |
| AC-16 | Approver approves verified request with reservation | State `approved`, asset stays **Reserved** until handover |
| AC-17 | ICT marks approved request as asset received | State `received`, equipment **Sold** (off pool) |
| AC-19 | Open track URL with another request’s token | No data leak (generic error or wrong record) |
| AC-20 | Rate limit: many submissions same email in 1 hour | Generic / rate error |
| AC-21 | Invalid OTP over max attempts | Verification failed; no plaintext OTP in chatter |

Automated coverage: run `odoo-bin -c odoo.conf -d <db> --test-enable --stop-after-init -i ewseta_eol_asset_purchase --test-tags ewseta_eol_asset_purchase`
