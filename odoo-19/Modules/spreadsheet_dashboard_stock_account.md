---
tags: [odoo, odoo19, spreadsheet, dashboard, stock, inventory, stock-account, valuation, warehouse]
---

# spreadsheet_dashboard_stock_account

## Overview

| Property | Value |
|----------|-------|
| Technical Name | `spreadsheet_dashboard_stock_account` |
| Category | Productivity/Dashboard |
| Depends | `spreadsheet_dashboard`, `stock_account` |
| Auto-install trigger | `stock_account` |
| License | LGPL-3 |
| Module type | Data-only (no Python models) |

Provides a pre-configured [spreadsheet_dashboard](Modules/spreadsheet_dashboard.md) template named "Warehouse Metrics" for warehouse managers and financial controllers. Focuses on inventory valuation and stock-level analytics that require both inventory (`stock`) and accounting (`stock_account`) data. Auto-installs when `stock_account` is active and appears in the Logistics dashboard group at sequence 300.

## Module Architecture

Pure data module — no Python model code.

```
spreadsheet_dashboard_stock_account/
├── __init__.py               # empty
├── __manifest__.py           # depends on stock_account, auto_install
└── data/
    ├── dashboards.xml        # creates spreadsheet.dashboard record
    └── files/
        ├── warehouse_metrics_dashboard.json        # live dashboard
        └── warehouse_metrics_sample_dashboard.json # sample fallback
```

## Dashboard Record Definition

Source: `/data/dashboards.xml`

```xml
<record id="spreadsheet_dashboard_warehouse_metrics" model="spreadsheet.dashboard">
    <field name="name">Warehouse Metrics</field>
    <field name="spreadsheet_binary_data" type="base64"
           file="spreadsheet_dashboard_stock_account/data/files/warehouse_metrics_dashboard.json"/>
    <field name="main_data_model_ids"
           eval="[(4, ref('stock.model_stock_quant'))]"/>
    <field name="sample_dashboard_file_path">
        spreadsheet_dashboard_stock_account/data/files/warehouse_metrics_sample_dashboard.json
    </field>
    <field name="dashboard_group_id"
           ref="spreadsheet_dashboard.spreadsheet_dashboard_group_logistics"/>
    <field name="group_ids"
           eval="[Command.link(ref('stock.group_stock_manager'))]"/>
    <field name="sequence">300</field>
    <field name="is_published">True</field>
</record>
```

### Record Properties

| Field | Value | Significance |
|-------|-------|--------------|
| `name` | "Warehouse Metrics" | Dashboard navigation label |
| `dashboard_group_id` | `group_logistics` | Appears under "Logistics" section |
| `group_ids` | `stock.group_stock_manager` | Stock Managers only |
| `sequence` | 300 | Position within Logistics group |
| `main_data_model_ids` | `stock.quant` | Empty check uses stock quant records |
| `is_published` | True | Visible immediately |

## Framework Integration

### Empty-Data Check on stock.quant

`_dashboard_is_empty()` checks `stock.quant.search_count([], limit=1)`. `stock.quant` records are created when inventory is received or adjusted. On a fresh database, no quants exist, so the framework serves the sample dashboard.

A notable characteristic: even if `sale.order` has data, if no goods have ever been received into stock, the dashboard falls back to sample data. This is appropriate — the "Warehouse Metrics" dashboard is only meaningful once inventory exists.

### Logistics Group

`spreadsheet_dashboard_group_logistics` is the Logistics dashboard group. Only `spreadsheet_dashboard_stock_account` adds a dashboard to this group in the standard distribution, making "Warehouse Metrics" the sole Logistics dashboard.

### Access: Stock Managers

`stock.group_stock_manager` is the warehouse management group. Regular stock users (`group_stock_user`) who process pickings cannot see this dashboard. The financial controller and warehouse manager roles both typically have this access.

## Why stock_account (Not stock Alone)

The dependency is on `stock_account`, not just `stock`. This is deliberate:

- **`stock` alone**: Tracks quantities (how many units, where, which lot)
- **`stock_account`**: Adds financial valuation (what those units are worth)

The "Warehouse Metrics" dashboard includes valuation KPIs (inventory value in currency). Without `stock_account`, there would be no `stock.valuation.layer` records and no inventory value data to display.

Companies using `stock` without `stock_account` (e.g., non-perpetual inventory) would need to manually install this dashboard module.

## Data Sources and KPI Structure

### Primary Model: `stock.quant`

`stock.quant` stores the current on-hand stock per product per location.

| Field | Type | Dashboard Use |
|-------|------|---------------|
| `product_id` | Many2one | Product dimension |
| `location_id` | Many2one | Warehouse/location dimension |
| `lot_id` | Many2one | Lot/serial number tracking |
| `quantity` | Float | On-hand quantity |
| `reserved_quantity` | Float | Quantity reserved for outgoing moves |
| `available_quantity` | Float | `quantity - reserved_quantity` |
| `inventory_quantity` | Float | Manual count quantity |
| `in_date` | Datetime | When this quant was last updated |

### Secondary Model: `stock.valuation.layer` (from stock_account)

This model records every inventory value change. It is the accounting bridge for inventory.

| Field | Type | Dashboard Use |
|-------|------|---------------|
| `product_id` | Many2one | Product |
| `stock_move_id` | Many2one | Triggering stock move |
| `quantity` | Float | Quantity change |
| `unit_cost` | Monetary | Cost per unit at time of move |
| `value` | Monetary | Total value change |
| `remaining_qty` | Float | Remaining quantity at this cost layer |
| `remaining_value` | Monetary | Remaining value at this cost layer |
| `description` | Char | Type of operation |
| `company_id` | Many2one | Company |
| `create_date` | Datetime | When layer was created |

