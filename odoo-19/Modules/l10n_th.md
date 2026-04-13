---
type: module
module: l10n_th
tags: [odoo, odoo19, l10n, localization, thailand]
created: 2026-04-06
---

# Thailand Localization (l10n_th)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Thailand - Accounting |
| **Technical** | `l10n_th` |
| **Category** | Localization / Account Charts |
| **Country** | Thailand |
| **Author** | Almacom (http://almacom.co.th/) |
| **Version** | 2.0 |
| **License** | LGPL-3 |
| **Countries** | Thailand (TH) |

## Description

Thai accounting localization providing a chart of accounts and tax templates for companies operating in Thailand. The module is based on Thai accounting standards and includes support for Thai VAT (Value Added Tax).

The module uses the `account_qr_code_emv` dependency to support QR payment codes on invoices, which is widely used in Thailand for bill payments.

## Dependencies

| Module | Purpose |
|--------|---------|
| [Modules/account](odoo-18/Modules/account.md) | Core accounting |
| [Modules/account_qr_code_emv](odoo-18/Modules/account_qr_code_emv.md) | EMV QR code generation for Thai QR payments |

## Key Models

### `account.chart.template` (template_th.py)
Extends the standard chart of accounts template with Thai-specific account codes and settings.

**Company Defaults**:
- Sets Thai fiscal year configuration
- Configures Thai tax accounts for VAT
- Sets up account code digits for Thai chart

### `account.move` (account_move.py)
Extends `account.move` with Thai-specific fields:

- **l10n_th_addr_branch**: Branch address information on invoices
- **l10n_th_tax_id**: Thai Tax Identification Number (TIN) display

### `res.partner` (res_partner.py)
Extends partner model:

- **l10n_th_branch_code**: Branch code field for Thai companies (used for branch identification)
- **l10n_th_addr_branch**: Registered branch address

### `ir.actions.report` (ir_actions_report.py)
Custom report actions for Thai invoice formatting.

## Country-Specific Features

### Thai Tax Structure
- **VAT (Value Added Tax)**: Standard rate typically at 7% (subject to change)
- Thai tax reports for VAT filing
- Support for both included and excluded tax fiscal positions

### QR Code Payments
- EMV QR code generation for Thai QR payment standard
- Compatible with PromptPay and other Thai QR payment systems

### Address Format
- Thai address formatting with branch identification
- Support for district, sub-district, province hierarchy

## Data Files

- `data/account_tax_report_data.xml` - Thai tax report templates
- `views/report_invoice.xml` - Invoice report customization
- `demo/demo_company.xml` - Demo company data

## Post-Init Hook

- `_preserve_tag_on_taxes`: Preserves account tags on taxes after installation

## Related

- [Modules/account](odoo-18/Modules/account.md) - Core accounting module
- [Modules/account_qr_code_emv](odoo-18/Modules/account_qr_code_emv.md) - QR code generation
