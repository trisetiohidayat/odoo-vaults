# Stock Move (`stock.move`)

## Overview

The `stock.move` model is the **central data structure** in Odoo's stock management system. It represents the physical movement of products between warehouse locations, serving as the atomic unit of stock operations. Every stock operation (transfers, receipts, deliveries, scrap, etc.) is ultimately composed of one or more `stock.move` records.

**Key architectural facts:**
- **Table:** `stock_move`
- **Inherits:** `models.Model` (BaseModel)
- **Order:** `sequence, id` -- moves are ordered first by sequence, then by ID
- **Rec Name:** `reference` -- the display name is computed from picking origin and location pair
- **Database Index:** Composite index on `(product_id, location_id, location_dest_id, company_id, state)` (`_product_location_index`)

The `stock.move` is fundamentally a **demand record**: it declares an intent to move a quantity of product from a source location to a destination location. The actual execution of this movement is tracked through `stock.move.line` child records.

```python
class StockMove(models.Model):
    _name = 'stock.move'
    _description = "Stock Move"
    _order = 'sequence, id'
    _rec_name = 'reference'
```

---

## Fields (L1 -- All Fields)

This section lists every field defined on `stock.move`, grouped by semantic category.

### Identity & Reference Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `sequence` | `Integer` | `10` | Controls ordering within a picking. Lower values appear first. |
| `reference` | `Char` | computed | Display name. Format: `[origin/][code: ]source_location > dest_location`. Source: `picking_id.name`, `scrap_id.name`, or inventory confirmation text. |
| `display_name` | `Char` | computed | Web client display name. Format: `[origin/]code: source > dest`. |
| `origin` | `Char` | -- | Reference to the source document that triggered the move (e.g., SO number, PO number, MO name). |
| `origin_returned_move_id` | `Many2one` | -- | Links a return move back to the original move that was returned. Indexed. Used for reverse logistics. |
| `returned_move_ids` | `One2many` | -- | All moves created as returns of this move (inverse of `origin_returned_move_id`). |
| `reference_ids` | `Many2many` | -- | Links to `stock.reference` records (e.g., sale lines, purchase lines). Used for cross-module traceability. |

### Product Fields

| Field | Type | Description |
|---|---|---|
| `product_id` | `Many2one(product.product)` | **Required.** The product being moved. Domain restricts to `type == 'consu'` (consumable). Checked against company. Indexed. |
| `product_tmpl_id` | `Many2one(product.template)` | Related from `product_id.product_tmpl_id`. |
| `product_category_id` | `Many2one(product.category)` | Related from `product_id.categ_id`. |
| `never_product_template_attribute_value_ids` | `Many2many` | Tracks attribute values that should never be applied to this move's product. Used in Kitting/MTO flows. |
| `description_picking` | `Text` | User-editable description for this move in the picking context. Computed from product's picking description, with inverse to persist manual edits. |
| `description_picking_manual` | `Text` | Stores the manual override of `description_picking`. Readonly after entry. |
| `is_storable` | `Boolean` | Related from `product_id.is_storable`. Convenience for UI logic. |

### Quantity Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `product_uom_qty` | `Float` | `0` | **The planned/demand quantity.** Expressed in `product_uom`. Required. Changing this on an assigned move affects reservation and should be done carefully. Lowering does NOT generate a backorder. |
| `product_qty` | `Float` | computed | **Real quantity in the product's default UoM.** Computed from `product_uom_qty` converted to product's `uom_id`. Has an inverse (`_set_product_qty`) that raises an error -- this field should never be written directly; use `product_uom_qty` instead. Stored. Digits: 0 (integer). |
| `quantity` | `Float` | computed | **Sum of done quantities from move lines.** Computed from `move_line_ids.quantity` converted to product UoM. Used to determine if backorder is needed. Has an inverse to propagate changes back to move lines. Stored. |
| `availability` | `Float` | computed | **Forecasted quantity available for reservation.** If `state == 'done'`, returns `product_qty`. Otherwise, returns `min(product_qty, available_quantity_at_source_location)`. |
| `packaging_uom_id` | `Many2one(uom.uom)` | computed | UoM for packaging. Defaults to `product_uom`. |
| `packaging_uom_qty` | `Float` | computed | Quantity converted to packaging UoM. |
| `next_serial` | `Char` | -- | First serial/lot number for serial number generation. |
| `next_serial_count` | `Integer` | -- | Number of serial numbers to generate. |

### Unit of Measure Fields

| Field | Type | Description |
|---|---|---|
| `product_uom` | `Many2one(uom.uom)` | **Required.** The UoM for `product_uom_qty`. Domain restricted to UoMs compatible with the product (computed via `allowed_uom_ids`). Precomputed and stored with `readonly=False` so it can be changed. |
| `allowed_uom_ids` | `Many2many(uom.uom)` | Computed from product's `uom_id`, `uom_ids`, and seller UoMs. Controls which UoMs appear in the domain for `product_uom`. |

### Location Fields

| Field | Type | Description |
|---|---|---|
| `location_id` | `Many2one(stock.location)` | **Source location** -- where products are taken from. Required. Computed from `picking_id.location_id` or `picking_type_id.default_location_src_id`. Has `bypass_search_access=True`. Indexed. |
| `location_dest_id` | `Many2one(stock.location)` | **Destination location** -- where products go. Required. Has complex computation that handles inter-company transit, intermediate locations, and final destination routing. Inverse (`_set_location_dest_id`) applies putaway strategy to move lines. |
| `location_final_id` | `Many2one(stock.location)` | **Final destination** in multi-step routing chains. Used when a move is part of a chain targeting a location beyond the immediate destination. For example, in cross-docking scenarios. |
| `location_usage` | `Selection` | Related from `location_id.usage`. Convenience field for display/logic. |
| `location_dest_usage` | `Selection` | Related from `location_dest_id.usage`. Convenience field. |
| `warehouse_id` | `Many2one(stock.warehouse)` | The warehouse considered for route selection on downstream procurement. Derived from location chain or explicitly set. |

### State & Workflow Fields

| Field | Type | Default | States |
|---|---|---|---|
| `state` | `Selection` | `'draft'` | `draft` (New), `waiting` (Waiting Another Move), `confirmed` (Waiting), `partially_available` (Partially Available), `assigned` (Available), `done` (Done), `cancel` (Cancelled). **Read-only.** Indexed. Not copied on duplicate. |
| `picked` | `Boolean` | `False` | Indicates the move has been "picked" (the operator confirmed physically handling). Computed inverse: setting `picked` on the move propagates to all move lines. Does not validate or generate any product moves itself -- purely indicative. |
| `is_locked` | `Boolean` | computed | True if the associated picking is locked. Inherited from `picking_id.is_locked`. |
| `is_initial_demand_editable` | `Boolean` | computed | True if the picking is not locked OR move is draft. Controls whether `product_uom_qty` is editable in the UI. |
| `is_date_editable` | `Boolean` | computed | True if picking's date is editable. |
| `is_quantity_done_editable` | `Boolean` | computed | True if product is set (always True when product exists). |
| `priority` | `Selection` | `'0'` (Normal) | Move priority. Computed from `picking_id.priority`. Stored. `PROCUREMENT_PRIORITIES = [('0', 'Normal'), ('1', 'Urgent')]`. |

