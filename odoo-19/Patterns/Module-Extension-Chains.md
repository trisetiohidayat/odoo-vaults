---
title: "Odoo 19 Module Extension Chains"
type: patterns
tags: [odoo, odoo19, architecture, inheritance, extension-modules]
related:
  - "[Core/BaseModel](../Core/BaseModel.md)"
  - "[Patterns/Inheritance Patterns](Inheritance Patterns.md)"
  - "[Modules/Stock](../Modules/Stock.md)"
  - "[Modules/Sale](../Modules/Sale.md)"
  - "[Modules/Purchase](../Modules/Purchase.md)"
  - "[Modules/MRP](../Modules/MRP.md)"
  - "[Modules/Account](../Modules/Account.md)"
  - "[Modules/Project](../Modules/Project.md)"
created: 2026-04-14
---

# Odoo 19 Module Extension Chains

## Overview

Odoo 19 uses a sophisticated modular architecture where extension modules extend base modules through inheritance. This document catalogs the extension chains for key cross-module integration modules, detailing what each module extends, new models introduced, fields added, methods overridden, computed fields, onchanges, and ir.rules/ir.filters added.

This architecture follows Odoo's **classical inheritance pattern** (`_inherit`) where extension modules add fields and methods to existing models without creating new database tables, and **delegation** (`_inherits`) for composed models.

---

## Extension Chain Relationship Diagram

```
base
 ├── sale
 │    ├── sale_management
 │    │    └── sale
 │    └── sale_stock ──────────→ stock_account ──────────→ stock
 │         │                         ↑                    ↑
 │         └── sale_mrp ─────────────┘                    │
 │              │                                          │
 │              └── sale_timesheet ──→ sale_project ────→ project
 │                                              ↑
 │                                              └── project_account
 │                                                    ↑
 │                                              project_purchase ──→ purchase
 │                                                    ↑
purchase ──→ purchase_stock ──→ stock_account ─────────┘
                                    ↑
account ──→ account_accountant
```

---

## Parent-to-Child Module Relationship Table

| Parent Module | Child Module | Key Extension |
|---|---|---|
| `stock` | `stock_account` | Adds accounting valuation to stock |
| `stock` + `account` | `stock_account` | Bridges stock and accounting |
| `sale` | `sale_stock` | Delivery tracking on SO |
| `stock_account` | `sale_stock` | Stock picking from SO with valuation |
| `purchase` | `purchase_stock` | Receipt tracking on PO |
| `stock_account` | `purchase_stock` | Stock picking from PO with valuation |
| `sale` + `stock` | `sale_mrp` | Kit products / MO from SO |
| `sale_stock` | `sale_mrp` | Links MO to sale reference |
| `mrp` + `sale_stock` | `sale_mrp` | Production from sale orders |
| `mrp` + `stock_account` | `mrp_account` | WIP valuation, analytic on MO |
| `account` | `account_accountant` | Deferred revenue, check printing |
| `sale_project` + `hr_timesheet` | `sale_timesheet` | Timesheet billing on SO |
| `project` + `account` | `project_account` | Profitability from bills |
| `project_account` + `purchase` | `project_purchase` | Purchase visibility in project |
| `project` + `stock` | `project_stock` | Pickings linked to project |
| `website_sale` + `sale_stock` | `website_sale_stock` | Real-time inventory on website |
| `point_of_sale` + `loyalty` | `pos_loyalty` | Loyalty programs at POS |
| `point_of_sale` + `hr` | `pos_hr` | Employee login at POS |
| `pos_restaurant` | `pos_self_order` | Kiosk self-ordering |
| `point_of_sale` | `pos_restaurant` | Restaurant-specific POS features |

---

## 1. stock_account — WMS Accounting

**Location:** `~/odoo/odoo19/odoo/addons/stock_account/`

**Manifest Dependencies:** `['stock', 'account']`

**Purpose:** Bridges the `stock` and `account` modules to enable perpetual inventory valuation. Creates accounting journal entries automatically when stock moves are validated.

### Models Extended

| Model | Extension Type | Key Addition |
|---|---|---|
| `stock.quant` | `_inherit = 'stock.quant'` | Valuation fields, cost method |
| `stock.move` | `_inherit = 'stock.move'` | `value`, `_create_account_move()` |
| `stock.picking` | `_inherit = 'stock.picking'` | Valuation views |
| `stock.location` | `_inherit = 'stock.location'` | Valuation account fields |
| `stock.lot` | `_inherit = 'stock.lot'` | Lot-level valuation |
| `product.product` | `_inherit = 'product.product'` | Cost method, valuation |
| `account.move` | `_inherit = 'account.move'` | Valuation entry links |

### New Fields Added

**`stock.quant`** (from `stock_account/models/stock_quant.py`):
- `value` — `Monetary` (computed, groups: `stock.group_stock_manager`)
- `currency_id` — `Many2one('res.currency')` (related to `company_id.currency_id`)
- `accounting_date` — `Date` — accounting date override for automated valuation
- `cost_method` — `Selection` (computed from `product_categ_id.property_cost_method`)

