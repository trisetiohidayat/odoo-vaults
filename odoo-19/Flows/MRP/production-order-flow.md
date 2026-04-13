---
type: flow
title: "Production Order Execution Flow"
primary_model: mrp.production
trigger: "User action — Manufacturing → Production Order → Start / Mark Done"
cross_module: true
models_touched:
  - mrp.production
  - mrp.workorder
  - stock.move
  - stock.quant
  - account.move
audience: ai-reasoning, developer
level: 1
source_module: mrp
source_path: ~/odoo/odoo19/odoo/addons/mrp/
created: 2026-04-07
updated: 2026-04-07
version: "1.0"
---

# Production Order Execution Flow

## Overview

Executing a production order consumes components from stock, produces finished goods, completes workorders at workcenters, and posts valuation entries if accounting is enabled. The flow progresses from `confirmed` → `progress` → `to_close` → `done`. Materials are reserved and consumed via stock moves; finished goods quantities are posted to stock quants; byproducts are handled; and an `account.move` is generated for inventory valuation.

## Trigger Point

`mrp.production.action_assign()` — checks material availability. `mrp.production.action_start()` — begins production. `mrp.production.action_done()` — finalizes the MO and posts all stock moves.

---

## Complete Method Chain

### START PRODUCTION

```
1. mrp.production.action_assign() — check material availability
   │
   ├─► 2. _action_assign() → stock.move _action_assign()
   │     └─► for each raw_material move:
   │           ├─► stock.quant reserved
   │           ├─► move.state = 'assigned'
   │           └─► reservation_state = 'assigned'
   │
   └─► 3. state: draft → confirmed (if not already)
        └─► availability_state checked

4. mrp.production.action_start() → _action_start()
   │
   ├─► 5. for each workorder: workorder.state = 'pending' or 'ready'
   │
   ├─► 6. for first workorder (by sequence): workorder.action_start()
   │     └─► workorder.state = 'in_progress'
   │           └─► workcenter blocked for this workorder
   │
   ├─► 7. state: confirmed → 'to_close'
   │     └─► reservation_state set to 'assigned'
   │
   └─► 8. date_start recorded = now()
```

### WORKORDER EXECUTION per operation

```
9.  mrp.workorder.action_start()  [per workorder]
    │
    ├─► 10. write({'state': 'progress', 'date_start': now()})
    │      └─► if time_tracking = 'auto': mrp.workcenter.productivity tracking started
    │
    ├─► 11. _start_timer() → workcenter blocked for this workorder
    │      └─► workcenter.working_state = 'blocked'
    │
    └─► 12. if operation type = 'quality': quality_check created
          └─► mrp.quality.check record generated

13. mrp.workorder.action_record_production()
    │
    ├─► 14. _record_production()
    │     ├─► for finished product move:
    │     │     └─► 15. stock.move._action_done() → qty_done recorded
    │     │           ├─► qty_done = qty_producing
    │     │           └─► if serial_number: assigned to move line
    │     │
    │     └─► 16. write({'qty_produced': qty_producing})
    │
    └─► 17. mrp.workorder.action_next() → move to next workorder
          └─► if next_workorder exists:
                └─► 18. next_workorder.action_start()
                else: workorder.state = 'done'

19. mrp.workorder.action_finish() → _action_finish()
    │
    ├─► 20. write({'state': 'done', 'date_finished': now()})
    │      └─► if time_tracking: stop_timer()
    │            └─► mrp.workcenter.productivity logged
    │
    └─► 21. duration = date_finished - date_start
          └─► workcenter unblocked (working_state = 'normal')
```

### COMPLETE PRODUCTION

