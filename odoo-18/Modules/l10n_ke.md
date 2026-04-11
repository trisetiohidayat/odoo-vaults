---
Module: l10n_ke
Version: 18.0
Type: l10n/kenya
Tags: #odoo18 #l10n #accounting #east_africa
---

# l10n_ke

## Overview
Kenya accounting localization — chart of accounts, VAT tax structure at 16% and 8% reduced rates, withholding tax report, KRA item codes, and fiscal positions. One of the most detailed Africa localization modules with specific Kenya Revenue Authority (KRA) reporting requirements.

## Country
Republic of Kenya — country code `ke`

## Dependencies
- account

## Key Models

### `AccountChartTemplate` (`account.chart.template`)
Inherits `account.chart.template`. Template prefix: `'ke'`.

Sets `code_digits: 6`, receivable at `ke1100`, payable at `ke2100`, expense categ at `ke5001`, income categ at `ke4001`, stock valuation at `ke1001`, stock output at `ke100120`, stock input at `ke100110`.

Company defaults: Anglo-Saxon accounting enabled, fiscal country `base.ke`, default sale tax `ST16` (16%), default purchase tax `PT16` (16%), tax eligibility on invoices enabled.

### `L10nKeItemCode` (`l10n_ke.item.code`)
Standalone model. KRA-defined item codes that justify a given tax rate or exemption on a product/service.

Fields:
- `code` (Char) — KRA item code
- `description` (Char) — description of the item
- `tax_rate` (Selection: `'C'` = Zero Rated, `'E'` = Exempted, `'B'` = Taxable at 8%) — maps item to reduced tax rate
- `display_name` — computed as `code description` via `_compute_display_name()`
- `_rec_names_search` on `['code', 'description']`

### `AccountTax` (`account.tax`)
Inherits `account.tax`. Adds `l10n_ke_item_code_id` — Many2one to `l10n_ke.item.code`. The KRA item code is linked to a tax and is reset (onchange) when the tax amount changes.

### `AccountMove` (`account.move`)
Inherits `account.move`. Adds:
- `l10n_ke_wh_certificate_number` (Char) — customer withholding certificate number for withholding tax transactions
- `l10n_ke_wh_certificate_date` (Date) — date of the withholding certificate

### `ResCompany` (`res.company`)
Inherits `res.company`. Adds `l10n_ke_oscu_is_active` (Boolean, computed) — indicates whether OSCU (Odoo State Cash Unit) flows are active. Computed field is overridden in Odoo Enterprise.

## Data Files
- `views/account_move_views.xml` — account move view extensions
- `views/account_tax_views.xml` — tax view with KRA item code field
- `views/l10n_ke_item_code_views.xml` — KRA item code model views
- `data/l10n_ke.item.code.csv` — KRA defined item codes (CSV data)
- `data/account_tax_report_data.xml` — VAT tax report with Box 1–12 structure: general rate 16%, other rate 8%, zero-rated, exempt, VAT payable, VAT payable adjustments, input VAT, and more
- `data/account_wh_tax_report_data.xml` — withholding tax report structure
- `security/ir.model.access.csv` — access rights for `l10n_ke.item.code`
- `demo/demo_company.xml` — Kenya demo company

## Chart of Accounts
6-digit Kenyan chart of accounts (e.g., `ke1100` receivable, `ke2100` payable). Not based on a standard international framework but tailored to Kenyan business and KRA requirements.

## Tax Structure
- VAT: 16% standard rate (ST16), 8% reduced rate (for specific sectors like sugar, maize), 0% zero-rated, exempt
- Withholding tax: WHT on dividends (0%), interest (15%/20%/25%), royalties (20%), management/professional fees (20%/30%), rental income (10%), among others
- KRA item codes (`l10n_ke.item.code`) link products to specific tax rates for e-tax filing

VAT report (Box 1–12): Standard rate sales/purchases, other rate, zero-rated, exempt, reverse charge, and VAT payable/input VAT sections.

## Fiscal Positions
Defined in `account_tax_report_data.xml`.

## Installation
`auto_install: ['account']` — automatically installed with account.

## Historical Notes
- Version 1.0 in Odoo 18
- Kenya uses the KRA iTax system for filing; the withholding tax report supports WHT certificate generation
- OSCU (Odoo State Cash Unit) is an Enterprise module feature
