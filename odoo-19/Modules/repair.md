---
type: module
module: repair
tags: [odoo, odoo19, repair, stock, aftersales, inventory, sale]
created: 2026-04-06
updated: 2026-04-11
---

# Repairs (`repair`)

## Overview

| Property | Value |
|----------|-------|
| **Module** | `repair` |
| **Category** | Supply Chain/Inventory |
| **License** | LGPL-3 |
| **Edition** | Community (CE) |
| **Depends** | `sale_stock`, `sale_management` |
| **Author** | Odoo S.A. |
| **Sequence** | 230 |

The Repair module manages after-sale product repairs end-to-end: intake, parts consumption (add/remove/recycle), warranty handling, and repair costing via linked sale quotations. It integrates deeply with [[Modules/Stock]] (locations, lots, moves, pickings) and [[Modules/Sale]] (quotations, service tracking). Parts are `stock.move` records with `repair_line_type` rather than a separate `repair.line` model.

---

## File Structure

```
repair/
├── __init__.py                   # registers models, wizard, report submodules
├── __manifest__.py               # Dependencies: sale_stock + sale_management
├── models/
│   ├── __init__.py
│   ├── repair.py                 # repair.order, repair.tags (MAIN model)
│   ├── stock_move.py             # stock.move extensions for repair lines
│   ├── stock_move_line.py       # _should_show_lot_in_invoice for repair lots
│   ├── stock_picking.py         # stock.picking extensions (return→repair)
│   ├── stock_traceability.py    # Traceability report links repair moves
│   ├── stock_lot.py             # stock.lot repair history counters
│   ├── product.py               # product.template / product.product extensions
│   ├── sale_order.py            # sale.order / sale.order.line extensions
│   └── stock_warehouse.py        # Warehouse repair_type_id auto-creation
├── wizard/
│   ├── stock_warn_insufficient_qty.py
│   └── stock_warn_insufficient_qty_views.xml
├── report/
│   ├── repair_reports.xml       # Report actions and paper format
│   └── repair_templates_repair_order.xml  # QWeb report template
├── security/
│   ├── repair_security.xml       # ir.rule multi-company rule
│   └── ir.model.access.csv      # ACL: stock.group_stock_user
├── data/
│   └── repair_data.xml           # Pre-created repair picking type for warehouse0
└── tests/
    ├── test_repair.py
    ├── test_anglo_saxon_valuation.py
    └── test_rules_installation.py
```

---

## Model: `repair.order`

**Primary model.** Tracks every repair job from creation to completion.

### Model Properties

```python
class RepairOrder(models.Model):
    _name = 'repair.order'
    _description = 'Repair Order'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'product.catalog.mixin']
    _order = 'priority desc, create_date desc'
    _check_company_auto = True
```

- **`mail.thread`**: Messaging, chatter, and email aliases on repair orders.
- **`mail.activity.mixin`**: Activity scheduling and to-do management.
- **`product.catalog.mixin`**: Enables the **Product Catalog** picker on the repair form (avoids the old one2many inline editor for parts). Scoped to `type='consu'` products.
- **`_check_company_auto`**: Enforces record-level company scoping on all company-dependent fields.
- **`_order`**: Default ordering by urgency then recency.

### Sequence / Naming

The `name` field is auto-generated from the `stock.picking.type` sequence on create:

```python
# models/repair.py — create()
if not vals.get('name', False) or vals['name'] == 'New':
    vals['name'] = picking_type.sequence_id.next_by_id()
```

Changing `picking_type_id` on a confirmed repair **reassigns the sequence** (the name is regenerated via `next_by_id()`). This is the only field that triggers a name change post-creation.

```python
# write(): triggers reassign when picking_type_id changes
if vals.get('picking_type_id'):
    repair.name = picking_type.sequence_id.next_by_id()
    moves_to_reassign |= repair.move_ids
```

---

### State Machine

```
draft ────── action_validate ──────> confirmed
  ↑                                    │
  │        action_repair_cancel_draft  │ action_repair_start
  │                                    ↓
cancel <─── action_repair_cancel ── under_repair
                                        │
                                        │ action_repair_end
                                        ↓ (via action_repair_done)
                                       done
```

| State | Label | Description |
|-------|-------|-------------|
| `draft` | New | Being configured; not yet validated |
| `confirmed` | Confirmed | Validated; part moves reserved or waiting |
| `under_repair` | Under Repair | Repair in progress; purely informational |
| `done` | Repaired | Completed; all moves done; product returned to output location |
| `cancel` | Cancelled | Cancelled; can reset to draft via `action_repair_cancel_draft` |

**No `ready` state.** The pipeline kanban column labelled "Ready to Process" filters `state == 'confirmed'` AND `parts_availability_state == 'available'`. This is a **UI filter**, not a state value.

---

### Field Reference

#### Core / Header

| Field | Type | Default | Constraints | Notes |
|-------|------|---------|-------------|-------|
| `name` | Char | `'New'` | Auto-increment from `picking_type_id.sequence_id`, `readonly=True`, `required=True` | Resets to new sequence when `picking_type_id` changes post-confirm |
| `company_id` | Many2one `res.company` | `env.company` | `required=True`, `readonly=True` | Multi-company scoping via `_check_company_auto` |
| `state` | Selection | `'draft'` | `readonly=True`, `tracking=True` | Drives which buttons/actions are visible |
| `priority` | Selection | `'0'` (Normal) | `0`=Normal, `1`=Urgent | Affects `_order` sort priority |
| `user_id` | Many2one `res.users` | `env.user` | `check_company=True` | Technician responsible for the repair |
| `internal_notes` | Html | False | — | Private notes for the technician (not shown to customer) |
| `tag_ids` | Many2many `repair.tags` | False | — | Kanban colour-tagged categorization |
| `repair_properties` | Properties | False | — | Schema from `picking_type_id.repair_properties_definition`; arbitrary custom fields per operation type |
| `schedule_date` | Datetime | `Datetime.now()` | `required=True` | Planned repair date; synced to all child `move_id`/`move_ids` dates on write |
| `search_date_category` | Selection | False | `store=False`, `readonly=True` | Custom search: `before/yesterday/today/day_1/day_2/after` → delegates to `stock.picking.date_category_to_domain()` |

