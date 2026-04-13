# stock.picking — Transfer / Picking Model

**Source:** `~/odoo/odoo19/odoo/addons/stock/models/stock_picking.py`
**Odoo Version:** 19
**Model:** `stock.picking`
**Inheritance:** `mail.thread`, `mail.activity.mixin`
**Description:** "Transfer" — represents a stock move operation (receipt, delivery, or internal transfer). A picking contains `stock.move` records, each of which contains `stock.move.line` detailed operations.

---

## Module Context: Two Classes in One File

This file contains two models:
1. `StockPickingType` (`stock.picking.type`) — the configuration model for operation types
2. `StockPicking` (`stock.picking`) — the main transfer/picking model

This document focuses exclusively on `StockPicking`.

---

## L1: Field Index — All Fields Defined on `stock.picking`

### Identity & Naming

| Field | Type | Default | Index | Purpose |
|-------|------|---------|-------|---------|
| `name` | Char | `/` | trigram, readonly | Reference number assigned by `picking_type_id.sequence_id` |
| `origin` | Char | `False` | trigram | Source document reference (e.g., SO number, PO number) |
| `note` | Html | `False` | — | Internal notes (user-editable rich text) |
| `company_id` | Many2one | `picking_type_id.company_id` | btree | Operating company |
| `backorder_id` | Many2one | `False` | btree_not_null | Link to the original picking when this is a backorder |
| `backorder_ids` | One2many | — | — | Reverse link: all backorders created from this picking |
| `return_id` | Many2one | `False` | btree_not_null | Link to the original picking when this is a return |
| `return_ids` | One2many | — | — | Reverse link: all return pickings created from this one |
| `return_count` | Integer | computed | — | Count of return pickings |

### State & Workflow

| Field | Type | Purpose |
|-------|------|---------|
| `state` | Selection | Computed from move states. Values: `draft`, `waiting`, `confirmed`, `assigned`, `done`, `cancel`. **Stored, computed, not directly writable.** |
| `priority` | Selection | From `PROCUREMENT_PRIORITIES`: `'0'` (Normal), `'1'` (Urgent). Affects reservation ordering. Default `'0'`. |
| `move_type` | Selection | Shipping policy. Values: `direct` (As soon as possible), `one` (When all products are ready). Computed from `picking_type_id.move_type`. |
| `is_locked` | Boolean | Default `True`. When `False`, initial demand (product_uom_qty) can be changed. When picking is done, controls whether done quantities can be changed. |

### Dates

| Field | Type | Purpose |
|-------|------|---------|
| `scheduled_date` | Datetime | Scheduled processing date. Computed inverse: setting it writes to all non-cancelled/non-done move dates. Default: `Datetime.now()`. |
| `date_deadline` | Datetime | Earliest (for `direct`) or latest (for `one`) move deadline date. Computed from `move_ids.date_deadline`. |
| `date_done` | Datetime | Date when transfer was validated or cancelled. Set by `_action_done` or cancellation. |
| `delay_alert_date` | Datetime | Max delay alert date among all moves. Used for rescheduling popover. |
| `search_date_category` | Selection | Virtual field for search UI: `before`, `yesterday`, `today`, `day_1`, `day_2`, `after`. Read-only, searchable. |

### Location & Partner

| Field | Type | Purpose |
|-------|------|---------|
| `location_id` | Many2one | **Source location** for the transfer. Computed from `picking_type_id.default_location_src_id` at creation (draft state only). |
| `location_dest_id` | Many2one | **Destination location**. Computed from `picking_type_id.default_location_dest_id` at creation. |
| `partner_id` | Many2one | Contact partner. For incoming, used to set `property_stock_supplier`. For outgoing, used to set `property_stock_customer`. |
| `owner_id` | Many2one | Assigns ownership of products when the transfer is validated. `restrict_partner_id` is written to moves and move lines. |
| `warehouse_address_id` | Many2one | Related: `picking_type_id.warehouse_id.partner_id`. Convenience field for address display. |

### Moves & Operations

| Field | Type | Purpose |
|-------|------|---------|
| `move_ids` | One2many | All `stock.move` records belonging to this picking. `copy=True` — moves are copied when picking is duplicated. |
| `move_line_ids` | One2many | All `stock.move.line` detailed operation records. Inverse of `picking_id` on `stock.move.line`. |
| `picking_type_id` | Many2one | Operation type (Receipt, Delivery, Internal Transfer). Drives default locations, sequence, reservation method, and auto-print settings. |
| `picking_type_code` | Selection | Related shorthand: `picking_type_id.code`. Values: `incoming`, `outgoing`, `internal`. Read-only. |
| `picking_type_entire_packs` | Boolean | Related: `picking_type_id.show_entire_packs`. Read-only. |
| `use_create_lots` | Boolean | Related from picking type. Controls lot creation behavior. |
| `use_existing_lots` | Boolean | Related from picking type. Controls lot selection behavior. |
| `show_operations` | Boolean | Related from picking type. Controls whether detailed operations page is shown. |
| `show_lots_text` | Boolean | Computed. `True` when picking type uses `create_lots` but not `existing_lots` and state is not `done`. |

### Stock Quantities & Availability

| Field | Type | Purpose |
|-------|------|---------|
| `products_availability` | Char | Computed availability status string: "Available", "Not Available", "Exp YYYY-MM-DD". |
| `products_availability_state` | Selection | Computed: `available`, `expected`, `late`. Searchable. |
| `show_check_availability` | Boolean | Computed. `True` when "Check Availability" button should be shown (state in `waiting/confirmed/assigned` and some moves not yet picked). |
| `show_allocation` | Boolean | Computed. `True` when "Allocation" button should be shown. Only for incoming/internal pickings with moves needing allocation. |

