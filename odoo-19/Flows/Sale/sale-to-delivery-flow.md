---
type: flow
title: "Sale Order to Delivery Flow"
primary_model: stock.picking
trigger: "Automatic — triggered from sale.order.action_confirm() OR Manual — Stock > Transfers > Create"
cross_module: true
models_touched:
  - stock.picking
  - stock.move
  - stock.quant
  - procurement.group
  - sale.order
  - sale.order.line
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[Flows/Sale/quotation-to-sale-order-flow](odoo-19/Flows/Sale/quotation-to-sale-order-flow.md)"
  - "[Flows/Sale/sale-to-invoice-flow](odoo-19/Flows/Sale/sale-to-invoice-flow.md)"
related_guides:
  - "[Modules/Sale](odoo-18/Modules/sale.md)"
  - "[Modules/Stock](odoo-18/Modules/stock.md)"
source_module: sale, stock
source_path: ~/odoo/odoo19/odoo/addons/stock/
created: 2026-04-06
updated: 2026-04-06
version: "1.0"
---

# Sale Order to Delivery Flow

## Overview

This flow covers the creation and validation of a delivery picking (stock.picking with `picking_type_code = 'outgoing'`) originating from a confirmed sale order. Odoo creates a procurement group when the sale order is confirmed, which triggers the generation of delivery pickings and their associated stock moves. The flow proceeds through reservation (stock quants being reserved), validation (button "Validate" / `action_done()`), and updates to actual stock quantities. If partial delivery occurs, a backorder picking is automatically generated.

## Trigger Point

**Automatic:** `sale.order.action_confirm()` → `procurement_group.run()` → `stock.picking.create()` — triggered when a quotation is confirmed (picking policy governs timing).

**Manual:** User navigates to **Stock > Transfers > Create** and manually creates a delivery picking, optionally linking it to a sale order via the `origin` field.

Alternative triggers:
- **Procurement scheduler cron:** `stock.scheduler.compute_stock_rule()` runs periodically and creates pickings for any unfulfilled procurement orders.
- **Replenishment:** From a product's **Replenish** button or the **Stock Replenishment** report.

---

## Complete Method Chain

```
PATH A: Automatic from sale.order.action_confirm()
────────────────────────────────────────────────────

1. sale.order.action_confirm()
   │
   ├─► 2. _action_confirm()
   │     └─► 3. procurement_group_id created
   │           └─► 4. procurement_group.run()
   │                 └─► 5. stock.rule._run()  [procurement rules evaluated]
   │                       └─► 6. stock.picking.create()
   │                             ├─► picking_type_id resolved (outgoing/dropship)
   │                             ├─► location_id = warehouse.lot_stock_id
   │                             ├─► location_dest_id = partner.property_stock_customer
   │                             ├─► origin = sale.order.name
   │                             └─► group_id = procurement_group
   │
   └─► 7. IF picking_policy == 'direct':
          └─► 8. stock.picking.action_assign() called immediately
                └─► 9. reservation occurs → stock.quant updated

PATH B: Picking confirmation (automatic or manual trigger)
────────────────────────────────────────────────────────

10. stock.picking.action_confirm()   [called by user or scheduler]
    │
    └─► 11. _action_confirm()
          └─► 12. stock.move.create() for each sale.order.line
                ├─► location_id = stock location (lot_stock)
                ├─► location_dest_id = customer location
                ├─► product_id, product_uom_qty from sale line
                ├─► group_id = procurement_group
                └─► state = 'confirmed' initially
          └─► 13. _assign_picking() — groups moves into this picking
                └─► 14. _compute_move_ids() [ORM computed field]

PATH C: Reservation (user-initiated or auto)
────────────────────────────────────────────

15. stock.picking.action_assign()   [User clicks "Check Availability"]
    │
    └─► 16. _action_assign()
          ├─► 17. stock.move._action_assign()
          │     ├─► 18. stock.move._do_unreserve() [clear any stale reservation]
          │     ├─► 19. stock.move._do_prepare_constrained_moves()
          │     ├─► 20. stock.quant._update_reserved_quantity()
          │     │     └─► 21. stock.quant record updated: reserved_qty += qty
          │     └─► 22. IF insufficient quants:
          │            └─► 23. move state = 'partially_available' or 'waiting'
          │
          └─► 24. picking state updated to 'assigned' (all moves reservable)
                └─► 25. Picking ready for user validation

PATH D: Validation (user clicks "Validate")
────────────────────────────────────────────

26. stock.picking.action_done()   [User clicks "Validate" / "Register Move"]
    │
    └─► 27. _button_validate()   [wizard handler]
          ├─► 28. IF immediate_transfer == False:
          │      └─► 29. wizard: `stock.immediate.transfer` prompts confirmation
          │            └─► 30. re-call `action_done()` with immediate=True
          │
          └─► 31. _action_done()   [core done logic]
                ├─► 32. stock.move.action_done()
                │     └─► 33. _action_done() on each stock.move
                │           ├─► 34. stock.move.line create/update (quantity done)
                │           ├─ 35. product_uom_qty confirmed vs reserved
                │           ├─ 36. IF qty_done < product_uom_qty:
                │           │      └─► backorder triggered → stock.backorder.create()
                │           │           └─► stock.picking (backorder) created
                │           │                 └─► stock.move (backorder moves) created
                │           ├─ 37. stock.quant._update_available_quantity()
                │           │     └─► stock.quant updated: available_qty -= qty
                │           │           └─► outgoing quant deducted at source location
                │           ├─ 38. stock.quant create (if new lot/serial)
                │           └─ 39. move state = 'done'
                │
                └─► 40. picking state = 'done'
                      └─► 41. sale.order.line write({'qty_delivered': qty})

PATH E: Post-done side effects
───────────────────────────────

    └─► 42. procurement_group.run()  [check if any remaining qty to procure]
    └─► 43. delivery notification → mail.mail queued
    └─► 44. IF order_policy == 'postpaid':
           └─► 45. sale.order._create_invoices() triggered
                 └─► account.move (out_invoice) created
```

