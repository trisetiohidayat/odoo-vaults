# l10n_at - Austria Accounting

## Overview
- **Name:** Austria - Accounting
- **Country:** Austria (AT)
- **Category:** Accounting/Localizations/Account Charts
- **Version:** 3.2.1
- **Author:** WT-IO-IT GmbH / Wolfgang Taferner
- **License:** LGPL-3
- **Dependencies:** `account`, `account_edi_ubl_cii`, `base_iban`, `base_vat`, `l10n_din5008`
- **Auto-installs:** `account`

## Description
Austrian accounting localization based on Einheitskontenrahmen 2010 (EKR 2010). Provides:
- Austrian general chart of accounts
- VAT templates for sales and purchases
- Tax templates
- Fiscal positions for Austrian legislation
- Tax reports U1/U30 (VAT declarations)

## Data Files
No Python models — fully data-driven. Key data files:
- `data/account_account_tag.xml` — Austrian account classification tags
- `data/account.account.tag.csv` — Account tag CSV data
- `data/account_tax_report_data.xml` — Austrian VAT report (U1/U30)
- `demo/demo_company.xml` — Demo company

## Tax Reports
- **U1/U30** — Austrian VAT declaration format (tax report data)

## Notes
- Shares DIN 5008 document standard with Germany and Switzerland (`l10n_din5008`)
- Very similar structure to German SKR-style accounting
