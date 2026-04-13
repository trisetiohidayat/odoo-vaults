---
type: flow
title: "BOM to Production Order Flow"
primary_model: mrp.production
trigger: "User action — Manufacturing → Orders → Create / From BOM"
cross_module: true
models_touched:
  - mrp.production
  - mrp.bom
  - mrp.bom.line
  - stock.move
  - stock.picking
  - procurement.group
audience: ai-reasoning, developer
level: 1
source_module: mrp
source_path: ~/odoo/odoo19/odoo/addons/mrp/
created: 2026-04-07
updated: 2026-04-07
version: "1.0"
---

# BOM to Production Order Flow

## Overview

Creating a production order from a Bill of Materials (BOM) is the entry point for the manufacturing lifecycle. When a user creates an `mrp.production` record — either manually or via the BOM wizard — Odoo automatically generates raw material stock moves from each BOM line, creates finished goods moves, and generates workorders from the BOM's routing operations. Component availability is checked immediately, and the production order state is set accordingly.

## Trigger Point

`mrp.production.create(vals)` — called directly or via the `mrp.product.template` action_compute_bom_days wizard. The user selects a product, quantity, and optionally a BOM; Odoo then auto-populates moves and workorders.

---

## Complete Method Chain

```
1. mrp.production.create({'product_id': p, 'product_qty': qty, 'bom_id': bom})
   │
   ├─► 2. _onchange_product_id() — set product_uom from product
   │     └─► product_uom_id = product.uom_id
   │
   ├─► 3. _onchange_bom_id() — fill moves from BOM lines
   │     └─► for each bom_line in bom.bom_line_ids:
   │           └─► 4. stock.move.create() — component consumption move
   │                 ├─► product_id = bom_line.product_id
   │                 ├─► product_uom_qty = bom_line.qty * production_qty / bom_line.bom_id.product_qty
   │                 ├─► product_uom_id = bom_line.product_uom_id
   │                 ├─► location_id = production.location_src_id (work order source)
   │                 ├─► location_dest_id = production.location_dest_id (finished goods dest)
   │                 ├─► raw_material_production_id = self
   │                 └─► bom_line_id = bom_line
   │
   ├─► 5. write({'bom_id': bom}) if not already set on vals
   │
   ├─► 6. _onchange_move_raw() — recompute quantities on raw moves
   │     └─► _update_move_raw_ids() recalculates product_uom_qty
   │
   ├─► 7. Finished goods move created (move_finished_ids)
   │     └─► stock.move.create()
   │           ├─► product_id = production.product_id
   │           ├─► product_uom_qty = production_qty
   │           ├─► location_id = production.location_src_id
   │           ├─► location_dest_id = production.location_dest_id
   │           └─► production_id = self
   │
   ├─► 8. workorder_ids created from routing (mrp.routing.workcenter)
   │     └─► for each operation in bom.operation_ids (sorted by sequence):
   │           └─► 9. mrp.workorder.create()
   │                 ├─► production_id = self
   │                 ├─► name = operation.name
   │                 ├─► workcenter_id = operation.workcenter_id
   │                 ├─► operation_id = operation
   │                 ├─► duration_expected = operation.time_cycle * qty / operation.workcenter_id.capacity
   │                 ├─► date_start = planned start from scheduling
   │                 ├─► date_finished = planned end
   │                 ├─► state = 'draft' (initially)
   │                 └─► blocked_by_workorder_ids = operation.blocked_by_operation_ids
   │
   ├─► 10. Availability check — _compute_move_raw_ids()
   │      └─► for each raw move: stock.move._action_assign()
   │            └─► stock.quant reserved if available
   │
   ├─► 11. IF all components available:
   │        └─► state = 'confirmed' / 'ready'
   │      ELSE:
   │        └─► state = 'confirmed' (waiting materials)
   │
   ├─► 12. commitment_date set — date by which materials must be reserved
   │
   ├─► 13. IF bom.type == 'phantom' (kit):
   │        └─► _explode Mara (recursive explode of sub-assemblies)
   │              └─► each sub-BOM exploded into its own bom_lines
   │
   ├─► 14. procurement.group created or reused for the production
   │      └─► group_id = procurement.group or existing
   │
   ├─► 15. IF tracked product (lot):
   │        └─► lot_producing_id must be assigned before done
   │
   ├─► 16. IF tracked product (serial):
   │        └─► one production per serial number required
   │
   └─► 17. byproducts from bom.byproduct_ids created
          └─► stock.move for each mrp.bom.byproduct
```

---

## Decision Tree

