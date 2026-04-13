---
type: module
module: mrp
tags: [odoo, odoo19, mrp, manufacturing, bom, production, workorder, mo]
created: 2026-04-11
updated: 2026-04-11
---

# MRP (Manufacturing)

## Quick Access

### Flows (Technical — AI & Developer)
- [Flows/MRP/bom-to-production-flow](flows/mrp/bom-to-production-flow.md) — BOM to production order
- [Flows/MRP/production-order-flow](flows/mrp/production-order-flow.md) — Production execution
- [Flows/MRP/workorder-execution-flow](flows/mrp/workorder-execution-flow.md) — Workorder lifecycle

### Related Modules
- [Modules/Stock](modules/stock.md) — Inventory and materials
- [Modules/Quality](modules/quality.md) — Quality checks
- [Patterns/Workflow Patterns](patterns/workflow-patterns.md) — State machine patterns

---

| Property | Value |
|----------|-------|
| **Name** | Manufacturing |
| **Version** | 2.0 |
| **Technical Name** | `mrp` |
| **Category** | Supply Chain/Manufacturing |
| **Summary** | Manufacturing Orders & BOMs |
| **Author** | Odoo S.A. |
| **License** | LGPL-3 |
| **Application** | Yes (full application) |
| **Website** | https://www.odoo.com/app/manufacturing |

## Dependencies

```
mrp
  ├── product     # Product definitions, tracking, variants
  ├── stock       # Inventory, warehouse, moves, quants
  └── resource    # Resource calendar, work center planning
```

**Module Load Hooks:**
- `pre_init_hook/_pre_init_mrp`: Adds `unit_factor` and `manual_consumption` columns to `stock_move` via raw SQL before ORM migration (prevents OOM on large tables >1M records).
- `post_init_hook/_create_warehouse_data`: Adds `manufacture_to_resupply=True` to existing warehouses without a `manufacture_pull_id`.
- `uninstall_hook`: Unsets `pbm_route_id` on warehouses and attempts to delete the route (fails silently if route is in use by `stock.rule`).

---

## All Models in MRP Module

### Core Models

#### 1. mrp.bom — Bill of Material

**File:** `models/mrp_bom.py`
**Inherits:** `mail.thread`, `product.catalog.mixin`
**Record Name:** `product_tmpl_id` (display shows `code: product_tmpl_name` if code present)
**Order:** `sequence, id`

##### Fields (L1-L2)

| Field | Type | Default | Required | Description |
|-------|------|---------|----------|-------------|
| `code` | Char | — | No | Internal reference/code for this BOM revision |
| `active` | Boolean | `True` | Yes | Soft-delete flag. Archived BOMs are excluded from `_bom_find` unless `active_test=False` |
| `type` | Selection | `'normal'` | Yes | `'normal'` = manufacture product; `'phantom'` = kit (substitutes into procurement chain, not a manufacturing step) |
| `product_tmpl_id` | Many2one `product.template` | — | Yes | The product being manufactured. Domain: `type='consu'`. This is the `_rec_name` and the anchor for variant-specific BOMs |
| `product_id` | Many2one `product.product` | — | No | If set, this BOM is variant-specific (available only for that variant). Mutually exclusive with variant-attribute `bom_product_template_attribute_value_ids` |
| `product_qty` | Float | `1.0` | Yes | Quantity of finished product produced per BOM cycle (smallest manufacturable unit). DB constraint: `CHECK(product_qty > 0)` |
| `product_uom_id` | Many2one `uom.uom` | smallest UoM by ID | Yes | Unit of measure for `product_qty`. Changing it does not update existing MOs |
| `bom_line_ids` | One2many `mrp.bom.line` | — | No | Component lines (materials, sub-assemblies) |
| `byproduct_ids` | One2many `mrp.bom.byproduct` | — | No | Secondary products produced alongside the main product |
| `operation_ids` | One2many `mrp.routing.workcenter` | — | No | Routing operations (work center steps) |
| `consumption` | Selection | `'warning'` | Yes | Component consumption enforcement: `'flexible'` (no warning), `'warning'` (warn on close), `'strict'` (manager blocks close) |
| `ready_to_produce` | Selection | `'all_available'` | Yes | When MO becomes `confirmed`/`reservation_state='assigned'`: `'all_available'` requires all components reserved; `'asap'` reserves only components for the first operation (requires `workorder_ids`) |
| `produce_delay` | Integer | `0` | No | Manufacturing lead time in **days**, added to `date_deadline` to compute `date_start`. In multi-level BOMs, delays of all sub-components are summed. In subcontracting, drives when components should be sent |
| `days_to_prepare_mo` | Integer | `0` | No | Days before MO creation for component procurement scheduling. Added to total lead time in `stock.rule._get_lead_days` as `'Days to Supply Components'` |
| `picking_type_id` | Many2one `stock.picking.type` | — | No | Controls: (1) which `stock.picking.type` the MO uses; (2) which BOM `_bom_find` returns when a `stock.rule` triggers manufacturing. Domain: `code='mrp_operation'` |
| `allow_operation_dependencies` | Boolean | `False` | No | When `True`, enables `blocked_by_operation_ids` on operations and `blocked_by_workorder_ids` on generated work orders. If `True` but no dependencies specified, all operations are assumed simultaneously startable |
| `company_id` | Many2one `res.company` | `env.company` | No | Multi-company scoping. BOMs with `company_id=False` are global |
| `batch_size` | Float | `1.0` | No | If `enable_batch_size=True`, all auto-generated MOs for this product will be this quantity. Must be positive (enforced by `_check_valid_batch_size`) |
| `enable_batch_size` | Boolean | `False` | No | Enables batch-size splitting for procurement-triggered MOs |
| `sequence` | Integer | — | No | Determines BOM priority when multiple BOMs exist for the same product/variant. Lowest sequence wins |
| `possible_product_template_attribute_value_ids` | Many2many | computed | No | All attribute values that could be applied to this BOM (computed from `product_tmpl_id.attribute_line_ids`) |
| `operation_count` | Integer | computed | No | Count of `operation_ids` (informational) |
| `show_set_bom_button` | Boolean | computed | No | Controls display of the "Set BoM on Orderpoint" button |

##### Key Methods (L3-L4)

```python
@api.model
def _bom_find(products, picking_type=None, company_id=False, bom_type=False):
    """
    Find the BEST (lowest sequence) BOM for each product in the recordset.

    L3: Resolution priority:
        1. Variant-specific BOM (product_id match) — highest priority
        2. Template-level BOM (product_id=False) — fallback
        3. Company-scoped BOMs preferred over global (company_id=False)
        4. picking_type-matched BOM preferred (for route-specific MOs)
    L4: Performance — single-product path avoids the inner loop over product_tmpl_id.product_variant_ids,
        cutting from O(products × BOMs × variants) to O(BOMs) for the common case.
    Returns: defaultdict(lambda: self.env['mrp.bom']) — missing products get empty recordset.
    """
```

```python
def explode(product, quantity, picking_type=False, never_attribute_values=False):
    """
    Recursively explodes the BOM into flattened component lines.

    L3: Handles multi-level BOMs (sub-BOMs), phantom kits, and variant-specific lines.
        For phantom sub-BOMs: recursively converts line qty via `bom.product_uom_id`.
        For normal sub-BOMs: adds to lines_done directly.
    Returns: (boms_done, lines_done) — both lists of (record, values_dict) tuples.
    L4 Performance: Clears product_ids set before the inner loop to avoid stale lookups.
        last line quantity is ROUNDED UP (UOM level), so partial units trigger full UOM consumption.
    """
```

```python
def _set_outdated_bom_in_productions():
    """
    Called when bom_line_ids, byproduct_ids, product_tmpl_id, product_id, or product_qty changes.
    Sets is_outdated_bom=True on confirmed/draft MOs using this BOM.
    L3: Draft MOs are flagged so users see the stale BOM indicator.
        Confirmed MOs are flagged so they can be updated via action_update_bom.
    """
```

```python
@api.constrains('active', 'product_id', 'product_tmpl_id', 'bom_line_ids')
def _check_bom_cycle():
    """
    Detects circular BOM dependencies (A uses B uses A).
    L3: Walks all sub-BOMs recursively. Only checks active BOMs.
        Variant-aware: groups components by attribute value to detect variant-specific cycles.
    L4 Failure Mode: False positives possible with very complex multi-level variants.
        The cycle check is skipped for archived BOMs to avoid cascading failures on archive.
    """
```

```python
def action_compute_bom_days():
    """
    Reads the BoM structure report to compute days_to_prepare_mo automatically.
    L3: Calls _get_max_component_delay on all components recursively.
        Returns a display_notification warning if any component lacks route information.
    """
```

##### BOM Consumption Modes (L3)

| Mode | Behavior | Manager Override? | Use Case |
|------|----------|-----------------|----------|
| `flexible` | No enforcement; any qty consumed is accepted | N/A | Job shop / variable yield processes |
| `warning` | Triggers consumption warning wizard on MO close | N/A | Standard assembly — warns but does not block |
| `strict` | Blocks MO close if consumption differs from BOM | Yes (requires `group_mrp_manager`) | Regulated manufacturing, yield-controlled processes |

**`is_outdated_bom` flag:** When a BOM used by confirmed/draft MOs is modified, `is_outdated_bom=True` is set. Users see an "Update BoM" button to relink the MO's moves/operations without losing progress.

##### Phantom BOM Kit Substitution (L4)

`type='phantom'` BOMs are resolved in the procurement chain — **not** by creating MOs. When `stock.rule.run()` processes a kit product:
1. `bom_kit = mrp.bom._bom_find(product, bom_type='phantom')` finds the kit BOM
2. `bom_kit.explode()` flattens all sub-components
3. Individual `stock.rule.run()` calls are made for each component (with `bom_line_id` injected into `procurement.values`)
4. The kit move is **cancelled and deleted**; no `mrp.production` is ever created

**Constraint:** Products with `stock.warehouse.orderpoint` records **cannot** have a phantom BOM (raises `ValidationError` in `_check_kit_has_not_orderpoint`). This prevents circular procurement loops.

##### Variant-Specific BOM Logic (L4)

`bom_product_template_attribute_value_ids` on lines/operations/byproducts specifies which variant combinations activate that line. Resolution uses `product._match_all_variant_values()`:
- `create_variant='no_variant'`: attribute values are **excluded** from match (line is optional)
- `create_variant='always'/'dynamic'`: attribute values must be present on the variant

