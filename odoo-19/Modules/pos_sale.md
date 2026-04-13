# POS Sale

## Overview
- **Name:** POS - Sales
- **Category:** Sales/Point of Sale
- **Depends:** `point_of_sale`, `sale_management`
- **Auto-install:** True
- **Author:** Odoo S.A.
- **License:** LGPL-3

## Description
Link module between Point of Sale and Sales. Enables loading and confirming sale orders from POS, syncing picking demand, and managing down payments. Adds a dedicated Sales Team for POS.

## Models

### `sale.order` (Extended)
| Field | Type | Description |
|-------|------|-------------|
| `pos_order_line_ids` | One2many | POS order lines linked to this SO |
| `pos_order_count` | Integer | Count of linked POS orders |
| `amount_unpaid` | Monetary | Amount left to pay in POS |

Computed: `_count_pos_order`, `_compute_amount_unpaid`, `_compute_amount_to_invoice`, `_compute_amount_invoiced`, `_compute_untaxed_amount_invoiced`

### `sale.order.line` (Extended)
| Field | Type | Description |
|-------|------|-------------|
| `pos_order_line_ids` | One2many | POS order lines linked to this SOL |

Key methods: `_compute_qty_delivered`, `_prepare_qty_delivered`, `_compute_qty_invoiced`, `_prepare_qty_invoiced`, `read_converted`, `_convert_qty()`

### `pos.order` (Extended)
| Field | Type | Description |
|-------|------|-------------|
| `crm_team_id` | Many2one | Sales team for the POS order |
| `sale_order_count` | Integer | Count of linked sale orders |
| `currency_rate` | Float | Currency conversion rate |

### `pos.order.line` (Extended)
| Field | Type | Description |
|-------|------|-------------|
| `sale_order_origin_id` | Many2one | Source sale order |
| `sale_order_line_id` | Many2one | Source sale order line |
| `down_payment_details` | Text | Down payment details |
| `qty_delivered` | Float | Computed delivery quantity |

## Key Features
- Load draft sale orders into POS for payment
- Sync picking demand from POS to Sale order stock moves
- Down payment creation from POS orders
- Prevent double-invoicing by tracking POS payments
- Sales team assignment per POS config

## Key Methods
- `load_sale_order_from_pos()` — Load SO and related data for POS
- `action_view_sale_order()` — Action to view linked sale orders
- `sync_from_ui()` — Process POS orders from UI, sync to Sale orders
- `_prepare_down_payment_line_values_from_base_line()` — Create SO down payment from POS line

## Data Files
- `data/pos_sale_data.xml` — Default sales team
- `security/pos_sale_security.xml` — Security rules
- `security/ir.model.access.csv` — Access control
- `views/point_of_sale_report.xml` — POS report views
- `views/sale_order_views.xml` — SO form/list views
- `views/pos_order_views.xml` — POS order views
- `views/sales_team_views.xml` — Sales team views
- `views/res_config_settings_views.xml` — Settings
- `views/stock_template.xml` — Stock picking views

## Hooks
- `post_init_hook: _pos_sale_post_init` — Post-install initialization

## Related
- [Modules/point_of_sale](odoo-18/Modules/point_of_sale.md) — Base POS module
- [Modules/Sale](odoo-18/Modules/sale.md) — Sales module
- [Modules/pos_sale_loyalty](odoo-18/Modules/pos_sale_loyalty.md) — POS Sale + Loyalty
- [Modules/pos_sale_margin](odoo-18/Modules/pos_sale_margin.md) — POS Sale + Margin
