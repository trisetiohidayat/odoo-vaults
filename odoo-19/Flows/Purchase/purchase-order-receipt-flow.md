---
type: flow
title: "Purchase Order Receipt Flow"
primary_model: stock.picking
trigger: "Automatic from PO confirm OR User action — Stock → Operations → Receipt"
cross_module: true
models_touched:
  - stock.picking
  - stock.move
  - stock.quant
  - purchase.order
  - purchase.order.line
  - stock.location
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[[Flows/Purchase/purchase-order-creation-flow]]"
  - "[[Flows/Purchase/purchase-to-bill-flow]]"
  - "[[Flows/Stock/receipt-flow]]"
related_guides:
  - "[[Modules/Purchase]]"
  - "[[Modules/Stock]]"
source_module: purchase, stock
source_path: ~/odoo/odoo19/odoo/addons/stock/
created: 2026-04-06
updated: 2026-04-06
version: "1.0"
---

# Purchase Order Receipt Flow

## Overview

This flow covers the physical receipt of products against a confirmed Purchase Order. An incoming `stock.picking` is created when `purchase.order.button_confirm()` is called, and it must be independently confirmed and validated by the warehouse user. Products move from the vendor/supplier location to the stock location, increasing on-hand quantities and creating stock valuation layers. The `purchase.order.line.qty_received` field is updated at each receipt, allowing the PO to track delivery progress against ordered quantities. Partial receipts, over-receipts, and under-receipts are all supported — the PO remains open until all ordered quantities are received or the user explicitly closes it.

## Trigger Point

**Automatic:** `purchase.order.button_confirm()` → `purchase.order._create_picking()` → `stock.picking` created with type `incoming`, linked to PO via `origin` field and `po_line_id` on moves.

**Manual:** User navigates to **Stock → Operations → Receipt**, creates picking manually, and optionally fills in the vendor's PO reference in the `origin` field.

Alternative triggers:
- **Partial receipt:** When a confirmed PO has some lines already received, modifying `product_qty` on remaining lines triggers additional stock moves/pickings.
- **PO line quantity change after confirm:** `_create_or_update_stock_moves()` creates new moves or updates existing ones.
- **Return from stock:** A return picking (return to vendor) uses the same incoming picking type.
- **Dropship receipt:** If configured, a dropship PO creates a receipt at the customer location or a transit location.

---

## Complete Method Chain