L4 Edge Case: When `product_id` is explicitly set on a BOM, `bom_product_template_attribute_value_ids` cannot also be set (`_check_bom_lines` raises `ValidationError`). These two modes are mutually exclusive.

---

#### 2. mrp.bom.line — BOM Line (Component)

**File:** `models/mrp_bom.py`
**Rec Name:** `product_id`
**Order:** `sequence, id`
**Constraint:** `CHECK(product_qty >= 0)` — zero-qty lines are **allowed** as optional components

##### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `product_id` | Many2one `product.product` | required | The component being consumed |
| `product_tmpl_id` | Many2one `product.template` | computed, stored | Mirror of `product_id.product_tmpl_id` |
| `product_qty` | Float | `1.0` | Quantity of this component per BOM cycle. Can be 0 (optional line) |
| `product_uom_id` | Many2one `uom.uom` | auto-set from product | UoM for the component. Onchange `product_id` auto-fills this |
| `sequence` | Integer | `1` | Display and explosion order |
| `bom_id` | Many2one `mrp.bom` | required, cascade delete | Parent BOM |
| `bom_product_template_attribute_value_ids` | Many2many | — | Variants required for this line to apply |
| `operation_id` | Many2one `mrp.routing.workcenter` | — | If set, this component is consumed **during** that specific operation (enables `manual_consumption=True` on the generated `stock.move`) |
| `child_bom_id` | Many2one `mrp.bom` | computed | If the component has its own BOM, this is the sub-BOM. Used by `explode()` for multi-level expansion |
| `child_line_ids` | One2many `mrp.bom.line` | computed | Lines of the sub-BOM (if `child_bom_id` is set) |
| `tracking` | Selection | related | From `product_id.tracking`: `'none'`, `'lot'`, `'serial'` |
| `attachments_count` | Integer | computed | Count of `product.document` records attached to the component |

##### Key Methods

```python
def _skip_bom_line(product, never_attribute_values=False):
    """
    L3: Determines whether this line should be skipped for a given finished product variant.
        Delegates to mrp.bom._skip_for_no_variant() for variant matching logic.
    L4: Returns False for lines with no product (shouldn't occur) or product.template (placeholder).
    """
```

```python
def _prepare_bom_done_values(quantity, product, original_quantity, boms_done):
    # Used during explode() to return structured dict for boms_done list
    return {'qty': quantity, 'product': product, 'original_qty': original_quantity, 'parent_line': self}

def _prepare_line_done_values(quantity, product, original_quantity, parent_line, boms_done):
    # Used during explode() to return structured dict for lines_done list
    return {'qty': quantity, 'product': product, 'original_qty': original_quantity, 'parent_line': parent_line}
```

**L4 `manual_consumption` determination:** When `operation_id` is set on a BOM line, `_determine_is_manual_consumption(bom_line)` returns `True`, making the resulting `stock.move.manual_consumption = True`. Any manual edit to the move's quantity also sets `manual_consumption = True`.

---

#### 3. mrp.bom.byproduct — Byproduct

**File:** `models/mrp_bom.py`

##### Fields

| Field | Type | Description |
|-------|------|-------------|
| `product_id` | Many2one `product.product` | The secondary product produced |
| `product_qty` | Float | Quantity produced per BOM cycle |
| `product_uom_id` | Many2one `uom.uom` | Auto-set from `product_id` on change |
| `cost_share` | Float | Percentage (0–100, 2 decimal places) of final product cost allocated to this byproduct. **Total across all byproducts per variant must not exceed 100** (enforced by `_check_bom_lines` on BOM and `_check_byproducts` on MO) |
| `operation_id` | Many2one `mrp.routing.workcenter` | Operation during which this byproduct is produced |
| `bom_id` | Many2one `mrp.bom` | Parent BOM, cascade delete |
| `bom_product_template_attribute_value_ids` | Many2many | Variants for which this byproduct applies |
| `sequence` | Integer | Display order |

**L4 Cost Share Mechanics:** The `cost_share` affects **cost accounting** (valuation of the main product) but does **not** affect stock moves directly. When `stock.valuation_account` entries are created, the byproduct's cost is offset against the main product's cost by `cost_share`%. A byproduct cannot be the same as the main BOM product (enforced by both `_check_bom_lines` on BOM and `_check_byproducts` on MO).

---

#### 4. mrp.routing.workcenter — Routing Operation

**File:** `models/mrp_routing.py`
**Inherits:** `mail.thread`, `mail.activity.mixin`
**Order:** `bom_id, sequence, id`

##### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Operation name (e.g., "Assembly", "Welding") |
| `active` | Boolean | Allows archiving obsolete operations |
| `workcenter_id` | Many2one `mrp.workcenter` | Assigned work center (required) |
| `sequence` | Integer | `100` default; determines routing order |
| `bom_id` | Many2one `mrp.bom` | Parent BOM (cascade delete) |
| `company_id` | Many2one | Related from `bom_id.company_id` (readonly) |
| `time_mode` | Selection | `'manual'` (fixed duration) or `'auto'` (computed from past WOs) |
| `time_mode_batch` | Integer | How many past work orders to average for `time_cycle` auto-computation |
| `time_cycle_manual` | Float | Fixed cycle time in minutes (used when `time_mode='manual'`) |
| `time_cycle` | Float | **Computed** or fixed cycle time in minutes per cycle |
| `cycle_number` | Integer | Number of cycles for current quantity (computed from qty/capacity) |
| `time_total` | Float | Total duration: `setup + cleanup + cycle_number × time_cycle × 100/efficiency` |
| `show_time_total` | Boolean | Whether to display total duration (hidden when single-cycle with no setup/cleanup) |
| `cost_mode` | Selection | `'actual'` (tracked time) or `'estimated'` (theoretical time × workcenter costs_hour) |
| `cost` | Float | Computed cost: `time_total / 60 × workcenter_id.costs_hour` |
| `blocked_by_operation_ids` | Many2many `mrp.routing.workcenter` | Operations that must complete before this one starts (same BOM) |
| `needed_by_operation_ids` | Many2many | Inverse of blocked_by (operations this operation blocks) |
| `workorder_count` | Integer | Count of finished work orders using this operation |

##### Time Computation (L3-L4)

```python
# time_total = time_start + (cycle_number × time_cycle × 100/efficiency) + time_stop
# where:
#   time_start = workcenter.time_start   (setup)
#   time_stop  = workcenter.time_stop    (cleanup)
#   cycle_number = ceil(qty / capacity)
#   capacity = workcenter._get_capacity(product, unit, bom.product_qty) → (capacity_qty, setup_mins, cleanup_mins)
```

**L4 Auto time_cycle computation:** When `time_mode='auto'`, `_compute_time_cycle` searches the last `time_mode_batch` (default 10) **finished** work orders for this operation, averages their `duration`, and divides by the total `cycle_number` across those WOs. This normalizes for batch-size changes.

**L4 Workcenter capacity priority:** `workcenter._get_capacity()` returns product-specific capacity if available (`capacity_ids` record with matching `product_id` AND `product_uom_id`), else UoM-general capacity, else default `1.0`.

---

#### 5. mrp.production — Manufacturing Order

**File:** `models/mrp_production.py` (~1900 lines)
**Inherits:** `mail.thread`, `mail.activity.mixin`, `product.catalog.mixin`
**Date Field:** `date_start` (controls reservation and planning)
**Order:** `priority desc, date_start asc, id`

