# MRP Production (Manufacturing Order) - L3 Documentation

**Source:** `/Users/tri-mac/odoo/odoo18/odoo/addons/mrp/models/mrp_production.py`
**Lines:** ~3010
**Inherits:** `mail.thread`, `mail.activity.mixin`, `product.catalog.mixin`

---

## Model Overview

`mrp.production` is the central model for Manufacturing Orders (MOs). It manages the full production lifecycle from draft through done/cancelled, including BOM explosion, workorder scheduling, move generation, and cost calculation. It integrates with stock moves, workorders, and the product catalog.

---

## Fields

### Identity & Classification
| Field | Type | Notes |
|---|---|---|
| `name` | Char | Auto-generated (sequence); used as display name |
| `origin` | Char | Source document (SO, PO, etc.) |
| `company_id` | Many2one | `res.company` |
| `user_id` | Many2one | `res.users`; production responsible |
| `picking_type_id` | Many2one | `stock.picking.type`; defines operation type |
| `location_src_id` | Many2one | `stock.location`; raw material source |
| `location_dest_id` | Many2one | `stock.location`; finished product destination |
| `is_locked` | Boolean | Locks the MO to prevent editing after picking |
| `allow_workorder_dependencies` | Boolean | Enable workorder dependency chains |
| `show_final_lots` | Boolean | Show lot tracking on finished products |

### Product & Quantity
| Field | Type | Notes |
|---|---|---|
| `product_id` | Many2one | `product.product`; product being manufactured |
| `product_tmpl_id` | Many2one | `product.template`; derived from product_id |
| `product_qty` | Float | Quantity to produce |
| `product_uom_id` | Many2one | `uom.uom`; unit of measure |
| `qty_producing` | Float | Quantity currently being produced |
| `lot_producing_id` | Many2one | `stock.lot`; lot assigned to finished product |
| `consume_quality_check` | Boolean | Trigger quality checks on component consumption |
| `produce_line_ids` | One2many | Quality check lines for finished product |
| `move_line_ids` | One2many | Consumed component move lines |

### Bill of Materials
| Field | Type | Notes |
|---|---|---|
| `bom_id` | Many2one | `mrp.bom`; bill of materials used |
| `bom_ready_to_produce` | Selection | Computed from `bom_id.ready_to_produce` |
| `construction` | Char | Free-text description (alternative to BoM) |

### State Machine
| Field | Type | Notes |
|---|---|---|
| `state` | Selection | `'draft'`, `'confirmed'`, `'planned'`, `'progress'`, `'done'`, `'cancel'` |
| `priority` | Selection | `'0'` (normal) to `'1'` (urgent) |

### Scheduling
| Field | Type | Notes |
|---|---|---|
| `date_start` | Datetime | Scheduled/planned start time |
| `date_finished` | Datetime | Scheduled/planned finish time |
| `date_deadline` | Datetime | Manufacturing deadline |
| `scheduled_date` | Datetime | Resolved date (date_start or earliest workorder start) |

### Movements
| Field | Type | Notes |
|---|---|---|
| `move_raw_ids` | One2many | `stock.move`; component consumption moves |
| `move_finished_ids` | One2many | `stock.move`; finished product moves |
| `workorder_ids` | One2many | `mrp.workorder`; work orders |
| `move_raw_ids_related` | Many2many | Related moves (mirrors move_raw_ids for catalog) |

### Scrap
| Field | Type | Notes |
|---|---|---|
| `scrap_ids` | One2many | `stock.scrap`; scrap records |
| `scrap_count` | Integer | Count of scrap records |

### Costing
| Field | Type | Notes |
|---|---|---|
| `extra_cost` | Float | Additional operation cost |
| `analytic_account_id` | Many2one | `account.analytic.account`; cost analysis |
| `mrp_production_calculation` | Many2one | Cost calculation reference |

---

## State Transitions

