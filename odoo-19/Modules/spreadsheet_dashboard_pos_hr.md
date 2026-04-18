---
tags: [odoo, odoo19, spreadsheet, dashboard, pos, point-of-sale, hr, employee]
---

# spreadsheet_dashboard_pos_hr

## Overview

| Property | Value |
|----------|-------|
| Technical Name | `spreadsheet_dashboard_pos_hr` |
| Category | Productivity/Dashboard |
| Depends | `spreadsheet_dashboard`, `pos_hr` |
| Auto-install trigger | `pos_hr` |
| License | LGPL-3 |
| Module type | Data-only (no Python models) |

Provides a pre-configured [spreadsheet_dashboard](spreadsheet_dashboard.md) template named "Point of Sale" for POS managers. Combines POS order reporting with employee/cashier data from `pos_hr`. Auto-installs when `pos_hr` is active and appears in the Sales dashboard group.

## Module Architecture

Pure data module — no Python model code.

```
spreadsheet_dashboard_pos_hr/
├── __init__.py               # empty
├── __manifest__.py           # depends on pos_hr, auto_install
└── data/
    ├── dashboards.xml        # creates spreadsheet.dashboard record
    └── files/
        ├── pos_dashboard.json        # live dashboard spreadsheet
        └── pos_sample_dashboard.json # shown when no POS data exists
```

## Dashboard Record Definition

Source: `/data/dashboards.xml`

```xml
<record id="spreadsheet_dashboard_pos" model="spreadsheet.dashboard">
    <field name="name">Point of Sale</field>
    <field name="spreadsheet_binary_data" type="base64"
           file="spreadsheet_dashboard_pos_hr/data/files/pos_dashboard.json"/>
    <field name="main_data_model_ids"
           eval="[(4, ref('point_of_sale.model_report_pos_order')),
                  (4, ref('point_of_sale.model_pos_order'))]"/>
    <field name="sample_dashboard_file_path">
        spreadsheet_dashboard_pos_hr/data/files/pos_sample_dashboard.json
    </field>
    <field name="dashboard_group_id"
           ref="spreadsheet_dashboard.spreadsheet_dashboard_group_sales"/>
    <field name="group_ids"
           eval="[Command.link(ref('point_of_sale.group_pos_manager'))]"/>
    <field name="sequence">300</field>
    <field name="is_published">True</field>
</record>
```

### Record Properties

| Field | Value | Significance |
|-------|-------|--------------|
| `name` | "Point of Sale" | Displayed in dashboard navigation |
| `dashboard_group_id` | `group_sales` | Appears under "Sales" section |
| `group_ids` | `point_of_sale.group_pos_manager` | Only POS Managers can access |
| `sequence` | 300 | High sequence = appears after Sales and other Sales dashboards |
| `main_data_model_ids` | `report.pos.order` AND `pos.order` | Both checked for empty-data fallback |
| `is_published` | True | Visible immediately |

## Framework Integration

### Dual Empty-Data Check

This module is notable for registering **two** models in `main_data_model_ids`:
- `report.pos.order` — the POS reporting SQL view
- `pos.order` — raw POS orders

`_dashboard_is_empty()` in the framework checks **any** of the registered models: if `search_count([], limit=1)` returns 0 for any of them, the dashboard is considered empty. In practice, if `pos.order` is empty, `report.pos.order` will also be empty. This dual registration ensures the empty check works whether or not the reporting view is enabled.

When both are empty, the framework serves `pos_sample_dashboard.json` with pre-populated demo retail data.

### Sales Group Placement

`spreadsheet_dashboard_group_sales` contains sales-related dashboards. Sequence 300 is the highest among the bundled sales dashboards, placing POS last in the Sales group (after Sales at 100, Product at 200). This reflects POS being a sub-channel of the broader sales picture.

### Access Control

`point_of_sale.group_pos_manager` is the management group for POS, distinct from the cashier group (`group_pos_user`). Cashiers operate the POS terminal but cannot access the analytics dashboard — only managers can.

## Data Sources and KPI Structure

### Primary Model: `report.pos.order`

This is a pre-aggregated reporting SQL view defined in `point_of_sale`. It aggregates individual POS order lines into a flat reporting structure.

| Field | Type | Dashboard Use |
|-------|------|---------------|
| `id` | Integer | Record ID (order line ref) |
| `name` | Char | Order reference |
| `date_order` | Datetime | Transaction timestamp |
| `partner_id` | Many2one | Customer (if identified) |
| `product_id` | Many2one | Product sold |
| `state` | Selection | paid/done/cancel |
| `price_total` | Float | Line total |
| `price_subtotal` | Float | Line total before tax |
| `qty` | Float | Quantity sold |
| `discount` | Float | Discount applied |
| `session_id` | Many2one | POS session |
| `config_id` | Many2one | POS configuration (shop) |
| `pricelist_id` | Many2one | Price list used |
| `journal_id` | Many2one | Payment method |
| `company_id` | Many2one | Company |
| `nbr_lines` | Integer | Lines per order |

### Secondary Model: `pos.order`

Raw order data for session-level analysis:

