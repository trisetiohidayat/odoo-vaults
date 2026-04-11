---
Module: l10n_my_edi_extended
Version: 18.0
Type: l10n/edi
Tags: #odoo18 #l10n #edi #malaysia #myinvois
---

# l10n_my_edi_extended

## Overview
Extends [[Modules/l10n_my_edi]] with three enhanced capabilities:
1. **Self-billing support**: allows buyers to generate invoices on behalf of suppliers
2. **QR code rendering**: embeds the MyInvois QR code in PDF reports
3. **Foreign customer TIN management**: better validation and display of non-Malaysian TINs

## EDI Format / Standard
Same as [[Modules/l10n_my_edi]] — MyInvois UBL 2.1 format.

## Dependencies
- `l10n_my_edi` — Base MyInvois module (auto-installs it)

## Key Models

| Class | _name | _inherit | Description |
|---|---|---|---|
| `AccountEdiXmlUBLMyInvoisMY` | `account.edi.xml.ubl_myinvois_my` | `account.edi.xml.ubl_myinvois_my` | Extended UBL generator with self-billing fields and foreign TIN handling |
| `AccountMoveLine` | `account.move.line` | `account.move.line` | Self-billing line identification |
| `AccountMove` | `account.move` | `account.move` | Self-billing flag, foreign TIN fields |
| `AccountMoveSend` | `account.move.send` | `abstract.model` | Enhanced send wizard |
| `ResPartner` | `res.partner` | `res.partner` | Foreign TIN and identification fields |

## Data Files
- `views/account_move_view.xml` — Extended invoice form with self-billing fields
- `views/account_portal_templates.xml` — Portal access for extended fields
- `views/report_invoice.xml` — MyInvois QR code on PDF invoice
- `views/res_partner_view.xml` — Partner foreign TIN fields

## How It Works

### Self-Billing
When the buyer issues an invoice on behalf of a supplier:
- Invoice flagged as self-billed in UBL
- Supplier TIN validated against MyInvois registry
- Submission includes both buyer and supplier identification

### QR Code
MyInvois QR code generated from invoice UUID and validation data. Rendered in invoice PDF via `report_invoice.xml` QWeb template.

### Foreign TIN
Non-Malaysian customer TINs validated and displayed with country prefix. Allows Malaysian companies to correctly report B2B invoices with foreign suppliers.

## Installation
Auto-installs with `l10n_my_edi`. No separate installation needed.

## Historical Notes
- **Odoo 18**: New module. Provides the extended MyInvois features that are optional but recommended for full compliance scenarios.