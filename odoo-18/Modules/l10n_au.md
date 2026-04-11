---
Module: l10n_au
Version: 18.0
Type: l10n/australia
Tags: #odoo18 #l10n #accounting #australia
---

# l10n_au — Australia Accounting

## Overview
Australian accounting localization module providing chart of accounts, GST tax structure, and country-specific invoice reporting. Australian companies use a 10% Goods and Services Tax (GST) applied to most goods and services.

## Country
Australia

## Dependencies
- account

## Key Models

### `AccountMove` (`account.move`)
- `_inherit = 'account.move'`
- Overrides `_get_name_invoice_report()` to use `l10n_au.report_invoice_document`
- Overrides `_get_automatic_balancing_account()` to manage DGST (Deferred GST) use case — single DGST line entries balance to the same DGST account rather than creating a balancing line

### `AccountPayment` (`account.payment`)
- `_inherit = 'account.payment'`
- Country-specific payment behavior

### `ResPartner` (`res.partner`)
- `_inherit = ['res.partner']`
- Australian partner bank details and GST handling

### `ResPartnerBank` (`res.partner.bank`)
- `_inherit = 'res.partner.bank'`
- Australian bank account type extensions

### `AccountChartTemplate` (AbstractModel)
- `_inherit = 'account.chart.template'`
- Defines 5-digit account code prefix
- Sets property accounts: receivable (`au_11200`), payable (`au_21200`), expense (`au_51110`), income (`au_41110`), stock input (`au_21210`), stock output (`au_11340`), stock valuation (`au_11330`), production cost (`au_11350`)
- Company defaults: `anglo_saxon_accounting = True`, fiscal year ends June 30 (`fiscalyear_last_month = 6`, `fiscalyear_last_day = 30`), default sale tax `au_tax_sale_10`, purchase tax `au_tax_purchase_10_service`

## Data Files
- `data/account_tax_report_data.xml` — Australian BAS tax report structure
- `data/account_tax_template_data.xml` — GST tax templates (10% standard rate)
- `data/res_currency_data.xml` — Regional currency activation (if applicable)
- `data/account.account.tag.csv` — Account tags for BAS reporting
- `views/menuitems.xml`, `views/report_invoice.xml`, `views/res_company_views.xml`, `views/res_partner_bank_views.xml`

## Chart of Accounts
5-digit account codes. Key prefixes: 1xxxx (Assets), 2xxxx (Liabilities), 4xxxx (Revenue), 5xxxx (Expenses), 6xxxx (Other income/expenses). Includes dedicated stock accounts for Anglo-Saxon accounting.

## Tax Structure
- **GST 10%** — Standard rate on most supplies
- Tax reports: Business Activity Statement (BAS) compliant
- DGST (Deferred GST) account mechanism handles GST on cash basis

## Fiscal Positions
Standard Australian fiscal positions for inter-state transactions handled via standard Odoo fiscal position mapping.

## Installation
Auto-installs with `account`. Applied when company country is set to Australia. Sets fiscal year start (July 1) automatically.

## Historical Notes
Version 1.1 in Odoo 18 (vs 1.0 in Odoo 17). Added DGST automatic balancing account logic to handle single-line GST journal entries correctly. Angular front-end invoice report `l10n_au.report_invoice_document` renders GST-compliant invoices.