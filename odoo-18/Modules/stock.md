---
title: Stock
description: Inventory management, stock moves, quants, warehouses, routes, and picking operations
version: Odoo 18
modules: [stock, stock_account, stock_picking_batch]
tags: [stock, inventory, warehouse, picking, quant, stock_move]
---

# Stock

**Module:** `stock` | **Models:** `stock.picking`, `stock.move`, `stock.move.line`, `stock.quant`, `stock.location`, `stock.warehouse`, `stock.lot`, `stock.rule`, `stock.route`, `stock.package`, `stock.package.level`, `stock.package.type`, `stock.scrap`, `stock.storage.category`, `stock.orderpoint`, `stock.putaway.rule`
**Source:** `~/odoo/odoo18/odoo/addons/stock/`

---

## Models

### stock.location

Storage locations forming a tree hierarchy. The location tree is the foundation of warehouse organization.

**Key Fields:**
- `name` — Location name (required)
- `complete_name` — Full path "WH/Stock/Shelf A" (computed recursive, stored)
- `location_id` — Parent location (`False` for root/warehouse tops)
- `parent_path` — Materialized path for hierarchy queries (`1/2/5/`, indexed, critical for `child_of` queries)
- `usage` — `supplier` | `view` | `internal` | `customer` | `inventory` | `production` | `transit` (required, indexed)
- `active` — Active flag
- `company_id` — Operating company (shared between companies if empty)
- `scrap_location` — Boolean, marks this as a scrap/damage location
- `replenish_location` — Activate replenish suggestions at this location (computed `False` for non-internal)
- `removal_strategy_id` — FEFO/FIFO/LIFO/Closest removal strategy (inherited from parent if unset)
- `putaway_rule_ids` — One2many to `stock.putaway.rule`
- `barcode` — Barcode for scanning (unique per company)
- `comment` — Html additional information
- `posx`, `posy`, `posz` — Optional bin coordinates (Corridor, Shelves, Height)
- `cyclic_inventory_frequency` — Days between scheduled counts (0 = disabled)
- `last_inventory_date` — Date of last inventory (readonly)
- `next_inventory_date` — Computed next scheduled count (based on frequency or company annual inventory month)
- `storage_category_id` — Storage category for capacity rules
- `warehouse_id` — Computed warehouse this location belongs to
- `child_internal_location_ids` — Computed recursive internal descendants (recursive=True compute)
- `net_weight` / `forecast_weight` — Computed weight fields (from quants + incoming/outgoing move lines)
- `is_empty` — Computed boolean, search-enabled

**Location Usage Types:**
| Usage | Purpose |
|-------|---------|
| `supplier` | Virtual source for incoming goods from vendors |
| `view` | Virtual container for hierarchy; cannot hold stock directly |
| `internal` | Physical warehouse locations where stock resides |
| `customer` | Virtual destination for outgoing deliveries |
| `inventory` | Virtual counterpart for inventory adjustment moves |
| `production` | Virtual counterpart for manufacturing (consumes components, produces finished goods) |
| `transit` | Counterpart for inter-company or inter-warehouse transfers |

**Key Methods:**
- `_compute_complete_name()` — Builds full path `parent/name` recursively (stored)
- `_get_putaway_strategy(product, quantity, package, packaging, additional_qty)` — Returns best destination location applying storage category rules and putaway rules. Handles package type matching, capacity checks, and storage category rules.
- `_get_next_inventory_date()` — Returns next scheduled inventory date: cyclic frequency first, then company annual inventory month/day
- `_get_weight(excluded_sml_ids)` — Returns dict `{location: {'net_weight', 'forecast_weight'}}`
- `_get_removal_strategy(product_id, location_id)` — Returns removal method string; falls back through product category -> parent location chain, defaulting to `fifo`
- `should_bypass_reservation()` — Returns `True` for `supplier`, `customer`, `inventory`, `production`, or scrap locations
- `_check_can_be_used(product, quantity, package, location_qty)` — Validates storage category constraints: weight capacity, product/package capacity, and allow_new_product rules (empty/same/mixed)
- `_child_of(other_location)` — Returns `True` if `self.parent_path` starts with `other_location.parent_path`
- `_is_outgoing()` — Returns `True` if location is `customer` usage or child of inter-company transit
- `_search_is_empty(operator, value)` — Search domain helper for empty locations

**Key Behaviors:**
- Cannot change `usage` to `view` if location contains products
- Cannot convert internal locations with stock to non-internal (raises `UserError`)
- Archiving a location used by an active warehouse is forbidden
- `unlink()` cascades to children locations
- `replenish_location` cannot have parent/child replenish locations simultaneously

---

### stock.warehouse

Warehouse configuration. Owns the tree of locations, picking types, routes, and auto-generated procurement rules.

**Key Fields:**
- `name` — Warehouse name (required)
- `code` — Short code (max 5 chars, unique per company)
- `company_id` — Operating company (readonly, required)
- `partner_id` — Address partner (defaults to company partner)
- `active` — Active flag
- `sequence` — Sort order for multi-warehouse display
- `view_location_id` — Root `view` location for this warehouse's hierarchy (created on warehouse creation)
- `lot_stock_id` — Main internal stock location (child of `view_location_id`)
- `route_ids` — Many2many to `stock.route` (default warehouse routes)
- `reception_steps` — `one_step` | `two_steps` | `three_steps` (incoming flow)
- `delivery_steps` — `ship_only` | `pick_ship` | `pick_pack_ship` (outgoing flow)
- `wh_input_stock_loc_id` — Input/staging location (for `two_steps`/`three_steps` receipts)
- `wh_qc_stock_loc_id` — Quality control location (for `three_steps` receipts)
- `wh_output_stock_loc_id` — Output/staging location (for `pick_ship`/`pick_pack_ship` deliveries)
- `wh_pack_stock_loc_id` — Packing location (for `pick_pack_ship` deliveries)
- `resupply_wh_ids` — Many2many of warehouses to resupply from
- `resupply_route_ids` — Auto-created resupply routes (inverse of `supplied_wh_id`)
- `crossdock_route_id` — Auto-created cross-dock route
- `reception_route_id` — Auto-created receipt route
- `delivery_route_id` — Auto-created delivery route
- `mto_pull_id` — MTO (Make to Order) stock.rule
- `in_type_id` — Default receipt picking type
- `out_type_id` — Default delivery order picking type
- `int_type_id` — Default internal transfer picking type
- `pick_type_id` — Default pick operation type
- `pack_type_id` — Default pack operation type
- `qc_type_id` — Default quality control picking type
- `store_type_id` — Default storage operation type
- `xdock_type_id` — Default cross-dock type

