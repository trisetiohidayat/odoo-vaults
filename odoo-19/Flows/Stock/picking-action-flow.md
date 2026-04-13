---
type: flow
title: "Picking Action Flow (confirm → assign → done)"
primary_model: stock.picking
trigger: "User action — Button clicks on picking form"
cross_module: true
models_touched:
  - stock.picking
  - stock.move
  - stock.quant
  - stock.location
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[Flows/Stock/delivery-flow](delivery-flow.md)"
  - "[Flows/Stock/receipt-flow](receipt-flow.md)"
  - "[Flows/Stock/internal-transfer-flow](internal-transfer-flow.md)"
related_guides:
  - "[Modules/Stock](Stock.md)"
source_module: stock
source_path: ~/odoo/odoo19/odoo/addons/stock/
created: 2026-04-06
updated: 2026-04-06
version: "1.0"
---

# Picking Action Flow (confirm → assign → done)

## Overview

This flow describes the generic lifecycle of a `stock.picking` through its three primary action buttons: **Confirm**, **Check Availability**, and **Validate**. These three actions (`action_confirm`, `action_assign`, `action_done`) are the backbone of all stock movement processing in Odoo, regardless of whether the picking is an incoming receipt, outgoing delivery, or internal transfer. Each action advances the picking through the state machine (`draft` → `confirmed` → `assigned` → `done`), with the stock quant table being updated at each stage. This document covers all three paths in detail with their method chains, decision logic, and side effects.

## Trigger Point

**User action:** User clicks one of the three action buttons on a picking form in the Odoo UI:
- **Confirm** (`action_confirm`) — transitions from `draft` to `confirmed`
- **Check Availability** (`action_assign`) — transitions from `confirmed` to `assigned` (or partially available)
- **Validate** (`action_done`) — transitions from `assigned` to `done`

Alternative triggers (system-initiated):
- **Scheduler:** Procurement scheduler may call `action_confirm` and `action_assign` automatically.
- **Procurement:** `procurement_group.run()` creates pickings already in `confirmed` state.
- **Onchange:** Some field changes may trigger availability checks automatically.
- **Wizard:** `stock.immediate.transfer` wizard calls `action_done()` programmatically.

---

## Complete Method Chain

