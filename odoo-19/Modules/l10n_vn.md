---
type: module
module: l10n_vn
tags: [odoo, odoo19, l10n, localization, vietnam]
created: 2026-04-06
---

# Vietnam Localization (l10n_vn)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Vietnam - Accounting |
| **Technical** | `l10n_vn` |
| **Category** | Localization / Account Charts |
| **Country** | Vietnam |
| **Author** | General Solutions |
| **Version** | 2.0.3 |
| **License** | LGPL-3 |
| **Countries** | Vietnam (VN) |

## Description

Vietnamese accounting localization module providing a comprehensive chart of accounts, tax structure, and banking information for companies operating in Vietnam. The module is based on the Vietnamese Accounting Standard (VAS) following Circular No. 200/2014/TT-BTC.

Key features:
- Chart of accounts following Vietnamese Accounting Standard (VAS)
- Vietnamese bank information updated by State Bank of Vietnam
- VietQR support for invoice QR payments
- Tax report templates for Vietnamese tax compliance

**Credits**: General Solutions, Trobz, and Jean Nguyen - The Bean Family (for VietQR implementation)

## Dependencies

| Module | Purpose |
|--------|---------|
| [Modules/account](Modules/account.md) | Core accounting |
| [Modules/account_qr_code_emv](Modules/account_qr_code_emv.md) | EMV QR code (VietQR support) |
| [Modules/base_iban](Modules/base_iban.md) | IBAN bank account support |

## Key Models

### `account.chart.template` (template_vn.py)
Extends chart of accounts with Vietnamese-specific template data:
- Vietnamese account code structure
- Tax accounts for Vietnam's tax system
- Inventory valuation accounts per VAS requirements

### `account.move` (account_move.py)
Extends `account.move` with Vietnamese fields:
- **l10n_vn.invoice_type**: Invoice type classification (e.g., invoice series/number)
- **l10n_vn_tax_type**: Tax type classification

### `res.bank` (res_bank.py)
Extends bank model with Vietnamese banking details:
- Full bank branch network of Vietnam
- BIC/SWIFT codes for Vietnamese banks
- State Bank of Vietnam certified data

## Country-Specific Features

### Vietnamese Tax Structure
- **VAT (Value Added Tax)**: Standard rates of 0%, 5%, 8%, 10% (exemptions apply)
- Invoice type classifications required by Vietnamese law
- Tax report configurations for Vietnam's tax authority

### VietQR Payment
- EMV QR code generation compatible with VietQR standard
- Support for QR-based payment identification
- Bank account information encoded in QR format

### Vietnamese Accounting Standards
- Follows Circular No. 200/2014/TT-BTC
- Account code structure for Vietnamese businesses
- Fiscal position templates for VAT handling

## Data Files

- `data/account_tax_report_data.xml` - Vietnamese tax report templates
- `views/account_move_views.xml` - Invoice view customization
- `views/res_bank_views.xml` - Bank configuration views
- `demo/demo_company.xml` - Demo company data

## Related

- [Modules/account](Modules/account.md) - Core accounting module
- [Modules/l10n_vn_edi_viettel](Modules/l10n_vn_edi_viettel.md) - Vietnam EDI e-invoicing via Viettel SInvoice

## See Also

- [Vietnam E-invoicing Portal](https://vinvoice.vn)
- [State Bank of Vietnam](https://sbv.gov.vn)