---

## Decision Tree

```
sale.picking.action_assign() — availability check
│
├─► All product qty available in stock?
│  ├─► YES (full qty in stock) → state = 'assigned' → ready to validate
│  ├─► PARTIAL (some qty available) → state = 'partially_available'
│  │     └─► User must manually adjust qty or force validate
│  └─► NO (zero qty available) → state = 'waiting'
│        └─► Procurement scheduler will create replenishment
│
└─► ALWAYS after availability check:
   └─► Picking shows "Ready" (green) if assigned, "Waiting" (orange) if not

stock.picking.action_done() — validation decision
│
├─► Full qty validated by user?
│  ├─► YES → state = 'done', no backorder
│  └─► PARTIAL (qty_done < reserved qty)?
│        ├─► User selected "Create Backorder" → backorder picking created
│        └─► User selected "No Backorder" → remaining qty cancelled
│
├─► Serial number validation?
│  └─► Lot/serial tracked products: qty_done must match number of serials scanned
│
└─► Immediate transfer wizard?
   └─► If not immediate: wizard shown → user confirms → proceeds with action_done
```

---

## Database State After Completion

| Table | Record Created/Updated | Key Fields |
|-------|----------------------|------------|
| `stock_picking` | Created (path A/B), then `state = 'done'` | `picking_type_id`, `location_id`, `location_dest_id`, `origin`, `group_id` |
| `stock_move` | Created per sale line, `state = 'done'` | `product_id`, `product_uom_qty`, `quantity_done`, `location_id`, `location_dest_id` |
| `stock_move_line` | Created/updated during `_action_done()` | `qty_done`, `lot_id` (if tracked), `location_id`, `location_dest_id` |
| `stock_quant` | Updated: `reserved_quantity` (step 21), `quantity` (step 37) | `product_id`, `location_id`, `reserved_quantity`, `quantity` |
| `stock_backorder` | Created if partial delivery | `picking_id`, `backorder_id`, `move_ids` |
| `sale_order_line` | Updated: `qty_delivered` written | `qty_delivered` = sum of move quantities |
| `procurement_group` | Existing from sale order | Group linking sale → picking → moves |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Reason |
|----------|-------------|---------------------|
| No stock available and no replenishment rule | `UserError: "Not enough inventory"` | `_update_reserved_quantity()` returns 0 |
| Product is tracked (lot/serial) but no lot selected | `UserError: "You need to supply Lot/Serial number"` | `stock.move._action_done()` validates lot for tracked products |
| Quantity done exceeds reserved qty (untracked) | `UserError: "Done qty exceeds reserved qty"` | `_action_done()` checks `qty_done > product_uom_qty` without backorder flag |
| Picking already done/cancelled | `UserError: "Picking is already done"` | Guard in `action_done()` checks `if self.state in ('done', 'cancel')` |
| Access rights — user cannot validate | `AccessError` | `groups` XML attribute on `action_done` button |
| Location deleted/missing | `ValidationError` | Foreign key constraint or location active check |
| Product type is `service` — not deliverable | `UserError: "Product type is not storable"` | `stock.rule` only runs for `type == 'product'` (storable) |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Stock quant reserved | `stock.quant` | `reserved_quantity` incremented at source location; prevents overselling |
| Stock quant decremented | `stock.quant` | `quantity` decremented at source location upon done |
| Lot/serial consumed | `stock.lot` | If product is lot-tracked, lot quantity reduced |
| Backorder created | `stock.picking` | New picking with `backorder_id` set; state = 'confirmed' |
| Delivered qty updated | `sale.order.line` | `qty_delivered` field written based on moves |
| Procurement triggered | `procurement.group` | Remaining unfulfilled lines trigger new procurement |
| Delivery email sent | `mail.mail` | Notification queued to customer (if `stock.mail_notification` enabled) |
| Update multi-company quant | `stock.quant` | `company_id` set on quant; multi-company rules respected |
| Automatic stock valuation entry | `account.move.line` | If `stock_account` installed: valuation journal entry created |