#### Product to Repair

| Field | Type | Default | Constraints | Notes |
|-------|------|---------|-------------|-------|
| `product_id` | Many2one `product.product` | False | Domain: `type='consu'`, optional `picking_product_ids` filter | Consumable type; the product being repaired. `is_storable` check used in `action_validate()` |
| `product_qty` | Float | `1.0` | `digits='Product Unit'` | Forced to `1.0` when `tracking='serial'`; computed from return `picking_id` when set |
| `product_uom` | Many2one `uom.uom` | `product_id.uom_id` | Domain from `_compute_allowed_uom_ids` | |
| `lot_id` | Many2one `stock.lot` | False | Domain: lots in `allowed_lot_ids` | Auto-populated when return picking has exactly one lot; cleared when product changes to incompatible lot |
| `tracking` | Selection | `product_id.tracking` | `readonly=False` | Related from product; drives serial/lot validation |
| `move_id` | Many2one `stock.move` | False | `readonly=True`, `copy=False` | **Output move** for the repaired product itself, created in `action_repair_done()`; `state='done'` when repair is complete |

#### Locations — Six Distinct Locations

All location fields are **computed from `picking_type_id`** unless manually overwritten. Changing `picking_type_id` does not retroactively overwrite manually-set locations (the compute has `readonly=False`).

| Field | Computed From | Purpose | Notes |
|-------|--------------|---------|-------|
| `location_id` | `picking_type_id.default_location_src_id` | **Component source**: where parts are taken from | Source for `repair_line_type='add'` moves |
| `location_dest_id` | `picking_type_id.default_location_dest_id` (related, readonly) | **Added parts destination**: production location | Destination for `repair_line_type='add'` moves |
| `product_location_src_id` | `picking_type_id.default_product_location_src_id` | **Product source**: where the broken product is located | Used in the output `move_id` creation |
| `product_location_dest_id` | `picking_type_id.default_product_location_dest_id` | **Product destination**: where repaired product goes | Used in output `move_id` creation |
| `parts_location_id` | `picking_type_id.default_remove_location_dest_id` (related, readonly) | **Removed parts scrap**: inventory loss location | Destination for `repair_line_type='remove'` moves |
| `recycle_location_id` | `picking_type_id.default_recycle_location_dest_id` | **Recycled parts return**: back to stock | Destination for `repair_line_type='recycle'` moves |

**Computed field chain** (all depend on `picking_type_id`):

```python
@api.depends('picking_type_id')
def _compute_location_id(self):
    for repair in self:
        repair.location_id = repair.picking_type_id.default_location_src_id

@api.depends('picking_type_id')
def _compute_product_location_src_id(self): ...
@api.depends('picking_type_id')
def _compute_product_location_dest_id(self): ...
@api.depends('picking_type_id')
def _compute_recycle_location_id(self): ...
# location_dest_id, parts_location_id are related fields (stored, readonly)
# recomputed via their depends=["picking_type_id"]
```

#### Parts — `move_ids` One2many

Parts are `stock.move` records with `repair_id` set and `repair_line_type != False`. This is **not** a separate `repair.line` model.

| Field | Type | Notes |
|-------|------|-------|
| `move_ids` | One2many `stock.move`, `repair_id` | Domain: `repair_line_type != False`. Excludes the output `move_id` which has `repair_line_type=False` |

#### Parts Availability (Computed)

| Field | Type | Notes |
|-------|------|-------|
| `parts_availability` | Char | `"Available"` / `"Not Available"` / `"Exp <date>"` |
| `parts_availability_state` | Selection | `available`, `expected`, `late` |
| `is_parts_available` | Boolean, stored | All parts available (green kanban) |
| `is_parts_late` | Boolean, stored | Any part late (red kanban) |

Computed on `('state', 'in', ['confirmed', 'under_repair'])` only. Logic: for each `move_id`, compare `forecast_availability` vs `product_uom_qty`. If any shortfall → `'late'`/`'Not Available'`. If all available → `'available'`. If all available but `forecast_expected_date > schedule_date` → `'late'`.

#### Sale Order Integration

| Field | Type | Notes |
|-------|------|-------|
| `sale_order_id` | Many2one `sale.order` | Linked sale quotation; created by `action_create_sale_order()` |
| `sale_order_line_id` | Many2one `sale.order.line` | The **originating** SO line that triggered RO creation (when `service_tracking='repair'`) |
| `repair_request` | Text (related) | `sale_order_line_id.name` — the RO description from the SO |

#### Return Picking Link

| Field | Type | Notes |
|-------|------|-------|
| `picking_id` | Many2one `stock.picking` | Return picking that triggered this repair. Domain: `return_id != False`. Auto-populates `partner_id`, `lot_id`, `product_id` on the RO |
| `picking_product_ids` | One2many `product.product` (computed) | Products available from the return picking's moves |
| `picking_product_id` | Many2one `product.product` (related) | Convenience link to `picking_id.product_id` |
| `allowed_lot_ids` | One2many `stock.lot` (computed) | Lot/serial numbers available for this repair (from return picking) |
| `reference_ids` | Many2many `stock.reference` | Links to the `stock.reference` record created at RO creation |

