---
type: flow
title: "Incoming Receipt Flow"
primary_model: stock.picking
trigger: "User action — Stock → Operations → Receipt (or from PO)"
cross_module: true
models_touched:
  - stock.picking
  - stock.move
  - stock.quant
  - stock.location
  - account.move
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[Flows/Stock/delivery-flow](delivery-flow.md)"
  - "[Flows/Purchase/purchase-order-receipt-flow](purchase-order-receipt-flow.md)"
  - "[Flows/Stock/stock-valuation-flow](stock-valuation-flow.md)"
related_guides:
  - "[Modules/Stock](Stock.md)"
  - "[Modules/Purchase](Purchase.md)"
source_module: stock, purchase
source_path: ~/odoo/odoo19/odoo/addons/stock/
created: 2026-04-06
updated: 2026-04-06
version: "1.0"
---

# Incoming Receipt Flow

## Overview

This flow covers the receipt of products from a vendor into the warehouse. An incoming receipt is a `stock.picking` with `picking_type_code = 'incoming'`. Products are received at the stock location (or an input/stocking location in multi-step flows), stock quants are updated to reflect new on-hand quantities, and if the `stock_account` module is installed, valuation journal entries are created. This flow is typically triggered automatically when a Purchase Order is confirmed, or manually by a user via **Stock → Operations → Receipt**.

## Trigger Point

**Automatic:** `purchase.order.button_confirm()` → `purchase.order.line._create_or_update_stock_moves()` → `stock.picking` created with type `incoming`.

**Manual:** User navigates to **Stock → Operations → Receipt**, selects the vendor/supplier location as source, the stock location as destination, and creates the picking lines manually.

Alternative triggers:
- **PO line change:** Modifying ordered quantities on a confirmed PO can create additional moves.
- **Return receipt:** A return from stock (internal transfer or return to vendor) uses the same incoming picking type but with a different source location.
- **Drop-ship receipt:** Some dropship configurations create incoming receipts at a transit location.

---

## Complete Method Chain

```
PATH A: Automatic from PO confirmation
────────────────────────────────────────────

1. purchase.order.button_confirm()
   │
   └─► 2. purchase.order._create_picking()
         ├─► 3. po_line._create_or_update_stock_moves() per line
         │     └─► 4. stock.picking.search([('picking_type_id', '=', incoming_type)])
         │           └─► 5. IF existing picking found for same PO:
         │                 └─► 6. stock.move.create() added to existing picking
         │           └─► 7. ELSE:
         │                 └─► 8. stock.picking.create() with type='incoming'
         │                       ├─► location_id = partner.lot_stock_id (vendor/supplier location)
         │                       ├─► location_dest_id = warehouse.lot_stock_id
         │                       ├─► origin = purchase.order.name
         │                       └─► picking_type_id = incoming receipt type
         └─► 9. po_line.write({'product_qty': ...}) — no change to state

PATH B: Picking confirmation
────────────────────────────────────────────

10. stock.picking.action_confirm()   [User clicks "Confirm" or scheduler]
    │
    └─► 11. _action_confirm()
          ├─► 12. stock.move._action_confirm() for each move
          │     ├─► 13. move._check_company()
          │     ├─► 14. IF chained (move_orig_ids): wait for source moves
          │     └─► 15. move state = 'confirmed'
          └─► 16. picking state = 'confirmed'

PATH C: Availability / reservation check
────────────────────────────────────────────

17. stock.picking.action_assign()   [User clicks "Check Availability"]
    │
    └─► 18. _action_assign()
          ├─► 19. stock.move._action_assign()
          │     ├─► 20. move._do_unreserve() [clear stale reservations]
          │     ├─► 21. move._action_confirm() [re-confirm if needed]
          │     └─► 22. IF incoming receipt (vendor location):
          │            └─► 23. Products are generally available — state = 'assigned'
          │                └─► Skip quant reservation (incoming quants don't exist yet)
          │     └─► ELSE (standard pull): reserve from stock quants
          └─► 24. picking state = 'assigned' (ready to receive)

PATH D: User registers quantities received
────────────────────────────────────────────

    └─► 25. stock.move.line create/update
          ├─► 26. qty_done set on move lines (user scans or types)
          └─► 27. IF lot/serial tracked:
                    └─► lot_id assigned per line — LOT REQUIRED before done

PATH E: Validation (user clicks "Validate")
────────────────────────────────────────────

28. stock.picking.action_done()   [User clicks "Validate"]
    │
    └─► 29. _button_validate()
          ├─► 30. IF immediate_transfer == False:
          │      └─► 31. wizard: `stock.immediate.transfer` shown
          │            └─► 32. re-call action_done() with immediate=True
          │
          └─► 33. _action_done()
                ├─► 34. stock.move.action_done()
                │     └─► 35. _action_done() per move
                │           ├─► 36. qty_done validated vs product_uom_qty
                │           ├─► 37. IF tracked product: lot_id verified
                │           ├─► 38. _update_available_quantity(+qty) at dest location
                │           │     └─► stock.quant updated: quantity += qty at dest
                │           ├─► 39. stock.quant._update_available_quantity(-qty) at source
                │           │     └─► source quant (vendor/partner location) decremented
                │           ├─► 40. stock.quant._update_reserved_quantity(-reserved_qty)
                │           │     └─► unreserve if anything was reserved
                │           ├─► 41. product.qty_on_hand recomputed
                │           ├─► 42. product.val_authoritative = current cost price
                │           ├─► 43. stock.valuation.layer.create()
                │           │     └─► layer: unit_cost, quantity, value recorded
                │           ├─► 44. account.move.line create (if valuation enabled)
                │           │     └─► credit to received inventory account
                │           └─► 45. move state = 'done'
                │
                └─► 46. picking state = 'done'
                      └─► 47. po_line.write({'qty_received': qty})

PATH F: Post-receipt side effects
─────────────────────────────────

    └─► 48. IF qty_done < product_uom_qty:
           └─► 49. Backorder picking created
                 └─► stock.picking (backorder) with backorder_id set
                       └─► Remaining moves in backorder state = 'confirmed'
    └─► 50. purchase.order.qty_received updated (sum of received lines)
    └─► 51. Activity scheduled for follow-up (if configured)
    └─► 52. Mail notification to vendor (if enabled)
```