```
22. mrp.production.action_done() → _action_done()
    │
    ├─► 23. for each finished move:
    │      └─► stock.move action_done()
    │            ├─► qty_done posted
    │            └─► location_dest_id: finished goods location
    │
    ├─► 24. stock.quant _update_available_quantity(+qty) at finished location
    │      └─► if lot tracked: lot assigned to finished quant
    │      └─► if serial tracked: serial numbers generated per unit
    │
    ├─► 25. for each raw move: action_done()
          └─► components consumed
          └─► stock.quant _update_available_quantity(-qty) at components location
          └─► reserved_quantity reduced on quants
    │
    ├─► 26. scrap created if any (mrp.scrap)
    │      └─► scrap moves created → stock.move
    │
    ├─► 27. if byproduct: byproduct moves created
    │      └─► stock.move for each mrp.bom.byproduct
    │            └─► qty = byproduct.product_qty * production_qty / bom.product_qty
    │
    ├─► 28. account_move generated (if valuation enabled via stock_account)
    │      └─► inventory valuation posted
    │      └─► debit: component value to WIP
    │      └─► credit: finished goods at cost
    │
    ├─► 29. state: to_close → 'done'
    │      └─► qty_produced updated
    │
    └─► 30. byproducts accounted in cost_share
          └─► finished goods cost reduced by byproduct value
```

---

## Decision Tree

```
action_done() called
│
├─► all workorders done?
│  ├─► YES → proceed to finalize production
│  └─► NO → raise UserError("Workorders not completed")
│
├─► any workorder in 'progress'?
│  └─► YES → must finish or cancel workorder first
│
├─► scrap created during production?
│  └─► YES → scrap move and quant updated
│        └─► scrap moves posted alongside component consumption
│
├─► qty_produced < product_qty (planned)?
│  ├─► YES → backorder created (if backorder confirmed)
│  │        └─► new MO for remaining qty
│  └─► NO → full qty produced
│
├─► lot/serial tracked?
│  ├─► YES → lot_producing_ids must be set
│  └─► NO → continue
│
└─► ALWAYS:
   └─► component quants consumed → available_qty reduced
       finished goods quants created → available_qty increased
       account.move posted (if valuation enabled)
```

---

## Database State After Completion

| Table | Record Created/Updated | Key Fields |
|-------|----------------------|------------|
| `mrp_production` | Updated | state = 'done', qty_produced, date_finished |
| `stock_move` (raw) | Updated | state = 'done', quantity_done |
| `stock_move` (finished) | Updated | state = 'done', quantity_done |
| `stock_move` (byproduct) | Created/Updated | state = 'done', byproduct qty done |
| `stock_quant` | Updated | available_quantity decreased for components, increased for finished goods |
| `mrp_workorder` (all) | Updated | state = 'done', date_finished, duration |
| `mrp_workcenter` | Updated | working_state = 'normal', blocked_time updated |
| `mrp_workcenter.productivity` | Created | duration logged per workorder |
| `mrp_scrap` | Created (if any scrap) | scrap_qty, location_id |
| `account_move` | Created (if valuation) | inventory valuation journal entry |
| `stock_valuation_layer` | Created | value posted for each move |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Reason |
|----------|-------------|---------------------|
| Workorders not done | `UserError` | All workorders must be `done` before MO done |
| No lot assigned for lot-tracked product | `UserError` | `lot_producing_id` required |
| Serial not assigned | `ValidationError` | Serial number required for tracked product |
| Insufficient stock at consume | `UserError` | No quant available to consume |
| Negative quant after consume | `UserError` | Cannot consume more than available |
| Production already done | `UserError` | Cannot re-done an `done` MO |
| MO cancelled | `UserError` | Cannot start a cancelled MO |
| Scrap qty > consumed qty | `ValidationError` | Cannot scrap more than consumed |
| Valuation account missing | `ValidationError` | `property_stock_valuation_account_id` must be set |
| Cost not computable | `UserError` | Cannot post valuation without cost |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Stock reserved | `stock.quant` | reserved_quantity set on component quants |
| Stock consumed | `stock.quant` | available_quantity decreased on component location |
| Finished goods posted | `stock.quant` | available_quantity increased at finished goods location |
| Workcenter blocked | `mrp.workcenter` | working_state = 'blocked' during workorder |
| Time logged | `mrp.workcenter.productivity` | Duration recorded for reporting |
| Inventory valuation | `account.move` | WIP debit, FG credit posted |
| Backorder created | `mrp_production` | New MO for remaining qty created |
| Scrap move created | `stock.move` | Scrap location receives components |
| MO sequence consumed | `ir.sequence` | No new sequence on done, only on create |
| OEE updated | `mrp.workcenter` | OEE (Overall Equipment Effectiveness) recalculated |