##### Fields (L1-L2)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | Char | `'New'` → sequence | Reference. Assigned on `create()` from picking_type sequence. Cannot be changed after confirmation. Constraint: `unique(name, company_id)` |
| `priority` | Selection | `'0'` | PROCUREMENT_PRIORITIES. Components reserved highest priority first |
| `backorder_sequence` | Integer | `0` | Non-zero means this MO is part of a backorder chain. `0` = no related backorder |
| `origin` | Char | — | Source document (e.g., SO name, MO name if propagated) |
| `product_id` | Many2one `product.product` | computed from `bom_id` | Domain: `type='consu'`. Compute auto-fills from `bom_id` if not set |
| `product_qty` | Float | computed from `bom_id.product_qty` | Qty to produce. DB constraint: `CHECK(product_qty > 0)` |
| `product_uom_id` | Many2one `uom.uom` | computed | Resolved from `bom_id.product_uom_id` or `product_id.uom_id` |
| `allowed_uom_ids` | Many2many `uom.uom` | computed | UoMs the user may select (product's own UoM + its alternative UoMs + BOM's UoM) |
| `bom_id` | Many2one `mrp.bom` | computed | Auto-resolved via `_bom_find`. Respects variant-specific vs template-level |
| `lot_producing_ids` | Many2many `stock.lot` | — | Lot/serial numbers assigned to finished product |
| `qty_producing` | Float | `0` | Quantity currently being produced in the active produce wizard |
| `qty_produced` | Float | computed | Sum of `done` finished move quantities (only `picked=True` moves counted) |
| `product_uom_qty` | Float | computed | `product_qty` converted to product's base UoM (for stock reports) |
| `state` | Selection | computed | `'draft'→'confirmed'→'progress'→'to_close'→'done'→'cancel'`. **Store-computed** from moves/WOs. See state machine below |
| `reservation_state` | Selection | computed | `'confirmed'` (waiting), `'assigned'` (ready), `'waiting'` (waiting another op) |
| `date_deadline` | Datetime | computed | Latest date production must finish to meet delivery. Set from procurement or MO creation |
| `date_start` | Datetime | `now` | Planned/actual start. Defaults to `now` or `date_deadline - 1 hour` |
| `date_finished` | Datetime | computed | `date_start + produce_delay` (plus WO durations if planned) |
| `duration_expected` | Float | computed | Sum of all WO `duration_expected` values |
| `duration` | Float | computed | Sum of all WO `duration` (actual) values |
| `location_src_id` | Many2one `stock.location` | computed | Components source. Resolved from `picking_type_id.default_location_src_id` or warehouse `lot_stock_id` |
| `location_dest_id` | Many2one `stock.location` | computed | Finished products destination. Resolved from `picking_type_id` or warehouse `lot_stock_id` |
| `production_location_id` | Many2one `stock.location` | computed | The `property_stock_production` location (intermediate between src and dest) |
| `picking_type_id` | Many2one `stock.picking.type` | computed | MRP operation type. Priority: explicit context > `bom_id.picking_type_id` > first company MRP operation type |
| `move_raw_ids` | One2many `stock.move` | computed (draft only) | Component stock moves. Recomputes on `bom_id`, `product_id`, `product_qty`, `location_src_id` changes |
| `move_finished_ids` | One2many `stock.move` | computed | Finished product + byproducts moves |
| `move_byproduct_ids` | One2many | computed | Filtered: finished moves where `product_id != production.product_id` |
| `workorder_ids` | One2many `mrp.workorder` | computed (draft only) | Work orders from BOM operations. Recomputes on BOM/product changes |
| `user_id` | Many2one `res.users` | `env.user` | Responsible. Domain limited to `group_mrp_user` members |
| `company_id` | Many2one `res.company` | `env.company` | Required |
| `is_locked` | Boolean | `not group_unlocked_by_default` | Locked MOs block qty/editing after `done`. Toggle with `action_toggle_is_locked()` |
| `is_planned` | Boolean | computed | `True` if any WO has both `date_start` and `date_finished` |
| `is_outdated_bom` | Boolean | `False` | `True` when the linked BOM has been modified since MO creation |
| `is_delayed` | Boolean | computed | `True` when `date_deadline < now` or `date_deadline < date_finished` |
| `consumption` | Selection | `'flexible'` | Copied from `bom_id.consumption` on `action_confirm()`. **Readonly after confirmation** |
| `components_availability` | Char | computed | Display string: `'Available'`, `'Not Available'`, or `'Exp YYYY-MM-DD'` |
| `components_availability_state` | Selection | computed | `'available'`, `'expected'`, `'late'`, `'unavailable'` |
| `production_capacity` | Float | computed | Max producible qty given current component stock: `min(available_qty / unit_factor)` across all components |
| `unbuild_ids` | One2many `mrp.unbuild` | — | Unbuild orders linked to this MO |
| `unbuild_count` | Integer | computed | Count of unbuild orders |
| `scrap_ids` | One2many `stock.scrap` | — | Scrap records from this MO |
| `scrap_count` | Integer | computed | Count of scrap records |
| `production_group_id` | Many2one `mrp.production.group` | created on `create()` | Groups related MOs (backorders, child MOs). Shared with all member `stock.move`s |
| `reference_ids` | Many2many `stock.reference` | — | Source document references for traceability |
| `orderpoint_id` | Many2one `stock.warehouse.orderpoint` | — | If MO was triggered by a reorder rule |
| `propagate_cancel` | Boolean | `False` | If True, cancelling a move triggers cancellation of downstream moves |
| `mrp_production_child_count` | Integer | computed | Count of child MOs in the same `production_group_id` |
| `mrp_production_backorder_count` | Integer | computed | Count of all MOs in the same `production_group_id` |
| `show_lock` | Boolean | computed | Whether lock/unlock buttons display |
| `show_lot_ids` | Boolean | computed | Whether to show lot/serial shortcut on moves |
| `show_generate_bom` | Boolean | computed | Shows "Generate BoM" button (no BOM, has components) |
| `show_produce` / `show_produce_all` | Boolean | computed | Controls produce wizard button visibility |
| `allow_workorder_dependencies` | Boolean | propagated from `bom_id` | Set at MO confirmation to mirror `bom_id.allow_operation_dependencies` |
| `forecasted_issue` | Boolean | computed | `True` when virtual_available of the finished product is negative at `date_start` |
| `show_allocation` | Boolean | computed | `True` when other moves in the warehouse can fulfill this MO's components |
| `delay_alert_date` | Datetime | computed | Latest `delay_alert_date` from raw component moves |
| `serial_numbers_count` | Integer | computed | Count of `lot_producing_ids` (for serial-tracked products) |
| `json_popover` | Char | computed | JSON blob for the late-delivery popover widget |
| `never_product_template_attribute_value_ids` | Many2many | — | "Never" attribute values for BOM explosion (excluded variants) |

##### Production State Machine (L3)

```
draft ───► confirmed ───► progress ───► to_close ───► done
   │                          │
   └──► cancel              ──┴──► cancel
```

**`_compute_state` logic (L4):**
1. If `state='cancel'` or all finished moves cancelled → `cancel`
2. If `state='done'` or (all raw moves `done/cancel` AND all finished moves `done/cancel`) → `done`
3. If all WOs `done/cancel` → `to_close`
4. If no WOs and `qty_producing >= product_qty` → `to_close`
5. If any WO `in progress/done` OR `qty_producing > 0` OR any raw move `picked` → `progress`
6. Otherwise → `confirmed`

**L4 Edge Case — Flexible Consumption:** When `consumption='flexible'` and user clicks Cancel on an MO where all raw moves are already `done/cancel` (but qty consumed < qty expected), the MO is automatically set to `done` rather than left in an orphaned `progress` state.

**Reservation State Computation (L3):**
```
reservation_state derived from move_raw_ids._get_relevant_state_among_moves():
  'partially_available' + bom_id.ready_to_produce='asap' → calls _get_ready_to_produce_state()
    → 'assigned' if all moves for 1st operation are 'assigned'
    → 'confirmed' otherwise
  otherwise → same state as moves
```

##### Key Action Methods (L3-L4)

```python
def action_confirm():
    """
    L3: Confirms the MO, triggering:
        1. UoM normalization for serial-tracked products (forces product_uom_id = product.uom_id)
        2. Copies bom_id.consumption → production.consumption (readonly after)
        3. _adjust_procure_method() on raw moves (determines MTS vs MTO)
        4. _action_confirm(merge=False) on all moves
        5. workorder_ids._action_confirm() → _link_workorders_and_moves()
        6. _trigger_scheduler() for under-stocked components
        7. Picking confirm for associated pickings
        8. state='confirmed' (for draft MOs only)
    L4: create_proc=False when called from procurement to avoid recursive trigger.
        Uses ignore_mo_ids context to prevent redundant scheduler triggers.
    """

def button_plan():
    """
    L3: Plans all un-planned work orders.
        Confirms draft MOs first, then calls _plan_workorders() for each.
    """

def _plan_workorders(replan=False):
    """
    L3: Schedules all WOs using backward scheduling from date_finished.
        Starts from WOs with no dependencies (needed_by_workorder_ids is empty).
        Each WO._plan_workorder() creates a resource.calendar.leaves record.
        Then writes date_start/date_finished back to the MO.
    L4: Final MO date_start = min(all WO date_start), date_finished = max(all WO date_finished).
        If allow_workorder_dependencies=True, respects blocked_by chain;
        otherwise, sequences WOs in sort order.
    """

def _get_consumption_issues():
    """
    L3: Compares actual vs expected component consumption.
        Expected = recomputed from BOM × current qty_producing.
        Actual = sum of picked quantities on raw moves.
        Returns list of (order, product, consumed_qty, expected_qty) tuples.
        Skipped if consumption='flexible' or no BOM.
    L4: Extra lines (consumed product not in BOM, picked with non-zero qty) → consumed=actual, expected=0.
    """

def action_cancel():
    """
    L3: Cancels the MO and all non-done moves/WOs.
        Does NOT allow cancelling done MOs (raises UserError).
        Logs activity on parent MOs for cancelled child MOs.
        Cancels pickings that have no done destination moves.
    L4: If flexible BOM and all moves done/cancel, auto-sets state='done'.
    """

def action_generate_bom():
    """
    L3: Creates a new BOM from this MO's current state.
        Returns _get_bom_values() tuple: (bom_lines_vals, byproduct_vals, operations_vals).
        Passes parent_production_id in context so the new BOM is auto-linked back to this MO.
    """

def action_update_bom():
    """
    L3: Re-links the MO to the current BOM (recomputes moves/WOs from BOM structure).
        Clears is_outdated_bom flag.
    """
```

##### Component Move Creation (L3-L4)

`_get_moves_raw_values()` is the canonical method generating `stock.move` dictionaries for each BOM line:
- `raw_material_production_id = self.id`
- `bom_line_id = bom_line.id`
- `procure_method = 'make_to_stock'` (always)
- `manual_consumption = _determine_is_manual_consumption(bom_line)` — True if line has `operation_id`
- `product_uom_qty = line_data['qty']` (from `bom.explode()`)

L4: When a move is manually added (no `bom_line_id`), `manual_consumption` defaults to False and the move is preserved on BOM changes. Moves from sub-phantom BOMs are **not** created — they are exploded inline.

##### Backorder Creation (L4)

Triggered via `mrp_production_backorder` wizard when `qty_produced < product_qty`:
1. Backorder MO created via `_post_inventory(cancel_backorder=True)`
2. Remaining raw move quantities split to backorder via `_split_draft_moves`
3. Backorder inherits same `production_group_id` as original
4. `backorder_sequence` incremented on the original MO
5. WOs that are `done` are not duplicated; partial WOs are linked to the backorder

---
## Override Patterns (L4)

### Component Move Override — `_get_moves_raw_values`

The canonical method generating `stock.move` dictionaries for each BOM line:

```python
def _get_moves_raw_values(self):
    # 1. Compute factor: MO qty expressed in BOM UoM, divided by BOM batch qty
    factor = production.product_uom_id._compute_quantity(
        production.product_qty, production.bom_id.product_uom_id, round=False
    ) / production.bom_id.product_qty
    # 2. Explode the BOM — recursively handles sub-BOMs and phantom kits
    _boms, lines = production.bom_id.explode(
        production.product_id, factor,
        picking_type=production.bom_id.picking_type_id,
        never_attribute_values=production.never_product_template_attribute_value_ids
    )
    # 3. For each exploded line:
    for bom_line, line_data in lines:
        # Skip phantom sub-BOMs (already exploded inline) and non-consumable products
        if bom_line.child_bom_id and bom_line.child_bom_id.type == 'phantom' \
                or bom_line.product_id.type != 'consu':
            continue
        # operation_id from line OR from parent_line (for sub-BOM lines)
        operation = bom_line.operation_id.id \
            or line_data['parent_line'] and line_data['parent_line'].operation_id.id
        moves.append(production._get_move_raw_values(...))
```

**Override point:** To add custom component logic, override `_get_moves_raw_values` and call `super()` first, then filter or augment the returned list. Do **not** override `_get_move_raw_values` without also updating the three documented copy sites (manual components, copied MO, backorder creation).

### Component Move Update — `_update_raw_moves`

Called when MO quantity changes (via `change_production.qty` wizard):

```python
def _update_raw_moves(self, factor):
    # factor = new_qty / old_qty
    for move in self.move_raw_ids.filtered(lambda m: m.state not in ('done', 'cancel')):
        old_qty = move.product_uom_qty
        # Always round UP to avoid under-consuming
        new_qty = move.product_uom.round(old_qty * factor, rounding_method='UP')
        if new_qty > 0:
            move.write({'product_uom_qty': new_qty})
        if move.reference_ids != self.reference_ids:
            move.reference_ids = self.reference_ids.ids
```

