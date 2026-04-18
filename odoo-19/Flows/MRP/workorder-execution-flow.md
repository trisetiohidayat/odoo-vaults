---
type: flow
title: "Workorder Execution Flow"
primary_model: mrp.workorder
trigger: "User action — Workorder → Start / Process / Record Production"
cross_module: true
models_touched:
  - mrp.workorder
  - stock.move
  - stock.move.line
  - mrp.workcenter
  - mrp.workcenter.productivity
audience: ai-reasoning, developer
level: 1
source_module: mrp
source_path: ~/odoo/odoo19/odoo/addons/mrp/
created: 2026-04-07
updated: 2026-04-07
version: "1.0"
---

# Workorder Execution Flow

## Overview

A workorder represents a single operation at a workcenter within a production order. The workorder lifecycle covers time tracking, component consumption at the operation level, quality checks, and recording finished goods quantity. Each workorder is sequenced within the production order's routing, and workorders can be dependent on each other (blocked_by/blocks relationships). When a workorder is completed, Odoo advances to the next operation or finalizes the production if it was the last workorder.

## Trigger Point

`mrp.workorder.action_start()` — begins the workorder timer and blocks the workcenter. `mrp.workorder.action_record_production()` — records the quantity produced at this operation. `mrp.workorder.action_finish()` — marks the operation complete and stops the timer.

---

## Complete Method Chain

```
1. mrp.workorder.action_start()
   │
   ├─► 2. write({'state': 'progress', 'date_start': now()})
   │
   ├─► 3. IF time_tracking = 'auto':
   │      └─► 4. _start_timer() → mrp.workcenter.productivity tracking started
   │            ├─► mrp.workcenter.productivity.create({
   │            │      workorder_id = self,
   │            │      workcenter_id = workcenter_id,
   │            │      date_start = now()
   │            │ })
   │            └─► 5. workcenter.working_state = 'blocked'
   │                  └─► workcenter blocked for this workorder
   │
   ├─► 6. IF operation type = 'material':
   │      └─► 7. components auto-reserved
   │            └─► for each move_raw linked to this workorder:
   │                  └─► stock.move._action_assign()
   │
   └─► 8. IF operation type = 'quality':
          └─► 9. quality_check created at operation
                └─► mrp.quality.check triggered before record production

10. mrp.workorder.action_record_production()
    │
    ├─► 11. _record_production()
    │     │
    │     ├─► 12. for finished product move linked to this workorder:
    │     │      └─► stock.move._action_done()
    │     │            ├─► qty_done += qty_producing
    │     │            └─► if serial_number:
    │     │                  └─► 13. lot/serial assigned to stock.move.line
    │     │                        └─► lot_id = lot_producing_id
    │     │
    │     ├─► 14. write({'qty_produced': qty_producing})
    │     │      └─► qty_producing updated on workorder
    │     │
    │     └─► 15. IF byproduct at this operation:
    │            └─► 16. stock.move for byproduct._action_done()
    │                  └─► byproduct quant created at operation location
    │
    └─► 17. mrp.workorder.action_next() → move to next workorder in sequence
          ├─► IF next_workorder exists (by sequence):
          │      └─► 18. next_workorder.action_start()
          │            └─► state = 'progress', timer starts
          └─► ELSE (no next workorder):
                 └─► 19. this workorder.state = 'done'
                       └─► production.state checked for finalization

20. mrp.workorder.action_finish() → _action_finish()
    │
    ├─► 21. write({'state': 'done', 'date_finished': now()})
    │
    ├─► 22. IF time_tracking = 'auto' or 'manual':
    │      └─► 23. _stop_timer()
    │            └─► mrp.workcenter.productivity.write({'date_end': now()})
    │                  └─► duration = date_end - date_start
    │                        └─► productivity.duration updated
    │
    ├─► 24. duration = date_finished - date_start (actual)
    │      └─► duration_expected compared for OEE calculation
    │
    ├─► 25. workcenter.working_state = 'normal'
    │      └─► workcenter unblocked — available for next workorder
    │
    └─► 26. IF all workorders on production are done:
              └─► production.state → 'to_close'
              └─► production.action_done() auto-triggered if all done
```

