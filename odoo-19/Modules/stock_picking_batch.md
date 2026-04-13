---
date: 2026-04-11
tags:
  - odoo
  - odoo19
  - modules
  - stock
  - batch-transfer
  - wave-transfer
---

# stock_picking_batch — Warehouse Management: Batch Transfer

> **Technical name:** `stock_picking_batch`
> **Category:** Supply Chain/Inventory
> **Depends:** `stock`
> **License:** LGPL-3
> **Author:** Odoo S.A.
> **Version:** 19.0 (CE)

Groups multiple stock transfers (receipts, internal moves, deliveries) into a single **Batch** or **Wave** for unified processing. This is the module behind the **Batch Transfer** and **Wave Transfer** menu items in the Inventory app.

---

## L1 — Conceptual Model

### Batch vs. Wave

Two distinct concepts share the same `stock.picking.batch` table, differentiated by the `is_wave` boolean.

| Concept | `is_wave` | Creation | Contents |
|---|---|---|---|
| **Batch** | `False` | Manual (wizard) or auto-batch | Whole `stock.picking` records only |
| **Wave** | `True` | Auto-waving or `stock.add.to.wave` wizard | Individual `stock.move.line` records (can split pickings) |

Batches group entire pickings that move through the pipeline together. Waves are more flexible: a warehouse operator can extract specific move lines from one or more pickings into a wave, causing the original picking to be split into two separate picking records.

### Primary Model

**File:** `models/stock_picking_batch.py`
**Inherits:** `mail.thread`, `mail.activity.mixin`
**Order:** `name desc`

**Key identity fields:** `name` (Char, auto-seq), `description` (Char), `is_wave` (Boolean)
**Key relation fields:** `picking_ids` (One2many stock.picking), `picking_type_id` (Many2one stock.picking.type)
**Key state:** `state` in `['draft', 'in_progress', 'done', 'cancel']`

### Extensions

| Model | File | Role |
|---|---|---|
| `stock.picking` | `models/stock_picking.py` | `batch_id` field, auto-batch algorithm, `_find_auto_batch()` |
| `stock.move` | `models/stock_move.py` | Auto-batch hooks in assignment and cancellation flows |
| `stock.move.line` | `models/stock_move_line.py` | Wave assignment engine, `_auto_wave()` |
| `stock.picking.type` | `models/stock_picking.py` | Batch and wave configuration fields |
| `stock.warehouse` | `models/stock_warehouse.py` | New-warehouse defaults for auto-batch |

---

## L2 — Field Inventory and State Machine

### `stock.picking.batch` — All Fields

#### Identity

| Field | Type | Default | Notes |
|---|---|---|---|
| `name` | `Char` | `'New'` → auto-seq | `copy=False`, `readonly=True`. Format: `{BATCH|WAVE}/{picking_type.sequence_code}/{N}`. `_prepare_name()` splits `ir.sequence.next_by_code()` output on `/`. |
| `description` | `Char` | — | Free-text. When context `add_to_existing_batch` is set, display name becomes `"{name}: {description}"` via `_compute_display_name()`. |
| `is_wave` | `Boolean` | `False` | Conceptual split between batch and wave. Not stored in `create()` vals — set explicitly by callers. |

#### Relations

| Field | Type | Notes |
|---|---|---|
| `picking_ids` | `One2many stock.picking` | Domain: `[('id', 'in', allowed_picking_ids)]`. `check_company=True`. |
| `allowed_picking_ids` | `One2many stock.picking` | NOT stored. Returns pickings with same `company_id`, state in `['waiting','confirmed','assigned']` (plus `'draft'` if batch is `draft`), filtered by `picking_type_id`. |
| `picking_type_id` | `Many2one stock.picking.type` | Not required on creation. Copied from first added picking. |
| `warehouse_id` | `Many2one stock.warehouse` | `related='picking_type_id.warehouse_id'`, `store=False`. |
| `picking_type_code` | `Selection` | `related='picking_type_id.code'` (incoming/outgoing/internal). |

#### People and Company

