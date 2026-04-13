---
description: Intercepts mrp.production and mrp.workorder finalization to detect expired component lots, triggering a confirmation wizard before allowing consumption. Built on the product_expiry framework.
tags:
  - odoo
  - odoo19
  - mrp
  - product-expiry
  - manufacturing
  - lots
  - fifo
---

# mrp_product_expiry — Manufacturing Expiry

## Module Overview

**Technical module.** Augments `mrp` with expiry-date awareness for component lots consumed during manufacturing. Automatically installed when both `mrp` and `product_expiry` are present (`auto_install: True`).

| Attribute      | Value                                  |
|---------------|----------------------------------------|
| Name          | Manufacturing Expiry                   |
| Version       | 1.0                                    |
| Category      | Supply Chain/Manufacturing             |
| Depends       | `mrp`, `product_expiry`               |
| Auto-install  | `True`                                 |
| Author        | Odoo S.A.                              |
| License       | LGPL-3                                 |

---

## File Inventory

```
mrp_product_expiry/
├── __init__.py
├── __manifest__.py               ← depends, data, auto_install
├── models/
│   ├── __init__.py
│   └── mrp_production.py         ← pre_button_mark_done override
├── wizard/
│   ├── __init__.py
│   ├── confirm_expiry.py         ← ExpiryPickingConfirmation override
│   └── confirm_expiry_view.xml   ← form view extension
└── tests/
    ├── __init__.py
    └── test_mrp_product_expiry.py
```

---

## Architecture

`mrp_product_expiry` is a thin overlay. It does not introduce new database models or tables. Instead it:

1. Overrides `mrp.production.pre_button_mark_done()` to detect expired lots in component move lines and launch a wizard before `button_mark_done()` proceeds.
2. Inherits `expiry.picking.confirmation` (from `product_expiry`) to add `production_ids` and `workorder_id` fields and replace the generic picking buttons with manufacturing-specific ones.
3. Patches the XML form view to show/hide the correct action buttons depending on whether the wizard was opened from a picking, a production order, or a workorder.

```
mrp_production
  └─ pre_button_mark_done()        [override]
       └─ _check_expired_lots()
            └─ returns wizard action if any lot is expired
                 └─ expiry.picking.confirmation (extended)
                      ├─ confirm_produce()   → button_mark_done(skip_expired=True)
                      ├─ confirm_workorder() → record_production(skip_expired=True)
                      └─ (parent: process() → button_validate on pickings)
```

---

## Class: `MrpProduction` — `models/mrp_production.py`

Inherits: `mrp.production` (classic `_inherit`)

### `pre_button_mark_done()`

```python
def pre_button_mark_done(self):
    confirm_expired_lots = self._check_expired_lots()
    if confirm_expired_lots:
        return confirm_expired_lots
    return super().pre_button_mark_done()
```

Hooked into the MRP finalize pipeline. If `_check_expired_lots()` returns a wizard action dict, execution short-circuits — the production is NOT marked done yet. The user must confirm or cancel the wizard. On cancel (or if no expired lots), execution falls through to the parent's `pre_button_mark_done()`, which handles consumption warnings and other sanity checks.

**Context gate — `skip_expired`:**
The parent's `pre_button_mark_done()` is also called inside `confirm_produce()` and `confirm_workorder()` via `button_mark_done()`, but with `skip_expired=True` in context. This makes `_check_expired_lots()` return `False` immediately, preventing re-triggering of the same wizard in the same flow.

### `_check_expired_lots()`

```python
def _check_expired_lots(self):
    if self.env.context.get('skip_expired'):
        return False
    expired_lot_ids = self.move_raw_ids.move_line_ids.filtered(
        lambda ml: ml.lot_id.product_expiry_alert
    ).lot_id.ids
    if expired_lot_ids:
        return {
            'name': _('Confirmation'),
            'type': 'ir.actions.act_window',
            'res_model': 'expiry.picking.confirmation',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': self._get_expired_context(expired_lot_ids),
        }
```

**Detection logic:** Iterates over `move_raw_ids` (component consumption moves) and their `move_line_ids` (reservation/consumption lines). Checks each line's `lot_id.product_expiry_alert` computed boolean. Collects unique lot IDs and launches the wizard.

Only `move_line_ids` are checked — lines without a lot assigned (e.g., untracked components) are silently skipped. Only the `lot_id` records are collected (`.ids` on the recordset), not the full move line objects.