**Failure mode:** If `factor < 1` (MO quantity decreased), UoM rounding may cause moves to retain quantities exceeding the new MO qty.

### Finished + Byproduct Moves — `_get_moves_finished_values` / `_create_update_move_finished`

```python
def _get_moves_finished_values(self):
    moves = []
    # Main finished product move
    finished_move_values = production._get_move_finished_values(
        production.product_id.id, production.product_qty, production.product_uom_id.id
    )
    finished_move_values['location_final_id'] = self.location_final_id.id
    moves.append(finished_move_values)
    # Byproduct moves — qty is proportional to MO qty
    for byproduct in production.bom_id.byproduct_ids:
        if byproduct._skip_byproduct_line(...):
            continue
        product_uom_factor = production.product_uom_id._compute_quantity(
            production.product_qty, production.bom_id.product_uom_id
        )
        qty = byproduct.product_qty * (product_uom_factor / production.bom_id.product_qty)
        moves.append(production._get_move_finished_values(
            byproduct.product_id.id, qty, byproduct.product_uom_id.id,
            byproduct.operation_id.id, byproduct.id, byproduct.cost_share
        ))
    return moves
```

**`_create_update_move_finished`** reconciles the values list against existing `move_finished_ids`:
- Existing main product move: `Command.update`
- Existing byproduct move (matched by `byproduct_id`): `Command.update`
- New byproduct (no existing record): `Command.create`

### Production State Computation — `_compute_production_ids`

Called on `product.product` and `product.template` to return all non-cancelled/done productions for a product. Used by:
- `stock.quant` to compute `production_id` for consumed quants
- The "Moves" smart button on the product form
- MRP kanban to group by product

### Production Group Linking

`production_group_id` (`mrp.production.group`) is created on MO creation and shared with all child `stock.move` records. This enables:
- Stock move traceability to the parent MO chain
- Backorder grouping
- Cross-MO cancellation propagation when `propagate_cancel=True`

Override `_get_production_group()` to provide custom group creation logic.

---

## Scrap Mechanism (L4)

MRP extends `stock.scrap` with manufacturing-specific fields and behavior.

### MRP Scrap Fields

| Field | Type | Description |
|-------|------|-------------|
| `production_id` | Many2one `mrp.production` | Source MO. `location_id` = `location_src_id` if MO not done, else `location_dest_id` |
| `workorder_id` | Many2one `mrp.workorder` | Source WO (informational — does not restrict quant selection) |
| `bom_id` | Many2one `mrp.bom` | Kit BOM when `product_is_kit=True`. Domain restricted to `type='phantom'` |
| `product_is_kit` | Boolean | Related from `product_id.is_kits` |
| `product_template` | Many2one | Related from `product_id.product_tmpl_id` |

### Scrap Location Resolution (`_compute_location_id` L4)

```
if production_id and state != 'done':
    location_id = production_id.location_src_id       # Components location
elif production_id and state == 'done':
    location_id = production_id.location_dest_id       # Finished goods location
elif workorder_id:
    location_id = workorder_id.production_id.location_src_id
else:
    → falls back to standard stock.scrap logic (warehouse scrap location)
```

### Scrap Move Creation (`_prepare_move_values` L4)

```python
def _prepare_move_values(self):
    vals = super()._prepare_move_values()
    if self.production_id:
        vals['origin'] = vals['origin'] or self.production_id.name
        if self.product_id in self.production_id.move_finished_ids.mapped('product_id'):
            # Scrap of finished/byproduct product → links to production_id
            vals.update({'production_id': self.production_id.id})
        else:
            # Scrap of raw component → links to raw_material_production_id
            vals.update({'raw_material_production_id': self.production_id.id})
    return vals
```

### Kit Product Scrap (L4)

When `product_is_kit=True`, the scrap form shows a `bom_id` selector (filtered to phantom BOMs). `_compute_scrap_qty` delegates to `_compute_kit_quantities` to compute how many kit units the scrap quantity represents. The `do_replenish()` method propagates `production_group_id` from the MO to the scrap's procurement.

### Serial Number Warning

When a serial-tracked product is scraped with a lot_id during an active MO, `_onchange_serial_number()` calls `stock.quant._check_serial_number()` to verify the serial number is in the correct location. If not, it warns the user and may suggest moving to the production location.

---

## Failure Modes (L4)

### Insufficient Component Quantity

**Symptom:** MO stuck in `confirmed` state, `reservation_state='confirmed'`, `components_availability_state` is `'late'` or `'unavailable'`.

**Root cause chain:**
1. `stock.move._action_confirm()` calls `_trigger_scheduler()` for moves with `forecast_availability < 0`
2. The scheduler creates `stock.move` procurements for missing components via `stock.rule`
3. If no procurement rule exists and no stock is available, the MO waits indefinitely

**Reservation state behavior:**
| State | Meaning | Resolution |
|-------|---------|-----------|
| `confirmed` | Components not reserved | Manual `action_assign()` or force reservation |
| `waiting` | Reserved but waiting for upstream moves | Complete the upstream MO/picking first |
| `assigned` | All components available | WO can start |

**`ready_to_produce='asap'` L4:** When BOM has `ready_to_produce='asap'`, only the **first operation's** component moves need to be reserved — later-operation components can be procured in parallel.

### MO Quantity Change — UoM Rounding Edge Case

**Symptom:** `_update_raw_moves(factor)` round-UP behavior causes component quantities to exceed the new MO quantity when reducing.

**Root cause:** `move.product_uom.round(old_qty * factor, rounding_method='UP')` never decreases quantities for small reductions. For unit-based UoMs, reducing from 10 to 9 may leave move quantities unchanged.

**Fix:** Manually delete excess component moves after reducing MO qty.

### Workcenter Overloaded / No Slot Available

**Symptom:** `button_plan()` raises `UserError: "No available slot found for work order..."`.

**Scheduling algorithm:**
```python
def _get_first_available_slot(start_datetime, duration):
    # 1. max_planning_iterations from ir.config_parameter (default 50)
    # 2. Each iteration: 14-day window (50 × 14 = 700 days max search)
    # 3. Get resource_calendar working intervals (respects leaves)
    # 4. Subtract existing WO calendar leaves (type='other')
    # 5. Use Intervals for gap detection
    # 6. Return (start, end) or (False, error_message)
```

**Resolution paths:**
| Path | Action |
|------|--------|
| Split MO | `mrp.production.split` wizard divides into smaller batches |
| Extend calendar | Add shifts/hours to `resource.calendar` for the workcenter |
| Add alternatives | Assign alternative workcenters to the routing operation |
| Bypass | `button_start()` skips slot check entirely — WO starts immediately |

### Phantom Kit Nested Explosion

**Symptom:** Phantom kit move stays in `assigned` state without exploding sub-components.

**Root cause:** Nested phantom BOMs explode one level at `_action_confirm()` time and the remainder at `_action_done()` time. If an intermediate BOM is archived or deleted, the explosion halts.

**Behavior:** A 3-level phantom kit (A→B→C→components) explodes: A at MO confirm, B at MO confirm (after A explosion), C at MO done. The kit move is fully resolved by the time the MO is closed.

### MO Cancellation Edge Cases

**Flexible consumption auto-done:** When `consumption='flexible'` and all raw moves are `done/cancel` but user calls `action_cancel()`, the MO is auto-set to `done`. This prevents an orphaned `progress` state.

**Propagate cancel:** When `propagate_cancel=True`, cancelling a move triggers cancellation of downstream moves. Critical for subcontracting where component moves feed the subcontractor's receipt.

**Child MOs:** Cancelling a parent MO logs a `mail.activity` on child MOs in the same `production_group_id`, requesting their cancellation.

### Byproduct Cost Share > 100%

**Symptom:** `ValidationError` when saving or closing the MO.

**Constraint:** `_check_byproducts()` on `mrp.production` validates total `cost_share` across all applicable variant byproducts does not exceed 100%. This is checked at MO save, confirmation, and during `_cal_price()`.

**Effect:** If total `cost_share = 100%`, the finished product's `price_unit = 0` (all cost allocated to byproducts). If `> 100%`, the valuation formula produces a negative price unit which fails.



#### 6. mrp.workorder — Work Order

**File:** `models/mrp_workorder.py`
**Order:** `sequence, leave_id, date_start, id`

##### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Work order name (defaults to operation.name) |
| `sequence` | Integer | From operation_id or `100`. Used for non-dependent WO ordering |
| `barcode` | Char | Computed: `{production_id.name}/{id}` for mobile scanning |
| `production_id` | Many2one `mrp.production` | Parent MO (required, readonly after create) |
| `workcenter_id` | Many2one `mrp.workcenter` | Assigned work center (required) |
| `operation_id` | Many2one `mrp.routing.workcenter` | Source routing operation. Can be null for manually added WOs |
| `state` | Selection | `'blocked'`, `'ready'`, `'progress'`, `'done'`, `'cancel'`. **Store-computed** |
| `qty_producing` | Float | Related from `production_id.qty_producing` |
| `qty_produced` | Float | Accumulated quantity done on this WO |
| `qty_remaining` | Float | `product_qty - qty_reported_from_previous_wo - qty_produced` |
| `qty_ready` | Float | `qty_remaining` minus blocked predecessor quantities |
| `qty_reported_from_previous_wo` | Float | Carried quantity from prior WO in a backorder chain |
| `date_start` | Datetime | Planned start (compute/inverse via `leave_id`) |
| `date_finished` | Datetime | Planned end (compute/inverse via `leave_id`) |
| `leave_id` | Many2one `resource.calendar.leaves` | Calendar booking record. Created by `_plan_workorder`, deleted on cancel/unplan |
| `duration_expected` | Float | Expected duration in minutes (recomputed when qty changes) |
| `duration` | Float | Actual duration from time_ids (inverse settable via `_set_duration`) |
| `duration_unit` | Float | `duration / max(qty_produced, 1)` — minutes per unit |
| `duration_percent` | Integer | `(duration_expected - duration) / duration_expected × 100` — positive = faster than expected |
| `progress` | Float | `duration × 100 / duration_expected` (%) |
| `move_raw_ids` | One2many `stock.move` | Component moves consumed during this operation |
| `move_finished_ids` | One2many `stock.move` | Finished product moves produced during this operation |
| `move_line_ids` | One2many `stock.move.line` | Move lines requiring lot scanning at this WO |
| `time_ids` | One2many `mrp.workcenter.productivity` | Time tracking entries |
| `is_user_working` | Boolean | `True` if current user has an open (no `date_end`) productive time log |
| `working_user_ids` | One2many `res.users` | All users currently working (open time logs) |
| `last_working_user_id` | Many2one `res.users` | Most recent worker |
| `costs_hour` | Float | Workcenter cost captured at WO finish time (for cost consistency) |
| `cost_mode` | Selection | `'actual'` (tracked) or `'estimated'` (theoretical) |
| `scrap_ids` / `scrap_count` | One2many / Integer | Scrap from this specific WO |
| `blocked_by_workorder_ids` | Many2many | Predecessor WOs that must complete before this can start |
| `needed_by_workorder_ids` | Many2many | Inverse — WOs blocked by this one |
| `production_date` | Datetime | `date_start` or fallback to `production_id.date_start` |
| `is_planned` | Boolean | Related from `production_id` |
| `production_availability` | Selection | Related from MO (for Kanban grouping) |
| `production_state` | Selection | Related from MO (readonly) |