**`stock.move`** (from `stock_account/models/stock_move.py`):
- `to_refund` — `Boolean` — triggers decrease of delivered/received qty on SO/PO
- `company_currency_id` — `Many2one('res.currency')` (related)
- `value` — `Monetary` — current monetary value of the move
- `value_justification` — `Text` (computed)
- `value_computed_justification` — `Text` (computed)
- `value_manual` — `Monetary` — manual valuation override
- `standard_price` — `Float` (related to `product_id.standard_price`)
- `is_in` — `Boolean` (computed, stored) — incoming valued move
- `is_out` — `Boolean` (computed, stored) — outgoing valued move
- `is_dropship` — `Boolean` (computed, stored)
- `is_valued` — `Boolean` (computed)
- `remaining_qty` — `Float` (computed with search)
- `remaining_value` — `Monetary` (computed)
- `analytic_account_line_ids` — `Many2many('account.analytic.line')`
- `account_move_id` — `Many2one('account.move')` (indexed, `btree_not_null`)

### Methods Overridden

**`stock.move._action_done()`**:
- Calls `_set_value()` on outgoing moves before super, then on all moves after
- Calls `_create_account_move()` to generate journal entries
- Updates `standard_price` on FIFO/average products

**`stock.move._create_account_move()`**:
- Creates `account.move` with lines debiting/crediting valuation accounts
- Posts the move automatically
- Links back via `account_move_id`

**`stock.move._set_value()`**:
- Computes value for incoming and outgoing moves
- For FIFO: uses `_run_fifo()` 
- For standard/average: uses `standard_price`
- Handles lot-level valuation

**`stock.quant._apply_inventory()`**:
- Respects `accounting_date` when set on quant

### Computed Fields

| Field | Model | Store | Dependencies |
|---|---|---|---|
| `value` | `stock.quant` | Yes | `company_id`, `location_id`, `owner_id`, `product_id`, `quantity` |
| `cost_method` | `stock.quant` | No | `product_categ_id.property_cost_method` |
| `is_in` | `stock.move` | Yes | `state`, `move_line_ids` |
| `is_out` | `stock.move` | Yes | `state`, `move_line_ids` |
| `is_dropship` | `stock.move` | Yes | `state` |
| `is_valued` | `stock.move` | No | `is_in`, `is_out` |
| `remaining_qty` | `stock.move` | No | `state`, `move_line_ids` |
| `remaining_value` | `stock.move` | No | `value`, `remaining_qty` |

### ir.rules

`stock_account_security.xml` adds domain restrictions for valuation fields (manager-only).

---

## 2. sale_stock — Sales and Warehouse Management

**Location:** `~/odoo/odoo19/odoo/addons/sale_stock/`

**Manifest Dependencies:** `['sale', 'stock_account']`

**Purpose:** Links sales orders to warehouse operations. Creates `stock.picking` deliveries from confirmed SOs, tracks delivered quantities, and supports shipping policies (partial vs. full delivery).

### Models Extended

| Model | Extension Type | Key Addition |
|---|---|---|
| `sale.order` | `_inherit = 'sale.order'` | Picking fields, warehouse, delivery status |
| `sale.order.line` | `_inherit = 'sale.order.line'` | Stock moves, routes, delivery qty tracking |
| `stock.picking` | `_inherit = 'stock.picking'` | Sale origin link |
| `res.company` | `_inherit = 'res.company'` | Default warehouse settings |

### New Fields Added

**`sale.order`** (from `sale_stock/models/sale_order.py`):
- `incoterm` — `Many2one('account.incoterms')` — International Commercial Terms
- `incoterm_location` — `Char`
- `picking_policy` — `Selection([('direct', ...), ('one', ...)])` — shipping all at once vs. as ready
- `warehouse_id` — `Many2one('stock.warehouse')` (computed, stored, readonly=False, precompute)
- `picking_ids` — `One2many('stock.picking', 'sale_id')` — all transfers for this SO
- `delivery_count` — `Integer` (computed)
- `delivery_status` — `Selection([('pending', ...), ('started', ...), ('partial', ...), ('full', ...)])` (computed, stored)
- `late_availability` — `Boolean` (computed with search)
- `stock_reference_ids` — `Many2many('stock.reference', 'stock_reference_sale_rel', ...)`
- `effective_date` — `Datetime` (computed from first done picking)
- `expected_date` — `Datetime` — promised delivery date
- `json_popover` — `Char` — late picking alert data
- `show_json_popover` — `Boolean`

**`sale.order.line`** (from `sale_stock/models/sale_order_line.py`):
- `qty_delivered_method` — Selection adds `('stock_move', 'Stock Moves')`
- `route_ids` — `Many2many('stock.route')` — delivery routes (MTO, dropship, etc.)
- `move_ids` — `One2many('stock.move', 'sale_line_id')` — reservation moves
- `virtual_available_at_date` — `Float` (computed)
- `scheduled_date` — `Datetime` (computed)
- `forecast_expected_date` — `Datetime` (computed)
- `free_qty_today` — `Float` (computed)
- `qty_available_today` — `Float` (computed)
- `warehouse_id` — `Many2one('stock.warehouse')` (computed, stored)
- `qty_to_deliver` — `Float` (computed)
- `is_mto` — `Boolean` (computed)
- `display_qty_widget` — `Boolean` (computed)

### Methods Overridden

