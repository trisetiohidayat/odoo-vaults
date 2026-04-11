# mrp_subcontracting - MRP Subcontracting

**Module:** `mrp_subcontracting`
**Depends:** `mrp`
**Category:** Manufacturing/Manufacturing

---

## Purpose

Enables manufacturing orders to be subcontracted to a third-party vendor. Components are sent to the subcontractor location, and finished products are received back. Uses a special `subcontract` BoM type to define what operations and materials the subcontractor manages.

---

## Subcontracting BoM Type

**File:** `models/mrp_bom.py`

```python
type = fields.Selection(selection_add=[
    ('subcontract', 'Subcontracting')
], ...)
subcontractor_ids = fields.Many2many('res.partner', ...)
```

- `type = 'subcontract'` - Identifies the BoM as subcontracting
- `subcontractor_ids` - List of approved subcontractor vendors
- Constraint: subcontract BoMs **cannot** have `operation_ids` or `byproduct_ids`
- `_bom_subcontract_find()` - Finds a subcontract BoM for a product/subcontractor combination, using `parent_of` domain for hierarchy matching

---

## Subcontracting Workflow

### Trigger: Incoming Receipt from Supplier

When a `stock.picking` (incoming type) with a move from supplier triggers `_action_confirm` on `stock.move`:

1. **`_get_subcontract_bom()`** - Finds `mrp.bom` of type `subcontract` for the product + subcontractor
2. **`is_subcontract = True`** - Marks the move
3. **`location_id`** - Set to `partner.property_stock_subcontractor` or `company.subcontracting_location_id`
4. **`_action_assign()`** - Re-reserves components
5. **`picking._subcontracted_produce()`** - Creates subcontracted `mrp.production` records

### Subcontracted MO Creation

**File:** `models/stock_picking.py` - `_subcontracted_produce()`

For each move with a subcontract BoM:

1. Creates `procurement.group` with `partner_id`
2. Uses `_prepare_subcontract_mo_vals()`:
   - `location_src_id` = subcontractor location
   - `location_dest_id` = subcontractor location
   - `subcontractor_id` = commercial partner of vendor
   - `bom_id` = subcontract BoM
   - `date_start` = move.date - bom.produce_delay
3. Creates and confirms the MO
4. Links finished move `move_dest_ids` back to the subcontract move

### Component Resupply

Components are automatically reserved and shipped to the subcontractor via the subcontracting location. The MO's `move_raw_ids` represent what the subcontractor has received.

---

## stock.move Extension

**File:** `models/stock_move.py`

| Field | Type | Description |
|---|---|---|
| `is_subcontract` | `Boolean` | True if this move is a subcontracting receipt |
| `show_subcontracting_details_visible` | `Boolean` | Computed - shows button to view raw materials |

**Key Methods:**

- `_action_confirm()` - Detects subcontract moves, sets `is_subcontract`, creates MO
- `_action_cancel()` - Cancels associated subcontract MOs
- `_get_subcontract_production()` - Returns `move_orig_ids.production_id` for is_subcontract moves
- `_subcontrating_should_be_record()` - Returns productions with unrecorded tracked components
- `_subcontrating_can_be_record()` - Returns productions with flexible/strict consumption
- `_subcontracting_possible_record()` - True if tracked components or flexible consumption
- `_auto_record_components()` - Automatically populates qty_producing/lot for simple cases
- `_update_subcontract_order_qty()` / `_reduce_subcontract_order_qty()` - Handles quantity changes on subcontract moves

---

## mrp.production Extension (Subcontracting)

**File:** `models/mrp_production.py`

| Field | Type | Description |
|---|---|---|
| `subcontracting_has_been_recorded` | `Boolean` | Component consumption has been recorded |
| `subcontractor_id` | `Many2one` | Restricts portal access to the subcontractor |
| `bom_product_ids` | `Many2many` | Computed from BoM lines, used for portal filtering |
| `incoming_picking` | `Many2one` | Related incoming receipt (finished product) |

**Key Methods:**

- `subcontracting_record_component()` - Records component consumption for subcontracted MO:
  - Validates qty > 0 and components consumed
  - Handles consumption issues
  - Calls `_update_finished_move()` to update subcontract picking move lines
  - Handles backorder creation

- `_update_finished_move()` - Updates move_line_ids on the subcontract receipt picking:
  - Sets `quantity`, `picked` on existing move lines
  - Creates new move lines if qty_producing exceeds reserved
  - Deletes unpicked lines if no backorder

