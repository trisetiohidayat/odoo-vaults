---
uuid: stock-fleet-l4
tags:
  - #odoo
  - #odoo19
  - #modules
  - #stock_fleet
  - #fleet
  - #logistics
  - #dispatch
created: 2026-04-11
modified: 2026-04-11
module: stock_fleet
module_version: "19.0"
module_category: Supply Chain/Inventory
module_type: Odoo Community (CE)
module_location: ~/odoo/odoo19/odoo/addons/stock_fleet/
module_dependencies:
  - stock_picking_batch
  - fleet
---

# Stock Fleet — Dispatch Management (`stock_fleet`)

## Overview

| Attribute | Value |
|---|---|
| **Name** | Stock Transport |
| **Technical name** | `stock_fleet` |
| **Category** | Supply Chain/Inventory |
| **Version** | 1.0 |
| **Depends** | `stock_picking_batch`, `fleet` |
| **Auto-install** | No |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

### Purpose

`stock_fleet` integrates fleet vehicles with warehouse dispatch operations. It enables assigning a `fleet.vehicle` to a `stock.picking.batch` (a dispatch), manages dock assignments at warehouses, and validates that a batch's total weight/volume does not exceed the assigned vehicle's capacity. It also provides ZIP-based sorting of pickings within a batch for route optimization.

This module does not manage vehicle maintenance, driver scheduling, or fuel costs — those belong to the `fleet` module. `stock_fleet` focuses purely on the dispatch planning and execution aspects of fleet operations.

---

## Module Structure

```
stock_fleet/
├── __init__.py                    # Imports: fleet_vehicle_model, stock_picking_batch,
│                                  #           stock_picking, stock_warehouse
├── __manifest__.py                # Depends: stock_picking_batch, fleet
├── models/
│   ├── __init__.py
│   ├── fleet_vehicle_model.py     # fleet.vehicle.model.category extensions
│   ├── stock_picking_batch.py      # stock.picking.batch extensions (primary)
│   ├── stock_picking.py           # stock.picking + stock.picking.type extensions
│   └── stock_warehouse.py          # stock.warehouse._get_picking_type_update_values
├── views/
│   ├── fleet_vehicle_model.xml     # Category capacity fields in form view
│   ├── stock_picking_batch.xml     # Vehicle, dock, capacity fields in batch form
│   ├── stock_picking_type.xml     # dispatch_management toggle in picking type form
│   ├── stock_picking_view.xml     # zip field in picking list/form
│   └── stock_location.xml         # Dock location domain helpers
├── report/
│   └── report_picking_batch.xml    # Batch report with vehicle/dock info
└── data/
    └── stock_fleet_demo.xml       # Demo: vehicles, categories with capacity
```

> **Note:** `stock.move.line` is **not** directly extended by `stock_fleet`. The `_get_aggregated_product_quantities` override that adds HS codes belongs to `stock_delivery`, not this module.

---

## Dependency Analysis

### `stock_picking_batch`

The primary dependency. `stock_fleet` extends `stock.picking.batch` with vehicle, dock, and capacity fields. The batch is the central dispatch object — it groups one or more `stock.picking` records for a single vehicle trip.

```
stock.picking.batch (from stock_picking_batch)
  └─► stock_fleet adds:
        ├── vehicle_id          (Many2one fleet.vehicle)
        ├── vehicle_category_id (computed from vehicle_id)
        ├── dock_id             (Many2one stock.location)
        ├── driver_id           (computed from vehicle_id)
        ├── vehicle_weight_capacity    (related to vehicle_category_id)
        ├── vehicle_volume_capacity    (related to vehicle_category_id)
        ├── used_weight_percentage     (computed)
        ├── used_volume_percentage     (computed)
        ├── end_date            (computed: scheduled_date + 1h)
        ├── allowed_dock_ids    (related from picking_type_id)
        └── has_dispatch_management    (related from picking_type_id)
```