| Field | Type | Notes |
|---|---|---|
| `user_id` | `Many2one res.users` | `tracking=True`, `check_company=True`. Changing cascades to all `picking_ids` via `assign_batch_user()`. |
| `company_id` | `Many2one res.company` | `required=True`, `readonly=True`, `index=True`. Enforced by `ir.rule` for multi-company. |

#### Computed Aggregates (all non-stored One2many computes)

| Field | Type | Compute | Notes |
|---|---|---|---|
| `move_ids` | `One2many stock.move` | `_compute_move_ids` | Union of all `batch.picking_ids.move_ids`. |
| `move_line_ids` | `One2many stock.move.line` | `_compute_move_line_ids` | Has `_set_move_line_ids` inverse and `_search_move_line_ids` search. |
| `show_check_availability` | `Boolean` | `_compute_move_ids` | `True` if any move not in `assigned/cancel/done`. |
| `show_allocation` | `Boolean` | `_compute_show_allocation` | `True` if user has `stock.group_reception_report` AND `picking_ids._get_show_allocation()` returns True. |
| `show_lots_text` | `Boolean` | `_compute_show_lots_text` | Mirrors `picking_ids[0].show_lots_text`. |
| `estimated_shipping_weight` | `Float` | `_compute_estimated_shipping_capacity` | Sum of package weights + unpacked product weights. |
| `estimated_shipping_volume` | `Float` | `_compute_estimated_shipping_capacity` | Sum of package volumes + unpacked product volumes. |

#### Scheduling

| Field | Type | Notes |
|---|---|---|
| `scheduled_date` | `Datetime` | `store=True`. `compute="_compute_scheduled_date"`: returns `min()` of child pickings' `scheduled_date`. `onchange_scheduled_date` propagates any manual write back to all child `picking_ids.scheduled_date`. |
| `properties` | `Properties` | `definition='picking_type_id.batch_properties_definition'`. Inherited from picking type at batch creation time. |

### State Machine

```
draft ──────► in_progress ──────► done
   │                │
   │                └──► cancel (any time)
   │
   └──► cancel
```

**`_compute_state` details** (only evaluates for batches not already `cancel` or `done`):

1. If `picking_ids` empty — no state change (stays `draft` or `in_progress`).
2. If **all** pickings `cancel` — `state = 'cancel'`.
3. If **all** pickings in `['cancel', 'done']` — `state = 'done'`.
4. `in_progress` is set only by explicit `action_confirm()`.

**Auto-cancel on write:** `write()` cancels any `in_progress` batch that ends up with no pickings.

### `stock.picking` Extension Fields

| Field | Type | Notes |
|---|---|---|
| `batch_id` | `Many2one stock.picking.batch` | `check_company=True`, `index=True`, `copy=False`. When set, ensures `batch_id.picking_type_id` matches the picking's type. |
| `batch_sequence` | `Integer` | Controls display order within a batch's picking list. |

### `stock.picking.type` — Batch and Wave Configuration Fields

#### Batch (batch transfer)

| Field | Type | Default | Notes |
|---|---|---|---|
| `auto_batch` | `Boolean` | `False` | Master switch: confirmed pickings on this type auto-join batches. |
| `batch_group_by_partner` | `Boolean` | `True` (new types via warehouse) | Group batches by `partner_id`. |
| `batch_group_by_destination` | `Boolean` | `False` | Group by `partner_id.country_id`. |
| `batch_group_by_src_loc` | `Boolean` | `True` (new types via warehouse) | Group by `location_id`. |
| `batch_group_by_dest_loc` | `Boolean` | `False` | Group by `location_dest_id`. |
| `batch_max_lines` | `Integer` | `0` (unlimited) | Max total `stock.move` records across all pickings in one batch. |
| `batch_max_pickings` | `Integer` | `0` (unlimited) | Max pickings per batch. Setting `<= 1` is blocked. |
| `batch_auto_confirm` | `Boolean` | `True` | Immediately confirms newly created batches and waves. |
| `batch_properties_definition` | `PropertiesDefinition` | — | Schema for `stock.picking.batch.properties`. |
| `count_picking_batch` | `Integer` (computed) | — | Active (non-done/non-cancel) batches with this type. |
| `count_picking_wave` | `Integer` (computed) | — | Active waves with this type. |

