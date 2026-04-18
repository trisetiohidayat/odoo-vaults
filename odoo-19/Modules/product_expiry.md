---
type: module
module: product_expiry
tags: [odoo, odoo19, stock, product, expiry, lot, fefo, traceability]
created: 2026-04-06
updated: 2026-04-11
---

# Products Expiration Date

## Overview

| Property | Value |
|----------|-------|
| **Name** | Products Expiration Date |
| **Technical** | `product_expiry` |
| **Category** | Supply Chain/Inventory |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Depends** | `stock` |
| **Post-init hook** | `_enable_tracking_numbers` |

## Module Purpose

Tracks expiration and shelf-life dates on products and production lots. Supports four distinct tracked dates per lot, implements **FEFO (First Expiry First Out)** removal strategy, and generates automated activity reminders via the Odoo scheduler. Core use cases are food, pharmaceutical, and cosmetic industries where regulatory compliance demands precise lot dating.

## Data Files

| File | Purpose |
|------|---------|
| `security/ir.model.access.csv` | ACL for `expiry.picking.confirmation` wizard |
| `security/stock_security.xml` | Creates `group_expiry_date_on_delivery_slip` group |
| `data/product_expiry_data.xml` | Registers `product.removal` record: `fefo` method |
| `views/production_lot_views.xml` | Form/tree/kanban/search views for lots |
| `views/product_template_views.xml` | Expiry time delta fields on product template |
| `views/stock_move_views.xml` | Expiry date columns on move lines |
| `views/stock_quant_views.xml` | Removal date/available qty on quants |
| `views/res_config_settings_views.xml` | Group toggles in settings |
| `wizard/confirm_expiry_view.xml` | Modal confirmation when validating picking with expired lots |
| `report/report_deliveryslip.xml` | Adds expiration date column to delivery report |
| `report/report_lot_barcode.xml` | Prints best-before and expiry on lot label barcodes |

## Architecture — Models Extended

```
product.template         → expiration time delta fields + use_expiration_date flag
product.product          → _compute_quantities_dict with expiration context
stock.lot                → 4 expiry datetime fields + alert flag + scheduler method
stock.quant              → expiry-related fields + FEFO strategy + available qty override
stock.move               → expiry-aware reservation/quantity + lot generation hooks
stock.move.line          → stored expiration_date/removal_date columns + compute methods
stock.picking            → pre-action validation hook for expired lot detection
stock.rule               → cron scheduler integration for _alert_date_exceeded
res.config.settings      → group_expiry_date_on_delivery_slip toggle
```

---

# L1 — Field Signatures and Method Declarations

## `product.template` Fields

| Field | Type | Default | Help |
|-------|------|---------|------|
| `use_expiration_date` | Boolean | `False` | Enables expiry tracking on lots. Only visible when `tracking != 'none'`. |
| `expiration_time` | Integer | `False` | Days after receipt after which goods become dangerous. Used to auto-compute lot expiration_date. |
| `use_time` | Integer | `False` | Days before expiration when quality deterioration begins. |
| `removal_time` | Integer | `False` | Days before expiration when goods should leave Fresh On Hand stock. |
| `alert_time` | Integer | `False` | Days before expiration to raise a scheduler alert. |

All four time fields are relative deltas against `expiration_time`. If a delta is `0`, the corresponding date equals `expiration_date`.

## `product.product` Fields

| Field | Type | Default | Help |
|-------|------|---------|------|
| `free_qty` | Float | inherited | Redefined here to document expiry-influenced computation |
| `virtual_available` | Float | inherited | Redefined here to document expiry-influenced computation |

Both are overriden just for updated help text. The actual computation is delegated to `stock` via `with_context(with_expiration=datetime.date.today())`.

## `stock.lot` Fields

