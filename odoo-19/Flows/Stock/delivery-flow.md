---
type: flow
title: "Outgoing Delivery Flow"
primary_model: stock.picking
trigger: "User action — Stock → Operations → Delivery Order"
cross_module: true
models_touched:
  - stock.picking
  - stock.move
  - stock.quant
  - sale.order
  - sale.order.line
  - procurement.group
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[Flows/Sale/sale-to-delivery-flow](Flows/Sale/sale-to-delivery-flow.md)"
  - "[Flows/Stock/picking-action-flow](Flows/Stock/picking-action-flow.md)"
  - "[Flows/Stock/receipt-flow](Flows/Stock/receipt-flow.md)"
related_guides:
  - "[Modules/Stock](Modules/stock.md)"
  - "[Modules/Sale](Modules/sale.md)"
source_module: stock, sale
source_path: ~/odoo/odoo19/odoo/addons/stock/
created: 2026-04-06
updated: 2026-04-06
version: "1.0"
---

# Outgoing Delivery Flow

## Overview

This flow covers the delivery of products from the warehouse to a customer. An outgoing delivery is a `stock.picking` with `picking_type_code = 'outgoing'`. Products are picked from stock locations, reserved quantities are released, and available stock is decremented. The flow proceeds through confirmation, reservation (quants being reserved to prevent overselling), and validation (button "Validate"). If partial delivery occurs, a backorder picking is automatically created. This flow is typically triggered automatically when a Sale Order is confirmed, or manually via **Stock → Operations → Delivery Order**.

## Trigger Point

**Automatic:** `sale.order.action_confirm()` → `procurement_group.run()` → `stock.rule._run()` → `stock.picking.create()` with type `outgoing`.

**Manual:** User navigates to **Stock → Operations → Delivery Order**, selects the stock location as source and the customer location as destination, and creates picking lines manually.

Alternative triggers:
- **Procurement scheduler cron:** `stock.scheduler.compute_stock_rule()` creates pickings for any unfulfilled procurement orders.
- **Make to Order (MTO) route:** Automatic procurement triggers delivery creation when sale order is confirmed with MTO route.
- **Dropship:** `stock.rule` with dropship route creates a delivery directly from supplier to customer.

---

## Complete Method Chain