**`sale.order._action_confirm()`**:
- Calls `order_line._action_launch_stock_rule()` to trigger procurement/picking creation

**`sale.order.write()`**:
- Updates picking partner when `partner_shipping_id` changes
- Propagates `commitment_date` to related stock move deadlines
- Logs decrease of ordered quantity when qty is reduced

**`sale.order._compute_expected_date()`**:
- Extends parent computation with warehouse/picking policy

**`sale.order._action_cancel()`**:
- Cancels related pickings when SO is cancelled

**`sale.order._prepare_invoice()`**:
- Adds `invoice_incoterm_id` and `delivery_date` to invoice vals

**`sale.order.line._action_launch_stock_rule()`** (new method):
- Creates `stock.rule` procurements for `consu` (consumable/storable) products
- Creates `stock.reference` records if not present

**`sale.order.line._compute_qty_delivered_method()`**:
- Sets method to `'stock_move'` for `consu` products

**`sale.order.line._prepare_procurement_values()`**:
- Builds values dict including `sale_line_id`, `origin`, `reference_ids`, `route_ids`, `warehouse_id`, `partner_id`, `date_deadline`, etc.

**`sale.order.line.create()`**:
- Triggers `_action_launch_stock_rule()` for lines created in `sale` state

**`sale.order.line.write()`**:
- Re-triggers procurement when `product_uom_qty` changes

### Onchanges Added

**`sale.order._onchange_partner_shipping_id()`**:
- Warns if changing delivery address on active pickings

### ir.rules

`security/sale_stock_security.xml`

---

## 3. purchase_stock — Purchase and Warehouse Management

**Location:** `~/odoo/odoo19/odoo/addons/purchase_stock/`

**Manifest Dependencies:** `['stock_account', 'purchase']`

**Purpose:** Links purchase orders to warehouse receipts. Creates `stock.picking` incoming shipments from confirmed POs, tracks received quantities, and supports reorder rules.

### Models Extended

| Model | Extension Type | Key Addition |
|---|---|---|
| `purchase.order` | `_inherit = 'purchase.order'` | Receipt tracking, picking type |
| `purchase.order.line` | `_inherit = 'purchase.order.line'` | Stock moves, received qty |
| `stock.picking` | `_inherit = 'stock.picking'` | Purchase origin link |
| `stock.rule` | `_inherit = 'stock.rule'` | Buy procurement |
| `product.product` | `_inherit = 'product.product'` | Buy routes |
| `res.partner` | `_inherit = 'res.partner'` | On-time rate |

### New Fields Added

**`purchase.order`** (from `purchase_stock/models/purchase_order.py`):
- `incoterm_location` — `Char`
- `incoming_picking_count` — `Integer` (computed)
- `picking_ids` — `Many2many('stock.picking')` (computed, stored)
- `dest_address_id` — `Many2one('res.partner')` (computed, stored)
- `picking_type_id` — `Many2one('stock.picking.type')` — deliver-to warehouse
- `default_location_dest_id_usage` — `Selection` (related)
- `reference_ids` — `Many2many('stock.reference', ...)`
- `is_shipped` — `Boolean` (computed)
- `effective_date` — `Datetime` (computed from first done receipt)
- `on_time_rate` — `Float` (related from partner)
- `receipt_status` — `Selection([('pending', ...), ('partial', ...), ('full', ...)])` (computed, stored)

**`purchase.order.line`** (from `purchase_stock/models/purchase_order_line.py`):
- `qty_received_method` — Selection adds `('stock_moves', 'Stock Moves')`
- `move_ids` — `One2many('stock.move', 'purchase_line_id')` — reservation moves
- `orderpoint_id` — `Many2one('stock.warehouse.orderpoint')` — reorder rule
- `move_dest_ids` — `Many2many('stock.move', ...)` — downstream moves
- `product_description_variants` — `Char`
- `propagate_cancel` — `Boolean` (default `True`)
- `forecasted_issue` — `Boolean` (computed)
- `is_storable` — `Boolean` (related)
- `location_final_id` — `Many2one('stock.location')`

### Methods Overridden

**`purchase.order.button_approve()`**:
- Calls `_create_picking()` after super

**`purchase.order._create_picking()`**:
- Creates incoming `stock.picking` for `consu` products
- Creates `stock.reference` record if not present
- Confirms and assigns moves

**`purchase.order.write()`**:
- Logs decrease of ordered quantity

**`purchase.order._prepare_picking()`**:
- Returns vals dict for picking creation

**`purchase.order._get_destination_location()`**:
- Returns destination based on dropship or warehouse setting

**`purchase.order.button_cancel()`**:
- Cancels related pickings
- Updates `move_dest_ids` propagation

**`purchase.order._log_decrease_ordered_quantity()`**:
- Renders `purchase_stock.exception_on_po` template for activity logging

**`purchase.order.line._create_or_update_picking()`**:
- Creates or updates picking when PO line changes

**`purchase.order.line._prepare_stock_move_vals()`**:
- Builds stock move vals including `purchase_line_id`, `reference_ids`, `propagate_cancel`, etc.

**`purchase.order.line._get_stock_move_price_unit()`**:
- Returns price unit in company currency for stock valuation

**`purchase.order.line.unlink()`**:
- Cancels related stock moves before unlinking