##### Work Order State Computation (L4)

```
blocked_by_workorder_ids.qty_ready calculation:
  qty_ready = qty_remaining
  For each non-cancelled predecessor WO:
      qty_ready = min(qty_ready, predecessor.qty_produced + predecessor.qty_reported_from_previous_wo)
  qty_ready -= qty_produced + qty_reported_from_previous_wo

state = 'blocked' if qty_ready == 0 (nothing to process) else 'ready'
       (overridden to 'progress'/'done'/'cancel' by explicit actions)
```

**L4 `blocked` vs `ready`:** `blocked` means the WO cannot start yet (no available qty). The MO must have `qty_producing > 0` or another WO must have produced some quantity. This is distinct from WO scheduling conflicts (shown via `json_popover`).

##### Key Methods

```python
def _plan_workorder(self, replan=False):
    """
    L3: Finds the first available time slot on the workcenter (or alternatives).
        Respects predecessor WO `date_finished` (blocked_by chain).
        Creates a resource.calendar.leaves record for the slot.
    L4: Searches up to 700 days ahead (50 iterations × 14-day chunks).
        Raises UserError if no slot available.
        If the preferred workcenter is busy, tries alternatives.
    """

def button_start(raise_on_invalid_state=False):
    """
    L3: Starts the WO:
        - Checks workcenter is not blocked (raises UserError if blocked)
        - Sets qty_producing = qty_remaining if 0
        - Creates mrp.workcenter.productivity record (starts timer)
        - Transitions MO to 'progress' if still 'confirmed'
        - Creates leave_id if not yet planned
    L4: Prevents duplicate timers for the same user (raises UserError).
        Does not auto-capture component lot on start (done in produce wizard).
    """

def button_finish():
    """
    L3: Finishes the WO:
        - Auto-sets picked=True on unpicked raw/byproduct moves (uses unit_factor × qty_producing)
        - Calls end_all() → closes all open time logs
        - Sets qty_produced, state='done', captures workcenter costs_hour
    L4: Batches writes with identical vals to reduce ORM calls.
        If actual duration > expected: splits the final time log into productive + performance loss.
    """

def _get_duration_expected(self, alternative_workcenter=False, ratio=1):
    """
    L3: Computes expected duration based on workcenter capacity and operation.
        Uses operation.time_cycle if linked, else manual calculation.
    L4: For quantity changes mid-production:
        - If qty_producing differs from origin: adjusts cycle count proportionally
        - time_efficiency factor: 100% efficiency → actual=expected
        - alternative_workcenter path: recalculates using alternative WC's capacity/time_start/time_stop
    """

def _set_duration():
    """
    L3: Allows manual duration override on the WO form.
        If increased: creates additional time log entries (or extends last entry)
        If decreased: removes time from the most recent entries
    L4: Correctly handles partial performance loss entries when reducing duration
        below expected (splits productive vs. performance time logs).
    """
```

---

#### 7. mrp.workcenter — Work Center

**File:** `models/mrp_workcenter.py`
**Inherits:** `mail.thread`, `resource.mixin`
**Order:** `sequence, id`

##### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Related from `resource_id.name` (synced). Workcenter display name |
| `code` | Char | Short code for barcode/planning |
| `note` | Html | Work center description |
| `sequence` | Integer | `1` default — ordering in lists |
| `color` | Integer | Color index for kanban/views |
| `costs_hour` | Float | Hourly cost used in WO cost calculation: `duration × costs_hour / 60` |
| `time_start` | Float | Setup time in **minutes** (used in routing `time_total`) |
| `time_stop` | Float | Cleanup time in **minutes** |
| `time_efficiency` | Float | Related from `resource_id.time_efficiency`. Default `100`%. >100% means faster than standard |
| `working_state` | Selection | `'normal'`, `'blocked'`, `'done'`. Computed from open `mrp.workcenter.productivity` records |
| `resource_calendar_id` | Many2one `resource.calendar` | Working hours definition (required for scheduling). Unset = 24/7 calendar |
| `alternative_workcenter_ids` | Many2many `mrp.workcenter` | Substitution options. **Cannot include self** (enforced by `_check_alternative_workcenter`) |
| `routing_line_ids` | One2many `mrp.routing.workcenter` | Operations defined for this WC |
| `order_ids` | One2many `mrp.workorder` | All work orders assigned to this WC |
| `capacity_ids` | One2many `mrp.workcenter.capacity` | Product-specific capacities (overrides default capacity of 1) |
| `tag_ids` | Many2many `mrp.workcenter.tag` | Color-coded grouping tags |
| `blocked_time` | Float | **Last 30 days**: hours spent in non-productive, non-performance states |
| `productive_time` | Float | **Last 30 days**: hours of productive time logs |
| `oee` | Float | `productive_time × 100 / (productive_time + blocked_time)` — percentage |
| `oee_target` | Float | Default `90`% — target OEE |
| `performance` | Integer | `100 × duration_expected / duration` for last 30d done WOs |
| `workorder_count` | Integer | All non-done/cancel WOs |
| `workorder_ready_count` | Integer | WOs in `ready` state |
| `workorder_progress_count` | Integer | WOs in `progress` state |
| `workorder_blocked_count` | Integer | WOs in `blocked` state |
| `workorder_late_count` | Integer | WOs in `blocked`/`ready` with `date_start < now` |
| `workcenter_load` | Float | Sum of `duration_expected` for pending/progress WOs |
| `kanban_dashboard_graph` | Text | JSON chart data for kanban card |
| `has_routing_lines` | Boolean | Whether any BOM references this WC |

##### Scheduling Algorithm (L4)

`_get_first_available_slot(start_datetime, duration)`:
1. Gets `max_planning_iterations` from `ir.config_parameter` (default `50`)
2. Searches in 14-day windows, up to 700 days ahead
3. For each window: gets working intervals from `resource_calendar_id` (respects leaves)
4. Intersects with existing work order intervals (from `resource.calendar.leaves` with `time_type='other'`)
5. Uses `Intervals` class for efficient interval arithmetic
6. Returns `(start_datetime, end_datetime)` tuple or `(False, 'error_message')`

**L4 Alternative Workcenter Fallback:** `button_plan` calls `workcenter._get_first_available_slot()` for each alternative in sequence. The first slot found wins. If no slot found in 700 days, raises `UserError`.

##### Work Center Block/Unblock (L3-L4)

```python
def unblock():
    """ Closes all open mrp.workcenter.productivity logs for this WC with date_end=now.
        working_state → 'normal'. """

mrp.workcenter.productivity.button_block():
    """ Calls workcenter_id.order_ids.end_all() — closes all open timers site-wide. """
```

---

#### 8. mrp.unbuild — Unbuild Order

**File:** `models/mrp_unbuild.py`
**Inherits:** `mail.thread`, `mail.activity.mixin`
**Order:** `id desc`

##### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Auto-generated from `mrp.unbuild` sequence |
| `product_id` | Many2one `product.product` | Product to disassemble. Computed from `mo_id` if linked |
| `product_qty` | Float | Quantity to unbuild. Computed from `mo_id.qty_produced` if linked |
| `product_uom_id` | Many2one `uom.uom` | From MO if linked, else from product |
| `bom_id` | Many2one `mrp.bom` | Resolved from MO or via `_bom_find`. Only `type='normal'` allowed |
| `mo_id` | Many2one `mrp.production` | Source MO. **Must be in `'done'` state**. Not required (manual unbuild allowed) |
| `mo_bom_id` | Many2one | Related: `mo_id.bom_id` |
| `lot_id` | Many2one `stock.lot` | Lot/serial of product being unbuilt. Required if product is tracked |
| `lot_producing_ids` | Many2many | Related from `mo_id` — available lots to select |
| `has_tracking` | Selection | Related from product (none/lot/serial) |
| `location_id` | Many2one `stock.location` | Source location (where finished product is). Defaults to warehouse `lot_stock_id` |
| `location_dest_id` | Many2one `stock.location` | Destination for components. Defaults to warehouse `lot_stock_id` |
| `consume_line_ids` | One2many `stock.move` | Moves consuming the finished product |
| `produce_line_ids` | One2many `stock.move` | Moves producing the components |
| `state` | Selection | `'draft'` → `'done'` |

##### Unbuild Flow (L3)

```
action_validate() → if stock available:
    action_unbuild() → generates consume + produce moves → _action_confirm() → _action_done()
                         └─ creates stock.move.line for lot-tracked products
                            └─ links consume_line to produce_line via produce_line_ids
                                └─ posts consume move (reduces finished product stock)
                                └─ posts produce moves (increases component stock)
                                └─ posts consume_unbuild moves (for finished product itself)
    └─ writes state='done'
```

**With `mo_id`:** `_generate_consume_moves()` uses `mo_id.move_finished_ids` (done moves) with a factor of `unbuild_qty / mo_id.qty_produced`. `_generate_produce_moves()` uses `mo_id.move_raw_ids` (done moves) similarly.

**Without `mo_id`:** `_generate_consume_moves()` creates a single move for the finished product. `_generate_produce_moves()` calls `bom_id.explode()` to flatten the BOM and create component moves.

**L4 Lot Tracing:** If the finished product is lot/serial tracked, `lot_id` is required. For serial-tracked products, `product_qty` is forced to `1`. When multiple unbuilds exist for the same MO with lot tracking, `previously_unbuilt_lots` is tracked to avoid double-recovering serial numbers.

**L4 Constraint:** `mo_id` must be in `'done'` state (strict — raises `UserError` if not done). Unbuild of cancelled/in-progress MOs is not allowed.

---

#### 9. mrp.production.group — Production Group

