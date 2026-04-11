# Peru - Point of Sale (`l10n_pe_pos`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | Peru - Point of Sale |
| **Technical** | `l10n_pe_pos` |
| **Category** | Accounting/Localizations/POS |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Depends** | `l10n_pe`, `point_of_sale` |

## Description
Peruvian POS localization. Ensures the "Consumidor Final" (anonymous end consumer) partner is always available in the POS partner list, filters identification types to Peruvian VAT codes, and loads Peruvian city/district data into POS sessions.

## Dependencies
| Module | Purpose |
|--------|---------|
| `l10n_pe` | Core Peruvian accounting |
| `point_of_sale` | Base POS module |

## Technical Notes
- Country code: `pe` (Peru)
- Key partner: `partner_pe_cf` (Consumer Final)
- POS session data includes: districts, cities, identification types, states

## Models

### `pos.config` (Extended)
**Key methods:**
- `get_limited_partners_loading()` — Appends `partner_pe_cf` to the partner list for POS session
- `_load_pos_data_read()` — Adds `_consumidor_final_anonimo_id` to session data for Peruvian companies

### `pos.session` (Extended)
**`_load_pos_data_models()`** — EXTENDS `point_of_sale`. For Peruvian companies, adds `l10n_pe.res.city.district`, `l10n_latam.identification.type`, and `res.city` to the POS session data models

### `l10n_latam.identification.type` (Extended)
**`_load_pos_data_domain()`** — For Peru, filters to only identification types with `l10n_pe_vat_code` set (i.e., valid Peruvian ID types)

### `res.city` (Extended — `pos.load.mixin`)
**`_load_pos_data_fields()`** — Returns `name`, `country_id`, `state_id` for POS session

### `l10n_pe.res.city.district` (Extended — `pos.load.mixin`)
Adds `country_id` and `state_id` as related fields; returns `name`, `city_id`, `country_id`, `state_id` for POS session

### `res.partner` (Extended)
**`_pe_unlink_except_master_data()`** — Prevents deletion of the `partner_pe_cf` master data record

## Related
- [[Modules/l10n_pe]] — Core Peruvian accounting
- [[Modules/l10n_ar_pos]] — Argentine POS (similar consumer-final pattern)