#### UI Visibility Flags

| Field | Type | Notes |
|-------|------|-------|
| `has_uncomplete_moves` | Boolean | Any part move with `quantity < product_uom_qty` |
| `unreserve_visible` | Boolean | State not in `(draft, done, cancel)` AND any reserved qty |
| `reserve_visible` | Boolean | State in `(confirmed, under_repair)` AND any un-reserved confirmed move |
| `picking_type_visible` | Boolean | More than one repair picking type exists in company → show the picker |

---

### Key Actions and Workflow Methods

#### `action_validate()`
**Draft → Confirmed.** Entry point for validating a repair order.

```
action_validate()
├── Rejects negative quantities on move_ids → UserError
├── If product is NOT storable → _action_repair_confirm() directly
└── If product is storable:
    ├── Checks available qty at product_location_src_id for partner (owner) and no-owner
    ├── If qty sufficient → _action_repair_confirm()
    └── If qty insufficient → wizard stock.warn.insufficient.qty.repair (confirm-anyway option)
```

Wizard `action_done()` calls `_action_repair_confirm()` even when qty is insufficient, allowing forced confirmation.

#### `_action_repair_confirm()`
Internal method; does **not** check quantity.

```
_action_repair_confirm()
├── _check_company()
├── move_ids._check_company()
├── move_ids._adjust_procurement_method(picking_type_code='repair_operation')
├── move_ids._action_confirm()
├── move_ids._trigger_scheduler()  → fires orderpoints for replenishment
└── write({'state': 'confirmed'})
```

#### `action_repair_start()`
```
action_repair_start()
└── (if state != confirmed) calls _action_repair_confirm()
└── write({'state': 'under_repair'})
```
Purely **informational** — no state guard on `_action_repair_confirm` call means it can be called from draft as well.

#### `action_repair_end()`
**Precondition: `state == 'under_repair'`** — raises `UserError` otherwise.

```
action_repair_end()
├── Checks for incomplete moves (quantity < product_uom_qty) — purely informational
├── Sets picked=True on all moves if none are picked
└── Delegates to action_repair_done()
```

#### `action_repair_done()`
**Final completion logic.** Creates the output `stock.move` for the repaired product.

```
action_repair_done()
├── Cancels zero-quantity moves
├── For each repair with sale_order_line_id (service product):
│   └── If type='service' AND (no service_policy OR service_policy='ordered_prepaid'):
│       → sets qty_delivered = product_uom_qty
├── Creates output move (move_id) per repair:
│   ├── location_id = product_location_src_id
│   ├── location_dest_id = product_location_dest_id
│   ├── lot_id = repair.lot_id
│   ├── consume_line_ids = repair.move_ids.move_line_ids  ← links consumed parts
│   └── repair_id = self
├── Moves state → done via _action_done(cancel_backorder=True)
└── write({'state': 'done'})
```

**Important**: `consume_line_ids` on the output move's `move_line_ids` links the repaired product's output line to all the parts consumed. This drives the traceability report. The output move has **no `picking_id`** (`picking_id=False`), meaning it is a phantom move not tied to any transfer.

#### `action_repair_cancel()`
- **Blocked if `state == 'done'`** — raises `UserError`.
- Sets linked `sale_order_line_id.product_uom_qty = 0.0` (the line that originated the RO).
- Calls `move_ids._action_cancel()` (zeros linked SOL product_uom_qty for added parts).
- Sets `state = 'cancel'`.

#### `action_repair_cancel_draft()`
- If any repair is not already cancel: calls `action_repair_cancel()` first.
- Sets all `move_ids.state = 'draft'`.
- Sets `state = 'draft'`.
- Recomputes SOL qty from surviving moves via `_update_repair_sale_order_line()`.

#### `action_create_sale_order()`
- **Blocked if `sale_order_id` already set** — raises `UserError`.
- **Blocked if any `partner_id` missing** — raises `UserError`.
- Creates one `sale.order` per repair order.
- Calls `move_ids._create_repair_sale_order_line()` to create SOLs for all `repair_line_type='add'` moves.

#### `action_assign()` / `action_unreserve()`
- `action_assign` → delegates to `move_ids._action_assign()`
- `action_unreserve` → delegates to `move_ids._do_unreserve()` for assigned/partially-available moves

#### `action_generate_serial()`
Creates a new `stock.lot` using the product's `lot_sequence_id`, or falls back to `stock.lot._get_next_serial()`. Sets `self.lot_id` to the new lot.

#### `action_add_from_catalog()`
Overrides `product.catalog.mixin` to add a custom search view. The Product Catalog is the **replacement UI** for the old one2many inline editor.

---

### `write()` Behavior

Key side-effects on `write()`:

```python
def write(self, vals):
    # If picking_type_id changes on a non-cancel/done repair:
    # - Reassigns name from new picking type sequence
    # - Collects move_ids for unreserve + reassign
    if 'picking_type_id' in vals:
        # name regenerated; moves unreserved then re-reserved

    # If product_id changes to a serial-tracked product:
    if 'product_id' in vals and self.tracking == 'serial':
        self.write({'product_qty': 1.0})  # Force qty=1 for serial

    # Location fields (any key in MAP_REPAIR_TO_PICKING_LOCATIONS):
    # → calls move_ids._set_repair_locations() to sync

    # schedule_date change:
    # → syncs date on move_id and move_ids that are not done/cancel

    # under_warranty change:
    # → calls _update_sale_order_line_price()
```

---

## Model: `repair.tags`

```python
class RepairTags(models.Model):
    _name = 'repair.tags'
    _description = "Repair Tags"

    name = fields.Char('Tag Name', required=True)
    color = fields.Integer(string='Color Index', default=lambda self: randint(1, 11))
```

