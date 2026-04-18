---
type: module
module: spreadsheet_dashboard_pos_restaurant
tags: [odoo, odoo19, spreadsheet, dashboard, pos, restaurant, pos_restaurant, pos_hr]
created: 2026-04-06
---

# Spreadsheet Dashboard for Restaurants

## Overview

| Property | Value |
|----------|-------|
| **Name** | Spreadsheet Dashboard for Restaurants |
| **Technical** | `spreadsheet_dashboard_pos_restaurant` |
| **Version** | 1.0 |
| **Category** | Productivity/Dashboard |
| **Summary** | Spreadsheet |
| **Depends** | `spreadsheet_dashboard`, `pos_hr`, `pos_restaurant` |
| **Auto-install** | Yes — installs automatically when `pos_hr` and `pos_restaurant` are both installed |
| **Installable** | True |
| **Author** | Odoo S.A. |
| **License** | LGPL-3 |

## Description

Provides a pre-configured `spreadsheet` dashboard template tailored for restaurant POS operators. Combines POS order data with restaurant-specific dimensions (floors, tables, courses) and employee attribution.

This is a **data-only module**: it contains no Python models or business logic. The entire module consists of a `data/dashboards.xml` file that creates a sample `spreadsheet.dashboard` record with pre-defined o-spreadsheet structure.

## Module Structure

```
spreadsheet_dashboard_pos_restaurant/
├── __init__.py
├── __manifest__.py
└── data/
    └── dashboards.xml    # Creates the dashboard spreadsheet record
```

## Data File: `dashboards.xml`

The module creates a single `spreadsheet.dashboard` record via XML data. This dashboard is a self-contained o-spreadsheet document — a JSON structure defining:

- **Sheets** — multiple tabs within the spreadsheet
- **Pivots** — OLAP-style data pivots over POS models
- **Charts** — bar, line, and pie charts for KPI visualization
- **Filters** — slicers to filter by date range, employee, floor, or table
- **Formulas** — o-spreadsheet formulas referencing data sources

## Restaurant KPI Dimensions

The dashboard pre-configures the following data dimensions specific to restaurant operations:

### Floors and Tables

The spreadsheet pivots and charts reference `pos.order` data filtered by:
- `pos_config_id` — which POS terminal
- `table_id` — which restaurant table (`pos_restaurant.floor.table`)
- `customer_count` — number of covers/seats
- `amount_total` — order value

### Courses and Course Sequencing

Orders in restaurant POS can be sent in **courses** (`pos.order.line` with `line_number`). The dashboard tracks:
- Time from order creation to each course being sent
- Average course delivery time per table/floor
- Course sequencing performance

### Employee Attribution

With `pos_hr` installed, each POS order is linked to a cashier (`user_id`). The dashboard provides:
- Revenue per employee per shift
- Average order value by cashier
- Order count per employee

### Split Bill Tracking

Restaurant orders can be split across multiple payment lines (`pos.payment`). The dashboard:
- Tracks partial payments per order
- Shows outstanding balances per table
- Monitors split-bill payment completion rates

## Key Performance Indicators (KPIs)

### Revenue Metrics

| KPI | Source | Calculation |
|-----|--------|-------------|
| Total Revenue | `pos.order` | Sum of `amount_total` for posted orders |
| Average Order Value | `pos.order` | `amount_total` / order count |
| Revenue per Floor | `pos.order` grouped by `table_id.floor_id` | SUM per floor |
| Revenue per Table | `pos.order` grouped by `table_id` | SUM per table |

### Table Turnover

| KPI | Source | Calculation |
|-----|--------|-------------|
| Orders per Table | `pos.order` by `table_id` | COUNT per table |
| Average Turnover Time | `pos.order` (order to payment) | AVG duration |
| Table Utilization % | Orders / Operating hours | occupancy rate |

### Service Metrics

