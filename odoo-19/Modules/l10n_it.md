# l10n_it - Italy Accounting

## Overview
- **Name:** Italy - Accounting
- **Country:** Italy (IT)
- **Category:** Accounting/Localizations/Account Charts
- **Version:** 0.9
- **Author:** OpenERP Italian Community
- **License:** LGPL-3
- **Dependencies:** `account`, `base_iban`, `base_vat`, `account_edi_ubl_cii`
- **Auto-installs:** `account`

## Description
Italian accounting chart and localization (Piano dei Conti). Provides tax report templates for both annual and monthly VAT reporting, plus withholding tax reports.

## Data Files
No Python models — fully data-driven. Key data files:

### Tax Report Data
- `data/tax_report/annual_report_sections/va.xml` — Annual report section VA (assets)
- `data/tax_report/annual_report_sections/ve.xml` — VE (equity)
- `data/tax_report/annual_report_sections/vf.xml` — VF (liabilities)
- `data/tax_report/annual_report_sections/vh.xml` — VH
- `data/tax_report/annual_report_sections/vj.xml` — VJ
- `data/tax_report/annual_report_sections/vl.xml` — VL
- `data/tax_report/account_annual_tax_report_data.xml` — Annual VAT report
- `data/tax_report/account_monthly_tax_report_data.xml` — Monthly VAT report
- `data/tax_report/account_withholding_report_data.xml` — Withholding tax report

### Views
- `views/account_tax_views.xml` — Tax configuration views

### Account Tags
- `data/account_account_tag.xml` — Italian account classification tags

## Related Modules
- **l10n_it_edi** — Italian electronic invoice (FatturaPA/Sdi)
- **l10n_it_edi_ndd** — Note di Debito (debit notes)
- **l10n_it_edi_withholding** — Withholding tax in EDI
- **l10n_it_stock_ddt** — Transport document (DDT) management
