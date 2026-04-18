---
type: module
module: l10n_ar_withholding
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# Argentina Accounting Localization (`l10n_ar_withholding`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Allows to register withholdings during the payment of an invoice. |
| **Technical** | `l10n_ar_withholding` |
| **Category** | Accounting/Localizations |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Allows to register withholdings during the payment of an invoice.

## Dependencies
| Module | Purpose |
|--------|---------|
| `l10n_ar` | Dependency |
| `l10n_latam_check` | Dependency |

## Technical Notes
- Country code: `ar` (Argentina)
- Localization type: withholding tax management
- Custom model files: account_tax.py, account_move.py, l10n_ar_partner_tax.py, account_payment.py, res_company.py, account_chart_template.py, l10n_ar_earnings_scale.py, res_config_settings.py, res_partner.py

## Models

### `l10n_ar.earnings.scale` + `l10n_ar.earnings.scale.line` (Earnings Scale)
Progressive tax brackets for Argentine withholding taxes.

**Fields (scale):**
- `name`, `type` — Scale name and type

**Fields (scale line):**
- `scale_id` — Parent scale
- `min_amount`, `max_amount` — Bracket range
- `percentage`, ` withhold_amount` — Rate and fixed amount

### `l10n_ar.partner.tax` (Argentinean Partner Taxes)
Stores partner-specific tax conditions for withholding computation.

### `account.move` (Extended)
Argentine withholding fields on invoices.

### `account.payment` (Extended)
Argentine withholding during payment registration.

### `res.partner` (Extended)
Argentine tax conditions (tax type, gross income number, earnings scale).

## Related
- [Modules/l10n_ar](Modules/l10n_ar.md) — Core Argentine accounting
- [Modules/l10n_latam_check](Modules/l10n_latam_check.md) — Latam check/cheque management