**Reception Step Flow:**
| Step | Flow |
|------|------|
| `one_step` | Vendor -> WH/Stock |
| `two_steps` | Vendor -> WH/Input -> WH/Stock |
| `three_steps` | Vendor -> WH/Input -> WH/Quality Control -> WH/Stock |

**Delivery Step Flow:**
| Step | Flow |
|------|------|
| `ship_only` | WH/Stock -> Customer |
| `pick_ship` | WH/Stock -> WH/Output -> Customer |
| `pick_pack_ship` | WH/Stock -> WH/Pack -> WH/Output -> Customer |

**Key Methods:**
- `_create_or_update_sequences_and_picking_types()` — Creates or updates all `stock.picking.type` records and their `ir.sequence`; picks next available color for kanban
- `_create_or_update_route()` — Creates or updates `stock.route` records for this warehouse
- `_create_or_update_global_routes_rules()` — Updates global rules (MTO, Buy, etc.) that apply to this warehouse
- `create_resupply_routes(warehouse_ids)` — Creates buy/pull routes for inter-warehouse resupply
- `_check_multiwarehouse_group()` — Automatically enables/disables `group_stock_multi_warehouses` based on warehouse count; activates `group_stock_multi_locations` if >1 warehouse

**Namedtuple Routing:**
```python
Routing = namedtuple('Routing', ['from_loc', 'dest_loc', 'picking_type', 'action'])
```

---

### stock.picking.type

Categories of picking operations. One picking type per warehouse per operation kind.

**Key Fields:**
- `name` — Operation type name (required, translatable)
- `code` — `incoming` | `outgoing` | `internal` (required, default `incoming`)
- `sequence_code` — Prefix for reference sequence (required)
- `sequence_id` — Auto-created `ir.sequence` for reference generation
- `warehouse_id` — Parent warehouse (computed from company)
- `color` — Kanban color index
- `sequence` — Sort order in kanban view
- `default_location_src_id` — Default source location (computed from code/warehouse)
- `default_location_dest_id` — Default destination location (computed from code/warehouse)
- `return_picking_type_id` — Linked return picking type
- `show_entire_packs` — If `True`, forces pack-level operations
- `show_operations` — If `True`, shows detailed move line operations in UI
- `use_create_lots` — If `True`, lots can be created on the fly (computed: always `True` for incoming)
- `use_existing_lots` — If `True`, lots must already exist to use (computed: always `True` for outgoing)
- `print_label` — Show "Print Shipping Label" option (computed from code)
- `reservation_method` — `at_confirm` | `manual` | `by_date` (how moves are reserved)
- `reservation_days_before` — Days before scheduled date to reserve (for `by_date`)
- `reservation_days_before_priority` — Days before for priority moves (for `by_date`)
- `move_type` — `direct` (ASAP) | `one` (when all ready) — shipping policy
- `create_backorder` — `ask` | `always` | `never` (backorder creation behavior on validation)
- `auto_show_reception_report` — Auto-show reception report on validation
- `auto_print_delivery_slip` / `auto_print_return_slip` — Auto-print on validation
- `auto_print_product_labels` — Auto-print product labels (Dymo, ZPL formats)
- `auto_print_lot_labels` — Auto-print lot/SN labels
- `auto_print_reception_report` / `auto_print_reception_report_labels` — Auto-print reception report
- `auto_print_packages` — Auto-print packages
- `auto_print_package_label` / `package_label_to_print` — Auto-print label on "Put in Pack"
- `product_label_format` — Label format: `dymo`, `2x7xprice`, `4x7xprice`, `4x12`, `4x12xprice`, `zpl`, `zplxprice`
- `lot_label_format` — Lot label format: `4x12_lots`, `4x12_units`, `zpl_lots`, `zpl_units`
- `is_favorite` — Show this type in user's dashboard (per-user, inverse-capable, sudo-computed)
- `favorite_user_ids` — Many2many to `res.users` (favorites)
- `picking_properties_definition` — `PropertiesDefinition` for picking custom properties
- `count_picking_draft`, `count_picking_ready`, `count_picking`, `count_picking_waiting`, `count_picking_late`, `count_picking_backorders` — Computed picking counts for kanban dashboard
- `count_move_ready` — Computed count of assigned moves
- `kanban_dashboard_graph` — JSON graph data for dashboard (past/today/future categories)
- `barcode` — Barcode field
- `show_picking_type` — Computed, `True` for incoming/outgoing/internal code
- `hide_reservation_method` — Computed, `True` for incoming picking types

---

### stock.picking

Represents a stock operation: delivery, receipt, or internal transfer. The main document users interact with.

