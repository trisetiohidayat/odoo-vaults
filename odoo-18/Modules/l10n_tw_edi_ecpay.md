---
Module: l10n_tw_edi_ecpay
Version: 18.0
Type: l10n/edi
Tags: #odoo18 #l10n #edi #taiwan #ecpay #einvoice
---

# l10n_tw_edi_ecpay

## Overview
Taiwan's e-invoicing module integrating with **Ecpay** (綠界科技), a major third-party e-invoice operator accredited by the Ministry of Finance. Ecpay issues e-invoices, manages carrier receipts (mobile barcode, citizen digital certificate), and handles allowance (refund) notes for B2B and B2C transactions in Taiwan.

## EDI Format / Standard
**Ecpay JSON API** — Custom JSON format over HTTPS POST. Not UBL-based. Ecpay defines its own schema with fields like: `MerchantID`, `RelateNumber`, `InvoiceType`, `TaxType`, `SalesAmount`, `TaxAmount`, `ItemArray`, etc. B2B includes `CustomerIdentifier` (8-digit tax ID).

## Dependencies
- `l10n_tw` — Taiwanese chart of accounts

## Key Models

| Class | _name | _inherit | Description |
|---|---|---|---|
| `AccountMove` | `account.move` | `account.move` | Full e-invoice state: file, ecpay_invoice_id, related_number, state (invoiced/valid/invalid), love_code, carrier_type/number, invoice_type, clearance_mark, zero_tax_rate_reason, refund_state |
| `AccountMoveLine` | `account.move.line` | `account.move.line` | `l10n_tw_edi_ecpay_item_sequence` for line tracking |
| `AccountMoveSend` | `account.move.send` | `abstract.model` | Send wizard |
| `AccountTax` | `account.tax` | `account.tax` | Taiwanese tax type (1/2/3/4) and special tax type |
| `ResCompany` | `res.company` | `res.company` | Ecpay merchant ID and credentials |
| `ResConfigSettings` | `res.config.settings` | `res.config.settings` | Settings form |
| `ResPartner` | `res.partner` | `res.partner` | Partner tax ID (for B2B) |

## Data Files
- `security/ir.model.access.csv` — Access control
- `views/res_config_setting_view.xml` — Settings
- `views/account_tax.xml` — Tax form fields
- `views/account_move_view.xml` — Invoice form
- `views/account_move_reversal_view.xml` — Reversal wizard
- `views/l10n_tw_edi_invoice_cancel_view.xml` — Cancel wizard
- `views/l10n_tw_edi_invoice_print_view.xml` — Print wizard

## How It Works

### Invoice Types
- **07** (General Invoice): standard VAT invoice, tax types 1, 2, 3
- **08** (Special Invoice): used with tax type 3 (duty-free) and 4 (special tax)

### Tax Types
- `1`: Standard 5% taxable
- `2`: Zero-rate
- `3`: Duty-free (with special tax type 8 = imported goods)
- `4`: Special tax rate (alcohol, tobacco, gasoline, etc.)
- `9`: Mixed (combined tax types on one invoice)

### Carrier Systems
- Type 1: Ecpay e-invoice carrier (barcode)
- Type 2: Citizen Digital Certificate (2 letters + 14 digits)
- Type 3: Mobile barcode (/ + 7 alphanumeric)
- Type 4: EasyCard
- Type 5: iPass

### B2B vs B2C
- **B2B**: Company partner with VAT number (8-digit tax ID), no carrier, printed, email notification
- **B2C**: Consumer, can use love code (charity donation) or carrier

### Zero Tax Rate
When tax type is 2 (zero-rate), requires:
- `ClearanceMark`: "1" (not via customs) or "2" (via customs)
- `ZeroTaxRateReason`: codes 71-79 (export goods, international transport, etc.)

### Allowance (Credit Note)
Out_refund generates an "allowance" (退款通知/折讓) on the original Ecpay invoice. Two types:
- **Offline Agreement**: seller notifies buyer, issues allowance
- **Online Agreement**: buyer clicks link from Ecpay email to agree before issuance

### Payment Status Sync
When payment state changes (paid/unpaid), `l10n_vn_edi_invoice_state` set to `payment_state_to_update`. Cron job syncs status with Ecpay.

### API Endpoints
- `/Issue`: Issue e-invoice
- `/GetIssue`: Query e-invoice status
- `/Invalid`: Invalidate e-invoice
- `/Allowance`: Issue allowance (credit note)
- `/AllowanceByCollegiate`: Issue allowance with online agreement
- `/updatePaymentStatus`: Update payment status
- `/cancelPaymentStatus`: Cancel payment status

## Installation
Standard module install. No post-init hook.

## Historical Notes
- **Odoo 17**: Taiwan e-invoicing not available in standard Odoo
- **Odoo 18**: First complete Ecpay integration. Taiwan mandated e-invoice issuance through accredited operators since 2013 for chain stores and large businesses, expanded over time.