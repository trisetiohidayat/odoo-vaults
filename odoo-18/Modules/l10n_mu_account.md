---
Module: l10n_mu_account
Version: 18.0
Type: l10n/mauritius
Tags: #odoo18 #l10n #accounting #southern_africa
---

# l10n_mu_account

## Overview
Mauritius accounting localization — chart of accounts, VAT tax structure, fiscal positions, and custom invoice report for Mauritian companies.

## Country
Republic of Mauritius — country code `mu`

## Dependencies
- account

## Key Models

### `AccountChartTemplate` (`account.chart.template`)
Inherits `account.chart.template`. Template prefix: `'mu'`.

### `AccountMove` (`account.move`)
Inherits `account.move`. Overrides `_get_name_invoice_report()` — returns `l10n_mu_account.report_invoice_document` custom Mauritius invoice layout when company is Mauritian.

### `BaseDocumentLayout` (`base.document.layout`)
Inherits `base.document.layout`. Used for company document layout configuration.

## Data Files
- `data/tax_report-mu.xml` — Mauritius tax/VAT report
- `views/report_invoice.xml` — Mauritius-specific invoice report template
- `demo/demo_company.xml` — Mauritius demo company

## Chart of Accounts
Mauritius chart of accounts with `mu` prefix. Mauritius follows IFRS-aligned Mauritian Accounting Standards (MAS). Not a SYSCOHADA country.

## Tax Structure
VAT at 15% standard rate. Income tax at 15% flat rate for companies. No capital gains tax in Mauritius. MRA (Mauritius Revenue Authority) administers taxes.

## Fiscal Positions
Defined in template data.

## Installation
Standard installation.

## Historical Notes
- Version 1.0 in Odoo 18
- Mauritius is a major financial services hub; the country uses IFRS as the basis for accounting standards