```
TRIGGER: PO confirmation creates receipt picking
────────────────────────────────────────────────────────────────

1. purchase.order.button_confirm()
   │
   └─► 2. _button_confirm()
         ├─► 3. _create_picking()
         │     ├─► 4. po_line.qty_received = 0 (initialized)
         │     ├─► 5. stock.picking.create() type='incoming'
         │     │     ├─► 6. location_id = vendor.partner_id.lot_stock_id (supplier)
         │     │     ├─► 7. location_dest_id = warehouse.lot_stock_id (stock)
         │     │     ├─► 8. origin = purchase.order.name
         │     │     ├─► 9. picking_type_id = incoming receipt type
         │     │     └─► 10. group_id = procurement_group (from PO)
         │     │
         │     └─► 11. for each po_line (grouped by product, only if type='product'):
         │           └─► 12. stock.move.create()
         │                 ├─► 13. product_id = po_line.product_id
         │                 ├─► 14. product_uom_qty = po_line.product_qty
         │                 ├─► 15. location_id = vendor location
         │                 ├─► 16. location_dest_id = warehouse lot_stock_id
         │                 ├─► 17. po_line_id = po_line.id
         │                 ├─► 18. state = 'draft'
         │                 └─► 19. origin = po_line.order_id.name
         │
         └─► 20. state = 'purchase' (PO locked)
               └─► 21. Picking in 'draft' state — user must confirm + validate

PICKING CONFIRM (user clicks "Confirm")
────────────────────────────────────────────────────────────────

22. stock.picking.action_confirm()   [User clicks "Confirm" on receipt]
    │
    └─► 23. _action_confirm()
          ├─► 24. stock.move._action_confirm() for each move
          │     ├─► 25. move._check_company()
          │     ├─► 26. IF chained: move_orig_ids check → 'waiting'
          │     └─► 27. move state = 'confirmed'
          └─► 28. picking state = 'confirmed'

AVAILABILITY CHECK (user clicks "Check Availability")
────────────────────────────────────────────────────────────────

29. stock.picking.action_assign()   [User clicks "Check Availability"]
    │
    └─► 30. _action_assign()
          ├─► 31. stock.move._action_assign()
          │     ├─► 32. Incoming receipt: no reservation needed
          │     │     └─► 33. move state = 'assigned' (incoming = always available)
          │     └─► ELSE (standard): reserve from stock quants
          └─► 34. picking state = 'assigned'

USER REGISTERS QUANTITIES RECEIVED
────────────────────────────────────────────────────────────────

    └─► 35. stock.move.line create/update
          ├─► 36. qty_done set on each move line
          │     └─► 37. IF lot/serial tracked: lot_id assigned — required before done
          └─► 38. User records actual received quantity

PICKING VALIDATION (user clicks "Validate")
────────────────────────────────────────────────────────────────

39. stock.picking.action_done()   [User clicks "Validate"]
    │
    └─► 40. _button_validate()
          ├─► 41. IF immediate_transfer == False:
          │      └─► 42. wizard: `stock.immediate.transfer` shown
          │            └─► 43. re-call action_done() with immediate=True
          │
          └─► 44. _action_done()
                ├─► 45. stock.move.action_done()
                │     └─► 46. _action_done() per move
                │           ├─► 47. qty_done validated vs product_uom_qty
                │           ├─► 48. IF tracked: lot_id verified
                │           ├─► 49. _update_available_quantity(+qty) at destination
                │           │     └─► 50. stock.quant updated: quantity += qty at stock location
                │           │           └─► 51. product.qty_on_hand INCREASED
                │           │           └─► 52. product.val_authoritative = cost price
                │           ├─► 53. _update_available_quantity(-qty) at source
                │           │     └─► 54. source (vendor) quant decremented
                │           ├─► 55. _update_reserved_quantity(-reserved_qty)
                │           ├─► 56. stock.valuation.layer.create()
                │           │     └─► 57. unit_cost = po_line.price_unit (or avg cost)
                │           │     └─► 58. quantity, value recorded for valuation
                │           ├─► 59. account.move.line created (if stock_account installed)
                │           │     └─► 60. Inventory asset account debited
                │           └─► 61. move state = 'done'
                │
                └─► 62. picking state = 'done'

POST-RECEIPT: PO line qty_received update
────────────────────────────────────────────────────────────────

    └─► 63. po_line._update_received_qty()
          ├─► 64. qty_received = sum of all stock.move.quantity_done linked to this po_line
          ├─► 65. IF qty_received > product_qty (ordered):
          │      └─► 66. Over-receipt: warning logged, qty_received > product_qty allowed
          │           └─► 67. Message posted: "Over-delivery by X units"
          ├─► 68. IF qty_received == product_qty:
          │      └─► 69. po_line.qty_received = product_qty — line fully received
          └─► 70. IF qty_received < product_qty:
                 └─► 71. po_line partially received — PO still open

POST-DONE SIDE EFFECTS
────────────────────────────────────────────────────────────────

    └─► 72. IF partial done (qty_done < product_uom_qty):
           └─► 73. Backorder picking created
                 └─► 74. stock.backorder record
                       └─► 75. New stock.picking (backorder) for remaining qty
                             └─► 76. po_line._update_received_qty() recalculated
    └─► 77. purchase.order.message_post() — receipt logged
    └─► 78. IF all po_lines fully received:
           └─► 79. purchase.order state → 'done' (if PO qty的控制 = 'manual')
           └─► OR: activity completed for receipt follow-up
    └─► 80. Stock alert if qty differs from ordered (over/under receipt logged)
```

---

## Decision Tree

```
User clicks "Validate" on PO receipt picking
│
├─► Is the product lot/serial tracked?
│  ├─► YES → lot_id MUST be assigned on each move line
│  │        └─► Missing lot → UserError: "You need to supply Lot/Serial number"
│  └─► NO → proceed
│
├─► qty_done (actual received) vs product_uom_qty (ordered)?
│  ├─► EQUAL → full receipt → po_line fully received
│  ├─► LESS (partial receipt)?
│  │     ├─► User selected "Create Backorder" → backorder created
│  │     └─► User selected "No Backorder" → remainder cancelled
│  └─► MORE (over-receipt)?
│        ├─► If allow_overdraw: accepted, po_line qty_received > product_qty
│        └─► If not: error raised
│
├─► PO line qty_received updated:
│  ├─► qty_received >= product_qty → fully received
│  └─► qty_received < product_qty → partial, PO still open
│
└─► All PO lines fully received?
   └─► YES → PO may auto-close (depends on qty_control setting)
```

---

## Database State After Completion