---

## Decision Tree

```
action_start()
│
├─► blocked_by_workorder_ids not empty?
│  ├─► YES → workorder state = 'blocked'
│  │        └─► Cannot start until predecessor is done
│  └─► NO → proceed to start
│
├─► time_tracking = 'auto'?
│  ├─► YES → timer started automatically on action_start()
│  └─► NO → manual time recording
│
action_record_production()
│
├─► quality_checks present?
│  ├─► YES → check must pass before recording
│  │        └─► if check fails: action_record_production blocked
│  └─► NO → continue
│
├─► lot/serial tracked on product?
│  ├─► YES → lot_producing_ids must be specified
│  │        └─► if serial: one qty per serial
│  └─► NO → any qty
│
├─► next workorder exists?
│  ├─► YES → advance to next workorder
│  └─► NO → mark current done, check if production complete
│
└─► ALWAYS:
   └─► qty_producing consumed from raw moves
       └─► component quants updated if consumed at operation
```

---

## Database State After Completion

| Table | Record Created/Updated | Key Fields |
|-------|----------------------|------------|
| `mrp_workorder` | Updated | state = 'done', date_finished, duration, qty_produced |
| `stock_move` (finished) | Updated | state = 'done', quantity_done, move_line_ids updated |
| `stock_move.line` | Created/Updated | lot_id, serial_number, qty_done per line |
| `stock_quant` | Updated | available_quantity consumed at operation location |
| `mrp_workcenter` | Updated | working_state = 'normal', oee updated |
| `mrp_workcenter.productivity` | Created | date_start, date_end, duration logged |
| `mrp_production` | Updated | state = 'to_close' when last workorder done |
| `stock_move` (byproduct) | Created/Updated | byproduct qty done |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Reason |
|----------|-------------|---------------------|
| Blocked by previous workorder | `UserError` | Cannot start blocked workorder |
| Quality check failed | `UserError` | Quality check must pass before record production |
| No serial number assigned | `ValidationError` | Serial tracking requires lot_producing_id |
| Duplicate serial number | `ValidationError` | Serial numbers must be unique |
| Workorder already started | No error | `action_start()` on `progress` is no-op |
| Workorder already done | `UserError` | Cannot re-done a workorder |
| Quantity exceeds production qty | `UserError` | Cannot record more than production_qty |
| Workcenter unavailable | `UserError` | Workcenter is blocked by another workorder |
| No qty_producing set | `UserError` | Must specify quantity before recording |
| Negative duration logged | `ValidationError` | date_end must be after date_start |
| Backorder qty mismatch | `UserError` | Recorded qty + scrap must equal production qty |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Workcenter blocked | `mrp.workcenter` | working_state = 'blocked' — no other WO can use this WC |
| Time log created | `mrp_workcenter.productivity` | Duration entry recorded for reporting |
| OEE updated | `mrp_workcenter` | Overall Equipment Effectiveness recalculated |
| Component consumed | `stock_quant` | available_quantity decreased at operation location |
| Finished goods quant created | `stock_quant` | available_quantity increased at finished goods location |
| Lot assigned | `stock_move.line` | lot_id set on move line |
| Next workorder auto-started | `mrp_workorder` | action_start() called on next by sequence |
| Production auto-closed | `mrp_production` | State → 'to_close' when last WO done |
| Scrap at operation | `mrp_scrap` | Scrap created if qty_consumed > qty_producing |

---

## Security Context

> *Which user context the flow runs under, and what access rights are required at each step.*

