---
type: module
module: l10n_ma
tags: [odoo, odoo19, localization, morocco, ice]
created: 2026-04-06
---

# Morocco - Localization

## Overview
| Property | Value |
|----------|-------|
| **Name** | Morocco - Accounting |
| **Technical** | `l10n_ma` |
| **Category** | Localization |
| **Country** | Morocco |

## Description
Localized accounting for Morocco. Provides the base accounting chart. Built with the help of Caudigef.

## Dependencies
- `base`
- `account`

## Key Models

### `res.partner` (Extended)
Inherits `res.partner` to add Moroccan company registry validation:

- `_check_company_registry_ma()`: Constrains the company registry (ICE number) to exactly 15 digits for Moroccan partners.
- `_get_company_registry_labels()`: Labels the company registry field as "ICE" for Morocco.

**ICE Number Validation:**
- Must be exactly 15 digits
- All characters must be numeric

## Related
- [Modules/account](Account.md)
