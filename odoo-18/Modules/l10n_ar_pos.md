---
Module: l10n_ar_pos
Version: 18.0
Type: l10n/argentina-pos
Tags: #odoo18 #l10n #accounting #argentina #pos
---

# l10n_ar_pos — Argentine Point of Sale with AR Document

## Overview
Bridge module that adds Argentine-specific requirements to the Point of Sale application. Depends on [Modules/l10n_ar](modules/l10n_ar.md) and `point_of_sale`. Extends the POS session to load Argentine-specific reference data and partner records for the POS interface.

## Country/Region
Argentina (AR)

## Dependencies
- l10n_ar
- point_of_sale

## Key Models

### `pos.session` (Extended)
Inherits: `pos.session`
Methods:
- `_load_pos_data_models()`: Adds `l10n_ar.afip.responsibility.type` and `l10n_latam.identification.type` to the POS data model list when company's country is AR
- `_load_pos_data()`: Injects `par_cfa` (consumidor_final_anonimo) partner reference into POS data for AR companies

## Data Files
- `views/templates.xml`: Frontend assets for Argentine POS

## Installation
Auto-installs with `point_of_sale` when company country is AR. POS session automatically loads AR-specific reference data and anonymous consumer partner.

## Historical Notes
Separated from the main `l10n_ar` module in Odoo 18 for cleaner separation of concerns between accounting and POS.