### Packages & Weight

| Field | Type | Purpose |
|-------|------|---------|
| `packages_count` | Integer | Count of packages in the picking. Computed differently for done vs. non-done pickings. |
| `package_history_ids` | Many2many | Links to `stock.package.history` for done pickings. Records package transfer history. |
| `weight_bulk` | Float | Computed total weight of products **not** in a package. Sum of `quantity * uom_qty * product.weight`. |
| `shipping_weight` | Float | Computed total shipping weight: includes package weights plus bulk weight. Writeable — user can override. |
| `shipping_volume` | Float | Computed total shipping volume: `sum(move.quantity * product.volume)`. |

### Printing & Signature

| Field | Type | Purpose |
|-------|------|---------|
| `printed` | Boolean | Whether the picking's report has been printed. Triggers `do_print_picking` to re-print. |
| `signature` | Image | Customer signature captured at validation. Stored as binary attachment. |
| `is_signed` | Boolean | Computed from presence of `signature` field. |

### Tracking & Warnings

| Field | Type | Purpose |
|-------|------|---------|
| `has_tracking` | Boolean | Computed. `True` if any move's product has tracking (`lot` or `serial`). |
| `has_scrap_move` | Boolean | Computed. `True` if any move has `location_dest_usage == 'inventory'` (scrap move). |
| `picking_warning_text` | Text | Computed warning message from partner and parent partner picking warnings. Only shown to users with `stock.group_warning_stock`. |
| `json_popover` | Char | JSON data for the delay-rescheduling popover widget. Contains late elements and delay date. |

### Scheduling & Deadlines

| Field | Type | Purpose |
|-------|------|---------|
| `has_deadline_issue` | Boolean | Computed. `True` when `date_deadline < scheduled_date`. Used to highlight late pickings. |

### Search Helper Fields

| Field | Type | Purpose |
|-------|------|---------|
| `product_id` | Many2one | Related from `move_ids.product_id`. Allows searching pickings by product. |
| `lot_id` | Many2one | Related from `move_line_ids.lot_id`. Allows searching pickings by lot/serial. |

### Properties & Favorites

| Field | Type | Purpose |
|-------|------|---------|
| `picking_properties` | Properties | Dynamic properties defined on the picking type. Copied to new pickings. |
| `show_next_pickings` | Boolean | Computed. `True` if there are chained pickings (destination moves have pickings). |
| `search_date_category` | Selection | Search-only field for date-based filtering in the UI. |

### Reference Document (Odoo 19 New)

| Field | Type | Purpose |
|-------|------|---------|
| `reference_ids` | Many2many | Links to `stock.reference` records. Related from `move_ids.reference_ids`. Allows cross-referencing external documents (purchase orders, sales orders, etc.) across all moves in the picking. Introduced in Odoo 19. |

### Print Label Configuration

| Field | Type | Purpose |
|-------|------|---------|
| `picking_type_entire_packs` | Boolean | Related from picking type. Controls whether barcode app shows entire packs. |

### Access Control

| Field | Type | Purpose |
|-------|------|---------|
| `user_id` | Many2one | Responsible user for the picking. Domain restricted to users in `stock.group_stock_user`. Default: current user. |

---

## L2: Field Type Details, Defaults, Constraints, and Purpose

### `picking_type_id` — Operation Type

```python
picking_type_id = fields.Many2one(
    'stock.picking.type',
    'Operation Type',
    required=True,
    index=True,
    default=_default_picking_type_id,
    tracking=True
)
```

**Purpose:** Determines the warehouse operation category (Receipt, Delivery, Internal Transfer). Drives default locations, reference sequence, reservation method, and many UI behaviors.

**Default computation:** If context contains `restricted_picking_type_code`, searches for a picking type matching that code and the current company. Falls back to the first matching type.

**Constraint:** Cannot be changed when state is `done` or `cancel`:
```python
def write(self, vals):
    if vals.get('picking_type_id') and any(picking.state in ('done', 'cancel') for picking in self):
        raise UserError(_("Changing the operation type of this record is forbidden at this point."))
```

**Tracking:** `tracking=True` — changes logged in chatter.

---

### `location_id` / `location_dest_id` — Source and Destination

```python
location_id = fields.Many2one(
    'stock.location',
    "Source Location",
    compute="_compute_location_id",
    store=True, precompute=True, readonly=False,
    check_company=True,
    required=True
)
location_dest_id = fields.Many2one(
    'stock.location',
    "Destination Location",
    compute="_compute_location_id",
    store=True, precompute=True, readonly=False,
    check_company=True,
    required=True
)
```

**L2 — Compute logic:**
- Computed from `picking_type_id.default_location_src_id` and `default_location_dest_id`
- **Supplier override:** If `location_id` usage is `'supplier'` and `partner_id` exists, use `partner_id.property_stock_supplier`
- **Customer override:** If `location_dest_id` usage is `'customer'` and `partner_id` exists, use `partner_id.property_stock_customer`
- **Non-computed when:** state is `done`/`cancel` or when `return_id` exists (return pickings keep their original locations)
- **Write propagation:** When picking's location changes, all non-scrap moves' locations are updated via `write()`:
  ```python
  if after_vals.get('location_id'):
      self.move_ids.filtered(lambda m: m.location_dest_usage != 'inventory').write({
          'location_id': after_vals['location_id']
      })
  ```

---

### `move_ids` — Stock Moves

```python
move_ids = fields.One2many(
    'stock.move',
    'picking_id',
    string="Stock Moves",
    copy=True
)
```