#### Wave (wave transfer)

| Field | Type | Notes |
|---|---|---|
| `wave_group_by_product` | `Boolean` | Split transfers by product; group pickings with the same product. |
| `wave_group_by_category` | `Boolean` | Split by product category. Used with `wave_category_ids`. |
| `wave_category_ids` | `Many2many product.category` | Only these categories considered for auto-waving. Lines with other categories excluded. |
| `wave_group_by_location` | `Boolean` | Group by location. Uses `wave_location_ids`. |
| `wave_location_ids` | `Many2many stock.location` | Domain: `usage = 'internal'`. Deepest matching ancestor used as grouping key per line. |

### `stock.move.line` Extension

| Field | Type | Notes |
|---|---|---|
| `batch_id` | `Many2one stock.picking.batch` | `related='picking_id.batch_id'`. Convenience for domain filtering. |

### Constraints

| Model | Constraint | Trigger |
|---|---|---|
| `stock.picking.type` | `_validate_auto_batch_group_by` | `@api.constrains` on all group-by keys + `auto_batch`. Raises `ValidationError` if `auto_batch=True` but no group-by key is set. |

---

## L3 — Cross-Model Integration, Override Patterns, Workflow Triggers, Failure Modes

### Cross-Model: Batch / Picking Relationship

The `batch_id` on `stock.picking` is the primary cross-module integration point. The relationship is strictly one-way from picking to batch — a batch does not "own" pickings in a database sense (no FK constraint), only via the One2many.

**Batch confirmation → picking lock:** When `action_confirm()` is called on a batch, it calls `picking_ids.action_confirm()` which triggers `_find_auto_batch()` on each picking. This means confirm a batch = confirm all its pickings + trigger auto-batch reassessment.

**Picking validation → batch detach:** In `stock.picking.button_validate()`, as soon as one picking in a batch reaches `done` while others are not, that picking is immediately severed from the batch (`picking.batch_id = None`). The remaining pickings stay in the batch.

**`picking_ids` vs `move_ids`:** `picking_ids` is the authoritative container — it's the set of whole pickings in the batch. `move_ids` and `move_line_ids` are computed unions of all moves/lines from all `picking_ids`. Operations like `action_put_in_pack` and `action_done` work on the aggregated `move_line_ids`.

### Override Patterns

#### Pattern: super() + side effect on related records

`stock.move._action_cancel()` calls `super()`, then severs `batch_id` from cancelled pickings that are not the last in their batch. This is safe because cancellation always completes before the batch state recomputes.

#### Pattern: context-passed IDs for cross-record coordination

`button_validate()` on `stock.picking` passes `pickings_to_detach: [...]` in context to its own `button_validate()`. The receiving method (in `stock`) reads this to know which pickings to remove from the batch without triggering re-batch logic.

#### Pattern: sudo() for batch searches

`_find_auto_batch()` searches `stock.picking.batch` and `stock.picking` using `sudo()` because the auto-batch logic runs under the user's context, but must bypass record rules to find compatible batches across users. The search is still scoped to the same `company_id`.

#### Pattern: Extension hooks (no-ops, override for custom logic)

`stock.move.line` defines four no-op hooks for wave auto-assignment:

| Hook | Signature | Purpose |
|---|---|---|
| `_get_potential_existing_waves_extra_domain` | `(domain_list, picking_type)` | Add extra domain conditions to existing wave search |
| `_get_potential_new_waves_extra_domain` | `(domain_list, picking_type)` | Add conditions for new wave creation |
| `_is_potential_existing_wave_extra` | `(wave)` | Custom wave compatibility check |
| `_is_new_potential_line_extra` | `(potential_line)` | Custom line compatibility check |

### Workflow Triggers

#### Trigger 1: Picking confirmed → auto-batch

```
stock.picking.action_confirm()
  → stock.picking._find_auto_batch()
    → domain: state='assigned', batch_id=False, same company+type
    → _is_picking_auto_mergeable() checks batch_max_lines/batch_max_pickings
    → if existing compatible batch found: batch.picking_ids |= self
    → else: creates new batch (optionally auto-confirms)
```

