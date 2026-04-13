---
description: Technical bridge module that chains sale_purchase + project_purchase + sale_project into a complete SO → PO → Project traceability chain, propagating project_id and analytic_distribution into the purchase procurement pipeline.
tags:
  - odoo
  - odoo19
  - modules
  - sale_purchase_project
  - inter-module-bridge
  - analytic-accounting
  - procurement
---

# sale_purchase_project

Technical bridge module that chains three modules together to provide a complete **SO → PO → Project** traceability chain, enabling purchase procurement and project delivery to share the same analytic cost center.

---

## Module Identity

| Attribute        | Value                                                         |
|------------------|----------------------------------------------------------------|
| **Name**         | Sale Purchase Project                                          |
| **Category**     | Sales                                                         |
| **Version**      | `19.0` (Odoo 19 only)                                         |
| **Depends**      | `sale_purchase`, `project_purchase`, `sale_project`           |
| **Auto-install** | `True` — installed automatically when all three deps are present |
| **License**      | LGPL-3                                                        |
| **Author**       | Odoo S.A.                                                     |
| **Summary**      | `Technical Bridge`                                             |

`auto_install: True` means this module activates as soon as all three dependencies are installed, without being manually selected. This is critical because it ensures the bridge is always active in any installation that has the full chain — preventing orphaned `purchase.order` records without `project_id` set in a partially-installed environment.

---

## L1 — Architecture Overview

`sale_purchase_project` does **not** define new models, new fields, new database tables, or new views. It is a pure behavioral patch module — two method overrides on `sale.order.line` from `sale_purchase`, injected into the PO creation pipeline.

### Dependency Chain (Full Triple)

```
sale.order.line
    │
    ├── via sale_purchase (provides _purchase_service_* methods):
    │       └─ creates purchase.order.line (service_to_purchase flow)
    │           └─ _purchase_service_create()
    │               ├─ _purchase_service_prepare_order_values()   ← PATCHED HERE
    │               └─ _purchase_service_prepare_line_values()     ← PATCHED HERE
    │
    ├── via sale_project (provides sale.order.project_id):
    │       └─ sale.order has Many2one: project_id
    │           └─ project._get_analytic_distribution() → analytic_distribution
    │
    └── via project_purchase (consumes the patch):
            └─ purchase.order has Many2one: project_id
                └─ purchase.order.line._compute_analytic_distribution() uses project_id
                    └─ PO lines appear in project profitability report
```

