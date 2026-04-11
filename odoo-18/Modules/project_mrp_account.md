---
Module: project_mrp_account
Version: 18.0.0
Type: addon
Tags: #odoo18 #project_mrp_account #project #mrp #analytic
---

## Overview

**Module:** `project_mrp_account`
**Depends:** `mrp_account`, `project_mrp` (auto_install: True)
**Location:** `~/odoo/odoo18/odoo/addons/project_mrp_account/`
**License:** LGPL-3
**Purpose:** Generates analytic account entries for manufacturing operations and surfaces MO costs in the project profitability panel. Validates mandatory analytic plans on MO confirmation.

---

## Models

### `mrp.production` (models/mrp_production.py, 1–34)

Inherits: `mrp.production`

| Field | Type | Line | Description |
|---|---|---|---|
| `has_analytic_account` | Boolean (computed) | 9 | `True` if the linked project has any analytic accounts. |

| Method | Decorator | Line | Description |
|---|---|---|---|
| `_compute_has_analytic_account()` | `@api.depends('project_id')` | 11 | Checks `project._get_analytic_accounts()` for each MO's project; returns `False` for draft/no-project MOs. |
| `action_view_analytic_accounts()` | action | 17 | Opens `account.analytic.account` list filtered to the project's analytic accounts. |
| `write(vals)` | override | 27 | If `project_id` changes on a non-draft MO: calls `_account_analytic_entry_move()` on components and `_create_or_update_analytic_entry()` on workorders to re-link analytic entries. |

### `mrp.workorder` (models/mrp_workorder.py, 1–15)

Inherits: `mrp.workorder`

| Method | Line | Description |
|---|---|---|
| `_create_or_update_analytic_entry_for_record(value, hours)` | 9 | Extends parent method. After the workorder's own analytic lines are created, creates additional lines under the **MO's project** analytic distribution for the same `value` and `hours`. Runs as sudo to create AAL records. |

### `project.project` (models/project_project.py, 1–56)

Inherits: `project.project`

| Method | Line | Description |
|---|---|---|
| `_get_profitability_labels()` | 14 | Adds `'manufacturing_order': self.env._('Manufacturing Orders')` to profitability section labels. |
| `_get_profitability_sequence_per_invoice_type()` | 19 | Assigns sequence `12` to the `manufacturing_order` section. |
| `_get_profitability_aal_domain()` | 24 | Excludes AAL lines with `category == 'manufacturing_order'` from the base AAL domain (they are tracked separately). |
| `_get_profitability_items(with_action=True)` | 30 | Reads `account.analytic.line` grouped by currency where `auto_account_id in self.account_id.ids` and `category == 'manufacturing_order'`. Converts to project currency. Adds `action: {name: 'action_view_mrp_production', type: 'object'}` if user has `mrp.group_mrp_user` and project singleton. Merges into `costs` section. |

#### Profitability — Manufacturing Orders Section
| Property | Value |
|---|---|
| Section ID | `manufacturing_order` |
| Sequence | `12` |
| Type | `costs` only |
| Source | `account.analytic.line` (auto, category=`manufacturing_order`) |
| Access | `mrp.group_mrp_user` for action link |

### `stock.move` (models/stock_move.py, 1–35)

Inherits: `stock.move`

| Method | Line | Description |
|---|---|---|
| `_get_analytic_distribution()` | 11 | Returns `raw_material_production_id.project_id._get_analytic_distribution()` if linked to an MO; falls back to `super()`. |
| `_prepare_analytic_line_values()` | 15 | Sets `category = 'manufacturing_order'` on analytic lines for MO-linked stock moves (distinguishes from `picking_entry`). |
| `_prepare_analytic_lines()` | 21 | Validates mandatory analytic plans on the MO's project before generating AALs. Raises `ValidationError` listing missing plan names. Runs before every analytic line generation on MO stock moves. |

**ValidationError thrown by `_prepare_analytic_lines`:** `"'<plan_names>' analytic plan(s) required on the project '<project_name>' linked to the manufacturing order."`

### `stock.rule` (models/stock_rule.py, 1–14)

Inherits: `stock.rule`

| Method | Line | Description |
|---|---|---|
| `_prepare_mo_vals()` | 9 | Propagates `project_id` from procurement `values` into MO creation vals. Mirrors logic from `project_mrp` but ensures it persists through accountancy-aware procurement. |

---

## Data

`data/project_mrp_account_demo.xml` — demo records linking analytic distributions to project-MO structures.

---

## Critical Notes

- Analytic lines for manufacturing carry `category='manufacturing_order'` (distinct from `picking_entry` used for standard stock moves).
- `stock_move._prepare_analytic_lines` raises `ValidationError` at MO stock move validation time if the project lacks mandatory plans.
- `mrp_production.write` re-posts analytic entries when `project_id` changes on a confirmed MO.
- v17→v18: No breaking changes.