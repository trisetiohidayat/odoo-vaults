---
Module: stock_picking_batch
Version: Odoo 18
Type: Core
Tags: #stock #batch #wave #picking #logistics
Related: [Modules/Stock](stock.md), [Modules/Stock Picking](Modules/Stock-Picking.md)
---

# stock_picking_batch — Batch Transfer

> **Odoo path:** `addons/stock_picking_batch/`
> **Depends:** `stock`
> **License:** LGPL-3

## Overview

The `stock_picking_batch` module groups multiple stock pickings into a single **Batch Transfer** for coordinated processing. It extends `stock.picking` with batch ownership and provides two grouping modes: **Batch** (manual assignment) and **Wave** (line-level grouping). Batches support auto-creation via picking type rules, backorder handling per picking, and estimated shipping metrics.

---

## Model: `stock.picking.batch`

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Auto-generated sequence (code: `picking.batch` or `picking.wave`); readonly, required |
| `description` | Char | Optional free-text description (used in auto-batch naming) |
| `user_id` | Many2one `res.users` | Responsible person for the batch |
| `company_id` | Many2one `res.company` | Required; set from current company on create |
| `picking_ids` | One2many `stock.picking` | Pickings in this batch; domain: `allowed_picking_ids` |
| `allowed_picking_ids` | One2many `stock.picking` | Computed domain of assignable pickings (states: `waiting`, `confirmed`, `assigned`, also `draft` if batch is draft) |
| `state` | Selection | `draft` / `in_progress` / `done` / `cancel`; computed from pickings; readonly |
| `picking_type_id` | Many2one `stock.picking.type` | Operation type; auto-set from first picking |
| `warehouse_id` | Many2one `stock.warehouse` | Related from `picking_type_id` |
| `picking_type_code` | Selection | Related from `picking_type_id` (`incoming`, `outgoing`, `internal`) |
| `scheduled_date` | Datetime | Earliest picking scheduled date; setting it propagates to all pickings via onchange |
| `is_wave` | Boolean | True = Wave mode (line-level), False = Batch mode (picking-level) |
| `move_ids` | One2many `stock.move` | Computed: all moves from all pickings |
| `move_line_ids` | One2many `stock.move.line` | Computed: all move lines; writable via `_set_move_line_ids` |
| `show_check_availability` | Boolean | True if any move is not `assigned`, `done`, or `cancel` |
| `show_allocation` | Boolean | True if current user can see allocation report (group: `stock.group_reception_report`) |
| `show_lots_text` | Boolean | True if pickings use lot/SN tracking |
| `estimated_shipping_weight` | Float | Computed from packs + unpacked moves |
| `estimated_shipping_volume` | Float | Computed from packs + unpacked moves |
| `properties` | Properties | Batch-level custom properties, definition from `picking_type_id.batch_properties_definition` |

### State Transitions

```
draft → in_progress  (action_confirm)
draft → cancel        (action_cancel)
in_progress → done    (action_done)   — only if all pickings done/cancel
in_progress → cancel  (action_cancel) — also if all pickings cancel automatically
done → (immutable, cannot delete)
```

### State Computation (`_compute_state`)

The batch `state` is derived from pickings:
- If **all pickings are `cancel`** → batch becomes `cancel`
- If **all pickings are `cancel` or `done`** → batch becomes `done`
- Empty batch remains `draft`

### Key Methods

| Method | Description |
|--------|-------------|
| `action_confirm()` | Calls `picking_ids.action_confirm()` on all pickings, sets state to `in_progress` |
| `action_done()` | Validates all pickings via `button_validate()`; detaches empty/waiting pickings via `pickings_to_detach` context; triggers backorder creation and auto-reassignment |
| `action_cancel()` | Sets state to `cancel` and clears `picking_ids` |
| `action_assign()` | Calls `action_assign()` on all pickings |
| `action_print()` | Returns report action for batch printing |
| `action_put_in_pack()` | Packs all "done" move lines into a new package |
| `action_view_reception_report()` | Opens reception report for all pickings |
| `action_open_label_layout()` | Opens label layout wizard filtered to batch moves |
| `_sanity_check()` | Validates all pickings are in `allowed_picking_ids`; raises if not |
| `_is_picking_auto_mergeable(picking)` | Checks `batch_max_lines` and `batch_max_pickings` constraints |
| `_is_line_auto_mergeable(...)` | Checks move count and picking count limits for wave mode |
| `write(vals)` | Auto-cancels batch if `picking_ids` becomes empty; auto-sets `picking_type_id` from first picking; propagates `user_id` to all pickings via `assign_batch_user()` |

### Name Sequences

- Batch: `picking.batch` sequence (company-scoped)
- Wave: `picking.wave` sequence (company-scoped)

### `display_name` Computation

When context `add_to_existing_batch` is set, display name becomes `"{name}: {description}"`.

