---
Module: l10n_br_website_sale
Version: 18.0
Type: l10n/brazil-ecommerce
Tags: #odoo18 #l10n #accounting #brazil #ecommerce
---

# l10n_br_website_sale — Brazil eCommerce Bridge

## Overview
Bridge module connecting [Modules/l10n_br](odoo-18/Modules/l10n_br.md) with `website_sale`. Adds Brazilian-specific fields to the eCommerce checkout: CNPJ/CPF, Inscricao Estadual, Inscricao Municipal, and SUFRAMA fields on partner form. Post-init hook injects Brazilian states into the website partner registration form.

## Country/Region
Brazil (BR)

## Dependencies
- l10n_br
- website_sale

## Key Models
No custom model classes.

### Post-Init Hook: `_l10n_br_website_sale_post_init_hook`
Loads Brazilian state data into website sale checkout forms.

## Data Files
- `data/ir_model_fields.xml`: Additional fields for website_sale checkout (IE, IM, CNPJ)
- `views/portal.xml`: Customer portal view with Brazilian fields
- `views/templates.xml`: eCommerce checkout form templates

## Installation
Auto-installs with website_sale when l10n_br is active. Post-init hook activates Brazilian state data.

## Historical Notes
New in Odoo 18 as a dedicated eCommerce bridge. In Odoo 17, Brazilian eCommerce fields were handled in the main module.