### Picking & Operation Type Fields

| Field | Type | Description |
|---|---|---|
| `picking_id` | `Many2one(stock.picking)` | The transfer/picking this move belongs to. Indexed. Checked against company. |
| `picking_type_id` | `Many2one(stock.picking.type)` | The operation type (e.g., Receipt, Delivery Order). Computed from `picking_id.picking_type_id`. Controls default locations, reservation methods, lot handling, etc. |
| `picking_code` | `Selection` | Related from `picking_id.picking_type_id.code` (incoming/outgoing/internal). Readonly convenience. |
| `is_inventory` | `Boolean` | True if this move was created from an inventory adjustment. |
| `inventory_name` | `Char` | Name of the inventory adjustment that created this move. |
| `show_operations` | `Boolean` | Related from `picking_id.picking_type_id.show_operations`. |

### Move Line Relations

| Field | Type | Description |
|---|---|---|
| `move_line_ids` | `One2many(stock.move.line)` | **Child move lines** representing granular execution details (per-lot, per-package, per-owner). A move has at least one move line when reserved or done. The existence of move lines is what "reserves" stock. |
| `move_lines_count` | `Integer` | Count of `move_line_ids`. Computed. |

### Chained Moves (MTO/MTS)

| Field | Type | Description |
|---|---|---|
| `move_dest_ids` | `Many2many(stock.move)` | **Destination moves** -- moves that should happen after this move. Used to chain operations (MTO -- Make To Order). For example, a receipt move's `move_dest_ids` could point to an internal transfer move. Not copied. |
| `move_orig_ids` | `Many2many(stock.move)` | **Original moves** -- moves that must complete before this move. Creates waiting dependencies. For example, an internal transfer's `move_orig_ids` could point to a receipt move. Not copied. |
| `procure_method` | `Selection` | `'make_to_stock'` (default) or `'make_to_order'`. Determines whether the system takes from existing stock (MTS) or creates a procurement to source the product (MTO). Required. Not copied. |
| `rule_id` | `Many2one(stock.rule)` | The stock rule that created this move. Ondelete: `restrict`. Points to the procurement rule that triggered this move. |
| `propagate_cancel` | `Boolean` | `True` (default). If checked, cancelling this move propagates cancellation to destination moves (if all their siblings are also cancelled). Controls chain cancellation behavior. |
| `route_ids` | `Many2many(stock.route)` | Preferred routes for this move. Overrides product/route-level defaults. |

### Tracking Fields

| Field | Type | Description |
|---|---|---|
| `has_tracking` | `Selection` | Related from `product_id.tracking` ('none', 'serial', 'lot'). Indicates if the product requires lot/serial tracking. |
| `lot_ids` | `Many2many(stock.lot)` | All lots/serials linked to this move via move lines. Computed from move lines with inverse to create/modify move lines when lots are assigned. |
| `display_import_lot` | `Boolean` | Computed. True if the UI should show the "Import Lots" button. |
| `display_assign_serial` | `Boolean` | Computed. True if the UI should show the "Assign Serial Numbers" button. |
| `show_lots_m2o` | `Boolean` | Show lot_id Many2one widget. |
| `show_lots_text` | `Boolean` | Show lot_name text input. |
| `show_quant` | `Boolean` | Show quants list in UI. |

### Owner & Partner Fields

| Field | Type | Description |
|---|---|---|
| `partner_id` | `Many2one(res.partner)` | Destination address for the move (used for allotment). Computed from `picking_id.partner_id`. Indexed with `btree_not_null`. |
| `restrict_partner_id` | `Many2one(res.partner)` | Restricts which owner's quants can be used when marking this move as done. Used in consignment scenarios. Indexed with `btree_not_null`. |

### Pricing & Cost Fields

| Field | Type | Description |
|---|---|---|
| `price_unit` | `Float` | Unit cost used when the move is validated with `average` or `real` costing method. Given in company currency and product UoM. Not copied. Not a monetary field -- intentionally no `digits` attribute (technical field). |
| `forecast_availability` | `Float` | Computed forecasted quantity available for the move by warehouse. Complex multi-branch computation. |
| `forecast_expected_date` | `Datetime` | Computed date when the forecasted quantity is expected. |

### Date & Scheduling Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `date` | `Datetime` | `Datetime.now` | **Scheduled date** of the move. Used for planning. Until the move is done, this is the planned date. After done, it is set to the actual processing datetime. Indexed. Required. |
| `date_deadline` | `Datetime` | -- | **Deadline date.** For outgoing moves: validate transfer before this date to deliver on time. For incoming moves: validate before this date to have products in stock by the promised date. Readonly. Not copied. |
| `delay_alert_date` | `Datetime` | computed | Date at which a delay alert should be triggered. Computed from upstream move dates. |
| `reservation_date` | `Date` | computed | Date when the move should be reserved. Computed based on `picking_type_id.reservation_method` (`by_date` or `manual`) and priority. |

### Company & Configuration Fields

| Field | Type | Default | Description |
|---|---|---|---|
| `company_id` | `Many2one(res.company)` | `env.company` | The company the move belongs to. Required. Indexed. |
| `scrap_id` | `Many2one(stock.scrap)` | -- | If this move came from a scrap operation, links to it. Indexed with `btree_not_null`. |
| `additional` | `Boolean` | `False` | True if the move was added after the picking was confirmed. Used to distinguish auto-confirmed moves from manually-added ones. |
| `is_quantity_done_editable` | `Boolean` | computed | Always True if product exists. Controls UI editability. |
| `procurement_values` | `Json` | -- | Dummy field to store procurement values that need to propagate to later steps in the procurement chain. Not stored. Set via `_prepare_procurement_values()` and passed to `stock.rule.run()`. |
| `orderpoint_id` | `Many2one(stock.warehouse.orderpoint)` | -- | Original reordering rule (orderpoint) that triggered this move, if any. Indexed. Used to link procurement-triggered moves back to their source orderpoint. |

### Extended Lifecycle Fields (L3+)