### Computed Fields

| Field | Model | Store | Dependencies |
|---|---|---|---|
| `receipt_status` | `purchase.order` | Yes | `picking_ids`, `picking_ids.state` |
| `effective_date` | `purchase.order` | Yes | `picking_ids.date_done` |
| `is_shipped` | `purchase.order` | No | `picking_ids`, states |
| `incoming_picking_count` | `purchase.order` | No | `order_line.move_ids.picking_id` |
| `forecasted_issue` | `purchase.order.line` | No | `product_uom_qty`, `date_planned` |

### Post-Init Hook

`_post_init_hook` / `_create_buy_rules` — creates buy procurement rules automatically.

---

## 4. mrp_account — Accounting MRP

**Location:** `~/odoo/odoo19/odoo/addons/mrp_account/`

**Manifest Dependencies:** `['mrp', 'stock_account']`

> **Note:** In Odoo 19, the `mrp_stock` module from earlier versions has been restructured. The bridge between MRP and Stock/Account is now primarily handled through `mrp_account` (MRP + stock_account) and `purchase_mrp` (Purchase + MRP). The `sale_mrp` module handles Sale + MRP.

**Purpose:** Integrates MRP with accounting and inventory valuation. Adds analytic accounting to manufacturing, computes work-in-process (WIP) valuation, and tracks production costs.

### Models Extended

| Model | Extension Type | Key Addition |
|---|---|---|
| `mrp.production` | `_inherit = 'mrp.production'` | WIP journal entries, extra cost |
| `stock.move` | `_inherit = 'stock.move'` | Production valuation hooks |
| `mrp.workorder` | `_inherit = 'mrp.workorder'` | Work center costing |
| `product.product` | `_inherit = 'product.product'` | BoM cost computation |
| `account.move` | `_inherit = 'account.move'` | WIP entry linking |

### New Fields Added

**`mrp.production`** (from `mrp_account/models/mrp_production.py`):
- `extra_cost` — `Float` — additional unit cost added to finished product
- `show_valuation` — `Boolean` (computed) — show valuation button when done
- `wip_move_ids` — `Many2many('account.move', 'wip_move_production_rel')` — WIP journal entries
- `wip_move_count` — `Integer` (computed)

### Methods Overridden

**`mrp.production._cal_price()`**:
- Computes finished move `price_unit` from:
  - Consumed component values (from stock_account)
  - Work center labor costs (`_cal_cost()` from workorders)
  - `extra_cost` field
  - Byproduct cost sharing
- Updates finished move price_unit for valuation

**`mrp.production._post_labour()`**:
- Creates WIP journal entries for labor when production uses real-time valuation
- Posts `account.move` debiting/crediting WIP accounts

**`mrp.production._post_inventory()`**:
- Calls `_post_labour()` after inventory posting

**`mrp.production.action_view_move_wip()`**:
- Returns action to view linked WIP journal entries

**`mrp.production.write()`**:
- Updates analytic line `ref` on name change

**`mrp.production._get_backorder_mo_vals()`**:
- Carries `extra_cost` to backorder

---

## 5. sale_mrp — Sales and MRP Management

**Location:** `~/odoo/odoo19/odoo/addons/sale_mrp/`

**Manifest Dependencies:** `['mrp', 'sale_stock']`

**Purpose:** Enables selling finished goods that trigger manufacturing. When a SO contains a kit/product with a phantom BoM, confirming the SO creates a `mrp.production` order linked back to the sale reference.

### Models Extended

| Model | Extension Type | Key Addition |
|---|---|---|
| `sale.order` | `_inherit = 'sale.order'` | MO count, action to view MOs |
| `sale.order.line` | `_inherit = 'sale.order.line'` | MO procurement values |
| `mrp.production` | `_inherit = 'mrp.production'` | Sale order origin link |
| `stock.move` | `_inherit = 'stock.move'` | Sale line reference |
| `stock.rule` | `_inherit = 'stock.rule'` | Manufacture procurement |
| `mrp.bom` | `_inherit = 'mrp.bom'` | BoM deletion protection |

### New Fields Added

**`sale.order`** (from `sale_mrp/models/sale_order.py`):
- `mrp_production_count` — `Integer` (computed) — count of linked MOs
- `mrp_production_ids` — `Many2many('mrp.production')` (computed) — linked MOs

**`mrp.production`** (from `sale_mrp/models/mrp_production.py`):
- `sale_order_count` — `Integer` (computed)
- `sale_line_id` — `Many2one('sale.order.line')` — origin SO line

### Methods Overridden

**`sale.order._compute_mrp_production_ids()`**:
- Computed from `stock_reference_ids.production_ids`
- Filters to first-level (non-cancelled) MOs

**`sale.order.action_view_mrp_production()`**:
- Returns action to view linked MO form or list

**`mrp.production.action_confirm()`**:
- Propagates `sale_line_id` to finished move when confirmed

**`mrp.production._compute_sale_order_count()`**:
- Counts unique sale orders from `reference_ids.sale_ids` and `sale_line_id.order_id`

**`mrp.production.action_view_sale_orders()`**:
- Returns action to view linked sale orders

**`mrp.bom._ensure_bom_is_free()`** (called by `write`/`unlink`):
- Prevents deactivating/deleting phantom BoMs that have active sale order lines

