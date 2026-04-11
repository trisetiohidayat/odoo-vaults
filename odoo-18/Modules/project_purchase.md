---
Module: project_purchase
Version: 18.0.0
Type: addon
Tags: #odoo18 #project_purchase #project #purchase
---

## Overview

**Module:** `project_purchase`
**Depends:** `purchase`, `project_account` (auto_install: True)
**Location:** `~/odoo/odoo18/odoo/addons/project_purchase/`
**License:** LGPL-3
**Purpose:** Tracks purchase orders and PO lines linked to projects (via `project_id` or analytic distribution). Integrates purchase costs into project profitability report with both billed and to-bill amounts.

---

## Models

### `purchase.order` (models/purchase_order.py, 1–9)

Inherits: `purchase.order`

| Field | Type | Line | Description |
|---|---|---|---|
| `project_id` | Many2one (`project.project`) | 9 | Links a PO directly to a project. Used to filter POs in project context. |

### `purchase.order.line` (models/purchase_order_line.py, 1–37)

Inherits: `purchase.order.line`

| Method | Decorator | Line | Description |
|---|---|---|---|
| `_compute_analytic_distribution()` | `@api.depends` | 9 | Adds project's analytic accounts (not already present as root plan) to the line's distribution. If no distribution set, uses `project._get_analytic_distribution()` directly. Context `project_id` takes precedence over `order_id.project_id`. |
| `create(vals_list)` | `@api.model_create_multi` | 32 | Calls `_recompute_recordset` on created lines to ensure `analytic_distribution` is computed. |

### `project.project` (models/project_project.py, 1–189)

Inherits: `project.project`

#### Fields

| Field | Type | Groups | Line | Description |
|---|---|---|---|---|
| `purchase_orders_count` | Integer (computed) | `purchase.group_purchase_user` | 12 | Count of POs linked directly or via analytic distribution. Two-pass: direct `project_id` + analytic distribution via `purchase.order.line`. |

#### Methods

`_compute_purchase_orders_count()` (line 14)
: Two-pass count. Pass 1: groups `purchase.order` by `project_id` where `order_line != False`. Pass 2: for projects without analytic account or to fill gaps, groups `purchase.order.line` by `analytic_distribution`. Combines both counts.

`action_open_project_purchase_orders()` (line 48)
: Opens `purchase.order` list via `purchase.order.line` search on `analytic_distribution` OR `order_id.project_id`. Sets `default_project_id` in context. Single result → form view.

`action_profitability_items(section_name, domain=None, res_id=False)` (line 77)
: Handles `section_name == 'purchase_order'`: opens `purchase.order.line` list (read-only) filtered by domain. Single res_id → form view. Delegates to super for other sections.

`_get_stat_buttons()` (line 106)
: Adds "Purchase Orders" stat button (seq 36, icon credit-card) for `purchase.group_purchase_user`.

`_get_profitability_aal_domain()` (line 121)
: Excludes `move_line_id.purchase_line_id` from AAL domain — prevents double-counting PO invoice lines with analytic account entries.

`_add_purchase_items(profitability_items, with_action=True)` (line 127)
: Returns `False`. Disables the default `project_account` purchase section, replaced by this module's custom `_get_profitability_items` implementation.

`_get_profitability_labels()` (line 130)
: Adds `'purchase_order': self.env._('Purchase Orders')` to profitability labels.

`_get_profitability_sequence_per_invoice_type()` (line 135)
: Assigns sequence `10` to `purchase_order` section.

`_get_profitability_items(with_action=True)` (line 140)
: Reads `account.move.line` with `purchase_line_id` and `analytic_distribution` matching project AA. Computes `amount_invoiced` (posted) and `amount_to_invoice` (draft). Uses analytic contribution weighting (handles split AA distributions). Adds PO line actions for users with purchase or invoice group access. Also calls `_get_costs_items_from_purchase` for other vendor bill lines not tied to PO lines.

#### Profitability — Purchase Orders Section
| Property | Value |
|---|---|
| Section ID | `purchase_order` |
| Sequence | `10` |
| Type | `costs` (billed + to_bill) |
| Access | `purchase.group_purchase_user` OR `account.group_account_invoice` OR `account.group_account_readonly` |

---

## Controllers

### `controllers/catalog.py` — `ProjectPurchaseCatalogController` (1–23)

Extends: `ProductCatalogController`

| Method | Line | Description |
|---|---|---|
| `product_catalog_update_order_line_info()` | 9 | Forwards `project_id` from request kwargs into Odoo's context before calling super. Ensures PO line analytic distribution uses the project's AA when editing from project catalog. |

---

## Views

**XML:** `views/project_project.xml`, `views/purchase_order.xml`

**Static:** `project_purchase/static/src/product_catalog/kanban_record.js` — frontend JS for product catalog within project context.

---

## Data

`data/project_purchase_demo.xml` — demo PO linked to project.

---

## Critical Notes

- PO profitability = invoice lines (billed) + draft invoice lines (to_bill), weighted by analytic contribution percentage per line.
- `_add_purchase_items` returns `False` to suppress the default `project_account` implementation.
- `_get_profitability_aal_domain` excludes PO-linked move lines from AAL to prevent double-counting.
- `project_id` on PO and analytic-distribution on PO lines are both tracked for count and profitability.
- v17→v18: No breaking changes.