Groups related manufacturing orders (backorders, subcontracted chains, multi-level MO hierarchies).

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Required, indexed. Typically mirrors the first MO's `name` |
| `production_ids` | One2many `mrp.production` | All MOs in this group |
| `child_ids` / `parent_ids` | Many2many `mrp.production.group` | Hierarchical groups (self-referential via `mrp_production_group_rel`) |

**L3 Use:** `stock.rule._make_mo_get_domain()` searches for existing draft/confirmed MOs to merge with the same `bom_id`, `product_id`, picking_type, `company_id`, `user_id=False`, and `reference_ids` — enabling automatic MO merging when the same procurement is triggered multiple times.

---

### Supporting Models

#### 10. mrp.workcenter.productivity — Time Tracking Log

**File:** `models/mrp_workcenter.py`

Records time spent on work orders. Each record represents a contiguous time block.

| Field | Type | Description |
|-------|------|-------------|
| `workcenter_id` | Many2one | Required |
| `workorder_id` | Many2one | Optional — links to specific WO |
| `production_id` | Many2one | Related from `workorder_id.production_id` (readonly) |
| `user_id` | Many2one | User performing the work. Default: current user |
| `loss_id` | Many2one `mrp.workcenter.productivity.loss` | **Required**. Determines `loss_type` |
| `description` | Text | Optional free-text note |
| `date_start` | Datetime | Required, default `now` |
| `date_end` | Datetime | Set when timer is closed |
| `duration` | Float | Computed: `(date_end - date_start)` converted via `_convert_to_duration()` |

**`loss_type` categories (from `loss_id`):**
- `'availability'`: Downtime (breakdown, changeover, material wait)
- `'performance'`: Running slower than standard (reduced speed)
- `'quality'`: Defects/rework time
- `'productive'`: Actual value-adding work

**`_convert_to_duration` L4:** If `loss_type` is `'availability'` or `'quality'` **and** the workcenter has a `resource_calendar_id`, duration is computed based on **working hours** (not wall-clock time). This means a 2-hour breakdown during a 4-hour shift equals 2 hours of blocked time, not 2 hours of calendar time. `productive` and `performance` always use wall-clock time.

**`_close()` L4 — Performance Loss Split:** When a timer with `date_end` is closed and `wo.duration > wo.duration_expected`, the system:
1. Calculates `productive_date_end = date_end - (duration - expected)`
2. If `productive_date_end <= date_start`: entire block is `performance` loss
3. Otherwise: splits into `productive` + `performance` records

---

#### 11. mrp.workcenter.productivity.loss — Loss Reason

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Reason name (e.g., "Machine Breakdown", "Lack of Material"). Translateable |
| `loss_type` | Selection | `'availability'`, `'performance'`, `'quality'`, `'productive'` |
| `loss_id` | Many2one `mrp.workcenter.productivity.loss.type` | Groups availability and quality losses |
| `manual` | Boolean | `True` = user-created; `False` = system-defined |

**Odoo ships with predefined losses:**
- `mrp.block_reason4` = Performance loss type
- `mrp.block_reason7` = Productive (base rate)
These are used by `_loss_type_change()` to auto-classify when duration exceeds expected.

---

#### 12. mrp.workcenter.productivity.loss.type — Loss Type Category

Groups loss reasons into the four OEE categories.

---

#### 13. mrp.workcenter.capacity — Product-Specific Capacity

Allows different cycle capacity per product at a work center.

| Field | Type | Description |
|-------|------|-------------|
| `workcenter_id` | Many2one | Parent work center |
| `product_id` | Many2one | Specific product (optional — if unset, this is the default capacity) |
| `product_uom_id` | Many2one | Unit for the capacity value (auto-set from product) |
| `capacity` | Float | Number of units producible **in parallel** per cycle for this product |
| `time_start` | Float | Setup time specific to this product (defaults from workcenter) |
| `time_stop` | Float | Cleanup time specific to this product (defaults from workcenter) |

**Unique constraint:** `(workcenter_id, COALESCE(product_id, 0), product_uom_id)` — only one capacity record per product/UoM combination.

**L4 capacity resolution in `_get_capacity()`:**
1. Exact product + exact UoM match
2. No product + exact UoM match
3. No product + product's base UoM match
4. Fall back to default capacity of `1` with workcenter's time_start/time_stop

---

#### 14. mrp.workcenter.tag — Work Center Tags

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Unique tag name |
| `color` | Integer | Randomly assigned (1–11) on create. Unique constraint on `name` |

---

### Stock Integration Models

#### 15. stock.move (Extended by MRP)

**File:** `models/stock_move.py`

| MRP-Added Field | Type | Description |
|----------------|------|-------------|
| `production_id` | Many2one | Set on finished product / byproduct moves (created by MO) |
| `raw_material_production_id` | Many2one | Set on component moves (consumed by MO) |
| `created_production_id` | Many2one | Set on the MO's *finished product* move (points back to creating MO) |
| `operation_id` | Many2one | Routing operation during which this component is consumed |
| `workorder_id` | Many2one | Specific work order consuming this component |
| `bom_line_id` | Many2one | Source BOM line (determines `manual_consumption`, unit_factor) |
| `byproduct_id` | Many2one | Source `mrp.bom.byproduct` if this is a byproduct move |
| `unbuild_id` | Many2one | Set on component moves generated by unbuild |
| `consume_unbuild_id` | Many2one | Set on finished product move consumed by unbuild |
| `unit_factor` | Float | `product_uom_qty / (mo.product_qty - mo.qty_produced)` — qty per finished unit |
| `should_consume_qty` | Float | `(qty_producing - qty_produced) × unit_factor` — expected to consume |
| `manual_consumption` | Boolean | True = user manually registers consumption; False = auto-computed |
| `cost_share` | Float | Percentage of final product cost for byproducts |

**Key Overrides (L3-L4):**

```python
def _compute_location_id():
    # For production_id moves: location_id = property_stock_production
    # For raw_material_production_id moves: location_id = production.location_src_id
    # Falls back to parent _compute_location_id() otherwise

def _action_confirm():
    # Calls action_explode() first for phantom kits, then parent's _action_confirm()
    # This means phantom kit procurement never reaches MO creation

def _action_done():
    # Re-explodes any remaining kit moves that weren't exploded during confirmation
    # (handles the edge case where a kit's sub-component MO wasn't yet done)

def _should_bypass_reservation():
    # Returns True for kit products (phantom BOMs) — they avoid reservation completely

def _action_cancel():
    # Adds auto-cancel logic: if all raw_material_production_id moves are cancelled,
    # the parent MO is also cancelled (unless 'skip_mo_check' in context)
```

**`manual_consumption` determination (L4):**
```python
def _is_manual_consumption(self):
    return self._determine_is_manual_consumption(self.bom_line_id)

@api.model
def _determine_is_manual_consumption(bom_line):
    return bool(bom_line and bom_line.operation_id)
    # True if component is tied to an operation → user must register manually
    # False if no operation → auto-consumed when WO starts
```

**`action_explode()` for Phantom Kits (L3):**
- Called from `_action_confirm()`
- For each kit move: finds phantom BOM via `_bom_find(product, bom_type='phantom')`
- Computes factor: `move.product_uom_qty / bom.product_qty`
- Calls `bom.explode()` to flatten
- Creates phantom sub-moves with `bom_line_id` populated
- Deletes the original kit move (sets `quantity=0`, cancels, then `unlink()`)

**Merge Rules (`_prepare_merge_moves_distinct_fields`):** Phantom BOM moves merge on `bom_line_id` additionally. Negative moves never merge across different `created_production_id`.

---

#### 16. stock.rule — Manufacturing Procurement Rule

**File:** `models/stock_rule.py`
**Action:** `'manufacture'` (selection_add)

```python
def _run_manufacture(procurements):
    """
    L3: Main entry point for MRP-triggered procurement.
        For each procurement:
          1. Finds matching BOM via _get_matching_bom()
          2. Searches for existing draft/confirmed MO to merge (unless batch_size enabled)
          3. If found: increases MO qty via change_production_qty
          4. If not found or batch_size: creates new MO(s)
             - batch_size loop: creates one MO per batch until procurement_qty exhausted
          5. Auto-confirms if _should_auto_confirm_procurement_mo()
          6. Calls _post_run_manufacture() with original procurements
    L4: Runs as SUPERUSER (bypasses ACL for MTO scenarios where normal user lacks perms).
    """
```

**BOM Matching Priority (L3):**
1. `values['bom_id']` — explicitly passed (e.g., from orderpoint)
2. `values['orderpoint_id'].bom_id` — from reorder rule
3. `bom._bom_find(product, picking_type=self.picking_type_id)` — picking-type-matched BOM
4. `bom._bom_find(product)` — fallback (ignores picking_type)

**Batch Size Splitting (L4):** When `bom.enable_batch_size=True`, `_run_manufacture` creates one MO per batch:
```python
while procurement_qty > 0:
    batch_qty = bom.product_uom._compute_quantity(bom.batch_size, procurement.product_uom)
    create MO with product_qty = batch_qty
    procurement_qty -= batch_qty
```

**Lead Time Integration (L3):**
```python
def _get_lead_days(product, bom, **values):
    total_delay += bom.produce_delay          # Manufacturing lead time
    total_delay += bom.days_to_prepare_mo     # Pre-production days
    # For non-one-step manufacturing: adds PBM route delays
```

---

#### 17. stock.warehouse (Extended by MRP)

**File:** `models/stock_warehouse.py`

| Field | Type | Description |
|-------|------|-------------|
| `manufacture_to_resupply` | Boolean | Toggle controlling whether this warehouse is assigned to the global manufacture route |
| `manufacture_pull_id` | Many2one `stock.rule` | The main manufacture procurement rule |
| `manufacture_mto_pull_id` | Many2one `stock.rule` | MTO-specific manufacture rule |
| `pbm_mto_pull_id` | Many2one `stock.rule` | PBM MTO pull rule |
| `sam_rule_id` | Many2one `stock.rule` | SAM push rule |
| `manu_type_id` | Many2one `stock.picking.type` | Manufacturing operation type for this warehouse |
| `pbm_type_id` | Many2one | Operation type for picking before manufacturing |
| `sam_type_id` | Many2one | Operation type for store after manufacturing |
| `manufacture_steps` | Selection | `'mrp_one_step'`, `'pbm'`, `'pbm_sam'` |
| `pbm_route_id` | Many2one `stock.route` | PBM route (deleted on uninstall_hook) |
| `pbm_loc_id` / `sam_loc_id` | Many2one `stock.location` | Intermediate locations for 2-step/3-step manufacturing |