- Unique constraint on `name`.
- Used for Kanban colour categorization on `repair.order.tag_ids`.

---

## `stock.move` Extensions

```python
class StockMove(models.Model):
    _inherit = 'stock.move'

    repair_id = fields.Many2one('repair.order', check_company=True,
        index='btree_not_null', copy=False, ondelete='cascade')
    repair_line_type = fields.Selection([
        ('add', 'Add'),
        ('remove', 'Remove'),
        ('recycle', 'Recycle')
    ], store=True, index=True)
```

### Location Mapping (`MAP_REPAIR_LINE_TYPE_TO_MOVE_LOCATIONS_FROM_REPAIR`)

```python
MAP_REPAIR_LINE_TYPE_TO_MOVE_LOCATIONS_FROM_REPAIR = {
    'add':     {'location_id': 'location_id',             'location_dest_id': 'location_dest_id'},
    'remove':  {'location_id': 'location_dest_id',        'location_dest_id': 'parts_location_id'},
    'recycle': {'location_id': 'location_dest_id',        'location_dest_id': 'recycle_location_id'},
}
```

Applied by `_compute_location_id()` and `_compute_location_dest_id()` via `_get_repair_locations()`.

### Key Computed Overrides

| Method | Behavior |
|--------|----------|
| `_compute_forecast_information` | For `repair_line_type='remove'`/`'recycle'`: sets `forecast_availability=product_qty` (always "available") and `forecast_expected_date=False` (not tracked) |
| `_compute_picking_type_id` | Overrides with `repair_id.picking_type_id` for repair moves |
| `_compute_reference` | Sets `reference=repair_id.name` for repair moves |
| `_compute_location_id` / `_compute_location_dest_id` | Overrides with repair location fields |
| `_is_consuming` | Returns `True` for `repair_line_type='add'` (treated as outbound move) |
| `_should_be_assigned` | Returns `False` for repair moves — no auto-assignment on creation |
| `_get_source_document` | Returns `repair_id` if present (before falling back to `procurement_id`/`picking_id`) |
| `_split` | Returns `[]` for repair moves — **prevents splitting when partially done** |

### SO Line Synchronization

| Method | Trigger | Behavior |
|--------|---------|----------|
| `_create_repair_sale_order_line()` | Move created with `repair_line_type='add'` and `sale_order_id` exists | Creates SOL with `price_unit=0.0` if `under_warranty`, else `price_unit=move.price_unit` |
| `_update_repair_sale_order_line()` | Move `write()` with `sale_line_id` + qty/line_type change | Re-aggregates qty from all moves linked to same SOL |
| `_clean_repair_sale_order_line()` | Move cancelled or unlinked | Sets linked SOL `product_uom_qty = 0.0` |

### `create()` Hook

When a repair move is created via `repair.order._update_order_line_info()` (from Product Catalog):

```python
# stock_move.py create()
repair_moves = moves.filtered(lambda m: m.repair_id)
# Sets reference_ids from repair order
# Sets picking_type_id from repair order
draft_repair_moves._adjust_procure_method(picking_type_code='repair_operation')
draft_repair_moves._action_confirm()
draft_repair_moves._trigger_scheduler()       # Fires replenishment orderpoints
confirmed_repair_moves._create_repair_sale_order_line()  # Creates SOL lines
```

**Performance note**: `_trigger_scheduler()` fires `stock.rule` procurement for every confirmed part move, which triggers MTO/PO flows if parts are out of stock.

### `write()` Hook

```python
def write(self, vals):
    # If repair move gains sale_line_id link:
    if not move.sale_line_id and 'sale_line_id' not in vals and move.repair_line_type == 'add':
        moves_to_create_so_line |= move  # Creates new SOL

    # If repair move with SOL has qty or line_type changed:
    if move.sale_line_id and ('repair_line_type' in vals or 'product_uom_qty' in vals):
        repair_moves |= move  # Updates/re-clean SOL

    repair_moves._update_repair_sale_order_line()
    moves_to_create_so_line._create_repair_sale_order_line()
```

---

## `stock.move.line` Extension

```python
class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    def _should_show_lot_in_invoice(self):
        return super()._should_show_lot_in_invoice() or self.move_id.repair_line_type
```

Forces lot/serial numbers to appear on the generated sale invoice for repair parts. Tested in `test_repair_components_lots_show_in_invoice`.

---

## `stock.picking` Extensions

### `stock.picking.type`

```python
class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    code = fields.Selection(selection_add=[('repair_operation', 'Repair')],
        ondelete={'repair_operation': 'cascade'})
```

`ondelete='cascade'` means deleting a repair operation type cascades to delete its sequence.

**Additional fields added:**

| Field | Type | Notes |
|-------|------|-------|
| `count_repair_confirmed` | Integer | Count of confirmed (not yet started) repairs |
| `count_repair_under_repair` | Integer | Count of repairs in progress |
| `count_repair_ready` | Integer | Confirmed repairs with all parts available |
| `count_repair_late` | Integer | Confirmed repairs past `schedule_date` or with late parts |
| `default_product_location_src_id` | Many2one | Default source for the product-to-repair |
| `default_product_location_dest_id` | Many2one | Default destination for the repaired product |
| `default_remove_location_dest_id` | Many2one | Default scrap/inventory-loss location for removed parts |
| `default_recycle_location_dest_id` | Many2one | Default stock location for recycled parts |
| `repair_properties_definition` | PropertiesDefinition | Schema for `repair.order.repair_properties` |

**Default location computation:**

