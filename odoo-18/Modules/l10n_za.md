---
Module: l10n_za
Version: 18.0
Type: l10n/south_africa
Tags: #odoo18 #l10n #accounting #southern_africa
---

# l10n_za

## Overview
South Africa accounting localization — chart of accounts and SARS VAT-ready tax structure. Developed by Paradigm Digital. South Africa follows IFRS-aligned International Financial Reporting Standards (IFRS) as the basis for its accounting standards.

## Country
Republic of South Africa — country code `za`

## Dependencies
- account
- base_vat

## Key Models

### `AccountChartTemplate` (`account.chart.template`)
Inherits `account.chart.template`. Template prefix: `'za'`.

## Data Files
- `data/account.account.tag.csv` — account tags for South African tax reporting
- `data/account_tax_report_data.xml` — SARS VAT 201 return report with sections for standard rate, zero-rated, exempt supplies, and output/input VAT calculations (Total A - Total B)
- `demo/demo_company.xml` — South Africa demo company

## Chart of Accounts
South African chart of accounts with `za` prefix. South Africa does not have a mandatory uniform chart of accounts. Companies use IFRS-aligned accounts. The localization provides a generic chart.

## Tax Structure
- VAT at 15% standard rate (SARS — South African Revenue Service)
- Zero-rated and exempt supplies categories
- VAT 201 return: Output tax sections ([1] Standard Rate, [4A] Other exports, [6] Dividends/Interest, [9] Local services, [11] Stratum 1 mining, [12] other) and Input tax sections
- Companies Income Tax (CIT): 28% for companies
- Capital Gains Tax: integrated with income tax

VAT report structure (from XML): Total A = [4] VAT on sales, [4A] VAT on other exports, (([6]+[7])*0.6) for dividends/interest, [11], [12]; Total B = Input VAT deducted. Result = Total A - Total B = VAT payable/refundable.

## Fiscal Positions
Defined in `account_tax_report_data.xml`.

## Installation
`auto_install: ['account']` — automatically installed with account.

## Historical Notes
- Version 1.0 in Odoo 18
- Developed by Paradigm Digital (South African Odoo partner)
- South Africa does not have a GST/VAT withholding system; VAT is collected and remitted by vendors via the VAT 201 return
- `base_vat` dependency provides TIN/company registry validation for South African entities
