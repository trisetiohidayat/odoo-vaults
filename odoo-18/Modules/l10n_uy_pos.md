---
Module: l10n_uy_pos
Version: 18.0
Type: l10n/uruguay-pos
Tags: #odoo18 #l10n #accounting #uruguay #pos
---

# l10n_uy_pos — Uruguayan Point of Sale

## Overview
Bridge module adding Uruguayan requirements to the Point of Sale application. Depends on [Modules/l10n_uy](l10n_uy.md) and `point_of_sale`. Loads frontend assets for Uruguayan POS regulation compliance.

## Country/Region
Uruguay (UY)

## Dependencies
- l10n_uy
- point_of_sale

## Key Models
No custom Python model classes.

## Frontend Assets
- `l10n_uy_pos/static/src/**/*`: Uruguayan POS technical requirements (JavaScript, CSS)

## Installation
Auto-installs with point_of_sale when l10n_uy is active.

## Historical Notes
Minimal bridge module. Uruguay's DGI requires POS systems to comply with specific requirements for electronic receipt issuance.