```
ACTION CONFIRM PATH (draft → confirmed)
────────────────────────────────────────────────────────────────

1. stock.picking.action_confirm()   [User clicks "Confirm"]
   │
   └─► 2. _action_confirm()
         ├─► 3. self.mapped('move_ids')._action_confirm()
         │     ├─► 4. move._action_confirm() per stock.move
         │     │     ├─► 5. move._check_company()
         │     │     ├─► 6. IF move.move_orig_ids (chained from another move):
         │     │     │     └─► 7. move.state = 'waiting'
         │     │     │           └─► 8. wait for upstream move to complete
         │     │     └─► 9. ELSE (no dependency):
         │     │           └─► 10. move.state = 'confirmed'
         │     │                 └─► 11. _update_reserve_quantity() [immediate reservation]
         │     │                       └─► 12. IF immediate: quant reserved → state 'assigned'
         │     │
         │     └─► 13. _assign_picking() — groups related moves into picking
         │           └─► 14. _compute_move_ids() [ORM computed field]
         │
         └─► 15. self.write({'state': 'confirmed'})

ACTION ASSIGN PATH (confirmed → assigned)
────────────────────────────────────────────────────────────────

16. stock.picking.action_assign()   [User clicks "Check Availability"]
    │
    └─► 17. _action_assign()
          ├─► 18. self.mapped('move_ids')._action_assign()
          │     ├─► 19. move._action_assign() per stock.move
          │     │     ├─► 20. _check_product() [product exists, active, type valid]
          │     │     ├─► 21. _do_unreserve()
          │     │     │     └─► 22. stock.quant._update_reserved_quantity(-reserved_qty)
          │     │     │           └─► 23. Any previous reservation cleared
          │     │     ├─► 24. _do_prepare_constrained_moves()
          │     │     │     └─► 25. Apply route/constraint logic before reservation
          │     │     ├─► 26. _product_reserve_prepare_dict()
          │     │     │     └─► 27. Build reservation dict: {quant_id: qty_to_reserve}
          │     │     ├─► 28. stock.quant._update_reserved_quantity(+qty) per quant
          │     │     │     └─► 29. stock.quant.reserved_quantity += qty
          │     │     │           └─► 30. Product now allocated to this move
          │     │     └─► 31. IF all demand met:
          │     │           └─► 32. move.state = 'assigned'
          │     │           ELSE IF partial demand met:
          │     │           └─► 33. move.state = 'partially_available'
          │     │           ELSE (no stock):
          │     │           └─► 34. move.state = 'waiting'
          │     │
          │     └─► 35. return {move.id: state} mapping
          │
          └─► 36. Picking state set based on move states:
                ├─► IF all moves 'assigned': picking.state = 'assigned'
                ├─► IF any 'partially_available': picking.state = 'assigned'
                └─► IF any 'waiting': picking.state = 'confirmed'

ACTION DONE PATH (assigned → done)
────────────────────────────────────────────────────────────────

37. stock.picking.action_done()   [User clicks "Validate"]
    │
    └─► 38. _button_validate()
          ├─► 39. IF self.show_transfers:
          │      └─► 40. Return wizard for multi-picking transfer
          │
          ├─► 41. IF immediate_transfer == False (and not immediate param):
          │      └─► 42. wizard: `stock.immediate.transfer` created
          │            └─► 43. user confirms wizard
          │            └─► 44. re-call action_done() with immediate_transfer=True
          │
          └─► 45. _action_done()
                ├─► 46. self.mapped('move_ids_without_package')._action_done()
                │     ├─► 47. move._action_done() per stock.move
                │     │     ├─► 48. _action_done_checks()
                │     │     │     ├─► 49. Validate qty_done > 0
                │     │     │     ├─► 50. IF tracked product: lot_id required
                │     │     │     └─► 51. _check_quantity()
                │     │     ├─► 52. _unreserve() if needed
                │     │     │     └─► 53. stock.quant._update_reserved_quantity(-reserved_qty)
                │     │     │           └─► 54. Reserved qty released before decrementing
                │     │     ├─► 55. _update_reserved_quantity(-reserved_qty) [final unreserve]
                │     │     ├─► 56. _update_available_quantity(-qty, location=location_id)
                │     │     │     └─► 57. stock.quant: available_qty -= qty at SOURCE
                │     │     │           └─► 58. Product leaves source location
                │     │     ├─► 59. _update_available_quantity(+qty, location=location_dest_id)
                │     │     │     └─60. stock.quant: available_qty += qty at DESTINATION
                │     │     │           └─► 61. Product arrives at destination
                │     │     ├─► 62. _create_or complete stock move line
                │     │     │     └─► 63. stock.move.line created/updated with qty_done, lot_id
                │     │     ├─► 64. IF partial done (qty_done < product_uom_qty):
                │     │     │     └─► 65. Backorder triggered
                │     │     │           └─► 66. _create_backorder()
                │     │     │                 └─► 67. stock.backorder record created
                │     │     │                       └─68. stock.picking (backorder) created
                │     │     │                             └─69. stock.move (backorder) created for remaining qty
                │     │     ├─► 70. IF valuation enabled (stock_account):
                │     │     │     └─► 71. stock.valuation.layer.create()
                │     │     │           └─► 72. account.move.line created (Dr/Cr pair)
                │     │     └─► 73. move.state = 'done'
                │     │
                │     └─► 74. _action_done() return: True
                │
                └─► 75. self.write({'state': 'done'})
                      └─► 76. IF origin is sale.order:
                             └─► 77. sale.order.line._update_received_qty()
                                   └─► 78. qty_delivered written on sale lines

POST-DONE SIDE EFFECTS
────────────────────────────────────────────────────────────────

    └─► 79. backorder picking: state = 'confirmed', backorder_id set on parent
    └─► 80. mail.notification → mail.mail queued (if enabled)
    └─► 81. activity scheduled (if configured on picking type)
    └─► 82. procurement_group.run() [may trigger new procurements for backorders]
```