| Field | Type | Description |
|---|---|---|
| `inventory_name` | `Char` | Set when the move originates from an inventory adjustment. Used as the `reference` display name instead of the generic picking name. |
| `delay_alert_date` | `Datetime` | Computed: if any un-done upstream move has a date later than `self.date`, that max date becomes the alert date. The `_delay_alert_get_documents` and `_propagate_date_log_note` methods post chatter alerts when deadline propagation occurs. |
| `route_ids` | `Many2many(stock.route)` | Preferred routes on the move. `_prepare_procurement_values` also pulls routes from the move line's result package's `package_type_id.route_ids`. |
| `warehouse_id` | `Many2one(stock.warehouse)` | Target warehouse for route selection on downstream procurement. Derived from source/destination location chain, or from `rule_id.route_id.supplier_wh_id` if the move originates from a supplier rule. |

---

## L2: Detailed Field Analysis

### `product_uom_qty` vs `quantity` vs `product_qty` -- The Three Quantities

Understanding the distinction between these three fields is critical:

| Field | Meaning | When to Set | On Assigned Moves |
|---|---|---|---|
| `product_uom_qty` | **Planned/demand quantity** in the move's UoM | At move creation | Changing triggers unreservation |
| `product_qty` | **Demand converted** to product's default UoM | Read-only (inverse raises error) | Read-only |
| `quantity` | **Actually done** quantity, sum of move lines | Via move lines or `_set_quantity` | Can be edited to record what was physically moved |

The relationship:
- `product_qty` = `product_uom._compute_quantity(product_uom_qty, product_id.uom_id)` -- conversion from move UoM to product UoM
- `quantity` = sum of `move_line_ids.quantity` converted to product UoM
- Backorder decision: `quantity < product_uom_qty` at `_action_done` time triggers backorder creation

**Important:** When `product_uom_qty` is decreased on an assigned move, Odoo automatically unreserves the excess. When increased, the picking must be reassigned to reserve additional stock.

### Location Source and Destination -- The Routing Chain

The location computation has special handling for multi-step routing:

```
location_id  -->  location_dest_id  -->  location_final_id
   (source)         (intermediate)        (final destination)
```

**`_compute_location_dest_id`** applies this priority:
1. If `picking_id` exists: use `picking_id.location_dest_id`
2. Else if `rule_id.location_dest_from_rule` exists: use rule's destination
3. Else: use `picking_type_id.default_location_dest_id`

Then, if both `location_final_id` and `location_dest_id` are set:
- If `location_final_id` is a child of `location_dest_id`: force `location_dest_id = location_final_id`
- If `location_dest_id` is a customer location and `location_final_id` is different (inter-company transit): force `location_dest_id = location_final_id`

The inverse `_set_location_dest_id` applies **putaway strategy** to all move lines, redirecting them to optimal sub-locations.

### The `state` Field -- Full State Machine

The state field drives the entire lifecycle of a stock move:

```
draft ──(confirm)──> confirmed ──(assign)──> assigned ──(done)──> done
                    │                      ▲
                    │                      │
                    └──(wait for orig)──> waiting ────────────> partially_available
                    │
                    └──(cancel)──────────────────────────────> cancel
```

| State | Meaning | Can Edit Demand? | Reserves Stock? |
|---|---|---|---|
| `draft` | Newly created, not confirmed. Not yet part of operations. | Yes | No |
| `confirmed` | Confirmed, waiting for availability. | Yes (triggers unreserve) | No |
| `waiting` | Waiting for upstream moves to complete. | Yes | No |
| `partially_available` | Some quantity reserved, more needed. | Yes (triggers unreserve) | Partial |
| `assigned` | Fully reserved. All stock is available. | Yes (triggers unreserve) | Yes |
| `done` | Physically moved and confirmed. | No | Yes (quants updated) |
| `cancel` | Cancelled. No stock movement. | No | No (unreserves if was reserved) |

State transitions are **not** done by writing directly to the `state` field in normal operation. Instead, they are driven by the action methods:

- `draft → confirmed/waiting`: `_action_confirm()`
- `confirmed/waiting/partially_available → assigned`: `_action_assign()`
- `* → done`: `_action_done()`
- `* → cancel`: `_action_cancel()`

The `_recompute_state()` method recalculates state based on quantity information, useful after quantity changes.

### The `procure_method` Field -- MTS vs MTO

The `procure_method` determines how the system sources products:

| Method | Behavior | Use Case |
|---|---|---|
| `make_to_stock` (default) | System checks existing stock at `location_id` before creating procurement. If stock is available, reserve it. If not, the move stays `confirmed` waiting. | Regular stock moves, replenishment |
| `make_to_order` | Immediately creates a procurement to source the product, bypassing available stock. The move stays in `waiting` until the procurement creates another move that delivers to `location_id`. | MTO (Make To Order), drop-shipping |

Additionally, the `stock.rule` model supports `mts_else_mto` -- a hybrid that:
1. Checks if stock is available at the source location
2. If yes: behaves like `make_to_stock`
3. If no: falls back to `make_to_order`

This is computed dynamically in `_prepare_procurement_qty()` which calculates the actual quantity to procure by subtracting free stock from the needed quantity.

### The `move_line_ids` -- Reservation and Execution

`stock.move.line` records represent the **granular execution** of a move. A move has move lines when:

1. **Reserved:** Stock has been reserved (state `assigned`). Each line represents a specific quant (lot, package, owner, location) being reserved.
2. **Done:** Stock has been physically moved. Lines record what was actually moved.

**Key fields on `stock.move.line`:**

| Field | Purpose |
|---|---|
| `location_id` | Where this specific line's stock comes from |
| `location_dest_id` | Where this specific line's stock goes |
| `lot_id` | Specific lot/serial (if tracked product) |
| `lot_name` | Lot name for new lots (before lot creation) |
| `package_id` | Source package being moved |
| `result_package_id` | Destination package |
| `owner_id` | Owner of the quants (consignment) |
| `quantity` | Quantity moved in `product_uom_id` |
| `quantity_product_uom` | Quantity converted to product's default UoM |
| `picked` | Whether this line has been physically picked |

The existence of move lines with `quantity > 0` at a location **reserves stock** in the `stock.quant` table. Removing move lines (`_do_unreserve`) unreserves stock.

### Chained Moves (`move_orig_ids` / `move_dest_ids`)

The move chaining system creates **dependency trees**:

```
receipt (supplier) ──> putaway ──> internal transfer ──> picking (customer)
   move_orig_ids=[]       move_orig_ids=[receipt]     move_orig_ids=[putaway]
   move_dest_ids=[putaway] move_dest_ids=[transfer]    move_dest_ids=[]
```

**Key behaviors:**
- When a move in a chain is confirmed with `move_orig_ids`, it goes to `waiting` state instead of `confirmed`
- When the origin move is done, `_action_assign()` is automatically triggered on destination moves via `_trigger_assign()`
- `propagate_cancel=True` (default): cancelling a move propagates cancellation down the chain (if all siblings are also cancelled)
- `propagate_cancel=False`: only unlinks the origin reference, does not cancel downstream moves