| Step | Security Mode | Access Required | Notes |
|------|-------------|----------------|-------|
| `action_start()` | Current user | `mrp.group_mrp_user` | Respects workcenter access |
| `_start_timer()` | `sudo()` | System — internal ORM | Productivity creation |
| `action_record_production()` | Current user | `mrp.group_mrp_user` | Records production qty |
| `_record_production()` | Current user | Read on `stock.move`, write on `stock.move.line` | Move line updates |
| `stock.move._action_done()` | `sudo()` | System — internal ORM | Consume components |
| `stock.quant _update_available_quantity()` | `sudo()` | System — internal ORM | No ACL for quant updates |
| `action_finish()` | Current user | `mrp.group_mrp_user` | Complete workorder |
| `_stop_timer()` | `sudo()` | System — internal ORM | Stop productivity log |
| Quality check | Current user | `quality.group_quality_user` | Quality check access |
| Scrap creation | Current user | `mrp.group_mrp_user` | Scrap rights |
| `action_next()` | Current user | `mrp.group_mrp_user` | Advances to next WO |

**Key principle:** Workorder lifecycle methods run as `sudo()` only for internal productivity logging and stock updates. User-facing buttons (`action_start`, `action_record_production`, `action_finish`) require `mrp.group_mrp_user` or higher. Quality checks require `quality` module rights.

---

## Transaction Boundary

> *Which steps are inside the database transaction and which are outside. Critical for understanding atomicity and rollback behavior.*

```
Steps 1-9   ✅ INSIDE transaction  — workorder start atomic
Steps 10-19 ✅ INSIDE transaction  — record production + advance atomic
Steps 20-26 ✅ INSIDE transaction  — finish workorder atomic
No async steps in workorder execution
```

| Step | Boundary | Behavior on Failure |
|------|----------|-------------------|
| Steps 1-9 (action_start) | ✅ Atomic | Rollback on any error — WO state unchanged |
| Steps 10-19 (record_production) | ✅ Atomic | Rollback — no partial qty recorded |
| Steps 20-26 (action_finish) | ✅ Atomic | Rollback — WO remains in progress |
| Productivity log creation | ✅ Atomic | Rolled back with workorder |
| Stock quant updates | ✅ Atomic | Part of same transaction |
| Quality check validation | ✅ Atomic | Rolled back if check fails |

**Rule of thumb:** Workorder execution is fully atomic within a single transaction. Each action (`start`, `record_production`, `finish`) is its own atomic unit. If `action_finish()` fails, the workorder remains in `progress` state with no time logged.

---

## Idempotency

> *What happens when this flow is executed multiple times (double-click, race condition, re-trigger).*

| Scenario | Behavior |
|----------|----------|
| Double-click "Start" button | ORM deduplicates — first `action_start()` succeeds, second is no-op |
| Re-start already started workorder | No-op — WO already in `progress` |
| Re-record production same qty | `qty_produced` re-written — no duplicate consumption |
| Double-click "Finish" button | First `action_finish()` succeeds, second raises `UserError` |
| Re-finish already done workorder | Raises `UserError("Workorder already finished")` |
| Record production twice same qty | First consumes components, second no-ops (qty already done) |
| Finish WO, then re-open | Must cancel and restart — no direct re-open |
| Concurrent action_finish() on same WO | First succeeds, second raises `UserError` — ORM locking |

**Common patterns:**
- **Idempotent:** `action_start()` on `progress` WO is no-op
- **Idempotent:** `action_record_production()` can be called multiple times (cumulative qty)
- **Non-idempotent:** `action_finish()` cannot be undone without cancelling the workorder
- **Deduplication:** Use `with context(tracking_disable=True)` to avoid mail thread noise on double-click

---

## Extension Points

> *Where and how developers can override or extend this flow. Critical for understanding Odoo's inheritance model.*

| Step | Hook Method | Purpose | Arguments | Override Pattern |
|------|-------------|---------|-----------|-----------------|
| Step 2 | `action_start()` | Pre-start logic | self | Extend with `super()` — add validation |
| Step 4 | `_start_timer()` | Custom time tracking | self | Override for custom productivity |
| Step 7 | `_action_assign()` | Custom component reservation | self | Extend for operation-level reserve |
| Step 9 | `_create_quality_check()` | Custom quality check | self | Override for custom QC |
| Step 11 | `_record_production()` | Record production hook | self | Extend with `super()` |
| Step 13 | `_assign_lot()` | Custom lot assignment | self | Override for custom lot logic |
| Step 17 | `action_next()` | Next workorder logic | self | Extend with `super()` |
| Step 20 | `action_finish()` | Pre-finish logic | self | Extend with `super()` |
| Step 23 | `_stop_timer()` | Custom timer stop | self | Override for custom logging |
| Step 25 | `_compute_duration()` | Custom duration calculation | self | Override for custom duration |
| Validation | `_check_*()` | Custom constraint | self | Add `@api.constrains` |

