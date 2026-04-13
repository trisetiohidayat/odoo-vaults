---
type: flow
title: "Stock Valuation Flow"
primary_model: stock.move
trigger: "System — stock.move.action_done() / User — Validate Delivery/Receipt"
cross_module: true
models_touched:
  - stock.move
  - stock.move.line
  - stock.quant
  - stock.valuation.layer
  - product.category
  - account.move
  - account.move.line
  - product.product
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[Flows/Stock/receipt-flow](Flows/Stock/receipt-flow.md)"
  - "[Flows/Stock/delivery-flow](Flows/Stock/delivery-flow.md)"
  - "[Modules/stock_landed_costs](Modules/stock_landed_costs.md)"
source_module: stock_account
source_path: ~/odoo/odoo19/odoo/addons/stock_account/
created: 2026-04-07
updated: 2026-04-07
version: "1.0"
---

# Stock Valuation Flow

## Overview

The Stock Valuation Flow automatically creates accounting journal entries when inventory moves are validated (action_done). Odoo supports two valuation methods — **Real-Time** (automated journal entries on every move) and **Manual** (periodic valuation adjustment) — controlled by the `property_valuation` field on `product.category`. When real-time valuation is enabled, every done move generates a `stock.valuation.layer` and a corresponding `account.move` debit/credit pair, moving value from the Stock Interim account to the Stock Valuation account. The flow supports FIFO, AVCO (Average), and Standard Cost methods, and integrates with landed costs to add freight, duties, and handling fees to the inventory valuation.

---

## Trigger Point

**Primary trigger:** `stock.move.action_done()` is called when a user clicks **Validate** on a `stock.picking` (receipt, delivery, or transfer). This is a system-level trigger — no user action happens after clicking Validate besides the automatic cascade through the valuation logic.

**Secondary trigger:** `product.product._change_product_cost_price()` is called when a user updates the standard cost of a product via **Product → Cost** tab. This creates additional valuation layers for all quantities on hand and triggers revaluation journal entries.

**Periodic trigger:** `stock.valuation.layer._adjust_landed_cost()` is called by `ir.cron` to rebalance valuation for landed costs when additional costs are confirmed.

---

## Complete Method Chain