---

## Decision Tree

```
ACTION CONFIRM: action_confirm()
│
├─► Is this picking part of a chain (move_orig_ids)?
│  ├─► YES → move.state = 'waiting' → waits for upstream move
│  └─► NO → move.state = 'confirmed'
│
└─► Picking state = 'confirmed'
   └─► Moves in 'confirmed' or 'waiting' — not yet reserved

ACTION ASSIGN: action_assign()
│
├─► Is product available in SOURCE location?
│  ├─► YES (full qty in stock) → reserved from quants → state = 'assigned'
│  ├─► PARTIAL (some qty available) → partially reserved → state = 'partially_available'
│  └─► NO (zero qty available) → state = 'waiting' → no reservation
│
└─► Picking state:
   ├─► All assigned → 'assigned' (green "Ready")
   ├─► Any partially available → 'assigned' (user can adjust)
   └─► Any waiting → 'confirmed' (orange "Waiting")

ACTION DONE: action_done()
│
├─► Is qty_done set on all move lines?
│  └─► NO (zero qty) → error: must register quantities
│
├─► Is product lot/serial tracked?
│  └─► YES → lot_id MUST be assigned on each move line
│
├─► qty_done == product_uom_qty (full)?
│  ├─► YES → full done, no backorder
│  └─► NO (partial)?
│        ├─► User selected "Create Backorder" → backorder for remainder
│        └─► User selected "No Backorder" → remainder cancelled
│
└─► Picking state = 'done'
   └─► Quants: source decreased, destination increased
```

---

## Database State After Completion

| Table | Record Created/Updated | Key Fields |
|-------|----------------------|------------|
| `stock_picking` | `state` transitions: draft → confirmed → assigned → done | `state`, `location_id`, `location_dest_id` |
| `stock_move` | `state` transitions per move | `state` ('confirmed'/'assigned'/'done'), `quantity_done`, `product_uom_qty` |
| `stock_move_line` | Created/updated during done | `qty_done`, `lot_id` (if tracked), `location_id`, `location_dest_id` |
| `stock_quant` | Updated at each action: reserve → unreserve → deduct/increment | `quantity`, `reserved_quantity` at source and destination locations |
| `stock_backorder` | Created if partial done | `picking_id`, `backorder_id` |
| `stock_backorder_picking` | Created if partial | New picking with remaining moves |
| `stock_valuation_layer` | Created per move (if valuation enabled) | `unit_cost`, `quantity`, `value` |
| `account_move_line` | Created (if stock_account installed) | Paired Dr/Cr entries for valuation |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Reason |
|----------|-------------|---------------------|
| Click Confirm on already confirmed picking | `UserError: "Picking is already done"` | Guard: `if self.state != 'draft'` |
| Click Assign on picking with no stock | `UserError: "Not enough inventory"` | `_update_reserved_quantity()` returns 0 — no available quants |
| Click Validate with qty_done = 0 | `UserError: "You have not processed any quantity"` | `_action_done_checks()` requires qty_done > 0 |
| Lot tracked product without lot assigned | `UserError: "You need to supply Lot/Serial number"` | `_action_done_checks()` validates lot_id for tracked products |
| qty_done > product_uom_qty (no backorder selected) | `UserError: "Done quantity exceeds reserved"` | `_action_done()` checks qty limits |
| Click Validate on already done picking | `UserError: "Picking is already done"` | Guard: `if self.state == 'done'` |
| Access rights — user cannot validate | `AccessError` | `groups` XML attribute on Validate button |
| Source location inactive | `ValidationError` | `location.active` check in `_action_done()` |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Stock quant reserved | `stock.quant` | `reserved_quantity` incremented at source (action_assign) |
| Stock quant unreserved | `stock.quant` | `reserved_quantity` decremented (action_done) |
| Stock quant at source decremented | `stock.quant` | `quantity` decreased at source location |
| Stock quant at destination incremented | `stock.quant` | `quantity` increased at destination location |
| Lot/serial reserved and consumed | `stock.lot` | Lot quantity reserved then consumed when done |
| Backorder picking created | `stock.picking` | New picking for remaining qty; state = 'confirmed' |
| Valuation layer created | `stock.valuation.layer` | Records cost and quantity for valuation |
| Journal entry posted | `account.move.line` | If `stock_account` installed — inventory value moved |
| Sale order qty_delivered updated | `sale.order.line` | When done picking linked to sale order |
| Mail notification queued | `mail.mail` | Sent to followers (outside transaction) |

