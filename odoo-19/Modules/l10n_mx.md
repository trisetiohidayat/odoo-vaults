# l10n_mx - Mexico Accounting

## Overview
- **Name:** Mexico - Accounting
- **Country:** Mexico (MX)
- **Category:** Accounting/Localizations/Account Charts
- **Version:** 2.3
- **Author:** Vauxoo
- **License:** LGPL-3
- **Dependencies:** `account`
- **Auto-installs:** `account`

## Description
Minimal accounting configuration for Mexico. Provides a minimal chart of accounts and tax structure compliant with SAT (Sistema de Administracion Tributaria) requirements. Does not include full EDI — companion modules handle electronic invoicing.

## Models

### account.chart.template (AbstractModel)
Inherits `account.chart.template`:
- **Template `mx`:**
  - Code digits: 9
  - Enables Anglo-Saxon accounting: `anglo_saxon_accounting: True`
  - Display invoice amount total in words: `display_invoice_amount_total_words: True`
  - Receivable: `cuenta105_01`, Payable: `cuenta201_01`
  - Stock valuation: `cuenta115_01`
  - Cash basis base account: `cuenta801_01_99`
  - Bank prefix: `102.01.0`, Cash: `101.01.0`, Transfer: `102.01.01`
  - Default sale tax: 12% VAT (`tax12`), purchase: 16% (`tax14`)
  - Creates tax cash basis journal `cbmx` (type: general, code: CBMX)
  - Income re-invoicing account: `cuenta402_04`
  - Discount account: `cuenta402_01`

### res.bank (Inherit)
Extends `res.bank`:
- **l10n_mx_edi_code:** 3-digit ABM code identifying Mexican banking institutions (Asociacion de Bancos de Mexico)
- **fiscal_country_codes:** Stores the fiscal country codes for the current companies

### res.partner.bank (Inherit)
Extends `res.partner.bank`:
- **l10n_mx_edi_clabe:** CLABE (Clave Bancaria Estandarizada) — 18-digit standardized banking cipher for Mexico

## Post-Init Hook
`_enable_group_uom_post_init` — enables the UoM group after installation.

## Data Files
- `data/account.account.tag.csv` — SAT account classification tags
- `data/account_report_diot.xml` — DIOT report (Declaracion Informativa de Operaciones con Terceros)
- `data/res_bank_data.xml` — Mexican bank data
- `data/l10n_mx_uom.xml` — Mexican-specific UoMs
- Views: partner, bank, account, tax, config settings

## DIOT Report
The DIOT is a mandatory monthly informational return for Mexican companies — declares operations with third parties.

## Related Modules
- **l10n_mx_hr** — Mexican HR extension