The `_break_mto_link()` method severs the chain, converting a dependent move to `make_to_stock` so it no longer waits for its parent.

### `stock.move.line` -- Full Reference

The `stock.move.line` model (`stock_move_line` table) records the granular execution of a move. **Table order:** `result_package_id desc, id` -- lines with destination packages appear first.

#### `stock.move.line` Fields (L1)

| Field | Type | Default | Description |
|---|---|---|---|
| `picking_id` | `Many2one` | -- | Parent transfer. `bypass_search_access=True`. Indexed. |
| `move_id` | `Many2one` | -- | Parent move. Checked against company. Indexed. |
| `company_id` | `Many2one` | required | Set from parent move or picking on create. Readonly after set. Indexed. |
| `product_id` | `Many2one` | required | Domain: `type != 'service'`. Checked against company. Indexed. |
| `allowed_uom_ids` | `Many2many` | computed | UoMs allowed for this product (product UoM + UoM category UoMs + seller UoMs). |
| `product_uom_id` | `Many2one` | computed | Line's unit of measure. Defaults to move's `product_uom` or product's `uom_id`. Stored, computed, readonly=False. |
| `quantity` | `Float` | 0 | **Quantity done** in `product_uom_id`. Stored. Computed from `quant_id` onchange when source quant is selected. |
| `quantity_product_uom` | `Float` | computed | `quantity` converted to product's default UoM. Stored. Used for reservation. |
| `picked` | `Boolean` | computed | True if state is done OR (with `allow_parent_move_picked_reset` context) parent move is picked. |
| `package_id` | `Many2one` | -- | **Source package** being picked up. Domain restricts to packages at `location_id`. Ondelete: `restrict`. |
| `lot_id` | `Many2one` | -- | Lot/serial assigned. Domain restricts to lots for this product. |
| `lot_name` | `Char` | -- | Lot name for new lots (before lot is created). Entered manually, then `_create_and_assign_production_lot` converts to `lot_id`. |
| `result_package_id` | `Many2one` | -- | **Destination package**. Domain complex: allows packages already at destination, the source package itself (for repack), or empty packages that have no move lines or whose lines go to the same destination. |
| `result_package_dest_name` | `Char` | related | Display name of destination package. |
| `package_history_id` | `Many2one` | -- | Points to `stock.package.history` record created during `_action_done`. Indexed `btree_not_null`. Used for traceability. |
| `is_entire_pack` | `Boolean` | -- | True if this line was added by scanning an entire package. Used for pack scanning workflows. |
| `date` | `Datetime` | `now` | When the line was processed. Updated to `now` when quantity is increased, picked status changes, or line is done. |
| `scheduled_date` | `Datetime` | related | Related from `move_id.date`. |
| `owner_id` | `Many2one` | -- | Owner of quants being moved. Used in consignment. Indexed `btree_not_null`. |
| `location_id` | `Many2one` | computed | Source location. Computed from `move_id.location_id` or `picking_id.location_id`. Required. Indexed. |
| `location_dest_id` | `Many2one` | computed | Destination location. Same pattern as source. Required. Indexed. |
| `location_usage` | `Selection` | related | `location_id.usage`. |
| `location_dest_usage` | `Selection` | related | `location_dest_id.usage`. |
| `lots_visible` | `Boolean` | computed | True if tracking is not `none` and picking type allows lot handling. |
| `picking_type_id` | `Many2one` | computed | `picking_id.picking_type_id`. |
| `picking_type_use_create_lots` | `Boolean` | related | Whether picking type creates new lots. |
| `picking_type_use_existing_lots` | `Boolean` | related | Whether picking type uses existing lots. |
| `state` | `Selection` | related | `move_id.state`, stored for filtering. |
| `consume_line_ids` | `Many2many` | -- | Lines consumed to produce this one (used in manufacturing tracking). |
| `produce_line_ids` | `Many2many` | -- | Lines produced by consuming this one. |
| `tracking` | `Selection` | related | `product_id.tracking` ('none', 'lot', 'serial'). |
| `quant_id` | `Many2one` | -- | Dummy field used in the detailed operation view to select a source quant. Not stored. On write, triggers `_copy_quant_info` to populate lot/package/location/owner. |
| `package_history_id` | `Many2one` | -- | Links line to the `stock.package.history` record created when a move is done. `btree_not_null` index. |

#### `stock.move.line` Key Methods

**`_action_done()`** -- Executes the move (called on all lines of done moves):
1. Validate `quantity` is non-negative and respects UoM rounding
2. Delete zero-quantity lines (unless `is_inventory`)
3. Require `lot_id` for tracked products (raise `UserError` if missing)
4. Auto-create lots from `lot_name` if picking type allows it
5. Call `_synchronize_quant(-qty, source_location)` -- unreserve from source
6. Call `_synchronize_quant(+qty, dest_location, package=result_package_id)` -- add to destination
7. If `available_qty < 0` (negative quant): call `_free_reservation()` to unreserve other lines
8. Create `stock.package.history` records for result packages
9. Call `result_package_id._apply_dest_to_package()` to finalize package destinations
10. Set `date = now()`

**`_synchronize_quant(quantity, location, action="available", in_date=False)`** -- Core quant mutation:
- `action="available"`: calls `stock.quant._update_available_quantity()`
- `action="reserved"`: calls `stock.quant._update_reserved_quantity()` (only if not bypassing reservation)
- If `available_qty < 0` and a `lot_id` is involved: tries to compensate using untracked quants at the same location, maintaining lot traceability
- Returns `(available_qty, in_date)` tuple

**`_free_reservation(product_id, location_id, quantity, lot_id, package_id, owner_id, ml_ids_to_ignore)`** -- Unreserve conflicting move lines when an edit causes negative quants:
- Searches for non-done/non-cancelled move lines with matching `(product, location, lot, package, owner)` where `quantity_product_uom > 0` and `picked=False`
- Sort order: current picking first, then by scheduled date (most recent first)
- Unlinks or partially reduces candidate move lines until the quantity is satisfied
- Calls `move_id._action_assign()` on affected moves to reassign them

**`_apply_putaway_strategy()`** -- Redirects lines to optimal sub-locations after reservation:
- Groups lines by `result_package_id.outermost_package_id`
- For package-type-aware putaway: uses the package's `package_type_id` to determine routing
- For non-packaged: calls `location_dest_id._get_putaway_strategy(product, qty, packaging)`
- Reads `move_id.location_dest_id.child_internal_location_ids` as the allowed sub-location scope

**`_onchange_serial_number()`** -- Onchange when lot_name/lot_id changes:
- Auto-sets `quantity = 1` for serial-tracked products
- Warns if the same serial number appears in multiple move lines of the picking
- Warns (and suggests a different source location) if the serial number exists in a location different from the picking's source location
- Uses `stock.quant._check_serial_number()` for location recommendation

