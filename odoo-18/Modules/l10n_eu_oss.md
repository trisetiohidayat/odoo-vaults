---
Module: l10n_eu_oss
Version: 1.0
Type: addon
Tags: #odoo18 #l10n_eu_oss #localization #eu #oss #vat #one-stop-shop
---

## Overview

**Module:** `l10n_eu_oss`
**Depends:** `account`
**Location:** `~/odoo/odoo18/odoo/addons/l10n_eu_oss/`
**License:** LGPL-3
**Purpose:** EU One Stop Shop (OSS) VAT module. Automatically creates fiscal positions and taxes for all EU member states when a company sells cross-border B2C within the EU. Covers the EU-wide threshold (EUR 10,000) for OSS registration and per-country VAT rates for B2C digital services.

---

## Architecture

OSS is not a country-specific localization but a cross-EU framework. It works by:

1. **EU_ACCOUNT_MAP** (`eu_account_map.py`): Maps chart template codes to OSS VAT payable accounts (e.g., `de_skr03` → `1767`).
2. **EU_FIELD_MAP** (`eu_field_map.py`): Sets localization-specific tax fields (e.g., for Spain, sets `l10n_es_type = 'no_sujeto_loc'` for OSS taxes).
3. **EU_TAG_MAP** (`eu_tag_map.py`): Maps fiscal country codes to tax tags (base/tax tags for each EU country on invoice and refund repartition lines).
4. **EU_TAX_MAP** (`eu_tax_map.py`): Defines OSS tax rates per EU member state.

---

## Models

### `res.company` (models/res_company.py)

Extends: `res.company` — adds OSS-specific configuration fields.

### `res.config.settings` (models/res_config_settings.py)

Extends: `res.config.settings` — exposes OSS settings.

---

## Key Data

**CSV:** `data/account_account_tag.xml` — EU OSS tax classification tags.
**Views:** `views/res_config_settings_views.xml` — OSS configuration UI.

---

## EU VAT Rates (OSS)

Standard OSS rates per EU member state:

| Country | Standard Rate |
|---|---|
| AT (Austria) | 20% |
| BE (Belgium) | 21% |
| BG (Bulgaria) | 20% |
| HR (Croatia) | 25% |
| CY (Cyprus) | 19% |
| CZ (Czech Republic) | 21% |
| DK (Denmark) | 25% |
| EE (Estonia) | 22% |
| FI (Finland) | 24% |
| FR (France) | 20% |
| DE (Germany) | 19% |
| GR (Greece) | 24% |
| HU (Hungary) | 27% |
| IE (Ireland) | 23% |
| IT (Italy) | 22% |
| LV (Latvia) | 21% |
| LT (Lithuania) | 21% |
| LU (Luxembourg) | 17% |
| MT (Malta) | 18% |
| NL (Netherlands) | 21% |
| PL (Poland) | 23% |
| PT (Portugal) | 23% |
| RO (Romania) | 19% |
| SK (Slovakia) | 20% |
| SI (Slovenia) | 22% |
| ES (Spain) | 21% |
| SE (Sweden) | 25% |

---

## Usage

When a company with an EU fiscal country sells cross-border B2C within the EU and exceeds the EUR 10,000 threshold, `l10n_eu_oss` automatically creates the necessary:
- Fiscal positions mapping domestic taxes to OSS foreign taxes
- OSS tax records for each destination country
- Account tags for proper financial reporting

---

## Uninstall Hook

`l10n_eu_oss_uninstall`: Cleans up OSS-specific configuration on module uninstall.

---

## Critical Notes

- **OSS Threshold**: EUR 10,000 (across all EU member states combined). Below this, domestic VAT rules apply.
- **B2C Digital Services**: Main use case. Services and digital goods sold to non-taxable persons in other EU countries.
- **Non-EU Country OSS**: Some non-EU countries also have OSS equivalents. This module focuses on EU OSS per Council Directive 2017/2455 and 2019/1995.
- **Implementation Regulation**: Council Implementing Regulation (EU) 2019/2026.
- This module is a framework — individual EU country l10n modules (l10n_de, l10n_fr, etc.) provide the actual charts and taxes.
- v17→v18: No breaking changes.