```
draft -> confirmed -> planned -> progress -> done
   \                  \           \
    \-> cancel          \-> cancel   \-> cancel
```

### State Definitions
- **`draft`**: Initial state; MO not confirmed
- **`confirmed`**: BOM exploded, stock moves created (but not reserved)
- **`planned`**: Workorders scheduled, moves reserved
- **`progress`**: Production started; at least one workorder done or qty_producing set
- **`done`**: Production completed; moves confirmed
- **`cancel`**: MO cancelled; moves cancelled

### `action_draft()`
Resets MO to draft state. Uncancels moves and workorders.

### `action_confirm()`
Conirms the MO. Triggers:
1. `_compute_move_raw_ids()` — creates stock moves from BoM lines
2. `_compute_move_finished_ids()` — creates finished product stock moves
3. `_compute_workorder_ids()` — creates workorders from routing

### `action_plan()`
Plans the MO. Triggers:
1. `_plan_workorders()` — schedules workorders on workcenters

### `action_start()`
Starts the MO. Triggers:
1. Sets `state = 'progress'`
2. `_generate_moves()` — ensures all component moves exist
3. Opens a wizard to set lot_producing_id and qty_producing if needed

### `action_produce()`
**Primary production completion method.**
Logic:
1. Validates `qty_producing` against `product_qty`
2. For `'finish'`
   a. Calls `_post_inventory()` to confirm finished product moves
   b. Sets lot serial number if `lot_producing_id` not set
   c. Validates consumed components via quality checks
3. For `'all'`
   a. Calls `_post_inventory()` for all moves
   b. Validates quality checks
4. If `backorder`:
   a. Creates a new draft MO for the remaining qty
   b. Splits moves via `_generate_backorder_production_lot()`
5. Calls `_cal_price()` to compute unit cost
6. Sets `state = 'done'`

### `action_cancel()`
Cancels the MO. Triggers:
1. Cancels all moves (`move_raw_ids` and `move_finished_ids`)
2. Cancels all workorders
3. Sets `state = 'cancel'`

### `action_unreserve()`
Unreserves all stock moves (raw materials).

---

## Key Methods

### `_compute_move_raw_ids()`
Creates `stock.move` records from BoM lines for the MO.
**Logic:**
1. Explodes `bom_id` recursively via `bom_id.explode(product_id, product_qty)`.
2. Filters out byproducts (moves with `cost_share > 0`).
3. Creates one move per exploded BoM line.
4. Sets `location_id` from MO's `location_src_id`.

**Failure modes:**
- If `bom_id` is not set and `construction` is empty, no moves are created.
- BoM with type `phantom` is fully exploded; type `normal` creates direct moves.

### `_compute_move_finished_ids()`
Creates finished product stock move.
**Logic:**
1. Creates a move for `product_id` with `product_qty`.
2. Sets `location_dest_id` from MO's `location_dest_id`.
3. If `byproduct_ids` exist on BoM, creates byproduct moves.

### `_post_inventory()`
Confirms and processes stock moves.
**Logic:**
1. Splits moves into: `done` (already confirmed), `to_do` (not picked), `to_cancel` (not picked).
2. Calls `_action_done()` on `to_do` moves (confirms and validates quantities).
3. Cancels `to_cancel` moves.
4. For each finished product move: sets quantity to `qty_producing - qty_produced`.
5. Calls `_prepare_finished_extra_vals()` for lot/serial data.
6. Updates move line quantities.

**Critical edge case:** If `qty_producing < qty_produced`, raises `UserError`. The finished move quantity must be positive.

### `_cal_price()`
Computes the unit cost of the manufactured product.
**Logic:**
1. Sums `amount` from all confirmed `mrp.workorder` records.
2. Adds `extra_cost`.
3. Divided by `qty_producing` (or `product_qty` if not set).
4. Writes `standard_price` on `product_id` via `product_id.with_context(force_computation=True).write({'standard_price': unit_cost})`.

