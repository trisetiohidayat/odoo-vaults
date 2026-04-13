---
type: module
module: project_mrp
tags: [odoo, odoo19, project, mrp, manufacturing, bom, bridge, auto-install]
created: 2026-04-06
updated: 2026-04-11
---

# Project MRP (`project_mrp`)

## Overview

| Property | Value |
|----------|-------|
| **Technical Name** | `project_mrp` |
| **Version** | 19.0.1.0.0 (Odoo CE) |
| **Category** | Services/Project |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Auto-install** | `True` |
| **Hard Depends** | `mrp`, `project` |

## Purpose

Bridges the MRP (Manufacturing) and Project modules. Enables Bills of Materials (BoMs) and Manufacturing Orders (MOs) to be linked to a `project.project`, with full visibility of manufacturing activity in the project dashboard, task list, and update pane.

This is a thin connector module — no independent business logic. It layers project awareness onto existing MRP records by adding fields, computed counters, and action buttons.

## Dependency Chain

```
project_mrp
├── mrp          (manufacturing orders, BoM)
└── project      (projects, tasks)

Dependent modules (auto-install):
  project_mrp_sale               ← project_mrp + sale_mrp + sale_project
  project_mrp_account            ← project_mrp + mrp_account
  project_mrp_stock_landed_costs ← project_mrp_account + mrp_landed_costs
```

`project_mrp_sale` (auto-install, no own models) ties manufacturing orders to sale orders through projects, enabling Make-to-Order flows via project-linked MOs. `project_mrp_account` bridges MO costing (analytic entries from `mrp_account`) into the project profitability panel. `project_mrp_stock_landed_costs` extends that chain to include landed cost splits.

---

## Model Extensions

### `mrp.bom` — Inherits `mrp.bom`

**File:** `models/mrp_bom.py`

#### Fields

| Field | Type | Storage | Groups | Description |
|-------|------|---------|--------|-------------|
| `project_id` | `Many2one` → `project.project` | Stored (direct column) | `project.group_project_user` | Links the Bill of Materials to a project. Domain excludes template projects (`is_template = False`). Editable regardless of BoM state. |

**Notes:**
- `project_id` on `mrp.bom` is the primary anchor for the MRP-Project integration. When an MO is created from a BoM, the MO's `project_id` is derived from here — not from origin, picking, or sale order.
- Unlike `mrp.production.project_id`, this field is a plain editable column: no compute, no constraint, no `on_delete`. Direct write only.
- There are no overrides on `mrp.bom` methods in this module. BoM creation and update flows are entirely from base `mrp`.

**View placement (XML):**
- `mrp_bom_form_view_inherited_project_mrp` extends `mrp.mrp_bom_form_view`: places `project_id` after `picking_type_id`, visible only to `project.group_project_user`.

**L4: `project_id` as the BoM-Project anchor:**
The BoM is the stable reference — it rarely changes. By storing `project_id` directly on the BoM, Odoo ensures that every MO produced from that BoM can be traced back to the same project without requiring the user to set it manually each time. The MO's computed `project_id` is a derived value; the BoM's `project_id` is the source of truth.

---

### `mrp.production` — Inherits `mrp.production`

**File:** `models/mrp_production.py`

#### Fields

| Field | Type | Compute | Store | Groups | Description |
|-------|------|---------|-------|--------|-------------|
| `project_id` | `Many2one` → `project.project` | `_compute_project_id` | `store=True` | — | Project linked to this MO. Derived from `bom_id.project_id` when not manually overwritten. Domain excludes templates. |

#### `project_id` Compute Logic

```python
@api.depends('bom_id')
def _compute_project_id(self):
    if not self.env.context.get('from_project_action'):
        for production in self:
            production.project_id = production.bom_id.project_id
```

**Key behavior:**

| Aspect | Behavior |
|--------|----------|
| Trigger | Fires only when `bom_id` changes on an existing MO record |
| `from_project_action` context | When `True`, compute is skipped entirely — allows project→MO navigation without overwriting manually set values |
| `store=True` | Computed value is written to the DB, enabling efficient domain filtering and `_read_group` aggregation |
| `readonly=False` | User can write directly to `project_id`, disconnecting it from the BoM's project |
| Domain | `[('is_template', '=', False)]` — project templates excluded |

