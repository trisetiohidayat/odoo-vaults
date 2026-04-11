---
Module: l10n_ec_website_sale
Version: 18.0
Type: l10n/ecuador-ecommerce
Tags: #odoo18 #l10n #accounting #ecuador #ecommerce
---

# l10n_ec_website_sale — Ecuador eCommerce Bridge

## Overview
Bridge module connecting [[Modules/l10n_ec]] with `website_sale`. Adds Ecuadorian-specific fields to the eCommerce checkout: RUC, identification types, and payment methods required for e-invoicing compliance. Payment method data includes Ecuador-specific payment types (credit cards, debit cards, cash, etc.).

## Country/Region
Ecuador (EC)

## Dependencies
- website_sale
- l10n_ec

## Key Models
No custom Python model classes.

## Data Files
- `data/ir_model_fields.xml`: Ecuadorian fields for checkout
- `data/payment_method_data.xml`: Ecuador-specific payment methods
- `views/portal_templates.xml`: Customer portal with Ecuadorian fields
- `views/website_sale_templates.xml`: Checkout form with RUC field
- `views/payment_method_views.xml`: Payment method configuration
- `demo/website_demo.xml`: Demo eCommerce data

## Installation
Auto-installs with website_sale when l10n_ec is active.

## Historical Notes
Added in Odoo 18 for Ecuadorian e-invoicing requirements in eCommerce checkout.
