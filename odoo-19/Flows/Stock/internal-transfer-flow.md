---
type: flow
title: "Internal Transfer Flow"
primary_model: stock.picking
trigger: "User action — Stock → Transfers → Create Transfer"
cross_module: true
models_touched:
  - stock.picking
  - stock.move
  - stock.quant
  - stock.location
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[Flows/Stock/picking-action-flow](odoo-19/Flows/Stock/picking-action-flow.md)"
  - "[Flows/Stock/delivery-flow](odoo-19/Flows/Stock/delivery-flow.md)"
  - "[Flows/Stock/receipt-flow](odoo-17/Flows/Stock/receipt-flow.md)"
related_guides:
  - "[Modules/Stock](odoo-18/Modules/stock.md)"
source_module: stock
source_path: ~/odoo/odoo19/odoo/addons/stock/
created: 2026-04-06
updated: 2026-04-06
version: "1.0"
---

# Internal Transfer Flow

## Overview

This flow covers internal transfers of products between warehouse locations within the same company. An internal transfer is a `stock.picking` with `picking_type_code = 'internal'`. Unlike incoming receipts or outgoing deliveries, internal transfers do not cross the company boundary — source and destination locations are both internal warehouse locations. Products leave the source location and arrive at the destination location. The flow supports single-step (direct location-to-location) and multi-step (via an intermediate staging location) routing based on warehouse configuration. Internal transfers are always manually initiated — there is no automatic triggering of internal transfers.

## Trigger Point

**Manual:** User navigates to **Stock → Transfers → Create Transfer** (or **Stock → Operations → Internal Transfers**), selects source and destination internal locations, adds product lines, and saves.

This flow is **always manually initiated**. There is no automatic internal transfer creation in standard Odoo.

Alternative triggers:
- **Wizard action:** `stock.picking` can be created from other flows (e.g., `stock.immediate.transfer` wizard, `stock.return.picking` wizard) which use internal transfer type.
- **Route-based (multi-step):** When a warehouse uses multi-step incoming or outgoing routes, intermediate transfers use internal transfer type between internal locations.
- **Inventory adjustments:** `stock.inventory` wizard can generate internal transfers to reconcile stock.

---

## Complete Method Chain

```
PATH A: Manual internal transfer creation
────────────────────────────────────────────────────────────────

1. stock.picking.create({
       'picking_type_id': internal_type,
       'location_id': source_location,
       'location_dest_id': dest_location,
       'location_id': ...
     })
   │
   ├─► 2. `picking_type_id` resolved to 'internal' type
   │     └─► 3. `location_id` set to source internal location
   │     └─► 4. `location_dest_id` set to destination internal location
   │     └─► 5. `origin` optionally set (reference document)
   │     └─► 6. state = 'draft'
   │
   └─► 7. stock.move.create() for each product line
         ├─► 8. location_id = source location
         ├─► 9. location_dest_id = destination location
         ├─► 10. product_id, product_uom_qty set
         └─► 11. state = 'draft'

PATH B: Picking confirmation
────────────────────────────────────────────────────────────────

12. stock.picking.action_confirm()   [User clicks "Confirm"]
    │
    └─► 13. _action_confirm()
          ├─► 14. stock.move._action_confirm() for each move
          │     ├─► 15. move._check_company()
          │     ├─► 16. IF move_orig_ids (chained): wait for source moves
          │     └─► 17. move state = 'confirmed'
          └─► 18. picking state = 'confirmed'

PATH C: Availability / reservation check
────────────────────────────────────────────────────────────────

19. stock.picking.action_assign()   [User clicks "Check Availability"]
    │
    └─► 20. _action_assign()
          ├─► 21. stock.move._action_assign()
          │     ├─► 22. _do_unreserve() [clear any stale reservation]
          │     ├─► 23. _do_prepare_constrained_moves() [route/constraint logic]
          │     ├─► 24. stock.quant._update_reserved_quantity(+qty) at source location
          │     │     └─► 25. stock.quant reserved_qty incremented
          │     │           └─► 26. Product now allocated to this internal transfer
          │     └─► 27. IF qty_available >= product_uom_qty:
          │            └─► 28. move state = 'assigned' → ready
          │           ELSE IF partial:
          │            └─► 29. move state = 'partially_available'
          │           ELSE:
          │            └─► 30. move state = 'waiting'
          │
          └─► 31. picking state updated to 'assigned' or 'confirmed'

PATH D: User registers quantities transferred
────────────────────────────────────────────────────────────────

    └─► 32. stock.move.line create/update
          ├─► 33. qty_done set on move lines
          └─► 34. IF lot/serial tracked:
                    └─► lot_id assigned per line — required before done

PATH E: Validation (user clicks "Validate")
────────────────────────────────────────────────────────────────

35. stock.picking.action_done()   [User clicks "Validate"]
    │
    └─► 36. _button_validate()
          ├─► 37. IF immediate_transfer == False:
          │      └─► 38. wizard: `stock.immediate.transfer` shown
          │            └─► 39. re-call action_done() with immediate=True
          │
          └─► 40. _action_done()
                ├─► 41. stock.move.action_done()
                │     └─► 42. _action_done() per move
                │           ├─► 43. qty_done validated vs product_uom_qty
                │           ├─► 44. IF partial: backorder created for remainder
                │           ├─► 45. stock.quant._update_reserved_quantity(-reserved_qty) at source
                │           │     └─► 46. reserved_qty released at source location
                │           ├─► 47. stock.quant._update_available_quantity(-qty) at source location
                │           │     └─► 48. available qty DECREASED at source (stock leaves)
                │           ├─► 49. stock.quant._update_available_quantity(+qty) at dest location
                │           │     └─► 50. available qty INCREASED at destination
                │           ├─► 51. IF valuation enabled: stock.valuation.layer created
                │           │     └─► 52. account.move.line created (no net GL effect — same company)
                │           └─► 53. move state = 'done'
                │
                └─► 54. picking state = 'done'

PATH F: Multi-step routing (if warehouse uses multi-step routes)
────────────────────────────────────────────────────────────────

    └─► 55. Intermediate picking created (type: internal)
          ├─► 56. Source → Staging location (e.g., QC zone, input zone)
          └─► 57. Second picking: Staging → Final destination
                └─► Each step follows Paths B–E above

PATH G: Post-transfer side effects
─────────────────────────────────

    └─► 58. IF qty_done < product_uom_qty:
           └─► 59. Backorder picking created for remainder
    └─► 60. `stock.move._action_done()` post-processing hooks
    └─► 61. Mail notification (if enabled, to followers)
```