**Manufacturing Steps:**

| Step | Components Flow | Finished Product | Use Case |
|------|----------------|-----------------|----------|
| `mrp_one_step` | MO consumes from `location_src_id` directly | MO produces to `location_dest_id` directly | Simple, fast |
| `pbm` (2-step) | Pick `→ PBM location` → MO consumes from PBM | MO produces to `location_dest_id` | Component picking before production |
| `pbm_sam` (3-step) | Pick `→ PBM location` → MO consumes from PBM | MO produces to `SAM location` → Store pick `→ stock` | Full warehouse control |

**L4:** `manufacture_steps != 'mrp_one_step'` triggers extra procurement rules from the PBM location to feed the MO. This adds `'pbm_mto_pull_id'` and `'sam_rule_id'` to the warehouse rules dictionary returned by `get_rules_dict()`.

---

#### 18. product.product / product.template (Extended by MRP)

**File:** `models/product.py`

| Extended Field | Model | Description |
|---------------|-------|-------------|
| `bom_ids` / `variant_bom_ids` | product.template / product.product | BOMs where this product is the finished product |
| `bom_line_ids` | both | BOM lines where this product is a component |
| `bom_count` | both | Count of BOMs (finished or as byproduct) |
| `used_in_bom_count` | both | Count of BOMs using this product as a component |
| `mrp_product_qty` | both | Total manufactured quantity (done MOs, last 365 days) |
| `is_kits` | both | `True` if product has a `type='phantom'` BOM |

**Kit Quantity Computation (`_compute_quantities_dict` L4):**
For phantom BOM products, the system:
1. Explodes the kit BOM to get all components and their ratios
2. Computes `qty_per_kit = sum(component_qty / component_uom_qty)` across all components
3. For each stock field (`virtual_available`, `qty_available`, etc.):
   `kit_qty = floor(component_available / qty_per_kit) × bom.product_qty`
4. Returns the **minimum** across all components (the bottleneck principle)

**L4 Performance:** Component quantities are prefetched in a single pass. The `mrp_compute_quantities` context key avoids redundant re-computation when called recursively.

**Action Archive Warning:** Archiving a product that is referenced in an **active** BOM line raises a non-blocking warning notification. The archive still proceeds but warns the user.

---

## Key Features

### Bill of Materials (BOM)

**Two BOM Types:**
- `'normal'`: Standard manufacturing BOM — creates `mrp.production` when triggered
- `'phantom'`: Kit BOM — resolved in the procurement chain as component substitutes, never creates an MO

**Multi-Level BOMs:** Sub-BOMs are recursively exploded. Sub-BOM lines with `child_bom_id.type='phantom'` are exploded inline; non-phantom sub-BOMs are included as sub-assemblies with their own workorders.

**By-products:** Secondary products with `cost_share` for cost allocation. Cannot exceed 100% total cost share. Cannot be the same as the main BOM product.

**Variant Support:** `bom_product_template_attribute_value_ids` on lines/operations/byproducts specifies which variants activate that element. Uses `no_variant` vs `always/dynamic` attribute matching.

**Flexible Consumption:**
- `'flexible'`: Any qty consumed is accepted
- `'warning'`: Wizard on MO close shows discrepancy
- `'strict'`: Manager required to close with discrepancy

**Batch Size:** When `enable_batch_size=True`, all auto-generated MOs are created in that quantity (split from a single procurement trigger).

### Production Order Workflow

```
Draft → Confirmed → In Progress → To Close → Done
   │               │
   └──► Cancel   ──┴──► Cancel
```

**`action_confirm()` triggers:**
- Procurement method adjustment on raw moves
- Move confirmation (creates reservations)
- Work order creation and linking
- Component availability scheduler
- Associated picking confirmation

**`button_plan()` triggers:**
- Work order scheduling via `resource.calendar`
- MO `date_start`/`date_finished` sync from WO dates
- Alternative workcenter fallback

**`action_generate_bom()`:** Creates a new BOM from the MO's current components, byproducts, and operations. Auto-links back to the MO via `parent_production_id` context.

### Manufacturing Steps (Warehouse Configuration)

| Step | Flow | `reservation_state` when |
|------|------|------------------------|
| `mrp_one_step` | Components from stock → MO → Finished to stock | `'assigned'` when all reserved |
| `pbm` | Pick components → PBM location → MO → Finished to stock | `'assigned'` when PBM pick assigned |
| `pbm_sam` | Pick → PBM → MO → SAM → Store to stock | `'assigned'` when SAM has the product |

### Backorder Mechanism

When a MO is partially produced and the user requests a backorder:
1. Original MO `qty_produced` updated
2. Backorder MO created with `backorder_sequence = original.backorder_sequence + 1`
3. Both share `production_group_id`
4. `reference_ids` shared across the group
5. Backorder WOs that overlap with done WOs are not duplicated

### Work Orders

**Key Functionality:**
- Linked to work centers with capacity planning
- Time tracking via `mrp.workcenter.productivity` records
- WO dependencies via `blocked_by_workorder_ids` / `needed_by_workorder_ids`
- Scheduling based on `resource.calendar` (or 24/7 if none)
- Barcode support via `barcode = {MO.name}/{WO.id}`
- Lot/serial capture at WO level (`finished_lot_ids`)

**Duration Calculation:**
```python
duration_expected = time_start
                 + ceil(qty / capacity) × time_cycle × 100 / time_efficiency
                 + time_stop
```

**L4 WO State → MO State Interaction:**
- First WO started → MO becomes `'progress'`
- All WOs done/cancel → MO becomes `'to_close'`
- If no WOs exist and `qty_producing >= product_qty` → MO becomes `'to_close'`

### Unbuild (Disassembly)

Reverse of production:
- Consumes the finished product from stock (via `consume_unbuild_id` moves)
- Produces components back to stock (via `unbuild_id` moves)
- Links to source MO (if provided) for full traceability
- State: `draft` → `done`

---

## Lead Times (L3-L4)

| Field | Scope | Used By | Notes |
|-------|-------|--------|-------|
| `produce_delay` | `mrp.bom` | `stock.rule._get_lead_days`, `_get_date_planned`, MO scheduling | In days; for subcontracting, drives when to ship components |
| `days_to_prepare_mo` | `mrp.bom` | `stock.rule._get_lead_days` (cumulative delay) | Added to `total_delay` as `'Days to Supply Components'` |
| Multi-level BOM | `mrp.bom` | `stock.rule._get_lead_days` | Odoo 19 adds all sub-BOM `produce_delay` values cumulatively |
| `stock.rule` delays | `stock.rule` | `_get_lead_days` | Security lead time, supplier lead time (purchase rules) |

**Scheduling formula:**
```
date_start = date_deadline - produce_delay
           - (sum of all workorder durations in minutes, converted to days)
           - days_to_prepare_mo
```

---

## OEE — Overall Equipment Effectiveness (L3)

OEE = `productive_time × 100 / (productive_time + blocked_time)` — computed over the last 30 days.

**OEE Components:**
- **Availability** = `(planned_time - blocked_time) / planned_time` — portion not blocked
- **Performance** = `duration_expected / duration` — actual vs theoretical speed
- **Quality** = tracked via `quality` loss type in time logs
- **OEE** = Availability × Performance × Quality (simplified to productive/blocked ratio here)

---

## Wizards

### Key Wizards

| Wizard | Purpose | Key Action |
|--------|---------|-----------|
| `change_production.qty` | Modify MO quantity after confirmation | Recomputes raw move qty via `_update_raw_moves(factor)` |
| `mrp.production.backorder` | Create backorder on partial MO close | Splits moves, creates backorder MO |
| `mrp.consumption.warning` | Show component consumption discrepancy | Allows flexible/warning override or cancel |
| `mrp.production.split` | Split MO into multiple orders | Splits moves and WOs proportionally |
| `mrp.production.serial_numbers` | Assign serial numbers for serial-tracked products | Creates `stock.lot` records, updates `lot_producing_ids` |
| `stock.warn.insufficient.qty.unbuild` | Warn when unbuild qty exceeds stock | Blocks or allows with message |
| `stock.warn.insufficient.qty` | General insufficient stock warning | Used during unbuild validation |
| `stock.replenishment.info` | Show replenishment details for components | Displays lead times, stock levels |

---

## Security (L4)

### MRP Security Groups

MRP defines seven security groups with explicit inheritance hierarchy:

| Group ID | Name | Implied Groups | Notes |
|----------|------|---------------|-------|
| `mrp.group_mrp_user` | User | `stock.group_stock_user` | Base MRP permissions |
| `mrp.group_mrp_manager` | Administrator | `group_mrp_user` (plus `base.user_admin`, `base.user_root`) | Full access |
| `mrp.group_mrp_routings` | Manage Work Order Operations | (none) | Controls routing management UI |
| `mrp.group_mrp_byproducts` | Produce residual products | (none) | Controls byproduct line visibility |
| `mrp.group_unlocked_by_default` | Unlocked by default | (none) | If active: new MOs are unlocked by default |
| `mrp.group_mrp_reception_report` | Use Reception Report with MOs | (none) | Enables MRP in receipt reports |
| `mrp.group_mrp_workorder_dependencies` | Use Operation Dependencies | (none) | Enables `blocked_by_operation_ids` on routings |

### Access Control Matrix (Exact Permissions from `ir.model.access.csv`)

**Core MRP models:**

| Model | `group_mrp_user` | `group_mrp_manager` | `stock.group_stock_user` |
|-------|-----------------|---------------------|-------------------------|
| `mrp.production` | CRUD | Read | Read |
| `mrp.workorder` | CRUD | CRUD | — |
| `mrp.bom` | Read | CRUD | Read |
| `mrp.bom.line` | Read | CRUD | Read |
| `mrp.bom.byproduct` | Read | CRUD | — |
| `mrp.routing.workcenter` | Read | CRUD | — |
| `mrp.workcenter` | Read | CRUD | — |
| `mrp.workcenter.productivity` | CRUD | CRUD | — |
| `mrp.workcenter.productivity.loss` | Read | CRUD | — |
| `mrp.workcenter.capacity` | Read | CRUD | — |
| `mrp.unbuild` | CRUD | CRUD | — |
| `mrp.production.group` | CRUD | CRUD | — |
| `stock.move` (MRP moves) | CRUD | CRUD | — |

**Wizards:**