---

## Security Context

> *Which user context the flow runs under, and what access rights are required at each step.*

| Step | Security Mode | Access Required | Notes |
|------|-------------|----------------|-------|
| `action_assign()` | Current user | `stock.group_stock_user` | Reserves materials |
| `action_start()` | Current user | `mrp.group_mrp_user` | Starts production |
| `workorder.action_start()` | Current user | `mrp.group_mrp_user` | Time tracking |
| `_action_done()` on moves | `sudo()` | System — internal ORM | Stock accounting |
| `stock.quant _update_available_quantity()` | `sudo()` | System — internal ORM | No ACL for quant updates |
| `action_done()` | Current user | `mrp.group_mrp_manager` | Finalize MO |
| Scrap creation | Current user | `mrp.group_mrp_user` | Scrap rights |
| Valuation posting | `sudo()` | System — internal | Accounting write without ACL |
| Backorder creation | `sudo()` | System | Creates new MO |

**Key principle:** Stock quant updates and accounting moves run as `sudo()` — they are internal framework operations that bypass ACL. User-facing buttons like `action_start()` and `action_done()` require the appropriate `mrp` user group.

---

## Transaction Boundary

> *Which steps are inside the database transaction and which are outside. Critical for understanding atomicity and rollback behavior.*

```
Steps 1-8   ✅ INSIDE transaction  — material reservation atomic
Steps 9-21  ✅ INSIDE transaction  — workorder execution atomic per WO
Steps 22-30 ✅ INSIDE transaction  — action_done atomic — all stock moves posted
No async steps in production execution
```

| Step | Boundary | Behavior on Failure |
|------|----------|-------------------|
| Steps 1-8 (action_assign/start) | ✅ Atomic | Rollback on any reservation error |
| Steps 22-30 (action_done) | ✅ Atomic | Rollback — no partial posting |
| Stock quant updates | ✅ Atomic | Part of action_done transaction |
| Account.move posting | ✅ Atomic | Posted within same DB transaction |
| Backorder creation | ✅ Atomic | Created in same transaction |
| Scrap creation | ✅ Atomic | Created within same transaction |
| Time tracking log | ✅ Atomic | Within workorder action_finish |

**Rule of thumb:** Production execution is fully atomic. If `action_done()` fails (e.g., no valuation account), no stock moves are posted and no accounting entry is created. The MO remains in `to_close` state.

---

## Idempotency

> *What happens when this flow is executed multiple times (double-click, race condition, re-trigger).*

| Scenario | Behavior |
|----------|----------|
| Double-click "Mark Done" button | ORM deduplicates — `action_done()` checks state first; second call raises `UserError` |
| Re-trigger action_done() on done MO | State machine prevents — raises `UserError("Production already done")` |
| Re-reserve already reserved components | No-op — `action_assign()` checks existing reservation |
| Re-start already started workorder | `action_start()` on `progress` WO is no-op |
| Re-finish already done workorder | `action_finish()` on `done` WO is no-op |
| Concurrent action_done() on same MO (two tabs) | First succeeds, second raises `UserError` — ORM locking |
| Network timeout + retry | MO may be already done — handle `UserError` gracefully |

**Common patterns:**
- **Idempotent:** `action_done()` on already-done MO raises error (safe guard)
- **Non-idempotent:** Each `action_done()` consumes stock quants once — consuming twice would cause negative quants (blocked by constraint)
- **Workorder time:** Calling `action_finish()` twice doubles logged time if not guarded

---

## Extension Points

> *Where and how developers can override or extend this flow. Critical for understanding Odoo's inheritance model.*

| Step | Hook Method | Purpose | Arguments | Override Pattern |
|------|-------------|---------|-----------|-----------------|
| Step 2 | `_action_assign()` | Custom reservation logic | self | Extend with `super()` — add custom reserve rules |
| Step 4 | `_action_start()` | Pre-start validation | self | Extend with `super()` — add checks before starting |
| Step 9 | `workorder.action_start()` | Workorder start logic | self | Override on `mrp.workorder` |
| Step 13 | `action_record_production()` | Record production hook | self | Extend with `super()` |
| Step 14 | `_record_production()` | Custom recording | self | Extend with `super()` |
| Step 22 | `_action_done()` | Finalize production | self | Extend with `super()` — add custom done logic |
| Step 23 | `_post_inventory()` | Inventory valuation hook | self | Extend for custom valuation |
| Step 25 | `_update_available_quantity()` | Custom stock update | self | Extend on `stock.quant` |
| Step 28 | `_create_account_move()` | Custom valuation entry | self | Override for custom costing |
| Validation | `_check_*()` | Custom constraint | self | Add `@api.constrains` |

