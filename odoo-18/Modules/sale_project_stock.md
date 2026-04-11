# sale_project_stock — Sale Project Stock

**Tags:** #odoo #odoo18 #sale #project #stock #delivery #reinvoice
**Odoo Version:** 18.0
**Module Category:** Sale + Project + Stock Integration
**Documentation Level:** L4
**Status:** Complete

---

## Module Overview

`sale_project_stock` connects sale orders, projects, and stock deliveries for service companies that ship products linked to project tasks. It enables reinvoicing stock moves from delivery pickings as sale order lines, and provides project-level access to stock move actions and picking information.

**Technical Name:** `sale_project_stock`
**Python Path:** `~/odoo/odoo18/odoo/addons/sale_project_stock/`
**Depends:** `sale_project`, `sale_stock`
**Inherits From:** `project.project`, `sale.order.line`, `stock.picking`, `stock.move`

---

## Python Model Files

| File | Model(s) Extended | Key Purpose |
|------|------------------|-------------|
| `models/project_project.py` | `project.project` | Picking action for project |
| `models/sale_order_line.py` | `sale.order.line` | Stock action per line |
| `models/stock_picking.py` | `stock.picking` | Reinvoice on validate |
| `models/stock_move.py` | `stock.move` | Invoice price, SO line vals, project in move vals |

---

## Models Reference

### `project.project` (models/project_project.py)

#### Methods

| Method | Behavior |
|--------|----------|
| `_get_picking_action()` | Override: returns stock picking action for project |

---

### `sale.order.line` (models/sale_order_line.py)

#### Methods

| Method | Behavior |
|--------|----------|
| `_get_action_per_item()` | Override: shows stock move action for non-service SOLs (not just delivery-type SOLs) |

---

### `stock.picking` (models/stock_picking.py)

#### Methods

| Method | Behavior |
|--------|----------|
| `button_validate()` | Overrides: on validate, checks for reinvoiceable moves and creates SOLs if SO state/lock allows |

---

### `stock.move` (models/stock_move.py)

#### Methods

| Method | Behavior |
|--------|----------|
| `_sale_get_invoice_price()` | Returns price from expense_policy if product is saleable |
| `_sale_prepare_sale_line_values()` | Prepares SOL vals from move (product, qty, uom, analytic distribution) |
| `_get_new_picking_values()` | Adds `project_id` from `sale_line_id.order_id.project_id` to picking vals |
| `_assign_picking_values()` | Assigns picking to project from SO's project |
| `_prepare_procurement_values()` | Adds `project_id` to procurement values |

---

## Security File

No security file.

---

## Data Files

No data file.

---

## Critical Behaviors

1. **Reinvoice on Validate**: `stock.picking.button_validate()` checks each move for `sale_line_id.is_service=False` (storable product on service SO) and `sale_line_id.order_id.state='sale'` and creates SOLs for the delivered quantity if not already on the SO.

2. **Project Linkage**: Stock pickings are linked to the project from the SO's `project_id` via `_get_new_picking_values()` and `_assign_picking_values()`.

3. **Stock Move Price**: `_sale_get_invoice_price()` checks `product_id.expense_policy` for the price — this is used in `sale_project` to determine what to charge for the delivered product.

4. **Action Per Item**: `_get_action_per_item()` on SOL returns the stock move action for non-service lines, enabling users to navigate from the SO to the actual delivery picking.

---

## v17→v18 Changes

- `_get_action_per_item()` now shows stock move action for all non-service SOLs (not just delivery-type)
- `_prepare_procurement_values()` now passes `project_id` for stock rule procurement

---

## Notes

- This module targets service companies that sell support contracts with physical product components (e.g., equipment, software licenses with USB keys)
- The reinvoice check in `button_validate()` prevents creating duplicate SOLs for already-invoiced products
- Project-level stock visibility enables project managers to track deliveries for their contracts