**Purpose:** Aggregate-level operations. Each `stock.move` represents a product line to transfer with its demand quantity (`product_uom_qty`), reserved quantity, and done quantity.

**Behavior:**
- `copy=True`: Moves are copied when picking is duplicated
- Moves are filtered during `_compute_state` to determine picking state
- `_autoconfirm_picking()` automatically confirms draft moves when new moves are added

**Relation:** The inverse `stock.move.picking_id` field is a Many2one linking each move back to its parent picking.

---

### `move_line_ids` — Detailed Operations

```python
move_line_ids = fields.One2many(
    'stock.move.line',
    'picking_id',
    'Operations'
)
```

**Purpose:** Granular operation-level records representing actual quantities moved per lot/package/location. A single move may have multiple move lines (e.g., split by lot).

**Key difference from `move_ids`:**
- `move_ids`: Aggregate demand/reservation level (what we plan to move)
- `move_line_ids`: Actual execution level (what was physically moved, per lot/package)

**Creation patterns:**
1. Created manually by users in the detailed operations view
2. Auto-created by `stock.move._action_assign()` (reservation)
3. Auto-created during `button_validate()` when no move lines exist and `show_operations=False`

---

### `state` — Status Field (Computed, Not Directly Writable)

```python
state = fields.Selection([
    ('draft', 'Draft'),
    ('waiting', 'Waiting Another Operation'),
    ('confirmed', 'Waiting'),
    ('assigned', 'Ready'),
    ('done', 'Done'),
    ('cancel', 'Cancelled'),
], string='Status',
    compute='_compute_state',
    copy=False, index=True, readonly=True, store=True, tracking=True,
)
```

**L2 — State computation logic** (`_compute_state`):

The state is computed by aggregating all move states using `defaultdict`:

```
Draft check:     any move is 'draft'           → picking = 'draft'
Cancel check:   all moves are 'cancel'        → picking = 'cancel'
Done check:      all moves are 'cancel' or 'done'
  ├─ all done and scrapped: cancel            → picking = 'cancel'
  └─ otherwise:                               → picking = 'done'
Waiting check:  source bypasses reservation?   → picking = 'assigned'
                 otherwise: get relevant state → picking = 'confirmed'/'waiting'/'partially_available'/'assigned'
```

Key insight: If `location_id.should_bypass_reservation()` returns `True` (e.g., virtual locations, supplier/customer locations), the picking immediately becomes `assigned` regardless of move reservation state. This is why incoming receipts from suppliers typically show `assigned` state immediately upon confirmation.

---

### `is_locked` — Reservation Lock

```python
is_locked = fields.Boolean(
    default=True,
    copy=False,
    help='When the picking is not done this allows changing the initial demand. '
         'When the picking is done this allows changing the done quantities.'
)
```

**L2 — Lock behavior:**

| Picking State | `is_locked=True` (default) | `is_locked=False` |
|---|---|---|
| draft/confirmed/waiting/assigned | Cannot change `product_uom_qty` on moves | Can change `product_uom_qty` |
| done | Cannot change `quantity` on move lines | Can change `quantity` on move lines |
| cancel | N/A | N/A |

**Toggle:** `action_toggle_is_locked()` flips the value.

**L3 — Cancellation locks:** When `action_cancel()` is called, `is_locked` is set to `True`:
```python
def action_cancel(self):
    self.move_ids._action_cancel()
    self.write({'is_locked': True})
```

---

### `immediate_transfer` — Note on Absence in Odoo 19

The `immediate_transfer` field (present in older Odoo versions) does not exist as a field in Odoo 19. Instead, Odoo 19 uses the **wizard pattern** via `stock_immediate_transfer` (if the module exists) or directly processes moves during `button_validate()`.

When `button_validate()` is called without pre-filled quantities:
1. If `show_operations=True`: User must fill detailed operations before validating
2. If `show_operations=False`: System auto-creates move lines for all reserved quantities
3. If a move has `picked=True` but no move lines exist, quantities are auto-assigned

---

### `reference_ids` — External References (Odoo 19 New)

```python
reference_ids = fields.Many2many(
    'stock.reference',
    related="move_ids.reference_ids",
    string="References",
    readonly=True
)
```

**Purpose:** Provides a unified view of all external document references (e.g., purchase orders, sales orders) across all moves in the picking. The `stock.reference` model stores named references that can be linked to multiple moves.

**L2 — `stock.reference` model:**
```python
class StockReference(models.Model):
    _name = 'stock.reference'
    _description = 'Reference between stock documents'

    name = fields.Char('Reference', required=True, readonly=True)
    move_ids = fields.Many2many(
        'stock.move', 'stock_reference_move_rel',
        'reference_id', 'move_id',
        string="Stock Moves"
    )
    picking_ids = fields.Many2many(
        'stock.picking',
        compute='_compute_picking_ids',
        string="Transfers",
        readonly=True
    )
```

---

### `return_id` / `return_ids` — Return Flow

```python
return_id = fields.Many2one(
    'stock.picking',
    'Return of',
    copy=False, index='btree_not_null', readonly=True,
    check_company=True,
    help="If this picking was created as a return of another picking, "
         "this field links to the original picking."
)
return_ids = fields.One2many('stock.picking', 'return_id', 'Returns')
return_count = fields.Integer('# Returns', compute='_compute_return_count', compute_sudo=False)
```

**L2 — Return linkage:**
- When a return picking is created from a done picking, `return_id` links back to the original
- `return_ids` provides the reverse: all returns created from this picking
- Return pickings are created by the `stock.return.picking` wizard (from `stock_picking_return` module)

