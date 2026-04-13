# Argentinean - Point of Sale (`l10n_ar_pos`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Argentinean - Point of Sale |
| **Technical** | `l10n_ar_pos` |
| **Category** | Accounting/Localizations/POS |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Depends** | `l10n_ar`, `point_of_sale` |

## Description
Argentinean POS localization. Ensures the "Consumidor Final Anonimo" (anonymous end consumer, RFCI/CAI counterpart) partner is always available in the POS partner list, and passes it to the POS session data for use when no customer is selected.

## Dependencies
| Module | Purpose |
|--------|---------|
| `l10n_ar` | Core Argentinean accounting |
| `point_of_sale` | Base POS module |

## Technical Notes
- Country code: `ar` (Argentina)
- Core concern: Anonymous consumer partner (par_cfa) availability in POS

## Models

### `pos.config` (Extended)
**Key methods:**
- `get_limited_partners_loading(offset)` — EXTENDS `point_of_sale`. Appends `l10n_ar.par_cfa` (Consumer Final Anonimo / RFCI partner) to the partner ID list returned for POS session
- `_load_pos_data_read(records, config)` — EXTENDS `point_of_sale`. For Argentine companies, adds `_consumidor_final_anonimo_id` to session data pointing to `par_cfa`

## Other Extended Models
- `l10n_ar.afip.responsibility.type` — AFIP fiscal responsibility types (used for partner identification)
- `l10n_latam.identification.type` — Latin American identification document types
- `res.partner` — Argentine-specific partner fields
- `pos.session` — Session-specific Argentine adjustments

## Related
- [Modules/l10n_ar](odoo-18/Modules/l10n_ar.md) — Core Argentinean accounting
- [Modules/l10n_ar_website_sale](odoo-18/Modules/l10n_ar_website_sale.md) — Argentine eCommerce
- [Modules/l10n_ar_withholding](odoo-18/Modules/l10n_ar_withholding.md) — Argentine withholding tax
- [Modules/l10n_ar_stock](odoo-19/Modules/l10n_ar_stock.md) — Argentine inventory/warehouse