---

## Decision Tree

```
User clicks "Validate" on incoming receipt
│
├─► Is the product lot/serial tracked?
│  ├─► YES → lot_id MUST be assigned on each move line before done
│  │        └─► Missing lot → UserError: "You need to supply Lot/Serial number"
│  └─► NO → proceed
│
├─► qty_done == product_uom_qty (ordered qty)?
│  ├─► YES → full receipt, no backorder
│  └─► NO (partial receipt)?
│        ├─► User selected "Create Backorder" → backorder created for remainder
│        └─► User selected "No Backorder" → remaining qty cancelled
│
├─► Was this receipt created from a PO?
│  ├─► YES → po_line.qty_received updated
│  │        └─► IF qty_received == product_qty: line fully received
│  └─► NO (manual receipt): no PO link
│
└─► Is stock valuation enabled (stock_account installed)?
   └─► YES → stock.valuation.layer + account.move.line created
```

---

## Database State After Completion

| Table | Record Created/Updated | Key Fields |
|-------|----------------------|------------|
| `stock_picking` | Created (auto or manual), `state = 'done'` | `picking_type_id = incoming`, `location_id`, `location_dest_id`, `origin` |
| `stock_move` | Created per PO line, `state = 'done'` | `product_id`, `product_uom_qty`, `quantity_done`, `location_id`, `location_dest_id` |
| `stock_move_line` | Created per move with qty_done set | `qty_done`, `lot_id` (if tracked), `location_id`, `location_dest_id` |
| `stock_quant` | Updated: `quantity += qty` at destination stock location | `product_id`, `location_id`, `quantity`, `lot_id` |
| `stock_valuation_layer` | Created per move (if stock_account installed) | `product_id`, `unit_cost`, `quantity`, `value`, `stock_move_id` |
| `account_move` | Created (if stock_account installed) | `ref = picking.name`, `state = 'posted'` |
| `account_move_line` | Created (if stock_account installed) | `account_id`, `debit/credit`, `product_id` |
| `purchase_order_line` | Updated: `qty_received` written | `qty_received` = sum of received quantities |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Reason |
|----------|-------------|---------------------|
| Lot/serial tracked but lot not assigned | `UserError: "You need to supply Lot/Serial number"` | `_action_done()` on stock.move validates tracked products |
| qty_done exceeds product_uom_qty without backorder | `UserError: "Done quantity exceeds reserved"` | `_action_done()` enforces qty_done <= product_uom_qty unless backorder flag set |
| Picking already done or cancelled | `UserError: "Picking is already done"` | Guard in `action_done()` checks `state in ('done', 'cancel')` |
| User without stock validation rights | `AccessError` | `groups` XML attribute on Validate button |
| Source/destination location inactive | `ValidationError` | `location.active` check in `stock.location._check_active()` |
| Product is a non-storable service | `UserError: "Product type is not storable"` | Only `type == 'product'` products generate stock moves |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Stock quant increased | `stock.quant` | `quantity` incremented at destination (stock) location |
| Stock quant at vendor location decremented | `stock.quant` | `quantity` decremented at supplier location |
| Valuation layer created | `stock.valuation.layer` | Records unit cost and qty for FIFO/AVCO valuation |
| Journal entry posted | `account.move` | If `stock_account` installed: inventory value posted to general ledger |
| PO line qty_received updated | `purchase.order.line` | `qty_received` field written; triggers `qty_received >= product_qty` check |
| Backorder picking created | `stock.picking` | New picking with `backorder_id` pointing to original; state = 'confirmed' |
| Product's qty_on_hand updated | `product.product` | Computed from quants; val_authoritative updated to cost price |
| Serial/lot quantity updated | `stock.lot` | Lot's `product_quantity` incremented when received |