**Computed field:** `_compute_return_count` simply returns `len(return_ids)`.

---

### `owner_id` — Ownership Assignment

```python
owner_id = fields.Many2one(
    'res.partner',
    'Assign Owner',
    check_company=True,
    index='btree_not_null',
    help="When validating the transfer, the products will be assigned to this owner."
)
```

**L2 — Usage:** When set, the transfer changes product ownership at the destination location. The `owner_id` is written to:
- `stock.move.restrict_partner_id`
- `stock.move.line.owner_id`

This enables "drop shipping to customer while billed by supplier" scenarios and third-party logistics.

---

### `print_label` — Label Generation

**Note:** `print_label` is a field on `stock.picking.type`, not on `stock.picking` directly. The picking inherits it through `picking_type_id.print_label`. The picking type's `print_label` setting determines whether label printing is enabled for transfers of that type.

---

## L3: All Method Signatures and Edge Cases

### Lifecycle Action Methods

#### `action_confirm()`

```python
def action_confirm(self) -> bool
```

**Purpose:** Confirm the picking — converts draft moves to confirmed state and triggers the procurement scheduler.

**L3 — Workflow triggers:**
1. Calls `move_ids.filtered(lambda m: move.state == 'draft')._action_confirm()` — confirms all draft moves
2. Calls `move_ids.filtered(...)._trigger_scheduler()` for moves that may run out of stock

**Edge cases:**
- Calling `action_confirm()` on an already-confirmed picking is idempotent — draft moves only
- Does NOT reserve quantities — use `action_assign()` for that
- Draft moves created via `action_assign()` (for draft pickings) are also confirmed

**Cross-model impact:** `_action_confirm()` on `stock.move`:
- Sets state to `confirmed` or `waiting` based on move dependencies
- Triggers `_action_assign()` if `procure_method == 'make_to_stock'` and source location bypasses reservation

---

#### `action_assign()`

```python
def action_assign() -> bool
```

**Purpose:** Check availability of products and reserve quantities (create stock.quant reservations).

**L3 — Workflow triggers:**
1. First confirms draft pickings: `draft_picking.action_confirm()`
2. For moves with zero `quantity` but non-zero `product_uom_qty`, auto-sets `quantity = product_uom_qty`
3. Runs `_action_assign()` on all non-draft, non-cancelled, non-done moves, sorted by priority and deadline

**Edge cases:**
- **Priority handling:** Moves are sorted by `(-int(priority), not bool(date_deadline), date_deadline, date, id)` — highest priority first
- **Zero quantity moves:** Moves with zero quantity and non-zero demand get `quantity` set equal to `product_uom_qty` before assignment
- **N+1 avoidance:** Uses `_action_assign()` in batch on the sorted move recordset, not per-picking

**Failure modes:**
- `UserError` if no moves exist: `'Nothing to check the availability for.'`
- If stock is insufficient, moves go to `confirmed` or `partially_available` state

---

#### `action_cancel()`

```python
def action_cancel() -> bool
```

**Purpose:** Cancel the picking and all its moves.

**L3 — Workflow triggers:**
1. Calls `move_ids._action_cancel()` on all moves
2. Sets `is_locked = True` on the picking
3. If picking has no moves (`not move_ids`), sets state to `cancel`

**Edge cases:**
- **Move dependencies:** `_action_cancel()` on moves respects `propagate_cancel` — if `True`, cancels chained destination moves as well
- **Reserved quants:** `_action_cancel()` unreserved quants automatically
- **After cancellation:** Picking is locked; no further modifications allowed except unlocking

**Cross-model impact:**
- Unlinks move lines (via `stock.move._action_cancel()`)
- Frees reserved stock in `stock.quant`

---

#### `button_validate()` — Main Validation Entry Point

```python
def button_validate() -> bool | dict
```

**Purpose:** Validate the transfer. This is the primary user-facing validation method.

**L3 — Full workflow sequence:**

```
Step 1: Filter done pickings
    ↓
Step 2: Confirm draft pickings via action_confirm()
    ↓
Step 3: Auto-assign quantity for zero-quantity draft moves
    ↓
Step 4: Sanity checks (empty picking, zero quantities, missing lots)
    ↓
Step 5: Pre-action hook (sets picked=True, backorder check)
    ↓
Step 6: Split by backorder policy
    ├─ pickings with create_backorder='never'      → cancel remaining
    └─ pickings with create_backorder='always/ask' → create backorder
    ↓
Step 7: Call _action_done() on each group
    ↓
Step 8: Auto-print reports (delivery slip, labels, reception report)
    ↓
Step 9: Return action (report print or reception report wizard)
```

**Edge cases:**
- **Multiple pickings:** If validating multiple pickings at once, backorder wizard shows per-picking checkboxes
- **Zero quantities:** Raises `UserError` via `_get_without_quantities_error_message()` if all moves have zero quantity
- **Empty picking:** Raises `UserError` if no moves exist
- **Missing lots:** Raises `UserError` listing products needing lot/serial numbers
- **Reception report:** Only shown for incoming/internal pickings with unassigned moves that could be assigned

**Immediate transfer mode:** If `show_operations=False`, the system auto-creates move lines for all reserved quantities before validation. If `show_operations=True`, users must manually fill detailed operations.

---

#### `_action_done()`

```python
def _action_done() -> bool
```

**Purpose:** Backend validation — processes all moves and move lines to actually transfer stock.

**L3 — Workflow:**
1. Writes `restrict_partner_id` and `owner_id` to all moves and move lines
2. Calls `todo_moves._action_done(cancel_backorder=...)` on `stock.move`
3. Sets `date_done = now()` and `priority = '0'`
4. Triggers `_trigger_assign()` on done incoming/internal moves
5. Sends confirmation email if configured

