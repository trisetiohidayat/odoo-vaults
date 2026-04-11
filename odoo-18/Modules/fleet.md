---
Module: fleet
Version: Odoo 18
Type: Business
---

# Fleet Management (`fleet`)

Manages company vehicles, drivers, contracts, service logs, and odometer tracking. Integrates with `hr` for driver management and `fleet_account` (optional) for cost tracking.

**Source path:** `~/odoo/odoo18/odoo/addons/fleet/`
**Depends:** `base`, `mail`, `resource` (optional via `hr_fleet`)

---

## Models

### `fleet.vehicle` — Core Vehicle Record

The central model. Stores vehicle identity, current driver, and computed summary counts.

```python
class FleetVehicle(models.Model):
    _inherit = ['mail.thread', 'mail.activity.mixin', 'avatar.mixin']
    _name = 'fleet.vehicle'
    _rec_names_search = ['name', 'driver_id.name']
```

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char (compute) | `"Brand/Model/LicensePlate"` — computed from `model_id.brand_id.name`, `model_id.name`, `license_plate` |
| `model_id` | M2O `fleet.vehicle.model` | Required. Drives `brand_id`, `vehicle_type`, and all model-default fields |
| `brand_id` | M2O `fleet.vehicle.model.brand` | Related from `model_id.brand_id`, stored |
| `license_plate` | Char | Tracked. User-facing identifier |
| `vin_sn` | Char | Chassis/VIN number. Tracked, copy=False |
| `driver_id` | M2O `res.partner` | Current driver. Tracked |
| `future_driver_id` | M2O `res.partner` | Next assigned driver |
| `manager_id` | M2O `res.users` | Fleet manager — domain filtered to `fleet.fleet_group_manager` group |
| `state_id` | M2O `fleet.vehicle.state` | Vehicle lifecycle state (default: `fleet_vehicle_state_new_request`) |
| `location` | Char | Garage or parking location |
| `acquisition_date` | Date | Registration/ownership date |
| `write_off_date` | Date | Date license plate cancelled |
| `first_contract_date` | Date | Date of first contract |
| `order_date` | Date | Purchase order date |
| `next_assignation_date` | Date | Future availability date |
| `odometer` | Float (compute/inverse) | Last recorded odometer reading |
| `odometer_unit` | Selection: `kilometers`/`miles` | Per-vehicle unit setting |
| `fuel_type` | Selection | Derived from model defaults |
| `color` | Char | Derived from model (`_compute_model_fields`) |
| `model_year` | Char | Derived from model |
| `seats` | Integer | Derived from model |
| `doors` | Integer | Derived from model |
| `trailer_hook` | Boolean | Derived from model |
| `co2` / `co2_standard` | Float / Char | Derived from model |
| `power` / `horsepower` / `horsepower_tax` | Integer / Float | Derived from model |
| `power_unit` | Selection: `power`/`horsepower` | Derived from model |
| `transmission` | Selection: `manual`/`automatic` | Derived from model |
| `electric_assistance` | Boolean | Derived from model |
| `category_id` | M2O `fleet.vehicle.model.category` | Derived from model |
| `vehicle_range` | Integer | Derived from model (EV range in km) |
| `vehicle_type` | Selection | Related from `model_id.vehicle_type` (`car`/`bike`) |
| `car_value` | Float | Catalog value (VAT incl.) |
| `net_car_value` | Float | Purchase value |
| `residual_value` | Float | Residual value |
| `active` | Boolean | Soft-delete flag |
| `company_id` | M2O `res.company` | Multi-company |
| `currency_id` | M2O `res.currency` | Related from company |
| `country_id` / `country_code` | M2O / Char | Related from company |
| `log_drivers` | O2M `fleet.vehicle.assignation.log` | Driver history records |
| `log_services` | O2M `fleet.vehicle.log.services` | Service log entries |
| `log_contracts` | O2M `fleet.vehicle.log.contract` | Contract records |
| `contract_count` | Integer (compute) | Non-closed contract count |
| `service_count` | Integer (compute) | Active service log count |
| `odometer_count` | Integer (compute) | Odometer reading count |
| `history_count` | Integer (compute) | Assignment log count |
| `contract_renewal_due_soon` | Boolean (compute/search) | Contract expiring within `delay_alert_contract` days |
| `contract_renewal_overdue` | Boolean (compute/search) | Contract already expired |
| `contract_state` | Selection | Last open contract state |
| `plan_to_change_car` | Boolean | Related from `driver_id` — triggers HR interest flags |
| `plan_to_change_bike` | Boolean | Related from `driver_id` |
| `service_activity` | Selection: `none`/`overdue`/`today` | Computed from log_services activity states |
| `vehicle_properties` | Properties | Inherits `model_id.vehicle_properties_definition` |
| `description` | Html | Vehicle description |
| `image_128` | Image | Related from model |
| `tag_ids` | M2M `fleet.vehicle.tag` | Custom tagging |