**`_get_aggregated_product_quantities(strict=False, except_package=False)`** -- Used by reports to aggregate lines by product/description/UoM:
- Follows backorder chain (`picking.backorder_ids`) to include quantities in follow-on pickings
- Filters out lines with result packages if `except_package=True`
- Computes `qty_ordered` (original demand) and `quantity` (done) separately for backorder reporting

**`action_revert_inventory()`** -- Reverts an inventory adjustment move by creating a counter-move:
- Only processes lines where `is_inventory=True` and `quantity != 0`
- Creates a `stock.move` with swapped `location_id`/`location_dest_id`, same product/UoM/quantity, `is_inventory=True`, `picked=True`
- Creates corresponding move lines preserving lot/package/owner
- Calls `_action_done()` on the new move and returns the list of affected line IDs

**`_pre_put_in_pack_hook()` / `_put_in_pack()` / `action_put_in_pack()`** -- Packaging workflow:
- `_pre_put_in_pack_hook` checks destinations (if mixed destinations, triggers `stock.package.destination` wizard)
- `_put_in_pack` creates or reuses a `stock.package`, applies putaway strategy for single-line packs, sets `result_package_id`
- `action_put_in_pack` handles both individual lines and entire packages, delegates to `_pre_put_in_pack_hook`, triggers auto-print if `picking_type_id.auto_print_package_label`

**`_unlink_except_done_or_cancel()`** -- Ondelete hook preventing deletion of non-cancelled/non-done lines.

#### `stock.move.line` Lifecycle

```
create() → (if picking exists and not done):
    → link to existing move OR create new stock.move
    → if reservation needed: _update_reserved_quantity on quants
    → if move is done: _update_available_quantity on quants
    → call _action_assign on next_moves

write() → (if quantity/location/lot/package/owner/product_uom changes):
    → if not done: _synchronize_quant(action="reserved") to update reservation
    → if done: undo the done move line + re-reserve next_moves
    → if quantity increased: set date=now
    → unreserve/reserve downstream moves

unlink() → _update_reserved_quantity(-qty, location) before deletion
        → _recompute_state on parent move
```

#### `_free_reservation_index` Partial Index

```sql
CREATE INDEX ON stock_move_line
    (id, company_id, product_id, lot_id, location_id, owner_id, package_id)
WHERE state IS NULL OR state NOT IN ('cancel', 'done')
  AND quantity_product_uom > 0
  AND picked IS NOT TRUE
```

This partial index covers the hot path for `_free_reservation()` queries, which search by product/location/lot/package/owner for unreserved, non-picked, non-done lines. It excludes the vast majority of done/cancelled lines from the index, keeping it lean.

#### `stock.move.line` Write Behavior on Done Moves

When editing a done move line, `write()` has special handling:
1. Undoes the original quantity at the destination location (`_synchronize_quant(-qty, dest, package=result_package_id)`)
2. Re-applies the quantity at the source location (`_synchronize_quant(qty, source)`)
3. Unreserves and re-assigns `move_dest_ids` of the parent move
4. Logs the change via `_log_message()` on the picking's chatter using the `stock.track_move_template` message template

This means editing a done line is equivalent to: undo → redo at corrected location/lot/package. The system propagates the correction downstream automatically.

---

## L3: Core Methods -- Edge Cases, Workflow Triggers, and Failure Modes

### `_action_confirm(merge=True, merge_into=False, create_proc=True)`

**Purpose:** Transitions moves from `draft` to `confirmed` or `waiting`. This is the **entry point** into the stock operation system.

**Algorithm:**

```
For each draft move:
  If has move_orig_ids:
    → state = 'waiting'  (depends on upstream)
    → add to move_create_proc if make_to_order
  Else if procure_method == 'make_to_order':
    → state = 'waiting'
    → add to move_create_proc (will create procurement)
  Else if rule_id.procure_method == 'mts_else_mto':
    → state = 'confirmed'
    → add to move_create_proc (procurement checks stock)
  Else:
    → state = 'confirmed'

  If should_be_assigned:
    → assign to picking (batch by ref_ids, location_id, location_dest_id)

After all confirmed:
  → run procurements for all make_to_order moves
  → write state 'confirmed' / 'waiting' in batch
  → assign picking for unassigned moves (batch)
  → check company
  → merge moves (if merge=True)
  → handle negative moves (returns, push rules)
  → assign at confirm for bypass-reservation moves
```

**Edge cases handled:**

1. **Negative `product_uom_qty`:** Moves with negative demand are transformed into return moves. Locations are swapped (`location_id` ↔ `location_dest_id`), and the move's `picking_type_id` is set to the return picking type. These moves are assigned to return pickings.

2. **MTS+MTO hybrid (`mts_else_mto`):** The `rule_id.procure_method == 'mts_else_mto'` case triggers procurement but the move itself goes to `confirmed`. The procurement checks free stock and only creates a sourcing move for the deficit quantity.

3. **Merge:** Confirmed/waiting/partially_available/assigned moves with the same product, UoM, location pair are merged (see `_merge_moves`). Merge reduces database records and simplifies operations. Negative moves are merged separately and can absorb positive moves.

4. **Push rules for negative moves:** If a negative move has a `location_final_id` different from `location_dest_id`, it triggers `_push_apply()` to create a new move pushing the returned quantity to the final destination.

5. **Auto-assign at confirm:** Moves whose `picking_type_id.reservation_method == 'at_confirm'` or whose `reservation_date <= today` are immediately assigned after confirmation via `_action_assign()`.

**Failure modes:**
- If a move in `waiting` state has its origin move cancelled, the waiting move does NOT automatically revert to `confirmed`. It stays `waiting` until explicitly reassigned.
- Procurement creation can fail (e.g., no vendor, product not purchasable). The MTO move stays `waiting`.
- Merge can fail if moves have conflicting `move_line_ids` (though in practice merge happens before lines are created).

### `_action_assign(force_qty=False)`

**Purpose:** Reserves stock by creating `stock.move.line` records linked to specific `stock.quant` records. Transitions from `confirmed/waiting/partially_available` to `assigned` or keeps at `partially_available`.

**Algorithm:**

```
For each move (filtered to confirmed/waiting/partially_available unless force_qty):
  Compute missing_reserved_uom_quantity = product_uom_qty - already_reserved

  If bypass reservation (virtual locations, non-storable):
    → create move lines directly (no quant reservation)
    → consider parent move lines via _get_available_move_lines
    → state = 'assigned'

  Else if no move_orig_ids:
    → call _update_reserved_quantity (searches quants, creates move lines)
    → if fully reserved: state = 'assigned'
    → else: state = 'partially_available' (or stays confirmed if nothing reserved)

  Else (has move_orig_ids -- chain reservation):
    → compute what parent moves brought in (done siblings)
    → subtract what sibling moves consumed
    → distribute available quantity across move lines
    → update/assign as needed

After all:
  → write state in batch
  → check entire pack
  → apply putaway strategy to redirect move lines
```