| Field | Type | Compute/Store | Help |
|-------|------|---------------|------|
| `use_expiration_date` | Boolean | Related (`product_id.use_expiration_date`) | Gateway field — if False, all other date fields are cleared |
| `expiration_date` | Datetime | Compute + Store, readonly=False | Date goods become dangerous. Auto-set from product's `expiration_time` on lot creation if not provided. |
| `use_date` | Datetime | Compute + Store, readonly=False | Date quality starts deteriorating |
| `removal_date` | Datetime | Compute + Store, readonly=False | Date to remove from Fresh On Hand (FEFO ordering) |
| `alert_date` | Datetime | Compute + Store, readonly=False | Date to trigger scheduler alert |
| `product_expiry_alert` | Boolean | Compute | `True` when `expiration_date <= now` |
| `product_expiry_reminded` | Boolean | Plain | Prevents duplicate scheduler activity creation |

## `stock.quant` Fields

| Field | Type | Help |
|-------|------|------|
| `expiration_date` | Datetime (related, store=True) | Mirrors `lot_id.expiration_date` |
| `removal_date` | Datetime (related, store=True) | Mirrors `lot_id.removal_date` |
| `use_expiration_date` | Boolean (related) | Mirrors `product_id.use_expiration_date` |
| `available_quantity` | Float | On-hand qty minus reserved minus any quantity past `removal_date` |

## `stock.move.line` Fields

| Field | Type | Compute/Store | Help |
|-------|------|---------------|------|
| `expiration_date` | Datetime | Compute + Store | Mirrors lot's expiration_date, or computes from product delta. Stored as `timestamp` column. |
| `removal_date` | Datetime | Compute + Store | Derived from expiration_date minus product removal_time. Stored as `timestamp` column. |
| `is_expired` | Boolean | Related (`lot_id.product_expiry_alert`) | Shortcut for template rendering |
| `use_expiration_date` | Boolean | Related (`product_id.use_expiration_date`) | Controls UI visibility |

## `stock.move` Methods (Extension)

| Method | Signature | Purpose |
|--------|-----------|---------|
| `action_generate_lot_line_vals` | `(context_data, mode, first_lot, count, lot_text) -> vals_list` | Auto-sets `expiration_date` on generated lot lines during picking creation |
| `_generate_serial_move_line_commands` | `(field_data, location_dest_id, origin_move_line) -> commands` | Injects `expiration_date` into serial-number move line commands |
| `_convert_string_into_field_data` | `(string, options) -> dict\|string` | Parses date strings (e.g., "2025-05-15") into `{'expiration_date': datetime}` |
| `_get_formating_options` | `(strings) -> dict` | Detects day-first vs year-first from user locale for date parsing |
| `_update_reserved_quantity` | `(need, loc, lot, pkg, owner, strict)` | Delegates to `with_context(with_expiration=self.date)` |
| `_get_available_quantity` | `(loc, lot, pkg, owner, strict, allow_neg)` | Delegates with expiration context |

## `stock.rule` Methods (Extension)

| Method | Signature | Purpose |
|--------|-----------|---------|
| `_run_scheduler_tasks` | `(use_new_cursor=False, company_id=False)` | Calls `self.env['stock.lot']._alert_date_exceeded()` after super() |
| `_get_scheduler_tasks_to_do` | `() -> int` | Returns `super() + 1` to account for expiry alert task |

## `stock.picking` Methods (Extension)

| Method | Signature | Purpose |
|--------|-----------|---------|
| `_pre_action_done_hook` | `() -> True\|action` | Intercepts `button_validate`; triggers expired-lot wizard |
| `_check_expired_lots` | `() -> recordset` | Returns pickings containing move lines with expired lots or past `removal_date` |
| `_action_generate_expired_wizard` | `() -> action` | Opens `expiry.picking.confirmation` wizard |

## `stock.lot._alert_date_exceeded()` — Scheduler Entry Point

```python
@api.model
def _alert_date_exceeded(self):
    alert_lots = self.env['stock.lot'].search([
        ('alert_date', '<=', fields.Date.today()),
        ('product_expiry_reminded', '=', False)])
    # filter to only lots with positive qty in internal locations
    lot_stock_quants = self.env['stock.quant'].search([
        ('lot_id', 'in', alert_lots.ids),
        ('quantity', '>', 0),
        ('location_id.usage', '=', 'internal')])
    alert_lots = lot_stock_quants.mapped('lot_id')
    for lot in alert_lots:
        lot.activity_schedule('mail.mail_activity_data_todo', ...)
    alert_lots.write({'product_expiry_reminded': True})
```

