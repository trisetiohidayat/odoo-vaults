---
tags: [odoo, odoo19, spreadsheet, dashboard, ecommerce, website-sale, online-shop]
---

# spreadsheet_dashboard_website_sale

## Overview

| Property | Value |
|----------|-------|
| Technical Name | `spreadsheet_dashboard_website_sale` |
| Category | Productivity/Dashboard |
| Depends | `spreadsheet_dashboard`, `website_sale` |
| Auto-install trigger | `website_sale` |
| License | LGPL-3 |
| Module type | Data-only (no Python models) |

Provides a pre-configured [spreadsheet_dashboard](Modules/spreadsheet_dashboard.md) template named "eCommerce" for online shop managers. Tracks online sales performance, product popularity, and channel attribution within the Website dashboard group. Auto-installs when `website_sale` is active.

## Module Architecture

Pure data module — no Python model code.

```
spreadsheet_dashboard_website_sale/
├── __init__.py               # empty
├── __manifest__.py           # depends on website_sale, auto_install
└── data/
    ├── dashboards.xml        # creates spreadsheet.dashboard record
    └── files/
        ├── ecommerce_dashboard.json        # live dashboard
        └── ecommerce_sample_dashboard.json # sample shown when no data
```

## Dashboard Record Definition

Source: `/data/dashboards.xml`

```xml
<record id="spreadsheet_dashboard_ecommerce" model="spreadsheet.dashboard">
    <field name="name">eCommerce</field>
    <field name="spreadsheet_binary_data" type="base64"
           file="spreadsheet_dashboard_website_sale/data/files/ecommerce_dashboard.json"/>
    <field name="main_data_model_ids"
           eval="[(4, ref('sale.model_sale_order'))]"/>
    <field name="sample_dashboard_file_path">
        spreadsheet_dashboard_website_sale/data/files/ecommerce_sample_dashboard.json
    </field>
    <field name="dashboard_group_id"
           ref="spreadsheet_dashboard.spreadsheet_dashboard_group_website"/>
    <field name="group_ids"
           eval="[Command.link(ref('sales_team.group_sale_manager'))]"/>
    <field name="sequence">200</field>
    <field name="is_published">True</field>
</record>
```

### Record Properties

| Field | Value | Significance |
|-------|-------|--------------|
| `name` | "eCommerce" | Dashboard navigation label |
| `dashboard_group_id` | `group_website` | Appears under "Website" section |
| `group_ids` | `sales_team.group_sale_manager` | Sales Managers can access |
| `sequence` | 200 | Position within Website group |
| `main_data_model_ids` | `sale.order` | Empty-check model |
| `is_published` | True | Visible immediately |

## Website Group Context

`spreadsheet_dashboard_group_website` contains dashboards relevant to website/eCommerce operations. Multiple modules contribute dashboards to this group:

| Module | Dashboard | Sequence |
|--------|-----------|----------|
| `spreadsheet_dashboard_im_livechat` | Live Chat | 100 |
| `spreadsheet_dashboard_im_livechat` | Live Chat - Ongoing | 125 |
| `spreadsheet_dashboard_website_sale` | eCommerce | 200 |
| `spreadsheet_dashboard_website_sale_slides` | eLearning | 200 |

The eCommerce and eLearning dashboards share sequence 200. Odoo sorts records at the same sequence alphabetically by name (eCommerce comes before eLearning).

## Access Control

`sales_team.group_sale_manager` controls access to the eCommerce dashboard. This is the same group as the Sales dashboards from `spreadsheet_dashboard_sale`. This choice makes sense — eCommerce is another channel of the same sales pipeline. The same Sales Manager who monitors offline sales can also view the online channel in the Website group.

## Data Sources and KPI Structure

`website_sale` adds `website_id` to `sale.order` — the critical field linking an order to the website it came from. The eCommerce dashboard filters or groups by `website_id` to distinguish online orders from manually-created sales orders.

### Primary Model: `sale.order`

| Field | Type | Dashboard Use |
|-------|------|---------------|
| `name` | Char | Order reference |
| `partner_id` | Many2one | Customer |
| `date_order` | Datetime | Order date/time |
| `website_id` | Many2one | Online shop (null = offline order) |
| `amount_total` | Monetary | Order total |
| `state` | Selection | Order status |
| `team_id` | Many2one | Sales team |
| `currency_id` | Many2one | Order currency |
| `cart_recovery_mail_sent` | Boolean | Abandoned cart recovery sent |
| `access_token` | Char | Unique order token (portal access) |

### Secondary Model: `sale.order.line`

| Field | Type | Dashboard Use |
|-------|------|---------------|
| `product_id` | Many2one | Product sold online |
| `product_uom_qty` | Float | Quantity ordered |
| `price_unit` | Monetary | Unit price |
| `price_subtotal` | Monetary | Line subtotal |
| `discount` | Float | Discount applied |

### website_sale-specific Fields and Models

