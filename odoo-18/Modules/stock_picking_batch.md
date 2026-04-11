# stock_picking_batch — Batch Transfer Management

**Module:** `stock_picking_batch`
**Odoo Version:** 18
**Source:** `~/Users/tri-mac/odoo/odoo18/odoo/addons/stock_picking_batch/`

---

## Overview

The `stock_picking_batch` module enables grouping multiple stock transfers (pickings) into a single batch for unified processing by a single warehouse operator. It supports both standard batch transfers and "waves" (a specialized batch type used for partial picking automation). Batches track combined weight/volume estimates, enforce picking type constraints, and auto-close when all pickings are completed.

---

## Architecture

### Model Structure

```
stock.picking.batch      # Batch transfer container
stock.picking            # Extended with batch_id link
stock.move               # Extended with batch_id link
stock.move.line          # Extended (via picking)
stock.picking.type       # Extended with batch constraints
```

### File Map

| File | Purpose |
|------|---------|
| `models/stock_picking_batch.py` | Core `stock.picking.batch` model |
| `models/stock_picking.py` | Picking extensions for batch support |
| `models/stock_move.py` | Move extensions for batch support |
| `models/stock_move_line.py` | Move line extensions |
| `models/stock_warehouse.py` | Warehouse batch constraints |
| `models/res_partner.py` | Partner extensions |

---

## Core Models

### stock.picking.batch

**`stock.picking.batch`** is the container model for grouped transfers.

**Inheritance:** `models.Model` + `mail.thread` + `mail.activity.mixin`
** `_name`: `stock.picking.batch`
** `_description`: `"Batch Transfer"`
** `_order`: `name desc`

#### State Machine

```
draft
   |
   | action_confirm()
   v
in_progress
   |
   | action_done() [all pickings done]
   v
done
   OR
cancel  ← action_cancel() at any time (or auto when all pickings cancelled)
```

#### Field Reference

**Identification**

| Field | Type | Description |
|-------|------|-------------|
| `name` | `Char` | Auto-generated from sequence: `picking.batch` (standard) or `picking.wave` (wave), default `'New'` |
| `description` | `Char` | Optional batch description |
| `is_wave` | `Boolean` | If `True`, this is a wave batch. Affects sequence code. Default `False` |

**Assignment**

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | `Many2one(res.users)` | Responsible warehouse operator. When set, `picking_ids.assign_batch_user()` is called |
| `company_id` | `Many2one(res.company)` | Company scope |
| `picking_type_id` | `Many2one(stock.picking.type)` | Constrains batch to one operation type |
| `warehouse_id` | `Many2one(stock.warehouse)` | Related from `picking_type_id.warehouse_id` |
| `picking_type_code` | `Selection` | Related from `picking_type_id.code` |

**Contents**

| Field | Type | Description |
|-------|------|-------------|
| `picking_ids` | `One2many(stock.picking)` | Transfers in this batch. Domained by `allowed_picking_ids` |
| `allowed_picking_ids` | `One2many(stock.picking)` | Computed: pickings available to add (same company, matching operation type, allowed states) |
| `move_ids` | `One2many(stock.move)` | Computed union of all picking moves |
| `move_line_ids` | `One2many(stock.move.line)` | Computed union of all picking move lines |

**State**

| Field | Type | Description |
|-------|------|-------------|
| `state` | `Selection` | `'draft'`, `'in_progress'`, `'done'`, `'cancel'`. Computed from picking states |

**Scheduling**

| Field | Type | Description |
|-------|------|-------------|
| `scheduled_date` | `Datetime` | Batch scheduled date. When set, propagates to all `picking_ids.scheduled_date` |
| `estimated_shipping_weight` | `Float` | Computed sum of package weights + line weights |
| `estimated_shipping_volume` | `Float` | Computed sum of package volumes + line volumes |

**UI Helpers**

| Field | Type | Description |
|-------|------|-------------|
| `show_check_availability` | `Boolean` | Show "Check Availability" button if any moves are unassigned |
| `show_allocation` | `Boolean` | Show "Allocation" button if reception report is available |
| `show_lots_text` | `Boolean` | Show lot/serial numbers as text (vs. separate column) |
| `properties` | `Properties` | Batch properties from picking type definition |

---

#### Key Methods

**`action_confirm()`**

Validates and starts the batch:
1. Raises `UserError` if no pickings in batch
2. Calls `picking_ids.action_confirm()` on all batch pickings
3. Sets state → `'in_progress'`

**`action_done()`**

Completes the batch — the primary batch processing action:
1. Identifies empty `assigned`/`waiting` pickings → detached from batch without cancelling
2. Runs `_sanity_check(separate_pickings=False)` on all non-cancelled/non-done pickings
3. Calls `picking.button_validate()` with `skip_sanity_check=True` and `pickings_to_detach` context
4. Posts batch transfer message to each picking's chatter
5. Batch state transitions to `'done'` automatically via `_compute_state()` once all pickings are done