```
STEP 1 — stock.move.action_done()
───────────────────────────────────
1. stock.move.action_done()
      │
      ├─► 2. stock.move._action_done()
      │        ├─► 3. Move lines confirmed (qty_done set)
      │        ├─► 4. stock.move.write({'state': 'done'})
      │        └─► 5. _action_done() — routing based on move type
      │              ├─► 6. IF move_type == 'incoming':
      │              │      └─► receipt logic (Steps 7-15)
      │              └─► 7. IF move_type == 'outgoing':
      │                     └─► delivery logic (Steps 16-25)
      │
      └─► 8. stock.picking._compute_state()
            └─► 9. state = 'done'

STEP 2 — Incoming Move: Receipt Valuation
─────────────────────────────────────────
10. stock.move._action_done() on incoming
      │
      ├─► 11. stock.move.line._action_done()
      │        └─► 12. stock.quant._update_available_quantity(
                     product_id, location_id, qty_done, lot_id, ...
                   )
      │              ├─► 13. IF valuation == 'real_time':
      │              │      └─► 14. stock.valuation.layer.create({
      │              │                  product_id, stock_move_id,
      │              │                  quantity, unit_cost,
      │              │                  value = qty * unit_cost,
      │              │                  account_move_id=None (yet)
      │              │            })
      │              │              └─► 15. _create_account_move_line()
      │              │                    ├─► 16. stock_account.move_line_create(
      │              │                    │       move, quantity, value, location
      │              │                    │     )
      │              │                    │        └─► 17. account.move.create({
      │              │                    │                  move_type='entry',
      │              │                    │                  line_ids: [
      │              │                    │                    (0,0,{account_id: valuation_acc,
      │              │                    │                               debit: value,
      │              │                    │                               credit: 0}),
      │              │                    │                    (0,0,{account_id: interim_acc,
      │              │                    │                               debit: 0,
      │              │                    │                               credit: value})
      │              │                    │                  ]
      │              │                  })
      │              │                    └─► 18. stock.valuation.layer.write(
      │              │                          {account_move_id: new_move.id}
      │              │                    )
      │              │
      │              └─► 19. ELSE (manual valuation):
      │                     └─► No accounting entry; layer created without move_id
      │
      ├─► 20. product.product._change_product_cost_price(move)
      │        ├─► 21. IF product.cost_method == 'standard':
      │        │      └─► 22. Compute diff: (new_cost - old_cost) * qty_on_hand
      │        │            └─► 23. stock.valuation.layer.create() + journal entry
      │        │                  for revaluation difference
      │        └─► 23. ELSE: no cost change triggered
      │
      └─► 24. stock.quant._get_valued_inventory_lines(move)
              └─► 25. IF lot_id/serial_number:
                       └─► Create stock.move.line per lot (for traceability)

STEP 3 — Outgoing Move: Delivery Valuation
─────────────────────────────────────────
26. stock.move._action_done() on outgoing
      │
      ├─► 27. stock.move.line._action_done()
      │        └─► 28. stock.quant._update_available_quantity(
                     product_id, location_id, -qty_done, lot_id, ...
                   )
      │              ├─► 29. IF FIFO:
      │              │      └─► 30. stock.quant._consume_layer_fifo(
      │              │                  product_id, qty, location
      │              │            )
      │              │              └─► 31. Consume oldest (by create_date)
      │              │                    layer; value = layer.unit_cost * qty
      │              │                    └─► 32. stock.valuation.layer.create(
      │              │                          {quantity: -qty, unit_cost: avg_cost,
      │              │                           value: -value})
      │              │
      │              ├─► 33. IF AVCO:
      │              │      └─► 34. Compute weighted average:
      │              │            new_avg = (old_value + new_qty*cost) / (old_qty + new_qty)
      │              │            value_out = qty * current_avg_cost
      │              │            └─► 35. stock.valuation.layer.create()
      │              │
      │              └─► 36. IF standard:
      │                     └─► 37. value = qty * product.standard_price
      │                           └─► 38. stock.valuation.layer.create()
      │
      └─► 39. _create_account_move_line() — credit Stock, debit Stock Interim
             └─► 40. account.move.create() with:
                   line_ids: [
                     (0,0,{account_id: stock_valuation_acc, debit: value, credit: 0}),
                     (0,0,{account_id: stock_interim_acc,   debit: 0, credit: value})
                   ]

STEP 4 — Landed Costs: Additional Valuation
──────────────────────────────────────────
41. stock.landed.cost.create({
         picking_id: receipt_picking,
         cost_lines: [(freight, insurance, duty)],
         account_id: valuation_account
    })
      │
      ├─► 42. stock.landed.cost._button_validate()
      │        └─► 43. _create_accounting_entries()
      │              ├─► 44. Compute: total cost / total qty = unit_cost_addition
      │              ├─► 45. Add to existing valuation layers:
      │              │      layer.value += qty * unit_cost_addition
      │              └─► 46. account.move.create() — journal entry:
      │                    Dr: Stock Valuation account (additional cost)
      │                    Cr: Stock Landed Costs account (payable/expense)
      │
      └─► 47. stock.valuation.layer.write({value: new_layer_value})
            └─► 48. product.product.write({standard_price: updated})
                  └─► 49. If AVCO: recompute average cost
```

---

## Decision Tree

```
stock.move.action_done() called
            │
            ▼
    ┌─────────────────────┐
    │ Move type?          │
    └──────┬──────────────┘
            │
     ┌──────┴──────┐
     │incoming      │outgoing
     ▼              ▼
┌──────────┐  ┌────────────────────┐
│ Receipt  │  │ Delivery           │
│ (incoming)│  └──────────┬─────────┘
└────┬─────┘             │
     │              ┌────┴──────────────┐
     ▼              │ Valuation method?│
┌──────────┐        └────┬──────────────┘
│ Update   │        ┌─────┴──────┐
│ quant    │        │FIFO│AVCO│STD│
└────┬─────┘        └────┬──────┘
     │              ┌────┴───────┐
     ▼              │ Compute    │
┌────────────────┐  │ value_out  │
│ Valuation      │  │ from layer │
│ method?        │  └─────┬──────┘
└────┬───────────┘        │
┌────┴──────────┐          ▼
│real_time│manual│  ┌──────────────┐
└────┬──────────┘  │ Create       │
     │             │ valuation    │
     ▼             │ layer        │
┌──────────────┐  └──────┬───────┘
│ Create layer  │         │
│ + journal     │         ▼
│ entry          │  ┌──────────────┐
└────────────────┘  │ Create       │
                    │ account.move │
                    │ (Dr Stock Val │
                    │  Cr Interim) │
                    └──────────────┘

AVCO BRANCH: recompute average cost on every receipt
FIFO BRANCH: consume oldest layer; value = layer.unit_cost
STD BRANCH: value = product.standard_price (static until updated)

LANDED COST: applied after receipt, increases layer.value
             → revaluation journal entry: Dr Stock Val / Cr Payable
```

---

## Database State After Completion

