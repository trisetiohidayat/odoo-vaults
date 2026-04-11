# l10n_ch - Switzerland Accounting

## Overview
- **Name:** Switzerland - Accounting
- **Country:** Switzerland (CH)
- **Category:** Accounting/Localizations/Account Charts
- **Version:** 11.3
- **Author:** Odoo S.A.
- **License:** LGPL-3
- **Dependencies:** `account`, `account_edi_ubl_cii`, `base_iban`, `l10n_din5008`
- **Auto-installs:** `account`

## Description
Swiss localization based on Swiss PME/KMU 2015 chart of accounts. Key feature: automatic Swiss QR-bill generation appended to invoices when:
1. Partner address is complete and in Switzerland
2. Swiss QR-code option is selected on the invoice (default)
3. Correct QR-IBAN is set on the bank journal
4. Payment reference is a QR-reference (when using QR-IBAN)

## Models
No Python models defined. The module is primarily data-driven.

## Swiss QR-Bill Generation
Report-driven via `report/swissqr_report.xml`. QR-bill is attached to invoice PDF when conditions are met.

## Data Files
- `data/account_tax_report_data.xml` — Swiss tax report structure
- `report/swissqr_report.xml` — Swiss QR-bill report layout
- `views/res_bank_view.xml` — Bank configuration with QR-IBAN fields
- `views/account_invoice.xml` — Invoice views with QR-bill options
- `views/setup_wizard_views.xml`, `views/qr_invoice_wizard_view.xml` — Setup wizards
- `views/account_payment_view.xml` — Payment views
- `security/ir.model.access.csv` — Access rights for custom models (wizards)

## Post-Init Hook
`post_init` — fires after module installation for any setup.

## Assets
- `l10n_ch/static/src/scss/**/*` — SCSS styles for QR-bill rendering (web.report_assets_common)

## Related Modules
- **l10n_ch_pos** — Swiss POS integration