---

## Model: `stock.picking` (Extension)

### Added Fields

| Field | Type | Description |
|-------|------|-------------|
| `batch_id` | Many2one `stock.picking.batch` | Batch this picking belongs to; indexed, copyable=False |
| `batch_sequence` | Integer | Sequence within the batch |

### Methods

| Method | Description |
|--------|-------------|
| `action_confirm()` | After confirming, calls `_find_auto_batch()` if `picking_type_id.auto_batch` is set |
| `button_validate()` | After validation: detaches pickings in `pickings_to_detach` context; backorders trigger `_find_auto_batch()` + `_auto_wave()` |
| `_create_backorder()` | Detaches pickings in `pickings_to_detach` from batch before creating backorder |
| `action_cancel()` | Removes picking from batch if other pickings remain |
| `_find_auto_batch()` | Attempts to auto-assign picking to existing or new batch based on `picking_type_id` grouping rules |
| `_is_auto_batchable(picking=None)` | Returns True only if state is `assigned` and batch max constraints are satisfied |
| `_get_possible_pickings_domain()` | Builds domain for finding compatible pickings to batch with (partner, country, source/dest location grouping) |
| `_get_possible_batches_domain()` | Builds domain for finding existing batches that can accept this picking |
| `_get_auto_batch_description()` | Constructs description from grouping criteria values |
| `_package_move_lines(batch_pack=False, ...)` | Delegates to batch's pickings when batch_pack=True |
| `assign_batch_user(user_id)` | Writes `user_id` on pickings, posts message to chatter |

---

## Model: `stock.picking.type` (Extension)

### Added Fields

| Field | Type | Description |
|-------|------|-------------|
| `auto_batch` | Boolean | Enable automatic batch/wave creation when pickings are confirmed |
| `batch_group_by_partner` | Boolean | Group by contact (partner_id) |
| `batch_group_by_destination` | Boolean | Group by destination country |
| `batch_group_by_src_loc` | Boolean | Group by source location |
| `batch_group_by_dest_loc` | Boolean | Group by destination location |
| `wave_group_by_product` | Boolean | Split transfers by product, then group |
| `wave_group_by_category` | Boolean | Split transfers by product category |
| `wave_category_ids` | Many2many `product.category` | Categories to consider for wave grouping |
| `wave_group_by_location` | Boolean | Split transfers by defined locations |
| `wave_location_ids` | Many2many `stock.location` | Locations for wave grouping (domain: `usage='internal'`) |
| `batch_max_lines` | Integer | Max total move lines per batch (0=unlimited) |
| `batch_max_pickings` | Integer | Max pickings per batch (0=unlimited) |
| `batch_auto_confirm` | Boolean | Auto-confirm newly created batches (default: True) |
| `batch_properties_definition` | PropertiesDefinition | Defines batch-level custom properties schema |
| `count_picking_batch` | Integer | Count of active batches (computed) |
| `count_picking_wave` | Integer | Count of active waves (computed) |

### Methods

| Method | Description |
|--------|-------------|
| `action_batch()` | Opens the batch/wave list view filtered to this picking type |
| `_is_auto_batch_grouped()` | Returns True if `auto_batch=True` and any batch group-by key is set |
| `_is_auto_wave_grouped()` | Returns True if `auto_batch=True` and any wave group-by key is set |
| `_get_batch_group_by_keys()` | Returns `['batch_group_by_partner', 'batch_group_by_destination', 'batch_group_by_src_loc', 'batch_group_by_dest_loc']` |
| `_get_wave_group_by_keys()` | Returns `['wave_group_by_product', 'wave_group_by_category', 'wave_group_by_location']` |

### Constraint

`_validate_auto_batch_group_by`: If `auto_batch=True`, at least one group-by key must be set.

### Group By Key Resolution for Waves

| Group By Key | Logic |
|--------------|-------|
| `wave_group_by_product` | Split pickings by `move.product_id` |
| `wave_group_by_category` | Split pickings by `move.product_id.categ_id`, optionally filtered by `wave_category_ids` |
| `wave_group_by_location` | Split pickings by defined `wave_location_ids` |

---

## Model: `stock.warehouse` (Extension)

When a warehouse creates its default picking types via `_get_picking_type_create_values`, all incoming and outgoing types are automatically configured with:
- `auto_batch: True`
- `batch_group_by_partner: True`

This means new warehouses start with auto-batching enabled by default.

---

## Wizards

### `stock.picking.to.batch` — Add Pickings to Batch

| Field | Type | Description |
|-------|------|-------------|
| `batch_id` | Many2one | Target batch; domain: `is_wave=False`, state in `draft/in_progress` |
| `mode` | Selection | `new` (create batch) or `existing` |
| `user_id` | Many2one `res.users` | Responsible for new batch |
| `is_create_draft` | Boolean | If True and mode=`new`, batch stays in draft (no auto-confirm) |
| `description` | Char | Description for new batch |