**L4: Interaction between `_prepare_mo_vals` and `_compute_project_id`:**

There are two independent mechanisms setting `project_id` on an MO:

1. **`stock.rule._prepare_mo_vals`** (in `models/stock.py`): writes `values['project_id']` into the MO `create()` vals dict during procurement-based MO creation. This is a direct write — it sets the value before the ORM creates the record.

2. **`_compute_project_id`** (in `models/mrp_production.py`): fires when `bom_id` changes. Reads `bom_id.project_id` and overwrites `project_id`.

When an MO is created via procurement with both a BoM and a project in `values`:
```
stock.rule._prepare_mo_vals():
  res = super()._prepare_mo_vals(...)   # mrp sets res['bom_id'] and res['project_id'] = bom.project_id
  if values.get('project_id'):
      res['project_id'] = values['project_id']   # project_mrp OVERWRITES with procurement's project_id

mrp.production.create(res):
  → mrp.production.project_id = values['project_id']   (direct write, not compute)
  → bom_id is set → compute fires → bom_id.project_id overwrites (if BoM has no project, sets False)
```

The end result depends on whether the BoM has a `project_id` set. This is the key design tension: when the BoM has no project, the compute sets `project_id = False` after procurement already set it to the SO's project. **This is a known limitation** — the BoM's project takes precedence over the procurement's project if the BoM has no project set. The workaround is to ensure the BoM also has `project_id` set when used in SO→MO flows.

#### Methods

**`action_generate_bom()`**

```python
def action_generate_bom(self):
    action = super().action_generate_bom()
    action['context']['default_project_id'] = self.project_id.id
    return action
```

Creates a new BoM from the MO form. Passes the MO's current `project_id` into the BoM creation context as `default_project_id`, pre-populating the field in the new BoM form. This creates a forward-link: MO → new BoM → MO's project.

**`action_open_project()`**

```python
def action_open_project(self):
    self.ensure_one()
    return {
        'type': 'ir.actions.act_window',
        'res_model': 'project.project',
        'view_mode': 'form',
        'res_id': self.project_id.id,
    }
```

Opens the linked project in form view. The button in the XML view is guarded with `invisible="not project_id"` — no explicit null-check needed in the method itself.

**View placements (XML):**

- `mrp_production_form_view_inherit_project_mrp`:
  - Inserts "Project" button into the button box (icon: `fa-puzzle-piece`, visible only when `project_id` is set, `project.group_project_user` required)
  - Injects `default_project_id` into the `bom_id` context so the BoM selector pre-sets the project
  - Places `project_id` on the "Miscellaneous" tab (after `is_delayed`)
- `view_production_tree_view_inherit_project_mrp`: adds `project_id` column to the MO list view as `optional="hide"`, `project.group_project_user`.

---

### `project.project` — Inherits `project.project`

**File:** `models/project_project.py`

#### Fields

| Field | Type | Groups | Stored | Description |
|-------|------|--------|--------|-------------|
| `bom_count` | `Integer` | `mrp.group_mrp_user` | No | Count of `mrp.bom` records linked to this project via `project_id`. |
| `production_count` | `Integer` | `mrp.group_mrp_user` | No | Count of `mrp.production` records linked to this project via `project_id`. |

#### Counter Compute Methods

Both use `_read_group` (SQL aggregation) rather than `search_count` for O(1) vs O(n) performance:

```python
def _compute_bom_count(self):
    bom_count_per_project = dict(
        self.env['mrp.bom']._read_group(
            [('project_id', 'in', self.ids)],
            ['project_id'], ['__count']
        )
    )
    for project in self:
        project.bom_count = bom_count_per_project.get(project)

def _compute_production_count(self):
    production_count_per_project = dict(
        self.env['mrp.production']._read_group(
            [('project_id', 'in', self.ids)],
            ['project_id'], ['__count']
        )
    )
    for project in self:
        project.production_count = production_count_per_project.get(project)
```