### `_get_expired_context(expired_lot_ids)`

```python
def _get_expired_context(self, expired_lot_ids):
    context = dict(self.env.context)
    context.update({
        'default_lot_ids': [(6, 0, expired_lot_ids)],
        'default_production_ids': self.ids,
    })
    return context
```

Sets two context keys that the wizard reads to populate its `lot_ids` and `production_ids` fields. The wizard reads these via `default_<field>` on the action context (not field defaults), since `expiry.picking.confirmation.lot_ids` is `required=True` and has no default.

`self.ids` is the current recordset of MO IDs — when called on a multi-record recordset (e.g., from a list action), `production_ids` in the wizard context correctly reflects all MOs involved.

---

## Class: `ExpiryPickingConfirmation` — `wizard/confirm_expiry.py`

Inherits: `expiry.picking.confirmation` (from `product_expiry`)

Parent model fields (inherited, from `product_expiry`):

| Field              | Type              | Notes                                                      |
|--------------------|-------------------|------------------------------------------------------------|
| `lot_ids`          | Many2many (`stock.lot`) | Required. Expired lots causing the wizard.          |
| `picking_ids`      | Many2many (`stock.picking`) | Pickings triggering the stock picking path.     |
| `description`      | Char              | Compute. Human-readable warning message.                   |
| `show_lots`        | Boolean           | Compute. True when multiple lots, to show the list widget. |

### New Fields Added by `mrp_product_expiry`

| Field              | Type              | Notes                                                      |
|--------------------|-------------------|------------------------------------------------------------|
| `production_ids`   | Many2many (`mrp.production`) | MO records that triggered the check. Readonly. |
| `workorder_id`     | Many2one (`mrp.workorder`)   | Workorder that triggered the check. Readonly.  |

### `_compute_descriptive_fields()`

```python
@api.depends('lot_ids')
def _compute_descriptive_fields(self):
    if self.production_ids or self.workorder_id:
        self.show_lots = len(self.lot_ids) > 1
        if self.show_lots:
            self.description = _(
                "You are going to use some expired components."
                "\nDo you confirm you want to proceed?"
            )
        else:
            self.description = _(
                "You are going to use the component %(product_name)s, %(lot_name)s which is expired."
                "\nDo you confirm you want to proceed?",
                product_name=self.lot_ids.product_id.display_name,
                lot_name=self.lot_ids.name,
            )
    else:
        super()._compute_descriptive_fields()
```

Replaces the message with a manufacturing-specific one ("use some expired components" instead of "deliver some product expired lots"). When only one lot is expired, includes the product name and lot name inline. When multiple are expired, shows the generic message and displays them via the `show_lots` list widget. Falls back to the parent (stock picking) message only when neither `production_ids` nor `workorder_id` is set — i.e., from the pure stock picking path.

### `confirm_produce()`

```python
def confirm_produce(self):
    ctx = dict(self.env.context, skip_expired=True)
    ctx.pop('default_lot_ids')
    return self.production_ids.with_context(ctx).button_mark_done()
```

Called from the "Confirm" button on the MO path. Sets `skip_expired=True` to suppress re-triggering, removes `default_lot_ids` (not needed downstream), and calls `button_mark_done()` on the production recordset. Returns whatever `button_mark_done()` returns — typically `True` on success, or a dict action from the backorder or consumption warning wizard.

### `confirm_workorder()`

```python
def confirm_workorder(self):
    ctx = dict(self.env.context, skip_expired=True)
    ctx.pop('default_lot_ids')
    return self.workorder_id.with_context(ctx).record_production()
```

Called from the "Confirm" button on the workorder path. Calls `record_production()` on the `mrp.workorder` record with the same `skip_expired=True` guard. `record_production()` is the standard workorder "Record Production" button action in the MRP base module — it handles workorder finalization including marking the operation done and creating finished product move lines.

---

## XML View Extension — `wizard/confirm_expiry_view.xml`

Extends `product_expiry.confirm_expiry_view` (the base form view for `expiry.picking.confirmation`).