| Table | Record Created/Updated | Key Fields |
|-------|----------------------|------------|
| `stock_move` | Updated | `state='done'`, `product_valuation_item_ids` |
| `stock_move_line` | Updated | `qty_done`, `state='done'` |
| `stock_quant` | Created/Updated | `product_id`, `location_id`, `quantity`, `reserved_quantity`, `layer_id` |
| `stock_valuation_layer` | Created | `product_id`, `quantity`, `unit_cost`, `value`, `account_move_id`, `stock_move_id` |
| `account_move` | Created | `move_type='entry'`, `ref='Valuation for: {move.name}'`, `state='posted'` |
| `account_move_line` | Created (2 lines) | One Dr (valuation account), one Cr (interim account) |
| `product_product` | Updated (if std cost change) | `standard_price` |
| `product_category` | Read | `property_valuation`, `property_cost_method`, `property_stock_valuation_account_id` |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Reason |
|----------|-------------|---------------------|
| No valuation account set on category | `UserError` "No valuation account defined on product category" | `property_stock_valuation_account_id` must be set when `property_valuation='real_time'` |
| Negative stock on delivery (FIFO/AVCO) | `UserError` "You cannot deliver a negative quantity" | `_update_available_quantity()` enforces `qty >= 0` unless `stock.allow_negative_stock` enabled |
| Wrong valuation method | No error, silent wrong valuation | AVCO vs FIFO vs Standard give different values — no runtime check |
| Inconsistent qty (quant mismatch) | `UserError` "Quantities are inconsistent" | Sum of `stock.quant.quantity` must equal sum of `stock.move.quantity` after done |
| Landed cost on non-receipt | `UserError` "Landed cost can only be added to receipts" | `stock.landed.cost` only links to incoming pickings |
| Cost method change mid-inventory | `UserError` "Costing method cannot be changed if valuations exist" | `product.category._check_cost_method_change()` prevents mid-stream changes |
| Currency mismatch on valuation | `ValidationError` "Currency mismatch" | `account.move` currency must match `company.currency_id` |
| No layer found for FIFO consume | `UserError` "No incoming stock to consume" | FIFO requires at least one positive layer before any outgoing |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Quant updated | `stock.quant` | `quantity` updated on receipt (+qty) or delivery (-qty) |
| Valuation layer created | `stock.valuation.layer` | Tracks: quantity, unit_cost, value, linked move |
| Journal entry created | `account.move` | `move_type='entry'` posted automatically |
| Cost recomputed | `product.product` | If `cost_method='average'`: `standard_price` updated |
| Stock report updated | `stock.history` | Inventory valuation report reflects new value |
| Landed cost allocation | `stock.valuation.layer` | Additional value added to existing layers |
| Lot traceability linked | `stock.production.lot` | Lot/serial number linked to valuation layer |

---

## Security Context

> *Which user context the flow runs under, and what access rights are required.*

| Step | Security Mode | Access Required | Notes |
|------|-------------|----------------|-------|
| `action_done()` | Current user | `group_stock_user` | User clicks Validate; respects record rules |
| `_action_done()` | `sudo()` | System | Internal move processing; bypasses ACL |
| `_update_available_quantity()` | `sudo()` | System | Writes to `stock.quant`; no user context |
| `_create_account_move_line()` | `sudo()` | System | Creates `account.move` entries; no ACL |
| `_change_product_cost_price()` | Current user | `product.product` write access | User changes cost on product form |
| `stock.landed.cost._button_validate()` | Current user | `group_stock_manager` | Validate landed cost button |
| `_get_valued_inventory_lines()` | `sudo()` | System | Read-only trace for lots/serials |

---

## Transaction Boundary

> *Which steps are inside the database transaction and which are outside.*

```
Steps 1-40   ✅ INSIDE transaction  — all done within action_done()
             account.move created with state='posted' inside same DB transaction
             Rollback on any error: move stays 'assigned', no quant updated

Steps 41-49  ✅ INSIDE transaction  — _button_validate() atomic
             Landed cost entries created in same transaction

Steps 50+    ❌ OUTSIDE transaction — ir.cron for periodic AVCO recompute
             (if configured)
```

| Step | Boundary | Behavior on Failure |
|------|----------|-------------------|
| `action_done()` through `_create_account_move_line()` | ✅ Atomic | Rollback: move reverts to 'assigned', no quant changes |
| `stock.landed.cost._button_validate()` | ✅ Atomic | Rollback: landed cost record stays in draft |
| `ir.cron` AVCO recompute | ❌ Outside | Re-computation via `product.product._compute_standard_price()` |
| Inventory valuation report | ✅ Within ORM | Computed from `stock.valuation.layer`; always consistent |

---

## Idempotency

> *What happens when this flow is executed multiple times.*

