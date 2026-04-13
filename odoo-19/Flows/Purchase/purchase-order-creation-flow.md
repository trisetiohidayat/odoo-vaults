---
type: flow
title: "Purchase Order Creation Flow"
primary_model: purchase.order
trigger: "User action — Purchase → Orders → Create"
cross_module: true
models_touched:
  - purchase.order
  - purchase.order.line
  - res.partner
  - product.product
  - product.supplierinfo
  - stock.picking
  - stock.move
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[Flows/Purchase/purchase-order-receipt-flow](flows/purchase/purchase-order-receipt-flow.md)"
  - "[Flows/Purchase/purchase-to-bill-flow](flows/purchase/purchase-to-bill-flow.md)"
  - "[Flows/Stock/receipt-flow](flows/stock/receipt-flow.md)"
related_guides:
  - "[Modules/Purchase](modules/purchase.md)"
source_module: purchase
source_path: ~/odoo/odoo19/odoo/addons/purchase/
created: 2026-04-06
updated: 2026-04-06
version: "1.0"
---

# Purchase Order Creation Flow

## Overview

This flow covers the lifecycle of a Purchase Order (PO) from its initial creation as a Request for Quotation (RFQ) to its confirmation as a binding purchase order. The key transition is `button_confirm()`, which locks in the order, triggers the creation of incoming receipts (for storable products), adds the vendor to the product's supplier info, and schedules follow-up activities. This flow bridges the Purchase and Stock modules — confirmed POs automatically generate `stock.picking` records for incoming receipts. Understanding the RFQ-to-PO transition is essential because `purchase.order` has different ACL and behavior in each state.

## Trigger Point

**User action:** User navigates to **Purchase → Orders → Requests for Quotation**, clicks **Create**, fills in vendor, order lines, and clicks **Confirm Order** (`button_confirm()`).

The flow is a two-phase creation:
- **Phase 1 (RFQ):** `purchase.order` created in `draft` state — can be edited, lines added/removed.
- **Phase 2 (PO):** `button_confirm()` called — order locked to `purchase` state — stock picking(s) created.

Alternative triggers:
- **PO from Replenishment:** `stock.warehouse.orderpoint` → procurement → creates draft PO.
- **PO from RFQ comparison:** User converts multiple RFQs to a single PO.
- **API/EDI:** External system creates PO via `purchase.order` JSON-RPC or webservice.
- **Copy from existing PO:** `purchase.order.copy()` creates new draft from confirmed PO.

---

## Complete Method Chain