```
PATH A: Automatic from sale.order.action_confirm()
────────────────────────────────────────────────────────────────

1. sale.order.action_confirm()
   │
   ├─► 2. _action_confirm()
   │     └─► 3. procurement_group_id created / reused
   │           └─► 4. procurement_group.run()
   │                 ├─► 5. stock.rule._run()  [procurement rules evaluated]
   │                 │     └─► 6. stock.picking.create()
   │                 │           ├─► 7. picking_type_id = outgoing delivery type
   │                 │           ├─► 8. location_id = warehouse.lot_stock_id
   │                 │           ├─► 9. location_dest_id = partner.property_stock_customer
   │                 │           ├─► 10. origin = sale.order.name
   │                 │           └─► 11. group_id = procurement_group
   │                 │
   │                 └─► 12. IF picking_policy == 'direct':
   │                       └─► 13. stock.picking.action_assign() called immediately
   │
   └─► 14. sale.order.line.write({'product_uom_qty': ...}) [no state change]

PATH B: Picking confirmation
────────────────────────────────────────────────────────────────

15. stock.picking.action_confirm()   [User clicks "Confirm" or scheduler]
    │
    └─► 16. _action_confirm()
          ├─► 17. stock.move.create() for each sale.order.line
          │     ├─► 18. location_id = stock location (lot_stock)
          │     ├─► 19. location_dest_id = customer location
          │     ├─► 20. product_id, product_uom_qty from sale line
          │     ├─► 21. group_id = procurement_group
          │     └─► 22. state = 'confirmed'
          └─► 23. _assign_picking() — groups moves into this picking
                └─► 24. picking state = 'confirmed'

PATH C: Reservation / availability check
────────────────────────────────────────────────────────────────

25. stock.picking.action_assign()   [User clicks "Check Availability"]
    │
    └─► 26. _action_assign()
          ├─► 27. stock.move._action_assign()
          │     ├─► 28. _do_unreserve() [clear any stale reservation]
          │     ├─► 29. _do_prepare_constrained_moves() [apply constraints]
          │     ├─► 30. stock.quant._update_reserved_quantity(+qty)
          │     │     └─► 31. stock.quant record updated: reserved_qty += qty
          │     │           └─► 32. Quant now has qty allocated to this move
          │     └─► 33. IF qty_available >= product_uom_qty:
          │            └─► 34. move state = 'assigned' → ready
          │           ELSE IF partial available:
          │            └─► 35. move state = 'partially_available'
          │           ELSE:
          │            └─► 36. move state = 'waiting'
          │
          └─► 37. picking state updated:
                ├─► IF all moves 'assigned': picking state = 'assigned' (green)
                ├─► IF some 'partially_available': picking state = 'assigned'
                └─► IF any 'waiting': picking state = 'confirmed' (orange)

PATH D: User registers quantities picked
────────────────────────────────────────────────────────────────

    └─► 38. stock.move.line create/update
          ├─► 39. qty_done set on move lines
          └─► 40. IF lot/serial tracked:
                    └─► lot_id assigned per line — required before done

PATH E: Validation (user clicks "Validate")
────────────────────────────────────────────────────────────────

41. stock.picking.action_done()   [User clicks "Validate"]
    │
    └─► 42. _button_validate()
          ├─► 43. IF immediate_transfer == False:
          │      └─► 44. wizard: `stock.immediate.transfer` shown
          │            └─► 45. re-call action_done() with immediate=True
          │
          └─► 46. _action_done()
                ├─► 47. stock.move.action_done()
                │     └─► 48. _action_done() per move
                │           ├─► 49. qty_done validated vs product_uom_qty
                │           ├─► 50. IF tracked: lot_id verified
                │           ├─► 51. IF partial (qty_done < product_uom_qty):
                │           │      └─► 52. Backorder triggered
                │           │            └─► 53. stock.backorder.create()
                │           │                 └─► 54. new stock.picking (backorder) created
                │           │                       └─► 55. new stock.move created for remaining qty
                │           ├─► 56. stock.quant._update_reserved_quantity(-reserved_qty)
                │           │     └─► 57. reserved_qty released at source location
                │           ├─► 58. stock.quant._update_available_quantity(-qty) at source
                │           │     └─► 59. available qty DECREASED at stock location
                │           ├─► 60. stock.quant._update_available_quantity(+qty) at dest
                │           │     └─► 61. available qty INCREASED at customer/consignment location
                │           └─► 62. move state = 'done'
                │
                └─► 63. picking state = 'done'
                      └─► 64. sale.order.line.write({'qty_delivered': qty})

PATH F: Post-delivery side effects
────────────────────────────────────────────────────────────────

    └─► 65. procurement_group.run()  [check remaining qty — may trigger backorder procurement]
    └─► 66. delivery notification → mail.mail queued (if enabled)
    └─► 67. IF order_policy == 'manual':
           └─► 68. Invoice creation manually triggered by user
    └─► 69. IF order_policy == 'postpaid' AND automatic invoice:
           └─► 70. sale.order._create_invoices() → account.move created
```

---

## Decision Tree

```
sale.picking.action_assign() — availability check
│
├─► Is product qty_available in stock >= product_uom_qty (demand)?
│  ├─► YES (full qty in stock) → move state = 'assigned'
│  │     └─► Picking state = 'assigned' (green "Ready")
│  ├─► PARTIAL (some qty available) → move state = 'partially_available'
│  │     └─► User must adjust qty or force validate
│  └─► NO (zero qty available) → move state = 'waiting'
│        └─► Picking state = 'confirmed' (orange "Waiting")
│             └─► Procurement scheduler may create replenishment
│
└─► ALWAYS after availability check:
   └─► Reserved quants updated — product is now allocated to this move

stock.picking.action_done() — validation decision
│
├─► qty_done == product_uom_qty (all qty picked)?
│  ├─► YES → full delivery, no backorder
│  └─► NO (partial)?
│        ├─► User selected "Create Backorder" → backorder picking created
│        │     └─► Remaining moves move to new picking (backorder_id set)
│        └─► User selected "No Backorder" → remaining qty cancelled
│
├─► Lot/serial tracked?
│  └─► Lot MUST be assigned per line before done
│
└─► Immediate transfer wizard?
   └─► If not immediate: wizard shown → user confirms → proceeds
```

---

## Database State After Completion