| KPI | Source | Calculation |
|-----|--------|-------------|
| Average Covers | `pos.order.customer_count` | AVG across orders |
| Covers per Shift | Grouped by `user_id` + date | SUM per employee/day |
| Course Delivery Time | `pos.order.line` timestamps | AVG(course_sent_time - order_time) |

### Payment Metrics

| KPI | Source | Calculation |
|-----|--------|-------------|
| Cash vs Card Split | `pos.payment` by `payment_method_id` | COUNT / SUM |
| Split Bill Completion | `pos.order` with multiple payments | COUNT completed / total |
| Outstanding Balance | `pos.order` residual | SUM where balance > 0 |

## Data Models Used

The dashboard reads from these models (via o-spreadsheet data sources):

### `pos.order`

Core POS order model. Relevant fields:
- `id`, `name` — order reference
- `date_order` — creation timestamp
- `user_id` — cashier (from `pos_hr`)
- `amount_total` — order total
- `state` — order state (draft, done, invoiced, etc.)
- `pos_reference` — POS-specific reference
- `table_id` — restaurant table link (`pos_restaurant`)
- `customer_count` — number of covers

### `pos.order.line`

Order line model. Relevant fields:
- `order_id` — parent order
- `product_id` — product sold
- `qty` — quantity
- `price_unit`, `price_subtotal` — pricing
- `line_number` — course sequence number (restaurant)
- `note` — line-level notes

### `pos_restaurant.floor`

Restaurant floor model:
- `name` — floor name (e.g., "Ground Floor", "Terrace")
- `sequence` — display order

### `pos_restaurant.table`

Restaurant table model:
- `name` — table name/number
- `floor_id` — parent floor
- `seats` — seat capacity
- `position_h`, `position_v` — floor plan coordinates

### `pos.payment`

Payment lines on orders. Relevant fields:
- `order_id` — parent order
- `payment_method_id` — cash, card, etc.
- `amount` — payment amount
- `session_id` — POS session

### `pos.session`

POS session model:
- `config_id` — POS config
- `user_id` — session responsible
- `start_at`, `stop_at` — session window

## o-Spreadsheet Data Sources

The dashboard uses o-spreadsheet's `pivot` data source type to pull data directly from Odoo's ORM:

```javascript
// Example pivot definition (in the dashboard JSON data)
{
  "pivots": {
    "1": {
      "type": "SPREADSHEET",
      "dataSet": {
        "model": "pos.order",
        "domain": [["state", "=", "done"]],
        "groupBy": ["table_id", "date_order:month"],
        "measures": ["amount_total:sum", "id:count"]
      }
    }
  }
}
```

The o-spreadsheet engine evaluates these pivot definitions server-side via RPC and returns aggregated data to the spreadsheet cells.

## Auto-Install Behavior

The module is marked as `auto_install: ['pos_hr', 'pos_restaurant']`. This means:

- When both `pos_hr` and `pos_restaurant` are installed (or get installed) in the same database, this module will automatically be installed
- No manual activation is needed — the dashboard appears in the spreadsheet dashboard list automatically
- This follows Odoo's `auto_install` mechanism for companion data modules

## Customization Points

To extend this dashboard for a specific restaurant:

1. **Create a new dashboard** inheriting from this one
2. Add custom KPIs by defining new pivot definitions
3. Add charts using the o-spreadsheet chart API
4. Restrict access via `spreadsheet.dashboard.group_ids`

Common customizations:
- Adding food-and-beverage category breakdown (via `pos.category`)
- Adding tip tracking (via `pos.payment` with tip payment method)
- Adding waste/spoilage tracking (via custom `pos.order.line` note field)

## Related

- [Modules/spreadsheet_dashboard](spreadsheet_dashboard.md) — Dashboard framework and data model
- [Modules/pos_restaurant](pos_restaurant.md) — Restaurant POS (floors, tables, split-bill, courses)
- [Modules/pos_hr](pos_hr.md) — POS employee login and attribution
- [Modules/spreadsheet](spreadsheet.md) — o-spreadsheet engine and formula language
- [Modules/point_of_sale](point_of_sale.md) — Base POS module