**Cross-model impact on `stock.move._action_done()`:**
- Validates lot/serial tracking
- Creates and deletes `stock.move.line` records as needed
- Moves quants from source to destination location
- Creates accounting entries (if `stock_account` installed)
- Updates `procurement.group` and chained moves

**Edge cases:**
- **Scrap moves:** Moves to `inventory` location are treated differently (no backorder, different quant handling)
- **Owner assignment:** When `owner_id` is set, all quants are created with that owner
- **Package handling:** `_check_entire_pack()` assigns `result_package_id` to entire packs

---

#### `action_toggle_is_locked()`

```python
def action_toggle_is_locked() -> bool
```

**Purpose:** Toggles the `is_locked` boolean to allow or prevent editing of demand/done quantities.

**Edge case:** Only operates on a single picking (`ensure_one()`). Returns `True`.

---

#### `action_split_transfer()`

```python
def action_split_transfer() -> None
```

**Purpose:** Split the current picking into two: one for done quantities, one for remaining quantities (backorder).

**L3 — Validation constraints (raises UserError if violated):**
1. At least one move must have a non-zero `quantity` (done qty)
2. At least one move must have `quantity != product_uom_qty` (not fully done)
3. No move can have `quantity > product_uom_qty` (over-quantity not allowed)

**Workflow:**
1. Filters moves with `state not in ('done', 'cancel')` and `quantity != 0`
2. Creates backorder moves via `moves._create_backorder()` for the remaining quantities
3. Also includes zero-quantity moves in the backorder
4. Calls `self._create_backorder()` with the combined backorder moves

---

#### `action_put_in_pack()`

```python
def action_put_in_pack(
    self,
    *,
    package_id=False,
    package_type_id=False,
    package_name=False
) -> bool | stock.package
```

**Purpose:** Put selected or all move lines into a package.

**L3 — Delegation:** Delegates to `move_line_ids.action_put_in_pack()`:
```python
def action_put_in_pack(self, *, package_id=False, ...):
    self.ensure_one()
    if self.state not in ('done', 'cancel'):
        return self.move_line_ids.action_put_in_pack(
            package_id=package_id,
            package_type_id=package_type_id,
            package_name=package_name
        )
```

**Edge cases:**
- Only works when picking is not done or cancelled
- If `sml_specific_default` context is set, clears it before delegating
- Can create a new package or use an existing one via `package_id`
- `package_name` sets the package's `name` field

---

### `return_to_location()` — Method Does NOT Exist in Odoo 19

The `return_to_location()` method was mentioned in the task specification but **does not exist** in the Odoo 19 stock module. This method may be:

1. Planned for a future Odoo version (Odoo 20+)
2. Part of a custom/EE module not present in the standard distribution
3. An alias for `stock.return.picking` wizard functionality

The standard return flow in Odoo 19 uses the `stock.return.picking` wizard (from `stock_picking_return` module), which creates a new return picking with reversed locations.

---

### `action_detailed_operations()`

```python
def action_detailed_operations() -> dict
```

**Purpose:** Opens the detailed operations list view for move lines.

**Returns:** An `ir.actions.act_window` action opening `stock.move.line` in list mode, filtered to this picking's move lines.

**L3 — Context passed:**
```python
context = {
    'sml_specific_default': True,      # Use move line defaults for this picking
    'default_picking_id': self.id,
    'default_location_id': self.location_id.id,
    'default_location_dest_id': self.location_dest_id.id,
    'default_company_id': self.company_id.id,
    'show_lots_text': self.show_lots_text,
    'picking_code': self.picking_type_code,
    'create': self.state not in ('done', 'cancel'),  # No create if done/cancel
}
```

---

### `action_next_transfer()`

```python
def action_next_transfer() -> dict
```

**Purpose:** Navigate to the next chained picking in the delivery chain.

**L3 — Logic:**
```python
def _get_next_transfers(self):
    next_pickings = self.move_ids.move_dest_ids.picking_id
    return next_pickings.filtered(lambda p: p not in self.return_ids)
```

**Edge case:** If only one next transfer exists, opens directly in form view. If multiple exist, opens a list view.

---

### Backorder Methods

#### `_check_backorder()`

```python
def _check_backorder() -> stock.picking recordset
```

**Purpose:** Determines which pickings need a backorder. A picking needs a backorder if any move has:
- `product_uom_qty > 0` but `picked == False`, OR
- `picked_quantity < product_uom_qty`

Only applies to pickings where `create_backorder == 'ask'`.

---

#### `_create_backorder(backorder_moves=None)`

```python
def _create_backorder(self, backorder_moves=None) -> stock.picking recordset
```

**L3 — Workflow:**
1. For each picking, determines which moves go to the backorder
2. Creates a new picking via `_create_backorder_picking()` (copy with `name='/'`, no moves)
3. Writes moves and move lines to the new backorder picking
4. Clears `user_id` on the backorder
5. Posts a chatter message linking to the new backorder
6. If backorder's picking type uses `reservation_method == 'at_confirm'`, calls `action_assign()`

**Edge case:** When `backorder_moves` is provided (from `action_split_transfer`), only those moves go to the backorder, not all incomplete moves.

---

#### `_create_backorder_picking()`

```python
def _create_backorder_picking(self) -> stock.picking
```

**Purpose:** Factory method creating a new backorder picking. Copies the original picking but:
- Sets `name = '/'` (triggers sequence generation)
- Clears `move_ids` and `move_line_ids` (will be populated by caller)
- Sets `backorder_id = self.id`