```python
# For repair_operation picking types:
default_location_src_id          = warehouse_id.lot_stock_id          # Stock
default_location_dest_id         = production location (usage='production') # Production
default_remove_location_dest_id  = inventory loss (usage='inventory')  # Scrap
default_recycle_location_dest_id = warehouse_id.lot_stock_id          # Back to stock
default_product_location_src_id   = warehouse_id.lot_stock_id
default_product_location_dest_id  = warehouse_id.lot_stock_id
```

### `stock.picking`

```python
class StockPicking(models.Model):
    _inherit = 'stock.picking'

    repair_ids = fields.One2many('repair.order', 'picking_id')
    nbr_repairs = fields.Integer(compute='_compute_nbr_repairs')
```

| Method | Description |
|--------|-------------|
| `action_repair_return()` | Opens `repair.order` form pre-populated with `picking_id`, `partner_id`, and warehouse's `repair_type_id`. Called from the return picking |
| `action_view_repairs()` | Smart button: opens single repair form or list if multiple |
| `get_action_click_graph()` | Redirects graph view click on repair operation type to repair-specific graph |

**Key test assertion** (`test_repair_from_return`): Parts added to a repair created from a return picking are **not** added to the return picking's move_ids — the repair's output move has `picking_id=False`.

---

## `stock.lot` Extensions

```python
class StockLot(models.Model):
    _inherit = 'stock.lot'

    repair_line_ids = fields.Many2many('repair.order', compute="_compute_repair_line_ids")
    repair_part_count = fields.Integer(compute="_compute_repair_line_ids")
    in_repair_count = fields.Integer(compute="_compute_in_repair_count")
    repaired_count = fields.Integer(compute="_compute_repaired_count")
```

| Field | Compute | Logic |
|-------|---------|-------|
| `repair_line_ids` | `_compute_repair_line_ids` | Done `stock.move` records (with `repair_line_type != False`) whose `lot_ids` include this lot |
| `repair_part_count` | `_compute_repair_line_ids` | Count of repair orders using this lot as a **part** |
| `in_repair_count` | `_compute_in_repair_count` | Non-done/non-cancel repairs where `lot_id = self` |
| `repaired_count` | `_compute_repaired_count` | Done repairs where `lot_id = self` |

| Method | Description |
|--------|-------------|
| `action_lot_open_repairs()` | Opens repair orders for this lot (with `default_repair_lot_id` context) |
| `action_view_ro()` | Smart button: single repair → form; multiple → list |
| `_check_create()` | Enforces `picking_type_id.use_create_lots` when creating a lot from a repair context |

---

## `stock.warehouse` Extensions

```python
class StockWarehouse(models.Model):
    _inherit = 'stock.warehouse'

    repair_type_id = fields.Many2one('stock.picking.type', 'Repair Operation Type',
        check_company=True, copy=False)
    repair_mto_pull_id = fields.Many2one('stock.rule', 'Repair MTO Rule', copy=False)
```

### Picking Type Auto-Creation

When a warehouse is created, `_get_picking_type_create_values()` adds:

```python
'repair_type_id': {
    'name': 'Repairs',
    'code': 'repair_operation',
    'default_location_src_id': warehouse.lot_stock_id,
    'default_location_dest_id': production_location,
    'default_remove_location_dest_id': scrap_location,
    'default_recycle_location_dest_id': warehouse.lot_stock_id,
    'sequence_code': 'RO',
    'use_create_lots': True,
    'use_existing_lots': True,
}
```

### MTO Rule

```python
'repair_mto_pull_id': {
    'procure_method': 'make_to_order',  # MTO — triggers PO/replenishment
    'auto': 'manual',
    'action': 'pull',
    'route_id': stock.route_warehouse0_mto (MTO global route),
    'location_dest_id': repair_type.default_location_dest_id,
    'location_src_id': repair_type.default_location_src_id,
    'picking_type_id': repair_type,
}
```

**Important**: The MTO rule is `procure_method='make_to_order'` with `auto='manual'`, meaning parts for repair are **not auto-procured** — they must be manually triggered or via `_trigger_scheduler()`.

### `__init__.py` Post-Init Hook

```python
def _create_warehouse_data(env):
    warehouses = env['stock.warehouse'].search([('repair_type_id', '=', False)])
    for warehouse in warehouses:
        vals = warehouse._create_or_update_sequences_and_picking_types()
        if vals:
            warehouse.write(vals)
```

This ensures any warehouse created **before** the repair module was installed gets a `repair_type_id` retroactively.

---

## `sale.order` / `sale.order.line` Extensions

### `sale.order`

```python
class SaleOrder(models.Model):
    _inherit = 'sale.order'

    repair_order_ids = fields.One2many('repair.order', 'sale_order_id')
    repair_count = fields.Integer(compute='_compute_repair_count')
```

| Method | Trigger | Behavior |
|--------|---------|----------|
| `_action_confirm()` | SO confirmed | Calls `order_line._create_repair_order()` for all lines |
| `_action_cancel()` | SO cancelled | Calls `order_line._cancel_repair_order()` for all lines |
| `action_show_repair()` | Button | Single repair → form; multiple → list filtered by `sale_order_id` |

### `sale.order.line`

#### `_create_repair_order()`

Triggered by: SO confirmation, SO line creation (if SO already confirmed), or SO line qty going from 0 → positive.

```python
# Conditions to create a repair order:
1. product_template.service_tracking == 'repair'
2. product_uom_qty > 0
3. No existing non-done repair for this SO line (idempotent)
4. No existing stock.move already linked to a repair (prevents duplicates)
```

Creates repair in `state='confirmed'` (skips draft), with:
- `partner_id` = order.partner_id
- `sale_order_id` = order.id
- `sale_order_line_id` = line.id
- `picking_type_id` = order.warehouse_id.repair_type_id