---

# L2 — Field Types, Defaults, Constraints, and Rationale

## Expiry Time Delta Fields on `product.template`

- **Type:** `Integer` — stored as columns on `product_template`
- **Default:** `False` (undefined / 0 behavior varies by field)
- **Constraint:** All must be `>= 0` if set. Odoo does not enforce this at ORM level; invalid values result in dates that equal or follow `expiration_date`.
- **Rationale:** Each field represents a **countdown offset** from the lot's absolute `expiration_date`. The template-level fields act as reusable defaults for all lots of that product.

### Date Equality Edge Case

When any time delta is `0`, the corresponding computed date equals `expiration_date`. The test `test_apply_same_date_on_expiry_fields` confirms this:
```python
expiration_time = 10, use_time=0, removal_time=0, alert_time=0
lot.use_date      == lot.expiration_date   # True
lot.removal_date  == lot.expiration_date   # True
lot.alert_date    == lot.expiration_date   # True
```

## `expiration_date` on `stock.lot`

- **Type:** `Datetime` — stored column
- **Compute trigger:** `@api.depends('product_id')` only fires when `expiration_date` is falsy at write time
- **Auto-set behavior:** If a lot is created without an explicit `expiration_date` and the product has `use_expiration_date=True`, the date is auto-set to `now + expiration_time days`
- **Editable:** `readonly=False` — users can override the computed value directly on the lot form

## `product_expiry_alert` — Boolean Flag

Computed via `@api.depends('expiration_date')` against `fields.Datetime.now()`. This is a **recomputed-on-read** flag; it does not require a write to update. It is used in:
- UI badge rendering (Kanban "Expired" pill)
- Search filter `expiration_alerts` domain: `('alert_date', '<=', 'now')`
- Picking validation logic: `ml.lot_id.product_expiry_alert or (ml.removal_date and ml.removal_date <= now)`

## `product_expiry_reminded` — Idempotency Guard

Once set to `True`, `_alert_date_exceeded()` will skip that lot on all subsequent scheduler runs, even if the `alert_date` is changed to a future date. This is an intentional design choice: the flag is a **one-time dismiss**, not a rolling alarm. Clearing the flag requires a manual write or a reset workflow.

## `stock.move.line` Stored Columns

Both `expiration_date` and `removal_date` are stored as `timestamp` columns via `_auto_init()` with `create_column()` to avoid ORM memory churn during module install. The columns are created with `NOT NULL`-compatible types; they remain nullable because the fields are optional.

---

# L3 — Cross-Model Relationships, Override Patterns, and Workflow Triggers

## Workflow: Lot Creation During Receipt

```
stock.picking (receipt)
  └─ stock.move.action_generate_lot_line_vals()
       └─ Adds expiration_date = picking.scheduled_date + product.expiration_time days
  └─ stock.move._generate_serial_move_line_commands()
       └─ Sets expiration_date = now + product.expiration_time days (for serial numbers)
  └─ stock.move.line._prepare_new_lot_vals()
       └─ Copies expiration_date into lot record at transfer time
```

The two methods are differentiated:
- `action_generate_lot_line_vals` handles **batch lot generation** (e.g., receiving 50 units with explicit lot names from the UI)
- `_generate_serial_move_line_commands` handles **single-unit serial number** generation

## Workflow: Picking Validation — Expired Lot Gate

```
stock.picking.button_validate()
  └─ _pre_action_done_hook()
       └─ If not skip_expired context:
            └─ _check_expired_lots()
                 └─ Returns pickings with:
                      ml.lot_id.product_expiry_alert == True
                      OR (ml.removal_date AND ml.removal_date <= now)
            └─ If any expired found: _action_generate_expired_wizard()
                 └─ Opens expiry.picking.confirmation modal
```

Two confirmation paths from the wizard:

| Button | Behavior |
|--------|---------|
| `process` | Validates picking with `skip_expired=True` context — expired lots are shipped |
| `process_no_expired` | Unlinks move lines with `removal_date < now`, then validates remaining |