**L4: `_read_group` vs `search_count`:**
- `_read_group` executes a single `SELECT project_id, COUNT(*) FROM mrp_bom WHERE project_id IN (...) GROUP BY project_id` SQL query.
- `search_count` executes one `SELECT COUNT(*) FROM mrp_bom WHERE project_id = ?` per project — O(n) queries.
- For a project list view with 50 projects and 100 MOs each, the difference is 1 query vs 50 queries.
- `groups='mrp.group_mrp_user'` means non-MRP users see `0` (not an access error) — allows stat button to use `show=self.bom_count > 0` without additional access checks.

#### Stat Button Methods

**`action_view_mrp_bom()`**
- Returns `ir.actions.act_window` for `mrp.bom` filtered to `project_id = self.id`.
- `context: {'default_project_id': self.id}` pre-fills project on new BoM creation.
- Single-BoM redirect: if exactly one BoM exists and not called from an embedded action, opens that BoM's form directly.
- Help text for empty state.

**`action_view_mrp_production()`**
- Calls `self.env['ir.actions.actions']._for_xml_id('mrp.mrp_production_action')` to load the standard MO action, then overrides `domain` and `context`.
- `context: {'default_project_id': self.id, 'from_project_action': True}` — `from_project_action` suppresses `project_id` compute in the MO form.
- Same single-record redirect behavior.

#### `_get_stat_buttons()` Override

```python
def _get_stat_buttons(self):
    buttons = super()._get_stat_buttons()
    if self.env.user.has_group('mrp.group_mrp_user'):
        buttons.extend([{
            'icon': 'flask',
            'text': self.env._('Bills of Materials'),
            'number': self.bom_count,
            'action_type': 'object',
            'action': 'action_view_mrp_bom',
            'show': self.bom_count > 0,
            'sequence': 35,
        },
        {
            'icon': 'wrench',
            'text': self.env._('Manufacturing Orders'),
            'number': self.production_count,
            'action_type': 'object',
            'action': 'action_view_mrp_production',
            'show': self.production_count > 0,
            'sequence': 46,
        }])
    return buttons
```

| Detail | Value |
|--------|-------|
| `sequence: 35` | Places "Bills of Materials" before standard task stat buttons |
| `sequence: 46` | Places "Manufacturing Orders" after task-related buttons |
| `show` condition | `count > 0` — buttons hidden when no linked records |
| `icon: 'flask'` | Visual cue (BoM), `icon: 'wrench'` (MO) |

**L4: Stat button placement vs embedded actions:**
`_get_stat_buttons()` populates the project dashboard smart buttons (the dashboard cards). The `ir.embedded.actions` XML records (see below) populate the project kanban embedded view tabs. Both coexist — the smart buttons appear on the dashboard, the embedded actions appear in the kanban card tabs. They call the same `action_view_mrp_*` methods with different contexts.

#### Embedded Actions (XML)

Four `ir.embedded.actions` records in `project_project_views.xml`:

| XML ID | Parent Action | Sequence | Context Flag |
|--------|--------------|----------|-------------|
| `project_embedded_action_bills_of_materials` | `project.act_project_project_2_project_task_all` | 95 | `from_embedded_action: true` |
| `project_embedded_action_bills_of_materials_dashboard` | `project.project_update_all_action` | 95 | `from_embedded_action: true` |
| `project_embedded_action_manufacturing_orders` | `project.act_project_project_2_project_task_all` | 100 | `from_embedded_action: true` |
| `project_embedded_action_manufacturing_orders_dashboard` | `project.project_update_all_action` | 100 | `from_embedded_action: true` |

- All gated by `mrp.group_mrp_user`.
- All carry `from_embedded_action: true` in context — this suppresses the single-record redirect in `action_view_mrp_*()` (the `if len(boms) == 1` check sees this context and skips the redirect), always showing a list.

---

### `stock.rule` — Inherits `stock.rule`

**File:** `models/stock.py`

#### `_prepare_mo_vals()` Override

```python
def _prepare_mo_vals(self, product_id, product_qty, product_uom, location_id, name, origin, company_id, values, bom):
    res = super()._prepare_mo_vals(product_id, product_qty, product_uom, location_id, name, origin, company_id, values, bom)
    if values.get('project_id'):
        res['project_id'] = values.get('project_id')
    return res
```