---

## Decision Tree

```
User creates internal transfer
│
├─► Is warehouse configured for multi-step routes?
│  ├─► YES → picking is split into two (or three) internal pickings
│  │        └─► First: Source → Staging/QC location
│  │        └─► Second: Staging → Final destination
│  │        └─► Each requires separate confirmation/validation
│  └─► NO → single-step direct transfer
│
├─► Is product available in source location?
│  ├─► YES (full qty) → immediate assign → state = 'assigned'
│  ├─► PARTIAL → state = 'partially_available' → partial transfer possible
│  └─► NO → state = 'waiting' → transfer waits for stock to arrive
│
└─► Lot/serial tracked?
   └─► Lot MUST be assigned per line before done

User clicks "Validate"
│
├─► Full qty transferred?
│  ├─► YES → transfer complete, no backorder
│  └─► NO → backorder for remainder (optional: user choice)
│
└─► Valuation?
   └─► Same product in same company: no GL entry (internal move, no change in value)
   └─► Different cost layer at dest location: valuation layer created
```

---

## Database State After Completion

| Table | Record Created/Updated | Key Fields |
|-------|----------------------|------------|
| `stock_picking` | Created, `state = 'done'` | `picking_type_id = internal`, `location_id`, `location_dest_id` |
| `stock_move` | Created per line, `state = 'done'` | `product_id`, `product_uom_qty`, `quantity_done`, `location_id`, `location_dest_id` |
| `stock_move_line` | Created/updated | `qty_done`, `lot_id` (if tracked), `location_id`, `location_dest_id` |
| `stock_quant` at source | Updated: `quantity -= qty`, `reserved_quantity` released | `product_id`, `location_id = source`, `quantity` |
| `stock_quant` at destination | Updated: `quantity += qty` | `product_id`, `location_id = dest`, `quantity` |
| `stock_valuation_layer` | Created (if valuation enabled) | Records value moved between locations |
| `account_move_line` | Created in pairs (if valuation) | Dr/Cr entries that net to zero — value moves with product |
| `stock_backorder` | Created if partial transfer | Backorder picking with remaining qty |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Reason |
|----------|-------------|---------------------|
| No stock at source location | `UserError: "Not enough inventory"` | `_update_reserved_quantity()` finds zero available quants at source |
| Product is lot/serial tracked but lot not assigned | `UserError: "You need to supply Lot/Serial number"` | `_action_done()` validates tracked products |
| qty_done > product_uom_qty without backorder | `UserError: "Done quantity exceeds reserved quantity"` | `_action_done()` enforces qty limits |
| Source or destination location is the same | `UserError: "Source and destination location cannot be the same"` | `stock.picking._check_locations()` constraint |
| Picking already done or cancelled | `UserError: "Picking is already done"` | Guard in `action_done()` |
| Access rights — user cannot transfer | `AccessError` | `group_stock_user` on Validate button |
| Location inactive | `ValidationError` | `location.active` check |
| Source location in different company | `AccessError` | `company_id` constraint — cross-company not allowed |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Stock quant at source decreased | `stock.quant` | `quantity` decremented at source internal location |
| Stock quant at destination increased | `stock.quant` | `quantity` incremented at destination internal location |
| Reserved quantity released | `stock.quant` | `reserved_quantity` decremented at source (unreserve) |
| Lot/serial moved | `stock.lot` | Lot location updated if lot-tracking per location enabled |
| Valuation layer created | `stock.valuation.layer` | Records unit cost at moment of transfer (for FIFO) |
| GL entries created in pairs | `account.move.line` | Dr from source location account, Cr to destination — net zero |
| Backorder created | `stock.picking` | New internal picking with remaining qty |
| Quant inventory value preserved | stock move | Cost layer follows product to destination location |

