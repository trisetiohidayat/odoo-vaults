---
Module: project_mrp
Version: 18.0.0
Type: addon
Tags: #odoo18 #project_mrp #project #mrp
---

## Overview

**Module:** `project_mrp`
**Depends:** `mrp`, `project` (auto_install: True)
**Location:** `~/odoo/odoo18/odoo/addons/project_mrp/`
**License:** LGPL-3
**Purpose:** Links manufacturing orders to projects. Propagates project context from BoM to MO, then through stock procurement rules.

---

## Models

### `mrp.bom` (models/mrp_bom.py, 1–9)

Inherits: `mrp.bom`

| Field | Type | Line | Description |
|---|---|---|---|
| `project_id` | Many2one (`project.project`) | 9 | Links a BoM to a project. Used to auto-fill `project_id` on MOs created from this BoM. |

### `mrp.production` (models/mrp_production.py, 1–21)

Inherits: `mrp.production`

| Field | Type | Line | Description |
|---|---|---|---|
| `project_id` | Many2one (`project.project`) | 9 | Computed from `bom_id.project_id`; writable unless `from_project_action` context is set. |

| Method | Decorator | Line | Description |
|---|---|---|---|
| `_compute_project_id()` | `@api.depends('bom_id')` | 11 | Sets `project_id` from `bom_id.project_id` unless `from_project_action` context is set (prevents overwrite when opening from project). |
| `action_generate_bom()` | action | 17 | Forwards `default_project_id` from the MO into the BOM creation wizard context. |

### `project.project` (models/project_project.py, 1–87)

Inherits: `project.project`

| Field | Type | Groups | Line | Description |
|---|---|---|---|---|
| `bom_count` | Integer (computed) | `mrp.group_mrp_user` | 9 | Count of MTP BOMs linked to this project. |
| `production_count` | Integer (computed) | `mrp.group_mrp_user` | 10 | Count of MO productions linked to this project. |

| Method | Line | Description |
|---|---|---|
| `_compute_bom_count()` | 12 | `_read_group` on `mrp.bom` grouped by `project_id`. |
| `_compute_production_count()` | 22 | `_read_group` on `mrp.production` grouped by `project_id`. |
| `action_view_mrp_bom()` | 32 | Opens `mrp.bom` list/kanban/form filtered to this project. Sets `default_project_id` in context. Single result → form view. |
| `action_view_mrp_production()` | 53 | Opens `mrp.production` action, sets `default_project_id` and `from_project_action` context. Single result → form view. |
| `_get_stat_buttons()` | 64 | Adds two stat buttons for MRP users: "Bills of Materials" (seq 35, icon flask) and "Manufacturing Orders" (seq 46, icon wrench). |

### `stock.rule` (models/stock.py, 6–13)

Inherits: `stock.rule`

| Method | Line | Description |
|---|---|---|
| `_prepare_mo_vals()` | 9 | Adds `project_id` from procurement `values` into MO vals. Propagates project into manufactured products. |

### `stock.move` (models/stock.py, 16–23)

Inherits: `stock.move`

| Method | Line | Description |
|---|---|---|
| `_prepare_procurement_values()` | 19 | Propagates `project_id` from MO's `group_id` into procurement values — only when the group has exactly one MO (avoids ambiguity). |

---

## Views

**XML:** `views/mrp_bom_views.xml`, `views/mrp_production_views.xml`, `views/project_project_views.xml`

---

## Profitability Buttons (Stat Buttons)
| Button | Sequence | Icon | Groups | Action |
|---|---|---|---|---|
| Bills of Materials | 35 | flask | `mrp.group_mrp_user` | `action_view_mrp_bom` |
| Manufacturing Orders | 46 | wrench | `mrp.group_mrp_user` | `action_view_mrp_production` |

---

## Critical Notes

- **Project propagation path:** BoM (`project_id`) → MO (`project_id`) → procurement values → stock moves.
- `_prepare_procurement_values` sets `project_id` only when the stock move's group has exactly one MO.
- `from_project_action` context flag prevents `_compute_project_id` from overwriting a manually-set project when navigating from the project.
- v17→v18: No breaking changes.