```
mrp.production.create({...})
│
├─► bom_id provided?
│  ├─► YES → _onchange_bom_id() — fill moves from BOM
│  └─► NO → user must fill moves manually
│
├─► bom.type == 'kit' (phantom)?
│  ├─► YES → explode() recursively — each sub-assembly becomes a move
│  │        └─► multi-level BOM: walk all child_bom_ids
│  └─► NO (normal) → bom_line → stock.move directly
│
├─► product tracking == 'lot'?
│  └─► YES → lot_producing_ids must be set before action_done()
│
├─► product tracking == 'serial'?
│  ├─► YES → one production per serial number
│  │        └─► qty must be 1 per MO for serial
│  └─► NO → any qty allowed
│
├─► multi-level BOM (child_bom_id on line)?
│  └─► YES → recursive explode — sub-assembly lines added
│
├─► bom.operation_ids present (routing)?
│  ├─► YES → workorder_ids created from each operation
│  └─► NO → no workorders, direct production
│
└─► ALWAYS:
   └─► move_raw_ids + move_finished_ids created
       └─► state set based on component availability
```

---

## Database State After Completion

| Table | Record Created/Updated | Key Fields |
|-------|----------------------|------------|
| `mrp_production` | Created | id, name, product_id, product_qty, bom_id, state, location_src_id, location_dest_id |
| `stock_move` (raw) | Created (one per BOM line) | product_id, product_uom_qty, location_id, location_dest_id, raw_material_production_id, state |
| `stock_move` (finished) | Created | product_id, product_uom_qty, production_id, location_id, location_dest_id, state |
| `mrp_workorder` | Created (one per routing operation) | production_id, workcenter_id, operation_id, duration_expected, state |
| `stock_quant` | Reserved (if components available) | reserved_quantity updated |
| `procurement_group` | Created or reused | group linking procurement |
| `mrp_bom_byproduct` | Linked | byproduct moves generated |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Reason |
|----------|-------------|---------------------|
| No BOM found for product | `UserError` | Odoo cannot find an active BOM for the product |
| product_qty <= 0 | `ValidationError` | Quantity must be positive |
| Component product inactive | `ValidationError` | Active BOM lines cannot reference inactive products |
| product_tmpl_id not set on BOM | `ValidationError` | BOM must have a product_tmpl_id |
| No workcenter on routing operation | `ValidationError` | Each operation must have a workcenter_id |
| Duplicate serial number assigned | `ValidationError` | Serial numbers must be unique per product |
| Insufficient stock for component | No error — state stays `confirmed` | Reservation fails; state remains `confirmed` waiting materials |
| BOM with cycle (A→B→A) | `UserError` | Recursive BOM explosion prevented |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Sequence incremented | `ir.sequence` | `mrp.production` name generated (e.g., MO/00123) |
| Stock reservation attempted | `stock.quant` | `reserved_quantity` increased on component quants |
| Move states updated | `stock_move` | Raw moves set to `assigned` if available |
| Production group created | `procurement_group` | Groups MO with related pickings |
| Picking type set | `stock.picking.type` | Inferred from warehouse manufacturing settings |
| Deadline propagated | `mrp_production` | date_deadline set from product lead time |
| MO visible in manufacturing dashboard | `mrp_production` | Record appears in Manufacturing → Orders |

---

## Security Context

> *Which user context the flow runs under, and what access rights are required at each step.*

| Step | Security Mode | Access Required | Notes |
|------|-------------|----------------|-------|
| `create()` | Current user | `mrp.group_mrp_manager` or `user` | Respects record rules for mrp_production |
| `_onchange_bom_id()` | Current user | Read ACL on `mrp.bom`, `mrp.bom.line` | Visible fields only |
| `stock.move.create()` | `sudo()` | System — internal ORM | Cross-model write without ACL |
| `_action_assign()` | Current user | Read ACL on `stock.quant`, write on `stock.move` | Reservation requires stock rights |
| Workorder creation | Current user | Read ACL on `mrp.routing.workcenter`, `mrp.workcenter` | Routing read access needed |
| Button "Create Manufacturing Order" | `ir.model.access` | `mrp.group_mrp_manager` | Portal users cannot create MO |

**Key principle:** Most Odoo methods run as the **current logged-in user**, not as superuser. Use `sudo()` only when intentionally bypassing ACL. Manufacturing order creation requires `mrp` user rights.

---

## Transaction Boundary

> *Which steps are inside the database transaction and which are outside. Critical for understanding atomicity and rollback behavior.*

```
Steps 1-17  ✅ ALL INSIDE transaction  — atomic (all or nothing)
No async steps in BOM → MO creation
```

| Step | Boundary | Behavior on Failure |
|------|----------|-------------------|
| Steps 1-17 | ✅ Atomic | Rollback on any error — no partial MO created |
| Stock reservation (`_action_assign`) | ✅ Atomic | Rolled back with MO if any error occurs |
| BOM explosion | ✅ Atomic | Rolled back with MO |

**Rule of thumb:** MO creation from BOM is a single atomic transaction. If any step fails (no BOM, invalid qty, etc.), the entire MO is rolled back. No external systems are called.

---

## Idempotency

> *What happens when this flow is executed multiple times (double-click, race condition, re-trigger).*