| Field | Type | Dashboard Use |
|-------|------|---------------|
| `name` | Char | Order reference |
| `date_order` | Datetime | Order timestamp |
| `session_id` | Many2one | POS session |
| `employee_id` | Many2one | Cashier (from pos_hr) |
| `amount_total` | Monetary | Order total |
| `amount_tax` | Monetary | Tax amount |
| `state` | Selection | Order status |
| `payment_ids` | One2many | Payment methods used |

### pos_hr Employee Integration

`pos_hr` adds `employee_id` to `pos.order`, enabling per-cashier reporting:

```
pos.order
    employee_id → hr.employee
        name, department_id, job_id
```

This field is what makes the "Point of Sale" dashboard a `pos_hr` dashboard rather than a plain `point_of_sale` dashboard — without `employee_id`, there would be no per-cashier breakdown.

### Session Model: `pos.session`

| Field | Type | Dashboard Use |
|-------|------|---------------|
| `name` | Char | Session reference (e.g., "POS/00001") |
| `config_id` | Many2one | Shop/terminal config |
| `start_at` | Datetime | Session open time |
| `stop_at` | Datetime | Session close time |
| `state` | Selection | opened/closing/closed |
| `cash_register_balance_start` | Monetary | Opening cash |
| `cash_register_balance_end_real` | Monetary | Actual closing cash |
| `cash_register_difference` | Monetary | Variance (expected vs. actual) |

## Key KPIs Tracked

**Sales Volume**
- Total orders per day/week/month
- Total revenue per period
- Average order value (AOV): `amount_total / order_count`
- Orders per hour (traffic pattern)
- Revenue by payment method (cash, card, gift card)

**Cashier Performance (pos_hr feature)**
- Revenue per employee/cashier in a session
- Order count per cashier
- Average order value per cashier
- Discount rate per cashier (flagging excessive discounting)
- Cashier shift comparison (morning vs. afternoon)

**Product Analysis**
- Top-selling products by quantity
- Top-selling products by revenue
- Product category revenue breakdown
- Slow-moving products (low quantity/revenue)
- Return/refund rate by product

**Session Analytics**
- Revenue per session
- Session duration
- Cash reconciliation: expected vs. actual closing balance
- Sessions with closing discrepancies (audit flag)
- Busiest hours across sessions

**Customer Insights**
- Identified vs. anonymous customer ratio
- Revenue from identified customers (loyalty)
- Return customer rate

## POS Session Lifecycle

```
Manager opens session
    ↓ state = 'opened'
Cashiers process orders
    → pos.order created (state = 'draft' → 'paid')
    → employee_id assigned (from pos_hr)
Cashier reconciles cash
    ↓ state = 'closing_control'
Manager validates and closes
    ↓ state = 'closed'
    → Accounting entries posted (if stock_account/pos_account)
```

The dashboard aggregates across all sessions to show performance trends. Closed sessions provide the complete data; open sessions show partial data.

## Auto-Install Behavior

```python
'auto_install': ['pos_hr'],
```

`pos_hr` itself depends on `point_of_sale` and `hr`. When both POS and HR are set up together (the typical retail configuration), this dashboard auto-installs, giving POS managers their analytics immediately.

Without `pos_hr` (POS used without HR employee tracking), this dashboard does not auto-install. A plain `point_of_sale` installation without employee attribution wouldn't benefit from the per-cashier KPIs this dashboard is designed around.

## Dependencies Chain

```
spreadsheet_dashboard_pos_hr
├── spreadsheet_dashboard   # base framework
└── pos_hr                  # depends on:
    ├── point_of_sale       # pos.order, pos.session, report.pos.order
    └── hr                  # hr.employee (for employee_id on orders)
```

## Retail Use Cases

**Multi-terminal setup**: If a store has multiple POS configurations (different tills or shops), the `config_id` dimension allows filtering by terminal. The dashboard can show which till is generating the most revenue.

**Shift management**: With `pos_hr` employee attribution, managers can run shift-by-shift analysis: morning shift revenue vs. afternoon shift, allowing staff scheduling optimization.

**Inventory integration**: If `point_of_sale` is used with `stock`, product sales automatically reduce inventory. The dashboard focuses on revenue KPIs; for inventory-impact reporting, combine with `spreadsheet_dashboard_stock_account`.

## Customization

1. **Add product category filter**: Insert a slicer by `product_id.categ_id` to filter by category
2. **Holiday vs. weekday**: Add a formula computing day-of-week from `date_order` to compare weekend vs. weekday performance
3. **Cashier target tracking**: Add a row for each cashier with a target column (manual input) and actual revenue, computing achievement %
4. **Session variance alert**: Highlight rows where `cash_register_difference` exceeds threshold

## Related Modules

- [spreadsheet_dashboard](spreadsheet_dashboard.md) — Dashboard framework
- [spreadsheet_dashboard_sale](spreadsheet_dashboard_sale.md) — Sales order dashboards (non-POS)
- `pos_hr` — Adds employee attribution to POS orders
- `point_of_sale` — Core POS models and reporting view

## Source Files

- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_pos_hr/__manifest__.py`
- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_pos_hr/data/dashboards.xml`
- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_pos_hr/data/files/pos_dashboard.json`
- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_pos_hr/data/files/pos_sample_dashboard.json`