### `fleet`

The `fleet` module provides `fleet.vehicle` and `fleet.vehicle.model.category`. `stock_fleet` extends the model category with capacity fields (`weight_capacity`, `volume_capacity`) and adds a `vehicle_id` Many2one to the batch.

```
fleet.vehicle (from fleet)
  └─► stock_fleet uses:
        ├── model_id.category_id  → vehicle_category_id on batch
        ├── driver_id             → driver_id on batch
        └── license_plate         (shown in batch form)

fleet.vehicle.model.category (from fleet)
  └─► stock_fleet adds:
        ├── weight_capacity       (Float)
        ├── weight_capacity_uom_name (Char, computed)
        ├── volume_capacity       (Float)
        ├── volume_capacity_uom_name (Char, computed)
        └── _compute_display_name override (appends capacity to name)
```

---

## Models

### L1/L2 — `fleet.vehicle.model.category` Extensions

**File:** `models/fleet_vehicle_model.py`

#### `weight_capacity`
- **Type:** `Float`
- **L2:** Maximum weight the vehicle category can carry (in the user's preferred weight UOM). Used to validate batches before dispatch.
- **Why it exists:** Different vehicle types (light van, truck, semi-trailer) have different payload limits. The capacity is stored at the category level so all vehicles in that category share the same limit.

#### `volume_capacity`
- **Type:** `Float`
- **L2:** Maximum volume (in cubic metres) the vehicle category can carry. Odoo uses `volume` on `product.product` (m3) for volume calculations.

#### `_compute_display_name` Override
```python
def _compute_display_name(self):
    super()._compute_display_name()
    for record in self:
        additional_info = []
        if record.weight_capacity:
            additional_info.append(_("%(wt)s %(wu)s", wt=record.weight_capacity, wu=record.weight_capacity_uom_name))
        if record.volume_capacity:
            additional_info.append(_("%(vt)s %(vu)s", vt=record.volume_capacity, vu=record.volume_capacity_uom_name))
        if additional_info:
            record.display_name = _("%(name)s (%(cap)s)", name=record.display_name,
                                    cap=format_list(self.env, additional_info, "unit-short"))
```
- **L2:** Appends capacity to the category's display name. Example: `"Van - Medium (1500 kg, 8 m³)"`.
- **L4:** Uses `format_list` for proper plural/unit formatting per locale. The `unit-short` style produces abbreviated units (kg, m³).

---

### L1/L2 — `stock.picking.type` Extensions

**File:** `models/stock_picking.py` (inline `StockPickingType` class)

#### `dispatch_management`
- **Type:** `Boolean`
- **L2:** Enables dispatch management UI elements on pickings and batches of this type. When `True`, the batch form shows vehicle, dock, and capacity utilization fields.
- **Default:** `False` (must be explicitly enabled per picking type).
- **Set by:** `post_init_hook` `_enable_dispatch_management` sets this to `True` on all existing picking types on module install.

#### `dock_ids`
- **Type:** `Many2many('stock.location')`
- **Domain:** `[('warehouse_id', '=', warehouse_id), ('usage', '=', 'internal')]`
- **L2:** Available dock locations for this picking type. Docks are internal `stock.location` records (usage = `internal`) within the warehouse.
- **Storage:** `store=True, compute='_compute_dock_ids', readonly=False` — the computed value is stored in the DB.

#### `_compute_dock_ids`
```python
@api.depends('warehouse_id')
def _compute_dock_ids(self):
    for picking_type in self:
        if picking_type.warehouse_id != picking_type._origin.warehouse_id and picking_type.dock_ids:
            picking_type.dock_ids = [Command.clear()]
```
- **L4:** Clears dock assignments when the warehouse changes on a picking type. This prevents a dock from Warehouse A being left assigned to a picking type that was moved to Warehouse B.

---

### L1/L2 — `stock.picking` Extensions

**File:** `models/stock_picking.py` (inline `StockPicking` class)

#### `zip`
- **Type:** `Char` (related, searchable)
- **Related:** `partner_id.zip`
- **L2:** Mirrors the delivery address ZIP code for use in batch sorting. Searchable via `_search_zip`.

#### `_search_zip`
```python
def _search_zip(self, operator, value):
    return [('partner_id.zip', operator, value)]
```
- **L4:** Delegates the search domain to the related `partner_id.zip` field. This enables searching/filtering pickings by customer ZIP code without a dedicated indexed column.

#### `write()` — Batch Assignment Trigger
```python
def write(self, vals):
    res = super().write(vals)
    if 'batch_id' not in vals:
        return res
    batch = self.env['stock.picking.batch'].browse(vals.get('batch_id'))
    if batch and batch.dock_id:
        batch._set_moves_destination_to_dock()
    else:
        self._reset_location()
    return res
```
- **L4 trigger:** When a picking is assigned to (or unassigned from) a batch via `write({'batch_id': ...})`, the destination location of its stock moves is updated to match the batch's dock. This only happens when `batch_id` is in `vals` — other field updates on the picking do not trigger this.
- **L4:** The `else` branch calls `_reset_location()` when the picking is removed from a batch with a dock — this reverts move destinations to the picking's original `location_dest_id`.

#### `_reset_location`
```python
def _reset_location(self):
    for picking in self:
        moves = picking.move_ids.filtered(
            lambda m: not m.location_dest_id._child_of(picking.location_dest_id)
        )
        moves.write({'location_dest_id': picking.location_dest_id.id})
```
- **L4:** Only resets moves whose destination is **not already a child of** the picking's `location_dest_id`. This prevents overwriting intentionally overridden move destinations.

---

### L1/L2 — `stock.warehouse` Extensions

**File:** `models/stock_warehouse.py`

#### `_get_picking_type_update_values`
```python
def _get_picking_type_update_values(self):
    values = super()._get_picking_type_update_values()
    if self.delivery_steps == 'pick_pack_ship':
        if values.get('pack_type_id'):
            values['pack_type_id']['dispatch_management'] = True
    elif self.delivery_steps == 'pick_ship':
        if values.get('pick_type_id'):
            values['pick_type_id']['dispatch_management'] = True

    if values.get('out_type_id'):
        values['out_type_id']['dispatch_management'] = True
        if self.delivery_steps in ('pick_ship', 'pick_pack_ship'):
            values['out_type_id']['dock_ids'] = [Command.link(self.wh_output_stock_loc_id.id)]
    if values.get('in_type_id'):
        values['in_type_id']['dispatch_management'] = True
    return values
```
- **L2:** On warehouse creation/reconfiguration, automatically enables `dispatch_management` on all applicable picking types and assigns the warehouse's output stock location as a dock for outgoing types.
- **L4:** Uses `Command.link` to add to the existing Many2many without replacing other dock assignments. The `pick_pack_ship` flow sets `dispatch_management` on the `pack_type_id` (the packing step); `pick_ship` sets it on `pick_type_id` (the pick step); both set it on `out_type_id` (the shipping step).
- **L4:** `in_type_id` (receipts) also gets `dispatch_management` enabled, allowing incoming goods to be dispatched from a dock at the receiving warehouse.

---

### L1/L2 — `stock.picking.batch` Extensions (Primary Model)

**File:** `models/stock_picking_batch.py`

#### `vehicle_id`
- **Type:** `Many2one('fleet.vehicle')`
- **L2:** The vehicle assigned to this dispatch. Used for capacity validation and driver lookup.
- **Constraint:** When set, `vehicle_category_id`, `driver_id`, and capacity fields are computed from the vehicle.

#### `vehicle_category_id`
- **Type:** `Many2one('fleet.vehicle.model.category')` (computed, writable)
- **L2:** Mirrors `vehicle_id.category_id`. Stored in DB so it can be set independently (e.g., to pre-assign a category before the specific vehicle is known).

#### `dock_id`
- **Type:** `Many2one('stock.location')` (computed, writable)
- **Domain:** `[('id', 'child_of', allowed_dock_ids)]`
- **L2:** The dock this batch departs from. When pickings are added to a batch with a dock set, their move destinations are automatically updated to the dock.
- **Auto-assignment:** `_compute_dock_id` sets `dock_id` automatically if all pickings in the batch share the same origin location that is also in `allowed_dock_ids`.

#### `driver_id`
- **Type:** `Many2one('res.partner')` (computed from `vehicle_id.driver_id`)
- **L2:** The driver assigned to the vehicle. Inherited from `fleet.vehicle.driver_id`.

#### `vehicle_weight_capacity`
- **Type:** `Float` (related: `vehicle_category_id.weight_capacity`)
- **L2:** Maximum weight from the vehicle's category. Used in `used_weight_percentage` compute.

#### `vehicle_volume_capacity`
- **Type:** `Float` (related: `vehicle_category_id.volume_capacity`)
- **L2:** Maximum volume from the vehicle's category. Used in `used_volume_percentage` compute.

#### `used_weight_percentage` / `used_volume_percentage`
- **Type:** `Float` (computed)
- **L2:** Percentage of vehicle capacity utilized by the batch's estimated shipment.
- **Formula:**
  ```python
  used_weight_percentage = 100 * (batch.estimated_shipping_weight / batch.vehicle_weight_capacity)
  used_volume_percentage = 100 * (batch.estimated_shipping_volume / batch.vehicle_volume_capacity)
  ```
- **Edge:** Both are `False` when `vehicle_weight_capacity` or `vehicle_volume_capacity` is 0 or unset. `estimated_shipping_weight/volume` come from `stock_picking_batch` base module (from `stock` module's move aggregations).

#### `end_date`
- **Type:** `Datetime` (computed: `scheduled_date + 1 hour`)
- **L2:** Estimated end time of the dispatch. Defaults to 1 hour after `scheduled_date`.

#### `has_dispatch_management`
- **Type:** `Boolean` (related: `picking_type_id.dispatch_management`)
- **L2:** Read-only flag indicating whether dispatch management features are enabled for this batch's picking type.

---

## Method Reference — L3

### `stock.picking.batch` — Capacity Computation

**`_compute_capacity_percentage()`**
```python
@api.depends('estimated_shipping_weight', 'vehicle_category_id.weight_capacity',
             'estimated_shipping_volume', 'vehicle_category_id.volume_capacity')
def _compute_capacity_percentage(self):
    self.used_weight_percentage = False
    self.used_volume_percentage = False
    for batch in self:
        if batch.vehicle_weight_capacity:
            batch.used_weight_percentage = 100 * (
                batch.estimated_shipping_weight / batch.vehicle_weight_capacity
            )
        if batch.vehicle_volume_capacity:
            batch.used_volume_percentage = 100 * (
                batch.estimated_shipping_volume / batch.vehicle_volume_capacity
            )
```
- **L3:** `estimated_shipping_weight` and `estimated_shipping_volume` are provided by `stock_picking_batch` / `stock` — they aggregate from the pickings' `stock.move` records.
- **L4:** Division by zero is prevented by checking `vehicle_weight_capacity` before computing. If the vehicle has no category or the category has no capacity, both percentages remain `False` (not an error).

---

### `stock.picking.batch` — Dock Assignment

**`_compute_dock_id()`**
```python
@api.depends('picking_ids', 'picking_ids.location_id', 'picking_ids.location_dest_id', 'picking_type_id')
def _compute_dock_id(self):
    for batch in self:
        if batch.picking_type_id != batch._origin.picking_type_id and batch.dock_id:
            batch.dock_id = False
        if batch.picking_ids and len(batch.picking_ids.location_id) == 1 \
                and batch.picking_ids.location_id in batch.allowed_dock_ids:
            batch.dock_id = batch.picking_ids.location_id
```
- **L3 auto-assignment:** If all pickings share the same `location_id` (origin) and that location is an allowed dock, `dock_id` is automatically set to that location. This is a convenience — users can override it manually.
- **L4:** The `len(batch.picking_ids.location_id) == 1` check uses the ORM's lazy evaluation — `location_id` on a recordset returns a unique value only when all records have the same value. This is O(1) in Python (it accesses a cached set).

---

### `stock.picking.batch` — CRUD and Lifecycle

**`create()`**
```python
@api.model_create_multi
def create(self, vals_list):
    batches = super().create(vals_list)
    batches.order_on_zip()
    batches.filtered(lambda b: b.dock_id)._set_moves_destination_to_dock()
    return batches
```
- **L3:** On batch creation, automatically sorts pickings by ZIP code and updates move destinations for batches that have a dock set. This means the dispatch is immediately ready for warehouse operators.

**`write()`**
```python
def write(self, vals):
    res = super().write(vals)
    if 'dock_id' in vals:
        self._set_moves_destination_to_dock()
    return res
```
- **L3:** If `dock_id` is changed on an existing batch, all moves in all pickings in the batch get their destination updated to the new dock.

---

### `stock.picking.batch` — Business Logic

**`order_on_zip()`**
```python
def order_on_zip(self):
    sorted_records = self.picking_ids.sorted(lambda p: p.zip or "")
    for idx, record in enumerate(sorted_records):
        record.batch_sequence = idx
```
- **L3:** Sorts pickings within the batch by customer ZIP code and assigns `batch_sequence` to create a route-friendly order. The sort is lexical on the ZIP string (not numeric) — "1000" comes before "200" in lexical order.
- **L4:** `batch_sequence` is a sequence field on `stock.picking` (from `stock_picking_batch`). It controls the order pickings appear in the batch's operation kanban and printed report.

**`_set_moves_destination_to_dock()`**
```python
def _set_moves_destination_to_dock(self):
    for batch in self:
        if not batch.dock_id:
            batch.picking_ids._reset_location()
        elif batch.picking_type_id.code in ["internal", "incoming"]:
            batch.picking_ids.move_ids.write({'location_dest_id': batch.dock_id.id})
        else:
            batch.picking_ids.move_ids.write({'location_id': batch.dock_id.id})
```
- **L3:** Updates stock move locations based on picking type:
  - **Outgoing (`outgoing`):** Updates `location_id` (source) to the dock — the goods are picked up from the dock location.
  - **Incoming (`incoming`):** Updates `location_dest_id` (destination) to the dock — goods are received at the dock.
  - **Internal:** Updates `location_dest_id` to the dock.
- **L4:** This is a dispatch-planning operation — it physically routes warehouse moves through the assigned dock. The `_reset_location` branch reverts moves to the picking's default destination when the dock is cleared.

**`_get_merged_batch_vals()`**
```python
def _get_merged_batch_vals(self):
    self.ensure_one()
    vals = super()._get_merged_batch_vals()
    vals.update({
        'vehicle_id': self.vehicle_id.id,
        'dock_id': self.dock_id.id,
    })
    return vals
```
- **L3:** When batches are merged (via `stock_picking_batch` merge wizard), the vehicle and dock from the source batch are carried forward to the merged batch.

---

## Hooks — L3

### Post-init Hook: `_enable_dispatch_management`

**File:** `__init__.py` (loaded via manifest `post_init_hook`)

```python
def _enable_dispatch_management(env):
    # Enable dispatch management on all existing picking types
    picking_types = env['stock.picking.type'].search([])
    picking_types.write({'dispatch_management': True})
```

- **L3:** On module install, enables the dispatch management flag on every picking type in the database. This ensures the UI is immediately visible for existing warehouses.
- **L4:** Uses `write()` on a potentially large recordset. For databases with thousands of picking types, this could be slow. The `stock_fleet` manifest does not wrap this in a batch loop. On upgrade, the hook re-runs and re-enables all picking types (idempotent, but not selective).

### Uninstall Behaviour

There is **no `uninstall_hook`**. Uninstalling the module leaves the `dispatch_management` flag and all capacity fields in place on existing records. The fields remain stored but `stock_fleet`'s logic no longer acts on them — the UI fields become inert. To fully clean up, manually set `dispatch_management = False` on all picking types.

---

## Workflow — L3 Dispatch Lifecycle

```
1. Create or open a stock.picking.batch
       │
       │   batch.picking_type_id.dispatch_management = True
       │   (already set by _enable_dispatch_management hook)
       ▼
2. Assign vehicle_id
       │
       │   vehicle_category_id = vehicle_id.category_id (computed)
       │   driver_id = vehicle_id.driver_id (computed)
       │   vehicle_weight_capacity = category.weight_capacity (related)
       │   vehicle_volume_capacity = category.volume_capacity (related)
       ▼
3. Add pickings to the batch
       │
       │   _compute_dock_id() auto-assigns dock if all pickings
       │   share the same origin location in allowed_dock_ids
       │
       │   OR manually set dock_id
       │
       ▼
4. (Optional) Sort by ZIP: batch.order_on_zip()
       │
       │   Each picking.batch_sequence is set based on zip
       ▼
5. Validate / Start batch
       │
       │   If dock_id is set: _set_moves_destination_to_dock()
       │     ├── Outgoing → move.location_id = dock_id
       │     ├── Incoming → move.location_dest_id = dock_id
       │     └── Internal → move.location_dest_id = dock_id
       │
       ▼
6. Warehouse operator executes moves at dock
       │
       ▼
7. End date auto-computed: scheduled_date + 1h
       │
       │   used_weight_percentage / used_volume_percentage
       │   computed against estimated_shipping_weight/volume
       ▼
```

---

## Performance Considerations — L4

### Batch Creation — `order_on_zip()`

`order_on_zip()` iterates all pickings in the batch and writes `batch_sequence` to each. For a batch with 100 pickings, this generates 100 individual `write()` calls unless `multi` optimization is applied by the ORM. Each write is a separate SQL UPDATE. For large batches (500+ pickings), consider batching the writes:

```python
def order_on_zip(self):
    sorted_records = self.picking_ids.sorted(lambda p: p.zip or "")
    for idx, record in enumerate(sorted_records):
        record.batch_sequence = idx
    # Odoo may batch these if multi=True on the field, but explicit batching:
    # self.env.cr.execute("""
    #     UPDATE stock_picking SET batch_sequence = v.seq
    #     FROM (VALUES %s) AS v(id, seq)
    #     WHERE stock_picking.id = v.id
    # """, [(r.id, i) for i, r in enumerate(sorted_records)])
```

### `_set_moves_destination_to_dock()`

The `write()` call on `move_ids` is a single ORM batch write — O(1) SQL UPDATE with a WHERE clause on move IDs. This is efficient. However, it does **not** respect move-level reservation states. If moves are already reserved (quantities assigned), changing `location_id` or `location_dest_id` may require unreserving and re-reserving quants — this can trigger additional stock.move lines and potentially alert warehouse managers to discrepancies.

### `used_weight_percentage` / `used_volume_percentage`

These fields depend on `estimated_shipping_weight` and `estimated_shipping_volume`, which are computed from the pickings' stock moves. If the pickings contain hundreds of moves, the aggregation in the base module could be slow. The recomputation is triggered when the batch form loads — it is not stored in the DB.

### `allowed_dock_ids` Related Field

```python
allowed_dock_ids = fields.Many2many(related='picking_type_id.dock_ids', string="Allowed Docks")
```

`related` fields are computed on read — they do not cause additional queries when accessed, but the underlying `dock_ids` on the picking type must be loaded. If the picking type's `dock_ids` is a large set (many internal locations in a large warehouse), loading the batch form could be slower.

---

## Security Considerations — L4

### ACL Scope

`stock_fleet` does not define its own `ir.model.access.csv`. All ACL permissions are inherited from `stock_picking_batch` and `fleet`:

| Model | Access via | Group |
|---|---|---|
| `stock.picking.batch` | `stock_picking_batch` ACL | `stock.group_stock_user` |
| `fleet.vehicle` | `fleet` ACL | `fleet.fleet_group_user` |
| `stock.picking.type` | `stock` ACL | `stock.group_stock_user` |
| `fleet.vehicle.model.category` | `fleet` ACL | `fleet.fleet_group_user` |

**L4 implication:** Any user who can access `stock.picking.batch` can assign a vehicle, dock, and view capacity utilization. Any user who can access `fleet.vehicle` can see which vehicles are assigned. There is no per-company restriction on vehicle assignment — a batch in Company A could theoretically be assigned a vehicle from Company B if the vehicle is accessible in the user's ACL scope.

### `dispatch_management` Toggle

The `dispatch_management` field is a UI toggle — it controls which fields are shown, not who can access them. All batch fields (`vehicle_id`, `dock_id`, capacity percentages) are accessible to any `stock.group_stock_user` regardless of the toggle state. The toggle only hides/show the UI elements; it does not enforce access control.

### No Write Restrictions on `vehicle_id`

A user who can edit a batch can assign any `fleet.vehicle` to it, regardless of whether that vehicle belongs to the same warehouse or company. This is a potential issue in multi-company deployments. Consider adding a `company_id` domain constraint:

```python
vehicle_id = fields.Many2one(
    'fleet.vehicle',
    domain="[('company_id', 'in', allowed_company_ids)]",
)
```

---

## Odoo 18 → Odoo 19 Changes

The `stock_fleet` module has no breaking changes between Odoo 18 and Odoo 19. All fields, methods, and behaviours are consistent.

### New in Odoo 19

None identified — `stock_fleet` is a thin integration module that was already stable in Odoo 18.

### Consistent Aspects

- `dispatch_management` field behaviour and defaulting unchanged.
- `order_on_zip()` sorting logic unchanged.
- `_set_moves_destination_to_dock()` location update logic unchanged.
- `_compute_capacity_percentage` formula unchanged.
- `post_init_hook` `_enable_dispatch_management` mechanism unchanged.

### `_get_merged_batch_vals` Addition

**Change:** The `_get_merged_batch_vals()` override (to preserve `vehicle_id` and `dock_id` during batch merge) was present in Odoo 18 as well, but its existence is worth noting as a key integration point with the `stock_picking_batch` merge wizard.

---

## Cross-Module Integration — L3

### With `stock_picking_batch`

| Integration Point | Detail |
|---|---|
| `stock.picking.batch` model | Extended with vehicle, dock, capacity fields |
| `batch_sequence` field | Written by `order_on_zip()` on batch creation |
| `write({'batch_id': ...})` | Picking's `write()` calls `_set_moves_destination_to_dock` when batch has dock |
| `_get_merged_batch_vals()` | Override preserves vehicle/dock during batch merge |

### With `fleet`

| Integration Point | Detail |
|---|---|
| `fleet.vehicle` model | `vehicle_id` on batch links to specific vehicle |
| `fleet.vehicle.driver_id` | Propagated to `driver_id` on batch |
| `fleet.vehicle.model.category` | Extended with `weight_capacity` / `volume_capacity` |
| Category `display_name` | Appends capacity to category name |

### With `stock`

| Integration Point | Detail |
|---|---|
| `stock.location` (docks) | Docks are internal locations; domain: `usage = 'internal'` |
| `stock.picking.type.dock_ids` | Many2many of allowed dock locations per picking type |
| `stock.picking.batch` picking_ids | Pickings with `location_id` in allowed docks trigger auto-dock assignment |
| `stock.picking.batch` move_ids | `_set_moves_destination_to_dock` writes to move `location_id` / `location_dest_id` |

### With `stock_warehouse`

| Integration Point | Detail |
|---|---|
| `_get_picking_type_update_values()` | Auto-enables `dispatch_management` and assigns output stock location as dock |
| `wh_output_stock_loc_id` | Used as default dock for outgoing picking types |

### Configuration Flow

```
Warehouse creation (stock.warehouse):
  └─► _get_picking_type_update_values()
        └─► Sets dispatch_management = True on out_type, pick_type, pack_type, in_type
        └─► Assigns wh_output_stock_loc_id as dock for out_type

Picking Type configuration:
  └─► Add dock locations (stock.location with usage=internal, warehouse_id=this warehouse)
  └─► Ensure dispatch_management = True

Vehicle Category configuration (fleet.vehicle.model.category):
  └─► Set weight_capacity and volume_capacity

Vehicle creation (fleet.vehicle):
  └─► Set model_id (which sets category_id)
  └─► Set driver_id

Batch dispatch:
  └─► Create batch with picking_type_id (dispatch_management = True)
  └─► Assign vehicle_id (auto-sets category, driver, capacity)
  └─► Add pickings
  └─► Auto-assigned or manually set dock_id
  └─► order_on_zip() to sequence by ZIP
  └─► Validate → moves routed to dock
```

---

## Failure Modes

| Scenario | Behaviour | Root Cause | Resolution |
|---|---|---|---|
| No capacity fields on vehicle category | `used_weight_percentage` = `False` | `fleet.vehicle.model.category` has no `weight_capacity` set | Set `weight_capacity` and `volume_capacity` on the vehicle category |
| `dock_id` not auto-assigned | Dock field stays empty after adding pickings | Pickings have different `location_id` values; none match allowed docks | Manually select a dock or add the picking origin as a dock location |
| Move destinations not updated after dock change | Warehouse operators don't see updated routing | `write({'dock_id': ...})` not called — dock set via UI but not persisted | Ensure `dock_id` is saved (click Save) before starting batch |
| `_reset_location` undoes intentional override | Move destination reverted to picking's default | Picking had a manually overridden `location_dest_id` that is a child of the picking's dest | Use a non-child location or override `_reset_location` |
| Batch merge loses dock | Merged batch has no dock | `_get_merged_batch_vals` not including dock_id (if override is removed) | Re-assign dock after merge |
| ZIP sort wrong order | Pickings ordered "1000, 200, 300" instead of numeric | Lexical string sort, not numeric | No fix in current code — request enhancement or sort in Python with `int(zip)` where zip is numeric |
| Picking type lacks `dispatch_management` | Batch form hides vehicle/dock fields | Picking type created after module install without `dispatch_management = True` | Manually set `dispatch_management = True` on the picking type |

---

## Related Documentation

- [Modules/Stock](modules/stock.md) — Core `stock.picking`, `stock.location` (docks), move routing
- [Modules/stock_picking_batch](modules/stock_picking_batch.md) — `stock.picking.batch` base model, batch operations, merge wizard
- [Modules/Fleet](modules/fleet.md) — `fleet.vehicle`, `fleet.vehicle.model.category`, driver management
- [Modules/stock_warehouse](modules/stock_warehouse.md) — `stock.warehouse`, picking types, delivery steps
- [Core/API](core/api.md) — `@api.depends`, `@api.model`, `@api.constrains`
- [Patterns/Workflow Patterns](patterns/workflow-patterns.md) — Batch validation, dock routing, dispatch workflow
- [Patterns/Security Patterns](patterns/security-patterns.md) — ACL inheritance across modules
