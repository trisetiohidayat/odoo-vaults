---
Module: mrp_subcontracting
Version: Odoo 18
Type: Integration
---

# MRP Subcontracting (`mrp_subcontracting`)

> Subcontracting module for Odoo 18 Manufacturing. Enables sending components to a subcontractor, who assembles them, and returns the finished product. Core flow: vendor supplies components, you assemble, return finished product.

**Depends:** `mrp`
**Category:** Manufacturing/Manufacturing

---

## Subcontracting Flow Overview

```
Your Warehouse                    Subcontractor Location            Vendor/Partner
  (Stock)     ─── resupply picking ──►  Subcontractor Lot Stock   ──► Partner

Receipt Picking    ◄──── finished product ──  Subcontracting Location ◄── MO runs here
```

1. **PO or manual receipt** created for subcontracted product → triggers `stock.picking` (incoming)
2. `_action_confirm` on moves detects subcontract BOM → marks move `is_subcontract = True`
3. `_subcontracted_produce` creates `mrp.production` linked to the subcontractor location
4. **Component resupply** (MTS/MTO rules) ships materials to `property_stock_subcontractor` location
5. Subcontractor records components via portal → MO marked recorded
6. Receipt validated → MO `button_mark_done` → move lines updated with lot/qty
7. Landed costs applicable via `mrp_subcontracting_landed_costs`

---

## `mrp.bom` — Subcontracting Bill of Materials

Subcontracting adds one selection value and a `Many2many` for allowed subcontractors.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `type` | `Selection` | `subcontract` added via inheritance. On delete of subcontract BOM: sets `type='normal'` and `active=False` |
| `subcontractor_ids` | `Many2many res.partner` | Allowed subcontractors for this BOM. Used by `_bom_subcontract_find` to select the right vendor |

### Key Methods

**`_bom_subcontract_find(product, picking_type, company_id, bom_type, subcontractor)`**
- Searches for a subcontract BOM matching the product
- If `subcontractor` is provided, adds `('subcontractor_ids', 'parent_of', subcontractor.ids)` domain
- Returns first match ordered by `sequence, product_id, id`

**`_check_subcontracting_no_operation`** (`@api.constrains`)
- Raises `ValidationError` if `type == 'subcontract'` AND (`operation_ids` OR `byproduct_ids`) are set
- Subcontracting BOMs do NOT support work orders or by-products

### Constraints

- Subcontracting BOMs cannot have operations (`operation_ids`) or by-products (`byproduct_ids`)
- Ondelete: subcontract type → resets to `normal` + deactivates record

---

## `mrp.production` — Subcontracting MO Additions

File: `mrp_subcontracting/models/mrp_production.py`

Inherits `mrp.production`, adds fields and overrides methods for the subcontracting lifecycle.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `subcontracting_has_been_recorded` | `Boolean` | Copy=False. Set `True` when subcontractor records components via portal |
| `subcontractor_id` | `Many2one res.partner` | Restricts portal access. If set, this is a subcontracted MO |
| `bom_product_ids` | `Many2many product.product` | Compute from `bom_id.bom_line_ids.product_id`. Used to filter portal product list |
| `move_line_raw_ids` | `One2many stock.move.line` | Detail components (inverse from `move_raw_ids.move_line_ids`) |
| `incoming_picking` | `Many2one related` | `move_finished_ids.move_dest_ids.picking_id` — the receipt picking |

### Key Methods

**`subcontracting_record_component()`**
- Sets `move_raw_ids.picked = True` (marks all component lines as done)
- Validates non-zero consumption for at least one component
- Calls `_get_consumption_issues()` and `_get_quantity_produced_issues()`
- Calls `sudo()._update_finished_move()` to update subcontract picking move lines
- Sets `subcontracting_has_been_recorded = True`
- If over-production: splits production, creates backorder

**`_update_finished_move()`**
- After producing, syncs qty/lot back to the subcontract receipt move line
- Finds unpicked move lines (matched by `lot_producing_id` or no lot)
- Updates `quantity`, `picked = True`, `lot_id`
- Creates new move line if residual qty exists
- Deletes unpicked lines if no backorder needed