### Supporting Models

| Model | Access Path | Dashboard Use |
|-------|------------|---------------|
| `product.product` | `stock_quant.product_id` | Product name, reference |
| `product.category` | via product | Category-level aggregation |
| `stock.warehouse` | via location | Warehouse breakdown |
| `stock.location` | `stock_quant.location_id` | Location detail |
| `stock.move` | via valuation layer | Operation type tracking |
| `account.account` | via valuation | Inventory account balance |

## Key KPIs Tracked

**Current Inventory Value**
- Total inventory value (sum of `stock.valuation.layer.remaining_value`)
- Inventory value by product category
- Inventory value by warehouse/location
- Value change from previous period

**Stock Level Analysis**
- On-hand quantity by product
- Available quantity (excluding reservations)
- Reserved quantity (committed to outgoing orders)
- Products with zero stock
- Products with negative stock (data quality issue)

**Stock Turnover**
```
Turnover = (COGS for period) / (Average inventory value for period)
```
High turnover → inventory is selling quickly (good for most businesses)
Low turnover → slow-moving stock or over-stocking

Dashboard shows:
- Turnover rate by product
- Turnover rate by category
- Products with the lowest turnover (potential dead stock)

**Reorder Analysis**
- Products below reorder point (`stock.warehouse.orderpoint`)
- Days of stock remaining: `available_quantity / (average_daily_consumption)`
- Products at risk of stockout

**Valuation Method Impact**

`stock_account` supports three inventory costing methods (set per product category):
- **Standard Price**: Fixed cost per unit
- **Average Cost (AVCO)**: Weighted average, recomputed on each receipt
- **FIFO**: First-in, first-out cost layers

The `stock.valuation.layer` records reflect these methods. Dashboard shows current values regardless of method, but interpretation differs.

**Inventory Movements**
- Receipts value this period (incoming goods value)
- Delivery/usage value this period (outgoing goods value)
- Inventory adjustments (manual corrections)
- Returns and refunds value

**Aging Analysis**
- Stock on-hand with `in_date` older than 90/180/365 days
- Value of aged stock (slow-moving inventory)
- Lot/serial expiry analysis (if expiry tracking enabled)

## Accounting Integration

`stock_account` creates journal entries automatically for inventory movements:

```
Receipt (vendor → stock):
    Dr. Stock Account (asset)
    Cr. Stock Interim Received account

Delivery (stock → customer):
    Dr. Cost of Goods Sold
    Cr. Stock Account (asset)

Inventory Adjustment:
    Dr./Cr. Stock Account (asset)
    Dr./Cr. Inventory Adjustment account
```

The dashboard can reflect these accounting impacts — the inventory value shown in the spreadsheet should reconcile with the balance of inventory accounts in [spreadsheet_account](Modules/spreadsheet_account.md).

## Stock Move Flow

```
Purchase Order confirmed
    → stock.picking created (receipt type)
    → stock.move: vendor location → stock location

Goods received (picking validated):
    → stock.quant updated (quantity increases)
    → stock.valuation.layer created (value recorded)
    → account.move created (journal entry)

Sales Order confirmed:
    → stock.picking created (delivery type)
    → stock.move reserved (quant.reserved_quantity increases)

Delivery validated:
    → stock.quant updated (quantity decreases)
    → stock.valuation.layer created (negative value)
    → account.move created (COGS entry)
```

## Auto-Install Behavior

```python
'auto_install': ['stock_account'],
```

`stock_account` is installed when a company uses perpetual inventory valuation (the standard for manufacturing and distribution). Auto-installing this dashboard ensures warehouse controllers and CFOs have inventory metrics immediately.

## Dependencies Chain

```
spreadsheet_dashboard_stock_account
├── spreadsheet_dashboard   # base framework
└── stock_account           # depends on:
    ├── stock               # stock.quant, stock.move, stock.picking
    └── account             # account.move, account.account
```

## Multi-Company and Multi-Warehouse

`stock.quant` and `stock.valuation.layer` both have `company_id`. The dashboard respects the current user's company context, showing only the relevant company's inventory. For multi-company setups, each company sees its own inventory metrics.

Warehouse filtering uses `location_id` → `location_id.warehouse_id` to show per-warehouse breakdown.

## Customization

1. **Low stock alert**: Add conditional formatting to highlight rows where `available_quantity < reorder_point`
2. **ABC analysis**: Add a classification column (A=top 20% by value, B=middle 30%, C=bottom 50%) and chart by class
3. **Currency conversion**: For multi-currency setups, add formulas converting inventory values to reporting currency
4. **Vendor lead time**: Add `product.supplierinfo.delay` to compute expected replenishment date

## Related Modules

- [spreadsheet_dashboard](Modules/spreadsheet_dashboard.md) — Dashboard framework
- [spreadsheet_account](Modules/spreadsheet_account.md) — Accounting formulas for GL balance integration
- `stock_account` — Inventory valuation and accounting entries
- `stock` — Core inventory management models

## Source Files

- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_stock_account/__manifest__.py`
- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_stock_account/data/dashboards.xml`
- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_stock_account/data/files/warehouse_metrics_dashboard.json`
- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_stock_account/data/files/warehouse_metrics_sample_dashboard.json`