**`stock.rule._prepare_mo_vals()`**:
- Passes `sale_line_id` from procurement values to MO

**`stock.rule._get_stock_move_values()`**:
- Links kit component moves to the originating `bom_line_id` from the sale order line

---

## 6. account_accountant — Accounting Accountant

**Location:** `~/odoo/odoo19/odoo/addons/account_accountant/`

**Manifest Dependencies:** `['account']`

**Purpose:** Adds advanced accounting features to the base account module: recurring entries, deferred revenue/expense, check printing, bank statement reconciliation improvements, and financial report filtering.

### Models Extended

| Model | Extension Type | Key Addition |
|---|---|---|
| `account.account` | `_inherit = 'account.account'` | Code/name hierarchy |
| `account.chart.template` | `_inherit = 'account.chart.template'` | Bank account setup |
| `account.move` | `_inherit = 'account.move'` | Recurring, deferred |
| `account.move.line` | `_inherit = 'account.move.line'` | Analytic, reconciliation |
| `account.bank.statement` | `_inherit = 'account.bank.statement'` | Balance checks |
| `res.company` | `_inherit = 'res.company'` | Accountant settings |
| `product.product` | `_inherit = 'product.product'` | Deferred revenue product |

### New Fields Added

**`account.move`**:
- Recurring entry scheduling fields
- Deferred revenue/expense schedule links
- Reconciliation improvement fields

**`account.move.line`**:
- `analytic_account_line_ids` — analytic distribution on move lines
- Enhanced reconciliation fields

**`res.company`**:
- Check printing layout settings
- Deferred revenue/expense default accounts
- Accountant-specific configuration

### Methods Overridden

**`account.move._post()`**:
- Handles recurring entry generation
- Processes deferred schedules

**`account.move.line._reconcile_lines()`**:
- Enhanced reconciliation with analytic distribution

**`res.company._check_accounting_settings()`**:
- Validates configuration for accountant features

### Security

`ir.model.access.csv` grants accountant-level permissions for new features.

---

## 7. sale_timesheet — Sales Timesheet

**Location:** `~/odoo/odoo19/odoo/addons/sale_timesheet/`

**Manifest Dependencies:** `['sale_project', 'hr_timesheet']`

**Purpose:** Links timesheet entries to sale order lines, enabling "bill based on timesheet" service products. Tracks billed vs. unbilled hours, creates invoices from timesheets, and manages prepaid/remaining hours.

### Models Extended

| Model | Extension Type | Key Addition |
|---|---|---|
| `sale.order` | `_inherit = 'sale.order'` | Timesheet count, duration |
| `sale.order.line` | `_inherit = 'sale.order.line'` | Timesheet billing |
| `project.project` | `_inherit = 'project.project'` | Pricing type, SOL mapping |
| `project.task` | `_inherit = 'project.task'` | SOL link, remaining hours |
| `account.move` | `_inherit = 'account.move'` | Timesheet invoice linking |
| `account.analytic.line` | `_inherit = 'account.analytic.line'` | SOL link, invoice state |

### New Fields Added

**`sale.order`** (from `sale_timesheet/models/sale_order.py`):
- `timesheet_count` — `Float` (computed)
- `timesheet_encode_uom_id` — `Many2one('uom.uom')` (related)
- `timesheet_total_duration` — `Integer` (computed) — total hours recorded
- `show_hours_recorded_button` — `Boolean` (computed)

**`project.project`** (from `sale_timesheet/models/project_project.py`):
- `pricing_type` — `Selection([('task_rate', ...), ('fixed_rate', ...), ('employee_rate', ...)])` (computed, searchable)
- `sale_line_employee_ids` — `One2many('project.sale.line.employee.map')` — employee rate mappings
- `timesheet_product_id` — `Many2one('product.product')` — default time product (service, invoice_policy='delivery', service_type='timesheet')
- `warning_employee_rate` — `Boolean` (computed, sudo)
- `partner_id` — `Many2one` (computed, stored, readonly=False)
- `allocated_hours` — `Float`
- `billing_type` — `Selection` (computed, stored)

**`project.task`** (from `sale_timesheet/models/project_task.py`):
- `sale_order_id` — `Many2one('sale.order')` (with domain on partner)
- `pricing_type` — `Selection` (related to `project_id.pricing_type`)
- `is_project_map_empty` — `Boolean` (computed)
- `has_multi_sol` — `Boolean` (computed, sudo)
- `timesheet_product_id` — `Many2one` (related)
- `remaining_hours_so` — `Float` (computed with search)
- `remaining_hours_available` — `Boolean` (related)
- `last_sol_of_customer` — `Many2one('sale.order.line')` (computed)

### Methods Overridden

**`sale.order._compute_timesheet_count()`**:
- Counts `account.analytic.line` records linked to the SO via `order_id`

**`sale.order._compute_timesheet_total_duration()`**:
- Sums unit amounts from timesheet lines, converted to company encoding UoM

**`sale.order._create_invoices()`**:
- Calls `moves._link_timesheets_to_invoice()` to attach timesheets to invoice

**`sale.order._compute_field_value()`** (for `invoice_status`):
- Triggers upsell activity when prepaid services exceed threshold