**Edge cases:**

1. **Multi-warehouse/MTO chain:** For MTO moves with `move_orig_ids`, the system queries the done move lines of parent moves to determine what quantity is actually available to consume. This prevents over-reservation when upstream moves deliver less than planned.

2. **Sibling consumption:** When multiple outgoing moves share the same origin (e.g., two deliveries from the same receipt), the system subtracts what sibling moves have already taken from the available pool.

3. **Serial number tracking:** For tracked products, `_action_assign` generates `next_serial_count = product_uom_qty` so the UI knows how many serial numbers to prompt for.

4. **`force_qty` parameter:** Used in `_action_done` to force-assign moves with incomplete reservations before validation. This ensures partial moves can still be processed.

5. **Reservation bypass:** `_should_bypass_reservation()` returns True for non-storable products and locations that are not real (e.g., view locations, partner locations). For these, move lines are created without actually reserving quants.

6. **Partial reservation:** If only some quants are available, the move goes to `partially_available`. The `quantity` field tracks how much is reserved vs. demanded.

7. **Putaway strategy:** After creating move lines, `_apply_putaway_strategy()` redirects them to optimal sub-locations based on putaway rules (e.g., routing product A to shelf A1, product B to shelf B2).

**Failure modes:**
- If no quants are available at the source location, the move stays `confirmed`. `_trigger_assign()` can re-trigger this later when incoming moves arrive.
- If some but not all quants are available, the move goes to `partially_available`. A backorder will be needed when validating.
- Serial number reservation can fail if fewer serial numbers are available than demanded.

### `_action_done(cancel_backorder=False)`

**Purpose:** Marks moves as done, updates quants, creates accounting entries (via `stock_account`), triggers downstream moves, and optionally creates backorders.

**Algorithm:**

```
1. Confirm all draft moves first (filtered(lambda m: m.state == 'draft')._action_confirm(merge=False))

2. Filter moves to process:
   - Cancel moves with picked=False and quantity<=0 (unless is_inventory)
   - Unlink non-picked move lines for picked moves
   - Keep moves where picked=True and quantity>0 (or is_inventory)

3. For remaining moves_todo:
   a. Create backorder if cancel_backorder=False and quantity < product_uom_qty:
      → _create_backorder() creates new moves with the undelivered quantity
      → backorder moves are confirmed but not auto-assigned

   b. Execute move lines: moves_todo.move_line_ids._action_done()
      → updates stock.quant (removes from source, adds to destination)
      → creates accounting entries if stock_account is installed
      → updates ownership

   c. Validate result packages (no split across multiple locations)

   d. Write state='done', date=now()

   e. Trigger push rules: moves_todo._push_apply()
      → creates new moves for routes (e.g., receipt → quality control → stock)
      → new push moves are confirmed

   f. Trigger downstream moves: for each move_dest in moves_todo.move_dest_ids:
      → call _action_assign() on the destination moves
      → propagates availability down the chain

   g. Check entire pack

   h. If picking exists and not cancel_backorder:
      → create backorder picking via picking._create_backorder()
      → check entire pack on the backorder

   i. Check quantity consistency: _check_quantity()
```

**Edge cases:**

1. **Backorder creation:** If `quantity < product_uom_qty` (i.e., not all demanded quantity was processed), `_create_backorder()` splits the move. The original move keeps the done quantity, and a new "WH/OA" move is created with the remaining quantity. The backorder is confirmed and merged with existing moves. This happens twice: once per-move (`_create_backorder` on `moves_todo`) and once per-picking (`picking._create_backorder`).

2. **Non-picked move lines:** In barcode/warehouse app scenarios, move lines that were not physically scanned (`picked=False`) are automatically unlinked before validation. Only picked lines are processed.

3. **Zero-quantity moves:** If a move has `quantity == 0` (and is not an inventory adjustment), it is cancelled unless `cancel_backorder=True`.

