---
Module: account_fleet
Version: Odoo 18
Type: Integration
Tags: #odoo18, #fleet, #accounting, #integration
---

# Account Fleet Module (`account_fleet`)

## Overview

**Category:** Accounting/Accounting
**Depends:** `fleet`, `account`
**Auto-install:** Yes
**License:** LGPL-3

The `account_fleet` module bridges the [Modules/Fleet](modules/fleet.md) and [Core/Account](core/account.md) modules. It enables vendor bills (purchase invoices) to be linked to specific vehicles, automatically creates service log entries from bill lines, and provides a "Bills" button on the vehicle form for direct access to all accounting documents related to a vehicle.

This is a **pure integration module** — it contains no standalone business logic. All models it defines or extends are thin bridges.

## Dependencies

```
fleet          → provides fleet.vehicle, fleet.vehicle.log.services
account        → provides account.move, account.move.line
account_fleet  → bridges the two
```

## Models Extended or Created

### `fleet.vehicle` — Extended by `account_fleet`

**File:** `models/fleet_vehicle.py`
**Inheritance:** `_inherit = 'fleet.vehicle'`

This extension adds accounting visibility to the vehicle form without introducing new business logic.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `bill_count` | Integer (computed) | Number of vendor bills (purchase-type moves) linked to this vehicle |
| `account_move_ids` | One2many `account.move` (computed) | All posted/non-cancelled vendor bills for this vehicle |

#### Methods

**`_compute_move_ids()`** — `compute` method
- Guards early if user lacks `account.group_account_readonly`
- Uses `_read_group()` on `account.move.line` to aggregate `move_id` grouped by `vehicle_id`
- Filters to purchase-types only: `move_type in ('in_invoice', 'in_refund', ...)`
- Excludes cancelled moves via `parent_state != 'cancel'`
- **Performance note:** Uses `_read_group` with `array_agg` to collect move IDs per vehicle in a single query, then `Command.set()` to assign them

**`action_view_bills()`** — Object button action
- Opens the list of vendor bills linked to this vehicle
- Uses `account_fleet.account_move_view_tree` as the list view
- Sets domain: `[('id', 'in', self.account_move_ids.ids)]`

---

### `account.move` — Extended by `account_fleet`

**File:** `models/account_move.py`
**Inheritance:** `_inherit = 'account.move'`

#### Key Method

**`_post(soft=True)`** — Hook into vendor bill posting

This is the core integration method. When a vendor bill is posted, it automatically creates `fleet.vehicle.log.services` records for each invoice line that has a `vehicle_id` set.

```
Flow:
  vendor bill posted
    → _post() runs
    → for each line with vehicle_id set
        → _prepare_fleet_log_service() builds vals
        → fleet.vehicle.log.services created
        → message_post() logs the bill link on the service record
```

Specific conditions for creating a log service:
- `vehicle_id` is set on the line
- `vehicle_log_service_ids` is empty (not already linked)
- `move_type == 'in_invoice'` (purchase invoice)
- `display_type == 'product'` (not a section/note line)

**L4 — Auto-create behavior:**
The auto-creation of service logs from vendor bill lines means users do not need to manually enter service records for every billable maintenance event. The `Vendor Bill` service type (created in `data/fleet_service_type_data.xml`) serves as the marker type. A `_prepare_fleet_log_service()` method on `AccountMoveLine` (see below) populates the log service with the vendor, description, and account move line reference.

---

### `account.move.line` — Extended by `account_fleet`

**File:** `models/account_move_line.py`
**Inheritance:** `_inherit = 'account.move.line'`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `vehicle_id` | Many2one `fleet.vehicle` | Links this invoice line to a specific vehicle. Indexed (`btree_not_null`) |
| `need_vehicle` | Boolean (computed) | Always `False` in this module — defined but not populated; reserved for future use |
| `vehicle_log_service_ids` | One2many `fleet.vehicle.log.services` | Reverse link to the auto-created service log. One2one relationship |

#### Methods

**`_compute_need_vehicle()`** — `compute` method
- Sets `need_vehicle = False` for all records
- This field exists as a hook point; it allows the vehicle column in invoice views to be conditionally required

**`_prepare_fleet_log_service()`** — Value dict builder
- Called by `account.move._post()` for each eligible invoice line
- Returns a dict:
  ```python
  {
      'service_type_id': vendor_bill_service.id,  # the "Vendor Bill" type
      'vehicle_id': self.vehicle_id.id,
      'vendor_id': self.partner_id.id,
      'description': self.name,                   # the line description
      'account_move_line_id': self.id,            # back-reference
  }
  ```

**`write(vals)`** — Override
- If `vehicle_id` is being cleared (`'vehicle_id': False`), unlinks the associated `vehicle_log_service_ids` with `ignore_linked_bill_constraint=True` context flag

**`unlink()`** — Override
- Before deleting the line, unlinks associated service logs using the same constraint-bypass context

---

### `fleet.vehicle.log.services` — Extended by `account_fleet`

**File:** `models/fleet_vehicle_log_services.py`
**Inheritance:** `_inherit = 'fleet.vehicle.log.services'`

