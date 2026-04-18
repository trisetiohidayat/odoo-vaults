---
tags: [odoo, odoo19, spreadsheet, dashboard, sales, sale-order, crm]
---

# spreadsheet_dashboard_sale

## Overview

| Property | Value |
|----------|-------|
| Technical Name | `spreadsheet_dashboard_sale` |
| Category | Productivity/Dashboard |
| Depends | `spreadsheet_dashboard`, `sale` |
| Auto-install trigger | `sale` |
| License | LGPL-3 |
| Module type | Data-only (no Python models) |

Provides two pre-configured [spreadsheet_dashboard](spreadsheet_dashboard.md) templates for sales managers: a **Sales** dashboard focused on revenue and orders, and a **Product** dashboard focused on product performance analytics. Auto-installs when the `sale` module is active.

This is the most broadly relevant spreadsheet dashboard in the suite — virtually every Odoo installation with sales capabilities will have it.

## Module Architecture

Pure data module — two JSON spreadsheets plus a single XML data file.

```
spreadsheet_dashboard_sale/
├── __init__.py               # empty
├── __manifest__.py           # depends on sale, auto_install
└── data/
    ├── dashboards.xml        # creates 2 spreadsheet.dashboard records
    └── files/
        ├── sales_dashboard.json          # Sales dashboard live data
        ├── sales_sample_dashboard.json   # Sample shown when no sales data
        ├── product_dashboard.json        # Product dashboard live data
        └── product_sample_dashboard.json # Sample shown when no sales data
```

## Dashboard Record Definitions

Source: `/data/dashboards.xml`

### Dashboard 1: Sales

```xml
<record id="spreadsheet_dashboard_sales" model="spreadsheet.dashboard">
    <field name="name">Sales</field>
    <field name="spreadsheet_binary_data" type="base64"
           file="spreadsheet_dashboard_sale/data/files/sales_dashboard.json"/>
    <field name="main_data_model_ids"
           eval="[(4, ref('sale.model_sale_order'))]"/>
    <field name="sample_dashboard_file_path">
        spreadsheet_dashboard_sale/data/files/sales_sample_dashboard.json
    </field>
    <field name="dashboard_group_id"
           ref="spreadsheet_dashboard.spreadsheet_dashboard_group_sales"/>
    <field name="group_ids"
           eval="[Command.link(ref('sales_team.group_sale_manager'))]"/>
    <field name="sequence">100</field>
    <field name="is_published">True</field>
</record>
```

### Dashboard 2: Product

```xml
<record id="spreadsheet_dashboard_product" model="spreadsheet.dashboard">
    <field name="name">Product</field>
    <field name="spreadsheet_binary_data" type="base64"
           file="spreadsheet_dashboard_sale/data/files/product_dashboard.json"/>
    <field name="main_data_model_ids"
           eval="[(4, ref('sale.model_sale_order'))]"/>
    <field name="sample_dashboard_file_path">
        spreadsheet_dashboard_sale/data/files/product_sample_dashboard.json
    </field>
    <field name="dashboard_group_id"
           ref="spreadsheet_dashboard.spreadsheet_dashboard_group_sales"/>
    <field name="group_ids"
           eval="[Command.link(ref('sales_team.group_sale_manager'))]"/>
    <field name="sequence">200</field>
    <field name="is_published">True</field>
</record>
```

### Record Properties Summary

| Property | Sales Dashboard | Product Dashboard |
|----------|----------------|-------------------|
| `name` | "Sales" | "Product" |
| `sequence` | 100 | 200 |
| `group` | Sales | Sales |
| `access` | `sales_team.group_sale_manager` | `sales_team.group_sale_manager` |
| `main_data_model_ids` | `sale.order` | `sale.order` |
| Sample file | Yes | Yes |

Both dashboards require the Sales Manager group. Regular salespeople (`group_sale_salesman`) do not see these dashboards.

## Framework Integration

### Empty-Data Fallback

Both dashboards check `sale.order.search_count([], limit=1)`. If no orders exist (fresh database), both switch to their sample JSON files. The Sales sample shows typical revenue charts with demo data; the Product sample shows product performance charts with hypothetical products.

### Sales Group

`spreadsheet_dashboard_group_sales` is the primary group for sales analytics. With this module, POS HR also adds a dashboard at sequence 300, giving the Sales group three dashboards: Sales (100), Product (200), Point of Sale (300). The ordering reflects analytical priority.

## Data Sources and KPI Structure

### Primary Model: `sale.order`

| Field | Type | Dashboard Use |
|-------|------|---------------|
| `name` | Char | Order reference |
| `partner_id` | Many2one | Customer |
| `date_order` | Datetime | Order date (primary time dimension) |
| `team_id` | Many2one | Sales team |
| `user_id` | Many2one | Salesperson |
| `state` | Selection | Pipeline stage |
| `amount_untaxed` | Monetary | Revenue before tax |
| `amount_tax` | Monetary | Tax amount |
| `amount_total` | Monetary | Total revenue |
| `invoice_status` | Selection | Billing status |
| `currency_id` | Many2one | Order currency |
| `company_id` | Many2one | Multi-company dimension |
| `validity_date` | Date | Quote expiry |
| `commitment_date` | Date | Promised delivery date |

### Secondary Model: `sale.order.line`

| Field | Type | Dashboard Use |
|-------|------|---------------|
| `product_id` | Many2one | Product sold |
| `product_uom_qty` | Float | Ordered quantity |
| `qty_delivered` | Float | Delivered quantity |
| `qty_invoiced` | Float | Invoiced quantity |
| `price_unit` | Monetary | Unit price |
| `price_subtotal` | Monetary | Line subtotal |
| `discount` | Float | Discount percentage |
| `product_updatable` | Boolean | Line editability flag |

