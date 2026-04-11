---
Module: l10n_jo_edi
Version: 18.0
Type: l10n/edi
Tags: #odoo18 #l10n #edi #jordan #jofotara #ubl
---

# l10n_jo_edi

## Overview
Jordanian e-invoicing module integrating with **JoFotara** (Jordan Free Invoice System). JoFotara is the government's electronic invoice platform mandated for VAT-registered businesses. Built on **UBL 2.1** customized for Jordanian requirements.

## EDI Format / Standard
**UBL 2.1 (JoFotara)** — Extends the standard `account.edi.xml.ubl_21` format with Jordan-specific customizations:
- Currency always `JO` (not JOD ISO code)
- Up to 9 decimal places for amounts
- Special/fixed tax support alongside percentage tax
- Party ID scheme: TN (Jordan), PN (other countries)
- No VAT parties reported with empty party identification
- Payment means code derived from scope + payment method + tax payer type

## Dependencies
- `account_edi_ubl_cii` — Base UBL/CII framework
- `l10n_jo` — Jordan chart of accounts

## Key Models

| Class | _name | _inherit | Description |
|---|---|---|---|
| `AccountEdiXmlUBL21JO` | `account.edi.xml.ubl_21.jo` | `account.edi.xml.ubl_21` | Jordanian UBL 2.1 format: templates `l10n_jo_edi.ubl_jo_Invoice`, tax handling with fixed+percent dual tax, discount reporting |
| `AccountMove` | `account.move` | `account.move` | Adds `l10n_jo_edi_uuid` field for unique invoice ID |
| `AccountMoveSend` | `account.move.send` | `abstract.model` | Send wizard |
| `AccountTax` | `account.tax` | `account.tax` | Jordanian tax classification |
| `IrAttachment` | `ir.attachment` | `ir.attachment` | UUID assignment on attachment creation |
| `ResCompany` | `res.company` | `res.company` | JoFotara configuration: taxpayer type (regular/income) |
| `ResConfigSettings` | `res.config.settings` | `res.config.settings` | Settings form |

## Data Files
- `data/ubl_jo_templates.xml` — QWeb UBL templates (InvoiceType, PaymentMeansType, InvoiceLineType, TaxTotalType)

## How It Works

### Tax Calculation
Jordan uses dual tax system:
- **General tax** (percentage): applied on (line amount + fixed tax)
- **Special tax** (fixed amount): per line
- Taxable amount = unit price × quantity - discount
- Tax amount = (taxable + fixed) × percentage

### Template Overrides
Customizes UBL template for JO:
- `ubl_jo_Invoice`: main template replacing `ubl_20_Invoice`
- `ubl_jo_InvoiceType`: type code "388" (invoice) / "381" (credit note)
- `ubl_jo_PaymentMeansType`: payment means
- `ubl_jo_InvoiceLineType`: line items with Jordan-specific tax totals
- `ubl_jo_TaxTotalType`: includes fixed+percent dual tax breakdown

### Party Identification
- Jordanian parties: schemeID `TN`, ID = VAT number (or `NO_VAT` if none)
- Foreign parties: schemeID `PN`
- Tax unregistered companies: empty party identification

### Refund Handling
Credit notes link to original invoice via `reversed_entry_id`. Line IDs are matched by product, name, price_unit, discount.

## Installation
Post-init hook `_post_init_hook` initializes defaults. Demo data: `demo/demo_company.xml`. Auto-installs with `l10n_jo`.

## Historical Notes
- **Odoo 18**: New module. Jordan mandated e-invoicing for VAT-registered businesses via JoFotara (phase-in from 2021). Odoo 18 provides the first complete integration.
- Maximum 9 decimal places distinguishes JO format from standard UBL
- Income taxpayer type: no tax values reported in invoice (tax-exempt income earners)