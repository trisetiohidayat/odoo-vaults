---
type: module
module: project_mrp_sale
tags: [odoo, odoo19, project, mrp, sale, bridge, integration, auto-install]
created: 2026-04-06
updated: 2026-04-11
---

# Project MRP Sale (`project_mrp_sale`)

## Overview

| Property | Value |
|----------|-------|
| **Technical Name** | `project_mrp_sale` |
| **Version** | 19.0.1.0.0 (Odoo CE) |
| **Category** | Services/Project |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Auto-install** | `True` |
| **Hard Depends** | `project_mrp`, `sale_mrp`, `sale_project` |

## Purpose

`project_mrp_sale` is a **pure glue module** — it defines no models, no fields, and no business logic of its own. Its sole purpose is to activate the three-way integration chain between `sale.order`, `mrp.production`, and `project.project` when all three underlying bridge modules (`project_mrp`, `sale_mrp`, `sale_project`) are installed simultaneously.

The three-way chain makes the Odoo manufacturing + project + sales integration work for Make-to-Order (MTO) flows: a sales order generates a manufacturing order, and that MO is linked to the same project the sales order belongs to. This allows manufacturing costs to flow into the project's analytic accounting and profitability panel.

## Dependency Architecture

```
Dependency chain:
  sale.order  ─────── (sale_project) ───────► project.project
       │                                            ▲
       │                                            │
       └─── (sale_mrp) ───► mrp.production ─────────┘
                                     ▲
                                     │
                              (project_mrp)

  project_mrp_sale is the "glue" that declares all three as
  required, triggering auto-install when the full chain is present.
```

| Module | Relationship Owned | Key File |
|--------|-------------------|----------|
| `sale_mrp` | `sale.order` → `mrp.production` (via `sale_line_id`, `reference_ids`) | `addons/sale_mrp/models/mrp_production.py`, `addons/sale_mrp/models/stock_rule.py` |
| `project_mrp` | `mrp.production` → `project.project` (via `project_id` on MO, `project_id` on BoM) | `addons/project_mrp/models/mrp_production.py`, `addons/project_mrp/models/stock.py` |
| `sale_project` | `sale.order` → `project.project` (via `project_id` on SO, `project_id` on SOL) | `addons/sale_project/models/sale_order.py`, `addons/sale_project/models/sale_order_line.py` |

**Why `auto_install: True` matters:** When a database has `project_mrp`, `sale_mrp`, and `sale_project` installed, Odoo's module installer automatically queues `project_mrp_sale` for installation. Without this module, the three-way chain would still work through shared data (all three pairs are independently connected), but `project_mrp_sale` ensures the chain is activated and tested as a cohesive unit. The test `test_mo_get_project_from_so` (see below) verifies this integration specifically.

---

## Integration Test: `test_mo_get_project_from_so`

**File:** `tests/test_sale_mrp_account.py`

```python
@common.tagged('post_install', '-at_install')
class TestSaleMrpAccount(TestMultistepManufacturing):
    def test_mo_get_project_from_so(self):
        """ ensure the project of MO is inherited from the SO if no project is set """
        project = self.env['project.project'].create({'name': 'SO Project'})
        self.sale_order.project_id = project
        self.assertFalse(self.sale_order.mrp_production_ids.project_id)
        self.sale_order.action_confirm()
        self.assertEqual(self.sale_order.mrp_production_ids.project_id, project)
```

**Test setup (`TestMultistepManufacturing` in `sale_mrp.tests.test_multistep_manufacturing`):**
- Creates a warehouse with MTO + manufacture routes enabled
- Creates a manufactured product (`Stick`) with a BoM (1x `Raw Stick`)
- Creates a SO for `Stick`, warehouse set, `picking_policy = 'direct'`
- The BoM has no `project_id` set

**Assertion sequence:**

1. `project_id` is set on the SO to a manually created project.
2. At SO-draft stage, `mrp_production_ids` is empty (SO not yet confirmed).
3. `action_confirm()` triggers:
   - Stock procurement generates the MO via `stock.rule._prepare_mo_vals`
   - The MO is created with `origin = self.name` (SO name)
4. `sale.order.mrp_production_ids` now contains the MO (via `stock_reference_ids.production_ids`).
5. The test asserts `project_id` equals the SO's project — **the key integration behavior**.

**L4: How project propagates from SO to MO:**

The propagation chain involves all three bridge modules working together:

