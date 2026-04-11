# l10n_nl - Netherlands Accounting

## Overview
- **Name:** Netherlands - Accounting
- **Country:** Netherlands (NL)
- **Category:** Accounting/Localizations/Account Charts
- **Version:** 3.4
- **Author:** Onestein
- **License:** LGPL-3
- **Dependencies:** `base_iban`, `base_vat`, `account`, `account_edi_ubl_cii`
- **Auto-installs:** `account`

## Description
Dutch accounting localization providing a chart of accounts for Dutch SMEs, aligned with Dutch reporting requirements.

## Data Files
No Python models — fully data-driven. Key data files:
- `data/account_account_tag.xml` — Dutch account classification tags
- `data/account_tax_report_data.xml` — Dutch tax report (BTW aangifte)
- `data/res_country_group.xml` — EU country grouping for OSS/VAT
- `views/res_config_settings_view.xml` — Configuration settings views

## Tax Report
Dutch BTW (VAT) report structure, aligned with the Belastingdienst (Tax and Customs Administration) requirements.

## Related Modules
- Dutch-specific EDI via `account_edi_ubl_cii` (XRechnung / UBL)