`project_purchase` is the module that **consumes** the bridge. Without this module, the PO would have `project_id` set but no cost would surface in profitability. Without `sale_purchase_project`, `project_purchase` would receive POs with `project_id = False` (because `sale_purchase` does not propagate the SO's project onto the PO).

### Why This Module Exists

`sale_purchase` handles the SO → PO creation mechanics: it has `_purchase_service_create()` and its helper methods. It does **not** know about `project_id` because `project_id` on `sale.order` is defined by `sale_project`, which `sale_purchase` does not depend on.

`sale_project` creates tasks from SOs and manages `sale.order.project_id`, but does not touch the purchase pipeline.

`project_purchase` extends `purchase.order.line` with `_compute_analytic_distribution()` that reads `line.order_id.project_id` and merges project analytic accounts into PO lines — but only if the PO's `project_id` is set.

`sale_purchase_project` is the missing wire: it injects `project_id` into the PO header and `analytic_distribution` into the PO line, closing the triple loop.

---

## L2 — Field Types, Defaults, Constraints

Since this module introduces no new models or fields, the relevant data structures are the vals dicts returned by the two overridden methods.

### `_purchase_service_prepare_order_values` Return Value

Called when a **new** `purchase.order` must be created (no matching draft PO for the vendor). Returns a `dict` passed directly to `env['purchase.order'].create(vals)`.

Injected field:

| Field                | Type       | Value                                         | Notes |
|----------------------|------------|-----------------------------------------------|-------|
| `project_id`         | `many2one` | `self.order_id.project_id.id`                | Can be `False`; ORM stores `False` if `id` is `False` |

The `project_id` field on `purchase.order` is defined by `project_purchase` (which inherits `project.project` pattern onto `purchase.order`). No constraint is added by this module.

### `_purchase_service_prepare_line_values` Return Value

Called to prepare values for each `purchase.order.line` created. Returns a `dict` passed to `env['purchase.order.line'].create(vals)`.

Injected field conditionally:

| Field                  | Type   | Value                                                              | Notes |
|------------------------|--------|--------------------------------------------------------------------|-------|
| `analytic_distribution` | `dict` | `self.order_id.project_id._get_analytic_distribution()` or nothing | Only injected if `self.analytic_distribution` is falsy |

**`analytic_distribution` type:** A `JSON` field on `purchase.order.line`. Stored as a Python `dict` in ORM but serialized to JSONB in PostgreSQL. Shape:

```python
{
    "<account_analytic_account_id_as_string>": <percentage_as_float>,
    ...
}
# Example: {'42': 100.0, '17': 50.0}
```

- Keys are **always string** (this is the source of many integration bugs in RPC calls — integer keys silently mismatch).
- Percentages must sum to 100.0 for the distribution to be valid.
- `_get_analytic_distribution()` returns a dict already keyed by `str(account.id)`.

### Defaults

No new defaults are introduced. The inheritance chain retains all defaults from `sale_purchase`:
- `purchase.order`: `state = 'draft'`, `date_order = now`
- `purchase.order.line`: `product_qty = 1.0`, `price_unit = 0.0`

### Constraints

No SQL or API constraints are added by this module. The only constraint logic is the conditional guard `if not self.analytic_distribution` — a Python `if` statement, not a formal Odoo constraint.

---

## L3 — Cross-Model, Override Pattern, Workflow Triggers

### Override Pattern: Why Both Methods?

`sale_purchase` creates POs in two stages:

**Stage 1 — PO header creation** (when no matching draft PO exists):
```python
def _purchase_service_create(self, supplierinfo):
    order_vals = self._purchase_service_prepare_order_values(supplierinfo)
    purchase_order = self.env['purchase.order'].create(order_vals)
    # ...
```

**Stage 2 — PO line creation** (always, whether PO is new or matched):
```python
    line_vals = self._purchase_service_prepare_line_values(purchase_order, quantity)
    po_line = self.env['purchase.order.line'].create(line_vals)
```

Both stages need project context:
- The PO header needs `project_id` so `project_purchase` can include it in profitability queries and the stat button.
- The PO line needs `analytic_distribution` so costs are attributed to the right analytic account when the vendor bill is posted.

If only the order-level patch existed, the PO would link to the project but PO line costs would not be attributed (since the line's `analytic_distribution` would be empty and `project_purchase`'s compute would have no `project_id` to read from the line itself — it would need to traverse `order_id.project_id` which it does, but the merge logic depends on the line having an existing distribution to merge **into**).

Actually, `project_purchase`'s `_compute_analytic_distribution()` reads `line.order_id.project_id` directly — so the PO line would still get project analytics even without the line-level patch. The line-level patch provides a fallback: if the SOL has no explicit distribution, the project's distribution is pre-seeded so `project_purchase`'s compute can merge additional plan accounts into it rather than replacing it.

### Workflow Trigger Chain (Complete)

```
sale.order.button_confirm()
  └─ sale.order._action_confirm()
      └─ sale.order.line._timesheet_service_generation()     [sale_project]
      └─ sale.order.line._purchase_service_generation()       [sale_purchase]
          └─ for each line with service_to_purchase=True:
              └─ _purchase_service_create(supplierinfo)
                  ├─ _match_or_create_purchase_order(supplierinfo)
                  │     └─ if no match: _create_purchase_order()
                  │           └─ _purchase_service_prepare_order_values()   ← HERE (1)
                  │                 └─ injects: {'project_id': self.order_id.project_id.id}
                  │                 └─ env['purchase.order'].create(vals)
                  │
                  └─ _purchase_service_prepare_line_values(purchase_order, qty)  ← HERE (2)
                        └─ injects: {'analytic_distribution': project._get_analytic_distribution()}
                        └─ env['purchase.order.line'].create(vals)
                              └─ purchase.order.line._compute_analytic_distribution() [project_purchase]
                                    └─ merges project accounts from different plans into line's distribution
```

### Cross-Model: `project_purchase` Merge Logic (L3 Detail)

After `sale_purchase_project` pre-seeds `analytic_distribution` on the PO line, `project_purchase`'s `purchase.order.line._compute_analytic_distribution()` fires as a `create()` write. Its merge logic:

```python
# Simplified from project_purchase
def _compute_analytic_distribution(self):
    if self.order_id.project_id:
        project_distribution = self.order_id.project_id._get_analytic_distribution()
        existing = self.analytic_distribution or {}
        applied_root_plans = {
            self.env['account.analytic.account'].browse(int(k)).root_plan_id
            for k in existing
        }
        accounts_to_add = self.order_id.project_id._get_analytic_accounts().filtered(
            lambda a: a.root_plan_id not in applied_root_plans
        )
        # Append new plan accounts to existing distribution
        for account in accounts_to_add:
            existing[str(account.id)] = 100.0  # or project distribution value
        self.analytic_distribution = existing
```

This means the **final** `analytic_distribution` on the PO line is a union of:
1. SOL's own explicit analytic distribution (if manually set, preserved — highest priority)
2. Project's default analytic distribution (pre-seeded by `sale_purchase_project` via `_purchase_service_prepare_line_values`)
3. Project accounts from **additional** analytic plans not already covered (appended by `project_purchase`)

The distinction between step 2 and 3 is subtle but important: `sale_purchase_project` provides the base distribution from the project's default analytic plan. `project_purchase` appends accounts from other plans if the project uses multiple plans.

---

## L4 — Version Change: Odoo 18 → Odoo 19

### Module Status Across Versions

`sale_purchase_project` was introduced in Odoo 16 as part of the project-purchase integration work and has remained essentially unchanged through Odoo 18 and 19.

### Key Changes in Odoo 18 → 19

#### 1. `analytic_distribution` Field API Stability

The `analytic_distribution` field (on `purchase.order.line`, `account.analytic.line`, and other models) uses **string keys** in its dict representation. This is stable across Odoo 18→19, but there are subtle differences in how the ORM serializes/deserializes:

- In Odoo 18, `str(account.id)` was consistently used throughout.
- In Odoo 19, the field uses JSONB storage in PostgreSQL. The serialization contract remains `str(key): float(percentage)`.
- **Migration concern:** If custom code stores integer keys in the dict (e.g., `{42: 100}` instead of `{'42': 100}`), the ORM may reject the value or silently corrupt it. Always use `str(account_id)`.

#### 2. `project_id` Propagation via Context vs. Field

In Odoo 18, `project_purchase` introduced the `project_id` field on `purchase.order`. The mechanism by which `sale_purchase` finds the project to link has two paths:

**Odoo 18 path:**
```python
# project_purchase: purchase.order.line._compute_analytic_distribution()
# reads from order_id.project_id directly
project = line.order_id.project_id
```

**Odoo 19 path:** Identical. The `project_id` on `purchase.order` is a stored field (not computed), so it is directly readable.

**Impact on `sale_purchase_project`:** The module's role is unchanged — it writes `project_id` on the PO header when creating a new PO, which populates the stored field. For matched POs (already existing draft POs for the vendor), `project_purchase`'s compute handles the line-level distribution.

#### 3. `Domain` Class API (Odoo 19 Pattern)

Not directly used in this module, but relevant to the ecosystem: Odoo 19 introduced the `Domain` helper class for composing domain tuples programmatically. This is used in `project_mrp_account` but not here.

#### 4. Method Signature Stability

Both overridden methods have stable signatures across Odoo 18→19:

```python
# sale_purchase: sale.order.line
def _purchase_service_prepare_order_values(self, supplierinfo) -> dict
def _purchase_service_prepare_line_values(self, purchase_order, quantity=False) -> dict
```

These are internal/private methods (no `_` prefix in name but no external API contract). They have been stable since their introduction.

#### 5. Potential Breaking Change: `sale.order.project_id` Compute

In Odoo 19, `sale_project`'s `sale.order.project_id` is a related field to `task_ids.project_id` (for project-based SOs). If the SO has tasks, the project is derived. If no tasks, the project may be manually set. This does not affect `sale_purchase_project`'s behavior — it reads `self.order_id.project_id` regardless of how it was set.

#### 6. `sudo()` Context in `_purchase_service_generation`

The parent method `_purchase_service_generation` (in `sale_purchase`) runs its PO creation in `sudo()` context:
```python
# sale_purchase: sale.order.line
def _purchase_service_generation(self):
    for line in self.filtered(...):
        line.sudo()._purchase_service_create(supplierinfo)
```

This is unchanged in Odoo 19. The implication is that the `project_id` and `analytic_distribution` written by `sale_purchase_project` bypass ACL checks. This is consistent with the rest of the SO confirmation flow.

### Migration Checklist

| Check | Detail |
|-------|--------|
| `analytic_distribution` key type | Ensure custom code always uses `str(account_id)`, not integer keys |
| `project_purchase` installed | This bridge requires `project_purchase`; without it, PO lines have no profitability linkage |
| `sale_project` project_id source | If using project-based SOs with task derivation, confirm the project is correctly set on the SO before confirmation |
| Multi-vendor batching | When multiple SOLs from the same SO use the same vendor, they are batched into one PO. `project_id` is set on first insertion and applies to the whole PO. Subsequent SOLs from the same SO do not re-write PO values. |

---

## Project Profitability Flow

The end-to-end cost tracking pipeline:

```
1. SO confirmed
     └─ SOL with service_to_purchase=True
          ├─ Creates purchase.order + purchase.order.line
          │     ├─ PO header: project_id = sale.order.project_id   (sale_purchase_project)
          │     └─ PO line: analytic_distribution = project AA    (sale_purchase_project)
          └─ PO line cost = 0 until receipt

2. Vendor bill posted (purchase.order → account.move)
     └─ purchase.order.line._compute_bill_account_id()
          └─ analytic_distribution controls which analytic account receives the cost

3. PO line linked to project profitability:
     └─ purchase.order.line.project_id = sale.order.project_id
     └─ project_purchase → appears in Project → 'Purchase Costs' section
```

`sale_purchase_project` is the missing link that propagates `project_id` from the SO header to the PO header, and `analytic_distribution` from the project to the PO line, enabling `project_purchase` to surface purchase costs in the project profitability report.

---

## Test Coverage

### `test_pol_analytic_distribution`

**File:** `tests/test_sale_purchase_project.py`

**Class:** `TestSalePurchaseProject` (inherits `TestSalePurchase` from `sale_purchase`)

**Scenario:** Two confirmed SOs assigned to the same project. One SOL has an explicit analytic distribution override; the other does not.

**Steps:**
1. Create a project with a named analytic plan and `test_analytic_account_1`. Remove the auto-generated `account_id` from the project (so only the named plan account is used).
2. Set `sale_order_1.project_id` and `sale_order_2.project_id` to the shared project.
3. Set `sale_order_2.order_line.analytic_distribution = {test_analytic_account_2: 100}` (explicit override).
4. Confirm both SOs → triggers `_purchase_service_generation`.

**Assertions:**
- Two separate POs are created (one per vendor), each with 2 lines.
- PO line from `sale_order_1`: `analytic_distribution` = `{project's analytic account: 100}` — inherited from project via `_purchase_service_prepare_line_values`.
- PO line from `sale_order_2`: `analytic_distribution` = `{test_analytic_account_2: 100}` — SOL's explicit distribution preserved. The conditional `if not self.analytic_distribution` guard prevents the project's distribution from overwriting the explicit override.

**Edge case validated by the test:**
The conditional guard in `_purchase_service_prepare_line_values` is the mechanism that produces this behavior:
```python
if not self.analytic_distribution and analytic_distribution:
    purchase_line_vals['analytic_distribution'] = analytic_distribution
```
Without it, the explicit SOL distribution would be silently overwritten by the project's distribution.

**Additional test assertions:**
- The 2 POs are in `draft` state (not auto-confirmed).
- Each PO has exactly 2 lines (one per SOL).
- The 2 SOLs that map to the same vendor product (same `seller_ids`) are batched into the same PO.

---

## Security Considerations (L4)

### `sudo()` Context Bypass

All PO creation via this module runs in `sudo()` context when called from `_purchase_service_generation` (via `lines.sudo().with_company(...)`). This bypasses record rules for `purchase.order.line` creation. This is inherited behavior from `sale_purchase` and is not changed by this module.

**Implication:** A user who can confirm an SO with a linked project will trigger PO line creation even if they lack direct `purchase.order.line` create permissions. The ACL check is bypassed at the ORM level.

### `analytic_distribution` Write Without ACL Visibility

The `analytic_distribution` written to PO lines controls cost attribution. A user with write access to `sale.order.line` (needed to set `service_to_purchase = True`) but without `account.analytic.account` read access could still trigger PO creation with analytic distributions referencing accounts they cannot inspect.

**Mitigation:** `analytic_distribution` requires `account.analytic.account` read access to be displayed in the UI. However, the dict is stored on the line regardless of whether the user can see it.

### `purchase.order.project_id` ACL Gap

`purchase.order.project_id` is a Many2one with no ACL enforcement specific to this module. Any user who can confirm an SO with a project linked can cause POs to be associated with that project. The project association then influences `project_purchase`'s profitability calculations.

**No record rule** restricts PO `project_id` assignment to project managers. This is a design choice — SO confirmation is already a high-privilege operation.

### `sale_purchase_project` Itself Has No ACL

No `security/ir.model.access.csv` file exists in this module. All access control inherits from the three dependency modules. The module introduces no new models, fields, or views.

---

## Edge Cases (L4)

### 1. No `project_id` on SO

If `sale.order.project_id` is `False` (no project linked), both overridden methods execute without injecting anything:
- `_purchase_service_prepare_order_values`: writes `{'project_id': False}` — PO has no project.
- `_purchase_service_prepare_line_values`: condition `if not self.analytic_distribution and analytic_distribution` fails because `analytic_distribution` is also `False` — no distribution injected.

**Result:** PO is created, but it has no `project_id` and no `analytic_distribution`. `project_purchase`'s compute finds nothing to attribute. **PO will not appear in project profitability.**

### 2. SOL Has Explicit `analytic_distribution`

If the SOL already has an explicit analytic distribution set (manually or via another module), the line-level patch preserves it:
```python
if not self.analytic_distribution and analytic_distribution:
```
The `not self.analytic_distribution` guard means: only inject project distribution if SOL has **none**. User-specified distribution is always preserved.

### 3. Same Vendor, Multiple SOLs, Same SO

When two SOLs from the same SO use the same vendor:
- `_match_or_create_purchase_order` finds the first draft PO created by the first SOL's call.
- The second SOL's `_create_purchase_order` is skipped; the existing PO is reused.
- `project_id` is already set on the PO header by the first call; the second call does not re-write.

**If the two SOLs belong to different SOs** (each with a different `project_id`): the first SO sets `project_id = project_A`, the second SO sets `project_id = project_B`. The PO ends up associated with the **last** project's `project_id`. Both SOLs' PO lines may have different `analytic_distribution` values but share the same PO `project_id`.

### 4. Changing `sale.order.project_id` After PO Creation

If the SO's `project_id` is changed after the PO has been created:
- Existing PO lines retain their `analytic_distribution` values.
- The PO's `project_id` is not updated (it's already written).
- **No automatic propagation** of the new project onto existing PO lines.