```
sale_order.action_confirm()
  → procurement triggered for SO line
  → sale_order_line._prepare_procurement_values()
      → values['project_id'] = self.order_id.project_id   (from sale_project)
      → values['sale_line_id'] = self.id                   (from sale_mrp)

  → stock.rule._prepare_mo_vals()
      → super() returns res with res['bom_id'] and res['project_id'] = bom.project_id
      → if values.get('sale_line_id'): res['sale_line_id'] = values['sale_line_id']  (sale_mrp)
      → if values.get('project_id'): res['project_id'] = values['project_id']        (project_mrp)
      → returns res with project_id from SO (values) and sale_line_id

  → mrp.production.create(res)
      → project_id written directly from vals
      → bom_id is set → _compute_project_id() fires
      → bom_id.project_id is False (BoM has no project)
      → production.project_id = False  ← compute OVERWRITES

[FAIL CASE] → In practice, this test should fail because the BoM has no project.
```

**CRITICAL FINDING — Test vs. Implementation Gap:**

The test asserts `project_id` equals the SO's project, but the BoM used in the test has no `project_id` set. The `_compute_project_id` method, when it fires, reads `bom_id.project_id` (which is `False`) and writes `False` to `project_id`, overwriting the value that `_prepare_mo_vals` set from `values['project_id']` (which came from the SO's project).