**Warning:** This overwrites the product's standard price globally. This can affect all other MOs and valuation.

### `_update_bom_lines_and_stock_moves()`
Called on production write to update BoM-linked moves.
**Logic:**
1. Detects BoM changes.
2. Re-explodes the BoM if quantity changed.
3. Cancels removed BoM lines.
4. Creates new moves for added BoM lines.

### `_generate_backorder_production_lot(moves_todo, cancel_backorder)`
Splits an MO into a backorder.
**Logic:**
1. Duplicates the production record as a draft.
2. Sets the original MO's `lot_producing_id` to the new backorder.
3. Adjusts move quantities to match what was produced vs what remains.
4. Returns the backorder MO.

**Failure modes:**
- If `_generate_backorder_production_lot` is called multiple times on the same MO, each call creates a new backorder with a new `lot_producing_id`, potentially creating duplicate lots.

### `copy_data(default=None)`
**Special behavior:**
- Clears `lot_producing_id`, `lot_producing_id` on copy.
- Decrements the sequence number in the generated name.
- Sets `origin` to reference the original MO.

### `_get_production_date_value()`
Returns `date_start` or `scheduled_date` for scheduling calculations.

---

## Workorder Integration

- `workorder_ids` is created from `bom_id.routing_id.operation_ids`.
- Each workorder references a `mrp.routing.workcenter` record.
- `_plan_workorders()` schedules workorders sequentially based on workcenter availability.
- `_compute_workorder_ids()` creates workorders if routing operations exist.

---

## Cross-Model Relationships

### With `mrp.bom`
- `bom_id`: The BoM driving move creation and workorder generation.
- `_check_explode_bom()` validates the BoM is appropriate for the product.

### With `stock.move`
- `move_raw_ids`: Component consumption moves (type `mrp_production`)
- `move_finished_ids`: Finished product moves (type `mrp_production`)
- Moves are created with `raw_material_production_id` and `production_id` back-references.

### With `mrp.workorder`
- `workorder_ids`: Work orders derived from routing operations.
- Workorder state drives `production.state` (when first workorder starts: `progress`).

### With `stock.picking`
- `_create_picking_from_bom()` creates a delivery picking for components if the BoM specifies `picking_type_id`.

---

## Edge Cases & Failure Modes

1. **`qty_producing > product_qty`:** Allowed; the MO can overproduce. Move quantities will be set to `qty_producing`.
2. **`lot_producing_id` and serial tracking:** If `product_id.tracking='serial'`, each unit requires a separate lot. Odoo enforces `qty_producing=1` in this case.
3. **BoM explosion with phantom BoMs:** Phantom BoMs are fully exploded recursively. If a component of a phantom BoM is also a phantom, it continues until a non-phantom is reached.
4. **Consuming more than available:** If component stock is insufficient, `_action_generate_moves()` creates moves in `assigned` or `confirmed` state. The production can still be confirmed; reservation failure does not block confirmation.
5. **MO with no BoM:** `move_raw_ids` and `workorder_ids` remain empty. User must manually set moves or assign a BoM.
6. **Cost calculation race condition:** Multiple concurrent `action_produce()` calls on the same MO can overwrite each other's `_cal_price()` result.
7. **Backorder creation:** The backorder mechanism creates a new MO via `copy_data()`. If the original MO had a name like `MO/001`, the backorder becomes `MO/001` and the original gets renamed — causing potential name collisions if name sequences are shared.
8. **Multi-company:** Each MO is tied to a `company_id`. Cross-company moves are prevented by location/warehouse security rules.
9. **Quality checks:** If `consume_quality_check=True` and a quality check fails, `_action_produce()` does not automatically block production — it depends on the check configuration.
10. **Cancel with done moves:** If some moves are already `done`, cancelling the MO does not revert those moves. Only `assigned` and `confirmed` moves are cancelled.