**`_subcontracting_filter_to_done()`**
- Filters productions where `state not in ('done','cancel')` AND `subcontracting_has_been_recorded == True`
- These are eligible for `button_mark_done`

**`_has_been_recorded()`**
- Returns `True` if state is `done`/`cancel`, or `subcontracting_has_been_recorded == True`

**`_has_tracked_component()`**
- Returns `True` if any `move_raw_ids` has `has_tracking != 'none'`

**`_has_workorders()`**
- If `subcontractor_id` is set, returns `False` (no workorders for subcontracted MO)

**`_get_subcontract_move()`**
- Returns `move_finished_ids.move_dest_ids.filtered(lambda m: m.is_subcontract)`

**`_subcontract_sanity_check()`**
- Validates: serial number required for tracked finished product
- Validates: serial number required for each tracked component line

**`action_merge()`**
- Raises `ValidationError` if `_get_subcontract_move()` exists — subcontracted MOs cannot be merged

**`_get_writeable_fields_portal_user()`**
- Returns: `['move_line_raw_ids', 'lot_producing_id', 'subcontracting_has_been_recorded', 'qty_producing', 'product_qty']`

**`pre_button_mark_done()`**
- For subcontract MOs: calls `super()` with `skip_consumption=True` context

---

## `stock.picking` — Subcontracting Additions

File: `mrp_subcontracting/models/stock_picking.py`

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `move_line_ids_without_package` | `One2many` | Domain overrides: includes subcontracting component moves |
| `display_action_record_components` | `Selection` | Computed: `hide` / `facultative` / `mandatory`. `mandatory` if tracked components; `facultative` if flexible consumption |

### Key Methods

**`_is_subcontract()`**
- `picking_type_id.code == 'incoming'` AND any `move_ids.is_subcontract`

**`_action_done()`** (override)
- For subcontract moves: auto-sets `qty_producing`/`lot_producing_id` for unrecorded MOs
- Calls `_update_subcontract_order_qty` if qty differs and `cancel_backorder` context
- Creates backorder MO per move line with correct lot/qty
- Calls `button_mark_done` on all `productions_to_done` (filtered via `_subcontracting_filter_to_done`)
- Sets production move dates to `minimum_date - 1 second` for traceability consistency

**`_subcontracted_produce(subcontract_details)`**
- `subcontract_details`: list of `(move, bom)` tuples per picking
- Skips moves that already have `move_orig_ids.production_id`
- Groups MO creation by company
- Creates `procurement.group` per picking
- Sets `date_finished` on MO to match subcontract move date
- Links finished move to subcontract move via `move_dest_ids`
- Calls `action_confirm` then `action_assign` on all MOs

**`_prepare_subcontract_mo_vals(subcontract_move, bom)`**
- Builds MO vals dict:
  - `company_id`, `procurement_group_id`, `subcontractor_id`, `picking_ids`
  - `location_src_id` = `partner_id.property_stock_subcontractor` or `company_id.subcontracting_location_id`
  - `location_dest_id` = same as `location_src_id` (MO stays at subcontractor location)
  - `date_start` = `subcontract_move.date - relativedelta(days=bom.produce_delay)`
  - `origin` = picking name

**`action_record_components()`**
- Opens MO form for the subcontracted production (via `_action_record_components`)

---

## `stock.move` — Subcontracting Additions

File: `mrp_subcontracting/models/stock_move.py`

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `is_subcontract` | `Boolean` | `True` if this is a subcontract receipt move (set during `_action_confirm`) |
| `show_subcontracting_details_visible` | `Boolean` | Computed: visible if qty > 0, not strict+untracked, and (picked OR has_been_recorded) |

### Key Methods

**`_action_confirm()`** (override)
- For incoming moves from supplier with a subcontract BOM: sets `is_subcontract = True`
- Sets `location_id` to `partner_id.property_stock_subcontractor` or `company.subcontracting_location_id`
- Calls `_action_assign` after location write (to re-reserve)
- After `super()` confirmation: calls `picking._subcontracted_produce(...)` for each picking

**`_get_subcontract_bom()`**
- Calls `mrp.bom.sudo()._bom_subcontract_find(product_id, picking_type, company_id, 'subcontract', partner)`