---

## Security Context

> *Which user context the flow runs under, and what access rights are required at each step.*

| Step | Security Mode | Access Required | Notes |
|------|-------------|----------------|-------|
| `stock.picking.create()` (from procurement) | `sudo()` (system) | System — no ACL | Triggered by `procurement.group.run()` |
| `stock.picking.action_confirm()` | Current user | `group_stock_user` | Button-level security |
| `stock.move.create()` | `sudo()` (system) | System — no ACL | Framework creates move records |
| `_action_assign()` | `sudo()` (system) | System — writes to `stock.quant` | Needs to update reserved quantities |
| `stock.quant._update_reserved_quantity()` | `sudo()` (system) | System | Must write to quants across all users |
| `stock.picking.action_done()` | Current user | `group_stock_user` | Button-level security |
| `_action_done()` | `sudo()` (system) | System | Updates quant actuals |
| `sale.order.line write()` | `sudo()` (system) | System | Delivery qty written back to sale line |
| `mail.mail` notification | `mail.group` | Public | Queued via `ir.mail_server` |

**Key principle:** Picking validation runs in **two modes** — procurement-triggered steps use `sudo()` (system), while user-action steps (`action_confirm`, `action_done`) respect the current user's ACL. This is critical for audit trails.

---

## Transaction Boundary

> *Which steps are inside the database transaction and which are outside. Critical for understanding atomicity and rollback behavior.*

```
Steps 1–9    ✅ INSIDE transaction  — procurement + picking creation (from sale.confirm)
Steps 10–14 ✅ INSIDE transaction  — picking confirm + move creation
Steps 15–25 ✅ INSIDE transaction  — reservation (quant reservation is atomic)
Steps 26–41 ✅ INSIDE transaction  — validation (quant deduction is atomic)
Step 42     ✅ INSIDE transaction  — post-done procurement check
Steps 43    ❌ OUTSIDE transaction — mail.notification queued via ir.mail_server
Step 45     ✅ INSIDE transaction (if postpaid invoice triggered)
```

| Step | Boundary | Behavior on Failure |
|------|----------|-------------------|
| Steps 1–42 | ✅ Atomic | Rollback on any error — quants revert to pre-reservation state |
| `stock.quant._update_reserved_quantity()` | ✅ Atomic | Reserved qty rolled back on error |
| `stock.quant._update_available_quantity()` | ✅ Atomic | Actual qty rolled back on error |
| `mail.mail` notification | ❌ Async queue | Retried by `ir.mail_server` cron if failed |
| Backorder creation | ✅ Atomic | Created in same transaction if partial delivery |
| Stock valuation journal entry | ✅ Atomic (if stock_account installed) | Rolled back with picking validation |
| External ERP sync (if configured) | ❌ Outside transaction | Queued via `queue_job` |

**Rule of thumb:** Quant reservation and deduction are always **atomic** — if validation fails, stock levels are fully reverted. Notifications and external integrations are outside the transaction.

---

## Idempotency

> *What happens when this flow is executed multiple times (double-click, race condition, re-trigger).*

| Scenario | Behavior |
|----------|----------|
| Double-click "Validate" button | Second call hits guard: `if self.state == 'done': return True` — no-op |
| Re-trigger `action_done()` on already done picking | No-op — state already 'done' |
| Re-run `action_assign()` on assigned picking | No-op — quants already reserved |
| Run `action_assign()` on partially available picking | Additional reservation attempted; may reserve newly available stock |
| Concurrent validation from two sessions | First write wins; second raises `UserError: "Picking is already done"` |
| Multiple procurement runs for same order line | Procurement checks `if procurement.state != 'exception': skip` |
| Backorder re-processed | Same as initial processing — fully re-run |

**Common patterns:**
- **Idempotent:** `action_done()` (state guard), `action_assign()` (skips if already assigned), `write()` with same values
- **Non-idempotent:** `stock.quant._update_available_quantity()` (quantity decremented), `stock.lot` quantity consumed, `ir.sequence` number consumed

---

## Extension Points

> *Where and how developers can override or extend this flow. Critical for understanding Odoo's inheritance model.*