| Wizard | `group_mrp_user` | `group_mrp_manager` |
|--------|-----------------|---------------------|
| `change_production.qty` | CRUD | CRUD |
| `mrp.production.backorder` | CRUD | CRUD |
| `mrp.consumption.warning` | CRUD | CRUD |
| `mrp.production.split` | CRUD | CRUD |
| `mrp.production.serial_numbers` | CRUD | CRUD |

**Critical permission note:** `group_mrp_user` has full CRUD on `mrp.production` but only **Read** on `mrp.bom`. This means users can create and execute MOs but cannot edit BOMs without `group_mrp_manager`.

### Record Rules (Multi-Company)

All MRP record rules scope records to the current user's `company_ids`:

| Model | Domain | Global Records |
|-------|--------|----------------|
| `mrp.production` | `company_id in company_ids` | No |
| `mrp.workorder` | `company_id in company_ids` | No |
| `mrp.bom` | `company_id in company_ids + [False]` | **Yes** |
| `mrp.bom.line` | `company_id in company_ids + [False]` | **Yes** |
| `mrp.bom.byproduct` | `company_id in company_ids + [False]` | **Yes** |
| `mrp.routing.workcenter` | `company_id in company_ids + [False]` | **Yes** |
| `mrp.workcenter` | `company_id in company_ids + [False]` | **Yes** |
| `mrp.workcenter.productivity` | `company_id in company_ids` | No |
| `mrp.unbuild` | `company_id in company_ids` | No |

Records with `company_id=False` are **global** and visible to all companies. Production orders and unbuilds are always company-scoped; BOMs and workcenters can be shared as master data.

### MO Locking and Unlocking (L4)

```python
is_locked = fields.Boolean(
    default=lambda self: not self.user_has_groups('mrp.group_unlocked_by_default')
)
```

- **If `group_unlocked_by_default` is active:** New MOs are unlocked — `group_mrp_user` can edit confirmed MOs freely.
- **If inactive (default):** New MOs lock after confirmation — editing is blocked until unlocked.
- **Toggle:** `action_toggle_is_locked()` allows authorized users to lock/unlock at any time.

Locked MOs prevent changes to: `product_qty`, component moves, finished moves, and WO assignments. The lock state is tracked in the chatter log.



## Odoo 18 → 19 Changes (L4)

| Feature | Odoo 18 | Odoo 19 | Impact |
|---------|---------|---------|--------|
| MO Locking | Optional feature | **Locked by default** unless `group_unlocked_by_default` active | Breaking: existing workflows relying on unlocked MOs need migration |
| `days_to_prepare_mo` | New field | Explicit pre-production lead time (cumulative with `produce_delay`) | Supply chain accuracy |
| `production_capacity` | Not present | Computed: `min(available_qty / unit_factor)` across all components | Production planning visibility |
| `is_delayed` | Not present | Computed + searchable: `date_deadline < now` or `date_finished > date_deadline` | Alert system |
| `_compute_state` | Implicit transition logic | Fully explicit store-computed with documented 6-step logic | Debugging, predictability |
| WO state | Based on `reservation_state` | Based on `qty_ready` (component availability per WO) | More granular WO control |
| BOM Archive Cascade | `action_archive()` only archives BOM | Also archives all `operation_ids` (routing operations) | Data integrity on archive |
| Kit Explosion | Single-level `explode()` | Multi-level recursive with per-level batch optimization | Complex kit support |
| `_bom_find` | Always loops over `product_tmpl_id.product_variant_ids` | **Single-product path** avoids inner loop | Performance for common case |
| Lead Time | `produce_delay` only | Added `days_to_prepare_mo` as separate cumulative component | Granular scheduling |
| `pre_init_hook` | Not present | SQL adds `unit_factor` + `manual_consumption` to `stock_move` before ORM migration | Zero-downtime install on large DBs |
| Backorder | MO `name` suffix (e.g., `MO/001-1`) | `backorder_sequence` integer + `production_group_id` | Better backorder grouping |
| Byproduct constraint | Not enforced on MO | `_check_byproducts()` validates `cost_share` total <= 100% at MO save | Data integrity |
| WO Duration | No rounding requirements | `_set_duration()` rounds to 6 decimal places | Precision |
| `blocked_by_workorder_ids` | Optional; defaults to sequential chaining | Respects `allow_operation_dependencies` on BOM | Conditional parallelism |
| Resource calendar | Single calendar per workcenter | `time_efficiency` factor applied to `duration_expected` | Performance variance tracking |
## Cross-Module Integration (L4)

### MRP — Stock

**Core integration via `stock.move`:**
- Component consumption: `stock.move.raw_material_production_id` — the consuming move links back to its MO
- Finished goods production: `stock.move.production_id` — the producing move links to its MO
- Byproduct production: `stock.move.byproduct_id` alongside `production_id`
- Scrap: `stock.scrap.production_id` or `stock.scrap.workorder_id`

**Procurement chain:**
```
stock.rule (action='manufacture')
  → _run_manufacture()
     → creates/merges mrp.production
        → action_confirm()
           → _adjust_procure_method()  # MTS or MTO per move
           → _action_confirm() on moves
              → creates stock.move.line reservations
           → workorder_ids._action_confirm()
              → _link_workorders_and_moves()
```

**Multi-company:** Stock moves generated by MRP inherit `company_id` from the MO. Cross-company component transfers (e.g., subcontracting) use `stock.rule` with appropriate company scoping in the vendor's data.

### MRP — Account (`mrp_account`)

| Stage | Method | Creates |
|-------|--------|---------|
| WO started | `mrp_workorder._create_or_update_analytic_entry()` | `account.analytic.line` (category: `manufacturing_order`) |
| WO finished | `mrp_workorder.button_finish()` captures `costs_hour` | Workorder cost snapshot for `_cal_price` |
| MO closed | `mrp_production._cal_price()` | Sets `price_unit` on finished move |
| MO closed | `mrp_production._post_labour()` | `account.move` (labor journal entries) |
| Valuation | `stock_move._action_done()` | `account.move` (stock valuation entries) |

**Cost calculation formula:**
```
finished_move.price_unit = (
    sum(consumed_moves.value)        # Component material cost
  + sum(wo._cal_cost())              # Workorder labor cost
  + extra_cost × quantity            # Extra unit cost
) × (1 - sum(byproduct_cost_share) / 100)  # Byproduct offset
  / quantity
```

**WIP tracking:** `mrp_production.wip_move_ids` holds `account.move` records created by `_post_labour()` for labor costs not yet capitalized.

### MRP — Quality (`mrp_quality`)

When `mrp_quality` is installed:
- `quality.point` with `operation_type='mrp_operation'`: Checks attached to routing operations
- `quality.point` with `picking_type_id` matching the MO's `picking_type_id`: General production checks
- Quality alerts (`quality.alert`) linked to `production_id` or `workorder_id`
- Checks can block WO completion when `quality.fail=True` (if configured)

### MRP — Project (`project`)

Each `mrp.workorder` can generate a `project.task` for time-tracking and planning outside the MRP UI:
- Task linked via `workorder_id` on the task
- Task tracks the same `product_id`, `production_id`, and `workcenter_id`
- Time logged on the task syncs to `mrp.workcenter.productivity.time_ids`

This enables using the project Gantt view for WO scheduling in complex production environments.

### MRP — Sale (`sale_mrp` / `sale`)

**Trigger:** `sale.order.line` with a manufacture route:
1. `procurement.group` created for the SO
2. `stock.rule` with `action='manufacture'` triggered
3. `mrp.production` created with `origin` = SO name
4. MO `product_id`, `product_qty` derived from the SO line

**Delivery integration:** When MO produces a tracked product, `lot_producing_ids` are assigned and linked. When MO is done, the finished product quant is available for the outgoing delivery picking.

**Locked MOs from SO:** `sale_mrp` may automatically unlock MOs created from SOs to allow seamless quantity adjustments — check `group_unlocked_by_default` interaction with sale workflows.

### MRP — Purchase / Subcontracting (`mrp_subcontracting`)

**Subcontracting flow:**
1. `stock.picking.type` with `is_subcontracting=True` triggers subcontracting rules
2. Components sent to subcontractor via `pbm` (pick before manufacturing) moves
3. Subcontractor receives components, performs MO, returns finished goods
4. `mrp_production.subcontractor_id` identifies the vendor

**Component traceability:** Components sent to subcontractor tracked via `stock.move.is_subcontracting=True` + `raw_material_production_id`. The subcontracting picking carries the MO reference for full traceability back to the PO.


| Analytic integration | Basic analytic lines | `analytic_distribution` on workcenter with `_perform_analytic_distribution()` | Cost allocation |
| Scrap mechanism | Basic scrap | Kit scrap via `_compute_kit_quantities`, `production_group_id` propagation | Scrap traceability |
| Subcontracting | Basic subcontracting | Enhanced with `subcontractor_id`, PBM/SAM steps, full component traceability | Better subcontractor management |

### Key Migration Notes

1. **MO locking:** After upgrade, check `group_unlocked_by_default` status. If inactive (default), existing draft/confirmed MOs are locked. Test all MO editing workflows before going live.

2. **`days_to_prepare_mo`:** Existing BOMs get `days_to_prepare_mo=0` by default. Update BOMs manually if pre-production lead time was implicitly handled elsewhere.

3. **WO state computation:** If custom code depends on WO being `ready` when all components are reserved, note that Odoo 19 computes `qty_ready` per WO based on predecessor WO output — the criterion changed from `reservation_state`.

4. **`cost_share` validation:** If existing BOMs have byproduct `cost_share` totaling >100%, the `_check_byproducts` constraint will block saving those BOMs after upgrade. Pre-audit all byproduct cost shares before upgrading.



## Related Modules

- [Modules/Stock](modules/stock.md) — Inventory management, stock moves, quants
- [Modules/Product](modules/product.md) — Product definitions, variants, UoM
- [Modules/Resource](modules/resource.md) — Resource calendar, work center planning
- [Modules/Purchase](modules/purchase.md) — Component procurement
- [Modules/Sale](modules/sale.md) — Sales orders triggering manufacturing
- [Modules/Quality](modules/quality.md) — Quality checks during production

---

## Related

[Modules/Stock](modules/stock.md), [Modules/Product](modules/product.md), [Modules/Resource](modules/resource.md), [Modules/Purchase](modules/purchase.md), [Modules/Quality](modules/quality.md), [Modules/MRP](modules/mrp.md), [Modules/mrp_account](modules/mrp_account.md), [Modules/mrp_subcontracting](modules/mrp_subcontracting.md), [Modules/MRP](modules/mrp.md), [Modules/mrp_repair](modules/mrp_repair.md)
