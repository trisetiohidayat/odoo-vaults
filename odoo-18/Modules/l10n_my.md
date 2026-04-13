---
Module: l10n_my
Version: 18.0
Type: l10n/malaysia
Tags: #odoo18 #l10n #accounting
---

# l10n_my

## Overview
Malaysia accounting localization providing the Malaysian chart of accounts and Sales and Service Tax (SST) structure. SST replaced GST in Malaysia in 2018. The module uses 6-digit account codes and supports Anglo-Saxon accounting. A companion module (`l10n_my_ubl_pint`) provides e-invoicing via Peppol PINT MY.

## Country
Malaysia

## Dependencies
- [Core/BaseModel](BaseModel.md) (account)
- `account` — core accounting module

## Key Models

### AccountChartTemplate (`account.chart.template`, classic extension)
- `_get_my_template_data()` — sets 6-digit account codes: receivable `l10n_my_1240`, payable `l10n_my_2211`, income `l10n_my_41`, expense `l10n_my_51`
- `_get_my_res_company()` — enables `anglo_saxon_accounting`, fiscal country `base.my`, bank prefix `1200`, cash prefix `1210`, transfer prefix `111220`, sale tax `l10n_my_tax_sale_10`

## Data Files
- `data/account_tax_report_data.xml` — **SST-02 (B2)** Sales and Service Tax report. Reports tax payable by rate (5% rate shown). Rooted on `account.generic_tax_report`, country `base.my`
- `migrations/1.1/end-migrate_update_taxes.py` — migration script to update tax rates
- `demo/demo_company.xml` — demo company data

## Chart of Accounts
6-digit account codes:
- `124xxx` — Receivables (`1240`, `1243` POS receivable)
- `221xxx` — Payables (`2211`)
- `41xxx` — Revenue/Income (`41`)
- `51xxx` — Expenses/Cost of Sales (`51`)
- `424xxx` — Other income (currency exchange gain `4240`)
- `524xxx` — Other expenses (currency exchange loss `5240`)

## Tax Structure
Malaysia uses **Sales and Service Tax (SST)**:
- `l10n_my_tax_sale_10` — Default sale SST (likely 10% standard rate)
- The module provides the SST-02 (B2) tax report structured around tax payable by rate category
- In Odoo 18 v1.1, tax definitions were updated

## Fiscal Positions
None explicitly defined in the template module.

## EDI/Fiscal Reporting
- SST-02 (B2) report via `account_tax_report_data.xml`
- Companion module [Modules/l10n_my_ubl_pint](l10n_my_ubl_pint.md) for Peppol PINT MY e-invoicing

## Installation
Install via Apps or during company setup by selecting Malaysia as country. Auto-installs with `account`. A post-install migration (`end-migrate_update_taxes`) updates tax definitions from v1.0.

## Historical Notes
- Version 1.1: Tax updates in Odoo 18.
- Malaysia replaced GST with SST effective September 1, 2018.
- Two types of SST: Sales Tax (manufactured goods, at import) and Service Tax (taxable services).
- The `l10n_my_ubl_pint` module provides Peppol PINT MY e-invoicing compliance for Malaysia's e-Invoice mandate.