**Key Fields:**
- `name` — Reference (sequence-generated, e.g., "WH/IN/00001", readonly after create, trigram indexed)
- `origin` — Source document (SO, PO, MO, or any reference string, trigram indexed)
- `note` — Html notes
- `backorder_id` — Parent picking if this is a backorder
- `backorder_ids` — One2many of created backorders
- `return_id` — Original picking if this is a return
- `return_ids` — One2many of return pickings
- `return_count` — Computed count of returns
- `state` — `draft` | `waiting` | `confirmed` | `assigned` | `done` | `cancel` (computed from moves, stored, indexed)
- `priority` — `0` (Normal) | `1` (Urgent)
- `scheduled_date` — Planned date (inverse writes to all move dates)
- `date_deadline` — Computed deadline from linked sale/purchase lines
- `has_deadline_issue` — Boolean, `True` if `date_deadline < scheduled_date`
- `date` — Creation date (default `Datetime.now`, copy=False)
- `date_done` — Actual completion datetime
- `delay_alert_date` — Computed from moves, max upstream delay date
- `location_id` / `location_dest_id` — Source/destination (computed from picking type, with partner property fallback)
- `picking_type_id` — `stock.picking.type` (required, indexed)
- `warehouse_address_id` — Related warehouse partner address
- `partner_id` — Contact partner (indexed, btree_not_null)
- `owner_id` — Consignment owner — if set, goods are on behalf of this partner
- `company_id` — Related from `picking_type_id.company_id` (readonly, stored, indexed)
- `user_id` — Responsible user
- `group_id` — `procurement.group` (linked from moves, stored)
- `move_type` — `direct` | `one` (shipping policy, computed from picking type or procurement group)
- `move_ids` — One2many to `stock.move` (the aggregate moves)
- `move_ids_without_package` — Domain-filtered subset (excludes pack-level moves)
- `move_line_ids` — One2many to `stock.move.line` (detailed operations)
- `move_line_ids_without_package` — Domain-filtered detailed ops without packages
- `package_level_ids` / `package_level_ids_details` — One2many to `stock.package_level`
- `has_scrap_move` — Computed boolean, `True` if any scrap move linked
- `move_line_exist` — Computed, `True` if any move lines exist
- `has_packages` — Computed, `True` if any `result_package_id` on move lines
- `show_check_availability` — Computed, controls "Check Availability" button visibility
- `show_allocation` — Computed, controls "Allocation" button visibility
- `show_operations` — Related to `picking_type_id.show_operations`
- `show_lots_text` — Computed, `True` if should show lot name text field (for create-only lot tracking)
- `has_tracking` — Computed, `True` if any tracked products in moves
- `printed` / `signature` / `is_signed` — Printing and signature fields
- `is_locked` — Default `True`; when `True`, initial demand cannot be edited
- `weight_bulk` — Computed weight of products NOT in packages
- `shipping_weight` / `shipping_volume` — Total shipping weight/volume
- `products_availability` — Computed string: "Available", "Exp [date]", "Not Available"
- `products_availability_state` — Computed selection: `available` | `expected` | `late`
- `picking_properties` — Properties definition from picking type
- `show_next_pickings` — Computed, `True` if there are chained destination pickings
- `json_popover` — JSON for delay alert popover widget

**State Machine (stored, computed from moves):**
```
draft ──(action_confirm)──> confirmed ──(action_assign)──> assigned ──(_action_done)──> done
    │                                         │
    └───(action_cancel)─── cancel <──────────────────────────────────────┘
```

**State Transition Logic (`_compute_state`):**
- All moves `cancel` -> picking `cancel`
- Any move `draft` + others `draft|cancel` -> picking `draft`
- Any move `waiting` + others `draft|waiting|cancel` -> picking `waiting`
- All moves `assigned` + some `confirmed` -> picking `confirmed`
- All moves `assigned|done` + none `confirmed|waiting|draft` -> picking `assigned`
- All moves `done` -> picking `done`

**Key Methods:**
- `action_confirm()` — Confirms the picking: generates moves for draft package levels, calls `move._action_confirm()` on draft moves, triggers scheduler for forecasted shortages
- `action_assign()` — Checks availability: generates package level moves, confirms draft pickings, calls `move._action_assign()` sorted by priority/date
- `action_cancel()` — Cancels all moves, locks the picking
- `_action_done()` — Core validation: calls `move._action_done()` on all non-cancelled moves, sets `date_done`, resets priority, triggers downstream assignment for incoming/internal completions, sends confirmation email
- `_sanity_check(separate_pickings)` — Pre-validation checks: no empty pickings, tracked products have lot/SN, quantities set (raises `UserError` with specific messages)
- `_check_entire_pack()` — Auto-creates `stock.package_level` records for entire packages being moved
- `do_unreserve()` — Unreserves all moves and deletes draft package levels
- `do_print_picking()` — Triggers `stock.action_report_picking` report
- `action_detailed_operations()` — Opens detailed operations list view
- `action_next_transfer()` — Opens the next chained picking
- `_get_show_allocation(picking_type_id)` — Determines if the allocation button should be shown (for incoming operations, checks for existing moves in warehouse)
- `_compute_location_id()` — Sets source/dest locations from picking type, with partner property fallback for supplier (`property_stock_supplier`) / customer (`property_stock_customer`) destinations

---

### stock.move

Individual product movement records within a picking (or standalone). The atomic unit of stock transfer.