| Step | Hook Method | Purpose | Arguments | Override Pattern |
|------|-------------|---------|-----------|-----------------|
| Step 5 | `stock.rule._run()` | Custom procurement routing | `self, procurements` | Override `stock.rule` or `stock.move.rule` |
| Step 6 | `_get_picking_values()` | Customize picking creation vals | `self, group, location, ...` | Extend vals dict before `create()` |
| Step 12 | `_prepare_stock_moves()` | Customize move creation | `self, sale_line` | Return custom vals for `stock.move.create()` |
| Step 19 | `_do_prepare_constrained_moves()` | Apply move constraints | `self` | Override for custom routing logic |
| Step 20 | `_update_reserved_quantity()` | Custom reservation behavior | `self, product_id, qty` | Override quant reservation logic |
| Step 37 | `_update_available_quantity()` | Custom quant deduction | `self, product_id, qty, location` | Override for custom valuation |
| Post-move done | `_after_move_done()` | Post-delivery side effects | `self` | Called after move state = 'done' |
| Pre-validation | `_check_picking_access()` | Custom validation before done | `self` | Add pre-done checks |
| Backorder | `_create_backorder()` | Control backorder creation | `self, backorder_moves` | Override to skip or customize backorder |

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
- Direct `_workflow` calls (deprecated)
- Overriding without calling `super()` — breaks quant tracking

---

## Reverse / Undo Flow

> *How to cancel or reverse this flow. Critical for understanding what is and isn't reversible.*

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| `stock.picking.action_done()` | **Return picking** | `stock.return.picking` wizard | Creates new incoming picking to return goods |
| Return picking validated | **Receive back** | Standard `stock.picking` validation | Goods returned to stock location |
| Picking in `done` state | **Cannot cancel directly** | Must use return flow | Odoo enforces immutability of done pickings |
| Picking in `draft/confirmed/assigned` | `action_cancel()` | `stock.picking.action_cancel()` | Unreserves quants, cancels moves |
| `action_cancel()` on picking | `action_draft()` | `stock.picking.action_draft()` | Resets to draft; quants remain unreserved |
| Partial return | Return only some lines | `stock.return.picking.line` | Only selected lines returned |
| Sale order delivery qty | Update `qty_delivered` | Manual write or `action_done` re-run | Must unlink/cancel old moves first |

**Important:** This flow is **partially reversible**:
- Picking `done` → must use **Return Picking** wizard (`stock.return.picking`) — this creates a new incoming picking, not a reversal of the original
- Return picking is a separate picking — it moves goods back from customer to stock
- The original outgoing picking and its stock moves remain `done` — they represent the historical shipment
- If `stock_account` is installed: a return creates a counter-journal entry to reverse the valuation

**Return Picking Wizard flow:**
1. User clicks **Return** on a done picking
2. `stock.return.picking` wizard opens — user selects lines and quantities to return
3. `stock.return.picking` → `create_returns()` called
4. New incoming `stock.picking` created with `origin = original_picking.name`
5. User validates the return picking → stock quants increased at return location

---

## Alternative Triggers

> *All the ways this flow can be initiated — not just the primary user action.*

| Trigger Type | Method / Endpoint | Context | Frequency |
|-------------|------------------|---------|-----------|
| Automatic from sale confirmation | `sale.order.action_confirm()` → procurement | Sale order UI | Manual (per order) |
| Procurement scheduler cron | `stock.scheduler.compute_stock_rule()` | Server startup | Configurable (default: daily) |
| Manual picking creation | Stock > Transfers > Create | Stock UI | Manual |
| Immediate transfer wizard | `stock.immediate.transfer` | UI wizard | Manual per picking |
| Scheduled replenishment | `stock.rule._run()` from scheduler | Server | On schedule |
| Dropship | `stock.rule` with `action_pull制造业` (dropship route) | Sale order | On order confirmation |
| Make to Order (MTO) route | `stock.route.route.mto` | Automatic | Per procurement |
| EDI / API | External system POSTs to delivery confirmation | Web service | On demand |

**For AI reasoning:** When asked "what happens if X?", trace all triggers to understand full impact. Delivery can be triggered from procurement scheduler even without a direct sale order link — useful for inter-warehouse transfers.

---

## Related

- [Modules/Sale](odoo-18/Modules/sale.md) — Sale module reference
- [Modules/Stock](odoo-18/Modules/stock.md) — Stock/picking module reference
- [Flows/Sale/quotation-to-sale-order-flow](odoo-19/Flows/Sale/quotation-to-sale-order-flow.md) — Sale order confirmation that triggers delivery
- [Flows/Sale/sale-to-invoice-flow](odoo-19/Flows/Sale/sale-to-invoice-flow.md) — Invoice creation (especially postpaid) after delivery
- [Patterns/Workflow Patterns](odoo-18/Patterns/Workflow Patterns.md) — Workflow pattern reference
- [Core/API](odoo-18/Core/API.md) — @api decorator patterns