| Table | Record Created/Updated | Key Fields |
|-------|----------------------|------------|
| `stock_picking` | Created (path A/B), `state = 'done'` | `picking_type_id = outgoing`, `location_id`, `location_dest_id`, `origin`, `group_id` |
| `stock_move` | Created per sale line, `state = 'done'` | `product_id`, `product_uom_qty`, `quantity_done`, `location_id`, `location_dest_id` |
| `stock_move_line` | Created/updated during `_action_done()` | `qty_done`, `lot_id` (if tracked), `location_id`, `location_dest_id` |
| `stock_quant` | Updated: `reserved_quantity` (step 31), then `quantity` (step 59) | `product_id`, `location_id`, `reserved_quantity`, `quantity` |
| `stock_backorder` | Created if partial delivery | `picking_id`, `backorder_id`, `move_ids` |
| `stock_backorder_picking` | Created as new picking | `picking_type_id`, `origin`, `state = 'confirmed'` |
| `sale_order_line` | Updated: `qty_delivered` written | `qty_delivered` = sum of quantities delivered |
| `procurement_group` | Existing from sale order | Group linking sale → picking → moves |
| `account_move` | Created (if order_policy='postpaid' and auto invoice) | Invoice linked to sale order |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Reason |
|----------|-------------|---------------------|
| No stock available — nothing to reserve | `UserError: "Not enough inventory"` | `_update_reserved_quantity()` returns 0, insufficient quants |
| Product is lot/serial tracked but lot not assigned | `UserError: "You need to supply Lot/Serial number"` | `_action_done()` on stock.move validates tracked products |
| qty_done > product_uom_qty without backorder flag | `UserError: "Done quantity exceeds reserved quantity"` | `_action_done()` enforces qty_done <= product_uom_qty |
| Picking already done or cancelled | `UserError: "Picking is already done"` | Guard in `action_done()` checks `state in ('done', 'cancel')` |
| Access rights — user cannot validate | `AccessError` | `groups` XML attribute on Validate button |
| Location deleted/missing | `ValidationError` | `location.active` check |
| Product type is `service` — not deliverable | `UserError` | `stock.rule` only runs for `type == 'product'` (storable) |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Stock quant reserved | `stock.quant` | `reserved_quantity` incremented at source (stock) location — prevents overselling |
| Stock quant actual decreased | `stock.quant` | `quantity` decremented at source location upon done — qty leaves warehouse |
| Stock quant at destination increased | `stock.quant` | `quantity` incremented at customer/consignment location |
| Lot/serial quantity consumed | `stock.lot` | Lot's `product_quantity` reduced when tracked product is shipped |
| Backorder picking created | `stock.picking` | New picking with `backorder_id` set; state = 'confirmed'; remaining qty |
| Delivered qty updated | `sale.order.line` | `qty_delivered` field written based on moves; triggers delivery completion check |
| Procurement triggered | `procurement.group` | Remaining unfulfilled lines may trigger new procurement |
| Delivery email sent | `mail.mail` | Notification queued to customer (if enabled) |
| Multi-company quant updated | `stock.quant` | `company_id` set on quant; multi-company rules respected |
| Automatic invoice created | `account.move` | If `order_policy == 'postpaid'` and `automatic_invoice`: invoice created |

---

## Security Context

> *Which user context the flow runs under, and what access rights are required at each step.*

| Step | Security Mode | Access Required | Notes |
|------|-------------|----------------|-------|
| `stock.picking.create()` (from procurement) | `sudo()` (system) | System — no ACL | Triggered by `procurement.group.run()` |
| `stock.picking.action_confirm()` | Current user | `group_stock_user` | Button-level security |
| `stock.move.create()` | `sudo()` (system) | System | Framework creates move records |
| `_action_assign()` | `sudo()` (system) | System | Writes to `stock.quant` reserved_quantity |
| `stock.quant._update_reserved_quantity()` | `sudo()` (system) | System | Must update reserved qty across all users |
| `stock.picking.action_done()` | Current user | `group_stock_user` | Validate button |
| `_action_done()` | `sudo()` (system) | System | Updates quant actuals, creates valuation layer |
| `stock.quant._update_available_quantity()` | `sudo()` (system) | System | Decrements stock — must bypass ACL |
| `sale.order.line.write()` | `sudo()` (system) | System | Delivery qty written back to sale line |
| `mail.mail` notification | `mail.group` | Public | Queued via `ir.mail_server` |

**Key principle:** Delivery validation runs in **two modes** — procurement-triggered steps use `sudo()` (system), while user-action steps (`action_confirm`, `action_done`) respect the current user's ACL. The critical security boundary is the Validate button, which enforces `group_stock_user`.

---

## Transaction Boundary

> *Which steps are inside the database transaction and which are outside. Critical for understanding atomicity and rollback behavior.*

