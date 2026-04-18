---
tags: [odoo, odoo17, module, stock_picking_batch]
research_depth: medium
---

# Stock Picking Batch Module — Deep Reference

**Source:** `addons/stock_picking_batch/models/`

| File | Content |
|------|---------|
| `stock_picking_batch.py` | Main `stock.picking.batch` model |
| `stock_picking.py` | `StockPickingType` extensions + `StockPicking.batch_id` |
| `stock_move.py` | `StockMove` auto-batch hooks |
| `stock_move_line.py` | Reserved line management |

## Overview

Batch transfers (also called waves) allow grouping multiple pickings together so a single worker processes them as one unit. The module supports manual batching and automatic batching triggered by picking confirmation.

## Key Model: `stock.picking.batch`

**Source:** `stock_picking_batch.py` — `StockPickingBatch` class

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Batch reference (auto-generated: `batch sequence` or `wave sequence`) |
| `user_id` | Many2one | Responsible user |
| `company_id` | Many2one | Company |
| `picking_ids` | One2many | Pickings in this batch |
| `move_ids` | One2many | All stock moves (computed from pickings) |
| `move_line_ids` | One2many | All move lines (computed, writable via `_set_move_line_ids`) |
| `state` | Selection | `draft` / `in_progress` / `done` / `cancel` |
| `picking_type_id` | Many2one | Filter: all pickings must match this type |
| `picking_type_code` | Selection | Related picking type code (convenience) |
| `scheduled_date` | Datetime | Earliest scheduled date among all pickings |
| `is_wave` | Boolean | True for wave batches (separate sequence) |
| `show_check_availability` | Boolean | Show "Check Availability" button (computed) |
| `show_allocation` | Boolean | Show reception report allocation button |
| `allowed_picking_ids` | One2many | Pickings eligible to add (computed, respects state/type) |
| `show_set_qty_button` | Boolean | Deprecated |
| `show_clear_qty_button` | Boolean | Deprecated |
| `show_lots_text` | Boolean | Show lot numbers as text |

### State Machine

```
draft → in_progress → done
           ↓              ↓
        cancel         cancel
```

State transitions:
- `draft → in_progress`: `action_confirm()` — confirms all pickings
- `in_progress → done`: `action_done()` — validates all pickings
- Any → `cancel`: `action_cancel()` — cancels batch and removes pickings

### `_compute_state()` Logic

The batch state is auto-computed from pickings:
- If **all** pickings are `cancel`: batch becomes `cancel`
- If **all non-cancel** pickings are `done`: batch becomes `done`
- Otherwise: computed from user-set `state` field

### `action_done()` Validation Sequence

```python
def action_done(self):
    # 1. Detach empty/waiting pickings that can't be validated
    pickings = pickings.filtered(lambda p: p.state not in ('cancel', 'done'))
    empty_waiting = pickings.filtered(lambda p: (p.state in ('waiting','confirmed') and has_no_qty) or (p.state=='assigned' and is_empty))
    pickings -= empty_waiting

    # 2. Sanity check all pickings at once (batch mode)
    pickings._sanity_check(separate_pickings=False)

    # 3. Call button_validate on each picking
    #    Passes skip_sanity_check + pickings_to_detach in context
    return pickings.with_context(
        skip_sanity_check=True,
        pickings_to_detach=empty_waiting.ids + empty_pickings.ids
    ).button_validate()
```

### Name Sequences

| Batch Type | Sequence Code | Format |
|------------|--------------|--------|
| Normal batch | `picking.batch` | `BATCH/00001` |
| Wave | `picking.wave` | `WAVE/00001` |

## Automatic Batching

Auto-batching is triggered in `stock.picking` after `action_confirm()`:

```python
# Hook in stock_picking_batch/models/stock_picking.py
def action_confirm(self):
    res = super().action_confirm()
    for picking in self:
        picking._find_auto_batch()   # trigger auto-batch lookup
    return res
```

### `_find_auto_batch()` Logic

