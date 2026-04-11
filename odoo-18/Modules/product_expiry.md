---
Module: product_expiry
Version: 18.0.0
Type: addon
Tags: #odoo18 #product #expiry #stock #lot
---

## Overview

Manages product shelf-life and expiry tracking. Adds expiration/use/removal/alert dates to `stock.lot`, validates delivery against expired lots, supports FEFO removal strategy, and schedules activity alerts.

**Depends:** `product`, `stock`

**Key Behavior:** Dates are auto-computed from product template expiry intervals when a lot is created. Delivery validation blocks on expired lots via a confirmation wizard. GS1 barcodes encode expiry dates in AI codes 15/17.

---

## Models

### `product.template` (Inherited)

**Inherited from:** `product.template`

| Field | Type | Note |
|-------|------|------|
| `use_expiration_date` | Boolean | Enable expiry date tracking |
| `expiration_time` | Integer | Days after receipt before expiry |
| `use_time` | Integer | Days before expiry when best-before starts |
| `removal_time` | Integer | Days before expiry when removal begins |
| `alert_time` | Integer | Days before expiry when alert triggers |

### `stock.lot` (Inherited)

**Inherited from:** `stock.lot`

| Field | Type | Note |
|-------|------|------|
| `use_expiration_date` | Boolean | Related from `product_id` |
| `expiration_date` | Datetime | Compute from product expiry_time on create; stored, writable |
| `use_date` | Datetime | Best-before date; computed from `expiration_date - use_time` |
| `removal_date` | Datetime | FEFO removal date; computed from `expiration_date - removal_time` |
| `alert_date` | Datetime | Alert trigger date; computed from `expiration_date - alert_time` |
| `product_expiry_alert` | Boolean (compute) | True when `expiration_date <= now` |
| `product_expiry_reminded` | Boolean | Prevents duplicate activity scheduling |

| Method | Returns | Note |
|--------|---------|------|
| `_compute_expiration_date()` | — | Sets default expiration date from product `expiration_time` on lot creation |
| `_compute_dates()` | — | Computes `use_date`, `removal_date`, `alert_date` from `expiration_date` delta |
| `_compute_product_expiry_alert()` | — | Sets alert flag when lot is expired |
| `_alert_date_exceeded()` | — | Scheduled action: creates activities on lots whose `alert_date` passed and not yet reminded |

### `stock.quant` (Inherited)

**Inherited from:** `stock.quant`

| Field | Type | Note |
|-------|------|------|
| `expiration_date` | Datetime | Related from `lot_id.expiration_date` (stored) |
| `removal_date` | Datetime | Related from `lot_id.removal_date` (stored) |
| `use_expiration_date` | Boolean | Related from `product_id` |

| Method | Returns | Note |
|--------|---------|------|
| `_get_gs1_barcode(...)` | str | Prepends AI code `17` (expiry) and `15` (best-before) to GS1 barcode |
| `_get_removal_strategy_order(removal_strategy)` | str | Returns `'removal_date, in_date, id'` for FEFO strategy |

### `stock.picking` (Inherited)

**Inherited from:** `stock.picking`

| Method | Returns | Note |
|--------|---------|------|
| `_pre_action_done_hook()` | Mixed | Checks for expired lots; triggers `_action_generate_expired_wizard` if any |
| `_check_expired_lots()` | recordset | Returns pickings with move lines linked to expired lots |
| `_action_generate_expired_wizard()` | Action | Opens `expiry.picking.confirmation` wizard |

### `stock.move` (Inherited)

**Inherited from:** `stock.move`

| Field | Type | Note |
|-------|------|------|
| `use_expiration_date` | Boolean | Related from `product_id` |

| Method | Returns | Note |
|--------|---------|------|
| `_generate_serial_move_line_commands(...)` | Commands | Auto-sets `expiration_date` from product expiry_time on new serial numbers |
| `_convert_string_into_field_data(string, options)` | dict/str | Parses date strings; returns `{'expiration_date': datetime}` |
| `_get_formating_options(strings)` | dict | Detects `dayfirst`/`yearfirst` from date format patterns |
| `_update_reserved_quantity(...)` | — | Passes `with_expiration=self.date` context when product uses expiry |
| `_get_available_quantity(...)` | — | Same context injection for expiry-aware quantity checks |

### `stock.move.line` (Inherited)

**Inherited from:** `stock.move.line`

No model-specific overrides in this module. Lot-level expiry fields are inherited from `stock.lot`.

### `procurement.group` (Inherited)

**Inherited from:** `procurement.group`

| Method | Returns | Note |
|--------|---------|------|
| `_run_scheduler_tasks(...)` | — | Extends parent scheduler; calls `_alert_date_exceeded` on stock lots |
| `_get_scheduler_tasks_to_do()` | int | Returns `super() + 1` (one additional task: expiry check) |

---

## Security / Data

**Groups:** `group_expiry_date_on_delivery_slip` — controls display of expiration dates on delivery reports.

**Cron:** `ir_cron_alert_date_exceeded` (or `_alert_date_exceeded` called from procurement scheduler) — runs daily to alert on expired lots.

---

## Critical Notes

- **FEFO Logic:** When `stock.quant._get_removal_strategy_order('fefo')` returns `'removal_date, in_date, id'`, stock picks the lot with the earliest removal date first.
- **Wizard Bypass:** `_check_expired_lots` checks `lot_id.product_expiry_alert`. User can confirm with `skip_expired` context key.
- **GS1 AI Codes:** `17` = expiry date (yymmdd), `15` = best-before date. These are prepended to the base GS1 barcode string for FEFO-aware barcode scanning.
- **`_get_scheduler_tasks_to_do`:** The +1 task for expiry alerts increments the progress tracking counter.