---

## Security Context

> *Which user context the flow runs under, and what access rights are required at each step.*

| Step | Security Mode | Access Required | Notes |
|------|-------------|----------------|-------|
| `stock.picking.create()` (manual) | Current user | `group_stock_user` | User creates transfer via UI |
| `stock.move.create()` (manual lines) | Current user | `group_stock_user` | Via picking form |
| `stock.picking.action_confirm()` | Current user | `group_stock_user` | Button-level security |
| `_action_assign()` | `sudo()` (system) | System | Writes to `stock.quant` reserved_quantity |
| `stock.quant._update_reserved_quantity()` | `sudo()` (system) | System | Must update reserved qty |
| `stock.picking.action_done()` | Current user | `group_stock_user` | Validate button |
| `_action_done()` | `sudo()` (system) | System | Updates quants at both locations |
| `stock.quant._update_available_quantity()` | `sudo()` (system) | System | Decrements source, increments destination |
| `account.move.line` creation | `sudo()` (system) | System (if valuation enabled) | Paired entries net zero |

**Key principle:** Internal transfers are unique in that they always respect the current user's ACL for creation and validation. The source/destination locations must be accessible to the user's company. Only the quant update steps use `sudo()` (system).

---

## Transaction Boundary

> *Which steps are inside the database transaction and which are outside. Critical for understanding atomicity and rollback behavior.*

```
Steps 1–11  ✅ INSIDE transaction  — picking and move creation
Steps 12–18 ✅ INSIDE transaction  — picking confirm
Steps 19–31 ✅ INSIDE transaction  — availability check (reservation is atomic)
Steps 32–34 ✅ INSIDE transaction  — user registers qty
Steps 35–54 ✅ INSIDE transaction  — validation + quant updates at both locations
Steps 58–59 ✅ INSIDE transaction  — backorder creation
Step 61     ❌ OUTSIDE transaction — mail notification queued
```

| Step | Boundary | Behavior on Failure |
|------|----------|-------------------|
| Steps 1–54 | ✅ Atomic | Rollback on any error — quants at both locations revert |
| `stock.quant._update_available_quantity()` at source | ✅ Atomic | Decrement rolled back |
| `stock.quant._update_available_quantity()` at destination | ✅ Atomic | Increment rolled back |
| `account.move.line` creation | ✅ Atomic | Paired GL entries rolled back together |
| Backorder creation | ✅ Atomic | Created in same transaction |
| `mail.mail` notification | ❌ Async queue | Retried by `ir.mail_server` cron |

**Rule of thumb:** Internal transfer is fully atomic — both the decrement at source and increment at destination are rolled back together if any error occurs. There is no cross-location inconsistency risk within Odoo's transaction model.

---

## Idempotency

> *What happens when this flow is executed multiple times (double-click, race condition, re-trigger).*

| Scenario | Behavior |
|----------|----------|
| Double-click "Validate" button | Second call hits guard: `if self.state == 'done': return True` — no-op |
| Re-trigger `action_done()` on done picking | No-op — state already 'done', quants already moved |
| Re-run `action_assign()` on assigned picking | No-op — quants already reserved |
| Concurrent validation from two sessions | First write wins; second raises `UserError: "Picking is already done"` |
| Re-create identical internal transfer | New picking created — transfer is not deduplicated |
| Transfer to same location as source (same picking re-done) | Prevented: `_check_locations()` validates source != destination |

**Common patterns:**
- **Idempotent:** `action_done()` (state guard), `action_assign()` (skips if already assigned)
- **Non-idempotent:** `stock.quant._update_available_quantity()` (quantity moved each time — double transfer would double-count), `stock.valuation.layer.create()` (new layer per transfer)

---

## Extension Points

> *Where and how developers can override or extend this flow. Critical for understanding Odoo's inheritance model.*

