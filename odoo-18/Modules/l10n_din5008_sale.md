---
Module: l10n_din5008_sale
Version: 18.0
Type: l10n/din5008/ sale
Tags: #odoo18 #l10n #din5008 #sale #layout
---

# l10n_din5008_sale

## Overview
DIN 5008 layout module for the Sale application. Extends sale order and quotation PDF/report templates with the German DIN 5008 business document layout standard (German norm for letterheads, document headers, and footers on business papers). This is a pure-report/link module with no business logic -- it overrides QWeb report templates.

## Country
Germany (DIN 5008 is a German document-layout standard, used across DACH region)

## Dependencies
- `l10n_din5008` (DIN 5008 base module -- provides the core layout snippets)
- `sale` (Sale application)

## Key Models
No Python models. Module contains only QWeb report XML overrides.

## Data Files
- `report/din5008_sale_templates.xml` -- QWeb template overrides for sale order / quotation
- `report/din5008_sale_order_layout.xml` -- DIN 5008 layout sections (letterhead, footer, address block)

## Report Layout
DIN 5008 specifies standard positions for:
- Company logo (top-left or top-center)
- Sender address / return address
- Document title and number
- Customer address block
- Date, reference fields
- Footer with legal notice, tax ID, bank details

When both `l10n_din5008` and `sale` are installed, `l10n_din5008_sale` replaces the standard Odoo sale report layout with the DIN 5008-compliant layout.

## Installation
Auto-installs when both `l10n_din5008` and `sale` are present in the database. Install manually to add DIN 5008 sale layout to an existing installation.

## Related Modules
- `l10n_din5008` -- base module with shared layout snippets
- `l10n_din5008_purchase` -- DIN 5008 layout for purchase orders
- `l10n_din5008_repair` -- DIN 5008 layout for repair orders
- `l10n_din5008_stock` -- DIN 5008 layout for stock operations

## Historical Notes
- Odoo 18: Separated into dedicated per-app modules (sale, purchase, repair, stock)
- Odoo 17 and earlier: DIN 5008 layout was bundled inside the `l10n_din5008` base module