### Related Models for Dimensions

| Model | Access Path | Dashboard Use |
|-------|------------|---------------|
| `res.partner` | `partner_id` | Customer name, country, industry |
| `crm.team` | `team_id` | Sales team breakdown |
| `res.users` | `user_id` | Salesperson breakdown |
| `product.product` | `order_line.product_id` | Product performance |
| `product.category` | via product | Category revenue analysis |
| `account.move` | via `invoice_ids` | Invoicing status |

## Sales Dashboard KPIs

**Revenue Overview**
- Total revenue (confirmed orders: state in `sale`, `done`)
- Revenue this month vs. last month (MoM growth %)
- Revenue this quarter vs. last quarter
- Revenue by sales team
- Revenue by salesperson (ranking)
- Revenue by customer (top clients)

**Order Volume**
- Total order count per period
- Average order value (AoV): `amount_total / order_count`
- Order count by state (draft/sent/sale/done/cancelled)
- Orders created vs. orders confirmed (conversion)

**Pipeline Health (Quote Analysis)**
- Quotes (state = `draft` or `sent`) total value
- Quote-to-order conversion rate
- Quotes by expiry date (urgency)
- Average quote validity period

**Delivery Status**
- Orders with `invoice_status = 'to invoice'` (ready to bill)
- Orders partially delivered
- Orders fully delivered and invoiced
- Commitment date compliance (on-time delivery rate)

**Trend Analysis**
- Monthly revenue trend (12-month rolling)
- Week-over-week order growth
- Seasonal patterns by month

## Product Dashboard KPIs

**Product Performance**
- Top products by revenue (by `sale.order.line.price_subtotal`)
- Top products by quantity sold
- Product revenue ranking (sorted table)
- Products not sold in the current period

**Category Analysis**
- Revenue by product category
- Quantity by category
- Category mix (% of total revenue per category)
- Category trends over time

**Pricing Analysis**
- Average unit price per product
- Discount rate by product (average `discount` on order lines)
- Price variance (min/max/avg across orders)
- Products frequently discounted

**Delivery Performance**
- `qty_delivered / product_uom_qty` ratio per product
- Products with delivery backlog
- Average time from order to delivery by product

## Order State Flow

```
draft (Quotation)
    ↓ send by email → state = 'sent' (Quotation Sent)
    ↓ confirm → state = 'sale' (Sales Order)
    ↓ lock → state = 'done' (Locked)
    ↓ (or) cancel → state = 'cancel'
```

The Sales dashboard typically filters to `state in ('sale', 'done')` for revenue KPIs, while the pipeline view includes `draft` and `sent` for quote analysis.

## Auto-Install Behavior

```python
'auto_install': ['sale'],
```

The `sale` module is one of the most commonly installed Odoo modules. Auto-installing at the same time as `sale` ensures that every sales team gets their dashboards from day one. No separate installation or configuration required.

## Multi-Dashboard Design Rationale

The split between Sales and Product dashboards serves two management audiences:

- **Sales managers** use the Sales dashboard for revenue targets, team performance, and pipeline review (daily/weekly cadence).
- **Product managers / merchandising teams** use the Product dashboard for assortment analysis, pricing review, and inventory planning (weekly/monthly cadence).

Keeping them separate allows each audience to bookmark their specific view. Both have the same access group (Sales Manager), but the content focus differs significantly.

## Interaction with Other Modules

| Module | Impact on This Dashboard |
|--------|--------------------------|
| `sale_timesheet` | `sale_timesheet` dashboard adds timesheet-billed revenue visibility |
| `website_sale` | eCommerce dashboard adds website order channel |
| `crm` | CRM module adds `opportunity_id` to orders; CRM funnel analytics |
| `account` | Invoicing status fields populated once account module installed |
| `stock` | Delivery quantities (`qty_delivered`) populated by stock moves |

## Dependencies Chain

```
spreadsheet_dashboard_sale
├── spreadsheet_dashboard   # base framework
└── sale                    # depends on:
    ├── base                # res.partner, res.users
    ├── product             # product.product, product.category
    ├── sales_team          # crm.team, group_sale_manager
    └── account             # invoicing integration (optional)
```

## Customization

**Common Sales dashboard extensions:**
1. **Target tracking**: Add a manual input row for monthly targets, compute achievement %
2. **Won/lost pipeline**: Add a section tracking quotes progressing through stages
3. **Customer segment filter**: Add a slicer by partner industry or country
4. **Salesperson comparison**: Add a ranking chart sorted by revenue with YoY delta

**Common Product dashboard extensions:**
1. **Margin analysis**: If cost price data is available, add margin % per product
2. **Stock availability**: Add `qty_available` from `product.product` alongside sales data
3. **New vs. repeat**: Track whether products are bought by new vs. returning customers

## Related Modules

- [spreadsheet_dashboard](spreadsheet_dashboard.md) — Dashboard framework
- [spreadsheet_account](spreadsheet_account.md) — Accounting formulas for financial integration
- [spreadsheet_dashboard_sale_timesheet](spreadsheet_dashboard_sale_timesheet.md) — Timesheet-billed sales analytics
- [spreadsheet_dashboard_website_sale](spreadsheet_dashboard_website_sale.md) — eCommerce channel analytics

## Source Files

- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_sale/__manifest__.py`
- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_sale/data/dashboards.xml`
- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_sale/data/files/sales_dashboard.json`
- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_sale/data/files/sales_sample_dashboard.json`
- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_sale/data/files/product_dashboard.json`
- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_sale/data/files/product_sample_dashboard.json`