#### Key Methods

- `_compute_vehicle_name()` — `Brand/Model/LicensePlate` format; if no plate, uses `"No Plate"`
- `_compute_model_fields()` — Copies fields from `model_id` to vehicle when model changes. Uses `MODEL_FIELDS_TO_VEHICLE` dict mapping: `transmission`, `model_year`, `electric_assistance`, `color`, `seats`, `doors`, `trailer_hook`, `default_co2→co2`, `co2_standard`, `default_fuel_type→fuel_type`, `power`, `horsepower`, `horsepower_tax`, `category_id`, `vehicle_range`, `power_unit`. Only copies truthy values.
- `_get_odometer()` — Reads most recent `fleet.vehicle.odometer` record ordered by `value desc`
- `_set_odometer()` — Creates new odometer record. **Blocks odometer decrease** (`UserError` if new value < current)
- `_compute_count_all()` — Uses `_read_group` to aggregate counts for contracts, services, odometers, history
- `_compute_contract_reminder()` — Groups open contracts by vehicle, finds max expiration date
- `_search_contract_renewal_due_soon()` / `_search_get_overdue_contract_reminder()` — Domain searches for contract alerts
- `_get_analytic_name()` — Returns `license_plate` or `"No plate"` — used by `fleet_account` for asset naming
- `create()` — Sets `driver_id` → creates `fleet.vehicle.assignation.log`; sets `future_driver_id` → flags partner's `plan_to_change_car/bike`
- `write()` — Validates odometer monotonic increase; on `driver_id` change: creates history log + schedules activity asking manager to set end date; on `future_driver_id` change: sets `plan_to_change_*` on partner
- `create_driver_history(vals)` — Creates assignment log entry with `date_start = today`
- `action_accept_driver_change()` — Transfers `future_driver_id → driver_id`, clears future driver, unsets `plan_to_change_*`
- `_track_subtype()` — Returns `fleet.mt_fleet_driver_updated` when driver changes

#### Constraints

- Odometer value cannot be lower than the previous reading (enforced in `write`)

---

### `fleet.vehicle.model` — Vehicle Model Master

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Model name (required) |
| `brand_id` | M2O `fleet.vehicle.model.brand` | Manufacturer (required) |
| `vehicle_type` | Selection: `car`/`bike` | Default: `car` |
| `transmission` | Selection: `manual`/`automatic` | Per-model default |
| `default_fuel_type` | Selection | Fuel type defaults to `electric` |
| `category_id` | M2O `fleet.vehicle.model.category` | Vehicle category |
| `model_year` | Integer | Model year |
| `color` | Char | Default color |
| `seats` / `doors` | Integer | Capacity |
| `trailer_hook` | Boolean | Hitch availability |
| `default_co2` / `co2_standard` | Float / Char | CO2 emissions |
| `power` / `horsepower` / `horsepower_tax` | Integer / Float | Power specs |
| `electric_assistance` | Boolean | E-bike |
| `power_unit` | Selection | kW or horsepower |
| `vehicle_range` | Integer | Range in km |
| `vehicle_count` | Integer (compute) | Active vehicles using this model |
| `vendors` | M2M `res.partner` | Preferred vendors |
| `image_128` | Image | Related from brand |
| `active` | Boolean | Soft delete |
| `vehicle_properties_definition` | PropertiesDefinition | Inheritable properties schema |

#### Key Methods

- `_compute_vehicle_count()` — Groups `fleet.vehicle` by `model_id`; used in `action_model_vehicle`
- `_search_vehicle_count()` — Supports `=`/`!=`/`<`/`>` operators for domain filtering
- `_compute_display_name()` — `"Brand/Model"` format
- `_search_display_name()` — Searches across both `name` and `brand_id.name`
- `action_model_vehicle()` — Opens vehicle kanban/list for this model

---

### `fleet.vehicle.model.brand` — Manufacturer

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Brand name (required) |
| `active` | Boolean | Soft delete |
| `image_128` | Image | Logo (128×128) |
| `model_count` | Integer (compute) | Active models under this brand |
| `model_ids` | O2M `fleet.vehicle.model` | Child models |

#### Key Methods

- `_compute_model_count()` — Uses `_read_group` filtered by `active=True`
- `action_brand_model()` — Action to open the brand's model list view

---

### `fleet.vehicle.state` — Vehicle States

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | State label (required) |
| `sequence` | Integer | Display order |

#### Constraints

- `_sql_constraints`: `fleet_state_name_unique` — `unique(name)`

