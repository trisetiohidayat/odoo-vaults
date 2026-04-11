---
type: module
module: delivery_mondialrelay
tags: [odoo, odoo19, delivery, shipping, mondial-relay, ecommerce]
created: 2026-04-06
---

# Delivery Mondial Relay

## Overview
| Property | Value |
|----------|-------|
| **Name** | Delivery Mondial Relay |
| **Technical** | `delivery_mondialrelay` |
| **Category** | Shipping Connectors |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Integrates the Mondiani Relay Point Relais delivery service. Allows customers to select a Point Relais as their shipping address in the eCommerce checkout. The module provides the widget integration; it does **not** implement the Mondial Relay WebService (pricing and Point Relais selection must be configured separately).

## Dependencies
- `stock_delivery`

## Key Models
| Model | Type | Description |
|-------|------|-------------|
| `delivery.carrier` | Extension | Adds Mondiani Relay-specific fields and tracking |
| `sale.order` | Extension | Validates carrier/address consistency on confirmation |

## `delivery.carrier` (Extension)
### Fields
| Field | Type | Description |
|-------|------|-------------|
| `is_mondialrelay` | Boolean | Computed; True if product default_code = `'MR'` |
| `mondialrelay_brand` | Char | Brand code; default `'BDTEST  '` (for testing) |
| `mondialrelay_packagetype` | Char | Package type; default `'24R'` (Advanced, system only) |

### Methods
| Method | Purpose |
|--------|---------|
| `_compute_is_mondialrelay` | Sets True if product default_code == `'MR'` |
| `_search_is_mondialrelay` | Domain search: `product_id.default_code = 'MR'` |
| `fixed_get_tracking_link` | Delegates to `base_on_rule_get_tracking_link` for MR carriers |
| `base_on_rule_get_tracking_link` | Returns Mondiani Relay tracking URL: `https://www.mondialrelay.com/public/permanent/tracking.aspx?ens={brand}&exp={track}&language={lang}` |

## `sale.order` (Extension)
### Validation
- `action_confirm` — Raises error if any SO has a Mondiani Relay carrier but the shipping address is not a Mondiani Relay address (or vice versa). Prevents mismatched configurations.

## Configuration Notes
- Requires a delivery product with `default_code = 'MR'`
- Pricing rules should be configured in `delivery.carrier` as regular pricing rules (not real-time WebService)
- Widget for Point Relais selection is loaded via web assets

## Related
- [[Modules/delivery]]
- [[Modules/stock_delivery]]
- [[Modules/website_sale_mondialrelay]]