```
Steps 1–13   ✅ INSIDE transaction  — procurement + picking creation (from sale.confirm)
Steps 15–24  ✅ INSIDE transaction  — picking confirm + move creation
Steps 25–37  ✅ INSIDE transaction  — reservation (quant reservation is atomic)
Steps 38–40  ✅ INSIDE transaction  — user registers qty (move lines written)
Steps 41–64  ✅ INSIDE transaction  — validation + quant deduction is atomic
Steps 65     ✅ INSIDE transaction  — post-done procurement check
Steps 66     ❌ OUTSIDE transaction — mail.notification queued via ir.mail_server
Steps 68–70  ✅ INSIDE transaction (if postpaid invoice triggered)
```

| Step | Boundary | Behavior on Failure |
|------|----------|-------------------|
| Steps 1–37 | ✅ Atomic | Rollback on any error — quants revert to pre-reservation state |
| `stock.quant._update_reserved_quantity()` | ✅ Atomic | Reserved qty rolled back on error |
| `stock.quant._update_available_quantity()` | ✅ Atomic | Actual qty rolled back on error |
| `mail.mail` notification | ❌ Async queue | Retried by `ir.mail_server` cron if failed |
| Backorder creation (steps 52–55) | ✅ Atomic | Created in same transaction if partial delivery |
| Stock valuation journal entry | ✅ Atomic (if stock_account installed) | Rolled back with picking validation |
| Invoice creation | ✅ Atomic (automatic invoice triggered within same request) | Rolled back with transaction |
| External ERP sync (if configured) | ❌ Outside transaction | Queued via `queue_job` |

**Rule of thumb:** Quant reservation and deduction are always **atomic** — if validation fails, stock levels are fully reverted. Notifications and external integrations are outside the transaction boundary.

---

## Idempotency

> *What happens when this flow is executed multiple times (double-click, race condition, re-trigger).*

| Scenario | Behavior |
|----------|----------|
| Double-click "Validate" button | Second call hits guard: `if self.state == 'done': return True` — no-op |
| Re-trigger `action_done()` on already done picking | No-op — state already 'done', quants already deducted |
| Re-run `action_assign()` on assigned picking | No-op — quants already reserved |
| Run `action_assign()` on partially available picking | Additional reservation attempted — may reserve newly available stock |
| Concurrent validation from two sessions | First write wins; second raises `UserError: "Picking is already done"` |
| Multiple procurement runs for same order line | Procurement checks `if procurement.state != 'exception': skip` |
| Backorder re-processed | Same as initial processing — fully re-run |
| Re-save with same qty values | `write()` re-runs, quants already updated, no further effect |

**Common patterns:**
- **Idempotent:** `action_done()` (state guard), `action_assign()` (skips if already assigned), `write()` with same values
- **Non-idempotent:** `stock.quant._update_available_quantity()` (quantity decremented on each run), `stock.lot` quantity consumed, `ir.sequence` number consumed, stock valuation posted

---

## Extension Points

> *Where and how developers can override or extend this flow. Critical for understanding Odoo's inheritance model.*

| Step | Hook Method | Purpose | Arguments | Override Pattern |
|------|-------------|---------|-----------|-----------------|
| Step 5 | `stock.rule._run()` | Custom procurement routing | `self, procurements` | Override `stock.rule` or `stock.move.rule` |
| Step 6 | `_get_picking_values()` | Customize picking creation vals | `self, group, location, ...` | Extend vals dict before `create()` |
| Step 17 | `_prepare_stock_moves()` | Customize move creation | `self, sale_line` | Return custom vals for `stock.move.create()` |
| Step 29 | `_do_prepare_constrained_moves()` | Apply move constraints | `self` | Override for custom routing logic |
| Step 30 | `_update_reserved_quantity()` | Custom reservation behavior | `self, product_id, qty` | Override quant reservation logic |
| Step 58 | `_update_available_quantity()` | Custom quant deduction | `self, product_id, qty, location` | Override for custom valuation |
| Step 59 | Post-decrement side effect | Post-stock-out logic | `self, location` | Called after qty deducted |
| Step 64 | `_after_move_done()` | Post-delivery side effects | `self` | Called after move state = 'done' |
| Pre-validation | `_check_picking_access()` | Custom validation before done | `self` | Add pre-done checks |
| Backorder | `_create_backorder()` | Control backorder creation | `self, backorder_moves` | Return `False` to skip or customize backorder |

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
- `stock.move._action_done()` is the core move-done logic — override for custom move processing
- `stock.picking._action_assign()` is the reservation logic — override for custom reservation rules
- Backorder creation is controlled by `_create_backorder()` — return `False` to skip
- Procurement rules can be extended via `stock.rule` model's `->_run_pull()` for pull movements