```
PHASE 1: RFQ Creation (draft state)
────────────────────────────────────────────────────────────────

1. purchase.order.create({
       'partner_id': vendor_id,
       'date_order': ...,
       ...
     })
   │
   ├─► 2. purchase.order.line.create() per order line
   │     ├─► 3. _onchange_product_id() per line
   │     │     ├─► 4. product.product.read(['list_price', 'seller_ids', ...])
   │     │     ├─► 5. Seller searched: product.supplierinfo.search([('partner_id', '=', vendor)])
   │     │     ├─► 6. price fetched from seller: product.seller_ids[0].price
   │     │     ├─► 7. taxes fetched: product.supplierinfo[0].product_tmpl_id.supplier_taxes_id
   │     │     ├─► 8. product_uom set: seller.product_uom or product.uom_po_id
   │     │     └─► 9. product_name / description synced from seller info
   │     ├─► 10. _onchange_product_uom() — unit of measure conversion
   │     └─► 11. line state = 'draft'; order state = 'draft'
   │
   └─► 12. purchase.order state = 'draft' (RFQ)

PHASE 2: RFQ → PO Confirmation (draft → purchase)
────────────────────────────────────────────────────────────────

13. purchase.order.button_confirm()
    │
    └─► 14. _button_confirm()
          ├─► 15. _check_order_enabled() [order must be in draft, not cancelled]
          │
          ├─► 16. self.write({'state': 'purchase', 'date_approve': now()})
          │     └─► 17. Order is now locked — lines cannot be freely edited
          │
          ├─► 18. for each po_line: _onchange_product_ids()
          │     ├─► 19. _onchange_product_id() [recompute price/taxes]
          │     └─► 20. _add_supplier_to_product()
          │           └─► 21. product.supplierinfo.create({
          │                    'partner_id': vendor_id,
          │                    'product_tmpl_id': product.product_tmpl_id.id,
          │                    'price': po_line.price_unit,
          │                    'currency_id': po_line.currency_id.id,
          │                    'min_qty': 1,
          │                    'delay': seller.delay
          │                  })
          │                 └─► 22. Vendor added to product's seller list
          │                       └─► 23. Future POs will default to this vendor
          │
          ├─► 24. _create_picking()
          │     ├─► 25. IF all lines are service type (type='service'):
          │     │      └─► 26. No picking created — service, no physical receipt
          │     ├─► 27. ELSE (storable products):
          │     │      ├─► 28. stock.picking.create() type='incoming'
          │     │      │     ├─► 29. location_id = vendor.partner_id.lot_stock_id (supplier)
          │     │      │     ├─► 30. location_dest_id = warehouse.lot_stock_id (stock)
          │     │      │     ├─► 31. origin = purchase.order.name
          │     │      │     └─► 32. group_id set (procurement group)
          │     │      │
          │     │      └─► 33. for each po_line (grouped by product):
          │     │            └─► 34. stock.move.create()
          │     │                  ├─► 35. product_id = po_line.product_id
          │     │                  ├─► 36. product_uom_qty = po_line.product_qty
          │     │                  ├─► 37. location_id = vendor stock location
          │     │                  ├─► 38. location_dest_id = warehouse lot_stock_id
          │     │                  ├─► 39. po_line_id = po_line.id (link back)
          │     │                  ├─► 40. state = 'draft' initially
          │     │                  └─► 41. procurement_id set (links to po_line procurement)
          │     │
          │     └─42. Picking created in 'draft' state
          │           └─► 43. User must confirm + validate receipt separately
          │           └─► See: [Flows/Purchase/purchase-order-receipt-flow](flows/purchase/purchase-order-receipt-flow.md)
          │
          ├─► 44. activity_ids create — scheduled reminder
          │     └─► 45. mail.activity: "Follow-up on purchase order" scheduled
          │           └─► 46. Assigned to PO responsible / purchase team
          │
          └─► 47. message_post "Purchase Order confirmed"
                └─► 48. Mail.message created — followers notified
                      └─► 49. purchase.order.line qty_received = 0 initially

POST-CONFIRMATION: Procurement group run
────────────────────────────────────────────────────────────────

    └─► 50. procurement_group.run()  [may trigger picking confirmation]
    └─► 51. stock.picking.action_confirm()  [if picking_policy='direct']
    └─► 52. po_line.invoice_count updated (computed)
```

---

## Decision Tree

```
User clicks "Confirm Order" on RFQ
│
├─► Is any line a storable product (type='product')?
│  ├─► YES → receipt picking(s) created automatically
│  │        └─► One picking per warehouse / route combination
│  │        └─► Multi-step warehouse: receipt → input → stock (additional internal pickings)
│  └─► NO (all service products) → no picking created
│
├─► Is this vendor already in product's seller list?
│  ├─► YES → price/taxes updated on existing supplierinfo
│  └─► NO → new product.supplierinfo record created
│
├─► Does warehouse use multi-step receipt routes?
│  ├─► YES (Receive in 2/3 steps) → picking goes through input location first
│  │     └─► Additional internal pickings for QC / input stage
│  └─► NO (Receive in 1 step) → single incoming receipt
│
└─► PO state: draft → purchase (locked)
   └─► Lines can still be edited (product_qty, price_unit) but new pickings created for changes
```

---

## Database State After Completion