4. **Push rules and chains:** After a move is done, `_push_apply()` can create new moves based on route rules (e.g., incoming receipt → push to QC location → push to stock). The system tracks whether a destination move should be unlinked from the chain (if its new location doesn't match the expected chain location).

5. **`_action_synch_order`:** A hook method called at the end (returns True by default, overridden in sale/purchase to sync line quantities back to the source document).

6. **Scrap context:** If `context.get('is_scrap')` is True, the method returns early without creating backorders (scrap moves don't have backorders).

**Failure modes:**
- If result packages contain quants at multiple different locations, an error is raised: "You cannot move the same package content more than once in the same transfer."
- If `stock_account` is installed and the move's `price_unit` is 0 for a real/average costing product, accounting entries may be incorrect.
- If the destination location has `should_bypass_reservation()` and the move uses putaway rules, the quant may end up at a different location than `location_dest_id` -- the system handles this correctly via `_push_apply`.
- **`picked` filter:** Any move line with `picked=False` on a `picked=True` move is deleted before processing. This means unscanned items in barcode workflows are automatically excluded from the transfer.
- **Zero-quantity done moves:** A move where `quantity <= 0` and `is_inventory=False` gets cancelled during `_action_done` unless it already has `product_uom_qty == 0` or `cancel_backorder=True`. This prevents accidental transfers with no lines.
- **`next_moves` reassignment:** After a done move line is edited (e.g., wrong lot assigned), the downstream `move_dest_ids` are unreserved and re-assigned to reflect the corrected quantity. This can surface stock availability issues that were masked during the original reservation.

### `_action_cancel()`

**Purpose:** Cancels moves, unreserves stock, and optionally propagates cancellation to destination moves.

**Algorithm:**

```
1. Validate: cannot cancel moves that are done (unless they went to inventory location)
   → raises UserError for done non-inventory moves

2. For each move to cancel:
   a. Set picked=False
   b. Call _do_unreserve() (unlink move lines, free quants)
   c. Set state='cancel'
   d. Propagate if propagate_cancel=True:
      → only cancel destination moves if ALL siblings are also cancelled
      → break the chain: set procure_method='make_to_stock', unlink from move_orig_ids
      → if cancel_moves_origin config is set, also cancel upstream moves
   e. If propagate_cancel=False:
      → only break the link, don't cancel downstream
      → set procure_method='make_to_stock'
```

**Edge cases:**

1. **`done` moves at inventory location:** A move that is done and its destination is an inventory adjustment location (`location_dest_usage == 'inventory'`) CAN be cancelled. This handles the case of inventory adjustment moves that need to be reversed.

2. **Sibling cancellation:** A destination move is only cancelled if ALL of its sibling origin moves are cancelled. For example, if a receipt feeds two internal transfers and only one transfer is cancelled, the receipt's destination link to the cancelled transfer is removed but the receipt itself is NOT cancelled.

3. **`cancel_moves_origin` config:** A system parameter (`stock.cancel_moves_origin`) controls whether cancelling a move also cancels its upstream sources.

### `_do_unreserve()`

**Purpose:** Removes reservation by deleting `stock.move.line` records, which frees the associated `stock.quant` records.

**Algorithm:**

```
For each move (skip cancel/done+inventory/picked moves):
  → collect all non-picked move lines to unlink
  → unlink the move lines
  → call _recompute_state() for moves that had lines removed

Moves that are done CANNOT be unreserved (raises UserError).
Moves that are picked: skipped (already processed by the operator).
```

**Key distinction from `_action_cancel`:**
- `_do_unreserve` only removes the reservation (deletes move lines)
- The move itself stays in its current state (typically `confirmed` or `partially_available`)
- Used when reducing `product_uom_qty` on an assigned/confirmed move
- `_action_cancel` also changes the state to `cancel` and handles chain propagation

### `_prepare_move_line_vals(quantity=None, reserved_quant=None)`

**Purpose:** Creates the dictionary of default values for creating a `stock.move.line` record. Called when reserving stock and when generating move lines for done operations.

**Returns:**
```python
{
    'move_id': self.id,
    'product_id': self.product_id.id,
    'product_uom_id': self.product_uom.id,
    'location_id': self.location_id.id,
    'location_dest_id': self.location_dest_id.id,
    'picking_id': self.picking_id.id,
    'company_id': self.company_id.id,
}
```

**If `quantity` is provided:** Converts to UoM-consistent quantity. If the rounded conversion matches the original, stores the converted quantity. Otherwise, stores the raw quantity and sets `product_uom_id` to the product's default UoM.

**If `reserved_quant` is provided:** Overrides location, lot, package, and owner from the quant's values. This is how reserved move lines get linked to specific quants.

**Used by:**
- `_action_assign` for creating reservation move lines
- `_generate_serial_move_line_commands` for serial number assignments
- `_set_quantity_done` for creating done move lines
- `_action_done` backorder creation

### `_update_reserved_quantity(need, location_id, lot_id, package_id, owner_id, strict)`

**Purpose:** The core reservation engine. Called from `_action_assign` to find quants and create move lines.

**Algorithm:**
```
1. Call stock.quant._get_reserve_quantity() to find available quants
2. Group quants by (location, lot, package, owner)
3. For each group:
   a. If an existing move line exists with same key: increase its quantity
   b. Else: create a new move line with _prepare_move_line_vals
4. For serial-tracked products: create one move line per unit
5. Return total taken quantity
```

**Interaction with quant reservation:** The `stock.quant` model uses `location_id.warehouse_id` to determine which company the quant belongs to. Quants are reserved by writing to the `reservation_id` field on the quant, creating a `stock.quant.package` link if reserved as a package.

---

## L4: Performance Implications, Historical Changes, and Security Concerns

### Performance Implications

#### 1. N+1 Query Prevention in `_action_assign`

The `_action_assign` method iterates over potentially thousands of moves. Key optimizations:

- **Batch reservation queries:** `stock.quant._get_reserve_quantity()` and `stock.quant._get_quants_by_products_locations()` are called in batches (for MTO moves), not per-move.
- **Prefetching:** `reserved_availability` and `roundings` are read into dictionaries before the loop to avoid per-iteration field cache invalidation.
- **`_read_group` for quantity:** `_compute_quantity` uses `_read_group` instead of looping over move lines, providing a single aggregate query.

**Performance risk:** If a move has thousands of small quants (e.g., individually reserved serial numbers), `_update_reserved_quantity` can generate thousands of `stock.move.line` records. This is slow to create and display. Serial number products should be reserved as whole quants when possible.

#### 2. Move Merge Performance

`_merge_moves()` is called on every `_action_confirm`. It groups moves by a composite key (product, location, UoM, etc.) and merges those sharing the same key. This reduces the number of move records but has a computational cost:

- Uses `itemgetter` for fast grouping
- Float fields are formatted to strings with precision matching to avoid rounding-induced merge failures
- Negative moves are handled in a separate pass to avoid incorrectly absorbing positive moves

**Risk:** In extreme cases with many small moves (e.g., from orderpoints with small reorder quantities), merge can be slow. The `stock.merge_only_same_date` and `stock.merge_ignore_date_deadline` config parameters allow tuning merge behavior.

#### 3. `_compute_forecast_information` Performance

This computed field runs on every stock move in a view. It:
- Prefetches `type` and `uom_id` on products in a single query
- Batches `virtual_available` reads by `(warehouse_id, date)` tuples
- Uses `defaultdict` to group moves by warehouse/location for batch forecast queries
- Only calls the expensive `_get_forecast_availability_outgoing` for outgoing unreserved moves

#### 4. Reservation and Quant Updates

Every `_action_assign` and `_do_unreserve` triggers writes on `stock.quant` records (updating the `reservation_id` field). These writes trigger quant recomputation. In high-concurrency scenarios (multiple operators reserving the same stock simultaneously), this can cause race conditions, mitigated by PostgreSQL's row-level locking.

#### 5. `_product_location_index` Composite Index

The composite index on `(product_id, location_id, location_dest_id, company_id, state)` covers the most common query patterns:
- "Find all moves for product X at location Y"
- "Find all incoming/outgoing moves for a product"
- Reservation queries that join moves with location/quant data

#### 6. `stock.move.line` Index

The `_free_reservation_index` on `stock.move.line` is a partial index:
```sql
CREATE INDEX ON stock_move_line (id, company_id, product_id, lot_id, location_id, owner_id, package_id)
WHERE state IS NULL OR state NOT IN ('cancel', 'done')
  AND quantity_product_uom > 0
  AND picked IS NOT TRUE
```
This index covers all queries finding unreserved move lines, which is the hot path for reservation operations.

### Historical Changes (Odoo 17 to 18 to 19)

#### Odoo 18 Changes

1. **Move line reservation changes:** The reservation mechanism was refactored to handle concurrent reservations better. The `reserved_quant` parameter pattern in `_prepare_move_line_vals` was enhanced.

2. **Putaway strategy changes:** `_apply_putaway_strategy()` was called on move line creation, not just on assignment completion.

3. **Forecast information:** The forecast availability computation was made more efficient with batched virtual_available reads.

4. **`stock.move.line` model introduced (renamed from `stock.pack.operation`):** In Odoo 18, the former `stock.pack.operation` model was replaced by `stock.move.line`. This changed the architecture: pack operations no longer existed as a separate concept. The move line now holds `quantity` (done) and `quantity_product_uom` (reserved), replacing the old `reserved_quantity` pattern on pack operations. The `_free_reservation_index` partial index was introduced in Odoo 18 as part of this refactoring.

5. **`_action_done` moved to `stock.move.line`:** The actual quant mutation logic (`_synchronize_quant`, lot creation, package history) moved from `stock.move._action_done` into `stock.move.line._action_done`. The move's `_action_done` now calls `move_line_ids._action_done()` as a delegation step.

#### Odoo 19 Changes

1. **`_product_location_index`:** Added as a new composite index in Odoo 19 to optimize the common join pattern between moves and locations.

2. **Return move handling:** Negative move detection and transformation logic in `_action_confirm` was refactored to use `Command` for link management instead of write.

3. **`lot_ids` computed field:** The Many2many `lot_ids` field was added as a computed inverse, allowing users to set lots at the move level (creating move lines as needed) rather than only at the move line level.

4. **Reservation date:** The `reservation_date` field and its computation (`_compute_reservation_date`) were enhanced to support the `by_date` reservation method on picking types.

5. **`_set_quantity` improvements:** The decrease/increase processing in `_set_quantity` was refactored with cleaner separation between `_process_decrease` and `_process_increase`.

6. **Push rule propagation:** The `_push_apply()` method was enhanced with better handling of inter-company transit and the `location_final_id` chain logic.

7. **`_action_done` backorder split:** Backorder creation was reorganized: the per-move `_create_backorder()` is called first, then the per-picking `picking._create_backorder()` handles any remaining moves. Previously these overlapped differently.

8. **`merge_extra` context:** A context flag was added to control whether `product_uom_qty` is summed during merge or kept from the first move.

### Security Concerns

#### 1. Access Control

`stock.move` is protected by the `stock` module's ACL:

- **`stock.group_stock_user`:** Can read, write, create, unlink stock moves (full user access)
- **`stock.group_stock_manager`:** Full access including administrative operations
- **`base.group_user`:** Can read moves through picking access

Portal users access stock moves through `stock.picking` records they are followers of or that have `base.group_portal` ACL grants.

**Key security points:**
- Moving quants updates `stock.quant` records with `company_id`. Record rules ensure users only see quants in their allowed companies (`company_ids` domain).
- The `restrict_partner_id` field prevents a move from consuming quants belonging to other owners, even if the user has stock access.
- `location_id`/`location_dest_id` should have `usage != 'view'` enforced (via domain), but this is UI-level enforcement. Server-side code should always validate.

#### 2. Move Line Integrity

The `_action_done` method updates `stock.quant` records directly. Key integrity checks:

- It validates that result packages are not split across multiple locations
- It checks for concurrent modification via PostgreSQL locking on quants
- It validates that the quantity being moved does not exceed available reserved quant quantities

**Known edge case:** If two users simultaneously validate pickings that consume overlapping quants, the second validation can fail silently or produce incorrect results. The system relies on PostgreSQL's `FOR UPDATE` locking on quant records to prevent this, but in high-contention scenarios, race conditions can still occur.

#### 3. Cost Price Exposure

The `price_unit` field (when set manually) is stored in the company's currency. In average costing, this price is used to update the product's `standard_price`. Users with access to stock moves but without accounting access can influence product costs, which can be a concern in organizations without proper separation of duties.

#### 4. Unreserve and Cancel -- Stock Availability Impact

`_do_unreserve` and `_action_cancel` both free up reserved quants. This happens automatically when `product_uom_qty` is reduced on an assigned move. In scenarios with:
- Multiple pickings for the same product
- Partial fulfillment of one picking
- Operator reducing quantities and unreserving stock

...the freed stock becomes available for other pickings. This is correct behavior but can be surprising in workflows where users expect a specific reservation to persist.

### Cross-Module Integration

The `stock.move` model is the integration hub for multiple modules:

| Module | Integration Point |
|---|---|
| `sale_stock` | `_action_synch_order` hook syncs delivered quantities back to sale lines |
| `purchase_stock` | MTO procurement creates purchase orders |
| `mrp` | BOM explode creates component moves; finished product moves |
| `stock_account` | `_action_done` triggers valuation entries via `stock.quant` |
| `stock_accountant` | `price_unit` field used for average/real costing |
| `delivery` | `_action_done` triggers carrier slipts |
| `mail` | Mixin with `mail.thread` for chatter and notifications |
| `sales_team` | `reference_ids` field links to sale order lines |
| `crm` | Opportunity/crm lead can generate stock moves through sales orders |

The `_prepare_procurement_values()` method builds the dictionary passed to `stock.rule.run()`, which in turn calls into module-specific procurement handlers.

### Key Design Patterns

1. **Demand-based:** A move declares WHAT should move and from WHERE to WHERE. The `_action_assign` step reconciles demand with physical reality by reserving specific quants. The `_action_done` step executes the physical movement.

2. **Chain propagation:** Moves are linked via `move_orig_ids`/`move_dest_ids`. When an upstream move is done, downstream moves are automatically assigned. This creates the "push" model for warehouse operations.

3. **Split capability:** Every move can be split (via `_split`). Backorders are created by splitting the original move, keeping the done portion in the original and creating a new move for the remaining quantity.

4. **Reservation decoupling:** The move (demand declaration) is separate from move lines (specific quant reservation). This allows partial reservations, lot-specific assignments, and putaway-based redirection.

5. **Inverse fields:** Computed fields with inverses (`description_picking`, `location_dest_id`, `quantity`, `lot_ids`, `product_qty`) allow bidirectional synchronization between the move and its related records, reducing the need for explicit write calls in many workflows.

---

## Related Models

- **`stock.picking`:** The parent transfer record that groups moves
- **`stock.move.line`:** Granular execution records (per-lot, per-package, per-owner)
- **`stock.quant`:** Physical stock records that are reserved/consumed by moves
- **`stock.rule`:** Procurement rules that generate moves
- **`stock.location`:** Source and destination locations
- **`stock.warehouse.orderpoint`:** Reordering rules that generate moves via procurement
- **`stock.package`:** Packages involved in moves
- **`stock.lot`:** Lot/serial number tracking

## Related Documentation

- [Modules/Stock](Stock.md) -- Overview of the stock module and other stock models
- [Modules/stock_quant](stock_quant.md) -- The `stock.quant` model and inventory tracking
- [Modules/stock_picking](stock_picking.md) -- The `stock.picking` model and transfer operations
- [Modules/stock_location](stock_location.md) -- Warehouse locations and location types
- [Core/API](API.md) -- Odoo ORM decorators (@api.depends, @api.model, etc.) used extensively in this model
- [Patterns/Workflow Patterns](Workflow Patterns.md) -- State machine patterns used in stock moves
