---
Module: l10n_co_pos
Version: 18.0
Type: l10n/colombia-pos
Tags: #odoo18 #l10n #accounting #colombia #pos
---

# l10n_co_pos — Colombian Point of Sale

## Overview
Bridge module adding Colombian requirements to the Point of Sale application. Depends on [Modules/l10n_co](l10n_co.md) and `point_of_sale`. Loads Colombian-specific reference data into POS sessions.

## Country/Region
Colombia (CO)

## Dependencies
- l10n_co
- point_of_sale

## Key Models
No custom Python model classes. Adds `res_config_settings_views.xml` for POS configuration.

## Data Files
- `views/res_config_settings_views.xml`: POS configuration view for Colombia

## Installation
Auto-installs with point_of_sale when l10n_co is active.

## Historical Notes
Minimal module added in Odoo 18 to bridge POS with Colombian localization.