**Standard override pattern:**
```python
# WRONG — replaces entire method
def _action_done(self):
    # your code only

# CORRECT — extends with super()
def _action_done(self):
    res = super()._action_done()
    # your additional code — e.g., notify external system
    return res
```

**Deprecated override points to avoid:**
- `@api.multi` on overridden methods (deprecated in Odoo 19)
- `@api.one` anywhere (deprecated)
- Direct `_workflow` calls (deprecated)
- Overriding without `super()` — breaks core flow
- `_action_done()` without calling `super()` — stock moves won't post

---

## Reverse / Undo Flow

> *How to cancel or reverse this flow. Critical for understanding what is and isn't reversible.*

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| `action_start()` | `action_draft()` | `production.action_draft()` | Resets to `draft` — unreserves quants |
| `action_done()` | `mrp.unbuild` | `action_unbuild()` | Creates unbuild order — returns components |
| Unbuild MO | `stock.quant` | `_update_available_quantity()` | Components returned to source location |
| Finished goods unbuild | Stock move created | New move for returned finished goods | Original `done` MO remains (immutable) |
| Cancel done MO | NOT directly possible | Must use `mrp.unbuild` | Cannot delete `done` MO without unbuilding |
| Cancel scrap | `unlink()` scrap record | Only if scrap not yet done | Scrap moves are posted |

**Important — partially reversible:**
- MO in `progress` → `action_draft()` fully reverses (resets to `draft`, unreserves quants)
- MO in `done` → `mrp.unbuild` is the only reversal path. It creates a disassembly order that:
  1. Consumes the finished goods (decreases FG quants)
  2. Produces back the original components (increases component quants)
  3. Creates its own moves and accounting entries
- Stock moves that were `done` are **immutable** — unbuild creates counter-moves
- `account.move` entries are immutable once posted — unbuild creates reversing entries

---

## Alternative Triggers

> *All the ways this flow can be initiated — not just the primary user action.*

| Trigger Type | Method / Endpoint | Context | Frequency |
|-------------|------------------|---------|-----------|
| User action | `action_start()` button | Form view button | Manual |
| User action | `action_done()` button | Form view button | Manual |
| User action | `action_mark_done()` via barcode | Barcode scanner | Manual |
| Workorder completion | `action_finish()` auto-trigger | Last workorder done | Automatic |
| Cron scheduler | `_cron_mrp_production_check()` | Auto-close finished MO | Scheduled |
| Quality alert | `quality.alert` resolution | Alert closed → continue | On event |
| Sale order cancellation | `sale.order action_cancel()` | Cancels linked MO | On event |
| Automated action | `base.automation` | Rule triggers action | On rule match |
| External / API | JSON-RPC on `mrp.production` | External MES | On demand |

**For AI reasoning:** When asked "what happens if X?", trace all triggers — a production can be started from the MO form, from a workorder, from a barcode scan, or automatically by a scheduler. Each path ends in the same state transitions.

---

## Related

- [Flows/MRP/bom-to-production-flow](Flows/MRP/bom-to-production-flow.md) — BOM to production order creation
- [Flows/MRP/workorder-execution-flow](Flows/MRP/workorder-execution-flow.md) — Workorder lifecycle
- [Modules/MRP](Modules/mrp.md) — MRP module reference
- [Modules/Stock](Modules/stock.md) — Inventory and materials
- [Modules/Account](Modules/account.md) — Inventory valuation
- [Modules/Quality](Modules/quality.md) — Quality checks integration
- [Patterns/Workflow Patterns](odoo-18/Patterns/Workflow Patterns.md) — State machine patterns
- [Core/API](Core/API.md) — @api decorator patterns