#### Trigger 2: Move assigned → auto-batch

```
stock.move._assign_picking_post_process()
  → picking._find_auto_batch()
```

Also: `stock.move.write()` with state transition to `'partially_available'` or `'assigned'` re-triggers `_find_auto_batch()`.

#### Trigger 3: Move line reserved → auto-wave

```
stock.move._action_assign(force_qty)
  → super()._action_assign()
  → self.move_line_ids._auto_wave()
    → _auto_wave_lines_into_existing_waves() — tries to attach to existing waves
    → _auto_wave_lines_into_new_waves() — creates new waves for unmatched lines
```

#### Trigger 4: Batch validated → detach partial pickings

```
stock.picking.batch.action_done()
  → stock.picking.batch.action_done() core logic
    → pickings.button_validate() with skip_sanity_check=True, pickings_to_detach=[...]
    → stock.picking.button_validate() reads pickings_to_detach from context
      → severs batch_id from pickings listed in context
      → backorder pickings collected and re-evaluated for auto-batch
```

### Failure Modes

| Failure Mode | Cause | Behavior |
|---|---|---|
| **Batch with one picking partially done** | User validates a single picking in batch via `button_validate()` | Batch immediately severs `batch_id` from the done picking. Backorder re-evaluated for auto-batch. |
| **Empty assigned picking at `action_done()`** | All moves in an `'assigned'` picking have zero `quantity` | Picking detached from batch without cancellation. Available for future batching. |
| **Cancelled picking in multi-picking batch** | `action_cancel()` on one picking | Picking's `batch_id` cleared if any other batch picking remains non-cancelled. Batch state recomputes. |
| **`batch_max_pickings <= 1`** | Misconfiguration | Explicitly blocked in `_is_auto_batchable()`. Raises `False`. |
| **`wave_group_by_category` with empty `wave_category_ids`** | Misconfiguration | `_is_auto_waveable()` returns `False` for all lines. Auto-waving silently disabled. |
| **Concurrent batch assignment** | Two simultaneous `action_confirm()` on different pickings matching same auto-batch | Odoo transaction isolation: second write succeeds, picking joins the already-confirmed batch (domain allows `state='in_progress'`). |
| **Merge across `is_wave` types** | User selects mix of batch and wave records | `action_merge()` raises `UserError`. |
| **Backorder after partial batch validation** | Some picks done, some not, user creates backorder | `button_validate()` collects all `backorder_ids` and re-runs `_find_auto_batch()` + `_auto_wave()` on each. |
| **Changing `picking_type_id` on batch with pickings** | User reassigns batch type | `write()` runs `_sanity_check()` after change. Incompatible pickings raise `UserError`. Batch renamed using new type's sequence. |
| **`allowed_picking_ids` stale on form load** | Non-stored compute runs on every access | View-level domain on `picking_ids` filters at UI layer. Expensive for large warehouses. |

---

## L4 — Performance, Odoo 18→19 Changes, Security

### Performance Considerations

#### `allowed_picking_ids` — non-stored compute on every form load

`_compute_allowed_picking_ids` runs `stock.picking.search()` on every batch form load. For large warehouses with thousands of pickings in `waiting`/`confirmed`/`assigned` states, this can be a significant query. The view-level domain on `picking_ids` (`[('id', 'in', allowed_picking_ids)]`) further restricts the displayed options at the UI layer, but the compute itself cannot be avoided without caching.

Mitigation: Keep picking backlogs processed. High-volume warehouses should ensure pickings do not accumulate in `waiting`/`confirmed` states for long.

#### `_auto_wave()` nested loop complexity

The `_auto_wave_lines_into_existing_waves()` method has complexity O(picking_types × waves × lines) in the worst case. For each picking type, it iterates all potential waves, and for each wave, it checks all lines. In high-volume warehouses with many active waves, set `batch_max_lines` or `batch_max_pickings` to prune the search space early — these limits are checked via `_is_line_auto_mergeable()` on every line-wave combination.

#### `move_ids` / `move_line_ids` — non-stored One2many computes

