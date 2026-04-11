---
Module: l10n_uy_website_sale
Version: 18.0
Type: l10n/uruguay-ecommerce
Tags: #odoo18 #l10n #accounting #uruguay #ecommerce
---

# l10n_uy_website_sale — Uruguay eCommerce Bridge

## Overview
Bridge module connecting [[Modules/l10n_uy]] with `website_sale`. Adds Uruguayan localization fields (department, locality) to the website address form and supports the Uruguayan consumer final partner in the eCommerce checkout.

## Country/Region
Uruguay (UY)

## Dependencies
- l10n_uy
- website_sale

## Key Models
No custom Python model classes.

## Data Files
- `data/ir_model_fields.xml`: Uruguayan address fields for checkout
- `views/website_sales_templates.xml`: Address form template modifications

## Installation
Auto-installs with website_sale when l10n_uy is active.

## Historical Notes
Added in Odoo 18 as a dedicated Uruguay eCommerce bridge.