| Model/Field | Purpose | Dashboard Use |
|-------------|---------|---------------|
| `website` | Multi-website configuration | Filter by website |
| `sale.order.website_id` | Links order to website | Channel dimension |
| `product.template.website_published` | Published status | Available products |
| `product.template.website_sequence` | Display order | Product ranking |
| Abandoned carts | Orders in draft/cancelled | Cart abandonment tracking |

## Key KPIs Tracked

**Online Revenue Overview**
- Total eCommerce revenue (filter: `website_id IS NOT NULL`)
- eCommerce revenue this month vs. last month
- eCommerce vs. total revenue ratio (online channel share)
- Revenue by website (for multi-website Odoo setups)

**Order Performance**
- Number of online orders per period
- Average order value (AOV) from online channel
- Order completion rate: confirmed vs. total carts created
- Orders per day (daily trend chart)

**Cart Abandonment**
- Carts created (sale.order in `draft` with `website_id`)
- Carts abandoned (draft with no conversion to `sale` state)
- Abandonment rate: `abandoned / total_carts × 100`
- Recovery campaigns: `cart_recovery_mail_sent = True`
- Recovered carts: previously abandoned orders now confirmed

**Product Performance Online**
- Top products by online revenue
- Top products by online quantity sold
- Products with high abandonment (added to cart but not purchased)
- Out-of-stock products affecting online availability
- Products not yet published (`website_published = False`) vs. generating revenue

**Customer Analytics**
- New customers from online channel (first purchase)
- Returning customers (customer lifetime value)
- Customer geography (country from shipping address)
- Guest checkout vs. registered account ratio

**Conversion Funnel**

```
Website visitor
    → Adds product to cart (sale.order draft with website_id)
    → Completes checkout (sale.order → state = 'sent' or 'sale')
    → Payment confirmed (state = 'sale')
    → Fulfillment (invoice_status, delivery)
```

Dashboard typically shows:
- Carts created (top of funnel)
- Checkouts initiated (added customer info)
- Orders confirmed (bottom of funnel)
- Conversion rate = confirmed / carts created

**Revenue by Payment Method**
- Credit card revenue
- PayPal revenue
- Bank transfer revenue
- Other payment providers
(Requires `payment` module integration)

## Website Multi-Channel Analysis

If multiple websites are configured in Odoo (e.g., a main shop + a B2B portal + a regional site), `website_id` distinguishes them. The dashboard can show:
- Revenue per website
- AOV per website
- Conversion rate per website
- Which website generates the most traffic (requires `website_visitor` model)

## Relationship with Sales Dashboard

The eCommerce dashboard is the online-channel complement to the Sales dashboard from `spreadsheet_dashboard_sale`:

| Aspect | Sales Dashboard | eCommerce Dashboard |
|--------|----------------|---------------------|
| Data source | All `sale.order` | `sale.order WHERE website_id IS NOT NULL` |
| Group | Sales | Website |
| Focus | Revenue & pipeline | Online conversion & products |
| Cart tracking | No | Yes (draft orders from web) |

The two dashboards share `sale.order` as their primary model but filter and visualize it differently.

## Auto-Install Behavior

```python
'auto_install': ['website_sale'],
```

`website_sale` is the module that turns Odoo's website into an online shop. When activated, the eCommerce dashboard auto-installs. Any business running an Odoo webshop gets this dashboard immediately.

## Dependencies Chain

```
spreadsheet_dashboard_website_sale
├── spreadsheet_dashboard   # base framework
└── website_sale            # depends on:
    ├── website             # website model, multi-website
    ├── sale                # sale.order (adds website_id)
    ├── stock               # inventory integration
    └── payment             # payment providers
```

## Customization

1. **UTM tracking**: If `utm` module is installed, add `utm_source`, `utm_medium`, `utm_campaign` dimensions to the order table for marketing attribution
2. **Pricelist analysis**: Group by `pricelist_id` to see which price lists drive the most eCommerce revenue
3. **Promotion codes**: If `loyalty` module is installed, add coupon/promo code redemption metrics
4. **Page views correlation**: For websites using `website_visitor`, correlate product page views with purchase rates

## Related Modules

- [spreadsheet_dashboard](Modules/spreadsheet_dashboard.md) — Dashboard framework
- [spreadsheet_dashboard_sale](Modules/spreadsheet_dashboard_sale.md) — Offline sales analytics (same data, different filter)
- [spreadsheet_dashboard_website_sale_slides](Modules/spreadsheet_dashboard_website_sale_slides.md) — eLearning analytics (same Website group)
- [spreadsheet_account](Modules/spreadsheet_account.md) — Accounting formulas for financial integration
- `website_sale` — eCommerce shop: `website_id` on orders, product publishing

## Source Files

- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_website_sale/__manifest__.py`
- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_website_sale/data/dashboards.xml`
- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_website_sale/data/files/ecommerce_dashboard.json`
- `/Users/tri-mac/odoo/odoo19/odoo/addons/spreadsheet_dashboard_website_sale/data/files/ecommerce_sample_dashboard.json`