**`attach_pickings()`**: Creates or uses existing batch, writes `batch_id` on all selected pickings. If mode=`new` and `is_create_draft=False`, auto-calls `action_confirm()`.

### `stock.add.to.wave` — Add to Wave

| Field | Type | Description |
|-------|------|-------------|
| `wave_id` | Many2one | Target wave; domain: `is_wave=True`, state in `draft/in_progress` |
| `picking_ids` | Many2many `stock.picking` | Pickings to add |
| `line_ids` | Many2many `stock.move.line` | Move lines to add (alternative to picking_ids) |
| `mode` | Selection | `existing` or `new` |
| `user_id` | Many2one `res.users` | Sets `active_owner_id` in context |

**`attach_pickings()`**: If `line_ids` present, calls `line_ids._add_to_wave(wave_id)`. Otherwise, opens the "Add Operations" view to allow line-level wave assignment.

---

## Key Workflows

### Manual Batch Creation

1. User selects multiple pickings → "Add to Batch" wizard (via `stock.picking.to.batch`)
2. Chooses new or existing batch, optional responsible, optional draft mode
3. Wizard writes `batch_id` on pickings; if not draft, batch auto-confirmed
4. Batch moves to `in_progress`; `action_confirm()` propagates to all pickings

### Auto-Batch on Picking Confirm

1. `stock.picking.action_confirm()` calls `picking._find_auto_batch()` if `picking_type_id.auto_batch` is set
2. `_find_auto_batch()` first searches existing batches matching group-by criteria; if found, picks are added to that batch
3. If no existing batch found, searches for compatible pickings and creates a new batch containing both
4. If still nothing found, creates a batch with the single picking
5. If `batch_auto_confirm=True`, batch is auto-confirmed immediately

### Batch Validation (`action_done`)

1. Identifies pickings to process vs. empty/waiting pickings to detach
2. Runs `_sanity_check()` on pickings as a batch (not per-picking)
3. Calls `pickings.button_validate()` with context:
   - `skip_sanity_check: True` (already done)
   - `pickings_to_detach: [...]` (IDs of pickings to unlink from batch)
4. Detached pickings get their backorders auto-waved if `picking_type_id.auto_batch` is enabled

### Backorder Handling

When a picking in a batch is partially processed:
- The completed portion is validated with the batch
- The backorder is automatically checked for auto-batch eligibility
- If eligible, `_find_auto_batch()` and `_auto_wave()` are called on the backorder
- The backorder is **not** returned to the original batch (it is assigned a new batch or left standalone)

---

## L4: Batch vs. Wave Picking

### Batch (Picking-Level Grouping)

- **Unit of assignment:** entire `stock.picking`
- **Add/remove:** pickings are assigned or unassigned as a whole
- **Use case:** Warehouse operators pick a fixed set of orders together
- **Constraints:** `batch_max_lines`, `batch_max_pickings`
- **Auto-batch:** Groups by partner/country/source/destination location

### Wave (Line-Level Grouping)

- **Unit of assignment:** individual `stock.move.line` within pickings
- **Add/remove:** specific lines are assigned to wave without moving entire pickings
- **Use case:** Cross-docking, zone picking, where different lines from the same picking may go to different waves or operators
- **Wave grouping:** by product, category, or location
- **Auto-wave:** Triggered by `stock.move.line._auto_wave()`; groups lines across pickings by defined criteria

### How Batches Affect Pick Progress

1. When a batch is `in_progress`, all its pickings move to `in_progress`
2. Completing a picking in a batch triggers batch state re-computation
3. If all pickings are done or cancel, batch transitions to `done`
4. If all pickings cancel, batch auto-transitions to `cancel`
5. Batch `done` is blocked from deletion (`_unlink_if_not_done`)
6. A picking can only belong to one batch at a time
7. Assigning a picking to a batch propagates `user_id` to the picking

### Auto-Batch Constraint Priority

When `_is_picking_auto_mergeable()` is called:
1. Check `batch_max_lines`: `len(batch.move_ids) + len(picking.move_ids) <= batch_max_lines`
2. Check `batch_max_pickings`: `len(batch.picking_ids) + 1 <= batch_max_pickings`
3. Both must pass for the picking to be merged into the batch
4. `_is_auto_batchable()` on the picking side checks same constraints before attempting merge

---

## File Map

| File | Models |
|------|--------|
| `models/stock_picking_batch.py` | `stock.picking.batch` |
| `models/stock_picking.py` | `stock.picking` (ext), `stock.picking.type` (ext) |
| `models/stock_warehouse.py` | `stock.warehouse` (ext) |
| `wizard/stock_picking_to_batch.py` | `stock.picking.to.batch` |
| `wizard/stock_add_to_wave.py` | `stock.add.to.wave` |