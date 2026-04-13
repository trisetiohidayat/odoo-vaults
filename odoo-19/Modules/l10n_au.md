---
type: module
module: l10n_au
tags: [odoo, odoo19, l10n, localization, australia]
created: 2026-04-06
---

# Australia Localization (l10n_au)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Australia - Accounting |
| **Technical** | `l10n_au` |
| **Category** | Localization / Account Charts |
| **Country** | Australia |
| **Author** | Odoo S.A. |
| **Version** | 1.1 |
| **License** | LGPL-3 |
| **Countries** | Australia (AU) |

## Description

Australian accounting localization providing BAS (Business Activity Statement) chart of accounts and taxes. The module activates regional currencies, sets up Australian GST (Goods and Services Tax) taxes, and includes comprehensive BAS reporting templates.

Australia has a federal GST system (10% standard rate) with quarterly or monthly BAS reporting obligations.

## Dependencies

| Module | Purpose |
|--------|---------|
| [Modules/account](modules/account.md) | Core accounting |

## Key Models

### `account.chart.template` (template_au.py)
Extends chart of accounts with Australian-specific data.

**Template Data** (`_get_au_template_data`):
- `code_digits`: 5
- `property_account_receivable_id`: `au_11200` (Accounts Receivable)
- `property_account_payable_id`: `au_21200` (Accounts Payable)
- `property_stock_valuation_account_id`: `au_11330` (Stock Valuation)
- `property_stock_account_production_cost_id`: `au_11350` (Production Costs)

**Company Defaults** (`_get_au_res_company`):
- `anglo_saxon_accounting`: True
- `account_fiscal_country_id`: `base.au`
- `bank_account_code_prefix`: `1111`
- `cash_account_code_prefix`: `1113`
- `transfer_account_code_prefix`: `11170`
- `fiscalyear_last_month`: `6` (June 30 fiscal year-end)
- `fiscalyear_last_day`: `30`
- `account_sale_tax_id`: `au_tax_sale_10`
- `account_purchase_tax_id`: `au_tax_purchase_10_service`
- `account_stock_valuation_id`: `au_11310`

### `res.partner` (res_partner.py)
Extends `res.partner`:
- `_get_company_registry_labels()`: Adds `ACN` label for Australian Company Number (AU)
- ABN and ACN display support

## Country-Specific Features

### Australian Tax Structure
- **GST (Goods and Services Tax)**: 10% standard rate
- **Luxury Car Tax (LCT)**: 33% on luxury vehicles above threshold
- **Wine Equalisation Tax (WET)**: 29% on wine products
- **Fuel Tax Credits**: Input tax credits for fuel

### BAS (Business Activity Statement) Reporting
The module includes comprehensive BAS report templates:
- **BAS A**: Total sales
- **BAS C**: Total purchases
- **BAS D**: GST on sales
- **BAS F**: GST on purchases
- **BAS G**: Total GST
- **BAS U**: GST installments
- **BAS V**: Export sales
- **BAS W**: Import GST
- **BAS X**: Wine equalisation tax
- **BAS Y**: Luxury car tax
- **Master BAS**: Complete BAS form

### ABN (Australian Business Number)
- 11-digit unique identifier
- Required on all tax invoices
- Verified against ABR (Australian Business Register)

### ACN (Australian Company Number)
- 9-digit number assigned by ASIC
- Required for all Australian companies
- Displayed on company forms

### Australia Tax Invoice Requirements
- ABN of supplier and recipient
- "Tax Invoice" statement
- Date and invoice number
- Description, quantity, and value of supply
- GST amount or statement that total includes GST

### Financial Year
- Australia uses a 1 July - 30 June financial year
- June 30 is the standard fiscal year-end

## Data Files

- `data/account_tax_report_data.xml` - BAS report structures
- `data/account_tax_template_data.xml` - Tax templates
- `data/bas_a.xml` through `data/bas_y.xml` - Individual BAS form templates
- `data/master_bas.xml` - Complete BAS master form
- `data/res_currency_data.xml` - AUD currency
- `data/account.account.tag.csv` - Account tags
- `views/menuitems.xml` - Navigation menus
- `views/report_invoice.xml` - Invoice report
- `views/res_company_views.xml` - Company configuration
- `views/res_partner_bank_views.xml` - Bank account views
- `demo/demo_company.xml` - Demo company
- `demo/res_bank.xml` - Demo bank data

## Related

- [Modules/account](modules/account.md) - Core accounting module
- [Modules/l10n_anz_ubl_pint](modules/l10n_anz_ubl_pint.md) - ANZ UBL PINT format for e-invoicing
- [ATO](https://www.ato.gov.au)
- [ABR](https://abr.business.gov.au)