**When called:** Invoked by the stock procurement engine when it needs to create an MO to fulfill a procurement order. Builds the initial values dict passed to `mrp.production.create()`.

**Propagation path:**
```
sale.order.line._prepare_procurement_values()
  → sets values['project_id'] = order_id.project_id (from sale_project)

stock.rule._prepare_mo_vals():
  → super() returns res with res['project_id'] = bom.project_id (if BoM has project)
  → if values.get('project_id'): res['project_id'] = values['project_id']  ← project_mrp override
  → returns res with project_id from procurement values

mrp.production.create(res):
  → writes project_id directly (not via compute, since compute only fires on bom_id change)
  → if bom_id set: compute _compute_project_id fires → bom_id.project_id may overwrite
```

**L4: Two write paths for `project_id` on MO creation:**

1. **Direct write** (not compute): `stock.rule._prepare_mo_vals` sets `res['project_id']` → `create()` writes it → `bom_id` may not yet be set → no compute.
2. **Compute overwrite** (when `bom_id` changes): After `create()`, if `bom_id` is assigned (from the BoM passed to `_prepare_mo_vals`), `_compute_project_id` fires and reads `bom_id.project_id`, potentially overwriting the procurement-derived value.

The `@api.depends('bom_id')` means the compute only fires when `bom_id` is **assigned** (or **changed** on an existing record). If the Mo's `bom_id` is set in the `create()` vals dict (as `super()._prepare_mo_vals` does when a BoM is passed), the compute fires after creation and may overwrite `project_id`.

**Edge case — BoM has no project:** If the BoM used in procurement has no `project_id` set, `super()._prepare_mo_vals()` from `mrp` sets `res['project_id'] = False` (via `bom.project_id`), and `project_mrp`'s override then writes `values['project_id']` (from the SO). After `create()`, the compute fires and overwrites with `False` (since `bom_id.project_id` is `False`). **This means the SO's project does not propagate if the BoM has no project set** — a key limitation of this module.

---

### `stock.move` — Inherits `stock.move`

**File:** `models/stock.py`

#### `_prepare_procurement_values()` Override

```python
def _prepare_procurement_values(self):
    res = super()._prepare_procurement_values()
    if res.get('group_id') and len(res['group_id'].mrp_production_ids) == 1:
        res['project_id'] = res['group_id'].mrp_production_ids.project_id.id
    return res
```

**When called:** During component consumption planning. Each component stock move calls this to build the `values` dict for procurement recommendations that may trigger sub-assembly MOs via `stock.rule`.

**Logic:** If the procurement group contains exactly one MO, that MO's `project_id` is propagated into the component procurement values. The `len(...) == 1` guard prevents ambiguous propagation when multiple MOs share the same group.

**L4: Sub-assembly project propagation chain:**

```
Top-level MO created with project_id = P
  → Component stock.move._prepare_procurement_values()
      → group.mrp_production_ids = [top_MO]
      → len == 1 → values['project_id'] = P
  → Component procurement.rule._prepare_mo_vals()
      → values.get('project_id') = P
      → res['project_id'] = P
  → Sub-assembly MO created with project_id = P
      → bom_id of sub-assembly may be set → compute fires
      → sub_MO.project_id = bom.project_id or P (depends on BoM)
```

This creates a cascade: top-level MO's project propagates to all sub-assembly MOs in the same production group. This is intentional — all production for a project should be tracked under the same project.

**Interaction with `_prepare_mo_vals`:** Values enriched by `_prepare_procurement_values` flow into `stock.rule._prepare_mo_vals`. The `project_mrp` override there copies `project_id` from `values` into the new sub-assembly MO. Combined, these two overrides create the full sub-assembly propagation chain.

---

## Security Model

**No dedicated ACL file** — no `security/ir.model.access.csv` or `ir.rule` records in this module.