**Key**: Qty > 1 does **not** create multiple repairs — one repair per line regardless of quantity.

#### `_cancel_repair_order()`

Triggered by: SO cancellation, or SO line qty going positive → 0.

```python
# Cancels all repairs for this line that are not already done
binded_ro_ids = line.order_id.repair_order_ids.filtered(
    lambda ro: ro.sale_order_line_id.id == line.id and ro.state != 'done'
)
binded_ro_ids.action_repair_cancel()
```

**Note**: If a cancelled repair's qty is set back to positive, `_create_repair_order()` re-runs and calls `action_repair_cancel_draft()` then `_action_repair_confirm()` on the cancelled repair.

#### `_prepare_qty_delivered()`

```python
def _prepare_qty_delivered(self):
    # For SO lines sourced by a repair:
    # delivered qty = repair.move_id.quantity (output move's done qty)
    # Only counted when exactly 1 done move is linked
```

---

## `product.template` / `product.product` Extensions

### `product.template`

```python
class ProductTemplate(models.Model):
    _inherit = 'product.template'

    service_tracking = fields.Selection(selection_add=[
        ('repair', 'Repair Order')
    ], ondelete={'repair': 'set default'})
```

When `service_tracking='repair'` is deleted (ondelete='set default'), it reverts to the parent value (likely `'no'` or `False`).

Also extends `_get_saleable_tracking_types()` to include `'repair'` — allowing this service type to be sold.

### `product.product`

```python
class ProductProduct(models.Model):
    _inherit = 'product.product'

    product_catalog_product_is_in_repair = fields.Boolean(
        compute='_compute_product_is_in_repair',
        search='_search_product_is_in_repair',
    )
```

This is a **search field** used in the Product Catalog to filter products already present in the current repair order. It searches the repair order's `move_ids.product_id` set.

```python
def _count_returned_sn_products_domain(self, sn_lot, or_domains):
    or_domains.append([
        ('move_id.repair_line_type', 'in', ['remove', 'recycle']),
        ('location_dest_usage', '=', 'internal'),
    ])
    return super()._count_returned_sn_products_domain(sn_lot, or_domains)
```

Products removed or recycled in a repair are counted as "returned" for SN-tracking purposes — blocking their use as loaner/demonstration units.

---

## `stock.warn.insufficient.qty.repair` Wizard

```python
class StockWarnInsufficientQtyRepair(models.Model):
    _name = 'stock.warn.insufficient.qty.repair'
    _inherit = ['stock.warn.insufficient.qty']

    repair_id = fields.Many2one('repair.order', string='Repair')

    def _get_reference_document_company_id(self):
        return self.repair_id.company_id  # Inherits company from repair, not context

    def action_done():
        return self.repair_id._action_repair_confirm()
```

Inherits the standard insufficient-qty warning form (title, message, quantity fields) from `stock.warn.insufficient.qty`. The company sourcing via `_get_reference_document_company_id()` is critical for multi-company correctness.

---

## `stock.traceability.report` Extension

```python
class StockTraceabilityReport(models.TransientModel):
    _inherit = 'stock.traceability.report'

    @api.model
    def _get_reference(self, move_line):
        # Overrides the reference for repair moves
        if move_line.move_id.repair_id:
            return ('repair.order', move_line.move_id.repair_id.id, move_line.move_id.repair_id.name)
        return super()._get_reference(move_line)

    @api.model
    def _get_linked_move_lines(self, move_line):
        # Wires consume_line_ids / produce_line_ids into traceability
        move_lines, is_used = super()._get_linked_move_lines(move_line)
        if not move_lines:
            move_lines = move_line.move_id.repair_id and move_line.consume_line_ids
        if not is_used:
            is_used = move_line.move_id.repair_id and move_line.produce_line_ids
        return move_lines, is_used
```

The `consume_line_ids` on the output `move_id` (set in `action_repair_done()`) feed directly into the traceability report's **upstream** view, while `produce_line_ids` feed the **downstream** view.

---

## Security

### Access Control (`ir.model.access.csv`)

| ID | Name | Model | Group | R | W | C | D |
|----|------|-------|-------|---|---|---|---|
| `access_repair_user` | Repair user | `model_repair_order` | `stock.group_stock_user` | 1 | 1 | 1 | 1 |
| `access_repair_tag_user` | Repair Tags user | `model_repair_tags` | `stock.group_stock_user` | 1 | 1 | 1 | 1 |
| `access_stock_warn_insufficient_qty_repair` | Insufficient qty wizard | `model_stock_warn_insufficient_qty_repair` | `stock.group_stock_user` | 1 | 1 | 1 | 0 |

### Record Rules (`repair_security.xml`)

```xml
<record model="ir.rule" id="repair_order_rule">
    <field name="name">repair order multi-company</field>
    <field name="model_id" search="[('model','=','repair.order')]" model="ir.model"/>
    <field name="domain_force">[('company_id', 'in', company_ids)]</field>
</record>
```

Multi-company record rule: users can only see/edit repair orders belonging to their permitted companies. `_check_company_auto = True` on the model enforces field-level company checks as well.

### Security Implications

- **`stock.group_stock_user`**: All repair CRUD operations require stock user privileges. This means users must have warehouse access to manage repairs.
- **`_check_company_auto`**: Any field with `check_company=True` is automatically validated against the record's `company_id` on write. Custom fields added via `repair_properties` also inherit this check.
- **`sudo()` in test data**: Some test scenarios use `sudo()` to bypass ACL checks when creating records under different users.
- **`reference_ids` (stock.reference)**: The `stock.reference` model is shared across modules. ACL on `stock.reference` must grant read access to repair users for traceability links to work properly.