---

### Sanity Check Methods

#### `_sanity_check(separate_pickings=True)`

```python
def _sanity_check(self, separate_pickings=True) -> None
```

**Purpose:** Validates that the picking is ready for validation. Raises `UserError` if not.

**L3 — Checks performed:**

1. **Empty picking:** No moves AND no move lines → `UserError("You can't validate an empty transfer")`

2. **Zero quantities:** All non-cancelled moves have zero quantity → error via `_get_without_quantities_error_message()`

3. **Missing lot/serial numbers:** For picking types with `use_create_lots` or `use_existing_lots`, any move line with tracked product but no `lot_id` or `lot_name` → `UserError` listing products

**Edge case — `separate_pickings`:** When `True` (default), each picking is checked independently. When `False` (used for batch validation), all pickings are treated as one unit — the zero-quantity check uses a different threshold.

---

#### `_get_lot_move_lines_for_sanity_check()`

```python
def _get_lot_move_lines_for_sanity_check(
    none_done_picking_ids: set,
    separate_pickings=True
) -> stock.move.line recordset
```

**Purpose:** Retrieves all move lines with tracked products that need lot/serial verification during sanity check.

**L3 — Logic:**
- If picking has no quantity set → include ALL tracked product move lines
- If picking has some quantity → include only move lines with `picked=True` and `quantity > 0`

---

### `_pre_action_done_hook()`

```python
def _pre_action_done_hook() -> bool | dict
```

**Purpose:** Pre-validation hook that runs before `_action_done()`. Returns `True` to proceed or a wizard action dict to interrupt.

**L3 — Workflow:**
1. Sets `picked=True` on all moves if any move has quantity but no moves are marked picked
2. Calls `_check_backorder()` if context `skip_backorder` is not set
3. If backorders needed → returns `_action_generate_backorder_wizard()` to show the backorder confirmation dialog

---

### `_check_entire_pack()`

```python
def _check_entire_pack() -> None
```

**Purpose:** For moves involving packages, automatically assigns `result_package_id` when entire packages are being moved.

**L3 — Logic:**
- For each package in `move_line_ids.package_id`:
  - If the transfer is a single picking
  - And all quants in the package are being moved (verified by `_check_move_lines_map_quant_package`)
  - Then set `result_package_id = package.id` and `is_entire_pack = True` on all non-done move lines for that package
- Calls `result_package_id._apply_package_dest_for_entire_packs()` to propagate container destinations

---

### Email and Reporting Methods

#### `_send_confirmation_email()`

```python
def _send_confirmation_email() -> None
```

**Purpose:** Sends a delivery confirmation email for outgoing pickings when `company_id.stock_move_email_validation` is `True`.

**L3 — Trigger conditions:**
- Picking type code is `'outgoing'`
- Company setting `stock_move_email_validation` is enabled

Uses `message_post_with_source()` with the company's configured `stock_mail_confirmation_template_id`.

---

#### `_get_autoprint_report_actions()`

```python
def _get_autoprint_report_actions() -> list
```

**L3 — Report actions collected:**
1. **Delivery slip:** If `auto_print_delivery_slip` on picking type
2. **Return slip:** If `auto_print_return_slip` on picking type
3. **Reception report:** If `auto_show_reception_report` on picking type and there are moves with allocation
4. **Reception report labels:** If `auto_print_reception_report_labels`
5. **Product labels:** Grouped by `product_label_format` (DYMO, ZPL, etc.)
6. **Lot/SN labels:** If `auto_print_lot_labels` and lot IDs exist
7. **Package labels:** If `auto_print_packages` and result packages exist

**Returns:** List of report actions to be printed by `do_multi_print` client action.

---

### `_compute_state()` — State Aggregation Algorithm

```python
def _compute_state(self) -> None
```

**L3 — Algorithm in detail:**

The method uses a two-pass approach: first it builds a state map, then it computes the picking state:

**Pass 1 — Build state map** (via `_read_group`):
```python
picking_moves_state_map[picking_id] = {
    'any_draft': bool,
    'all_cancel': bool,
    'all_cancel_done': bool,
    'all_done_are_scrapped': bool,
    'any_cancel_and_not_scrapped': bool,
}
```

**Pass 2 — Determine state:**

| Condition | State |
|---|---|
| No moves OR any draft move | `draft` |
| All moves cancelled | `cancel` |
| All moves cancel/done | `done` (unless all done AND scrapped AND any cancelled non-scrap) → `cancel` |
| Source bypasses reservation AND all moves are `make_to_stock` | `assigned` |
| Otherwise | Move's relevant state via `_get_relevant_state_among_moves()` |

**Edge case — `partially_available`:** If the relevant move state is `partially_available`, the picking state becomes `assigned` (not `partially_available`). This is because Odoo 19 flattened `partially_available` into `assigned` at the picking level.

---

## L4: Performance Implications, Historical Changes, and Security Concerns

### Performance Implications

#### N+1 Query Risk in `_compute_state()`

**Issue:** The state computation performs a `_read_group` query per picking to aggregate move states, then calls `_get_relevant_state_among_moves()` which may trigger additional queries.

**Mitigation:** The `_read_group` is a single SQL query that fetches all move states at once:
```python
for move in self.env['stock.move'].search([('picking_id', 'in', self.ids)]):
```

For large picking sets (100+), this is more efficient than individual ORM searches.

#### `_compute_products_availability()` — Forced Prefetch

```python
all_moves._fields['forecast_availability'].compute_value(all_moves)
```