1. **Check eligibility**: picking must be `assigned`, `batch_id` empty, and satisfy type's `batch_max_lines` / `batch_max_pickings`.
2. **Find existing batch**: search for a compatible draft/in-progress batch (same type, same group-by criteria).
3. **Create new batch**: if no existing batch found, search for a compatible picking and create a new batch containing both.
4. **Auto-confirm**: if `batch_auto_confirm` on the picking type, new batches are auto-confirmed.

### Group-By Criteria

Configured on `stock.picking.type` via `stock_picking_batch` extensions:

| Field | Groups By |
|-------|----------|
| `batch_group_by_partner` | `partner_id` |
| `batch_group_by_destination` | `partner_id.country_id` |
| `batch_group_by_src_loc` | `location_id` |
| `batch_group_by_dest_loc` | `location_dest_id` |

### Batch Constraints

| Field | Check |
|-------|-------|
| `batch_max_lines` | `len(batch.move_ids) + len(new_picking.move_ids) <= max` |
| `batch_max_pickings` | `len(batch.picking_ids) + 1 <= max` (must be > 1) |

## Stock Move Integration

### `stock_picking_batch/models/stock_move.py`

```python
class StockMove(models.Model):
    _inherit = "stock.move"

    # Don't assign to a picking that is in a non-wave batch
    def _search_picking_for_assignation_domain(self):
        domain = super()._search_picking_for_assignation_domain()
        domain = expression.AND([domain, [
            '|',
            ('batch_id', '=', False),
            ('batch_id.is_wave', '=', False)
        ]])
        return domain

    def _action_cancel(self):
        # Remove picking from batch when cancelled (if batch still has other pickings)
        pass

    def _assign_picking_post_process(self, new=False):
        # Trigger auto-batch after picking assignment
        for picking in self.picking_id:
            picking._find_auto_batch()

    def write(self, vals):
        # Trigger auto-batch when move state becomes 'assigned'
        pass
```

## Stock Picking Integration

### `stock_picking_batch/models/stock_picking.py`

```python
class StockPicking(models.Model):
    batch_id = fields.Many2one('stock.picking.batch', string='Batch Transfer')

    def action_cancel(self):
        # Remove picking from batch if other pickings remain
        for picking in self:
            if picking.batch_id and any(picking.state != 'cancel' for ...):
                picking.batch_id = None

    def button_validate(self):
        # After validation: detach empty/waiting pickings
        # For backorders: re-run _find_auto_batch on each new backorder
        pass
```

## Batch Picking Type Extensions

**Source:** `stock_picking_batch/models/stock_picking.py` — `StockPickingType`

Extends `stock.picking.type` with batch-specific fields (see [Modules/stock_picking_type](Modules/stock_picking_type.md)).

## Key Constraints

### `batch_id` Write Behavior

When pickings are added to or removed from a batch:
- Empty batches in `in_progress` state are automatically cancelled.
- If `picking_type_id` not set on batch, it is auto-set to the first picking's type.
- When a batch user changes, all pickings are reassigned via `assign_batch_user()`.

### `allowed_picking_ids` Domain

Only pickings in these states can be added to a batch:

```python
allowed_picking_states = ['waiting', 'confirmed', 'assigned']
if batch.state == 'draft':
    allowed_picking_states.append('draft')
```

Plus: same `company_id`, same `picking_type_id` (if set).

## Action Methods on `stock.picking.batch`

| Method | Behavior |
|--------|---------|
| `action_confirm()` | Sanity check + confirm all pickings + set `state='in_progress'` |
| `action_cancel()` | Cancel batch, detach all pickings |
| `action_done()` | Validate all non-empty pickings via `button_validate()` |
| `action_assign()` | Call `action_assign()` on all pickings |
| `action_print()` | Print batch report |
| `action_put_in_pack()` | Put done quantities into a new package |
| `action_view_reception_report()` | Show reception report for batch |
| `action_open_label_layout()` | Print product or lot labels |
| `_sanity_check()` | Verify all pickings are still compatible with the batch |

## See Also

- [Modules/stock](Modules/stock.md) — `stock.picking`, `stock.move`
- [Modules/stock_picking_type](Modules/stock_picking_type.md) — picking type batch configuration
- [Modules/stock_warehouse](Modules/stock_warehouse.md) — warehouse picking types