---

## Cross-Module Integration Map

```
sale.order (confirmed)
    └── sale.order.line (_create_repair_order)
            └── repair.order (state='confirmed')
                    ├── stock.move (repair_line_type='add/remove/recycle')
                    │       ├── _create_repair_sale_order_line()
                    │       │       └── sale.order.line (quotation for parts)
                    │       ├── _trigger_scheduler() → stock.rule → procurement/PO
                    │       └── _action_confirm() → state=confirmed
                    │
                    └── action_repair_done()
                            └── stock.move (output move, move_id)
                                    ├── consume_line_ids = move_ids.move_line_ids
                                    └── location_id = product_location_src_id
                                            location_dest_id = product_location_dest_id

stock.picking (return, return_id != False)
    └── action_repair_return()
            └── repair.order (picking_id=return_picking)
                    ├── partner_id = return_picking.partner_id (computed)
                    ├── lot_id = return_picking.move_ids.lot_ids (if single)
                    └── product_id = return_picking.product_id (suggested)

stock.lot
    ├── repair_line_ids (computed, from done repair moves with lot_id)
    ├── in_repair_count (non-done repairs with lot_id=self)
    └── repaired_count (done repairs with lot_id=self)

product.product
    └── service_tracking='repair' → auto-creates repair.order on SO confirm
```

---

## Parts Costing

The repair module does not carry its own cost accounting. Valuation flows through standard stock accounting:

1. **Component costs** — tracked on `stock.move` (Anglo-Saxon via `stock_account`). When `action_repair_done()` calls `_action_done()`, component moves consume inventory at their standard/last-in cost.
2. **Repaired product output** — the `move_id` created in `action_repair_done()` returns the product to `product_location_dest_id` at the cost of the components consumed (via `consume_line_ids` linking).
3. **Warranty** — `under_warranty=True` sets `price_unit=0.0` on all SOLs created from `add` moves. Customer pays nothing; cost still absorbed by inventory valuation.
4. **Labour** — not modelled in repair module. Must be added as a separate service line in the quotation post-creation.

---

## Performance Considerations

| Concern | Detail |
|---------|--------|
| **Orderpoint triggering** | `_action_repair_confirm()` calls `move_ids._trigger_scheduler()` — fires `stock.rule` for every unreserved part move. Can create many procurements on first confirm |
| **Forecast availability** | `_compute_parts_availability` forces `compute_value` on `forecast_availability` for all moves, bypassing the 1000-record prefetch chunking. Safe for typical repair sizes |
| **SO line sync on write** | Every `stock.move.write()` that touches `product_uom_qty` or `repair_line_type` triggers `_update_repair_sale_order_line()`, which groups by SOL and sums qty. Batch-friendly |
| **Traceability report** | `consume_line_ids` stored on `move_line_ids` at `action_repair_done()` time. No recompute needed; direct lookup in traceability |
| **Lot repair history** | `_compute_repair_line_ids` searches all `done` repair moves with `lot_id` — `name` depends is safe since lot names are indexed |
| **Multi-company** | Record rule `('company_id', 'in', company_ids)` supports both single-company and multi-company without additional filters |
| **Product Catalog writes** | `_update_order_line_info()` creates/updates `stock.move` records directly. Each write to `product_uom_qty` triggers `_update_repair_sale_order_line()`; batch creation via catalog is more efficient than individual line edits |
| **Reference IDs** | `stock.reference` records are created via `Command.link()` in `repair.order.create()`. The `reference_ids` Many2many on `repair.order` and the back-link on `stock.move` create dual indexes — both are read-heavy; acceptable for typical scale |
| **Lot domain search** | `_compute_allowed_lot_ids` uses `Domain()` constructor for dynamic domain from return picking's lot IDs. Safe for single-lot and multi-lot scenarios |

---

## Repair-to-Invoice Mechanism

The repair module does **not** directly generate invoices. Invoicing flows entirely through the linked `sale.order`:

### Flow: Repair Parts → Sale Quotation → Invoice

```
1. User clicks "Create Quotation" on repair order
   → action_create_sale_order()
   → Creates sale.order with origin = repair.name
   → move_ids._create_repair_sale_order_line()
      Creates sale.order.line for each 'add' move:
      - product_id = move.product_id
      - product_uom_qty = move.product_uom_qty (or move.quantity if done)
      - price_unit = 0.0 if under_warranty, else move.price_unit
      - move_ids = [move.id]  ← links SOL back to stock.move

2. User confirms sale.order (Sale Order workflow)
   → invoice generation follows standard sale order flow

3. Parts removed/recycled do NOT appear on the invoice
   → repair_line_type='remove' and 'recycle' are excluded from SOL creation

4. If under_warranty=True:
   → All 'add' SOLs created with price_unit=0.0
   → Warranty does not prevent invoicing — quotation is still sent
   → User must manually adjust or cancel the quotation

5. If repair is cancelled:
   → action_repair_cancel() sets sale_order_line_id.product_uom_qty = 0.0
   → move_ids._action_cancel() zeros the linked SOL qty
   → Existing invoices referencing those SOLs are NOT auto-reversed

6. If repair order is completed:
   → action_repair_done() does NOT trigger invoice creation
   → Invoice must be created manually from the linked sale.order
   → SOL qty_delivered is set from stock.move.quantity (not product_uom_qty)
```

### Key Constraints

- **One SO per repair order**: `action_create_sale_order()` raises `UserError` if `sale_order_id` already set
- **Customer required**: Raises `UserError` if `partner_id` is not set on any repair in the batch
- **No partial invoice**: All `add` moves for a repair are included in one SOL; partial invoicing requires splitting the repair order
- **Warranty is price-only**: No automatic invoice cancellation or discount when `under_warranty` toggled — price updates only affect future SOLs or `price_unit=0` for newly-created SOLs