---

## Security Context

> *Which user context the flow runs under, and what access rights are required at each step.*

| Step | Security Mode | Access Required | Notes |
|------|-------------|----------------|-------|
| `action_confirm()` | Current user | `group_stock_user` | Button-level security |
| `_action_confirm()` | `sudo()` (system) | System | Creates/links moves |
| `action_assign()` | Current user | `group_stock_user` | Check availability button |
| `_do_unreserve()` | `sudo()` (system) | System | Clears reservations across all users |
| `stock.quant._update_reserved_quantity()` | `sudo()` (system) | System | Writes to reserved_quantity |
| `action_done()` | Current user | `group_stock_user` | Validate button |
| `_action_done()` | `sudo()` (system) | System | Updates quants — must bypass ACL |
| `_update_available_quantity()` | `sudo()` (system) | System | Decrements source, increments dest |
| `stock.valuation.layer.create()` | `sudo()` (system) | System | Valuation record |
| `mail.mail` notification | `mail.group` | Public | Queued outside transaction |

**Key principle:** All three action buttons run under the **current user's ACL** — a user must have `group_stock_user` to confirm, assign, or validate pickings. However, the underlying quant update methods (`_update_available_quantity`, `_update_reserved_quantity`, `_create_valuation_layer`) all run under `sudo()` (system) because they must write to records across all users and companies.

---

## Transaction Boundary

> *Which steps are inside the database transaction and which are outside. Critical for understanding atomicity and rollback behavior.*

```
Steps 1–15   ✅ INSIDE transaction  — action_confirm (draft → confirmed)
Steps 16–36  ✅ INSIDE transaction  — action_assign (confirmed → assigned/reserved)
Steps 37–78  ✅ INSIDE transaction  — action_done (assigned → done + quant updates)
Step 79      ✅ INSIDE transaction  — backorder creation
Step 80      ❌ OUTSIDE transaction — mail notification queued
Step 82      ✅ INSIDE transaction  — procurement check
```

| Step | Boundary | Behavior on Failure |
|------|----------|-------------------|
| Steps 1–36 | ✅ Atomic | Can be re-run safely — confirmation and reservation are idempotent |
| Steps 37–78 | ✅ Atomic | All-or-nothing: if any move fails, no quants are updated |
| `stock.quant._update_available_quantity()` | ✅ Atomic | Rolled back on error |
| `stock.quant._update_reserved_quantity()` | ✅ Atomic | Reserved qty reverted |
| Backorder creation (steps 66–69) | ✅ Atomic | Created in same transaction |
| `stock.valuation.layer` | ✅ Atomic | Rolled back with picking |
| `account.move.line` | ✅ Atomic (stock_account) | Rolled back with picking |
| `mail.mail` notification | ❌ Async queue | Retried by `ir.mail_server` cron |
| `procurement_group.run()` | ✅ Atomic | Runs within same transaction |