| XPath expr                            | Change                                                         |
|--------------------------------------|----------------------------------------------------------------|
| `//field[@name='description']`       | Inject three `invisible="1"` fields: `picking_ids`, `production_ids`, `workorder_id`. Fields must be in the DOM for conditional `invisible` on buttons to resolve. |
| `//button[@name='process']`          | `invisible="not picking_ids"` — hide stock picking "Process" button when opened from MO or workorder. |
| `//button[@name='process_no_expired']`| Same `invisible` rule — hide "Process without expired" for manufacturing. |
| `//button[@special='cancel']`        | `invisible="production_ids"` — hide cancel when opened from MO (MO has its own "Discard"). Still shown for workorder path. |
| After `//button[@name='process']`    | Append three new buttons for manufacturing: `confirm_produce` (hotkey `q`, primary, invisible `not production_ids`), `Discard` (hotkey `x`, secondary, same visibility), `confirm_workorder` (no hotkey, primary, invisible `not workorder_id`). |

**Note on button visibility logic:** The `invisible` attribute on the base stock picking buttons uses `not picking_ids`. Since `production_ids` and `picking_ids` are `Many2many`, an empty recordset is falsy in XML domain expressions, so these correctly hide the stock picking actions when the wizard was opened from manufacturing. The cancel button check uses `production_ids` only — it remains visible for stock pickings and workorders, but is hidden for MOs.

---

## Cross-Module Integration

### `product_expiry` — `stock.lot.product_expiry_alert`

The expiry detection chain starts here. On `stock.lot`, the field is:

```python
product_expiry_alert = fields.Boolean(
    compute='_compute_product_expiry_alert',
    help="The Expiration Date has been reached."
)

@api.depends('expiration_date')
def _compute_product_expiry_alert(self):
    current_date = fields.Datetime.now()
    for lot in self:
        if lot.expiration_date:
            lot.product_expiry_alert = lot.expiration_date <= current_date
        else:
            lot.product_expiry_alert = False
```

`expiration_date` on the lot is itself computed from the product template's `expiration_time` (days) if not explicitly set at lot creation. The full chain:

```
product.product.expiration_time
  → stock.lot.expiration_date            (compute, set at lot creation if not provided)
  → stock.lot.product_expiry_alert      (compute: expiration_date <= now)
  → stock.move.line.is_expired           (related: lot_id.product_expiry_alert)
  → mrp.production._check_expired_lots() (checks move_line_ids.lot_id.product_expiry_alert)
```

`product_expiry` also defines `_alert_date_exceeded()` (scheduled action on `stock.lot`) that creates `mail.activity` records on lots whose `alert_date` has been reached, and writes `product_expiry_reminded = True` to prevent duplicate activities.

### `product_expiry` — `expiry.picking.confirmation` base

The parent wizard model provides `lot_ids`, `picking_ids`, `description`, `show_lots`, the base `_compute_descriptive_fields()`, and `process()` / `process_no_expired()` actions for stock pickings. `mrp_product_expiry` extends this with manufacturing-specific fields and actions, overriding `_compute_descriptive_fields()` and adding `confirm_produce()` and `confirm_workorder()`.

### `product_expiry` — `stock.move` FEFO overrides

`product_expiry/models/stock_move.py` overrides `_update_reserved_quantity()` and `_get_available_quantity()` to pass the move's `date` as `with_expiration` context when the product uses expiration dates. This causes the stock quant domain to exclude quants past their `removal_date`. During MRP production consumption this ensures:

1. **FEFO reservation:** When the production is confirmed, stock moves reserve from quants sorted by `removal_date ASC`, so earliest-expiry lots are consumed first.
2. **Removal date cutoff:** Once a quant's `removal_date` has passed, it is excluded from reserved quantity even if not yet technically expired.

`mrp_product_expiry` adds a human-gate on top: even if the system reserved an expired lot under FEFO rules, the user must still explicitly confirm before the MO can be marked done.

### `mrp` — `mrp.production` finalize pipeline

```
button_mark_done()
  └─ pre_button_mark_done()          ← mrp override point
       ├─ _button_mark_done_sanity_checks()
       ├─ _auto_production_checks()
       ├─ _set_quantities()
       ├─ [HERE: mrp_product_expiry._check_expired_lots()]
       └─ ... (consumption warnings, backorder wizard, etc.)
  └─ workorder_ids.button_finish()
  └─ _post_inventory()
  └─ write({state: 'done'})
```

Since `mrp_product_expiry.pre_button_mark_done()` inserts itself between the MRP framework's own checks and the state transition, it is guaranteed to only see productions the user intends to finish — upstream sanity checks (lot generation, quantity sanity, etc.) have already passed.

### `mrp` — `mrp.workorder` workorder path