---

## Failure Modes

### Parts Unavailable (Insufficient Quantity)

**Trigger**: `action_validate()` on a storable product with insufficient stock at `product_location_src_id`.

**Behavior**:
- Shows wizard `stock.warn.insufficient.qty.repair` with product name, qty available, qty requested
- User can **cancel** or **force confirm**
- Wizard `action_done()` calls `repair_id._action_repair_confirm()` regardless of qty
- Parts availability remains `'late'` / `'Not Available'` in the kanban

**Diagnosis**:
```
Is qty available at the right location?
  └→ Check repair.location_id vs stock.quant location
     └→ repair.product_location_src_id is used for availability check
        (NOT repair.location_id which is for component sourcing)

Is qty reserved by another document?
  └→ Check stock.quant._update_available_quantity()
     └→ Reserved qty reduces available qty

Is lot/owner matching?
  └→ action_validate() checks BOTH owner=partner and owner=None
     └→ Available qty = owner_qty + no-owner qty (combined)
```

### Warranty Claim (`under_warranty=True`)

**Trigger**: User manually toggles `under_warranty` checkbox on the repair order.

**Effect on invoicing**:
```
under_warranty=True → _update_sale_order_line_price()
  ├→ Finds all 'add' moves with sale_line_id
  └→ Sets price_unit=0.0, technical_price_unit=0.0 on each linked SOL

under_warranty=False → _update_sale_order_line_price()
  ├→ Finds all 'add' moves with sale_line_id
  └→ Calls sale_order_line_id._compute_price_unit()
      (recomputes from product.list_price or product supplier price)
```

**Does NOT affect**:
- Already-confirmed/posted invoices
- `remove` or `recycle` moves (no SOL created)
- `move_id` output move (product returned regardless of warranty)

**No automatic guarantee_limit**: Unlike earlier Odoo versions (≤16), there is no `guarantee_limit` date field. Automatic warranty detection based on delivery date must be implemented as custom code (e.g., overriding `_compute_under_warranty` or using `sale_order_line_id.product_id.product_tmpl_id.sale_delivery_address`).

### Product UoM Mismatch

**Trigger**: User tries to change `product_id.uom_id` on a product that has already been used in repairs.

```python
# product.py _update_uom()
def _update_uom(self, to_uom_id):
    # Groups repairs by product_uom
    repairs = self.env['repair.order']._read_group(
        [('product_id', 'in', self.ids)],
        ['product_uom', 'product_id'],
        ['id:recordset'],
    )
    for uom, product, repairs in repairs:
        if uom != product.product_tmpl_id.uom_id:
            raise UserError(_(
                'As other units of measure (ex : %(problem_uom)s) '
                'than %(uom)s have already been used for this product, '
                'the change of unit of measure can not be done.'
            ))
        repairs.product_uom = to_uom_id  # Updates all existing repairs
    return super()._update_uom(to_uom_id)
```

**Fix**: Archive the product and create a new one with the correct UoM.

---

## Odoo 18 to 19 Changes

The repair module received significant rework in Odoo 19:

1. **No `repair.line` model**: Earlier versions (Odoo ≤16) had `repair.line` and `repair.fee` as separate models. Odoo 17+ consolidated parts into `stock.move` with `repair_line_type`. Odoo 19 retains this architecture.
2. **No `guarantee_limit` date field**: The old `guarantee_limit` date field was removed. Warranty is now a manual `under_warranty` boolean. Date-based automatic warranty checking must be implemented as custom logic.
3. **No `invoice_method` field**: Invoicing is entirely via the linked `sale.order`. `invoice_method` and the direct invoice generation logic were removed.
4. **Product Catalog replacement**: The old `repair.line` one2many inline editor on the form is replaced by `product.catalog.mixin`'s catalog picker, scoped to `type='consu'` products.
5. **`is_storable` replaces `type='product'`**: Field checks use `product_id.is_storable` rather than `product_id.type == 'product'`.
6. **`_get_product_catalog_*` methods**: New catalog integration methods added for the Product Catalog picker: `_get_product_catalog_domain()`, `_get_product_catalog_order_data()`, `_get_product_catalog_record_lines()`, `_update_order_line_info()`, `_is_display_stock_in_catalog()`.
7. **`MAP_REPAIR_TO_PICKING_LOCATIONS` constant**: Introduced to centralize the mapping of repair location fields to picking type defaults, used in `write()` to detect location changes.
8. **`is_parts_available` / `is_parts_late`**: New stored boolean fields added for kanban column coloring, computed from `parts_availability_state`.
9. **`search_date_category` custom search**: Delegates to `stock.picking.date_category_to_domain()` for unified date-range filtering across both modules.
10. **`repair_properties`**: New Properties field linked to `picking_type_id.repair_properties_definition`, allowing per-operation-type custom fields on the repair form.
11. **`reference_ids` (stock.reference)**: Introduced for linking repair orders to multiple reference documents (MO, transfer, etc.), replacing or supplementing the single `picking_id` link.

---

## Related Documentation
- [[Modules/Stock]] — Locations, moves, lots, picking types, traceability
- [[Modules/sale_stock]] — MTO, dropship, sale-stock integration
- [[Modules/sale_management]] — Sale quotation management
- [[Modules/mrp_repair]] — MRP + Repair integration (phantom BOM, MTO → MO)
- [[Patterns/Workflow Patterns]] — State machine design patterns
- [[Core/Fields]] — Field types used in repair (Many2one, One2many, Properties)
- [[Core/API]] — @api.depends, @api.onchange, @api.model_create_multi usage in repair
