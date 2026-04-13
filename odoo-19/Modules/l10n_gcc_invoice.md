---
type: module
module: l10n_gcc_invoice
tags: [odoo, odoo19, l10n, localization, gcc, arabic, invoice]
created: 2026-04-06
---

# Gulf Cooperation Council Invoice (`l10n_gcc_invoice`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Gulf Cooperation Council - Invoice |
| **Technical** | `l10n_gcc_invoice` |
| **Category** | Accounting/Localizations |
| **Countries** | KW, OM, QA, AE, SA |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Adds Arabic as a secondary language on invoices, credit notes, debit notes, vendor bills, and refund bills. Base module for all GCC country localizations. Used by Kuwait, Oman, Qatar, UAE, and Saudi Arabia.

## Dependencies
| Module | Purpose |
|--------|---------|
| `account` | Core accounting module |

## Key Models

### `account.move` (Extended)
Extends `account.move` to add Arabic bilingual support on printed reports.

### `product.product` (Extended)
Adds Arabic language translation support for product names and descriptions on GCC invoices.

### `res.company` (Extended)
Extends company to support Arabic company name and address on invoice reports.

## Technical Notes
- Post-init hook: `_l10n_gcc_invoice_post_init` - activates Arabic on existing companies
- Assets: SCSS styles for bilingual invoice layout
- Report templates: `views/report_invoice.xml`
- Settings: `views/res_config_settings_views.xml`

## Related
- [Modules/account](modules/account.md)
- [Modules/l10n_sa](modules/l10n_sa.md)
- [Modules/l10n_ae](modules/l10n_ae.md)
- [Modules/l10n_kw](modules/l10n_kw.md)
- [Modules/l10n_om](modules/l10n_om.md)
- [Modules/l10n_qa](modules/l10n_qa.md)
- [Modules/l10n_gcc_pos](modules/l10n_gcc_pos.md)
- [Modules/l10n_gcc_invoice_stock_account](modules/l10n_gcc_invoice_stock_account.md)