States are defined via XML data: `fleet_vehicle_state_new_request`, `fleet_vehicle_state_waiting_list`, `fleet_vehicle_state_running`, `fleet_vehicle_state_closed`.

---

### `fleet.vehicle.odometer` — Odometer Readings

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char (compute) | `"VehicleName / Date"` |
| `date` | Date | Reading date (default: today) |
| `value` | Float | Odometer value |
| `vehicle_id` | M2O `fleet.vehicle` | Parent vehicle (required) |
| `unit` | Selection | Related from `vehicle_id.odometer_unit` |
| `driver_id` | M2O `res.partner` | Related from vehicle's current driver |

#### Key Methods

- `_compute_vehicle_log_name()` — `"VehicleName / Date"`; if no vehicle name uses date alone
- `_onchange_vehicle()` — Sets `unit` from the vehicle's odometer unit

---

### `fleet.vehicle.log.contract` — Leases & Contracts

| Field | Type | Notes |
|-------|------|-------|
| `vehicle_id` | M2O `fleet.vehicle` | Required, check_company |
| `cost_subtype_id` | M2O `fleet.service.type` | Type (domain: `category='contract'`) |
| `amount` | Monetary | Total contract cost |
| `date` | Date | Execution date |
| `start_date` | Date | Coverage start (default: today) |
| `expiration_date` | Date | Coverage end (default: +1 year via `compute_next_year_date`) |
| `days_left` | Integer (compute) | Days until expiration; `-1` if closed; `0` if overdue |
| `expires_today` | Boolean (compute) | True when expiration is today |
| `has_open_contract` | Boolean (compute) | Other open contracts exist for vehicle |
| `state` | Selection: `futur`/`open`/`expired`/`closed` | Status; default `open` |
| `insurer_id` | M2O `res.partner` | Vendor/insurer |
| `purchaser_id` | M2O `res.partner` | Related from vehicle's driver |
| `ins_ref` | Char | External reference |
| `notes` | Html | Terms and conditions |
| `cost_generated` | Monetary | Recurring cost amount |
| `cost_frequency` | Selection: `no`/`daily`/`weekly`/`monthly`/`yearly` | Default `monthly` |
| `service_ids` | M2M `fleet.service.type` | Included services |
| `user_id` | M2O `res.users` | Responsible (default: vehicle's manager) |
| `active` | Boolean | Soft delete |
| `name` | Char (compute) | `"Type VehicleName"` |

#### Key Methods

- `compute_next_year_date(strdate)` — Uses `dateutil.relativedelta` to add 1 year
- `_compute_contract_name()` — Concatenates `cost_subtype_id.name + vehicle_id.name`
- `_compute_days_left()` — Returns `diff_time` if positive else `0` for open/expired; `-1` for closed
- `_compute_has_open_contract()` — Checks if vehicle has any other open, non-expired contract
- `write()` — On `start_date`/`expiration_date` change: auto-transitions state: `futur` if future start, `open` if within range, `expired` if past expiration. Reschedules renewal activities.
- `action_close()` / `action_draft()` / `action_open()` / `action_expire()` — State transitions
- `scheduler_manage_contract_expiration()` — Cron method that: (1) creates renewal activities for contracts expiring within `delay_alert_contract` days (config param `hr_fleet.delay_alert_contract`), (2) expires past-due contracts, (3) transitions `futur→open` for contracts whose start date is now
- `run_scheduler()` — Wrapper for the cron scheduler

#### L4: Contract State Machine Logic

```
write(start_date, expiration_date):
  date_today < start_date          → state = 'futur'
  start_date ≤ date_today ≤ exp_date → state = 'open'
  date_today > expiration_date      → state = 'expired'

scheduler cron:
  open contracts + expiration < today+delay  → schedule activity
  state not in [expired,closed] + expiration < today  → action_expire()
  state not in [futur,closed] + start_date > today    → action_draft()
  state = 'futur' + start_date ≤ today              → action_open()
```

---

### `fleet.vehicle.log.services` — Service Logs

| Field | Type | Notes |
|-------|------|-------|
| `vehicle_id` | M2O `fleet.vehicle` | Required |
| `manager_id` | M2O `res.users` | Related from vehicle |
| `amount` | Monetary | Service cost |
| `description` | Char | Service description |
| `odometer_id` | M2O `fleet.vehicle.odometer` | Linked odometer reading |
| `odometer` | Float (compute/inverse) | Odometer at time of service |
| `odometer_unit` | Selection | Related from vehicle |
| `date` | Date | Service date (default: today) |
| `company_id` / `currency_id` | M2O | Company/currency |
| `purchaser_id` | M2O `res.partner` | Computed from vehicle's driver |
| `inv_ref` | Char | Vendor reference |
| `vendor_id` | M2O `res.partner` | Service vendor |
| `notes` | Text | Internal notes |
| `service_type_id` | M2O `fleet.service.type` | Required; default: `fleet.type_service_service_7` |
| `state` | Selection: `new`/`running`/`done`/`cancelled` | Stage; default `new` |

#### Key Methods

- `_get_odometer()` / `_set_odometer()` — Same inverse pattern as `fleet.vehicle`; creates new odometer entry on write
- `_compute_purchaser_id()` — Sets `purchaser_id = vehicle_id.driver_id`
- `create()` — Removes `odometer=0` from vals before creating (avoids logging zero readings)

---

### `fleet.service.type` — Service Type Master Data

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Service type name (required, translated) |
| `category` | Selection: `contract`/`service` | Whether type applies to contracts, services, or both |

#### Key Notes

- Used as domain filter: `cost_subtype_id` on contracts uses `category='contract'`; `service_type_id` on logs uses all
- `fleet.service.type` is a shared master data table consumed by both contracts and service logs

---

### `fleet.vehicle.assignation.log` — Driver Assignment History

| Field | Type | Notes |
|-------|------|-------|
| `vehicle_id` | M2O `fleet.vehicle` | Required |
| `driver_id` | M2O `res.partner` | Required |
| `date_start` | Date | Assignment start |
| `date_end` | Date | Assignment end (empty = current) |

#### Key Methods

- `_compute_display_name()` — `"VehicleName - DriverName"`
- Created automatically by `fleet.vehicle.create_driver_history()` when `driver_id` changes

---

### `fleet.vehicle.model.category` — Vehicle Category

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Category name (required) |
| `sequence` | Integer | Display order |

#### Constraints

- `unique(name)` SQL constraint

---

### `fleet.vehicle.tag` — Vehicle Tags

| Field | Type | Notes |
|-------|------|-------|
| `name` | Char | Tag name (required, translated) |
| `color` | Integer | Kanban color index |

#### Constraints

- `unique(name)` SQL constraint

---

### `res.partner` — EXTENDED (fleet module)

| Field | Type | Notes |
|-------|------|-------|
| `plan_to_change_car` | Boolean | Set by vehicle's future driver assignment for cars |
| `plan_to_change_bike` | Boolean | Set by vehicle's future driver assignment for bikes |

#### L4: Driver ↔ HR Integration

The `fleet` module does **not** depend on `hr`, but `hr_fleet` (a separate module) bridges the two. In the base `fleet` module, `driver_id` is a plain `res.partner` field — not an `hr.employee`. The `plan_to_change_car` / `plan_to_change_bike` booleans on `res.partner` are used to signal to the HR department that an employee intends to change their company vehicle. The `action_accept_driver_change()` method on `fleet.vehicle` manages the handoff: it clears the current driver's assignment across all vehicles of the same type, then transfers the future driver to current driver.

---

### L4: Odometer Tracking Pattern

Odometer is tracked at two levels:

1. **Vehicle level** (`fleet.vehicle.odometer`): Last reading via `_get_odometer()` — searches by `value desc`
2. **Service log level** (`fleet.vehicle.log.services.odometer_id`): Links a service entry to a specific odometer reading

The inverse setter `_set_odometer()` on both `fleet.vehicle` and `fleet.vehicle.log.services` **always creates a new `fleet.vehicle.odometer` record** — never updates an existing one. This preserves the full reading history. The service log odometer is optional; when set, it provides a link between the service record and the odometer snapshot.

Constraint: odometer cannot decrease (enforced in `fleet.vehicle.write`).

---

### L4: fleet + account.move (via fleet_account)

The base `fleet` module does **not** create journal entries. When `fleet_account` is installed:

- `fleet.vehicle` gains a `product_id` field linking to a product used for depreciation
- `fleet.vehicle.log.contract` generates `account.move.line` entries for each `cost_frequency` period via scheduled actions
- The `_get_analytic_name()` method on `fleet.vehicle` returns the license plate for naming analytic accounts

The contract's `cost_generated` and `cost_frequency` fields drive recurring journal entries. See `fleet_account` module for full accounting integration details.

---

### L4: hr_fleet Module Bridge (extension)

The `hr_fleet` module (not in base `fleet`) extends:
- `hr.employee` with a `vehicle_id` M2O to `fleet.vehicle`
- `fleet.vehicle` driver_id becomes an `hr.employee` rather than raw `res.partner`
- Adds `vehicle_assignation_log` linking employee assignments to vehicle logs

This separates the concept of "driver (person)" from "employee (HR record)" while keeping the vehicle assignment workflow intact.

---

## Tags

#fleet #odoo18 #business #vehicle #driver #odometer #contract