```python
# Handle empty pickings
empty_waiting_pickings = pickings.filtered(
    lambda p: (p.state in ('waiting', 'confirmed') and has_no_quantity(p))
    or (p.state == 'assigned' and is_empty(p))
)
pickings = pickings - empty_waiting_pickings

# Skip sanity check, remove waiting pickings from batch
context = {'skip_sanity_check': True, 'pickings_to_detach': empty_waiting_pickings.ids}

return pickings.with_context(**context).button_validate()
```

**`action_cancel()`**

Sets batch state to `'cancel'` and unlinks all `picking_ids` from the batch (does NOT cancel the pickings themselves).

**`action_assign()`**

Calls `action_assign()` on all batch pickings.

**`action_put_in_pack()`**

Creates a package from done quantities in the first picking, following the same logic as `stock.picking._package_move_lines()`.

---

#### Write Behavior

When `write()` is called with `user_id`:
```python
self.picking_ids.assign_batch_user(vals['user_id'])
```

This assigns the batch operator to all pickings in the batch.

When `write()` removes all pickings from a batch in `in_progress` state:
```python
if not self.picking_ids:
    self.filtered(lambda b: b.state == 'in_progress').action_cancel()
```

---

### stock.picking — Batch Extension

**Model:** `stock.picking`

#### `batch_id` (inherited)

Pickings carry a `batch_id` Many2one pointing to their parent batch.

#### `batch_picking_count` (computed, inherited)

Number of batches a picking belongs to (typically 0 or 1).

---

## Picking Type Batch Constraints

The `stock.picking.type` model is extended with batch capacity limits:

| Field | Type | Description |
|-------|------|-------------|
| `batch_max_lines` | `Integer` | Maximum total move lines per batch for this operation type |
| `batch_max_pickings` | `Integer` | Maximum total pickings per batch for this operation type |

These are enforced via:
- `_is_picking_auto_mergeable(picking)` — when adding a picking to a batch
- `_are_pickings_auto_mergeable(n)` — when adding N pickings
- `_are_moves_auto_mergeable(n)` — when adding N moves

---

## Batch Auto-Closing Logic

`_compute_state()` automatically manages batch lifecycle:

```
If all pickings cancelled → batch state = 'cancel'
If all remaining pickings done/cancelled → batch state = 'done'
Otherwise → batch state unchanged
```

The batch transitions to `'done'` without an explicit `action_done()` call if all pickings are already completed when any one is validated.

---

## Wave vs. Standard Batch

| Attribute | Standard Batch | Wave |
|-----------|---------------|------|
| `is_wave` | `False` | `True` |
| Sequence code | `picking.batch` | `picking.wave` |
| Use case | Manual grouping of related pickings | Automated partial picking for pick-and-ship |
| Typical operator | Warehouse supervisor | Automated or warehouse operator |
| Constraint enforcement | Yes | Yes |

---

## Key Design Decisions

1. **Picking type constraint:** A batch can only contain pickings of a single operation type. This is enforced by `allowed_picking_ids` domain and `_sanity_check()`.

2. **Allowed states:** Pickings can be added to a batch only if in `'waiting'`, `'confirmed'`, `'assigned'` (or `'draft'` if the batch is also draft). This prevents adding already-done or cancelled pickings.

3. **Empty picking detachment:** When `action_done()` runs, pickings that have zero quantities to process are silently removed from the batch (via `pickings_to_detach` context) rather than blocking the batch completion. This supports partial fulfillment scenarios.

4. **Write propagation:** Writing to the batch propagates changes to pickings: `scheduled_date` writes to all pickings, `user_id` writes to all pickings via `assign_batch_user()`.

5. **No cascade delete:** If a batch is deleted, pickings are NOT deleted — they are simply unlinked from the batch. The batch is purely a grouping mechanism, not a parent that owns pickings.

6. **Mail tracking:** The batch inherits `mail.thread` and tracks state changes via the `mt_batch_state` subtype, keeping the chatter synchronized with batch lifecycle events.

---

## Notes

- The batch model uses `skip_sanity_check=True` context when calling `button_validate()` to avoid redundant checks — the sanity check is already run once in `action_done()`.
- `allowed_picking_ids` is computed fresh on each access, so pickings that change state or operation type after the batch is created will no longer appear in the allowed list.
- The `show_allocation` field depends on the `stock.group_reception_report` user group — only users with that permission see the allocation button.
- Batch transfers integrate with the `stock` module's `do_unreserve()` and `_action_assign()` to manage stock reservations at the batch level.