Both fields recompute on every access. `_search_move_line_ids` allows the detailed operations list to use a domain search without loading all lines into memory. For very large batches, prefer using `_search_move_line_ids` domain searches rather than directly accessing `move_line_ids`.

#### `sudo()` in `_find_auto_batch()`

Batch and picking searches run as superuser to bypass record rules during the auto-batch flow. This is safe because searches are scoped to the same `company_id`. The `sudo()` call is on specific `env` lookups, not a general elevation.

#### Merge operation — loads all records

`action_merge()` calls `mapped()` on all `move_line_ids` and `picking_ids` across all batches being merged. For very large batches this can consume significant memory. Consider splitting large batches before merging.

#### Batch vs. Individual Picking Processing

Processing pickings individually (one at a time via `stock.picking.button_validate()`) triggers O(n) separate transactions with O(n) separate state recomputations on the batch. Processing via `stock.picking.batch.action_done()` handles all pickings in a single batch operation with one shared `_sanity_check()`, making it significantly more efficient for bulk warehouse operations.

### Odoo 18 → 19 Changes

| Change | Detail |
|---|---|
| **`batch_group_by_destination`** | New group-by key for destination country (`partner_id.country_id`). Added to `stock.picking.type` config and both `_get_possible_*_domain()` methods on `stock.picking`. |
| **`batch_auto_confirm` default `True`** | Now defaults to `True` on newly created picking types (via `stock.warehouse` override). Auto-batch creates confirmed batches by default — this is an opt-out behavior. |
| **New warehouse defaults: `auto_batch=True`, `batch_group_by_partner=True`** | Incoming and outgoing picking types created for new warehouses automatically get `auto_batch=True` and `batch_group_by_partner=True`. Auto-batching is now opt-out for new Odoo 19 installations. |
| **`action_merge()`** | New method to consolidate multiple batches or waves with matching `picking_type_id`, `is_wave`, and non-terminal `state`. Returns `display_notification` with deep link to merged batch. |
| **Auto-waving from `_action_assign()`** | `_action_assign()` on `stock.move` now calls `_auto_wave()` on `move_line_ids` after standard reservation, enabling automatic wave creation from the standard "Check Availability" flow. This was previously triggered only manually or from picking confirm. |
| **`is_wave` fully operational** | The conceptual separation between batch and wave on `stock.picking.batch` is fully operational in Odoo 19 with the complete auto-waving engine in `stock.move.line`. |
| **`wave_group_by_location` — nearest-parent location tracking** | When `wave_group_by_location` is enabled, waves are filtered to only those whose all existing lines share the same nearest parent location (walked from line up to ancestor). New lines that don't match are excluded from joining incompatible waves. |
| **4 extension hooks on `stock.move.line`** | `_get_potential_existing_waves_extra_domain`, `_get_potential_new_waves_extra_domain`, `_is_potential_existing_wave_extra`, `_is_new_potential_line_extra` — all no-ops, override for custom wave assignment logic. |
| **`_get_merged_batch_vals()`** | New method returning dict of vals from the earliest-scheduled batch used during merge. Consolidates `user_id`, `description`, `scheduled_date`. |

### Security Analysis

#### ACL — `ir.model.access.csv`

| ACL ID | Model | Group | R | W | C | D |
|---|---|---|---|---|---|---|
| `access_stock_picking_batch` | `stock.picking.batch` | `stock.group_stock_user` | 1 | 1 | 1 | 1 |
| `access_stock_picking_to_batch` | `stock.picking.to.batch` | `stock.group_stock_user` | 1 | 1 | 1 | 0 |
| `access_stock_add_to_wave` | `stock.add.to.wave` | `stock.group_stock_user` | 1 | 1 | 1 | 0 |

Both wizards are transient so D ACL is irrelevant. Only `stock.group_stock_user` (warehouse users and managers) can access batch functionality.

#### Record Rule — Multi-company

```python
stock_picking_batch_multicompany_rule:
  model_id: model_stock_picking_batch
  domain_force: [('company_id', 'in', company_ids)]
```

Standard Odoo multi-company enforcement: users can only see and write batches belonging to companies they belong to. No batch can span multiple companies (enforced by `company_id` required and the `check_company` on `picking_ids`).

