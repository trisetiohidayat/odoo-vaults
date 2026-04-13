---
Module: l10n_br_sales
Version: 18.0
Type: l10n/brazil-sales
Tags: #odoo18 #l10n #accounting #brazil #sales
---

# l10n_br_sales — Brazil Sale Bridge

## Overview
Bridge module connecting [Modules/l10n_br](l10n_br.md) with the `sale` module. Adds Brazilian-specific views and portal templates for sale orders and invoices. Auto-installs with sale and l10n_br.

## Country/Region
Brazil (BR)

## Dependencies
- l10n_br
- sale

## Key Models
No custom model classes.

### `sale.order` (Extended via Views)
Extends sale order portal templates with Brazilian-specific fields (IE, IM on partner display).

## Data Files
- `views/sale_portal_templates.xml`: Brazilian customer portal layout
- `report/sale_order_templates.xml`: Sale order report customization
- `report/report_invoice_templates.xml`: Invoice report customization

## Installation
Auto-installs. No manual configuration required.

## Historical Notes
Separated from main `l10n_br` module in Odoo 18 for cleaner separation of accounting and sales portal concerns.
