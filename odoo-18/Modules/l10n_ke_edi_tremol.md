---
Module: l10n_ke_edi_tremol
Version: 18.0
Type: l10n/edi
Tags: #odoo18 #l10n #edi #kenya #tremol #kra #tims
---

# l10n_ke_edi_tremol

## Overview
Integrates with the **Kenya Tremol G03 Control Unit (CU)** fiscal device for sending invoices to the Kenya Revenue Authority (KRA) via TIMS (Tax Invoice Management System). The G03 is a hardware fiscal device attached to the point of sale; this module communicates with it over TCP/IP to log invoices and receive back the fiscal receipt number, serial, and QR code.

## EDI Format / Standard
**Tremol G03 Protocol** — Binary protocol over TCP/IP. Commands in cp1251 (Windows Eastern European) encoding. Used by the Kenyan G03 CU device mandated by KRA for VAT-compliant POS systems.

## Dependencies
- `l10n_ke` — Kenyan chart of accounts

## Key Models

| Class | _name | _inherit | Description |
|---|---|---|---|
| `AccountMove` | `account.move` | `account.move` | Fields: `l10n_ke_cu_datetime`, `l10n_ke_cu_serial_number`, `l10n_ke_cu_invoice_number`, `l10n_ke_cu_qrcode`, `_compute_l10n_ke_cu_show_send_button` |
| `AccountMoveSend` | `account.move.send` | `abstract.model` | Send wizard with CU integration |
| `ResCompany` | `res.company` | `res.company` | CU proxy address, OSCU active flag |
| `ResConfigSettings` | `res.config.settings` | `res.config.settings` | Settings form |
| `ResPartner` | `res.partner` | `res.partner` | Partner KRA fields |

## Data Files
- `views/account_move_view.xml` — CU fields on invoice form
- `views/report_invoice.xml` — QR code on invoice report
- `views/res_config_settings_view.xml` — Settings
- `views/res_partner_views.xml` — Partner KRA fields
- `static/src/components/*` — Web components for JS client action `l10n_ke_post_send`

## How It Works

### Fiscal Device Protocol
Communication with Tremol G03 uses binary commands:
- `0x30`: Open fiscal receipt — sends company name, VAT, address, customer info
- `0x31`: Sale of article — sends name, VAT class (A/B/C/D/E), price, UoM, KRA item code, description, tax rate, quantity, optional discount %
- `0x38`: Close fiscal receipt
- `0x68`: Read date/time (used to get CU timestamp after closing)

### Message Format
All data fields padded/justified to fixed lengths (cp1251 encoded), separated by `;` (semicolon). Command byte prefix, data bytes after.

### Line Distribution
If a discount line (negative amount) exists on the invoice, it is distributed across matching product lines by tax type (VAT 16%, 8%, 0%). Discounts aggregated and reported as a line discount percentage.

### Validation
Before sending:
- Must be posted Kenyan invoice (country_code = KE)
- Currency must be KES
- Each line must have exactly one VAT tax (16%, 8%, or 0%)
- Zero-rate lines must have a KRA item code on the tax
- Cannot send twice (fields already filled)

### OSCU Override
If company has `l10n_ke_oscu_is_active`, the TREMOL send button is hidden and a message directs users to use "Send to eTIMS" instead.

### Responses
After sending, device returns:
- Serial number (factory-set)
- Invoice number (sequential within CU)
- QR code (URL for KRA verification)
- Timestamp

## Installation
Standard module installation. Depends on `l10n_ke`. Web client action handles the JavaScript communication with the hardware device.

## Historical Notes
- **Odoo 18**: New module. Kenya mandated fiscal device integration with TIMS for all VAT-registered businesses with POS systems. The G03 Tremol device is one certified option. Currency conversion to KES from other currencies uses invoice-level exchange rate or original invoice rate for refunds.