**`project.project._compute_pricing_type()`**:
- `employee_rate` if `sale_line_employee_ids` exists
- `fixed_rate` if `sale_line_id` exists
- `task_rate` otherwise

**`project.project._compute_partner_id()`**:
- Auto-fills partner from `sale_line_id.order_partner_id` for billable projects

**`project.project._compute_sale_line_id()`**:
- Sets default SOL for employee-rate projects based on partner and remaining hours

**`project.project._get_profitability_items_from_aal()`**:
- Adds timesheet revenue sections: `billable_fixed`, `billable_time`, `billable_milestones`, `billable_manual`, `non_billable`

**`project.task._compute_remaining_hours_so()`**:
- Tracks remaining billable hours based on SOL remaining_hours and recorded timesheets

**`project.task._compute_sale_line()`**:
- Auto-fills `sale_line_id` from `last_sol_of_customer` if billable and not set

**`project.task._inverse_partner_id()`**:
- Triggers `_compute_last_sol_of_customer` when partner changes

**`project.task._get_last_sol_of_customer_domain()`**:
- Builds domain for finding customer's last SOL with remaining hours

### Computed Fields

| Field | Model | Store | Dependencies |
|---|---|---|---|
| `timesheet_total_duration` | `sale.order` | No | `order_line.timesheet_ids` |
| `pricing_type` | `project.project` | No | `sale_line_employee_ids`, `sale_line_id` |
| `warning_employee_rate` | `project.project` | No | `task_ids`, `sale_line_employee_ids` |
| `remaining_hours_so` | `project.task` | No | `sale_line_id`, `timesheet_ids` |
| `has_multi_sol` | `project.task` | No | `timesheet_ids`, `so_line` |

---

## 8. project_account — Project Account

**Location:** `~/odoo/odoo19/odoo/addons/project_account/`

**Manifest Dependencies:** `['account', 'project']`

**Purpose:** Computes project profitability by pulling bill amounts from vendor bills, other costs, and other revenues via analytic accounting entries. Adds vendor bill visibility to the project update view.

### Models Extended

| Model | Extension Type | Key Addition |
|---|---|---|
| `project.project` | `_inherit = 'project.project'` | Purchase cost, vendor bill sections |

### New Fields Added

No new fields — purely computed/profitability method overrides.

### Methods Overridden

**`project.project._add_purchase_items()`**:
- Calls `_get_costs_items_from_purchase()` to include vendor bill costs in profitability

**`project.project._get_add_purchase_items_domain()`**:
- Returns domain for `in_invoice`, `in_refund` moves with positive `price_subtotal`

**`project.project._get_costs_items_from_purchase()`**:
- Reads `account.move.line` records linked to project's analytic account
- Computes billed and to-be-billed amounts from vendor bills
- Adds `other_purchase_costs` section to profitability

**`project.project._get_profitability_labels()`**:
- Adds: `other_purchase_costs`, `other_revenues_aal`, `other_costs_aal`

**`project.project._get_profitability_sequence_per_invoice_type()`**:
- Assigns sequence numbers for new sections (e.g., `other_purchase_costs: 11`)

**`project.project.action_profitability_items()`**:
- Opens `account.move` list for `other_purchase_costs`
- Opens analytic line entries for `other_revenues_aal` / `other_costs_aal`

**`project.project._get_items_from_aal()`**:
- Aggregates analytic lines not linked to move lines
- Groups by company currency for revenue/cost totals

**`project.project.action_open_analytic_items()`**:
- Opens analytic entries filtered to project's account

**`project.project._get_domain_aal_with_no_move_line()`**:
- Returns `[('account_id', '=', self.account_id.id), ('move_line_id', '=', False)]`

---

## 9. project_purchase — Project Purchase

**Location:** `~/odoo/odoo19/odoo/addons/project_purchase/`

**Manifest Dependencies:** `['purchase', 'project_account']`

**Purpose:** Makes purchase orders visible within the project interface. Users can create purchase orders from the project, linked to the project's analytic account.

### Models Extended

| Model | Extension Type | Key Addition |
|---|---|---|
| `purchase.order` | `_inherit = 'purchase.order'` | Project link |

### New Fields Added

**`purchase.order`**:
- `project_id` — `Many2one('project.project')` — link to originating project

### Methods Overridden

**`purchase.order._prepare_invoice()`**:
- Sets analytic distribution from project if set

### Auto-Install

`auto_install: True` — automatically installed when both `purchase` and `project_account` are present.

---

## 10. project_stock — Project Stock

**Location:** `~/odoo/odoo19/odoo/addons/project_stock/`

**Manifest Dependencies:** `['stock', 'project']`

**Purpose:** Links stock pickings to projects. Adds a `project_id` field to `stock.picking`, enabling pickings to be associated with and tracked within project context.

### Models Extended

| Model | Extension Type | Key Addition |
|---|---|---|
| `stock.picking` | `_inherit = 'stock.picking'` | `project_id` link |

### New Fields Added

**`stock.picking`** (from `project_stock/models/stock_picking.py`):
- `project_id` — `Many2one('project.project', domain: `[('is_template', '=', False)]`)`

---

## 11. website_sale_stock — Website Sale Stock