| Step | Hook Method | Purpose | Arguments | Override Pattern |
|------|-------------|---------|-----------|-----------------|
| Step 7 | `_get_picking_values()` | Customize picking creation | `self` | Override vals dict for custom location/rules |
| Step 7 | `stock.move.create()` | Add custom move lines | `self` | Override `_prepare_stock_moves()` |
| Step 14 | `_prepare_stock_moves()` | Customize move vals | `self` | Return custom vals dict |
| Step 24 | `_update_reserved_quantity()` | Custom reservation at source | `self, product_id, qty, location` | Override for custom source selection |
| Step 47 | `_update_available_quantity(-)` | Custom qty decrement at source | `self, product_id, qty, location` | Override for custom source logic |
| Step 49 | `_update_available_quantity(+)` | Custom qty increment at destination | `self, product_id, qty, location` | Override for custom dest logic |
| Step 51 | `_create_valuation_layer()` | Custom valuation layer | `self, move` | Override for cost tracking customization |
| Post-done | `_after_move_done()` | Post-transfer side effects | `self` | Called after move state = 'done' |
| Pre-validation | `_check_locations()` | Validate source != destination | `self` | Already in Odoo — add additional checks |
| Multi-step | `stock.route.rule` | Custom multi-step routing | `self, location, ...` | Override for custom route logic |

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
- `stock.move._action_done()` is the core move-done logic for internal transfers
- `stock.picking._action_assign()` — internal transfers use standard reservation from source location
- Valuation layers for internal moves are created but GL entries net to zero (Dr = Cr)
- Multi-step routing is controlled by `stock.location.route` — configure on warehouse

**Deprecated override points to avoid:**
- `@api.multi` on overridden methods (deprecated in Odoo 19)
- `@api.one` anywhere (deprecated)
- Direct `_workflow` calls (deprecated)
- Overriding without calling `super()` — breaks dual-location quant tracking

---

## Reverse / Undo Flow

> *How to cancel or reverse this flow. Critical for understanding what is and isn't reversible.*

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| `stock.picking.action_done()` | **Return transfer** | Create new internal transfer (reverse direction) | Create transfer from destination back to source |
| Picking in `confirmed/assigned` | `action_cancel()` | `stock.picking.action_cancel()` | Unreserves quants, cancels moves |
| Picking in `draft` | `action_draft()` or `action_cancel()` | `stock.picking.action_draft()` | Resets to draft |
| `action_cancel()` on picking | `action_draft()` | `stock.picking.action_draft()` | Resets to draft; quants unreserved |
| Multi-step transfer partially done | Complete remaining steps | Standard validation on remaining pickings | Each step is independent |
| Stock already transferred | **Create reverse transfer** | New `stock.picking` (internal, reverse direction) | Original remains `done`; new transfer moves qty back |

**Important:** Internal transfers are **fully reversible** via a reverse transfer:
- Original: Source location A → Destination location B (qty moved from A to B)
- Reverse: Source location B → Destination location A (qty moved back from B to A)
- Both pickings remain `done` — they represent the complete history of stock movements
- If `stock_account` is installed: the reverse transfer creates counter-journal entries that net the original GL entries to zero
- There is no "undo" button — a new reverse picking must be created

**Return Picking Wizard:**
- The standard `stock.return.picking` wizard also works for internal transfers
- It creates a new picking in the opposite direction

---

## Alternative Triggers

> *All the ways this flow can be initiated — not just the primary user action.*

| Trigger Type | Method / Endpoint | Context | Frequency |
|-------------|------------------|---------|-----------|
| Manual creation | Stock > Transfers > Create Transfer | Stock UI | Manual |
| Route-based intermediate | `stock.rule` with internal route | Warehouse routes | Automatic when parent picking created |
| Inventory adjustment | `stock.inventory` reconciliation | Stock UI | Manual or scheduled |
| Return picking wizard | `stock.return.picking` wizard | Stock UI | Manual |
| Immediate transfer wizard | `stock.immediate.transfer` | Stock UI | Manual |
| EDI / API | External system POSTs internal transfer | Web service | On demand |
| Scheduled scrap/waste | `stock.scrap` wizard | Stock UI | Manual |

**For AI reasoning:** Internal transfers are the building block for all complex stock movements. Multi-step routes (two-step receipt, two-step delivery) are built from chains of internal transfers between internal locations (Input → Stock, Stock → Output).

---

## Related

- [Modules/Stock](odoo-18/Modules/stock.md) — Stock/picking module reference
- [Flows/Stock/picking-action-flow](odoo-19/Flows/Stock/picking-action-flow.md) — Generic picking lifecycle (confirm→assign→done)
- [Flows/Stock/delivery-flow](odoo-19/Flows/Stock/delivery-flow.md) — Outgoing delivery (similar logic, external destination)
- [Flows/Stock/receipt-flow](odoo-17/Flows/Stock/receipt-flow.md) — Incoming receipt (similar logic, external source)
- [Patterns/Workflow Patterns](odoo-18/Patterns/Workflow Patterns.md) — Workflow pattern reference
- [Core/API](odoo-18/Core/API.md) — @api decorator patterns
