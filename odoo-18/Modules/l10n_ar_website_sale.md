---
Module: l10n_ar_website_sale
Version: 18.0
Type: l10n/argentina-ecommerce
Tags: #odoo18 #l10n #accounting #argentina #ecommerce
---

# l10n_ar_website_sale — Argentine eCommerce Bridge

## Overview
Bridge module for [Modules/l10n_ar](Modules/l10n_ar.md) and `website_sale`. Exposes AFIP Responsibility Type and Identification Type fields in the eCommerce checkout form so Argentine customers can specify their fiscal condition during online purchases.

## Country/Region
Argentina (AR)

## Dependencies
- website_sale
- l10n_ar

## Key Models
No custom models. Extends `website_sale` views via XML.

## Data Files
- `data/ir_model_fields.xml`: Adds Identification Type and AFIP Responsibility Type fields to the website_sale checkout model
- `views/templates.xml`: Frontend form modifications for checkout

## Installation
Auto-installs when both website_sale and l10n_ar are active. No manual configuration needed.

## Historical Notes
Added in Odoo 18 as a dedicated bridge module. In earlier versions, AR fields were handled via post-install patches.