---

## Security Context

> *Which user context the flow runs under, and what access rights are required at each step.*

| Step | Security Mode | Access Required | Notes |
|------|-------------|----------------|-------|
| `stock.picking.create()` (from PO) | `sudo()` (system) | System — no ACL | Triggered by `purchase.order._create_picking()` |
| `stock.picking.action_confirm()` | Current user | `group_stock_user` | Button-level security |
| `stock.move.create()` | `sudo()` (system) | System | Framework creates move records |
| `stock.picking.action_assign()` | Current user | `group_stock_user` | Check availability button |
| `_action_assign()` | `sudo()` (system) | System | Updates reserved quants |
| `stock.picking.action_done()` | Current user | `group_stock_user` | Validate button |
| `_action_done()` | `sudo()` (system) | System | Updates quants and creates valuation layer |
| `stock.quant._update_available_quantity()` | `sudo()` (system) | System | Writes to quants — must bypass ACL |
| `stock.valuation.layer.create()` | `sudo()` (system) | System | Valuation record creation |
| `account.move.line.create()` | `sudo()` (system) | System (if stock_account installed) | Accounting entries |

**Key principle:** Incoming receipts are more permissive than outgoing deliveries because the vendor/supplier location does not require reservation (quants don't exist yet at the vendor). All quant writes use `sudo()` to allow the system to update inventory across all users.

---

## Transaction Boundary

> *Which steps are inside the database transaction and which are outside. Critical for understanding atomicity and rollback behavior.*

```
Steps 1–9    ✅ INSIDE transaction  — PO confirmation + picking/move creation
Steps 10–16 ✅ INSIDE transaction  — picking confirm + move creation
Steps 17–24 ✅ INSIDE transaction  — availability check (reservation is atomic)
Steps 25–27 ✅ INSIDE transaction  — user registers qty (move lines written)
Steps 28–47 ✅ INSIDE transaction  — validation + quant updates + valuation layer
Steps 48     ✅ INSIDE transaction  — backorder creation
Steps 50–52  ❌ OUTSIDE transaction — mail notification queued via ir.mail_server
```

| Step | Boundary | Behavior on Failure |
|------|----------|-------------------|
| Steps 1–47 | ✅ Atomic | Rollback on any error — quants revert to pre-receipt state |
| `stock.quant._update_available_quantity()` | ✅ Atomic | Stock levels rolled back on error |
| `stock.valuation.layer.create()` | ✅ Atomic | Valuation layer rolled back with picking validation |
| `account.move` posting | ✅ Atomic (if stock_account installed) | Rolled back with transaction |
| `mail.mail` notification | ❌ Async queue | Retried by `ir.mail_server` cron |
| `mail.activity` creation | ✅ Atomic | Rolled back with transaction |

**Rule of thumb:** The entire receipt validation (steps 28–48) is atomic — if any step fails, the picking state rolls back and no quants are updated. Only async mail notifications are outside the transaction boundary.

---

## Idempotency

> *What happens when this flow is executed multiple times (double-click, race condition, re-trigger).*

| Scenario | Behavior |
|----------|----------|
| Double-click "Validate" button | Second call hits guard: `if self.state == 'done': return True` — no-op |
| Re-trigger `action_done()` on done picking | No-op — state already 'done', quants already updated |
| Re-run `action_assign()` on assigned incoming receipt | No-op for incoming (no reservation needed); `sudo()` call is safe to re-run |
| Concurrent validation from two sessions | First write wins; second raises `UserError: "Picking is already done"` |
| Receipt of already-received PO line (re-trigger) | Quant would be double-counted — prevented by PO line state check |
| Receive same lot twice (same picking re-done) | Error: picking already done |

**Common patterns:**
- **Idempotent:** `action_done()` (state guard), `action_assign()` for incoming receipts, `write()` with same values
- **Non-idempotent:** `stock.quant._update_available_quantity()` (quantity added), `stock.valuation.layer.create()` (new layer per move), `stock.lot` quantity updated

---

## Extension Points

> *Where and how developers can override or extend this flow. Critical for understanding Odoo's inheritance model.*

| Step | Hook Method | Purpose | Arguments | Override Pattern |
|------|-------------|---------|-----------|-----------------|
| Step 3 | `_create_or_update_stock_moves()` | Control move creation from PO lines | `self` (po_line) | Extend to set custom location/quantity |
| Step 8 | `_get_picking_values()` | Customize incoming picking vals | `self, group, location, ...` | Override to set custom origin, note |
| Step 12 | `_prepare_stock_moves()` | Customize move creation | `self, po_line` | Return custom vals before `create()` |
| Step 22 | `_action_assign()` incoming branch | Custom incoming availability logic | `self` | Override for special vendor handling |
| Step 38 | `_update_available_quantity()` | Custom quant update | `self, product_id, qty, location` | Override for custom valuation |
| Step 43 | `_create_valuation_layer()` | Custom valuation layer creation | `self, move` | Extend for landed cost integration |
| Post-receipt | `_after_move_done()` | Post-receipt side effects | `self` | Called after move state = 'done' |
| Pre-validation | `_check_picking_access()` | Pre-validation checks | `self` | Add checks before done |
| Backorder | `_create_backorder()` | Control backorder creation | `self, backorder_moves` | Return `False` to skip backorder |

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
- `stock.picking._action_assign()` — incoming branch skips standard reservation
- `stock.valuation.layer.create()` — override to integrate with landed costs
- Backorder creation is controlled by `_create_backorder()` — return `False` to prevent

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
| `stock.picking.action_done()` | **Return to vendor** | `stock.return.picking` wizard | Creates new outgoing picking (return) |
| Return picking validated | Vendor credited | Vendor bill reversal or credit note | Stock decreases, vendor liability cleared |
| Picking in `confirmed/assigned` | `action_cancel()` | `stock.picking.action_cancel()` | Cancels moves before done |
| `action_cancel()` on picking | `action_draft()` | `stock.picking.action_draft()` | Resets to draft; PO line qty_received stays |
| Picking in `done` state | Cannot directly cancel | Must use return flow | Odoo immutability for done pickings |
| Partial receipt | Receive remaining via backorder | Standard receipt flow on backorder | PO line tracks partial received qty |

**Important:** This flow is **partially reversible**:
- Receipt `done` → must use **Return Picking** wizard (`stock.return.picking`) — creates a new outgoing picking to return goods to vendor
- The original incoming picking remains `done` — it is the historical receipt record
- If `stock_account` is installed: a vendor return creates a counter-journal entry to reverse the valuation
- The PO's `qty_received` field is not automatically adjusted by the return flow — manual adjustment or credit note needed

**Return Picking Wizard flow:**
1. User clicks **Return** on a done incoming picking
2. `stock.return.picking` wizard opens — user selects lines and quantities to return
3. `stock.return.picking` → `create_returns()` called
4. New outgoing `stock.picking` created with `origin = original_picking.name`
5. User validates return picking → stock quants at stock location decreased
6. Vendor credited via credit note or bill reversal

---

## Alternative Triggers

> *All the ways this flow can be initiated — not just the primary user action.*

| Trigger Type | Method / Endpoint | Context | Frequency |
|-------------|------------------|---------|-----------|
| Automatic from PO confirmation | `purchase.order.button_confirm()` | Purchase UI | Per confirmed PO |
| Manual receipt creation | Stock > Operations > Receipt | Stock UI | Manual |
| PO line quantity change | `_create_or_update_stock_moves()` | Purchase UI | On PO line edit |
| Multi-step receipt (input + stock) | Intermediate pickings in two/three-step routes | Stock routes | Automatic based on route config |
| Dropship receipt | `stock.rule` with dropship route | Purchase order | On order confirmation |
| EDI/API | External system POSTs delivery receipt | Web service | On demand |
| Return from internal use | Internal transfer reversal | Stock UI | Manual |

**For AI reasoning:** Incoming receipts created from POs are tightly coupled — the PO line tracks `qty_received` and the receipt's `origin` links back to the PO. Manual receipts are independent and have no PO link.

---

## Related

- [Modules/Stock](Stock.md) — Stock/picking module reference
- [Modules/Purchase](Purchase.md) — Purchase module reference
- [Flows/Stock/delivery-flow](delivery-flow.md) — Outgoing delivery counterpart
- [Flows/Purchase/purchase-order-receipt-flow](purchase-order-receipt-flow.md) — PO-linked receipt flow
- [Flows/Stock/stock-valuation-flow](stock-valuation-flow.md) — Stock valuation layer and account.move integration
- [Patterns/Workflow Patterns](Workflow Patterns.md) — Workflow pattern reference
- [Core/API](API.md) — @api decorator patterns