## Workflow: FEFO Reservation

```
stock.move._update_reserved_quantity()
  └─ Passes with_context(with_expiration=self.date)
       └─ stock.quant _update_reserved_quantity() uses:
            └─ _get_removal_strategy_order('fefo')
                 └─ Returns 'removal_date, in_date, id'
```

The `with_expiration` context is used by `stock.quant._update_reserved_quantity` and `stock.quant._get_available_quantity` in `stock` to filter quants by expiry status when computing what's reservable.

## Workflow: Scheduler Alert

```
ir.cron (stock scheduler)
  └─ stock.rule._run_scheduler_tasks()
       └─ Calls stock.lot._alert_date_exceeded()
            └─ Filters to lots with alert_date <= today AND product_expiry_reminded == False
            └─ Further filters to lots with qty > 0 in internal locations
            └─ Schedules mail.activity on lot record
            └─ Sets product_expiry_reminded = True
```

The scheduler is part of the stock module's nightly cron. The `+1` in `_get_scheduler_tasks_to_do` ensures the scheduler does not report "no tasks" when only expiry alerts need to run.

## Workflow: Quantity Computation with Expiry

```
product.product._compute_quantities_dict()
  └─ Called with with_context(with_expiration=datetime.date.today())
       └─ stock.quant _compute_available_quantity()
            └─ For each quant where use_expiration_date AND removal_date <= now:
                 └─ available_quantity = 0
```

The `report.stock.quantity` SQL override in `report/report_stock_quantity.py` further adjusts the reporting query:
```sql
CASE WHEN q.removal_date IS NOT NULL
     AND q.removal_date::date <= now()::date
     AND date >= now()::date   -- still has a reservation
THEN q.reserved_quantity
ELSE q.quantity END
```
This ensures that **reserved quantities of expired quants are still counted** (the stock is already allocated), but **unreserved expired quantities are not counted** as available stock.

## Cross-Model: GS1 Barcode Encoding

`stock.quant._get_gs1_barcode()` appends GS1 Application Identifier codes:
- **AI `17`**: Expiration date (`'YYMMDD'` format)
- **AI `15`**: Best-before date (`'YYMMDD'` format)

These codes are embedded in the datamatrix barcode on lot labels for scanning by warehouse logistics systems.

## Cross-Model: Delivery Report

`stock.report_delivery_document` is extended to append an "Expiration Date" column. This is gated behind the `product_expiry.group_expiry_date_on_delivery_slip` group, which is itself gated behind `stock.group_lot_on_delivery_slip`.

---

# L4 — Performance, Odoo 18 to 19 Changes, Security, and Edge Cases

## Performance

### `_alert_date_exceeded` — Two-Pass Search

The method performs two separate `search()` calls:
1. First search finds all lots with `alert_date <= today` that have not been reminded — potentially thousands in large deployments
2. Second search filters those lots through `stock.quant` to find only lots with **positive quantity in internal locations**

On warehouses with many lots but low inventory, the second filter significantly reduces activity creation. Conversely, a warehouse with high inventory of lots approaching alert date will create many `mail.activity` records in a single cron run, which can be resource-intensive.

**Mitigation:** The `product_expiry_reminded` guard prevents repeated scheduling, but does not prevent mass activity creation on first run.

### Stored Computed Fields on `stock.lot`

The four date fields (`expiration_date`, `use_date`, `removal_date`, `alert_date`) are all stored. This means:
- **Write-time cost:** When `expiration_date` is changed, all three derived dates are computed and written in a single transaction — acceptable.
- **Read-time benefit:** All date displays (list, kanban, form, search) read directly from stored columns — no on-demand recomputation.
- **Auto-init memory risk:** The `_auto_init()` on `stock.move.line` uses raw SQL `create_column()` to pre-create the stored columns before the ORM tries to `compute()` them, avoiding a full-table write during module install on large databases.

### FEFO Sorting and Quant Reservation

The FEFO removal strategy uses `'removal_date, in_date, id'` as the `order by` clause. On large quant tables, this sort requires an index on `removal_date`. Odoo's `stock` module does not add a dedicated index for `removal_date` — query performance for FEFO-priority reservations degrades linearly with quant table size.