**Standard override pattern:**
```python
# WRONG — replaces entire method
def action_record_production(self):
    # your code only

# CORRECT — extends with super()
def action_record_production(self):
    res = super().action_record_production()
    # your additional code — e.g., notify MES system
    self.production_id.message_post(body="Production recorded at operation")
    return res
```

**Deprecated override points to avoid:**
- `@api.multi` on overridden methods (deprecated in Odoo 19)
- `@api.one` anywhere (deprecated)
- Direct `_workflow` calls (deprecated — use `action_*` methods)
- Overriding without `super()` — breaks core timer and move logic
- `_action_done()` without calling `super()` — moves won't post

---

## Reverse / Undo Flow

> *How to cancel or reverse this flow. Critical for understanding what is and isn't reversible.*

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| `action_start()` | `action_cancel()` | `workorder.action_cancel()` | Cancels WO — timer stopped |
| `action_record_production()` | `action_cancel()` | `workorder.action_cancel()` | Resets WO to `ready` |
| `action_finish()` | `action_cancel()` | `workorder.action_cancel()` | Cancels done WO — production must be un-done |
| Cancel workorder on `done` production | `mrp.unbuild` | `action_unbuild()` | Unbuilds linked production |
| Re-open cancelled WO | `action_draft()` | `workorder.action_draft()` | Only if production still `draft`/`confirmed` |
| Undo finished WO | Unbuild production | `mrp.unbuild` | Components returned, FG consumed |

**Important — partially reversible:**
- Workorder in `progress` → `action_cancel()` resets to `ready` and stops timer
- Workorder in `done` → must cancel the parent production and unbuild
- Recorded production quantities are part of the MO's move lines — reversing the WO does not automatically reverse the MO's move lines
- `mrp.unbuild` is the only way to undo a completed production that consumed components

---

## Alternative Triggers

> *All the ways this flow can be initiated — not just the primary user action.*

| Trigger Type | Method / Endpoint | Context | Frequency |
|-------------|------------------|---------|-----------|
| User action | `action_start()` button | Form view | Manual |
| User action | `action_record_production()` button | Form view | Manual |
| User action | `action_finish()` button | Form view | Manual |
| User action | Tablet view (MES) | Workorder tablet UI | Manual |
| Barcode scanner | Barcode action on workorder | Barcode scan | Manual |
| Workorder auto-advance | `action_next()` | From record_production | Automatic |
| Production auto-close | `action_finish()` on last WO | Last operation complete | Automatic |
| Production start | `action_start()` on first WO | MO action_start | Automatic |
| Cron scheduler | `_cron_mrp_workorder()` | Auto-close stale workorders | Scheduled |
| Quality alert | Quality check pass | Quality system | On event |
| External / API | JSON-RPC on `mrp.workorder` | MES integration | On demand |

**For AI reasoning:** When asked "what happens if X?", trace all triggers — a workorder can be started from the form, from the tablet view, from the production order's action_start, or automatically when the previous workorder is recorded. Each path results in the same workorder state changes.

---

## Related

- [Flows/MRP/production-order-flow](Flows/MRP/production-order-flow.md) — Production order execution
- [Flows/MRP/bom-to-production-flow](Flows/MRP/bom-to-production-flow.md) — BOM to production order creation
- [Modules/MRP](Modules/MRP.md) — MRP module reference
- [Modules/Stock](Modules/Stock.md) — Inventory and materials
- [Modules/Quality](Modules/quality.md) — Quality checks
- [Patterns/Workflow Patterns](Patterns/Workflow Patterns.md) — State machine patterns
- [Core/API](Core/API.md) — @api decorator patterns
