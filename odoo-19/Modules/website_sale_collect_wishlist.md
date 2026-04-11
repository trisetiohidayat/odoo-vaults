# website_sale_collect_wishlist

Odoo 19 Website/e-Commerce Module

## Overview

`website_sale_collect_wishlist` is a **bridge module** between `website_sale_collect` (Click & Collect) and `website_sale_wishlist` (Wishlist). Allows users to add products to wishlist when not available at their selected pickup location.

## Module Details

- **Category**: Website/Website
- **Depends**: `website_sale_wishlist`, `website_sale_collect`
- **Author**: Odoo S.A.
- **License**: LGPL-3
- **Auto-install**: Yes

## Functionality

When a product is unavailable at the selected Click & Collect store, the wishlist button remains accessible. Products can be added to wishlist for later purchase when available.

This is a thin bridge module — no additional Python models. Relies on inherited behavior from `website_sale_collect` and `website_sale_wishlist`.

### Views

- `delivery_form_templates.xml` — Template overrides for the pickup form to show wishlist option.

## Relationship to Other Modules

| Module | Role |
|---|---|
| `website_sale_wishlist` | Wishlist feature |
| `website_sale_collect` | Click & Collect with in-store stock checking |
| `website_sale_collect_wishlist` | Bridge — allows wishlist add when out of stock at store |
