---
Module: project_stock
Version: 18.0.0
Type: addon
Tags: #odoo18 #project_stock #project #stock
---

## Overview

**Module:** `project_stock`
**Depends:** `stock`, `project` (auto_install: True)
**Location:** `~/odoo/odoo18/odoo/addons/project_stock/`
**License:** LGPL-3
**Purpose:** Links stock pickings to projects. Adds `project_id` on `stock.picking` and provides action buttons on the project form to view incoming, outgoing, and all pickings.

---

## Models

### `stock.picking` (models/stock_picking.py, 1–9)

Inherits: `stock.picking`

| Field | Type | Line | Description |
|---|---|---|---|
| `project_id` | Many2one (`project.project`) | 9 | Links a picking to a project. Used to track stock operations in project context. |

### `project.project` (models/project_project.py, 1–46)

Inherits: `project.project`

| Method | Line | Description |
|---|---|---|
| `action_open_deliveries()` | 10 | Calls `_get_picking_action` with `picking_type='outgoing'`. Label: "From WH". |
| `action_open_receipts()` | 14 | Calls `_get_picking_action` with `picking_type='incoming'`. Label: "To WH". |
| `action_open_all_pickings()` | 18 | Calls `_get_picking_action` with no picking type (all pickings). Label: "Stock Moves". |
| `_get_picking_action(action_name, picking_type=None)` | 22 | Builds `ir.actions.act_window` for `stock.picking`. Sets `default_project_id`, `default_partner_id` (for outgoing), and `restricted_picking_type_code` (for view filtering). Help template rendered from `stock.help_message_template`. |

---

## Views

**XML:** `views/stock_picking_views.xml`, `views/project_project_views.xml`

---

## Critical Notes

- `restricted_picking_type_code` context flag is used by the picking tree view to pre-filter by type code.
- Outgoing pickings get `default_partner_id` set to the project's partner.
- v17→v18: No breaking changes.