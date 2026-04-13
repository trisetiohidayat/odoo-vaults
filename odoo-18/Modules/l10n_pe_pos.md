---
Module: l10n_pe_pos
Version: 18.0
Type: l10n/peru-pos
Tags: #odoo18 #l10n #accounting #peru #pos
---

# l10n_pe_pos — Peruvian Point of Sale

## Overview
Bridge module adding Peruvian requirements to the Point of Sale application. Depends on [Modules/l10n_pe](Modules/l10n_pe.md) and `point_of_sale`. Extends POS sessions to load Peruvian reference data (districts, identification types) and sets default values for the POS customer.

## Country/Region
Peru (PE)

## Dependencies
- l10n_pe
- point_of_sale

## Key Models

### `pos.session` (Extended)
Inherits: `pos.session`
Methods:
- `_load_pos_data_models()`: Adds `l10n_pe.res.city.district`, `l10n_latam.identification.type`, and `res.city` to the POS data model list for PE companies
- `_load_pos_data()`: Sets `_default_l10n_latam_identification_type_id` to DNI and `_consumidor_final_anonimo_id` to the PE anonymous consumer partner for PE POS sessions

### `res.partner` (Extended via Data)
Added via data: Peruvian consumer anonymous partner record for POS.

## Data Files
- `data/res_partner_data.xml`: consumidor_final anonimo partner for Peru POS
- `views/templates.xml`: Frontend templates

## Installation
Auto-installs with point_of_sale when l10n_pe is active. POS session automatically loads PE-specific reference data.

## Historical Notes
Added in Odoo 18 as a dedicated Peru POS bridge.