**Location:** `~/odoo/odoo19/odoo/addons/website_sale_stock/`

**Manifest Dependencies:** `['website_sale', 'sale_stock', 'stock_delivery']`

**Purpose:** Displays real-time product inventory availability on the eCommerce website. Supports out-of-stock handling, back-in-stock notifications, and cart-level availability checks.

### Models Extended

| Model | Extension Type | Key Addition |
|---|---|---|
| `product.product` | `_inherit = 'product.product'` | Stock notifications |
| `sale.order` | `_inherit = 'sale.order'` | Cart availability |

### New Fields Added

**`product.product`** (from `website_sale_stock/models/product_product.py`):
- `stock_notification_partner_ids` — `Many2many('res.partner', relation: 'stock_notification_product_partner_rel')`

### Methods Overridden

**`sale.order._compute_warehouse_id()`**:
- For website orders, uses `website_id.warehouse_id` instead of user default

**`sale.order._verify_updated_quantity()`**:
- Validates cart quantity against available stock
- Returns warning if quantity exceeds free_qty
- Enforces `allow_out_of_stock_order` setting

**`sale.order._get_free_qty()`**:
- Returns free quantity from warehouse context

**`sale.order._get_shop_warehouse_id()`**:
- Returns `website.warehouse_id` for availability checks

**`sale.order._check_cart_is_ready_to_be_paid()`**:
- Checks all line availability via `_check_availability()`
- Raises ValidationError if any line is unavailable

**`product.product._get_max_quantity()`**:
- Computes max purchasable qty = free_qty minus cart_qty

**`product.product._is_sold_out()`**:
- Returns `True` if product is storable, not allow_out_of_stock, and free_qty <= 0

**`product.product._website_show_quick_add()`**:
- Hides quick-add if product is sold out

**`product.product._send_availability_email()`**:
- Cron-triggered method that sends "back in stock" emails
- Removes partner from notification list after sending

**`product.product._to_markup_data()`**:
- Adds Schema.org `InStock` / `OutOfStock` availability

### ir.filters / Scheduled Actions

- `ir_cron_data.xml` — cron job for `_send_availability_email()`
- Email templates for back-in-stock notifications

---

## 12. pos_loyalty — POS Loyalty and Coupons

**Location:** `~/odoo/odoo19/odoo/addons/pos_loyalty/`

**Manifest Dependencies:** `['loyalty', 'point_of_sale']`

**Purpose:** Enables loyalty programs, coupons, and gift cards within the Point of Sale. Integrates the `loyalty` module's reward/loyalty program engine into the POS frontend.

### Models Extended

| Model | Extension Type | Key Addition |
|---|---|---|
| `loyalty.rule` | `_inherit = 'loyalty.rule'` | POS-specific rules |
| `loyalty.reward` | `_inherit = 'loyalty.reward'` | POS redemption |
| `pos.order` | `_inherit = 'pos.order'` | Loyalty program application |
| `pos.order.line` | `_inherit = 'pos.order.line'` | Loyalty discount lines |

### New Fields Added

**`pos.order`**:
- `loyalty_code` — `Char` — loyalty program code used
- `loyalty_card_id` — `Many2one('loyalty.card')` — loyalty card applied

### Methods Overridden

**`pos.order._process_loyalty()`**:
- Applies loyalty points and rewards at order finalization

### Security

`security/ir.model.access.csv` grants POS-specific permissions.

---

## 13. pos_hr — POS HR

**Location:** `~/odoo/odoo19/odoo/addons/pos_hr/`

**Manifest Dependencies:** `['point_of_sale', 'hr']`

**Purpose:** Links POS sessions to employees (not just users). Allows employees to log into POS via barcode + PIN, tracks per-employee sales, and enables manager oversight at POS level.

### Models Extended

| Model | Extension Type | Key Addition |
|---|---|---|
| `pos.order` | `_inherit = 'pos.order'` | Employee link |
| `pos.payment` | `_inherit = 'pos.payment'` | Employee link |
| `pos.config` | `_inherit = 'pos.config'` | HR settings |
| `res.partner` | `_inherit = 'res.partner'` | PIN field for employees |

### New Fields Added

**`pos.order`**:
- `employee_id` — `Many2one('hr.employee')` — employee who created the order
- `cashier` — `Char` — cashier name (from user)

**`pos.payment`**:
- `employee_id` — `Many2one('hr.employee')` — employee who processed payment

**`res.partner`**:
- `pos_pin` — `Char` — PIN code for POS login (security field)

### Methods Overridden

**`pos.order._export_for_ui()`**:
- Includes employee information in order export

**`pos.order._get_fields_for_order_line()`**:
- Includes employee link in order line export

---

## 14. pos_restaurant — POS Restaurant

**Location:** `~/odoo/odoo19/odoo/addons/pos_restaurant/`

**Manifest Dependencies:** `['point_of_sale']`

**Purpose:** Restaurant-specific POS features: table management, floor plans, split bills, bill printing to kitchen, and order routing to different preparation areas.

### Models Extended

| Model | Extension Type | Key Addition |
|---|---|---|
| `pos.order` | `_inherit = 'pos.order'` | Table, floor, split tracking |
| `pos.order.line` | `_inherit = 'pos.order.line'` | Print status |
| `pos.config` | `_inherit = 'pos.config'` | Restaurant settings |