| Table | Record Created/Updated | Key Fields |
|-------|----------------------|------------|
| `stock_picking` | Created from PO, `state = 'done'` | `picking_type_id = incoming`, `location_id = vendor`, `location_dest_id = stock`, `origin = PO.name` |
| `stock_move` | Created per PO line, `state = 'done'` | `product_id`, `product_uom_qty`, `quantity_done`, `po_line_id`, `location_id`, `location_dest_id` |
| `stock_move_line` | Created/updated during done | `qty_done`, `lot_id` (if tracked), `location_id`, `location_dest_id` |
| `stock_quant` | Updated: `quantity += qty` at stock location | `product_id`, `location_id = stock`, `quantity`, `lot_id` |
| `stock_valuation_layer` | Created per move | `product_id`, `unit_cost = po_line.price_unit`, `quantity`, `value`, `stock_move_id`, `po_line_id` |
| `account_move_line` | Created (if stock_account installed) | Dr to inventory asset account, linked to valuation layer |
| `purchase_order_line` | Updated: `qty_received` written | `qty_received` = sum of quantity_done on linked moves |
| `purchase_order` | `qty_received` updated per line | `invoice_status` may change |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Reason |
|----------|-------------|---------------------|
| Lot/serial tracked but lot not assigned | `UserError: "You need to supply Lot/Serial number"` | `_action_done()` on stock.move validates lot_id for tracked products |
| qty_done exceeds ordered qty (over-receipt not allowed) | `UserError: "Over-delivery not allowed"` | `purchaseline.product_id.purchase_method` and allow_overdraw setting |
| qty_done > product_uom_qty (no backorder selected) | `UserError: "Done quantity exceeds reserved"` | `_action_done()` enforces qty limits |
| Picking already done or cancelled | `UserError: "Picking is already done"` | Guard in `action_done()` |
| Access rights — user cannot validate | `AccessError` | `group_stock_user` on Validate button |
| PO line product is `service` type | No picking created for that line | `_create_picking()` skips service products |
| Source/destination location inactive | `ValidationError` | `location.active` check |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Stock quant increased | `stock.quant` | `quantity` incremented at destination (stock) location |
| Stock quant at vendor location decremented | `stock.quant` | `quantity` decremented at vendor location |
| PO line qty_received updated | `purchase.order.line` | `qty_received` = sum of received quantities; triggers full-receipt check |
| Over-receipt logged | `purchase.order.line` | `qty_received` can exceed `product_qty`; warning in chatter |
| Stock valuation layer created | `stock.valuation.layer` | Records unit cost (from PO price), qty, and value for FIFO/AVCO |
| Journal entry created | `account.move.line` | If `stock_account` installed: inventory asset account debited |
| Product's qty_on_hand increased | `product.product` | `qty_on_hand` computed from quants; val_authoritative updated |
| Lot/serial received | `stock.lot` | Lot's `product_quantity` incremented |
| Backorder created | `stock.picking` | New receipt picking for remaining qty; state = 'confirmed' |
| PO state may auto-close | `purchase.order` | If qty_control='manual' and all lines fully received |
| Activity completed | `mail.activity` | Receipt follow-up activity marked done |

---

## Security Context

> *Which user context the flow runs under, and what access rights are required at each step.*

| Step | Security Mode | Access Required | Notes |
|------|-------------|----------------|-------|
| `purchase.order._create_picking()` (from confirm) | `sudo()` (system) | System | Triggered by PO confirm |
| `stock.picking.action_confirm()` | Current user | `group_stock_user` | Button-level security |
| `stock.move.create()` | `sudo()` (system) | System | Framework creates move records |
| `stock.picking.action_assign()` | Current user | `group_stock_user` | Check availability button |
| `stock.picking.action_done()` | Current user | `group_stock_user` | Validate button |
| `_action_done()` | `sudo()` (system) | System | Updates quants and creates valuation layer |
| `stock.quant._update_available_quantity()` | `sudo()` (system) | System | Writes to quants — bypasses ACL |
| `po_line._update_received_qty()` | `sudo()` (system) | System | Updates PO line qty_received |
| `stock.valuation.layer.create()` | `sudo()` (system) | System | Valuation record creation |
| `account.move.line` creation | `sudo()` (system) | System (if stock_account installed) | Accounting entries |
| `mail.message` | Current user | Write ACL | Receipt logged in PO chatter |

**Key principle:** Receipt validation uses `sudo()` for quant updates because it must write to quants across all users. However, the Validate button itself requires `group_stock_user`. The PO's `qty_received` field is updated via `sudo()` within the same transaction as the quant update.