**Key Fields:**
- `name` — Description (required, auto from product, max 2000 chars)
- `sequence` — Integer, default 10, for ordering within a picking
- `priority` — `0` (Normal) | `1` (Urgent), computed from picking
- `date` — Scheduled datetime (default `Datetime.now`, indexed, required)
- `date_deadline` — Deadline from linked sale/purchase line (readonly, propagated to chain)
- `delay_alert_date` — Computed/stored, the latest upstream un-done move date that exceeds this move's date
- `company_id` — Operating company (required, indexed)
- `product_id` — Product being moved (required, domain `type='consu'`, indexed)
- `description_picking` — Description used on picking forms
- `product_qty` — Real quantity in default UoM of product (computed from `product_uom_qty`, inverse to update demand)
- `product_uom_qty` — Demand quantity in move's UoM (required, default 0)
- `product_uom` — Unit of measure (computed from product, required)
- `product_tmpl_id` — Related from product
- `location_id` / `location_dest_id` — Source/destination (required, indexed)
- `location_final_id` — Final destination when chained operations are involved (separate from intermediate dest)
- `location_usage` / `location_dest_usage` — Related from location
- `partner_id` — Destination address (for dropshipping/allotment)
- `picking_id` — Parent `stock.picking` (indexed)
- `picking_type_id` — Operation type (computed from picking)
- `picking_code` — Related picking type code
- `state` — `draft` | `waiting` | `confirmed` | `partially_available` | `assigned` | `done` | `cancel` (indexed, readonly)
- `picked` — Boolean, checkbox indicating products have been picked (inverse writes to all move lines)
- `price_unit` — Unit cost for valuation (used for average/FIFO real price)
- `origin` — Source document reference
- `procure_method` — `make_to_stock` | `make_to_order` | `mts_else_mto` (supply method)
- `scrapped` — Boolean, related from `location_dest_id.scrap_location`, stored
- `scrap_id` — Linked scrap record
- `group_id` — `procurement.group` (indexed)
- `rule_id` — `stock.rule` that triggered this move (on delete restrict)
- `procurement_group` alias: `group_id`
- `propagate_cancel` — If `True`, cancelling this move cancels linked downstream moves
- `move_dest_ids` / `move_orig_ids` — Many2many chained moves
- `origin_returned_move_id` / `returned_move_ids` — Return move tracking
- `availability` — Forecasted available quantity (computed for display)
- `forecast_availability` / `forecast_expected_date` — Complex computed forecast per warehouse
- `restrict_partner_id` — Restrict quant ownership when marking move done
- `route_ids` — Many2many of preferred routes
- `warehouse_id` — Warehouse to consider for route/procurement selection
- `has_tracking` — Related from product
- `quantity` — Sum of move line `quantity` values (computed, inverse to set line quantities)
- `show_details_visible` — Computed, `True` if user has rights to see detailed operations
- `is_locked` / `is_initial_demand_editable` / `is_quantity_done_editable` — Editability flags
- `reference` — Smart display: picking name or "[Product] Description"
- `move_lines_count` — Count of move line records
- `move_line_ids` — One2many to `stock.move.line`
- `package_level_id` — Linked package level
- `picking_type_entire_packs` — Related from picking type
- `display_assign_serial` / `display_import_lot` — Computed booleans for SN assignment UI
- `next_serial` / `next_serial_count` — First SN name and count for bulk serial generation
- `orderpoint_id` — Original reorderpoint rule that triggered procurement
- `is_inventory` — Boolean, marks this as an inventory adjustment move
- `product_packaging_id` / `product_packaging_qty` / `product_packaging_quantity` — Packaging tracking
- `show_quant` / `show_lots_m2o` / `show_lots_text` — UI display flags
- `reservation_date` — Computed/stored date when move should be reserved (for `by_date` reservation method)

**Key Methods:**
- `_action_confirm()` — Converts `draft` -> `confirmed`/`waiting`. For `make_to_order` moves, creates procurement. For `make_to_stock`, triggers push rules. Handles move chaining.
- `_action_assign()` — Converts `confirmed`/`waiting`/`partially_available` -> `assigned`. Reserves quants via `stock.quant._update_reserved_quantity()`. Handles partial availability by splitting moves.
- `_action_done()` — Converts `assigned` -> `done`. Updates quants, creates valuation layers, handles backorders.
- `_action_cancel()` — Cancels move and propagates to next moves if `propagate_cancel=True`.
- `_do_unreserve()` — Releases reserved quants via `stock.quant._update_reserved_quantity(negative)`.
- `_push_apply()` — Applies push rules from destination location routes.
- `_set_quantity_done(move)` — Called from move line validation, updates quantities.
- `_compute_quantity()` — Sums all move line quantities using `_read_group`.
- `_set_quantity()` — Inverse of `quantity`: processes increases/decreases by creating/removing/adjusting move lines. Handles rounding precision validation.
- `_compute_product_availability()` — Sets `availability` field for display.
- `_compute_forecast_information()` — Complex computation of `forecast_availability` and `forecast_expected_date` per warehouse. Prefetches virtual_available efficiently for draft consuming moves.
- `_compute_delay_alert_date()` — Detects when upstream moves will cause this move to be late.
- `_compute_reservation_date()` — Computes when to reserve based on picking type `reservation_days_before`.
- `_is_consuming()` — Returns `True` if this is a consumption move (outgoing picking type).
- `_should_bypass_reservation()` — Checks if source/destination locations bypass reservation rules.

**Move State Transitions:**
```
draft ──(action_confirm)──> waiting/confirmed ──(action_assign)──> assigned ──(action_done)──> done
                              │
                              └───────────────── cancel <─────────────────────┘
```

---

### stock.move.line

Detailed tracking at the lot/serial/package level within a move. One move can have multiple move lines (e.g., same product from different lots).