## Historical Changes: Odoo 18 to Odoo 19

### New in Odoo 19

1. **`_auto_init()` column pre-creation on `stock.move.line`**: The `expiration_date` and `removal_date` columns are now explicitly created via SQL on install. In earlier versions these were computed-only, which caused memory issues on populated databases during upgrade.

2. **`_compute_quantities_dict` context injection on `product.product`**: The `_compute_quantities_dict` override now passes `with_context(with_expiration=datetime.date.today())`. Previously, expiry-aware quantity filtering was only on `stock.quant` directly.

3. **`_convert_string_into_field_data` date parsing**: Lot creation via barcode scanner or serial-number input now supports parsing arbitrary date strings (e.g., scanning a label with "EXP 2025-12-31" embedded). This was added to support GS1 barcode workflows.

4. **`display_name` extension with expiry suffixes**: Lots now display `--Expired--` or `--Expire on <date>--` in their name when rendered with `formatted_display_name` context. This is used in traceability and reporting views.

5. **`stock_forecasted` report extension**: The forecasted stock view now shows per-removal-date "To Remove" lines, a major UX enhancement for warehouse managers.

### Behavioral Changes

- **Delivery validation**: The confirmation wizard now offers two buttons (Confirm vs. Proceed except expired), giving warehouse staff the choice to ship expired goods or only valid stock. Previously the wizard was a simple confirmation.
- **`product_expiry_reminded` flag scope**: The flag now prevents re-alerting even if `alert_date` is changed to a past date after the first alert. This was not explicitly documented before.
- **`removal_date` as `available_quantity=0` trigger**: Quants past their removal date now have their `available_quantity` zeroed rather than being excluded via domain. This changes the behavior of `qty_available` computations for these products.

## Security

### ACL on Wizard Model

`expiry.picking.confirmation` has `perm_create=1` (it is a TransientModel, so this is expected for the wizard). The model is accessible to any user who can validate pickings — effectively `stock.group_stock_user` and above.

### Group Hierarchy

```
base.group_user
  └─ implied_ids: stock.group_production_lot   (added by _enable_tracking_numbers hook)
  └─ implied_ids: stock.group_stock_user
```

`group_expiry_date_on_delivery_slip` is a standalone group created in `stock_security.xml`. It is not implied by `group_production_lot`. Users must be explicitly granted access to see expiration dates on printed delivery slips.

### Information Disclosure

The `expiration_date` and `alert_date` fields are visible on `stock.lot` form/list views. A user with read access to lots but not to the product's cost price can still infer shelf-life and procurement margins from expiry patterns. Consider field group restrictions (`groups="stock.group_stock_user"`) if this is a concern in your deployment.

## Edge Cases

### Lot with `expiration_date = False` but Product Uses Expiry

A lot created without an `expiration_date` when `use_expiration_date=True` is treated as **non-perishable**. It will not trigger the expired lot wizard on picking validation. `product_expiry_alert` evaluates to `False`. The lot's `available_quantity` is unaffected.

### `removal_date = False` but Past `expiration_date`

In this scenario, `product_expiry_alert = True` (expired), but `available_quantity` is not zeroed because the check is `removal_date <= now`. The lot shows an "Expired" badge but still counts as available stock. This is intentional — it allows businesses to decide whether expired stock is usable based on their own policies.

### Setting `removal_time = 0`

`removal_date = expiration_date - 0 = expiration_date`. Such quants are immediately at removal threshold upon lot creation. The "To remove now" line in the forecasted report will show these quantities.

### Scheduler Fires on Unconfirmed Pickings

`_alert_date_exceeded` only filters lots with `quantity > 0` in `stock.quant`. A lot that is fully reserved on an outgoing picking (quantity = 0 in stock but the picking is not yet done) will not receive an alert, even if its `alert_date` has passed. The lot will be picked up on the next scheduler run after the picking is completed (returning the quantity to stock).

### Multi-company Environment