**Deprecated override points to avoid:**
- `@api.multi` on overridden methods (deprecated in Odoo 19)
- `@api.one` anywhere (deprecated)
- Direct `_workflow` calls (deprecated — use `action_*` methods)
- Overriding without calling `super()` — breaks quant tracking

---

## Reverse / Undo Flow

> *How to cancel or reverse this flow. Critical for understanding what is and isn't reversible.*

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| `stock.picking.action_done()` | **Return picking** | `stock.return.picking` wizard | Creates new incoming picking to return goods |
| Return picking validated | Goods returned to stock | Standard incoming picking validation | Stock quants restored at stock location |
| Picking in `confirmed/assigned` | `action_cancel()` | `stock.picking.action_cancel()` | Unreserves quants, cancels moves |
| Picking in `draft` | `action_draft()` | `stock.picking.action_draft()` | Resets to draft; quants remain unchanged |
| `action_cancel()` on picking | `action_draft()` | `stock.picking.action_draft()` | Resets to draft; quants unreserved |
| Partial return | Return only some lines | `stock.return.picking.line` | Only selected lines returned |
| Sale order delivery qty | Update `qty_delivered` | Manual write or new delivery | Must unlink/cancel old moves first |
| Invoice created from delivery | Credit note | `account.move.reversal_entry()` | Reverses posted invoice |

**Important:** This flow is **partially reversible**:
- Delivery `done` → must use **Return Picking** wizard (`stock.return.picking`) — creates a new incoming picking, not a reversal of the original
- Return picking is a separate picking — it moves goods back from customer location to stock location
- The original outgoing picking and its stock moves remain `done` — they represent the historical shipment
- Sale order's `qty_delivered` is not automatically adjusted — the return picking increases the customer's on-hand (consignment stock) but does not change delivered qty
- If `stock_account` is installed: a return creates a counter-journal entry to reverse the valuation

**Return Picking Wizard flow:**
1. User clicks **Return** on a done outgoing picking
2. `stock.return.picking` wizard opens — user selects lines and quantities to return
3. `stock.return.picking` → `create_returns()` called
4. New incoming `stock.picking` created with `origin = original_picking.name`
5. User validates return picking → stock quants increased at return location

---

## Alternative Triggers

> *All the ways this flow can be initiated — not just the primary user action.*

| Trigger Type | Method / Endpoint | Context | Frequency |
|-------------|------------------|---------|-----------|
| Automatic from sale confirmation | `sale.order.action_confirm()` | Sale order UI | Per confirmed SO |
| Procurement scheduler cron | `stock.scheduler.compute_stock_rule()` | Server startup | Configurable (default: daily) |
| Manual picking creation | Stock > Operations > Delivery Order | Stock UI | Manual |
| Immediate transfer wizard | `stock.immediate.transfer` | UI wizard | Manual per picking |
| Scheduled replenishment | `stock.rule._run()` from scheduler | Server | On schedule |
| Dropship | `stock.rule` with dropship route | Sale order | On order confirmation |
| Make to Order (MTO) route | `stock.route.route.mto` | Automatic | Per procurement |
| EDI / API | External system POSTs delivery confirmation | Web service | On demand |

**For AI reasoning:** When asked "what happens if X?", trace all triggers to understand full impact. Delivery can be triggered from the procurement scheduler even without a direct sale order link — useful for inter-warehouse transfers and replenishment flows.

---

## Related

- [Modules/Stock](Modules/stock.md) — Stock/picking module reference
- [Modules/Sale](Modules/sale.md) — Sale module reference
- [Flows/Sale/sale-to-delivery-flow](Flows/Sale/sale-to-delivery-flow.md) — Sale order to delivery (same content, SO-focused)
- [Flows/Stock/picking-action-flow](Flows/Stock/picking-action-flow.md) — Generic picking lifecycle (confirm→assign→done)
- [Flows/Stock/receipt-flow](Flows/Stock/receipt-flow.md) — Incoming receipt counterpart
- [Patterns/Workflow Patterns](odoo-18/Patterns/Workflow Patterns.md) — Workflow pattern reference
- [Core/API](Core/API.md) — @api decorator patterns
