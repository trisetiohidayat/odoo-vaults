# Sale Product Configurators Tests (`test_sale_product_configurators`)

**Category:** Hidden
**Depends:** `event_sale`, `sale_management`, `sale_product_matrix`
**Author:** Odoo S.A.
**License:** LGPL-3

## Overview

Test module for sale product configurator features (optional products, optional product attributes, matrix grid ordering) in the sales app. Depends on `sale_management` and `sale_product_matrix` for configurable product ordering.

## Dependencies

| Module | Purpose |
|--------|---------|
| `sale_management` | Sale order templates and optional product lines |
| `sale_product_matrix` | Grid/product matrix ordering for configurable products |
| `event_sale` | Event ticket sales |

## Models

This module has no Python models. It contains only test tours that exercise:
- Optional product line addition on sale orders
- Product configurator modal (attributes: color, size, custom text)
- Matrix grid ordering for products with multiple attributes
- Event ticket configuration

## Test Assets

- `test_sale_product_configurators/static/tests/tours/**/*` — Configurator test tours