| Table | Record Created/Updated | Key Fields |
|-------|----------------------|------------|
| `purchase_order` | Created, `state = 'purchase'` | `partner_id`, `date_order`, `date_approve`, `state` |
| `purchase_order_line` | Created per line | `product_id`, `product_qty`, `price_unit`, `product_uom`, `partner_id` |
| `product_supplierinfo` | Created or updated | `partner_id`, `product_tmpl_id`, `price`, `currency_id`, `min_qty`, `delay` |
| `stock_picking` | Created (one per warehouse, for storable lines) | `picking_type_id = incoming`, `location_id = vendor`, `location_dest_id = stock`, `origin = PO name` |
| `stock_move` | Created per po_line (storable only) | `product_id`, `product_uom_qty`, `location_id`, `location_dest_id`, `po_line_id` |
| `procurement_group` | Created / reused | Groups PO → picking → moves |
| `mail.activity` | Created | `res_model='purchase.order'`, scheduled follow-up |
| `mail.message` | Created | Notification posted on PO chatter |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Reason |
|----------|-------------|---------------------|
| Confirm PO with no order lines | `UserError: "No line to confirm"` | `_button_confirm()` requires at least one line |
| Confirm PO with zero-qty line | `UserError` or warning | Line with qty=0 may be skipped in `_create_picking()` |
| Vendor inactive/blocked | `UserError` or access warning | `res.partner` active check on vendor |
| Product on line not purchasable | `UserError: "Product is not purchaseable"` | `product_product.purchase_ok` flag |
| User without purchase rights | `AccessError` | `group_purchase_user` required to confirm |
| Duplicate PO number | `ValidationError` | `_sql_constraints` unique on `name` per sequence |
| PO line product is a consumable with stock valuation | May create unexpected quants | Consumables don't create stock moves |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Vendor added to product's sellers | `product.supplierinfo` | Vendor now appears in product's seller list; future POs auto-populate |
| Price updated on supplierinfo | `product.supplierinfo` | Current PO price recorded in vendor master |
| Incoming receipt picking created | `stock.picking` | Picking in 'draft' state waiting to be confirmed and validated |
| Stock moves created | `stock.move` | One per storable PO line, linked to PO line |
| Follow-up activity scheduled | `mail.activity` | Reminder created for PO responsible user |
| PO followers notified | `mail.message` | Chatter message posted: "Purchase Order confirmed" |
| Procurement group created | `procurement.group` | Links PO to picking for traceability |
| `invoice_count` computed | `purchase.order` | Shows 0 initially; increases when vendor bill created |

---

## Security Context

> *Which user context the flow runs under, and what access rights are required at each step.*

| Step | Security Mode | Access Required | Notes |
|------|-------------|----------------|-------|
| `purchase.order.create()` (RFQ creation) | Current user | `group_purchase_user` | User can create draft RFQs |
| `_onchange_product_id()` | Current user | Read ACL on `product.product`, `product.supplierinfo` | Fetches seller price |
| `button_confirm()` | Current user | `group_purchase_manager` (or `group_purchase_user` if configured) | Locks the order |
| `_add_supplier_to_product()` | `sudo()` (system) | System | Writes to `product.supplierinfo` |
| `_create_picking()` | `sudo()` (system) | System | Creates `stock.picking` and `stock.move` records |
| `stock.picking.create()` | `sudo()` (system) | System | Picking creation bypasses ACL |
| `mail.activity.create()` | `sudo()` (system) | System | Activity scheduled regardless of user |
| `message_post()` | Current user | Write ACL on `purchase.order` | Posts to chatter |

**Key principle:** The `button_confirm()` method is the security boundary that locks the PO. Users need elevated rights to confirm a PO because it creates financial commitments (vendor bills) and triggers stock movements. Supplier info updates use `sudo()` because they are system-level data maintenance.

---

## Transaction Boundary

> *Which steps are inside the database transaction and which are outside. Critical for understanding atomicity and rollback behavior.*