---

## Transaction Boundary

> *Which steps are inside the database transaction and which are outside. Critical for understanding atomicity and rollback behavior.*

```
Steps 1–21  ✅ INSIDE transaction  — PO confirm + picking creation (already confirmed PO)
Steps 22–28 ✅ INSIDE transaction  — picking confirm + move state change
Steps 29–34 ✅ INSIDE transaction  — availability check
Steps 35–38 ✅ INSIDE transaction  — user registers qty on move lines
Steps 39–61 ✅ INSIDE transaction  — validation + quant updates + valuation layer
Steps 62–76 ✅ INSIDE transaction  — po_line qty_received update + backorder
Step 77     ✅ INSIDE transaction  — message_post (ORM write)
Step 78–80  ✅ INSIDE transaction  — PO state / activity updates
```

| Step | Boundary | Behavior on Failure |
|------|----------|-------------------|
| Steps 1–61 | ✅ Atomic | Rollback on any error — quants and valuation layers revert |
| `stock.quant._update_available_quantity()` | ✅ Atomic | Stock levels rolled back on error |
| `stock.valuation.layer.create()` | ✅ Atomic | Valuation layer rolled back with picking |
| `po_line._update_received_qty()` | ✅ Atomic | PO line rolled back on error |
| `account.move` posting | ✅ Atomic (if stock_account) | Rolled back with transaction |
| Backorder creation | ✅ Atomic | Created in same transaction |
| `mail.mail` notification | ❌ Async queue | Retried by `ir.mail_server` cron |
| `mail.activity` completion | ✅ Atomic | Rolled back with transaction |

**Rule of thumb:** The entire receipt validation and PO line update (steps 39–80) is atomic — if quant update fails, `qty_received` is also rolled back. No inconsistency between stock levels and PO received quantities is possible within Odoo's transaction model.

---

## Idempotency

> *What happens when this flow is executed multiple times (double-click, race condition, re-trigger).*

| Scenario | Behavior |
|----------|----------|
| Double-click "Validate" button | Second call hits guard: `if self.state == 'done': return True` — no-op |
| Re-trigger `action_done()` on done picking | No-op — state already 'done', quants already updated |
| Re-run `action_assign()` on assigned incoming receipt | No-op for incoming (no reservation needed) |
| Concurrent validation from two sessions | First write wins; second raises `UserError: "Picking is already done"` |
| Receive same PO line again via backorder | Picks up remaining qty — backorder created from first partial |
| `qty_received` recomputed | Sum of all linked move quantities — idempotent aggregate |

**Common patterns:**
- **Idempotent:** `action_done()` (state guard), `po_line._update_received_qty()` (sum of all linked moves — same result)
- **Non-idempotent:** `stock.quant._update_available_quantity()` (quantity added on each run), `stock.valuation.layer.create()` (new layer per move per run), `stock.lot.product_quantity` incremented

---

## Extension Points

> *Where and how developers can override or extend this flow. Critical for understanding Odoo's inheritance model.*

| Step | Hook Method | Purpose | Arguments | Override Pattern |
|------|-------------|---------|-----------|-----------------|
| Step 3 | `_create_picking()` | Control picking creation from PO | `self` | Override to skip, customize, or add lines |
| Step 11 | `_prepare_picking()` | Customize picking vals | `self, picking` | Override for custom picking attributes |
| Step 12 | `_prepare_stock_moves()` | Customize move vals | `self, picking` | Override for custom move attributes |
| Step 46 | `_action_done()` | Core done logic for PO receipt | `self` (move) | Override for custom receipt processing |
| Step 49 | `_update_available_quantity(+)` | Custom quant increment at stock | `self, product_id, qty, location` | Override for custom valuation |
| Step 56 | `_create_valuation_layer()` | Custom valuation layer | `self, move` | Extend for landed cost, duty integration |
| Step 63 | `_update_received_qty()` | Custom qty_received logic | `self` (po_line) | Override for custom partial-receipt logic |
| Step 66 | Over-receipt handling | Custom over-receipt behavior | `self` | Add approval workflow for over-delivery |
| Pre-validation | `_check_picking_access()` | Pre-receipt validation | `self` | Add checks before done |
| Backorder | `_create_backorder()` | Control backorder creation | `self, backorder_moves` | Return `False` to skip |
| Post-receipt | `_post_purchase_receipt()` | Post-receipt side effects | `self` | Notification, approval, etc. |

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
- `stock.move._action_done()` is the primary override for customizing what happens when a receipt move is validated
- `purchase.order._create_picking()` controls picking creation from the PO side
- `stock.picking._action_assign()` — incoming receipts skip standard reservation
- `_update_received_qty()` on `purchase.order.line` controls PO line receipt tracking
- Backorder creation is controlled by `_create_backorder()` — return `False` to skip