| Scenario | Behavior |
|----------|----------|
| Double-click "Create" button | ORM deduplicates — one MO created; second click creates second MO |
| Create with same vals twice | Two separate MO records created (each has unique `ir.sequence` name) |
| Re-call `_onchange_bom_id()` on existing MO | Moves may be re-created if not yet confirmed — Odoo warns if moves already exist |
| Re-trigger on confirmed MO | State machine prevents — `action_draft()` needed first |
| Concurrent creation (two users same product) | Two separate MOs created — no conflict |

**Common patterns:**
- **Non-idempotent:** Sequence number consumed on each `create()` — name is unique
- **Idempotent:** `_onchange_*()` methods can be called multiple times safely
- **Deduplication not automatic:** Multiple MO creation is by design; use lock or check before creating

---

## Extension Points

> *Where and how developers can override or extend this flow. Critical for understanding Odoo's inheritance model.*

| Step | Hook Method | Purpose | Arguments | Override Pattern |
|------|-------------|---------|-----------|-----------------|
| Step 2 | `_onchange_product_id()` | Set defaults from product | self | Extend with `super()` — add uom or name logic |
| Step 3 | `_onchange_bom_id()` | Fill moves from BOM | self | Override to add custom move fields |
| Step 4 | `_prepare_mrp_production_blend()` | Pre-create hook for moves | vals, bom_line | Extend `create()` vals modification |
| Step 8 | `_create_workorder_from_routing()` | Workorder creation logic | self, operations | Override to add custom workorder fields |
| Pre-create | `_init()` / `create()` vals hook | Pre-creation validation | vals | Extend `create()` with vals inspection |
| Post-create | `_<model>_post_create()` | Post-creation side effect | self | Extend via `create()` override |
| Step 10 | `_action_assign()` | Component availability | self | Override to add custom reservation logic |
| Validation | `_check_*()` | Custom constraint | self | Add `@api.constrains` |

**Standard override pattern:**
```python
# WRONG — replaces entire method
def _onchange_bom_id(self):
    # your code only

# CORRECT — extends with super()
def _onchange_bom_id(self):
    res = super()._onchange_bom_id()
    # your additional code — e.g., set custom move fields
    return res
```

**Deprecated override points to avoid:**
- `@api.multi` on overridden methods (deprecated in Odoo 19)
- `@api.one` anywhere (deprecated)
- Direct `_workflow` calls (deprecated — use `action_*` methods)
- Overriding `create()` without calling `super()` — breaks framework

---

## Reverse / Undo Flow

> *How to cancel or reverse this flow. Critical for understanding what is and isn't reversible.*

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| `create()` MO | `action_cancel()` | `production.action_cancel()` | Only if state is `draft` or `confirmed` |
| Confirmed MO cancellation | `action_draft()` | Resets to `draft` — unreserve quants | Stock quants unreserved |
| Confirmed MO with reserved stock | `action_unreserve()` | Unreserves quants, MO stays `confirmed` | Materials no longer locked |
| `unlink()` | NOT reversible | Deletes MO and all related moves/workorders | Cascade delete |
| Set to `done` | `mrp.unbuild` | `action_unbuild()` | Returns components to stock |

**Important — partially reversible:**
- MO in `draft` → fully reversible (no stock effects yet)
- MO in `confirmed` → reversible (quants unreserved on cancel)
- MO in `done` → use `mrp.unbuild` to return materials to stock; original MO and moves remain
- Stock moves that were `done` are immutable — unbuild creates counter-moves

---

## Alternative Triggers

> *All the ways this flow can be initiated — not just the primary user action.*

| Trigger Type | Method / Endpoint | Context | Frequency |
|-------------|------------------|---------|-----------|
| User action | `action_create_mo()` button in BOM | Interactive | Manual |
| User action | `Manufacturing → Orders → Create` | Form view | Manual |
| Automated action | `stock.rule` (procurement) | `procurement.group` scheduler | On reorder point |
| Cron scheduler | `_cron_mrp_production_order()` | Server action | Scheduled |
| Ondemand procurement | `procurement.group.run()` | From sale order or MTO | On demand |
| Onchanges on related models | `_onchange_product_id()` cascade | Product change on form | On demand |
| API / External | `mrp.production` JSON-RPC create | External system | On demand |
| Kit explosion | `mrp.bom explode()` | Phantom BOM on order | On demand |

**For AI reasoning:** When asked "what happens if X?", trace all triggers — an MO can be created from a BOM, from a sale order line, from a reorder point, or manually. Each path has the same end state but different origins.

---

## Related

- [Flows/MRP/production-order-flow](flows/mrp/production-order-flow.md) — Production order execution
- [Flows/MRP/workorder-execution-flow](flows/mrp/workorder-execution-flow.md) — Workorder lifecycle
- [Modules/MRP](modules/mrp.md) — MRP module reference
- [Modules/Stock](modules/stock.md) — Inventory and materials
- [Patterns/Workflow Patterns](patterns/workflow-patterns.md) — State machine patterns
- [Core/API](core/api.md) — @api decorator patterns