The fleet module already defines `fleet.vehicle.log.services`. This extension adds the accounting bridge fields and computed amounts.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `account_move_line_id` | Many2one `account.move.line` | Back-link to the source invoice line. One2one |
| `account_move_state` | Selection (related) | `parent_state` of the linked move line. Shows `posted`/`draft`/etc |
| `amount` | Monetary (computed + inverse) | Cost — computed as `debit` from the linked invoice line |
| `vehicle_id` | Many2one `fleet.vehicle` | Vehicle — recomputed from `account_move_line_id.vehicle_id` if set |

#### Methods

**`_compute_vehicle_id()`** — `compute` method
- Copies `vehicle_id` from the linked `account_move_line_id` if present
- Does NOT clear `vehicle_id` if the line has no vehicle (avoids breaking the required field)

**`_inverse_amount()`** — Inverse method
- Raises `UserError` if user tries to edit amount while the record is linked to an invoice line
- Forces editing to happen on the accounting entry instead

**`_compute_amount()`** — `compute` method
- Reads `debit` from the linked `account_move_line_id`
- Note: Uses `debit`, not `credit` — the vendor bill line's debit (expense/debit) amount becomes the service cost

**`action_open_account_move()`** — Object button action
- Opens the linked `account.move` form from the service log
- Visible only when `account_move_line_id` exists

#### Constraint

**`_unlink_if_no_linked_bill()`** — `@api.ondelete(at_uninstall=False)`
- Prevents deletion of service logs that have a linked invoice line
- Bypassed with context `ignore_linked_bill_constraint=True` (used by `account.move.line` unlink/write overrides)

---

## Data Files

### `data/fleet_service_type_data.xml`

Creates the `fleet.service.type` record that marks auto-created log entries:

```xml
<record id="data_fleet_service_type_vendor_bill" model="fleet.service.type">
    <field name="name">Vendor Bill</field>
    <field name="category">service</field>
</record>
```

External ID: `account_fleet.data_fleet_service_type_vendor_bill`

This service type is referenced by `_prepare_fleet_log_service()` and `_post()` to classify auto-created logs.

---

## Views

### `views/fleet_vehicle_views.xml`

Extends `fleet.fleet_vehicle_view_form` — adds a **Bills** stat button before the assignation logs button:

```xml
<button name="action_view_bills" type="object" class="oe_stat_button"
    icon="fa-pencil-square-o" invisible="bill_count == 0">
    <field name="bill_count" widget="statinfo" string="Bills"/>
</button>
```

### `views/account_move_views.xml`

Three view overrides:

1. **`view_move_form`** — Injects `vehicle_id` column into invoice line tree:
   - Only visible for `in_invoice` / `in_refund` types
   - Optional hidden column (shown for account accountants)
   - Required when `need_vehicle = True`

2. **`account_move_view_tree`** — Custom list view for fleet bills:
   - Renames `date` column to "Creation Date"
   - Adds `invoice_date` as an optional column

3. **`view_move_line_tree_fleet`** — Adds `vehicle_id` as hidden column in move line tree

### `views/fleet_vehicle_log_services_views.xml`

Extends `fleet.fleet_vehicle_log_services_view_form`:
- Adds "Service's Bill" button (green if posted, yellow if draft)
- Makes `amount` field readonly when linked to an invoice line

---

## L4: Fleet Cost Flow into Accounting

```
1. Vendor submits repair/maintenance invoice
2. Accountant enters vendor bill (account.move in 'in_invoice')
3. On each invoice line, accountant selects the vehicle from vehicle_id dropdown
4. Bill is posted → _post() fires
5. For each line with vehicle_id:
     a. fleet.vehicle.log.services record auto-created
        - service_type_id = "Vendor Bill"
        - vehicle_id = line's vehicle
        - vendor_id = line's partner (vendor)
        - description = line name
        - account_move_line_id = self
     b. amount computed from line.debit
     c. message_post links the bill on the log
6. Vehicle's "Bills" counter increments
7. From vehicle form, accountant opens all related vendor bills
8. Amount is synced: editing line amount in accounting updates the service log cost
9. To edit cost, user MUST edit the vendor bill — direct edit raises UserError
```

### Analytic Account Integration

Note: The original prompt mentioned analytic account fields on the contract model. The `account_fleet` module does **not** extend `fleet.vehicle.log.contract`. Analytic account integration would typically be handled at the `account.move.line` level via the standard Odoo analytic distribution mechanism (the `analytic_distribution` JSON field on move lines), not via `account_fleet`. The module links vehicle costs to accounting entries purely through the `vehicle_id` / `account_move_line_id` back-reference pair.

### No Contract Amortization

`fleet.vehicle.log.contract` (leasing/financing contracts) are **not** extended by `account_fleet`. The module only handles service costs from vendor bills. Contract amortization (e.g., recognizing lease expense over time) is outside this module's scope.

---

## Security

- `_compute_move_ids()` checks `account.group_account_readonly` before computing
- Non-accounting users see `bill_count = 0` and empty `account_move_ids`
- The `vehicle_id` field on invoice lines respects standard accounting ACLs
- Deleting a service log linked to a posted bill is blocked (`_unlink_if_no_linked_bill`)