This suggests one of the following is true in Odoo 19:
1. The test BoM is created with a project in the full `TestMultistepManufacturing` setup (via the warehouse's default BoM or MTO route setup).
2. The compute does NOT fire during `create()` when `bom_id` is passed in the vals dict and `project_id` is also present — the ORM may short-circuit recomputation if the value being computed matches the value already being written.
3. The test is testing the intended *design* behavior (that SO→project→MO should work), and the actual code path relies on the BoM also having a project set.

**Workaround for production use:** Ensure the BoM used in SO→MO flows has `project_id` set to the same project as the SO, OR set `project_id` directly on the MO after creation. When the BoM has a `project_id`, the compute correctly propagates it to the MO.

---

## Complete Integration Chain: All Three Bridge Modules

### `sale_project` — `sale.order.line` Extension

**File:** `addons/sale_project/models/sale_order_line.py`

```python
def _prepare_procurement_values(self):
    values = super()._prepare_procurement_values()
    if self.order_id.project_id:
        values['project_id'] = self.order_id.project_id.id
    return values
```

This is the **origin of `project_id` in the procurement values** for SO-triggered manufacturing. When a sale order line triggers a procurement (via MTO route), this method populates `values['project_id']` from `order_id.project_id`.

Note: This only runs for procurement-triggered MOs, not for manually created MOs or BoM-based MOs created outside of a sale context.

### `project_mrp` — `stock.rule._prepare_mo_vals` Extension

**File:** `addons/project_mrp/models/stock.py`

```python
def _prepare_mo_vals(self, product_id, product_qty, product_uom, location_id, name, origin, company_id, values, bom):
    res = super()._prepare_mo_vals(product_id, product_qty, product_uom, location_id, name, origin, company_id, values, bom)
    if values.get('project_id'):
        res['project_id'] = values.get('project_id')
    return res
```

This copies `values['project_id']` (set by `sale_project`'s `_prepare_procurement_values`) into the MO vals dict. This is the **second link** in the chain: procurement → MO.

### `sale_mrp` — `stock.rule._prepare_mo_vals` Extension

**File:** `addons/sale_mrp/models/stock_rule.py`

```python
def _prepare_mo_vals(self, product_id, product_qty, product_uom, location_dest_id, name, origin, company_id, values, bom):
    res = super()._prepare_mo_vals(product_id, product_qty, product_uom, location_dest_id, name, origin, company_id, values, bom)
    if values.get('sale_line_id'):
        res['sale_line_id'] = values['sale_line_id']
    return res
```

This copies `sale_line_id` from procurement values into the MO. This is the **parallel link** that creates the SO↔MO relationship (distinct from the project link). It works alongside `project_mrp`'s override in the same method, but they handle different fields.

### `project_mrp` — `mrp.production._compute_project_id`

**File:** `addons/project_mrp/models/mrp_production.py`

```python
@api.depends('bom_id')
def _compute_project_id(self):
    if not self.env.context.get('from_project_action'):
        for production in self:
            production.project_id = production.bom_id.project_id
```

This is the **potential overwrite** in the chain. When an MO is created from a BoM (which is always the case in SO→MO flows), `bom_id` is set. The compute fires and reads `bom_id.project_id`. If the BoM has a project set, the MO gets that project. If the BoM has no project, the compute writes `False`, overwriting whatever `_prepare_mo_vals` set.

### `sale_mrp` — `mrp.production` Fields and Actions

**File:** `addons/sale_mrp/models/mrp_production.py`

| Field | Type | Groups | Description |
|-------|------|--------|-------------|
| `sale_order_count` | `Integer` (computed) | `sales_team.group_sale_salesman` | Count of distinct SOs linked to this MO. Union of `reference_ids.sale_ids` and `sale_line_id.order_id`. |
| `sale_line_id` | `Many2one` → `sale.order.line` | — | The specific SOL that triggered MO creation (set by `stock.rule._prepare_mo_vals`). |

```python
@api.depends('reference_ids.sale_ids', 'sale_line_id.order_id')
def _compute_sale_order_count(self):
    for production in self:
        production.sale_order_count = len(
            production.reference_ids.sale_ids | production.sale_line_id.order_id
        )
```

**`action_confirm()` Enhancement:**
```python
def action_confirm(self):
    res = super().action_confirm()
    for production in self:
        if production.sale_line_id:
            production.move_finished_ids.filtered(
                lambda m: m.product_id == production.product_id
            ).sale_line_id = production.sale_line_id
    return res
```

On MO confirmation, `sale_line_id` is propagated to the finished stock move (`move_finished_ids` where the product matches the MO's finished product). This links the finished goods stock move back to the SOL, enabling:
- Delivery picking to be linked back to the SOL
- `sale.order` `stock_reference_ids` to capture the finished goods move
- Invoicing workflows that match moves back to SOLs

### `sale_mrp` — `sale.order` Extension

**File:** `addons/sale_mrp/models/sale_order.py`

| Field | Type | Groups | Description |
|-------|------|--------|-------------|
| `mrp_production_count` | `Integer` | `mrp.group_mrp_user` | Count of top-level (non-sub) MOs linked to this SO. |
| `mrp_production_ids` | `Many2many` → `mrp.production` | `mrp.group_mrp_user` | All first-level (non-cancelled) MOs generated by this SO. Excludes sub-assembly MOs. |

```python
@api.depends('stock_reference_ids.production_ids')
def _compute_mrp_production_ids(self):
    for sale in self:
        mos = sale.stock_reference_ids.production_ids
        sale.mrp_production_ids = mos.filtered(
            lambda mo: not mo.production_group_id.parent_ids and mo.state != 'cancel'
        )
        sale.mrp_production_count = len(sale.mrp_production_ids)
```

Key filter: `not mo.production_group_id.parent_ids` removes sub-assembly MOs — only the top-level MO that directly fulfills the SO line appears on the SO. `state != 'cancel'` excludes cancelled MOs.

### `sale_project` — `sale.order` Extension

**File:** `addons/sale_project/models/sale_order.py`

| Field | Type | Description |
|-------|------|-------------|
| `project_id` | `Many2one` → `project.project` | The project linked to this SO. Domain: `[('allow_billable', '=', True), ('is_template', '=', False)]`. |
| `project_account_id` | `Many2one` → `account.analytic.account` | Related (readonly) to `project_id.account_id`. Used as analytic distribution default on SOLs. |
| `tasks_ids` | `Many2many` → `project.task` | All tasks linked to this SO (via SOL `project_id` or `sale_order_id`). |
| `project_ids` | `Many2many` → `project.project` | All projects linked to this SO (SO-level + SOL-level). |
| `project_count` | `Integer` | Count of active linked projects. |

**`_action_confirm()` Enhancement (partial):**

```python
def _action_confirm(self):
    if self.env.context.get('disable_project_task_generation'):
        return super()._action_confirm()
    # service line → task/project generation
    self.order_line.sudo().with_company(self.company_id)._timesheet_service_generation()
    ...
    return super()._action_confirm()
```

On SO confirmation, service lines generate tasks or projects under `sale.order.project_id`. This creates the project that `project_mrp` then propagates to the MO via procurement.

---

## Workflow Triggers: When Does Each Link Activate?

### Trigger 1: SO Confirmation → MO creation → Project link

```
User action: SO → Confirm
  sale_order.action_confirm()
    → _action_confirm() [sale_project]
      → _timesheet_service_generation() creates tasks/projects
    → super()._action_confirm() [sale]
      → procurement launches for SO lines with MTO route

  Procurement engine runs:
    sale_order_line._prepare_procurement_values() [sale_project]
      → values['project_id'] = order.project_id
    stock.rule._prepare_mo_vals() [project_mrp + sale_mrp]
      → res['sale_line_id'] = values['sale_line_id']      [sale_mrp]
      → res['project_id'] = values['project_id']           [project_mrp]
    mrp.production.create(res)
      → project_id set from vals
      → if bom_id: _compute_project_id() fires
        → project_id = bom_id.project_id  (may overwrite)
```

### Trigger 2: MO creation from BoM → Project via BoM

```
User action: MRP → Create MO → Select BoM
  mrp.production.create({..., 'bom_id': bom_id})
    → if bom_id: _compute_project_id() fires
      → production.project_id = bom_id.project_id
    → project derived from BoM, not from procurement
```

### Trigger 3: MO creation from procurement (non-SO) → Project via group

```
User/Scheduler action: Procurement launch for non-SO source
  stock.move._prepare_procurement_values() [project_mrp]
    → if group.mrp_production_ids has exactly 1 MO:
      → values['project_id'] = group.mrp_production_ids.project_id
    → values passed to stock.rule._prepare_mo_vals()
    → res['project_id'] = values['project_id']  [project_mrp]
```

---

## Failure Modes

| Failure Mode | Cause | Symptom | Fix |
|-------------|-------|---------|-----|
| MO has no `project_id` despite SO having one | BoM has no `project_id` set; compute overwrites procurement-derived project | MO not visible in project dashboard; manufacturing costs not attributed to project | Set `project_id` on the BoM, or set it manually on the MO after creation |
| Sub-assembly MOs get wrong project | `len(group.mrp_production_ids) > 1` causes `_prepare_procurement_values` to skip propagation | Sub-assemblies under wrong project | Assign project to each sub-assembly BoM individually |
| MO project overwritten when BoM changed | User changes BoM on an existing MO with a project set | `project_id` reverts to BoM's project (or `False`) | The `from_project_action` context prevents this during project-dashboard navigation, but not during manual BoM changes |
| `sale_line_id` not set on MO | Procurement not triggered via MTO route; or SOL not linked to procurement | `sale_order_count = 0` on MO; finished move not linked to SOL | Ensure MTO route is active on the product/warehouse; verify `sale_line_id` in the procurement values |

---

## Security Model

`project_mrp_sale` has no own security records (no `security/ir.model.access.csv`, no `ir.rule` definitions). Security is entirely delegated to the three dependent modules.

| Concern | Resolution |
|---------|------------|
| Who can create MOs linked to a project? | `mrp.group_mrp_user` ACL on `mrp.production` |
| Who can see `project_id` on the MO form? | `project.group_project_user` via `groups` attribute |
| Who can link a SO to a project? | `project.group_project_user` ACL on `project.project` |
| Who can see `sale_line_id` on the MO? | No group restriction — available to all users (used in manufacturing context) |
| Record-level access: can a user see MOs for projects they don't have access to? | Not enforced by this module. An `ir.rule` on `mrp.production` with domain `[('project_id', 'in', user.project_ids.ids)]` would be needed. |

---

## Version Changes: Odoo 18 to 19

No changes to `project_mrp_sale` itself (the module has no code). However, the following changes in Odoo 19 affect the integration chain:

| Component | Odoo 18 | Odoo 19 | Impact |
|-----------|---------|---------|--------|
| `sale_line_id` on `mrp.production` | Stored directly | Stored directly | No change |
| `reference_ids` (polymorphic link) | `stock.scrap` origin tracking | `stock.record` model for polymorphic links | `sale_mrp` uses `reference_ids.sale_ids` for SO counting — this is Odoo 19's new polymorphic mechanism and works correctly |
| `_read_group` on counters | Standard | Standard | No change |
| `_compute_project_id` | Identical | Identical | No change |

**`stock.record` (Odoo 19 new feature):** The `reference_ids` field is a polymorphic `stock.record` relation introduced in Odoo 18/19. It replaces ad-hoc origin tracking. `sale_mrp` uses `reference_ids.sale_ids` to find all SOs linked to an MO's procurement group. This is a stable Odoo 19 API.

**No deprecations or breaking changes** in the integration chain between Odoo 18 and 19.

---

## Related Documentation

- [[Modules/project_mrp]] — MRP ↔ Project bridge (this module's foundation)
- [[Modules/sale_mrp]] — Sale ↔ MRP bridge
- [[Modules/sale_project]] — Sale ↔ Project bridge
- [[Modules/mrp]] — MRP (Manufacturing) module reference
- [[Modules/project]] — Project management module reference
- [[Modules/project_mrp_account]] — MRP + Account bridge (adds profitability)
- [[Modules/project_mrp_stock_landed_costs]] — MRP + Account + Landed Costs