- `_subcontracting_filter_to_done()` - Filters MOs ready to be marked done (recorded + not cancelled)
- `_get_subcontract_move()` - Returns the incoming `stock.move` with `is_subcontract = True`
- `_has_workorders()` - Returns False for subcontracted MOs (no workcenters)
- `_subcontract_sanity_check()` - Validates lot tracking for finished product and components

---

## stock.picking Extension

**File:** `models/stock_picking.py`

| Field | Type | Description |
|---|---|---|
| `display_action_record_components` | `Selection` | `hide` / `facultative` / `mandatory` based on consumption type |
| `move_line_ids_without_package` | `One2many` | Adjusted domain for subcontracting transfers |

**Key Methods:**

- `action_record_components()` - Triggers component recording wizard
- `_is_subcontract()` - True if picking is incoming with subcontract moves
- `_action_done()` - Auto-records components if not done, then marks subcontract MOs done
- `_subcontracted_produce()` - Creates subcontract MOs from subcontract details

---

## Subcontracting Location Management

**File:** `models/stock_location.py`

| Field | Type | Description |
|---|---|---|
| `is_subcontracting_location` | `Boolean` | Marks a custom subcontracting location |
| `subcontractor_ids` | `One2many` | Partners using this location as `property_stock_subcontractor` |

**Constraint:** Subcontracting locations must be `usage = 'internal'`

**Methods:**

- `_activate_subcontracting_location_rules()` - Creates stock rules for custom subcontracting locations based on the company's reference location rules
- `_archive_subcontracting_location_rules()` - Archives rules when location is no longer subcontracting

---

## res.company Extension

**File:** `models/res_company.py`

| Field | Type | Description |
|---|---|---|
| `subcontracting_location_id` | `Many2one` | The company's default subcontracting location |

Lifecycle: Created automatically by `_create_subcontracting_location()` (called in `_create_per_company_locations` hook), which also sets this location as the default `property_stock_subcontractor` on all partners.

---

## res.partner Extension

**File:** `models/res_partner.py`

| Field | Type | Description |
|---|---|---|
| `property_stock_subcontractor` | `Many2one` | Custom subcontracting location for this vendor |
| `is_subcontractor` | `Boolean` | Computed - partner is a subcontractor with portal user access |
| `bom_ids` | `Many2many` | BoMs where this partner is a subcontractor |
| `production_ids` | `Many2many` | Subcontracted MOs for this partner |
| `picking_ids` | `Many2many` | Subcontract pickings for this partner |

**Search:** `_search_is_subcontractor()` - Allows searching partners as subcontractors

---

## product.supplierinfo Extension

**File:** `models/product.py`

| Field | Type | Description |
|---|---|---|
| `is_subcontractor` | `Boolean` | Computed - this vendor is a subcontractor for this product |

Used by `_prepare_sellers()` to filter sellers by subcontractor when sourcing for subcontract production.

---

## Subcontracting Portal Access

Portal/subcontractor users can:
- See subcontracted MOs where `subcontractor_id` matches their partner
- Record component consumption via `subcontracting_record_component()`
- View raw material moves

Access is restricted via `_get_writeable_fields_portal_user()` which only allows writing: `move_line_raw_ids`, `lot_producing_id`, `subcontracting_has_been_recorded`, `qty_producing`, `product_qty`

---

## Key Integration Points

### Subcontracting Account Move

When `stock.valuation.layer` is linked to a subcontracted production, valuation flows through the standard production valuation chain. The subcontracted product's cost is determined by the MO's `_cal_price()` which computes from components + labor as normal.

### subcontracting Location Visibility

Subcontractors can access their dedicated subcontracting location via `_check_access_putaway()` which grants sudo access if the user is a subcontractor.

---

## Dependencies

```
mrp (core)
  └── mrp_subcontracting
        ├── mrp_subcontracting_account (optional - landed costs)
        ├── mrp_subcontracting_dropshipping (optional)
        └── mrp_subcontracting_repair (optional)
```

---

## Related Modules

| Module | Purpose |
|---|---|
| `mrp_subcontracting_account` | Landed costs for subcontracting |
| `mrp_subcontracting_dropshipping` | Drop-ship components to subcontractor |
| `mrp_subcontracting_purchase` | Purchase flow for subcontracting |
| `mrp_subcontracting_repair` | Repair orders with subcontracted parts |