---
Module: l10n_jo
Version: 18.0
Type: l10n/jordan
Tags: #odoo18 #l10n #accounting #jordan
---

# l10n_jo

## Overview
Jordan accounting localization — chart of accounts, tax structure, tax report, and fiscal position mappings for Jordanian companies.

## Country
Hashemite Kingdom of Jordan — country code `jo`

## Dependencies
- account

## Key Models

### `AccountChartTemplate` (`account.chart.template`)
Inherits `account.chart.template`. Template prefix: `'jo'`. Provides `_get_jo_standard_template_data()` (standard accounting template).

Note: File named `template_jo_standard.py` — Jordan's accounting follows Jordanian Accounting Standards (JAS) which are IAS/IFRS-based.

## Data Files
- `data/account_tax_report_data.xml` — tax report for Jordan
- `demo/demo_company.xml` — Jordan demo company
- `demo/demo_partner.xml` — Jordan demo partner

## Chart of Accounts
Jordan chart of accounts with `jo` prefix following Jordanian Accounting Standards.

## Tax Structure
Sales Tax at 16% (standard rate). Also zero-rated and exempt categories. Fiscal positions defined.

## Fiscal Positions
Defined in `account_tax_report_data.xml`.

## Installation
Standard installation.

## Historical Notes
- Version 1.0 in Odoo 18
- Jordan's Income Tax Law and Sales Tax Law (GST-type tax at 16%)
