---
Module: l10n_ng
Version: 18.0
Type: l10n/nigeria
Tags: #odoo18 #l10n #accounting #west_africa
---

# l10n_ng

## Overview
Nigeria accounting localization — chart of accounts, VAT tax report, and withholding VAT report for Nigerian companies. Uses `base_vat` for Nigerian TIN (Tax Identification Number) support.

## Country
Federal Republic of Nigeria — country code `ng`

## Dependencies
- base_vat

## Key Models

### `AccountChartTemplate` (`account.chart.template`)
Inherits `account.chart.template`. Template prefix: `'ng'`.

## Data Files
- `data/tax_report.xml` — Nigerian VAT report with transaction summary (Section A: No. of branches, total sales, purchases, VAT collected/paid, Section B: VAT payable calculation) and item-level tags
- `data/withholding_vat_report.xml` — withholding tax on supplies and services (WHT at source — contractors, rent, dividends, interest, royalties, management fees)
- `demo/demo_company.xml` — Nigeria demo company

## Chart of Accounts
Nigerian chart of accounts with `ng` prefix. Nigeria follows the Statement of Accounting Standards (SAS) issued by the Nigerian Accounting Standards Board (NASB), aligned with IFRS. Not a SYSCOHADA country.

## Tax Structure
- VAT at 7.5% standard rate (increased from 5% in February 2020)
- WHT (Withholding Tax): Applied on payment for services, dividends, interest, rent, royalties, commissions at 5%–10% depending on the transaction type and recipient
- Companies Income Tax (CIT): 30% for companies (20% for small companies)
- Tertiary Education Tax (TET): 2%
- Nigeria Police Trust Fund Levy: 0.005% (employers)
- Lagos State Infrastructure Maintenance Charge: where applicable

VAT report and withholding VAT report defined in XML data files.

## Fiscal Positions
Defined in tax report data.

## Installation
Standard installation (no `auto_install` specified).

## Historical Notes
- Version 1.0 in Odoo 18
- Nigeria's FIRS (Federal Inland Revenue Service) administers VAT; state-level taxes (e.g., Lagos State) may also apply
- VAT rate has changed over time: 5% (pre-2020) → 7.5% (2020 onwards)