**Rule of thumb:** The entire Validate action (`_action_done()`) is atomic — if any move fails validation (e.g., missing lot on a tracked product), the entire operation rolls back and no quants are updated. The state machine ensures each action can be re-run safely.

---

## Idempotency

> *What happens when this flow is executed multiple times (double-click, race condition, re-trigger).*

| Scenario | Behavior |
|----------|----------|
| Double-click "Confirm" button | Second call: `if self.state != 'draft': return True` — no-op |
| Double-click "Check Availability" | `_do_unreserve()` runs first (idempotent) → then re-reserves — may re-reserve from different quants |
| Double-click "Validate" button | Second call: `if self.state == 'done': return True` — no-op |
| Re-trigger `action_done()` on done picking | No-op — state guard prevents re-execution |
| Re-run `action_assign()` on assigned picking | `_do_unreserve()` clears, then re-reserves — may re-reserve from different lots/quants |
| Run `action_assign()` on partially available picking | Additional reservation attempted — can reserve newly available stock |
| Concurrent calls to `action_done()` on same picking | First write wins; second raises `UserError: "Picking is already done"` |
| Re-confirm a waiting picking (after source arrived) | `action_confirm()` re-runs, may advance to 'assigned' |

**Common patterns:**
- **Idempotent:** `action_confirm()` (draft-state guard), `action_done()` (done-state guard), `_do_unreserve()` (clears nothing if already unreserved)
- **Non-idempotent:** `_update_available_quantity()` (quant changes each time — double-validate = double-count), `stock.valuation.layer.create()` (new layer per move per run)

---

## Extension Points

> *Where and how developers can override or extend this flow. Critical for understanding Odoo's inheritance model.*

| Step | Hook Method | Purpose | Arguments | Override Pattern |
|------|-------------|---------|-----------|-----------------|
| Step 3 | `_action_confirm()` | Extend confirm logic | `self` | Add logic before/after move confirmation |
| Step 11 | `_update_reserve_quantity()` | Immediate reservation on confirm | `self` | Override for custom immediate reservation |
| Step 19 | `_action_assign()` | Extend availability check | `self` | Add pre/post reservation logic |
| Step 21 | `_do_unreserve()` | Custom unreservation logic | `self` | Override to skip certain quants |
| Step 28 | `_update_reserved_quantity()` | Custom reservation behavior | `self, product_id, qty` | Override for custom source selection |
| Step 47 | `_action_done()` | Core done logic — HIGHEST VALUE override | `self` | Override for custom move processing |
| Step 49 | `_action_done_checks()` | Pre-done validation | `self` | Add custom validation before done |
| Step 57 | `_update_available_quantity(-)` | Custom source decrement | `self, product_id, qty, location` | Override for custom deduction |
| Step 60 | `_update_available_quantity(+)` | Custom dest increment | `self, product_id, qty, location` | Override for custom increment |
| Step 71 | `_create_valuation_layer()` | Custom valuation | `self, move` | Extend for landed cost integration |
| Step 66 | `_create_backorder()` | Control backorder creation | `self, backorder_moves` | Return `False` to skip backorder |
| Step 76 | Post-done origin-specific logic | Sale/PO/Manufacturing link | `self` | Extend for manufacturing/order updates |

**Standard override pattern:**
```python
# WRONG — replaces entire method
def action_done(self):
    # your code

# CORRECT — extends with super()
def action_done(self):
    res = super().action_done()
    # your additional code
    return res
```

**Odoo 19 specific hooks:**
- `stock.move._action_done()` is the primary override point for customizing what happens when a move is validated
- `stock.picking._action_assign()` controls the reservation logic
- `stock.picking._action_confirm()` is the confirm hook
- Backorder creation is controlled by `_create_backorder()` — return `False` to skip
- `stock.move._action_done_checks()` for pre-validation custom checks

