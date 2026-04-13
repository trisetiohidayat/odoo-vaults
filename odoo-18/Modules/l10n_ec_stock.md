---
Module: l10n_ec_stock
Version: 18.0
Type: l10n/ecuador-stock
Tags: #odoo18 #l10n #accounting #ecuador #stock
---

# l10n_ec_stock — Ecuador Stock

## Overview
Bridge module between [Modules/l10n_ec](modules/l10n_ec.md) and `stock`. Adds Ecuadorian SRI (Servicio de Rentas Internas) compliance to stock operations. Post-init hook activates Ecuadorian data in stock module. Works with [Modules/Stock](modules/stock.md) integration.

## Country/Region
Ecuador (EC)

## Dependencies
- l10n_ec
- stock

## Key Models
No custom Python model classes.

## Post-Init Hook: `post_init_hook`
Activates Ecuador-specific stock data after l10n_ec is installed.

## Installation
Auto-installs with stock when l10n_ec is active.

## Historical Notes
New in Odoo 18 as a dedicated stock bridge for Ecuadorian SRI compliance.