| Object | Access Control |
|--------|----------------|
| `mrp.bom` / `mrp.production` | Standard `mrp.group_mrp_user` and `mrp.group_mrp_manager` ACL |
| `project.project` | Standard `project.group_project_user` and `project.group_project_manager` ACL |
| `bom_count` / `production_count` fields | `groups='mrp.group_mrp_user'` — field is invisible to non-MRP users; `0` returned (not access error) |
| `project_id` on MO/BoM forms | `groups='project.group_project_user'` — field invisible to non-project users |
| Stat buttons | Hidden when `bom_count = 0` / `production_count = 0` OR user lacks `mrp.group_mrp_user` |

**L4: `groups` attribute is display-level only, not a true ACL:**
The `groups='...'` attribute on fields is an invisible/readonly filter applied at the UI level. It does NOT block programmatic `write()` or SQL access. Users without `project.group_project_user` can still set `project_id` via Python code or direct DB manipulation. For true record-level security (e.g., users can only see MOs for their assigned projects), `ir.rule` records on `mrp.production` with domain `[('project_id', 'in', user.project_ids.ids)]` must be added separately.

**L4: Cross-module ACL interaction:**
`project_mrp` bridges two security domains (MRP and Project). A user with `mrp.group_mrp_user` but without `project.group_project_user` can see `project_id` in the stat buttons (via `bom_count` / `production_count`) but not in the MO/BoM form fields. This is intentional — manufacturing users see the project link in the dashboard but cannot edit the project field directly.

---

## Performance Considerations

| Area | Concern | Mitigation |
|------|---------|------------|
| `store=True` on `mrp.production.project_id` | Every `bom_id` change triggers a DB write + column update | Intended — enables efficient domain filtering; BoM changes are infrequent |
| `_read_group` counters | No N+1 risk at compute level (single SQL group-by) | `_read_group` replaces O(n) `search_count` calls with O(1) SQL query |
| `_prepare_procurement_values` on every move | Runs on every component stock move during procurement planning | The `len(group.mrp_production_ids) == 1` check is a lightweight SQL count; called frequently in large MOs but microsecond-level |
| `_prepare_mo_vals` override | Called once per MO creation via procurement | Negligible overhead — single conditional check |
| `action_open_project()` with null guard | No explicit guard for `project_id = False` | XML button has `invisible="not project_id"` — method only called when project exists |

---

## Version Changes: Odoo 18 to 19

No functional changes to `project_mrp` between Odoo 18 and 19. The module structure, field definitions, and method implementations are identical across both versions.

Minor annotation-level changes:
- `export_string_translation=False` on `bom_count` and `production_count` fields was introduced in Odoo 17 and persists in 19. This prevents these system-integer fields from appearing in `.po` translation files — no functional impact.

No deprecations, no API changes, no new dependencies.

---

## Field Reference

### `mrp.bom` Fields Added by `project_mrp`

| Field | Type | Required | Indexed | Stored |
|-------|------|----------|---------|--------|
| `project_id` | `Many2one(project.project)` | No | Yes (FK) | Yes (direct column) |

### `mrp.production` Fields Added by `project_mrp`

| Field | Type | Required | Indexed | Stored | Compute |
|-------|------|----------|---------|--------|---------|
| `project_id` | `Many2one(project.project)` | No | Yes (FK) | Yes | `_compute_project_id` |

### `project.project` Fields Added by `project_mrp`

| Field | Type | Groups | Stored | Compute |
|-------|------|--------|--------|---------|
| `bom_count` | `Integer` | `mrp.group_mrp_user` | No | `_compute_bom_count` |
| `production_count` | `Integer` | `mrp.group_mrp_user` | No | `_compute_production_count` |

---

## Related Documentation

- [Modules/mrp](Modules/mrp.md) — MRP (Manufacturing) module reference
- [Modules/project](Modules/project.md) — Project management module reference
- [Modules/project_mrp_account](Modules/project_mrp_account.md) — MRP + Account bridge
- [Modules/project_mrp_sale](Modules/project_mrp_sale.md) — MRP + Sale bridge (triple integration)
- [Modules/project_mrp_stock_landed_costs](Modules/project_mrp_stock_landed_costs.md) — MRP + Account + Landed Costs
- [Patterns/Workflow Patterns](odoo-18/Patterns/Workflow Patterns.md) — State machines and action methods
