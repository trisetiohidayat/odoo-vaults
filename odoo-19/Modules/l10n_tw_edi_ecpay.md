---
type: module
module: l10n_tw_edi_ecpay
tags: [odoo, odoo19, l10n, localization, taiwan, edi, einvoice]
created: 2026-04-06
---

# Taiwan EDI - ECPay E-invoicing (l10n_tw_edi_ecpay)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Taiwan - E-invoicing |
| **Technical** | `l10n_tw_edi_ecpay` |
| **Category** | Localization / EDI |
| **Country** | Taiwan |
| **Author** | Odoo S.A. |
| **Version** | 1.0 |
| **License** | LGPL-3 |
| **Countries** | Taiwan (TW) |

## Description

Taiwan e-invoicing module that integrates with ECPay, one of Taiwan's approved e-invoice platform operators. The module enables businesses to issue, transmit, and manage electronic invoices in compliance with Taiwan's e-invoice regulations set by the Ministry of Finance.

Taiwan's e-invoice system (電子發票) requires businesses to issue e-invoices for B2B and B2C transactions, with transmission through approved e-invoice platforms.

## Dependencies

| Module | Purpose |
|--------|---------|
| [Modules/l10n_tw](odoo-18/Modules/l10n_tw.md) | Base Taiwanese accounting localization |
| [Modules/base_vat](odoo-17/Modules/base_vat.md) | Business/Uniform Number validation |

## Key Models

### `l10n_tw_edi.invoice` (account_move.py)
Extends `account.move` with ECPay e-invoice fields:
- E-invoice status (unsent, sent, validated, voided)
- ECPay invoice number (20-digit format)
- Carrier ID (爱心码) for B2C invoices
- Tax breakdown per Taiwan tax requirements

### `account.move` (account_move.py)
Extends invoice model:
- E-invoice issuance and voiding workflow
- ECPay API integration for invoice operations
- Automatic invoice number generation

### `account.move.send` (account_move_send.py)
Extends invoice sending to include ECPay submission.

### `account.move.line` (account_move_line.py)
Line-level tax configuration for Taiwan tax types:
- Tax-exempt goods classification
- Zero-rated supply identification
- Zero-tax classification for specific items

### `res.company` (res_company.py)
Company configuration for ECPay:
- ECPay merchant ID
- API key configuration
- Company seal/ chop information

### `res.config.settings` (res_config_settings.py)
Settings for ECPay e-invoice configuration:
- API credentials
- Environment selection (production/test)
- Auto-issue settings

### `res.partner` (res_partner.py)
Extends partner with Taiwan e-invoice fields:
- **Uniform Number** (統一編號): Business registration number
- **Carrier ID** (愛心碼): For B2C e-invoice carrier binding
- Citizen digital certificate support

## Country-Specific Features

### Taiwan E-invoice System
Taiwan's e-invoice system (電子發票) under the Business Entity Invoice Act:
- **B2B Invoices**: E-invoices between businesses, transmitted directly
- **B2C Invoices**: With carrier (捐贈碼/爱心码) for lottery donations
- 20-digit invoice numbers
- Monthly reporting to tax authority

### ECPay Integration
- Invoice issuance API
- Invoice void/cancel API
- Invoice query and status check
- Batch invoice operations
- B2C carrier binding (捐贈碼)

### Taiwan Tax Classification
- **Taxable**: Standard 5% business tax
- **Zero-rated**: 0% for exports
- **Tax-exempt**: Exempt from business tax
- **Tax-free**: Specific goods/services not subject to business tax

### Invoice Types
- General e-invoice (一般電子發票)
- Special tax-exempt invoice (特種統一發票)
- Carrier e-invoice (愛心碼電子發票)

## Data Files

- `security/ir.model.access.csv` - Access rights
- `views/res_config_setting_view.xml` - Settings view
- `views/account_tax.xml` - Tax form updates
- `views/account_move_view.xml` - Invoice form updates
- `views/account_move_reversal_view.xml` - Invoice reversal view
- `views/l10n_tw_edi_invoice_cancel_view.xml` - Cancellation view
- `views/l10n_tw_edi_invoice_print_view.xml` - Invoice print format

## Uninstall Hook

Cleans up ECPay-specific data and API configurations when the module is uninstalled.

## Related

- [Modules/l10n_tw](odoo-18/Modules/l10n_tw.md) - Base Taiwanese accounting
- [Modules/l10n_tw_edi_ecpay_website_sale](odoo-19/Modules/l10n_tw_edi_ecpay_website_sale.md) - E-commerce e-invoice bridge
- [Modules/account_edi](odoo-17/Modules/account_edi.md) - EDI framework
