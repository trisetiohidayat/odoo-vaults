# stock_fleet — Stock Fleet

**Tags:** #odoo #odoo18 #stock #fleet #delivery #logistics
**Odoo Version:** 18.0
**Module Category:** Stock + Fleet Integration
**Documentation Level:** L4
**Status:** Complete

---

## Module Overview

`stock_fleet` extends the stock picking batch with fleet vehicle management — assigning vehicles, drivers, and dock locations to delivery batches, with capacity tracking (weight and volume utilization percentages).

**Technical Name:** `stock_fleet`
**Python Path:** `~/odoo/odoo18/odoo/addons/stock_fleet/`
**Depends:** `stock_picking_batch`, `fleet`
**Inherits From:** `stock.picking.batch`, `stock.location`, `fleet.vehicle.model.category`

---

## Python Model Files

| File | Model(s) Extended | Key Purpose |
|------|------------------|-------------|
| `models/stock_picking_batch.py` | `stock.picking.batch` | Vehicle, driver, dock, capacity tracking |
| `models/stock_location.py` | `stock.location` | Dock location flag |
| `models/fleet_vehicle_model.py` | `fleet.vehicle.model.category` | Weight/volume capacity on vehicle categories |
| `models/stock_picking.py` | `stock.picking` | Zip code search and batch write handling |

---

## Models Reference

### `stock.picking.batch` (models/stock_picking_batch.py)

#### Fields

| Field | Type | Compute/Store | Notes |
|-------|------|---------------|-------|
| `vehicle_id` | Many2one | — | `fleet.vehicle` assigned to batch |
| `vehicle_category_id` | Many2one | Yes (store) | From vehicle.category_id |
| `dock_id` | Many2one | Yes (store) | `stock.location` flagged as dock |
| `vehicle_weight_capacity` | Float | — | Related from category |
| `weight_uom_name` | Char | Yes | Weight UOM label |
| `vehicle_volume_capacity` | Float | — | Related from category |
| `volume_uom_name` | Char | Yes | Volume UOM label |
| `driver_id` | Many2one | Yes (store) | From `vehicle_id.driver_id` |
| `used_weight_percentage` | Float | Yes | `100 * estimated_weight / weight_capacity` |
| `used_volume_percentage` | Float | Yes | `100 * estimated_volume / volume_capacity` |
| `end_date` | Datetime | — | Default `Datetime.now` |

#### Methods

| Method | Decorators | Behavior |
|--------|-----------|----------|
| `_compute_vehicle_category_id()` | `@api.depends('vehicle_id')` | Sets category from vehicle |
| `_compute_dock_id()` | `@api.depends` | Auto-detects dock from first picking location if single dock location |
| `_compute_weight_uom_name()` | — | Gets weight UOM from product template |
| `_compute_volume_uom_name()` | — | Gets volume UOM from product template |
| `_compute_driver_id()` | `@api.depends('vehicle_id')` | Sets driver from vehicle |
| `_compute_capacity_percentage()` | `@api.depends` | Computes weight/volume utilization % |
| `create(vals_list)` | — | Calls `order_on_zip()`, sets dock moves if dock_id set |
| `write(vals)` | — | Calls `_set_moves_destination_to_dock()` when dock_id changes |
| `order_on_zip()` | — | Sorts pickings by zip code, assigns `batch_sequence` |
| `_set_moves_destination_to_dock()` | — | Writes `location_dest_id` or `location_id` to dock for all batch moves |

#### Batch Creation Logic

On `create()`:
1. Calls `order_on_zip()` — sorts pickings by zip and assigns sequence
2. If `dock_id` is set, calls `_set_moves_destination_to_dock()`

On `write()` with `dock_id`:
- Clears dock: calls `_reset_location()` on pickings (move back to picking destination)
- Sets dock: for `incoming`/`internal` pickings, moves go to dock; for `outgoing`, moves start from dock

#### Capacity Utilization

`used_weight_percentage = 100 * (estimated_shipping_weight / vehicle_weight_capacity)`
`used_volume_percentage = 100 * (estimated_shipping_volume / vehicle_volume_capacity)`
Both are False if capacity is zero (no vehicle assigned).

---

### `stock.location` (models/stock_location.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `is_a_dock` | Boolean | Flags location as a loading/unloading dock |

---

### `fleet.vehicle.model.category` (models/fleet_vehicle_model.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `weight_capacity` | Float | Max weight (e.g., truck payload in kg) |
| `weight_capacity_uom_name` | Char | Weight UOM label |
| `volume_capacity` | Float | Max volume (m³) |
| `volume_capacity_uom_name` | Char | Volume UOM label |

#### Methods

| Method | Behavior |
|--------|----------|
| `_compute_display_name()` | Appends "(capacity)" info to model name |
| `_compute_weight_capacity_uom_name()` | Gets from product template |
| `_compute_volume_capacity_uom_name()` | Gets from product template |

---

### `stock.picking` (models/stock_picking.py)

#### Fields

| Field | Type | Notes |
|-------|------|-------|
| `zip` | Char | Related from partner.zip, searchable |

#### Methods

| Method | Behavior |
|--------|----------|
| `_search_zip()` | Delegates to `partner_id.zip` search |
| `write(vals)` | Handles batch dock assignment: if `batch_id` changes and batch has dock, sets moves to dock or resets |

| Method | Behavior |
|--------|----------|
| `_reset_location()` | For each picking, moves moves that are outside `location_dest_id` hierarchy back to `location_dest_id` |

---

## Security File

No security file (`security/` directory does not exist in this module).

---

## Data Files

No data file (`data/` directory does not exist in this module).

---

## Critical Behaviors

1. **Dock Auto-Detection**: `_compute_dock_id()` automatically sets the dock from the first picking's source location if all pickings share the same source location and that location is marked `is_a_dock = True`.

2. **Batch Write with Dock**: When a picking is added to a batch that has a dock, `stock.picking.write()` automatically moves the picking's destination (outgoing) or source (incoming) location to the dock.

3. **Order on Zip**: `order_on_zip()` sorts pickings by zip code and assigns `batch_sequence` for efficient delivery route planning.

4. **Capacity Percentage**: Utilization percentages are computed from batch `estimated_shipping_weight/volume` divided by the vehicle category's capacity limits.

5. **Driver from Vehicle**: `driver_id` is derived from `vehicle_id.driver_id` — no separate field entry needed.

---

## v17→v18 Changes

No significant changes from v17 to v18 identified.

---

## Notes

- This module integrates three distinct domains: stock batching, fleet management, and logistics planning
- Vehicle categories store weight/volume capacity (shared between fleet and stock modules)
- The `is_a_dock` flag on `stock.location` enables dock-to-batch associations
- `estimated_shipping_weight` and `estimated_shipping_volume` on `stock.picking.batch` are inherited from the `stock_picking_batch` base module
