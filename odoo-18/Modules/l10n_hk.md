---
Module: l10n_hk
Version: 18.0
Type: l10n/hong-kong
Tags: #odoo18 #l10n #accounting #hong-kong
---

# l10n_hk — Hong Kong Accounting

## Overview
Hong Kong accounting localization module providing chart of accounts, enabling Hong Kong companies to use Odoo accounting with locale-specific accounts. Hong Kong has no GST/VAT system, making this module lighter than India or China localizations. Depends on `account_qr_code_emv` for QR-code based payment support.

## Country
Hong Kong SAR, China

## Dependencies
- account_qr_code_emv
- account

## Key Models

### `ResPartnerBank` (`res.partner.bank`)
- `_inherit = 'res.partner.bank'`
- Hong Kong-specific bank account fields and validation

### `AccountChartTemplate` (AbstractModel)
- `_inherit = 'account.chart.template'`
- 6-digit account code prefix
- Property accounts: receivable (`l10n_hk_1240`), payable (`l10n_hk_2211`), income (`l10n_hk_41`), expense (`l10n_hk_51`)
- Company defaults: `anglo_saxon_accounting = True`, fiscal country `base.hk`, bank prefix `1200`, cash prefix `1210`, transfer prefix `111220`, POS receivable `l10n_hk_1243`, currency exchange gain `l10n_hk_4240`, loss `l10n_hk_5240`, early pay discount gain `l10n_hk_4250`, loss `l10n_hk_5250`

## Data Files
- `data/account_chart_template_data.xml` — Hong Kong account structure
- `views/res_bank_views.xml` — Bank view extensions
- `demo/demo_company.xml` — Demo company for Hong Kong

## Chart of Accounts
6-digit codes in standard Odoo pattern. No GST/VAT accounts — Hong Kong uses a simple profit/loss structure aligned with Hong Kong Financial Reporting Standards (HKFRS).

## Tax Structure
**No GST/VAT** — Hong Kong operates on a direct tax system (Salaries Tax, Profits Tax, Property Tax). No VAT or sales tax equivalents. This module provides accounts for standard HKFRS compliance.

## Fiscal Positions
Standard Odoo fiscal position mechanism. Hong Kong has no inter-region tax distinctions, so fiscal positions are minimal.

## EDI/Fiscal Reporting
No EDI module in this package. However, QR-code payment integration via `account_qr_code_emv` enables EMV QR standards commonly used in Hong Kong (FPS — Faster Payment System).

## Installation
Auto-installs with `account`. Applied when company country is Hong Kong.

## Historical Notes
Version 1.0 in Odoo 18. Simple, focused module leveraging `account_qr_code_emv` for payment integration.