#### Deletion protection

`_unlink_if_not_done()` with `@api.ondelete(at_uninstall=False)` raises `UserError` if any batch is `done`. Batches in `draft`, `in_progress`, or `cancel` can be deleted. This prevents accidental data loss from completed work.

#### sudo() in auto-batch — safe scope

`_find_auto_batch()` uses `sudo()` only for searching batches and pickings, not for writing. The actual batch write (`batch.picking_ids |= self`) happens in the normal user context. This prevents privilege escalation.

#### Integrity of picking → batch relationship

`write()` on `stock.picking` with a new `batch_id` triggers `batch_id._sanity_check()` to validate compatibility. This prevents adding a picking to a batch with a mismatched `picking_type_id` or `company_id`.

#### Audit trail

`mail.thread` on `stock.picking.batch` + `mt_batch_state` subtype means all state transitions are automatically logged in the chatter. The batch also posts messages linking back to itself during validation.

---

## Wizards

### `stock.picking.to.batch` — Manual Batch Creation

**Model:** `stock.picking.to.batch` (Transient)

| Field | Type | Notes |
|---|---|---|
| `batch_id` | `Many2one stock.picking.batch` | Domain: `is_wave=False`, `state in ('draft', 'in_progress')`. |
| `mode` | `Selection` | `'existing'` or `'new'`. Default: `'new'`. |
| `user_id` | `Many2one res.users` | Optional responsible. |
| `is_create_draft` | `Boolean` | If `True`, skips `action_confirm()`. Default: `False` (auto-confirm). |
| `description` | `Char` | Free-text description for new batch. |

**`attach_pickings()`**: Reads active pickings from context. If `mode == 'new'`: creates batch with first picking's `picking_type_id` and `company_id`. Writes `batch_id` on all active pickings. If not `is_create_draft`: calls `batch.action_confirm()`.

### `stock.add.to.wave` — Add to Wave

**Model:** `stock.add.to.wave` (Transient)

| Field | Type | Notes |
|---|---|---|
| `wave_id` | `Many2one stock.picking.batch` | Domain: `is_wave=True`, `state in ('draft', 'in_progress')`. |
| `picking_ids` | `Many2many stock.picking` | Full pickings to add. |
| `line_ids` | `Many2many stock.move.line` | Individual lines to add. |
| `mode` | `Selection` | `'existing'` or `'new'`. Default: `'existing'`. |
| `user_id` | `Many2one res.users` | Passed as `active_owner_id` in context to `_add_to_wave()`. |

**`attach_pickings()`**: If `line_ids`: passes `active_owner_id` in context, calls `line_ids._add_to_wave(wave_id)`. If `picking_ids`: opens the "Add Operations" view passing `active_wave_id` and `picking_to_wave` in context. The lines shown there trigger `_add_to_wave()` when added.

---

## Data

- **`picking.batch` sequence** — Prefix `BATCH/`, padding 5, company-scoped via `_prepare_name()`.
- **`picking.wave` sequence** — Prefix `WAVE/`, padding 5.
- **`mt_batch_state`** — `mail.message.subtype` on `stock.picking.batch`. Triggered by `_track_subtype()` when `state` changes.

---

## Cross-Module Integration Summary

| Module | Integration |
|---|---|
| `stock` | All base models. `batch_id` on `stock.picking` and `stock.move.line`. Auto-batch hooks in `action_confirm`, `_action_assign`, `_assign_picking_post_process`, `button_validate`, `_action_cancel`. |
| `mail` | `mail.thread` + `mail.activity.mixin` on batch. `mt_batch_state` subtype. Chatter messages posted during batch validation linking back to batch. |
| `stock_account` | Batch validation ultimately triggers `stock_account` valuation moves. Batch grouping does not alter valuation logic. |
| `delivery` | Via `delivery_stock_picking_batch` module (separate addon). |

---

## Related

- [Modules/Stock](Stock.md) — Base warehouse management
- [Modules/Purchase](Purchase.md) — Purchase order → receipt flow
- [Modules/Sale](Sale.md) — Sale order → delivery flow
- [Modules/MRP](MRP.md) — Manufacturing → work order flow
