# MRP Unbuild - L3 Documentation

**Source:** `/Users/tri-mac/odoo/odoo18/odoo/addons/mrp/models/mrp_unbuild.py`
**Lines:** ~339

---

## Model Overview

`mrp.unbuild` reverses a manufacturing order by consuming a finished product and producing back its components. It is used to disassemble finished goods or correct production errors. Unlike scrap, unbuild restores components to stock.

---

## Fields

| Field | Type | Notes |
|---|---|---|
| `name` | Char | Auto-generated name |
| `product_id` | Many2one | `product.product`; product to unbuild |
| `product_qty` | Float | Quantity to unbuild |
| `bom_id` | Many2one | `mrp.bom`; BoM to reverse |
| `mo_id` | Many2one | `mrp.production`; source manufacturing order |
| `lot_id` | Many2one | `stock.lot`; specific lot to unbuild |
| `location_id` | Many2one | `stock.location`; source location (where finished product is) |
| `location_dest_id` | Many2one | `stock.location`; destination (where components go) |
| `company_id` | Many2one | `res.company` |
| `state` | Selection | `'draft'`, `'done'` |
| `consume_line_ids` | One2many | `stock.move`; component consumption moves |
| `produce_line_ids` | One2many | `stock.move`; finished product consumption move |
| `analytic_account_id` | Many2one | `account.analytic.account`; cost attribution |

---

## Key Methods

### `action_unbuild()`
The main action that executes the unbuild.
**Steps:**
1. Validates `product_qty > 0`.
2. If `mo_id` is set and `bom_id` is not: uses `mo_id.bom_id` as `bom_id`.
3. Calls `_generate_consume_moves()`: creates consumption of the finished product (stock move).
4. Calls `_generate_produce_moves()`: creates production of the components (stock moves back to stock).
5. Confirms and reserves all generated moves.
6. Sets `state = 'done'`.

**Post-conditions:**
- Finished product is removed from `location_id`.
- Components are added to `location_dest_id`.

### `_generate_consume_moves()`
Creates stock moves that consume the finished product.
**Logic:**
1. If `mo_id` is set: generates moves from the MO's `move_finished_ids` filtered to the `product_id`.
2. If `lot_id` is set: uses only moves linked to that lot.
3. If `mo_id` is not set: generates a move directly from `bom_id`.
4. Uses `_generate_move_from_existing_move()` or `_generate_move_from_bom_line()`.

### `_generate_produce_moves()`
Creates stock moves that produce the components back into stock.
**Logic:**
1. If `mo_id` is set: generates moves from the MO's `move_raw_ids` (original component consumption).
2. If `lot_id` is set: filters to moves linked to that lot.
3. Handles lot tracking for components (tracking lots from the original production).
4. Uses `_generate_move_from_existing_move()` or `_generate_move_from_bom_line()`.
5. Sets `location_dest_id` to the unbuild's destination location.

### `_generate_move_from_existing_move(move)`
Creates a reverse move from an existing production move.
**Logic:**
1. Creates a new move with swapped source/destination.
2. Copies `product_uom_qty` from the original (consumed qty for finished product, produced qty for components).
3. Sets `location_id` / `location_dest_id` from the unbuild record.
4. **Lot tracking:** For serialized components, uses `_generate_move_from_existing_move_serial()` to generate one move per unit from the original lot's move lines.

### `_generate_move_from_bom_line(line, product_qty, byproduct=False)`
Creates a move from a BoM line.
**Logic:**
1. For byproducts: multiplies `product_qty` by `line.bom_line_id.product_qty / bom.product_qty`.
2. For regular components: `qty = product_qty × line.product_qty / self.bom_id.product_qty`.
3. Creates a move with `location_dest_id = self.location_dest_id`.

**Edge case:** For byproducts with `cost_share > 0`, the byproduct is still produced (not treated as scrap).

---

## Lot Tracking in Unbuild

When `lot_id` is set:
1. The finished product lot is consumed.
2. For components produced from a serialized product:
   - If the original MO had `lot_producing_id` set, component moves are linked to that lot's move lines.
   - `_generate_move_from_existing_move_serial()` handles per-unit move creation.
3. For components with lot tracking: if the original production consumed tracked lots, those lots are restored via `_generate_move_from_existing_move()` with move line references.

### `qty_already_used defaultdict`
Used to handle lot reuse within a single unbuild operation. When multiple BoM lines consume the same lot, the `qty_already_used` dict tracks how much of the lot has already been allocated, preventing over-allocation.

---

## Edge Cases & Failure Modes

1. **Unbuild without MO:** If `mo_id` is not set, the system falls back to `bom_id`. If neither is set, no moves are generated and the operation silently fails (no error raised by `_generate_consume_moves`).
2. **Lot tracking on MO components:** If the original MO consumed components from specific lots but those lots have since been partially consumed by other transactions, the unbuild may not fully restore the original quantities.
3. **Negative stock after unbuild:** If the finished product is not in stock at `location_id`, the consumption move will be in `assigned` state but cannot be reserved. The unbuild will proceed but stock will go negative.
4. **MO already cancelled:** If `mo_id` is cancelled, `_generate_consume_moves()` still uses its moves (in `cancel` state) — but those moves won't be available for reservation. The unbuild may fail silently.
5. **Cost attribution:** Unbuild reverses the cost impact of production. The `_cal_price()` on the MO is not automatically reversed; the accounting impact depends on the cost calculation method and the `analytic_account_id` set on the unbuild.
6. **Partial unbuild:** `product_qty` can be less than the MO's `product_qty`. The system generates moves proportional to `product_qty / mo.product_qty`.
7. **BoM with byproducts:** Byproducts are included in `_generate_produce_moves()`. Cost share is respected — the byproduct is still produced even if its `cost_share > 0` (since unbuild reverses production, not just raw materials).
8. **Multiple unbuilds for same lot:** Each unbuild generates new moves. If the lot was already partially unbuilt, subsequent unbuilds use `qty_already_used` to prevent over-consuming the same lot.
9. **Unbuild of a product without BoM:** If the product has no active BoM, `_generate_produce_moves()` has no components to generate. The finished product is still consumed, but no components are restored.
10. **MO state is 'done':** Unbuild works with done MOs. The finished product moves are already done and won't be modified — only a new reverse move is created for the unbuild consumption.
