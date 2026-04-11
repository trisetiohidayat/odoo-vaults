---
type: module
module: l10n_gcc_pos
tags: [odoo, odoo19, l10n, localization, gcc, pos, point-of-sale, arabic]
created: 2026-04-06
---

# Gulf Cooperation Council POS (`l10n_gcc_pos`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Gulf Cooperation Council - Point of Sale |
| **Technical** | `l10n_gcc_pos` |
| **Category** | Accounting/Localizations/Point of Sale |
| **Countries** | KW, OM, QA, AE, SA |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Adds Arabic as a secondary language on Point of Sale receipts for GCC countries. Provides bilingual receipt formatting for Point of Sale transactions.

## Dependencies
| Module | Purpose |
|--------|---------|
| `point_of_sale` | Core POS module |
| `l10n_gcc_invoice` | GCC invoice bilingual support |

## Key Models

### `pos.config` (Extended)
| Field | Type | Description |
|-------|------|-------------|
| `l10n_gcc_dual_language_receipt` | Boolean | Enable GCC Formatted bilingual receipts |

## Technical Notes
- Auto-installs: True
- Settings view: `views/res_config_settings_views.xml`
- Static assets: `l10n_gcc_pos/static/src/**/*` (bilingual receipt styling)
- Asset bundle: `point_of_sale._assets_pos`

## Related
- [[Modules/point_of_sale]]
- [[Modules/l10n_gcc_invoice]]
- [[Modules/l10n_sa_pos]]
- [[Modules/l10n_ae_pos]]