```
Steps 1–12  ✅ INSIDE transaction  — RFQ creation + line creation
Steps 13–22 ✅ INSIDE transaction  — button_confirm + state lock + supplierinfo
Steps 24–43 ✅ INSIDE transaction  — picking + move creation (atomic)
Steps 44–46 ✅ INSIDE transaction  — activity creation (ORM write)
Steps 47–49 ✅ INSIDE transaction  — message_post + field writes
Steps 50–52 ✅ INSIDE transaction  — procurement group run + potential picking confirm
```

| Step | Boundary | Behavior on Failure |
|------|----------|-------------------|
| Steps 1–43 | ✅ Atomic | Rollback on any error — PO remains in draft if confirm fails |
| `_create_picking()` failure | ✅ Atomic | PO stays in 'purchase' state but no picking created — inconsistency |
| `_add_supplier_to_product()` | ✅ Atomic | Vendor info rolled back if error |
| `mail.activity.create()` | ✅ Atomic (ORM) | Rolled back with transaction |
| `message_post()` | ✅ Atomic (ORM) | Chatter message rolled back |
| `mail.mail` notification | ❌ Async queue | Queued for delivery outside transaction |
| Stock picking validation | ❌ OUTSIDE this flow | Separate flow — user must validate receipt |

**Rule of thumb:** PO confirmation is atomic — if `_create_picking()` fails (e.g., due to missing warehouse), the entire confirm operation rolls back. The stock picking created here must be independently confirmed and validated in the receipt flow.

---

## Idempotency

> *What happens when this flow is executed multiple times (double-click, race condition, re-trigger).*

| Scenario | Behavior |
|----------|----------|
| Double-click "Confirm Order" | Second call: `if self.state != 'draft': return True` — no-op; state already 'purchase' |
| Re-trigger `button_confirm()` on confirmed PO | No-op — state guard prevents re-execution |
| Re-create PO from same vendor/product | New PO created (new record) — not deduplicated |
| `copy()` a confirmed PO | Creates new draft PO — `_create_picking()` NOT called on copy (no `button_confirm()`) |
| Multiple confirmations in concurrent sessions | First write wins; second no-ops |
| PO confirmed with service + product lines | Only product lines generate pickings; service lines skipped |

**Common patterns:**
- **Idempotent:** `button_confirm()` (draft-state guard), `write()` with same state
- **Non-idempotent:** `product.supplierinfo.create()` (new record each time — duplicate seller info possible), `stock.picking.create()` (new picking each time), `mail.activity.create()` (new activity)

---

## Extension Points

> *Where and how developers can override or extend this flow. Critical for understanding Odoo's inheritance model.*

| Step | Hook Method | Purpose | Arguments | Override Pattern |
|------|-------------|---------|-----------|-----------------|
| Step 1 | `purchase.order.create()` | Pre-creation validation | vals | Extend `create()` with vals |
| Step 3 | `_onchange_product_id()` | Customize onchange cascade | `self` | Add field sync after `super()` |
| Step 5 | `product.supplierinfo.search()` | Custom seller selection | `self` | Override for multi-vendor selection |
| Step 14 | `_button_confirm()` | Pre-confirm validation | `self` | Add checks before state change |
| Step 20 | `_add_supplier_to_product()` | Custom vendor info update | `self` | Override to set custom min_qty, delay |
| Step 24 | `_create_picking()` | Control picking creation | `self` | Override to customize or skip picking |
| Step 33 | `_prepare_picking()` | Customize picking vals | `self, picking` | Override for custom picking attributes |
| Step 34 | `_prepare_stock_moves()` | Customize move vals | `self, picking` | Override for custom move attributes |
| Step 44 | `activity_create()` | Custom activity scheduling | `self` | Override for custom reminder logic |
| Post-confirm | `_post_purchase_order()` | Post-confirm side effects | `self` | Called after state = 'purchase' |

**Standard override pattern:**
```python
# WRONG — replaces entire method
def button_confirm(self):
    # your code

# CORRECT — extends with super()
def button_confirm(self):
    res = super().button_confirm()
    # your additional code
    return res
```

