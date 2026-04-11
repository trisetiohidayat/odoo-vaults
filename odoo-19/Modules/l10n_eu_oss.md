---
type: module
module: l10n_eu_oss
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# EU Accounting Localization (`l10n_eu_oss`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | EU One Stop Shop (OSS) VAT |
| **Technical** | `l10n_eu_oss` |
| **Category** | Accounting/Localizations |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
EU One Stop Shop (OSS) VAT
==========================

From July 1st 2021, EU businesses that are selling goods within the EU above EUR 10 000 to buyers located in another EU Member State need to register and pay VAT in the buyers’ Member State.
Below this new EU-wide threshold you can continue to apply the domestic rules for VAT on your cross-border sales. In order to simplify the application of this EU directive, the One Stop Shop (OSS) registration scheme allows businesses to make a unique tax declaration.

This module makes it possible by helping with the creation of the required EU fiscal positions and taxes in order to automatically apply and record the required taxes.

All you have to do is check that the proposed mapping is suitable for the products and services you sell.

References
++++++++++
Council Directive (EU) 2017/2455 Council Directive (EU) 2019/1995
Council Implementing Regulation (EU) 2019/2026

## Dependencies
| Module | Purpose |
|--------|---------|
| `account` | Dependency |

## Technical Notes
- Country code: `eu`
- Localization type: accounting chart, taxes, and fiscal positions
- Custom model files: eu_tag_map.py, eu_tax_map.py, eu_account_map.py, eu_field_map.py, res_company.py, res_config_settings.py

## Models

### `res.company` (Extended)
Inherits `res.company` to add OSS-specific methods.

**Key Methods:**
- `_map_all_eu_companies_taxes()` — Identifies EU companies (those with fiscal country in Europe) and calls `_map_eu_taxes()` for each
- `_map_eu_taxes()` — Creates/updates fiscal positions and OSS taxes for all EU destination countries. Creates `account.fiscal.position` records (one per country), OSS `account.tax` copies, and `account.tax.group` entries with proper payable/receivable accounts. Handles sequence ordering relative to existing B2B/B2C fiscal positions
- `_get_repartition_lines_oss()` — Returns invoice/refund repartition lines using OSS account and tags
- `_get_oss_account()` — Gets or creates the OSS tax payable account for the company (via `_create_oss_account()`)
- `_create_oss_account()` — Creates an OSS account based on EU_ACCOUNT_MAP or derived from existing sales tax accounts; registers as `l10n_eu_oss.oss_tax_account_company_{id}`
- `_get_oss_tags()` — Gets account tags for OSS tax lines (from EU_TAG_MAP, keyed by chart template)
- `_get_country_from_vat()` — Determines country from VAT prefix or falls back to fiscal country
- `_get_country_specific_account_tax_fields()` — Returns country-specific extra fields from EU_FIELD_MAP

## Data Maps

- `EU_TAX_MAP` — Full matrix: (domestic_country_code, domestic_tax_rate, dest_country_code) -> foreign_tax_rate
- `EU_ACCOUNT_MAP` — Chart-template-specific OSS account codes
- `EU_FIELD_MAP` — Chart-template-specific extra fields for OSS tax creation
- `EU_TAG_MAP` — Chart-template-specific account tags for OSS repartition lines

## Key Features
- Auto-creates fiscal positions with `auto_apply=True` for all EU destination countries
- Creates OSS-specific taxes with proper `tax_group_id`, `country_id`, and `original_tax_ids` linking
- Handles `oss_tax_group_{rate}_{country}` XML IDs on `account.tax.group`
- Supports uninstall hook to clean up OSS-created records
- OSS tax names: `{rate}% {country_code} {VAT_label}`

## Related