**Deprecated override points to avoid:**
- `@api.multi` on overridden methods (deprecated in Odoo 19)
- `@api.one` anywhere (deprecated)
- Direct `_workflow` calls (deprecated)
- Overriding without calling `super()` — breaks quant and PO tracking

---

## Reverse / Undo Flow

> *How to cancel or reverse this flow. Critical for understanding what is and isn't reversible.*

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| Picking in `draft/confirmed/assigned` | `action_cancel()` | `stock.picking.action_cancel()` | Cancels moves; PO line qty_received stays 0 |
| Picking in `done` | **Return to vendor** | `stock.return.picking` wizard | Creates outgoing picking to return goods to vendor |
| Return picking validated | Vendor credit note | `account.move.reversal_entry()` | Reverses vendor bill if already billed |
| PO line qty_received updated | Not automatically reduced | By return picking validation | Return reduces stock, not PO received qty |
| Picking in `done` + vendor bill received | Cancel bill first | `account.move.reversal_entry()` | Then return goods |
| `action_cancel()` on picking | `action_draft()` | `stock.picking.action_draft()` | Resets to draft; quants unreserved |
| PO cancelled after receipt | Manual qty adjustment | `write()` on po_line | qty_received not auto-adjusted |

**Important:** This flow is **partially reversible**:
- Receipt `done` → must use **Return Picking** wizard (`stock.return.picking`) — creates a new outgoing picking to return goods to vendor
- The original receipt picking remains `done` — it is the historical receipt record
- Return picking decreases stock quants at the stock location (goods leave warehouse)
- Return picking validation does NOT automatically reduce `po_line.qty_received` — the received quantity remains on the PO line
- If `stock_account` is installed: the return creates counter-journal entries to reverse the valuation
- If vendor bill was created from the receipt: must reverse the bill before or alongside the return

**Return Picking Wizard flow (return to vendor):**
1. User clicks **Return** on done receipt picking
2. `stock.return.picking` wizard opens — user selects lines and quantities
3. `create_returns()` called — new outgoing `stock.picking` created with `origin = original.name`
4. User validates return picking → stock quants decreased at stock location
5. Vendor credited via credit note / bill reversal
6. PO line `qty_received` remains unchanged (manually adjust if needed)

**Partial return:**
- Return only some lines or partial qty via `stock.return.picking.line`
- Stock decreases by returned qty
- PO received qty does not change — manually adjust if needed

---

## Alternative Triggers

> *All the ways a PO receipt can be initiated — not just the primary user action.*

| Trigger Type | Method / Endpoint | Context | Frequency |
|-------------|------------------|---------|-----------|
| Automatic from PO confirmation | `purchase.order.button_confirm()` | Purchase UI | Per confirmed PO |
| Manual receipt creation | Stock > Operations > Receipt | Stock UI | Manual |
| PO line qty change after confirm | `_create_or_update_stock_moves()` | Purchase UI | On PO line edit |
| EDI / API receipt | JSON-RPC `stock.picking.action_done()` | Web service | On demand |
| Return from stock (to vendor) | `stock.return.picking` wizard | Stock UI | Manual |
| Multi-step receipt (2/3 steps) | Intermediate pickings via routes | Stock routes | Automatic |

**For AI reasoning:** When asked "what happens if X?", trace from the PO line: `qty_received` is the key field that tracks receipt progress. A PO is fully received when all lines have `qty_received >= product_qty`. The receipt picking is created automatically from `purchase.order._create_picking()` and must be independently validated — the PO state does not automatically change to 'done' upon full receipt in standard Odoo (depends on configuration).

---

## Related

- [[Modules/Purchase]] — Purchase module reference
- [[Modules/Stock]] — Stock/picking module reference
- [[Flows/Purchase/purchase-order-creation-flow]] — PO creation and confirmation that triggers this flow
- [[Flows/Purchase/purchase-to-bill-flow]] — Vendor bill creation from received PO
- [[Flows/Stock/receipt-flow]] — Generic incoming receipt (same mechanics as PO receipt)
- [[Patterns/Workflow Patterns]] — Workflow pattern reference
- [[Core/API]] — @api decorator patterns