**Key Fields:**
- `move_id` — Parent `stock.move` (required)
- `picking_id` — Computed from `move_id.picking_id`
- `product_id` — Product (required)
- `product_uom_id` — Unit of measure (required)
- `product_qty` — Quantity in product's default UoM (for display)
- `location_id` / `location_dest_id` — Source/destination locations
- `lot_id` — Lot/serial number (constrained by product tracking)
- `lot_name` — Lot name for new lot creation (text field, alternative to `lot_id`)
- `package_id` — Source package
- `result_package_id` — Destination package (set by "Put in Pack" operation)
- `owner_id` — Consignment owner
- `quantity` — Reserved quantity (updated by reservation system)
- `qty_done` — Actually moved quantity
- `picked` — Boolean, has this line been picked
- `state` — Inherited from move (computed, not stored)
- `description_picking` — Move description for display
- `date` — Operation date
- `is_inventory` — Boolean, is this an inventory adjustment line
- `produce_line_ids` — For manufacturing: lines producing this SN (for SN traceability)
- `consume_line_ids` — For manufacturing: lines consuming from this SN
- `package_level_id` — Linked `stock.package_level`
- `location_done` — Boolean, marks line as already processed

---

### stock.quant

**The core inventory tracking model** — one record per product/lot/location/package/owner combination. This is the fundamental record of what inventory exists where.