**Performance concern:** This line forces computation of `forecast_availability` on all moves at once, bypassing the default prefetch chunk size of 1000. This prevents N+1 queries when accessing availability across many pickings but may cause a heavy query on large datasets.

**Recommendation:** If your dataset has pickings with thousands of moves, consider adding a `limit` or processing in batches.

#### `_compute_state()` Called Frequently

**Issue:** The `state` field is stored but still recomputed when moves change. Any write to `move_ids`, `move_line_ids`, or picking fields that affect move states triggers a recomputation.

**Mitigation:** The computation is batched across all pickings in `self`, minimizing SQL round-trips.

#### `_create_backorder()` — Move Relinking

**Performance concern:** When creating a backorder, moves and move lines are written individually per picking:
```python
moves_to_backorder.write({'picking_id': backorder_picking.id, 'picked': False})
moves_to_backorder.mapped('move_line_ids').write({'picking_id': backorder_picking.id})
```

For pickings with many moves/lines, consider batching these writes.

#### `_compute_packages_count()` — Multiple Query Pattern

```python
packages = self.env['stock.package'].search([('picking_ids', 'in', other_pickings.ids)])
for pack in packages:
    for picking in pack.picking_ids:
        packages_by_pick[picking] += 1
```

**Issue:** This has O(n*m) complexity where n = packages, m = pickings per package. For large datasets, use `_read_group` instead:
```python
self.env['stock.package']._read_group(
    [('picking_ids', 'in', self.ids)],
    ['picking_ids'],
    ['__count']
)
```

---

### Historical Changes: Odoo 17 → 18 → 19

#### Odoo 18 → 19 Key Changes

1. **`stock.reference` Model (New):** Odoo 19 introduces a new `stock.reference` model to link external documents (e.g., PO, SO) to stock moves. The picking exposes this via `reference_ids = fields.Many2many(related='move_ids.reference_ids')`.

2. **`return_to_location` Method (Does NOT Exist):** Despite being mentioned in the task requirements, this method does not exist in Odoo 19. The return mechanism uses the `stock.return.picking` wizard instead.

3. **Flattened State for `partially_available`:** In Odoo 18, pickings could have a `partially_available` state. In Odoo 19, this is absorbed into `assigned`. The `_compute_state()` method maps `partially_available` move states to `assigned` picking state.

4. **Immediate Transfer Mode Changes:** Odoo 19 consolidates immediate transfer logic into `button_validate()` without a separate `immediate_transfer` field. The behavior depends on `show_operations` and the presence of move lines.

5. **`show_operations` Field Now on Picking Type:** The `show_operations` boolean moved from the picking to the picking type (`stock.picking.type.show_operations`), with the picking inheriting it via `related`.

6. **Removal of `from_immediate_transfer` View Field:** The `from_immediate_transfer` computed field (present in older versions as a UI helper) was removed. The immediate transfer wizard behavior is now handled through context and direct processing.

7. **New `return_id` / `return_ids` Fields:** Odoo 19 adds explicit return tracking fields. Previous versions relied on the backorder mechanism and domain searches.

8. **`search_date_category` Field (New):** Odoo 19 adds this virtual selection field for date-based filtering in the UI with categories: `before`, `yesterday`, `today`, `day_1`, `day_2`, `after`.

9. **`json_popover` Field (New):** New field storing JSON for a delay-rescheduling popover widget, replacing older JavaScript-based approaches.

10. **`picking_warning_text` Field (New):** New computed field aggregating partner and parent partner picking warnings into a single text field.

#### Odoo 17 → 18 Key Changes

1. **`picked` Field on Moves:** Odoo 18 introduced the `picked` boolean on `stock.move`, replacing the need to manually set quantities for all moves. The picking's `button_validate()` auto-sets `picked=True` in the pre-hook if any quantity is entered.

2. **`move_type` Inversion for Deadline Computation:** Odoo 18 changed `_compute_date_deadline()`:
   - `direct` policy: takes `min` date_deadline (earliest)
   - `one` policy: takes `max` date_deadline (latest)
   This was reversed in some earlier versions.

---

### Security Concerns

#### SQL Injection — Low Risk

**Assessment:** The `stock.picking` model uses the ORM exclusively for all database operations. No raw SQL concatenation was found. The `_order_field_to_sql` method on `StockPickingType` uses `SQL.identifier()` for safe column reference in ordering.

#### Access Control — Record Rules Required

**Concern:** Out of the box, Odoo does NOT create `ir.rule` records for `stock.picking`. All users with `stock.group_stock_user` access can see all pickings.

**Recommendation:** Implement record rules to restrict access:
```xml
<!-- Multi-company: Users only see pickings from their companies -->
<record id="stock_picking_comp_rule" model="ir.rule">
    <field name="name">Multi-company Rule</field>
    <field name="model_id" ref="model_stock_picking"/>
    <field name="domain_force">[('company_id', 'in', company_ids)]</field>
</record>

<!-- User isolation: Users only see their assigned pickings (optional) -->
<record id="stock_picking_user_rule" model="ir.rule">
    <field name="name">User: Own Pickings</field>
    <field name="model_id" ref="model_stock_picking"/>
    <field name="domain_force">[('user_id', '=', user.id)]</field>
    <field name="groups" eval="[(4, ref('stock.group_stock_user'))]"/>
</record>
```

#### Field-Level Security

**Sensitive fields requiring `groups` restrictions:**

| Field | Recommended Group | Risk |
|-------|-------------------|------|
| `owner_id` | `stock.group_stock_manager` | Changing ownership can redirect valuable inventory |
| `is_locked` | `stock.group_stock_manager` | Unlocking done pickings allows quantity modification |
| `date_done` | `stock.group_stock_manager` | Backdating completed transfers |
| `signature` | `stock.group_stock_user` | Customer signature data |
| `picking_warning_text` | `stock.group_warning_stock` | Sensitive partner warnings |

