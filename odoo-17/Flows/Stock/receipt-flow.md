---
tags: [odoo, odoo17, flow, stock]
---

# Stock Receipt Flow

## Overview

Receiving goods from a vendor into the warehouse. Triggered by a confirmed **Purchase Order** (PO) or created manually.

## Actors

- Warehouse operator (receives goods)
- Vendor (delivers goods)
- Accountant (matches vendor bill against receipt)

## Prerequisites

- `stock` module installed
- `purchase` module installed (for PO-triggered receipts)
- Warehouse configured with at least one location (`stock.warehouse`)
- Products defined with `type = "product"` (storable)
- Vendor set up in `res.partner`

---

## Step-by-Step Flow

### Step 1: Purchase Order Confirmation

A **Purchase Order** is confirmed (status: `Purchase Order` → `Purchase Order confirmed`).

This triggers the procurement engine:

1. PO line generates a procurement (`procurement.group`)
2. Procurement evaluates the product's routes
3. A **procurement rule** (`stock.rule`, action=`pull`) fires
4. Creates a `stock.picking` with:
   - `picking_type_id`: Receipt (code=`incoming`)
   - `location_id`: Vendor location (`stock.location` usage=`supplier`)
   - `location_dest_id`: Warehouse's `lot_stock_id`
   - One `stock.move` per PO line

**Result:** Picking created in `draft` or `confirmed` state.

### Step 2: Operator Opens the Picking

The warehouse operator navigates to **Inventory > Receipts** (or the specific picking via the PO).

The picking shows:
- Source: Vendor
- Destination: Warehouse stock location
- Lines: One move per product on the PO

### Step 3: Check Availability (Optional)

Clicking **Check Availability** (`move_ids._action_assign()`):

1. System searches `stock.quant` records at the source location
2. Matches by product, lot (if tracked), and package
3. Reserves the matching quants
4. Move state transitions: `confirmed` → `partially_available` or `assigned`
5. `reserved_quantity` is set on matching `stock.quant` records

> For incoming receipts from vendor, availability is not checked at source (vendor location is empty). This step is more relevant for internal transfers.

### Step 4: Receive Goods (Detailed Operations)

User clicks **Validate** or **Open Detailed Operations** to enter quantities.

For products with **lot tracking** (`tracking = 'lot'`):
- User must select or create a lot number
- Use **Create Lots/Serial Numbers** or **Use Existing Lots** based on picking type settings

For products with **serial tracking** (`tracking = 'serial'`):
- Each unit gets a unique serial number
- User enters/assigns one serial per unit

For products **without tracking**:
- Enter the quantity received directly on the move line

### Step 5: Validate (button_validate)

**Source:** `stock_picking.py`, line 1134

```
button_validate()
  ├─ _sanity_check()          # line 1090 — no empty picking, lots assigned
  ├─ _pre_action_done_hook()  # run any pre-validation wizards
  └─ _action_done()           # line 978
       └─ stock.move._action_done()  # stock_move.py, line 1909
```

#### Inside `stock.move._action_done()` (line 1909):

1. **Confirm draft moves** — calls `_action_confirm(merge=False)`
2. **Cancel non-picked moves** — moves without quantity are cancelled (unless `is_inventory`)
3. **Extra moves** — if user entered more than PO quantity, create extra move lines
4. **Split for backorder** — if received < PO quantity:
   - `stock.move._split()` creates a backorder move for the remaining qty
   - Backorder picking (`backorder_id`) is created for remaining
5. **Execute move lines** — `move_line_ids._action_done()`:
   - Creates or updates `stock.quant` records at `location_dest_id`
   - Quant identity: `(product_id, location_dest_id, lot_id, package_id, owner_id)`
6. **State update** — all moves and the picking go to `done`
7. **Downstream triggers** — `_action_assign()` called on `move_dest_ids`
8. **Backorder creation** — `picking._create_backorder()` if partial

### Step 6: Quant Creation

When move lines are executed, `stock.quant` records are created/updated:

```
For each stock.move.line being done:
  1. Determine quant identity tuple:
     (product_id, location_dest_id, lot_id, package_id, owner_id)
  2. If matching quant exists at destination:
       quantity += move_line.quantity
  3. Else:
       Create new stock.quant with quantity = move_line.quantity
  4. in_date set to now()
```

### Step 7: Inventory Valuation (if stock_account installed)

If `stock_account` module is active:

- Each quant creation triggers an `account.move` (journal entry)
- Debit: Inventory asset account (from product category)
- Credit: Stock Received But Not Billed (or PO payables account)
- Valuation uses `price_unit` from the move or the product's cost

---

## Receipt Picking States

```
draft ──(action_confirm)──> confirmed ──(availability)──> assigned ──(validate)──> done
```

| State | Meaning |
|-------|---------|
| `draft` | Picking created but not confirmed |
| `confirmed` | Move confirmed, waiting for availability |
| `assigned` | All products are reserved |
| `done` | Validated — quants updated |
| `cancel` | Cancelled |

---

## Backorder Handling

When received quantity < expected quantity:

1. User clicks **Validate** (default: `ask`)
2. Dialog: "Do you want to create a backorder?"
3. If **Create Backorder**: new `stock.picking` created for remaining qty
4. If **No Backorder**: remaining moves are cancelled

The backorder picking is linked via `backorder_id` field.

---

## Key Methods Reference

| Method | File | Line | Purpose |
|--------|------|------|---------|
| `button_validate()` | stock_picking.py | 1134 | Entry point for validation |
| `_action_done()` | stock_picking.py | 978 | Delegates to stock.move |
| `_sanity_check()` | stock_picking.py | 1090 | Validates before validation |
| `_action_done()` | stock_move.py | 1909 | Executes the stock move |
| `_action_done()` | stock_move_line.py | — | Creates/updates quants |
| `_create_backorder()` | stock_picking.py | — | Splits remaining into new picking |

---

## Return Receipt Flow

When goods are returned to vendor:

1. From the original receipt, click **Return** (`stock.return.picking`)
2. System creates a return picking:
   - Swaps `location_id` and `location_dest_id`
   - Links via `return_id` / `return_ids`
3. Return picking follows the same validation flow
4. Quants at vendor location are updated

---

## See Also

- [Modules/stock](stock.md) — Full stock module reference
- [Modules/purchase](purchase.md) — Purchase order workflow
- [Modules/account](account.md) — Vendor bill matching
- [Flows/Stock/delivery-flow](Flows/Stock/delivery-flow.md) — Outgoing delivery flow