### New Fields Added

**`pos.order`**:
- `table_id` — `Many2one('restaurant.table')`
- `floor_id` — `Many2one('restaurant.floor')`
- `customer_count` — `Integer` — number of customers
- `state` — Selection adds restaurant-specific states: `to_invoice`, `paid`

### Methods Overridden

**`pos.order._order_fields()`**:
- Includes table/floor data when loading orders

**`pos.order.action_pos_order_paid()`**:
- Handles restaurant-specific payment flow

---

## 15. pos_self_order — POS Self Order (Kiosk)

**Location:** `~/odoo/odoo19/odoo/addons/pos_self_order/`

**Manifest Dependencies:** `['pos_restaurant', 'http_routing', 'link_tracker']`

**Purpose:** Customer-facing self-ordering kiosk. Customers scan a QR code, browse the menu on their smartphone, and place orders that appear instantly in the POS for kitchen/preparation.

### Models Extended

| Model | Extension Type | Key Addition |
|---|---|---|
| `pos.order` | `_inherit = 'pos.order'` | Self-order tracking |
| `pos.session` | `_inherit = 'pos.session'` | Kiosk mode |
| `restaurant.table` | `_inherit = 'restaurant.table'` | QR code generation |

### New Fields Added

**`restaurant.table`**:
- `qr_code_url` — `Char` — URL for self-ordering access

### Methods Overridden

**`pos.session._validate_order()`**:
- Handles orders placed via self-order kiosk

### Auto-Install

`auto_install: ['pos_restaurant']` — automatically installs when dependencies are present.

---

## Cross-Module Extension Pattern Analysis

### Pattern 1: Valuation Bridge (stock_account)

```
stock ──────► stock_account ◄─────── account
                │
           ┌────┴────┐
        sale      purchase
        _stock     _stock
           │            │
        sale_        purchase_
        mrp          _mrp
```

The `stock_account` module is the **hub** for all inventory valuation. Every module that moves stock (sale, purchase, mrp, manufacturing) routes through it for accounting entries. Key extension points:

- `stock.move._action_done()` — central hook where valuation entries are created
- `stock.quant._apply_inventory()` — accounting date override
- `product.product` cost method fields — drive the valuation computation

### Pattern 2: Delivery Chain (sale → stock)

```
sale ───► sale_stock ──► stock_account ──► stock
          │
          └────► sale_mrp ──► mrp ──► mrp_account ──► stock_account
```

The delivery chain flows from SO confirmation through procurement rules to picking creation, with valuation entries generated at picking confirmation.

### Pattern 3: Purchase Chain (purchase → stock)

```
purchase ──► purchase_stock ──► stock_account ──► stock
              │
              └────► purchase_mrp ──► mrp ──► mrp_account ──► stock_account
```

Mirror image of the sale chain but for incoming receipts.

### Pattern 4: Project Profitability Stack

```
project
   │
   ├──► project_account ──► account
   │        │
   │        └──► project_purchase ──► purchase
   │
   ├──► project_stock ──► stock
   │
   └──► sale_timesheet ──► sale_project ──► project
                              │
                              └──► sale
```

Each layer adds a profitability section to the project update view. The stack is additive — later modules extend earlier ones.

---

## Extension Mechanism Summary

| Mechanism | Usage in These Modules |
|---|---|
| `_inherit = 'parent.model'` | All modules — adds fields/methods to existing model |
| `@api.depends` | All computed fields |
| `@api.onchange` | sale_stock, website_sale_stock |
| `@api.constrains` | sale_mrp (BoM deletion) |
| `One2many` reverse | sale_stock (picking_ids on SO), purchase_stock (picking_ids on PO) |
| `Many2one` forward | project_stock (project_id on picking), sale_mrp (sale_line_id on MO) |
| `_action_*` methods | All workflow modules — launch downstream operations |
| `post_init_hook` | stock_account, purchase_stock, sale_timesheet |
| `auto_install: True` | Most modules — automatically installed when dependencies present |

---

## Security Considerations

| Module | Security Addition |
|---|---|
| `stock_account` | Valuation fields restricted to `stock.group_stock_manager` |
| `sale_timesheet` | Timesheet fields restricted to `hr_timesheet.group_hr_timesheet_user` |
| `pos_hr` | PIN field for employee authentication at POS |
| `account_accountant` | Accountant-level permissions via ACL |

---

## See Also

- [Core/BaseModel](../Core/BaseModel.md) — ORM foundation and inheritance patterns
- [Patterns/Inheritance Patterns](Inheritance Patterns.md) — detailed inheritance mechanics (_inherit vs _inherits vs mixin)
- [Modules/Stock](../Modules/Stock.md) — stock.quant, stock.move, stock.picking core models
- [Modules/Sale](../Modules/Sale.md) — sale.order, sale.order.line core models
- [Modules/Purchase](../Modules/Purchase.md) — purchase.order, purchase.order.line core models
- [Modules/MRP](../Modules/MRP.md) — mrp.production, mrp.bom core models
- [Modules/Account](../Modules/Account.md) — account.move, account.move.line core models
- [Modules/Project](../Modules/Project.md) — project.project, project.task core models