**Odoo 19 specific hooks:**
- `purchase.order._create_picking()` is the primary override for customizing receipt behavior
- `_prepare_picking()` and `_prepare_stock_moves()` control picking and move creation
- `_add_supplier_to_product()` can be overridden to control when/how vendors are added
- Post-confirm logic should be added in `_post_purchase_order()` or via `button_confirm()` override

**Deprecated override points to avoid:**
- `@api.multi` on overridden methods (deprecated in Odoo 19)
- `@api.one` anywhere (deprecated)
- Direct `_workflow` calls (deprecated — use `button_*` methods)
- Overriding without calling `super()` — breaks picking creation

---

## Reverse / Undo Flow

> *How to cancel or reverse this flow. Critical for understanding what is and isn't reversible.*

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| PO in `draft` (RFQ) | Delete or `action_draft` | `unlink()` or `action_draft()` | RFQ has no downstream effects |
| `button_confirm()` | `button_cancel()` | `purchase.order.button_cancel()` | Only if not yet invoiced |
| `button_cancel()` on PO | `action_draft()` | `purchase.order.action_draft()` | Resets to RFQ; linked picking must also be cancelled |
| Picking created but not done | Cancel picking | `stock.picking.action_cancel()` | Cancels moves; PO line qty_received stays 0 |
| Picking already done | Cannot cancel picking | Must return goods | Return picking required |
| PO invoiced (bill received) | Reverse via credit note | `account.move.reversal_entry()` | Invoice must be reversed before PO cancel |
| Vendor added to supplierinfo | Manual edit | `product.supplierinfo.write()` | Not automatically removed on PO cancel |

**Important:** This flow is **partially reversible**:
- PO in draft: fully reversible (just delete the RFQ)
- PO confirmed (not invoiced): can be cancelled via `button_cancel()` → back to draft
- PO confirmed + picking created (not done): cancel the picking → then cancel PO
- PO confirmed + picking done: must return goods first → then cancel PO
- PO invoiced: must reverse invoice first → then cancel PO

**Cancel PO chain:**
1. Cancel any done pickings (via return)
2. Cancel any pending pickings (`action_cancel()`)
3. If bill received: reverse the vendor bill
4. `button_cancel()` on PO → state = 'cancel'
5. `action_draft()` if needed → state back to 'draft'

---

## Alternative Triggers

> *All the ways a PO can be created and confirmed — not just the primary user action.*

| Trigger Type | Method / Endpoint | Context | Frequency |
|-------------|------------------|---------|-----------|
| User action — Create RFQ | `purchase.order.create()` | Purchase UI | Manual |
| RFQ → Confirm Order | `button_confirm()` | Purchase UI | Manual |
| Replenishment orderpoint | `stock.warehouse.orderpoint` → procurement | Automatic | Based on orderpoint min/max |
| PO from Make to Order | `mrp.production` → procurement | Manufacturing | On MO creation |
| API / EDI | JSON-RPC `purchase.order.create()` | Web service | On demand |
| Copy existing PO | `purchase.order.copy()` | Purchase UI | Manual |
| Request for Quotation comparison | Multiple RFQs → one PO | Purchase UI | Manual |

**For AI reasoning:** PO creation always starts as an RFQ. The `button_confirm()` is the critical transition that creates stock pickings and locks the order. Never assume a PO is editable after confirmation — lines can be modified but changes to `product_qty` or `price_unit` create additional stock moves, not replacements.

---

## Related

- [Modules/Purchase](modules/purchase.md) — Purchase module reference
- [Modules/Stock](modules/stock.md) — Stock/picking module reference
- [Flows/Purchase/purchase-order-receipt-flow](flows/purchase/purchase-order-receipt-flow.md) — Receipt of goods against confirmed PO
- [Flows/Purchase/purchase-to-bill-flow](flows/purchase/purchase-to-bill-flow.md) — Vendor bill creation and payment
- [Flows/Stock/receipt-flow](flows/stock/receipt-flow.md) — Incoming receipt (same as PO receipt)
- [Patterns/Workflow Patterns](patterns/workflow-patterns.md) — Workflow pattern reference
- [Core/API](core/api.md) — @api decorator patterns