The scheduler method `stock.lot._alert_date_exceeded()` runs as `SUPERUSER_ID` when triggered by cron, meaning it processes lots from all companies. The activity's `user_id` is resolved via `lot.product_id.with_company(lot.company_id).responsible_id` — falling back to `product.responsible_id` then `SUPERUSER_ID`. If `responsible_id` is not set, the activity is created on the admin account.

### Serial Number vs Lot Tracking

For serial-number-tracked products, each unit is its own lot with quantity 1. The expiration date fields apply identically, but FEFO ordering at the individual serial level means the oldest serial is always picked first. `_generate_serial_move_line_commands` sets `expiration_date` per-unit from the product's `expiration_time`.

### Date String Parsing Format Detection

`_get_formating_options` uses a heuristic cascade:
1. If the first date token contains letters → month-first format (e.g., "Jan 15 2025")
2. If `value_1 > 31` → year-first (e.g., "2025-01-15")
3. If `value_1 > 12` and `value_2` has letters or `<= 12` → day-first (e.g., "15-01-2025")
4. Otherwise → read the user's lang date format

This handles most ISO and locale-specific formats but can misparse ambiguous strings like "01-02-2025" in en_US locale.

## Wizard: `expiry.picking.confirmation`

**Model:** `expiry.picking.confirmation` — TransientModel

| Field | Type | Compute | Purpose |
|-------|------|---------|---------|
| `lot_ids` | Many2many(`stock.lot`) | readonly | Expired lots in the picking |
| `picking_ids` | Many2many(`stock.picking`) | readonly | Pickings being validated |
| `description` | Char | `_compute_descriptive_fields` | Dynamic message string |
| `show_lots` | Boolean | `_compute_descriptive_fields` | Controls lot list visibility (>1 lot) |

**`process()`**: Re-enters picking validation with `skip_expired=True`. Used when the warehouse manager explicitly accepts expired stock.

**`process_no_expired()`**: Unlinks move lines whose `removal_date < now`, then calls `button_validate()` on remaining lines. This is destructive — it removes move lines from the picking without unlinking the move itself. The unlinked line's reserved quantity is returned to the quant.

## Key Method: `_compute_dates` — Date Cascade Logic

The method has two distinct behaviors:

**Case 1 — On lot creation or when `expiration_date` changes:**
```python
lot.use_date     = lot.expiration_date - product_tmpl.use_time days
lot.removal_date = lot.expiration_date - product_tmpl.removal_time days
lot.alert_date   = lot.expiration_date - product_tmpl.alert_time days
```
Fires when: `lot._origin.product_id != lot.product_id` OR all three derived dates are unset OR `lot._origin.expiration_date` is falsy.

**Case 2 — When `expiration_date` is shifted (delta-based):**
```python
time_delta = lot.expiration_date - lot._origin.expiration_date
lot.use_date     = lot._origin.use_date     + time_delta if lot._origin.use_date
lot.removal_date = lot._origin.removal_date + time_delta if lot._origin.removal_date
lot.alert_date   = lot._origin.alert_date   + time_delta if lot._origin.alert_date
```
This preserves manually-set derived dates proportional to the shift.

**Important:** If a user manually sets `use_date` to a value different from `expiration_date - use_time`, and then changes `expiration_date`, the `use_date` will be proportionally shifted rather than recomputed from the delta. This is a deliberate behavior to avoid overwriting intentional manual adjustments.

## Related Modules

- `stock` — Core inventory. `product_expiry` extends lot, quant, move, move line, picking, rule
- `stock_account` — Coordinates with `product_expiry` for valuation entries on expired lot scrapping
- `mrp_product_expiry` — Extends `mrp.production` with expiry-on-production functionality
- `sale_stock_product_expiry` — Handles expiry on sale-to-delivery flow
- `delivery` — Delivery report inherits expiry date columns

## See Also

- [Modules/stock](Modules/Stock.md)
- [Modules/product](Modules/Product.md)
- [Core/API](Core/API.md) — `@api.depends`, `@api.model`, compute field patterns
- [Patterns/Security Patterns](Patterns/Security Patterns.md) — ACL CSV, ir.rule, field groups