**Resolution:** User must manually update the PO's `project_id` and PO lines' `analytic_distribution`.

### 5. Stale Analytic Account After Deletion

If `project_id.account_id` (the analytic account on the project) is deleted after PO creation:
- PO lines retain the stale distribution dict with the deleted account's ID.
- No automatic cleanup occurs.
- Vendor bill posting may fail or create orphaned analytic lines.

---

## Related Modules

| Module                | Role in Chain                                                          |
|-----------------------|------------------------------------------------------------------------|
| `sale_purchase`       | Core SO → PO creation; `_purchase_service_*` method family             |
| `project_purchase`    | `purchase.order.project_id` field; PO costs in project profitability    |
| `sale_project`        | `sale.order.project_id` field; task generation from SOs                 |
| `sale_purchase_project` | **This module** — bridges project context into PO creation pipeline     |

---

## Related

- [Modules/sale_purchase](modules/sale_purchase.md) — Core SO to PO linking
- [Modules/project_purchase](modules/project_purchase.md) — PO costs in project profitability
- [Modules/sale_project](modules/sale_project.md) — Task generation from SOs
- [Patterns/Workflow Patterns](patterns/workflow-patterns.md) — State machine patterns
- [Modules/Stock](modules/stock.md) — Stock move costing (`_create_analytic_move`)
