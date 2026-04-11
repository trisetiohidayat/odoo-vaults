---
Module: l10n_din5008_stock
Version: 18.0
Type: l10n/din5008/ stock
Tags: #odoo18 #l10n #din5008 #stock #layout
---

# l10n_din5008_stock

## Overview
DIN 5008 layout module for the Stock application. Extends delivery slip and stock report PDF templates with the German DIN 5008 business document layout standard. Pure-report module with no business logic.

## Country
Germany (DIN 5008 standard)

## Dependencies
- `l10n_din5008` (DIN 5008 base -- shared layout snippets)
- `stock` (Stock application)

## Key Models
No Python models. Module contains only QWeb report XML overrides.

## Data Files
None (layout via `l10n_din5008` base module snippets).

## Report Layout
Applies DIN 5008 layout to:
- Delivery Slip (stock.report_deliverySlip)
- Picking slip / transfer report

## Installation
Auto-installs when both `l10n_din5008` and `stock` are present. Install manually to add DIN 5008 stock layout to existing installation.

## Related Modules
- `l10n_din5008` -- base module with shared layout snippets
- `l10n_din5008_sale` -- DIN 5008 layout for sale orders
- `l10n_din5008_purchase` -- DIN 5008 layout for purchase orders
- `l10n_din5008_repair` -- DIN 5008 layout for repair orders

## Historical Notes
- Odoo 18: Split into per-app modules
- Odoo 17 and earlier: DIN 5008 layout bundled in `l10n_din5008` base