**`_subcontrating_should_be_record()`**
- Returns productions that are not recorded AND have tracked components (`_has_tracked_component`)

**`_subcontrating_can_be_record()`**
- Returns productions that are not recorded AND `consumption != 'strict'`

**`_subcontracting_possible_record()`**
- Returns productions where tracked OR `consumption != 'strict'`

**`_get_subcontract_production()`**
- Returns `move_orig_ids.production_id` filtered to `is_subcontract` moves

**`_action_record_components()`**
- Opens `mrp.production` form in subcontracting view for the linked MO
- Portal users get portal-specific form view

**`_auto_record_components(qty)`**
- Automatically records components when qty is changed on subcontract move
- Handles serialtracked products: splits productions per unit, generates lots
- For non-serial: sets `qty_producing`, adjusts MO qty via `change.production.qty`, calls `_set_qty_producing`
- Calls `subcontracting_record_component()` with `cancel_backorder=False`

**`_reduce_subcontract_order_qty(quantity_to_remove)`**
- Cancels or shrinks MOs when subcontracted qty is reduced
- Last MO kept alive (never cancelled if it's the only one) but may get qty zeroed

**`_update_subcontract_order_qty(new_quantity)`**
- Called when `product_uom_qty` changes on a subcontract move
- Calls `_reduce_subcontract_order_qty`

**`_action_cancel()`** (override)
- Cancels linked subcontract MOs for any subcontract move being cancelled

**`_should_bypass_reservation()`** (override)
- Returns `True` for `is_subcontract` moves (reservation bypassed)

**`_is_subcontract_return()`**
- `True` if: `is_subcontract == False`, `origin_returned_move_id.is_subcontract`, and `location_dest_id == subcontracting_location`

---

## `stock.rule` — Subcontracting Rules

File: `mrp_subcontracting/models/stock_rule.py`

### Key Methods

**`_push_prepare_move_copy_values()`** (override)
- When propagating moves through push rules: sets `is_subcontract = False` on the copied move

This ensures subcontract flag does not leak into downstream push moves.

---

## `stock.location` — Subcontracting Location

File: `mrp_subcontracting/models/stock_location.py`

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `is_subcontracting_location` | `Boolean` | Marks a location as a dedicated subcontracting location |
| `subcontractor_ids` | `One2many res.partner` | Inverse of `property_stock_subcontractor` on partners |

### Key Methods

**`_check_subcontracting_location`** (`@api.constrains`)
- Prevents the company's primary subcontracting location from being altered
- Requires `usage == 'internal'` for subcontracting locations

**`_activate_subcontracting_location_rules()`**
- Called on location creation/write when `is_subcontracting_location` is set
- Copies all rules from the company's reference subcontracting location to the new custom location
- Unarchives rules if they already exist but were archived

**`_archive_subcontracting_location_rules()`**
- Archives all rules referencing the location as source/dest when `is_subcontracting_location` is unset

**`_check_access_putaway()`**
- For subcontractor portal users: returns `self.sudo()` (bypasses access checks)

---

## `stock.warehouse` — Subcontracting Warehouse Config

File: `mrp_subcontracting/models/stock_warehouse.py`

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `subcontracting_to_resupply` | `Boolean` | Default `True`. Enables the resupply route for this warehouse |
| `subcontracting_route_id` | `Many2one stock.route` | `Resupply Subcontractor` route for this warehouse |
| `subcontracting_type_id` | `Many2one stock.picking.type` | `code='mrp_operation'`, `sequence_code='SBC'`. Subcontracting operation type |
| `subcontracting_resupply_type_id` | `Many2one stock.picking.type` | `code='internal'`, `sequence_code='RES'`. Component resupply type |
| `subcontracting_mto_pull_id` | `Many2one stock.rule` | MTO rule pulling stock to subcontractor location |
| `subcontracting_pull_id` | `Many2one stock.rule` | MTS rule (also MTO via route) pulling from subcontractor location |

### Routes Created

**`subcontracting_route_id`** — `mrp_subcontracting.route_resupply_subcontractor_mto`
- `product_categ_selectable: False`, `warehouse_selectable: True`, `product_selectable: False`
- Active when `subcontracting_to_resupply == True`

**`subcontracting_mto_pull_id`** — Rule on `stock.route_warehouse0_mto`
- Source: `lot_stock_id` → Dest: `subcontracting_location`
- `procure_method: make_to_order`, `action: pull`, `auto: manual`

**`subcontracting_pull_id`** — Rule on `subcontracting_route_id`
- Source: `subcontracting_location` → Dest: `production_location`
- `procure_method: make_to_order`, `action: pull`, `auto: manual`

**Picking Type Sequences**

| Code | Name | Sequence |
|------|------|----------|
| `SBC` | Subcontracting | `next_seq + 2` |
| `RES` | Resupply Subcontractor | `next_seq + 3` |

---

## `res.company` — Subcontracting Location

File: `mrp_subcontracting/models/res_company.py`

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `subcontracting_location_id` | `Many2one stock.location` | Per-company primary subcontracting location |

### Lifecycle

**`_create_subcontracting_location()`**
- Creates location: name=`Subcontracting Location`, usage=`internal`, `is_subcontracting_location=True`
- Sets `property_stock_subcontractor` default on `res.partner` for this company
- Called via `_create_per_company_locations()` hook

**`_create_missing_subcontracting_location()`**
- Cron-like method: finds companies without a subcontracting location and creates one
- Called via `__manifest__.py` post-init hook

---

## `res.partner` — Subcontractor Partner

File: `mrp_subcontracting/models/res_partner.py`

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `property_stock_subcontractor` | `Many2one stock.location` | Company-dependent. Partner's dedicated subcontracting location |
| `is_subcontractor` | `Boolean` | Computed: `True` if partner has portal users AND appears in any subcontract BOM |
| `bom_ids` | `Many2many mrp.bom` | Subcontracting BOMs where this partner is listed as subcontractor |
| `production_ids` | `Many2many mrp.production` | MOs where this partner is the subcontractor |
| `picking_ids` | `Many2many stock.picking` | Pickings where this partner is the subcontracting vendor |

### Key Methods

**`_search_is_subcontractor`**
- Returns partners whose `id in subcontractor_ids` of any `type='subcontract'` BOM

**`_compute_is_subcontractor`**
- `True` if any user of the partner is portal AND a subcontract BOM exists with this partner as subcontractor
- Used for portal sudo access grants

---

## `stock.quant` — Subcontracting Quant

File: `mrp_subcontracting/models/stock_quant.py`

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `is_subcontract` | `Boolean` (search only) | Search for quants in subcontracting locations |

---

## `product.supplierinfo` — Subcontractor Flag

File: `mrp_subcontracting/models/product.py`

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `is_subcontractor` | `Boolean` | Computed: `True` if vendor is in any subcontracting BOM for the product |

### Key Methods

**`_compute_is_subcontractor`**
- Reads all `variant_bom_ids` and `bom_ids` for the product
- Checks if `partner_id in boms.subcontractor_ids`

---

## Wizard: `stock.return.picking` — Subcontracting Returns

File: `mrp_subcontracting/wizard/stock_picking_return.py`

### Key Methods

**`_prepare_picking_default_values()`** (override)
- If any return line has `is_subcontract == True`: sets `location_dest_id` to `partner_id.property_stock_subcontractor`
- Ensures returns go back to the subcontractor, not to stock

**`_prepare_move_default_values()`** (override on `ReturnPickingLine`)
- Always sets `is_subcontract = False` on return moves

---

## Wizard: `change.production.qty` — Subcontracting Qty Change

File: `mrp_subcontracting/wizard/change_production_qty.py`

### Key Methods

**`_need_quantity_propagation(move, qty)`** (override)
- Returns `False` if the move has any `is_subcontract` destination move
- Prevents qty propagation to subcontracted moves

---

## Wizard: `mrp.consumption.warning` — Subcontracting Consumption

File: `mrp_subcontracting/wizard/mrp_consumption_warning.py`

### Key Methods

**`action_confirm()`** (override)
- If MO has a subcontract move: calls `subcontracting_record_component()` with `skip_consumption=True`
- Otherwise delegates to `super()`

**`action_cancel()`** (override)
- If MO has a subcontract move: opens the record components form for the subcontract move
- Otherwise delegates to `super()`

---

## Report: `report.mrp.report_bom_structure` — Subcontracting BoM Cost

File: `mrp_subcontracting/report/mrp_report_bom_structure.py`

### Key Methods

**`_get_subcontracting_line(bom, seller, level, bom_quantity)`**
- Converts seller price to company currency
- Returns line dict: `name` = subcontractor name, `prod_cost`/`bom_cost` = price × quantity

**`_get_bom_data()`** (override)
- For `bom.type == 'subcontract'`: adds `subcontracting` line using first matching subcontractor seller
- Adds subcontract cost to `bom_cost` total

**`_get_bom_array_lines()`** (override)
- Appends subcontracting line type `subcontract` with `bom_cost`, `prod_cost`, `level`

**`_find_special_rules()`** (override)
- If parent product's route is `subcontract`: looks up rules from `property_stock_subcontractor` location
- Used for component availability check at subcontractor location

**`_get_quantities_info()`** (override)
- For subcontracted products: checks `free_qty`/`qty_available` at `subcontracting_location`
- Stores in `product_info[product.id]['consumptions'][f'subcontract_{loc_id}']`

**`_get_resupply_availability()`** (override)
- For subcontract routes: computes max component delay, then `lead_time += max(vendor_lead_time, manufacture_lead_time + days_to_prepare_mo)`

---

## L4: Landed Costs for Subcontracting

The `mrp_subcontracting_landed_costs` module extends this module to support landed cost computation on subcontracting receipts.

**Flow:**
1. Receipt validated → `stock.landed.cost` created linked to the picking
2. Landed cost lines include subcontracting processing fees, freight, etc.
3. `stock.landed.cost.button_validate()` distributes costs to product valuation layers

**Landed Cost Lines available types (via `stock.landed.cost`):**
- `price_unit` — subcontracting fee
- `percentage` — % of product value
- `lumpsum` — fixed fee per receipt
- `fixed` — manual distribution

---

## L4: Component Supply to Subcontractor

Two supply modes via `stock.rule`:

| Rule | Source | Destination | Procure Method |
|------|--------|-------------|----------------|
| `subcontracting_mto_pull_id` | `lot_stock_id` | `subcontracting_location` | MTO |
| `subcontracting_pull_id` | `subcontracting_location` | `production_location` | MTO (via subcontracting route) |

**Supply triggers:**
- `make_to_order`: When subcontracted MO reserves components, an MTO procurement is created
- A `stock.picking` (internal transfer, type `subcontracting_resupply_type_id`) is generated to ship components
- The `print_label` flag on the resupply picking type enables label printing

**Consumption modes on MO:**
- `strict` (default for subcontract): Components must be consumed exactly as per BoM
- `flexible` / `overrides`: Allow variances, show consumption wizard
- When `_subcontracting_possible_record()` — components can be auto-recorded

---

## L4: Portal Subcontractor Access

Subcontractor portal users (with `is_subcontractor == True`) get:
- Dedicated receipt picking form (`subcontracting_portal_view_production_action`)
- Can record components (`subcontracting_record_component`) and lot numbers
- Access to raw material moves for their MO (`action_show_subcontract_details`)
- `sudo()` access via `_check_access_putaway()` on locations

**Restricted write fields** (portal): `move_line_raw_ids`, `lot_producing_id`, `subcontracting_has_been_recorded`, `qty_producing`, `product_qty`

---

## Security

File: `security/mrp_subcontracting_security.xml`

Typical ACL entries:
- `mrp_subcontracting.user`: read/write on subcontract pickings, read on MOs
- Portal: read-only on their own subcontract pickings and linked MOs

---

## Related Modules

| Module | Relationship |
|--------|-------------|
| `mrp_subcontracting_account` | Add subcontracting costs to MRP anal accounting |
| `mrp_subcontracting_dropshipping` | Direct dropship components to subcontractor |
| `mrp_subcontracting_landed_costs` | Landed costs on subcontracting receipts |
| `mrp_subcontracting_purchase` | PO creation from subcontracting |
| `mrp_subcontracting_repair` | Repair integration for subcontracted products |

---

## Tags

#odoo #odoo18 #mrp #subcontracting #stock #workflow
