---
type: module
module: l10n_ae
tags: [odoo, odoo19, localization, uae, gcc]
created: 2026-04-06
---

# United Arab Emirates - Localization

## Overview
| Property | Value |
|----------|-------|
| **Name** | United Arab Emirates - Accounting |
| **Technical** | `l10n_ae` |
| **Category** | Localization |
| **Country** | United Arab Emirates |

## Description
Localized accounting for the UAE. Activates chart of accounts, taxes, tax report, and fiscal positions. Builds on the GCC invoice module.

## Dependencies
- `account`
- `l10n_gcc_invoice`

## Key Models

### `account.move` (Extended)
Inherits `account.move` to add UAE-specific invoice reporting:

- `_get_name_invoice_report()`: Returns the UAE invoice report template for UAE-based companies.
- `_l10n_gcc_get_invoice_title()`: Returns "Tax Invoice" or "Simplified Tax Invoice" based on customer type.
- `_l10n_ae_is_simplified()`: Returns True if customer is an individual (B2C invoice).

## Related
- [[Modules/account]]
- [[Modules/l10n_gcc_invoice]]