| Scenario | Behavior |
|----------|----------|
| Double-click Validate button | ORM creates move once; second click does nothing (state already 'done') |
| Re-process done move via button | `UserError` "Stock move already processed" — state machine prevents re-run |
| Same delivery reversed and re-done | Creates new layer with potentially different unit_cost (current date price) |
| FIFO layer partially consumed, re-run | Consumes next oldest layer portion — not duplicative |
| AVCO re-compute on already done moves | No new layers created; existing layers' `unit_cost` not modified |
| Landed cost added twice | Two separate landed cost records create two additional layers — risk of double-addition |

---

## Extension Points

> *Where and how developers can override or extend this flow.*

| Step | Hook Method | Purpose | Arguments | Override Pattern |
|------|-------------|---------|-----------|-----------------|
| Pre-valuation | `_do_unreserve()` | Modify before valuation | `self` | Extend before `_action_done()` |
| Layer creation | `_create_valuation_layer()` | Custom layer logic | `self`, `vals` | Override in `stock.quant` or `stock.move` |
| Value computation | `_value_by_cost_method()` | Custom AVCO/FIFO logic | `self`, `product` | Override for special costing (e.g., LIFO) |
| Journal entry | `_create_account_move_line()` | Custom accounts per product | `move`, `quantity`, `value` | Extend for multi-company cost allocation |
| Landed cost | `_create_accounting_entries()` | Add custom landed cost accounts | `self` | Extend for duty, insurance specific accounts |
| Cost update | `_change_product_cost_price()` | Trigger on cost change | `move` | Extend for integration with purchase price lists |

**Standard override pattern:**
```python
# Custom valuation account per product type
class StockMove(models.Model):
    _inherit = 'stock.move'

    def _prepare_account_move_line(
        self, move, credit_account_id, debit_account_id, qty, description, value
    ):
        self.ensure_one()
        # Route to different valuation accounts by product type
        if self.product_id.categ_id.l10n_id_product_type == 'finished_goods':
            debit_account_id = self.product_id.categ_id.property_stock_valuation_account_id.id
        elif self.product_id.categ_id.l10n_id_product_type == 'raw_material':
            debit_account_id = self.env.ref('l10n_id.stock_valuation_rm').id
        return super()._prepare_account_move_line(
            move, credit_account_id, debit_account_id, qty, description, value
        )
```

---

## Reverse / Undo Flow

> *How to cancel or reverse this flow.*

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| Move done (receipt) | Return goods | `stock.return.picking.create()` → new `stock.picking` | Creates reverse quant entry; new layer with negative qty |
| Move done (delivery) | Unbuild / return | `stock.return.picking` or `mrp.unbuild` | Outgoing layers not deleted; new receipt layer created |
| Valuation layer | NOT directly reversible | — | Layers are append-only; reversal via new compensating layer |
| Journal entry | `account.move` reversal | `account.move._reverse_moves()` | Creates opposite Dr/Cr; keeps audit trail |
| Landed cost | Cancel button | `stock.landed.cost.button_cancel()` | Reverses additional valuation entry |
| Cost change (standard) | Revert to old cost | `product.product.write({'standard_price': old})` | Triggers another revaluation layer |

**Important:** Valuation layers are **append-only** (no delete). Returns create new compensating layers. The journal entry can be reversed, but the reversal itself is a new entry.

---

## Alternative Triggers

> *All the ways this flow can be initiated.*

| Trigger Type | Method / Endpoint | Context | Frequency |
|-------------|------------------|---------|-----------|
| User action | `action_done()` | Validate picking button | Manual |
| Automatic transfer | `stock.picking._ action_assign()` + auto-validate | Rules-based | Rule-triggered |
| Receipt from PO | `purchase.order` receipt validation | Purchase → Validate receipt | Per PO |
| Delivery from SO | `sale.order` delivery validation | Sales → Validate delivery | Per SO |
| Landed cost | `stock.landed.cost._button_validate()` | Inventory → Landed Costs | Manual |
| Cost update | `product.product.write('standard_price')` | Product form save | Manual |
| Cron recompute | `stock.quant._recompute_product_cost_average()` | Nightly | Daily |

---

## Related

- [Modules/Stock](Modules/Stock.md) — `stock.move`, `stock.quant`, `stock.valuation.layer` field reference
- [Flows/Stock/receipt-flow](Flows/Stock/receipt-flow.md) — Purchase receipt from PO to quant
- [Flows/Stock/delivery-flow](Flows/Stock/delivery-flow.md) — Sales delivery from SO to quant
- [Modules/stock_landed_costs](Modules/stock_landed_costs.md) — Landed cost integration with valuation
- [Patterns/Workflow Patterns](Patterns/Workflow-Patterns.md) — State machine pattern in Odoo
- [Core/API](Core/API.md) — `@api.depends` decorator for computed fields
