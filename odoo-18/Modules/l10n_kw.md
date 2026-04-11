---
Module: l10n_kw
Version: 18.0
Type: l10n/kuwait
Tags: #odoo18 #l10n #accounting #kuwait #gcc
---

# l10n_kw

## Overview
Kuwait accounting localization — chart of accounts for Kuwaiti companies.

## Country
State of Kuwait — country code `kw`

## Dependencies
- account

## Key Models

### `AccountChartTemplate` (`account.chart.template`)
Inherits `account.chart.template`. Template prefix: `'kw'`.

## Data Files
- `demo/demo_company.xml` — Kuwait demo company

## Chart of Accounts
Kuwait chart of accounts with `kw` prefix.

## Tax Structure
No tax data or report files in this module. Kuwait does not currently have VAT (as of Odoo 18 documentation snapshot). Note: Kuwait is not a GCC VAT implementing state (only UAE, Saudi Arabia, and Bahrain implemented VAT as of 2024).

## Fiscal Positions
Not defined in this module.

## Installation
Standard installation.

## Historical Notes
- Version 1.0 in Odoo 18
