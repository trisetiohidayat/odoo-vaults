---
Module: l10n_pe_website_sale
Version: 18.0
Type: l10n/peru-ecommerce
Tags: #odoo18 #l10n #accounting #peru #ecommerce
---

# l10n_pe_website_sale — Peruvian eCommerce Bridge

## Overview
Bridge module connecting [Modules/l10n_pe](modules/l10n_pe.md) with `website_sale`. Exposes the Peruvian Identification Type (DNI, RUC, Carnet de Extranjeria) in the eCommerce checkout form so online customers can select their document type during purchase. Auto-installs with website_sale and l10n_pe.

## Country/Region
Peru (PE)

## Dependencies
- website_sale
- l10n_pe

## Key Models
No custom Python model classes. JavaScript asset extends the checkout form.

### Frontend Asset: `l10n_pe_website_sale/static/src/js/website_sale.js`
Injects identification type selection into the website_sale checkout form.

## Data Files
- `security/ir.model.access.csv`
- `data/ir_model_fields.xml`: Additional fields for checkout
- `views/templates.xml`: Checkout form templates

## Installation
Auto-installs with website_sale when l10n_pe is active.

## Historical Notes
Version 0.1 in Odoo 18. Peru's SUNAT requires that electronic invoices (Facturas) issued through eCommerce include the customer's RUC for VAT credit purposes. This bridge enables RUC collection during online checkout.