#### XSS Risk — `note` Field

**Concern:** The `note` field is `Html` type, which allows rich text but also potentially malicious scripts if rendered without escaping in custom views.

**Mitigation:** Odoo's `Html` field type automatically sanitizes content using an allowed tags whitelist. However, custom QWeb templates rendering `note` should use `{{note}}` (escaped) or `t-raw="note"` (unescaped — only use if absolutely sure content is safe).

#### Mass Action Security

**Concern:** `action_assign()` and `action_cancel()` operate on entire recordset batches. A user with access to multiple pickings could inadvertently affect pickings they shouldn't modify.

**Recommendation:** Implement domain-based record rules to limit which pickings a user can operate on, rather than relying solely on menu access control.

#### File Attachment — `signature` Field

**Concern:** The `signature` field stores images as binary attachments. Without access controls:
- Anyone with write access to the picking can overwrite the signature
- The signature PDF attachment created by `_attach_sign()` is world-readable if not properly secured

**Mitigation:** Signatures are only attached after validation, reducing the attack surface. However, ensure `ir.attachment` record rules restrict access to signed delivery slips.

#### Portal/Public Access

**Concern:** If `stock_picking` is exposed via the website or portal, portal users need explicit ACL entries:

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_stock_picking_portal,access_stock_picking_portal,model_stock_picking,base.group_portal,1,0,0,0
```

Without these, portal users receive `Access Error` when attempting to view delivery orders.

---

### Edge Cases and Known Failure Modes

#### Circular Move Dependencies

**Issue:** If moves have circular `move_orig_ids` / `move_dest_ids` dependencies, `_compute_state()` may cause infinite recursion in `_get_relevant_state_among_moves()`.

**Mitigation:** Odoo validates move chaining at the move creation level, but custom code creating circular dependencies should be avoided.

#### Concurrent Validation

**Issue:** Two users validating the same picking simultaneously could cause race conditions in quant creation.

**Mitigation:** Odoo uses PostgreSQL row-level locking (`FOR UPDATE`) on the picking and move records during `_action_done()`. However, high-concurrency scenarios (barcode scanner + web UI) may still cause transient conflicts.

#### Multi-Company Picking Type Change

**Issue:** Changing `picking_type_id` regenerates the `name` from the new sequence. If pickings are linked to moves in other companies (due to cross-company rules), this could cause data inconsistency.

**Mitigation:** `write()` prevents changing `picking_type_id` on done/cancelled pickings, and the company check on `StockPickingType` limits the risk.

#### Backorder with `propagate_cancel=False`

**Issue:** If a move has `propagate_cancel=False` and the picking is cancelled, the destination move remains in its current state while the source move is cancelled. This can leave the chain in an inconsistent state.

**Mitigation:** Always set `propagate_cancel=True` for moves that are part of a critical chain, or implement monitoring for orphaned moves.

#### `scheduled_date` Modification After Moves Exist

**Issue:** Changing `scheduled_date` on a picking with existing moves overwrites all move dates, potentially disrupting procurement schedules and deadline tracking.

**Mitigation:** The `_set_scheduled_date()` inverse method handles this, but users should be warned before modifying scheduled dates on pickings with confirmed procurement orders.

---

## Related Models

| Model | Relationship | Key Fields |
|-------|-------------|------------|
| `stock.picking.type` | `stock.picking` is `Many2one` from picking → type | `code`, `default_location_src_id`, `default_location_dest_id`, `sequence_id`, `reservation_method`, `create_backorder` |
| `stock.move` | `stock.picking` is `One2many` inverse | `picking_id`, `product_id`, `product_uom_qty`, `quantity`, `state`, `picked`, `move_line_ids` |
| `stock.move.line` | `stock.picking` is `One2many` inverse | `picking_id`, `product_id`, `location_id`, `location_dest_id`, `quantity`, `lot_id`, `package_id`, `result_package_id`, `owner_id` |
| `stock.quant` | Created by `stock.move.line._action_done()` | `product_id`, `location_id`, `quantity`, `lot_id`, `package_id`, `owner_id`, `value` |
| `stock.package` | Linked via `move_line_ids.result_package_id` | `package_type_id`, `quant_ids`, `packaging_user_id`, `shipping_weight` |
| `stock.reference` | Linked via `move_ids.reference_ids` | `name`, `move_ids`, `picking_ids` |
| `res.partner` | `stock.picking` is `Many2one` via `partner_id`, `owner_id` | `property_stock_supplier`, `property_stock_customer`, `picking_warn_msg` |
| `stock.location` | `stock.picking` is `Many2one` via `location_id`, `location_dest_id` | `usage`, `company_id`, `location_id` (parent) |

---

## See Also

- [Modules/Stock](Modules/stock.md) — Stock module overview and quant/picking type documentation
- [Core/Fields](Core/Fields.md) — Field type reference (Many2one, One2many, computed fields)
- [Core/API](Core/API.md) — `@api.depends`, `@api.onchange`, `@api.constrains` decorators
- [Patterns/Security Patterns](odoo-18/Patterns/Security Patterns.md) — ACL, ir.rule, and field-level security
- [Patterns/Workflow Patterns](odoo-18/Patterns/Workflow Patterns.md) — State machine implementation in Odoo
- [Tools/ORM Operations](odoo-18/Tools/ORM Operations.md) — `search()`, `browse()`, `write()`, domain operators