The `workorder_id` field in the wizard and `confirm_workorder()` method target `mrp.workorder` records. When a workorder is recorded via `record_production()`, it internally calls `button_mark_done()` on the linked production. The `skip_expired=True` context is inherited through this call chain, so no re-trigger of the expiry wizard occurs.

---

## Edge Cases

**MO with no component move lines:** `_check_expired_lots()` iterates over `move_raw_ids.move_line_ids`. If there are no move lines yet (production not reserved), the filtered set is empty and no wizard fires. This is correct — the user has not yet consumed anything.

**MO where lot was reserved before expiry but confirmed after expiry:** The quant reservation happened under FEFO rules before the lot expired. `move_line_ids` still contains the line with the expired lot. `_check_expired_lots()` detects it and fires the wizard, requiring explicit user confirmation even though the system correctly reserved it earlier.

**Workorder recorded after production's expired lots were already detected:** The production already passed `_check_expired_lots()`. The workorder's `confirm_workorder()` passes `skip_expired=True`, so no re-trigger occurs. This prevents double-wizard scenarios.

**Concurrent modification of lot expiry between wizard open and confirm:** If the lot's `expiration_date` is updated after the wizard loads but before `confirm_produce()` is called, the production finalizes without error — `skip_expired=True` bypasses the check.

**Multiple MOs in wizard context:** When `button_mark_done()` is called on a multi-record production recordset, `pre_button_mark_done()` runs on each. After the first confirmation sets `skip_expired=True`, subsequent MOs bypass the wizard even if they also contain expired lots. This is a known limitation — the context records only which lots were expired at the time of the first MO's check.

**MO with no tracked components:** Only `move_line_ids` with an assigned `lot_id` are checked. Untracked component lines are ignored. If all components are untracked, no wizard fires.

---

## Performance Considerations

| Concern | Detail |
|---------|--------|
| Recordset filtering | `_check_expired_lots()` calls `.filtered()` on `move_line_ids`, which accesses `lot_id.product_expiry_alert`. Each access triggers a browse of `stock.lot`. For MOs with many component lines from many lots, this can generate an N+1 lot read pattern. Prefetching `lot_id` on the move lines before the filter would eliminate the N+1. |
| Transient wizard | `expiry.picking.confirmation` is a `TransientModel`. Transient records are cleaned up by `ir.cron.autovacuum()`. They do not create database contention. |
| Super call depth | Both `mrp_production.py` and `confirm_expiry.py` call `super()` in a two-level chain — no risk of deep recursion. |
| `record_production()` call | `confirm_workorder()` returns whatever `record_production()` returns (action dict or `True`). No additional wrapping or error handling is applied. |

---

## Test Coverage — `tests/test_mrp_product_expiry.py`

Two test cases subclassing `TestStockCommon` (from `stock/tests/common.py`):

| Test | Scenario | Asserts |
|------|----------|---------|
| `test_01_product_produce` | MO with a non-expired lot as component. MO is confirmed, quantity set, lot assigned to move line, `button_mark_done()` called. | Returns `True` directly — no wizard. |
| `test_02_product_produce_using_expired` | MO with an expired lot (created by setting `expiration_date = today - 10 days`). Same flow as above with the expired lot. | Returns action dict with `res_model == 'expiry.picking.confirmation'`. |

Test product configuration:

```python
{
    'name': 'Apple',
    'is_storable': True,
    'tracking': 'lot',
    'use_expiration_date': True,
    'expiration_time': 10,   # expiration_date = now + 10 days
    'use_time': 5,           # use_date = expiration_date - 5 days
    'removal_time': 8,        # removal_date = expiration_date - 8 days
    'alert_time': 4,          # alert_date = expiration_date - 4 days
}
```

The expired lot is created normally via `Form`, then edited to set `expiration_date` to `datetime.today() - timedelta(days=10)`, which is before `now`, so `product_expiry_alert` evaluates to `True`.

---

## Related Documentation

- [Modules/MRP](modules/mrp.md) — Manufacturing orders and workorders
- [Modules/product_expiry](modules/product_expiry.md) — Product lot expiry tracking, `stock.lot` expiry fields, base wizard
- [Modules/Stock](modules/stock.md) — Lot numbers, `stock.move`, `stock.move.line`, FEFO reservation
- [Modules/Stock](modules/stock.md) — `stock.quant`, `stock.picking`, `stock.move` full field reference

---

*Documented: 2026-04-11*
