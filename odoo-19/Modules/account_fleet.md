---
type: module
module: account_fleet
tags: [odoo, odoo19, account, fleet, vehicle, accounting]
created: 2026-04-06
---

# Accounting/Fleet Bridge

## Overview

| Property | Value |
|----------|-------|
| Category | Accounting/Accounting |
| Depends | fleet, account |
| Author | Odoo S.A. |
| License | LGPL-3 |
| Auto-install | True |

## Description

Links **fleet management** with accounting. Tracks vehicle costs through vendor bills and auto-creates service log entries from bill lines with a vehicle reference. Enables accounting-level visibility into fleet operational costs.

## Key Models

### `fleet.vehicle` (Inherited)

| Field | Type | Description |
|-------|------|-------------|
| `bill_count` | Integer | Number of vendor bills (readonly) |
| `account_move_ids` | One2many (account.move) | Linked account moves |

**Key Methods:**

- `_compute_move_ids()` — Searches `account.move.line` with `vehicle_id` matching and `move_type` in purchase types. Groups by vehicle to set `account_move_ids` and `bill_count`. Requires `account.group_account_readonly`.
- `action_view_bills()` — Opens vendor bill list filtered to this vehicle's moves.

### `fleet.vehicle.log.services` (Inherited)

| Field | Type | Description |
|-------|------|-------------|
| `account_move_line_id` | Many2one (account.move.line) | Linked bill line (one2one) |
| `account_move_state` | Selection | State of the linked move (related) |
| `amount` | Monetary | Cost (computed from linked bill line, stored) |
| `vehicle_id` | Many2one (fleet.vehicle) | Vehicle (computed from bill line, stored) |

**Key Methods:**

- `_compute_vehicle_id()` — Sets `vehicle_id` from linked bill line's `vehicle_id` field (avoids clearing on empty).
- `_compute_amount()` — Computes `amount` from `account_move_line_id.debit`.
- `_inverse_amount()` — Raises `UserError` if linked to a bill line (must be modified on the accounting entry instead).
- `action_open_account_move()` — Opens the linked vendor bill form.
- `_unlink_if_no_linked_bill()` — Prevents deletion of service logs that have been converted to bill lines (ondelete constraint).

### `account.move` (Inherited)

**Key Methods:**

- `_post(soft=True)` — Post-hook: scans posted move lines for those with `vehicle_id` and no existing log service, then auto-creates `fleet.vehicle.log.services` records (one per line) and logs a message on each. Requires `data_fleet_service_type_vendor_bill` reference data.

### `account.move.line` (Inherited)

| Field | Type | Description |
|-------|------|-------------|
| `vehicle_id` | Many2one (fleet.vehicle) | Vehicle referenced on this line |
| `need_vehicle` | Boolean | Whether vehicle_id is editable (always False in this module) |
| `vehicle_log_service_ids` | One2many (fleet.vehicle.log.services) | Service logs linked to this line (inverse of `account_move_line_id`) |

**Key Methods:**

- `_compute_need_vehicle()` — Sets `need_vehicle = False` (overridable by other modules).
- `_prepare_fleet_log_service()` — Returns values dict for service log creation with vendor bill service type.
- `write(vals)` — On unsetting `vehicle_id`, deletes linked service log entries.
- `unlink()` — Cascades deletion to linked service log entries.

## Key Features

- View vendor bills from vehicle form
- Auto-create service logs from bill lines with vehicle
- Service cost tracking from accounting entries
- Fleet expense reporting via account move grouping
- Two-way sync: service log amount drives bill line, or bill line creates log

## Related

[Account.md](Account.md.md), [Fleet.md](Fleet.md.md)