**Deprecated override points to avoid:**
- `@api.multi` on overridden methods (deprecated in Odoo 19)
- `@api.one` anywhere (deprecated)
- Direct `_workflow` calls (deprecated — use `action_*` methods)
- Overriding without calling `super()` — breaks quant tracking and state machine

---

## Reverse / Undo Flow

> *How to cancel or reverse this flow. Critical for understanding what is and isn't reversible.*

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| `action_confirm()` | `action_draft()` or `action_cancel()` | `stock.picking.action_draft()` | Resets to draft; no quant changes yet |
| `action_assign()` | `action_unassign()` | `stock.picking.action_unassign()` | Unreserves quants; picking back to 'confirmed' |
| `action_done()` | **Return picking** | `stock.return.picking` wizard | Creates new picking in opposite direction |
| Picking in `draft` | `action_draft()` or `action_cancel()` | `stock.picking.action_draft()` | No effect |
| Picking in `confirmed` | `action_cancel()` | `stock.picking.action_cancel()` | Cancels moves; no quant changes |
| Picking in `assigned` | `action_unassign()` → `action_cancel()` | `stock.picking.action_unassign()` | Unreserves, then cancels |
| Picking in `done` | **Cannot directly cancel** | Must use return flow | Odoo immutability for done pickings |
| Backorder picking | `action_cancel()` | Standard cancel | Cancels remaining qty |

**Important:** Done pickings are **immutable** in Odoo's state machine — they cannot be reverted directly. To reverse:
1. Create a **Return Picking** (`stock.return.picking`) from the done picking
2. The wizard creates a new picking in the opposite direction (incoming if original was outgoing)
3. Validate the return picking to restore stock

**Return Picking Wizard flow (applies to all picking types):**
1. User clicks **Return** on any done picking
2. `stock.return.picking` wizard opens — user selects lines and quantities
3. `create_returns()` called → new picking created with `origin = original.name`
4. New picking validated → quants restored/decreased at return location

---

## Alternative Triggers

> *All the ways these actions can be triggered — not just user button clicks.*

| Trigger Type | Method / Endpoint | Context | Frequency |
|-------------|------------------|---------|-----------|
| User click — Confirm | `action_confirm()` | Picking form button | Manual per picking |
| User click — Check Availability | `action_assign()` | Picking form button | Manual per picking |
| User click — Validate | `action_done()` | Picking form button | Manual per picking |
| Immediate transfer wizard | `stock.immediate.transfer` | UI wizard → calls `action_done()` | Manual per picking |
| Return picking wizard | `stock.return.picking` → `create_returns()` | UI wizard → creates new picking | Manual |
| Procurement scheduler | `stock.scheduler.compute_stock_rule()` | Server cron | Configurable |
| `procurement_group.run()` | Creates pickings in `confirmed` state | Automatic | On sale/purchase confirm |
| Chain-triggered | `move_orig_ids` dependency resolved | Automatic | When upstream move done |
| API / external | `stock.picking` JSON-RPC endpoint | Web service | On demand |

**For AI reasoning:** All three action methods are public entry points on `stock.picking` and `stock.move`. They are the standard integration points for any automation or API work. The underlying `_action_confirm`, `_action_assign`, and `_action_done` methods on `stock.move` are the hooks for customization.

---

## Related

- [Modules/Stock](Stock.md) — Stock/picking module reference
- [Flows/Stock/delivery-flow](delivery-flow.md) — Outgoing delivery (applies this action flow)
- [Flows/Stock/receipt-flow](receipt-flow.md) — Incoming receipt (applies this action flow)
- [Flows/Stock/internal-transfer-flow](internal-transfer-flow.md) — Internal transfer (applies this action flow)
- [Patterns/Workflow Patterns](Workflow Patterns.md) — Workflow pattern reference
- [Core/API](API.md) — @api decorator patterns