**Key Fields:**
- `product_id` — Product (required, restricted to `is_storable=True`, indexed, ondelete restrict)
- `product_tmpl_id` / `product_uom_id` / `is_favorite` — Related from product
- `company_id` — Related from location (readonly, stored)
- `location_id` — Storage location (required, indexed, auto_join, restricted to internal/transit)
- `warehouse_id` / `storage_category_id` / `cyclic_inventory_frequency` — Related from location
- `lot_id` — Lot/serial number (indexed, ondelete restrict, restricted by product)
- `lot_properties` — Properties from lot (readonly, via `lot_id.lot_properties`)
- `sn_duplicated` — Computed boolean, `True` if same SN exists in another quant (triggers warning)
- `package_id` — Package containing this quant (indexed)
- `owner_id` — Consignment owner (indexed, btree_not_null)
- `quantity` — Total quantity in this quant (readonly, in product's default UoM)
- `reserved_quantity` — Quantity reserved by assigned moves (readonly, required, default 0)
- `available_quantity` — Computed: `quantity - reserved_quantity`
- `in_date` — Incoming datetime (readonly, required, default `Datetime.now`)
- `tracking` — Related from product (readonly)
- `on_hand` — Boolean search field for "on hand" filter
- `inventory_quantity` — Counted quantity for manual inventory adjustment
- `inventory_quantity_auto_apply` — Auto-set counted qty (used in background counting)
- `inventory_diff_quantity` — Computed: `inventory_quantity - quantity`
- `inventory_date` — Scheduled date for next count (computed from location, stored)
- `last_count_date` — Computed from move lines: last inventory adjustment date
- `inventory_quantity_set` — Boolean, has user set a counted quantity
- `is_outdated` — Computed, `True` if counted quantity differs from current qty
- `user_id` — User assigned for counting

**Inventory Workflow:**
1. User sets `inventory_quantity` (or uses `inventory_quantity_auto_apply`)
2. `action_apply_inventory()` triggers `_apply_inventory()`
3. Creates and validates a `stock.move` for the difference
4. Clears the counted quantities

**Key Methods:**
- `_update_available_quantity(product_id, location_id, quantity, reserved_quantity, lot_id, package_id, owner_id, in_date)` — **CORE METHOD**. Increases/decreases `quantity` or `reserved_quantity`. Uses `FOR NO KEY UPDATE SKIP LOCKED` SQL to handle concurrent writes. Merges with existing quants or creates new ones. Returns `(available_quantity, in_date)`.
- `_update_reserved_quantity(product_id, location_id, quantity, ...)` — Wrapper around `_update_available_quantity` with `reserved_quantity` param only. Used by reservation system.
- `_get_available_quantity(product_id, location_id, lot_id, package_id, owner_id, strict, allow_negative)` — Returns available quantity. For tracked products, returns per-lot availability. For non-strict searches, sums across matching lots.
- `_get_reserve_quantity(product_id, location_id, quantity, ...)` — Returns list of `(quant, reserved_qty)` tuples for reservation. Handles packaging reservation, serial number rounding (no fractional qty for serial), and negative quant compensation.
- `_gather(product_id, location_id, lot_id, package_id, owner_id, strict, qty)` — Returns quants matching criteria, applying removal strategy. Uses `quants_cache` from context for performance. Returns quants sorted by removal strategy order.
- `_get_gather_domain(product_id, location_id, lot_id, package_id, owner_id, strict)` — Builds domain for `_gather()`.
- `_get_removal_strategy(product_id, location_id)` — Returns removal method string; falls back through product category -> parent location chain, defaulting to `fifo`.
- `_get_removal_strategy_order(strategy)` — Returns SQL `ORDER BY` clause: `in_date ASC` for FIFO, `in_date DESC` for LIFO, `False` for Closest.
- `_run_least_packages_removal_strategy_astar(domain, qty)` — A* algorithm for minimum-package-count selection.
- `_apply_inventory()` — **CORE METHOD**. Creates and validates `stock.move` records for each quant where `inventory_diff_quantity != 0`. Positive diff -> move from inventory location to quant. Negative diff -> move from quant to inventory location. Clears inventory_quantity after application.
- `_get_inventory_move_values(qty, location_dest, location_src, package_dest_id)` — Prepares dict for inventory adjustment stock move.
- `_is_inventory_mode()` — Returns `True` if user has stock manager group or context has `inventory_mode=True`.
- `_get_quants_by_products_locations(product_ids, location_ids, extra_domain)` — Batch query for quant fetching by product/location combinations.
- `_clean_reservations()` — Cleans inconsistencies between quant reservations and move line reservations.
- `_unlink_zero_quants()` — SQL-based bulk deletion of quants with zero quantities (defers unlink for performance).
- `_read_group_select(aggregate_spec)` — Handles special aggregates: `inventory_quantity:sum` returns NULL in report mode; `available_quantity:sum` computes `quantity_sum - reserved_quantity_sum`.
- `_check_serial_number(product, lot, company, location, location_dest)` — Validates SN assignment: single SN per location for serial-tracked products.
- `check_quantity()` — Constraint: raises `ValidationError` if any serial-tracked quant at a location has qty != 1.
- `check_lot_id()` — Constraint: lot's product must match quant's product.
- `check_location_id()` — Constraint: cannot be in a `view` location.
- `check_product_id()` — Constraint: product must be storable.
- `action_view_stock_moves()` — Opens move line history for this quant.
- `action_view_orderpoints()` — Opens reorderpoints for this product.
- `action_view_quants()` / `action_view_inventory()` — Opens quant tree view.
- `action_apply_inventory()` — Validates inventory count, opens conflict/SN wizards if needed.
- `action_stock_quant_relocate()` — Opens relocation wizard.

**Quant Lifecycle:**
1. **Created** via `_update_available_quantity` when a move is confirmed/done
2. **Reserved** via `_update_reserved_quantity` when a move is assigned
3. **Unreserved** when a move is cancelled
4. **Updated** when a move is validated (quantity transferred)
5. **Adjusted** via `_apply_inventory()` during physical counts
6. **Merged** automatically: when same product/lot/location/package/owner, quants are merged
7. **Deleted** via `_unlink_zero_quants()` when quantity reaches zero

---

### stock.lot

Lot/serial number tracking. A lot groups quants of the same production batch; a serial number is a lot with qty=1.

**Key Fields:**
- `name` — Lot/serial number (required, default from `stock.lot.serial` sequence, trigram indexed, unique per product+company)
- `ref` — Internal reference (different from manufacturer's lot)
- `product_id` — Product template (required, domain restricts to tracked products with `is_storable=True`)
- `product_uom_id` — Related from product (stored)
- `company_id` — Company (computed from product or context)
- `quant_ids` — One2many of linked quants (readonly)
- `product_qty` — Computed sum of quants (only internal/transit locations with company), with search capability
- `note` — Html description
- `display_complete` — Computed, `True` if record exists or context requests full form
- `delivery_ids` / `delivery_count` — Many2many computed, deliveries using this lot
- `last_delivery_partner_id` — Computed, most recent delivery's partner (for serial numbers)
- `lot_properties` — Properties definition from product template
- `location_id` — Single location if lot exists in exactly one location (computed, editable, creates a move on change)

**Key Methods:**
- `_check_unique_lot()` — Constraint: `name` must be unique per `(product_id, company_id)`. Handles cross-company duplicate prevention by checking sudo.
- `_product_qty()` — Sums `quantity` from quants in internal/transit locations (with company).
- `_search_product_qty(operator, value)` — Enables searching lots by available quantity, handling operators `=`, `!=`, `>`, `<`, `>=`, `<=` and zero-value edge cases.
- `_find_delivery_ids_by_lot()` — Recursively traces SN through production/consumption chains to find delivery pickings. Handles circular lot paths.
- `_set_single_location()` — Writes quants to new location (creates a stock move). Raises `UserError` if lot is in multiple locations.
- `action_lot_open_quants()` — Opens quant tree filtered to this lot (uses inventory mode for managers).
- `action_lot_open_transfers()` — Opens delivery pickings for this lot.
- `generate_lot_names(first_lot, count)` — Static method: generates sequential lot names from a base string (handles padding, suffix/prefix).
- `_get_next_serial(company, product)` — Static method: returns next serial number for a product.

---

### stock.rule

Procurement/push/pull rule definitions. Rules drive automatic stock movements.

**Key Fields:**
- `name` — Rule name (required, translatable)
- `active` — Active flag
- `action` — `pull` | `push` | `pull_push` | `manufacture` | `subcontract` (required, default `pull`, indexed)
- `sequence` — Rule priority within route (default 20, lower = first)
- `company_id` — Operating company
- `route_id` — Parent `stock.route` (required, cascade delete)
- `route_company_id` — Related from route
- `picking_type_id` — Operation type for this rule (required)
- `picking_type_code_domain` — Computed char for domain filtering
- `location_src_id` — Source location for pull rules (indexed)
- `location_dest_id` — Destination location (indexed)
- `location_dest_from_rule` — If `True`, move's dest comes from rule instead of picking type
- `procure_method` — `make_to_stock` | `make_to_order` | `mts_else_mto` (default `make_to_stock`, required)
- `delay` — Lead time in days (default 0), applied as `date_planned - delay`
- `partner_address_id` — Partner address for delivery
- `group_propagation_option` — `none` | `propagate` | `fixed` (how to handle procurement group)
- `group_id` — Fixed procurement group when `group_propagation_option='fixed'`
- `propagate_cancel` — Propagate cancellation to next move (default `False`)
- `propagate_carrier` — Propagate carrier to next move (default `False`)
- `warehouse_id` — Applicable warehouse (indexed)
- `propagate_warehouse_id` — Warehouse to propagate on created move
- `auto` — `manual` | `transparent` (automatic move behavior)
- `rule_message` — Computed HTML describing the rule (for UI tooltips)
- `push_domain` — Char for push applicability (advanced)

**Supply Methods:**
| Method | Behavior |
|--------|----------|
| `make_to_stock` | Take from available stock at source location |
| `make_to_order` | Ignore stock, trigger another rule to procure |
| `mts_else_mto` | Try stock first, if unavailable trigger another rule |

**Actions:**
| Action | Behavior |
|--------|----------|
| `pull` | Creates a move from source -> dest when need exists at dest |
| `push` | Triggered when goods arrive at source, creates move to dest |
| `pull_push` | Both pull and push behavior |
| `manufacture` | Triggers manufacturing order |
| `subcontract` | Triggers subcontracting |

**Key Methods:**
- `_onchange_picking_type()` — Auto-fills `location_src_id` and `location_dest_id` from picking type defaults
- `_get_message_dict()` — Returns HTML message describing the rule for UI tooltips (overridden by `mrp`, `purchase_stock`)
- `_compute_action_message()` — Computes `rule_message` field
- `_run_push(move)` — Executes push rule: either updates move location (`auto='transparent'`) or creates a new move. Handles `location_final_id` for chained pushes and `make_to_stock` override for bypass reservations.
- `_push_prepare_move_copy_values(move_to_copy, new_date)` — Prepares dict for creating a pushed move, including `location_final_id`, `rule_id`, `date_deadline` propagation.
- `_run_pull(procurements)` — Executes pull rules: batches procurements by company, creates moves with `sudo()`, calls `_action_confirm`. Handles `mts_else_mto` preliminary check.
- `_get_stock_move_values(product_id, product_qty, product_uom, location_dest_id, name, origin, company_id, values)` — **CORE METHOD**. Builds dict for `stock.move` creation from a procurement. Handles group propagation, date scheduling with lead time, partner assignment, description, packaging, route_ids, `orderpoint_id`, priority.
- `_get_lead_days(product, **values)` — Computes cumulative delay across rules chain

---

### stock.route

Named collection of stock rules (procurement route).

**Key Fields:**
- `name` — Route name (required, translatable)
- `active` — Active flag
- `sequence` — Priority (default 0)
- `rule_ids` — One2many of `stock.rule` (copy=True)
- `product_selectable` — Can be assigned to individual products (default `True`)
- `product_categ_selectable` — Can be assigned to product categories
- `warehouse_selectable` — Can be assigned to warehouses
- `packaging_selectable` — Can be assigned to product packaging
- `supplied_wh_id` — Warehouse being resupplied (for dropship buy rules)
- `supplier_wh_id` — Supplier warehouse (for dropship buy rules)
- `company_id` — Operating company
- `product_ids` — Many2many to `product.template`
- `categ_ids` — Many2many to `product.category`
- `packaging_ids` — Many2many to `product.packaging`
- `warehouse_ids` — Many2many to `stock.warehouse`
- `warehouse_domain_ids` — Computed domain of warehouses available for this route

**Key Methods:**
- `_compute_warehouses()` — Returns warehouses matching the route's company
- `_onchange_company()` — Filters warehouses to same company
- `_onchange_warehouse_selectable()` — Clears warehouse selection when disabled
- `toggle_active()` — Cascades active state to rules (respects rule-level active state and location active state)

---

### stock.scrap

Scrap/waste record for removing inventory from stock.

**Key Fields:**
- `name` — Reference (auto-generated from `stock.scrap` sequence, readonly)
- `origin` — Source document reference
- `company_id` — Operating company (required)
- `product_id` — Product to scrap (required, domain `type='consu'`)
- `product_uom_id` — UoM (computed from product, required)
- `tracking` — Related product tracking (readonly)
- `lot_id` / `package_id` / `owner_id` — Lot/package/owner to scrap
- `move_ids` — One2many of created stock moves
- `picking_id` — Related picking (if scrap from a transfer)
- `location_id` — Source location (computed: from picking if done, else from warehouse, required, domain `usage='internal'`)
- `scrap_location_id` — Destination (computed from company, required, domain `scrap_location=True`)
- `scrap_qty` — Quantity to scrap (computed from moves, default 1, required)
- `state` — `draft` | `done` (readonly, default `draft`)
- `date_done` — Completion date
- `should_replenish` — Trigger replenishment after scrap
- `scrap_reason_tag_ids` — Many2many to `stock.scrap.reason.tag`

**Key Methods:**
- `_prepare_move_values()` — Builds dict for the stock.move: source=location, dest=scrap_location, creates move line with full lot/package/owner info, sets `scrapped=True`, `picked=True`
- `do_scrap()` — Creates stock.move from `_prepare_move_values()`, calls `move._action_done(is_scrap=True)`, sets state `done`, optionally triggers replenishment via `do_replenish()`
- `do_replenish(values)` — Runs procurement group with the same product/qty/location
- `action_validate()` — Validates scrap: if `check_available_qty()` passes -> `do_scrap()`, else opens insufficient quantity wizard
- `check_available_qty()` — Checks if enough qty available at source location using `product_id.qty_available` with strict location/lot/package/owner context
- `_compute_location_id()` / `_compute_scrap_location_id()` — Compute defaults from picking/company using `_read_group`

---

## Valuation

### stock.valuation.layer

Tracks inventory value per product/lot/quantity. Created when moves are validated.

**Key Fields:**
- `product_id` / `lot_id` / `location_id` — Location of the value
- `company_id` — Company
- `stock_move_id` — Source stock.move
- `stock_valuation_layer_id` — Parent layer (for layered cost, e.g., landed costs)
- `quantity` — Quantity change (positive for in, negative for out)
- `value` — Value change in company currency
- `unit_cost` — Unit cost at layer creation
- `remaining_qty` — Quantity remaining after this layer (for FIFO/AVCO)
- `remaining_value` — Value remaining
- `create_date` — Creation timestamp
- `account_move_id` — Linked `account.move` (for real-time/manual valuation)
- `description` — Layer description

### stock.valuation.account.move

Links valuation layers to accounting entries.

**Fields:**
- `stock_valuation_layer_id`
- `account_move_id` — `account.move`
- `date`
- `ref` — Reference

---

## Supporting Models

### stock.package

Represents a package (box, pallet) containing quants.

**Key Fields:**
- `name` — Package name
- `package_type_id` — Type (defines dimensions, max weight)
- `location_id` — Current location of the package
- `quant_ids` — One2many of quants inside
- `包裹_ids` / `包裹_id` — Nested/parent package relationship
- `weight` / `weight_uom_id` / `volume` — Physical characteristics
- `shipping_weight` — Weight for shipping carrier calculation
- `package_use` — `reusable` | `disposable` | `customer` (determines if package returns after delivery)
- `company_id` — Company
- `purchase_id` / `sale_id` — Related PO/SO (for dropshipping tracking)

### stock.package.level

Tracks package state within a picking operation.

**Key Fields:**
- `picking_id` — Parent picking
- `package_id` — Package being moved
- `location_id` / `location_dest_id` — Source/destination
- `move_line_ids` — Move lines in this package level
- `state` — `draft` | `assigned` | `done` | `cancel`
- `company_id`

### stock.storage.category

Defines storage constraints for a zone of locations.

**Key Fields:**
- `name` — Category name
- `allow_new_product` — `empty` (only when location empty) | `same` (only same product) | `mixed` (any products)
- `max_weight` — Maximum weight capacity
- `product_capacity_ids` — Per-product max quantity rules
- `package_capacity_ids` — Per-package-type max count rules

### stock.orderpoint (Reordering Rule)

Triggers procurement when product stock falls below a threshold.

**Key Fields:**
- `name` — Rule name
- `product_id` / `product_tmpl_id` — Product
- `location_id` / `warehouse_id` — Where/which warehouse to replenish
- `product_min_qty` / `product_max_qty` — Minimum and maximum stock levels
- `qty_multiple` — Round order qty to multiple of this
- `product_uom` — UoM for min/max quantities
- `group_id` — Procurement group
- `rule_id` — Stock rule to use
- `lead_days` / `lead_days_type` — Lead time calculation
- `snooze_until` — Snooze date
- `trigger` — `auto` | `manual`

### stock.putaway.rule

Maps products/categories/packages to preferred destination locations.

**Key Fields:**
- `product_id` / `category_id` / `package_type_ids` — Applicability criteria
- `location_in_id` — Source/parent location
- `location_out_id` — Destination location

---

## Module Relations

| Module | Relation |
|--------|----------|
| `stock` -> `account` | Creates `account.move` for inventory valuation |
| `stock` -> `purchase` | Incoming receipts from PO; `purchase_stock` adds `picking_type_id` to PO |
| `stock` -> `sale` | Outgoing deliveries to customers; `sale_stock` adds `picking_type_id` to SO |
| `stock` -> `mrp` | Work orders consume components, produce finished goods; `mrp` adds `picking_type_id` to MO |
| `stock` -> `stock_account` | Inventory valuation layer + landed costs + valuation adjustments |
| `stock` -> `stock_picking_batch` | Batch processing of multiple pickings together |
| `stock` -> `product` | Product `type` (`consu`, `product`, `service`), `tracking`, `is_storable` |

---

## Key Architecture Notes (Odoo 18)

### Quant Reservation Flow
```
move._action_assign()
  -> quant._update_reserved_quantity(+qty)    # reserves quants
  -> move_line._update_reserved_quantity()    # creates move lines for reserved quants
```

### Move Validation Flow
```
move._action_done()
  -> move_line._action_done()
     -> quant._update_available_quantity(-qty)    # source: decreases quantity
     -> quant._update_available_quantity(+qty)    # dest: increases quantity
  -> stock.valuation.layer created
  -> account.move created (if stock_account installed)
```

### Push vs Pull Rules
- **Pull** (`pull`): Activated when a need exists at destination. Creates a move FROM source TO destination. Example: delivery order pulls from stock.
- **Push** (`push`): Activated when goods arrive at a location. Creates a move FROM arrival TO next destination. Example: QC check after receipt.

### Removal Strategies
| Strategy | Order | Use Case |
|----------|-------|----------|
| `fifo` | `in_date ASC` | First in, first out |
| `lifo` | `in_date DESC` | Last in, first out |
| `closest` | `complete_name ASC` | Nearest location first |
| `least_packages` | A* algorithm | Minimize package count |

### Location Architecture for Warehouse
```
stock.stock_location_locations (root, view)
  └── WH/view (view, per warehouse)
       ├── WH/Stock (internal)
       ├── WH/Input (internal, for two_steps/three_steps)
       ├── WH/Quality Control (internal, for three_steps)
       ├── WH/Output (internal, for pick_ship/pick_pack_ship)
       ├── WH/Pack (internal, for pick_pack_ship)
       └── WH/...
```

### MTO (Make to Order) Flow
```
sale.order.line
  -> procurement.group.run()
     -> stock.rule (procure_method=make_to_order)
        -> stock.move (pull from vendor location)
           -> stock.rule (procure_method=make_to_order) [MTO rule at WH]
              -> procurement [triggers purchase/manufacturing]
```

### Picking State Computed from Moves
The `state` field on `stock.picking` is **stored** and **computed** by `_compute_state()`, which aggregates the states of all child `stock.move` records. This is the reverse of typical Odoo patterns where state is a plain stored field written explicitly by action methods.

### Immediate Transfer vs Reserved
- **Immediate Transfer**: All moves processed at validation, no availability check needed
- **Reserved**: `action_assign` runs first to reserve quants; `action_done` only processes reserved quantities

### Quants Cache
`stock.quant._gather()` supports a `quants_cache` in the environment context for batch operations, avoiding redundant searches during the same transaction.

### Serial Number Constraints
- Serial-tracked products: exactly 1 unit per quant per location
- `check_quantity()` enforces this constraint via `ValidationError`
- `_get_reserve_quantity` enforces no fractional reservation for serial numbers
