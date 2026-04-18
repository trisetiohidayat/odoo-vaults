---
type: module
module: fleet
tags: [odoo, odoo19, fleet, vehicle, fleet-management, cost-tracking, driver-assignment]
created: 2026-04-06
updated: 2026-04-11

# Fleet Module (fleet)

## Overview

| Property | Value |
|----------|-------|
| **Technical Name** | `fleet` |
| **Category** | Human Resources/Fleet |
| **Sequence** | 185 |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Website** | https://www.odoo.com/app/fleet |
| **Installable** | True |
| **Application** | True |
| **Dependencies** | `base`, `mail` |
| **Module Version** | 0.1 |

## Description

The Fleet module manages vehicles, their contracts, services, odometer readings, driver assignments, and cost tracking. It integrates with `mail` for chatter and activity reminders, and with `fleet_account` (an add-on) for accounting journal entries.

**Main Features:**
- Add and manage vehicles in the fleet
- Manage contracts (leasing, insurance, omnium) with expiration tracking
- Log services and maintenance records
- Track odometer readings per vehicle
- Driver assignment with full history logs
- Cost analysis reports (contract vs. service costs)
- Odometer reporting with monthly interpolation
- Reminder activities for expiring contracts via scheduler cron
- Mass email to drivers via wizard

---

## Module File Layout

```
fleet/
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── fleet_vehicle.py              # fleet.vehicle (primary model)
│   ├── fleet_vehicle_model.py         # fleet.vehicle.model
│   ├── fleet_vehicle_model_brand.py   # fleet.vehicle.model.brand
│   ├── fleet_vehicle_model_category.py
│   ├── fleet_vehicle_log_contract.py  # fleet.vehicle.log.contract
│   ├── fleet_vehicle_log_services.py # fleet.vehicle.log.services
│   ├── fleet_vehicle_odometer.py      # fleet.vehicle.odometer
│   ├── fleet_vehicle_assignation_log.py
│   ├── fleet_vehicle_state.py
│   ├── fleet_vehicle_tag.py
│   ├── fleet_service_type.py
│   ├── mail_activity_type.py
│   └── res_config_settings.py
├── wizard/
│   ├── __init__.py
│   └── fleet_vehicle_send_mail.py
├── report/
│   ├── __init__.py
│   ├── fleet_report.py                # fleet.vehicle.cost.report (SQL view)
│   └── odometer_report.py             # fleet.vehicle.odometer.report (SQL view)
├── security/
│   ├── fleet_security.xml            # Groups + ir.rule
│   └── ir.model.access.csv
└── data/
    ├── fleet_data.xml                # States: New Request, To Order, Registered, Downgraded
    ├── fleet_cars_data.xml           # 50+ brands with logos
    ├── fleet_demo.xml
    ├── mail_activity_type_data.xml   # Contract to Renew activity type
    └── mail_message_subtype_data.xml
```

---

## Model Index

| Model | File | Purpose |
|-------|------|---------|
| `fleet.vehicle` | `fleet_vehicle.py` | Primary vehicle entity |
| `fleet.vehicle.model` | `fleet_vehicle_model.py` | Vehicle model/variant (brand + name) |
| `fleet.vehicle.model.brand` | `fleet_vehicle_model_brand.py` | Manufacturer |
| `fleet.vehicle.model.category` | `fleet_vehicle_model_category.py` | Vehicle category |
| `fleet.vehicle.log.contract` | `fleet_vehicle_log_contract.py` | Contracts (lease, insurance, etc.) |
| `fleet.vehicle.log.services` | `fleet_vehicle_log_services.py` | Service/maintenance logs |
| `fleet.vehicle.odometer` | `fleet_vehicle_odometer.py` | Odometer reading records |
| `fleet.vehicle.assignation.log` | `fleet_vehicle_assignation_log.py` | Driver assignment history |
| `fleet.vehicle.state` | `fleet_vehicle_state.py` | Vehicle lifecycle states |
| `fleet.vehicle.tag` | `fleet_vehicle_tag.py` | Custom tags for vehicles |
| `fleet.service.type` | `fleet_service_type.py` | Service/contract type taxonomy |
| `fleet.vehicle.cost.report` | `fleet_report.py` | SQL view: monthly cost aggregation |
| `fleet.vehicle.odometer.report` | `odometer_report.py` | SQL view: monthly mileage |
| `fleet.vehicle.send.mail` | `fleet_vehicle_send_mail.py` | Transient: mass email wizard |
| `fleet.vehicle.odometer.report` | `odometer_report.py` | Odometer analysis view |
| `mail.activity.type` | `mail_activity_type.py` | Extends activity type for fleet renewals |

---

## fleet.vehicle

**File:** `~/odoo/odoo19/odoo/addons/fleet/models/fleet_vehicle.py`
**Inherits:** `mail.thread`, `mail.activity.mixin`, `avatar.mixin`
**Order:** `license_plate asc, acquisition_date asc`

### Fields

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `name` | Char | No | computed | `brand/model/license_plate` via `_compute_vehicle_name` |
| `description` | Html | No | - | Free-form vehicle description |
| `active` | Boolean | No | `True` | Archival flag; cascades to deactivate contracts/services on write |
| `manager_id` | Many2one `res.users` | No | - | Fleet manager; domain: non-share users in fleet group |
| `company_id` | Many2one `res.company` | No | `self.env.company` | Multi-company filtering |
| `currency_id` | Many2one `res.currency` | No | related | Via `company_id.currency_id` |
| `country_id` | Many2one `res.country` | No | related | Via `company_id.country_id` |
| `country_code` | Char | No | related | Via `country_id.code` |
| `license_plate` | Char | No | - | Free text; used in `name` display |
| `vin_sn` | Char | No | - | VIN/Chassis number; `copy=False` (not duplicated on copy) |
| `trailer_hook` | Boolean | No | `False` | `store=True, readonly=False, compute='_compute_trailer_hook'` |
| `driver_id` | Many2one `res.partner` | No | - | Current driver; `copy=False` |
| `future_driver_id` | Many2one `res.partner` | No | - | Next assigned driver; `check_company=True`; `copy=False` |
| `model_id` | Many2one `fleet.vehicle.model` | **Yes** | - | Vehicle model/variant |
| `brand_id` | Many2one `fleet.vehicle.model.brand` | No | related | Via `model_id.brand_id`; `store=True` |
| `log_drivers` | One2many | No | - | `fleet.vehicle.assignation.log` → `vehicle_id` |
| `log_services` | One2many | No | - | `fleet.vehicle.log.services` → `vehicle_id` |
| `log_contracts` | One2many | No | - | `fleet.vehicle.log.contract` → `vehicle_id` |
| `contract_count` | Integer | No | computed | Via `_compute_count_all` |
| `service_count` | Integer | No | computed | Via `_compute_count_all` |
| `odometer_count` | Integer | No | computed | Via `_compute_count_all` |
| `history_count` | Integer | No | computed | Via `_compute_count_all` |
| `next_assignation_date` | Date | No | - | When car will be available (unset = instantly) |
| `order_date` | Date | No | - | Purchase order date |
| `acquisition_date` | Date | No | `today` | Registration/acquisition date |
| `write_off_date` | Date | No | - | When license plate was cancelled |
| `contract_date_start` | Date | No | `today` | First contract start date |
| `color` | Char | No | computed | `store=True`; copied from `model_id.color` |
| `state_id` | Many2one `fleet.vehicle.state` | No | `_get_default_state` | Default: `fleet.fleet_vehicle_state_new_request` |
| `location` | Char | No | - | Garage or parking location |
| `seats` | Integer | No | computed | Seating capacity; `store=True` |
| `model_year` | Selection | No | computed | Range 1970–current; `store=True` |
| `doors` | Integer | No | computed | Number of doors; `store=True` |
| `tag_ids` | Many2many `fleet.vehicle.tag` | No | - | Via `fleet_vehicle_vehicle_tag_rel` |
| `odometer` | Float | No | computed | Last reading; inverse `_set_odometer` creates new `fleet.vehicle.odometer` record |
| `odometer_unit` | Selection | **Yes** | `kilometers` | `kilometers` / `miles` |
| `transmission` | Selection | No | computed | `manual` / `automatic`; `store=True` |
| `fuel_type` | Selection | No | computed | See `FUEL_TYPES` constant below; `store=True` |
| `power_unit` | Selection | **Yes** | `power` | `power` (kW) / `horsepower` (hp) |
| `horsepower` | Float | No | computed | `store=True` |
| `horsepower_tax` | Float | No | computed | Horsepower taxation; `store=True` |
| `power` | Float | No | computed | Power in kW; `store=True` |
| `co2` | Float | No | computed | CO2 emissions; `store=True` |
| `co2_emission_unit` | Selection | **Yes** | `g/km` | Derived from `range_unit`; `g/km` or `g/mi` |
| `co2_standard` | Char | No | computed | Emission standard; `store=True` |
| `category_id` | Many2one `fleet.vehicle.model.category` | No | computed | `store=True` |
| `image_128` | Image | No | related | From `model_id.image_128` |
| `contract_renewal_due_soon` | Boolean | No | computed | `search='_search_contract_renewal_due_soon'` |
| `contract_renewal_overdue` | Boolean | No | computed | `search='_search_get_overdue_contract_reminder'` |
| `contract_state` | Selection | No | computed | Last open contract state |
| `car_value` | Float | No | - | Catalog value (VAT Incl.) |
| `net_car_value` | Float | No | - | Purchase value |
| `residual_value` | Float | No | - | Residual value for leasing |
| `plan_to_change_car` | Boolean | No | `False` | HR flag; set when car change is planned |
| `plan_to_change_bike` | Boolean | No | `False` | HR flag; set when bike change is planned |
| `vehicle_type` | Selection | No | related | `car` / `bike` from `model_id.vehicle_type` |
| `frame_type` | Selection | No | - | Bike frame type: `diamant` / `trapez` / `wave` |
| `electric_assistance` | Boolean | No | computed | `store=True` |
| `frame_size` | Float | No | - | Bike frame size |
| `service_activity` | Selection | No | computed | `none` / `overdue` / `today` from `log_services.activity_state` |
| `vehicle_properties` | Properties | No | - | Custom properties defined on `model_id.vehicle_properties_definition` |
| `vehicle_range` | Integer | No | computed | Range; `store=True` |
| `range_unit` | Selection | **Yes** | `km` | `km` / `mi`; `store=True` |

### FUEL_TYPES Constant

Defined in `fleet_vehicle_model.py`, imported into `fleet_vehicle.py`:

```python
FUEL_TYPES = [
    ('diesel', 'Diesel'),
    ('gasoline', 'Gasoline'),
    ('full_hybrid', 'Full Hybrid'),
    ('plug_in_hybrid_diesel', 'Plug-in Hybrid Diesel'),
    ('plug_in_hybrid_gasoline', 'Plug-in Hybrid Gasoline'),
    ('cng', 'CNG'),
    ('lpg', 'LPG'),
    ('hydrogen', 'Hydrogen'),
    ('electric', 'Electric'),
]
```

### MODEL_FIELDS_TO_VEHICLE Field Propagation Map

A key pattern in `fleet.vehicle` is the `_load_fields_from_model()` method, which propagates defaults from `fleet.vehicle.model` to `fleet.vehicle` on create and when `model_id` changes. The mapping:

```python
MODEL_FIELDS_TO_VEHICLE = {
    'transmission':       'transmission',
    'model_year':         'model_year',
    'electric_assistance':'electric_assistance',
    'color':              'color',
    'seats':              'seats',
    'doors':              'doors',
    'trailer_hook':       'trailer_hook',
    'default_co2':        'co2',               # note: renamed
    'co2_standard':       'co2_standard',
    'default_fuel_type':  'fuel_type',         # note: renamed
    'power':              'power',
    'horsepower':         'horsepower',
    'horsepower_tax':     'horsepower_tax',
    'category_id':        'category_id',
    'vehicle_range':      'vehicle_range',
    'power_unit':         'power_unit',
    'range_unit':         'range_unit',
}
```

Only non-empty (`truthy`) model fields are propagated. Model values are cached per `model_id` to avoid N+1 writes.

### Key Methods

#### `_get_default_state()`
Returns the `fleet.vehicle.state` record with xmlid `fleet.fleet_vehicle_state_new_request`. Used as default for `state_id`.

#### `_compute_count_all()`
Uses `_read_group` with `active_test=False` context on services and contracts to compute all four counts in a single query pass per aggregate. `contract_count` filters to `state != 'closed'`. This is the method powering the smart buttons on the vehicle form.

#### `_compute_contract_reminder()`
Reads non-closed contracts grouped by `vehicle_id` and `state`, finding the latest `expiration_date`. Sets `contract_renewal_overdue`, `contract_renewal_due_soon`, and `contract_state`. The `delay_alert_contract` threshold (default 30 days) is read from `ir.config_parameter` `hr_fleet.delay_alert_contract`.

#### `_get_odometer()` / `_set_odometer()`
- `_get_odometer()`: searches `fleet.vehicle.odometer` ordered by `value desc`, limit 1. Returns 0 if no readings exist.
- `_set_odometer()`: validates the new value is **not lower** than the current odometer (enforced in `write()` with a `UserError`). Creates a new `fleet.vehicle.odometer` record with the current `driver_id`.

**Edge case:** Odometer value cannot be set to 0 to "empty" a reading — raising `UserError`. Creating a service log with `odometer=0` strips the field from vals before create (see `fleet.vehicle.log.services.create()`).

#### `create(vals_list)` — Driver Change Flagging on Create
When `future_driver_id` is set and the vehicle is not in "waiting list" or "new request" state, the system searches for other vehicles of the same type (`car`/`bike`) currently assigned to that driver and sets their `plan_to_change_car` or `plan_to_change_bike` flag to `True`. If `driver_id` is also set, a `fleet.vehicle.assignation.log` entry is created immediately.

#### `write(vals)` — Driver Change Triggers
1. **Odometer guard**: If `odometer` in vals, raises `UserError` if new value < current value.
2. **Driver change**: If `driver_id` changes to a new driver, creates a `fleet.vehicle.assignation.log` entry with today's date as `date_start`, and schedules a todo activity on the fleet manager to set the end date of the **departing** driver.
3. **Future driver change**: If `future_driver_id` changes, searches for other vehicles of the same type assigned to that future driver and sets their `plan_to_change_*` flag.
4. **Active cascade**: If `active` is set to `False`, all related `fleet.vehicle.log.contract` and `fleet.vehicle.log.services` records are deactivated.

#### `action_accept_driver_change()`
Called from the UI to finalize a driver swap:
1. Finds all vehicles of the same `vehicle_type` whose current `driver_id` matches this vehicle's `future_driver_id`.
2. Clears their `driver_id`, sets `plan_to_change_car/bike = False`.
3. Sets this vehicle's `driver_id = future_driver_id` and clears `future_driver_id`.

#### `_track_subtype()`
Returns `fleet.mt_fleet_driver_updated` message subtype when `driver_id` or `future_driver_id` changes. Otherwise delegates to `mail.thread`.

---

## fleet.vehicle.model

**File:** `~/odoo/odoo19/odoo/addons/fleet/models/fleet_vehicle_model.py`
**Inherits:** `mail.thread`, `mail.activity.mixin`, `avatar.mixin`
**Order:** `name asc`

### Fields

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `name` | Char | **Yes** | - | Model name (e.g., "A4", "Model 3") |
| `brand_id` | Many2one `fleet.vehicle.model.brand` | **Yes** | - | Manufacturer; `index='btree_not_null'` |
| `category_id` | Many2one `fleet.vehicle.model.category` | No | - | Vehicle category |
| `vendors` | Many2many `res.partner` | No | - | Preferred vendors for this model |
| `image_128` | Image | No | related | `related='brand_id.image_128'` (brand logo as model image) |
| `active` | Boolean | No | `True` | |
| `vehicle_type` | Selection | **Yes** | `car` | `car` / `bike` |
| `transmission` | Selection | No | - | `manual` / `automatic` |
| `vehicle_count` | Integer | No | computed | Count of vehicles using this model |
| `model_year` | Selection | No | - | Range 1970–current year |
| `color` | Char | No | - | Default color |
| `seats` | Integer | No | - | Seating capacity |
| `doors` | Integer | No | - | Number of doors |
| `trailer_hook` | Boolean | No | `False` | |
| `default_co2` | Float | No | - | Default CO2 emissions |
| `co2_emission_unit` | Selection | **Yes** | computed | `g/km` / `g/mi` derived from `range_unit` |
| `co2_standard` | Char | No | - | Emission standard test procedure |
| `default_fuel_type` | Selection | No | `electric` | Default: `electric` in Odoo 19 |
| `power` | Float | No | - | Power value |
| `horsepower` | Float | No | - | |
| `horsepower_tax` | Float | No | - | Horsepower taxation |
| `electric_assistance` | Boolean | No | `False` | |
| `power_unit` | Selection | **Yes** | `power` | `power` (kW) / `horsepower` (hp) |
| `vehicle_properties_definition` | PropertiesDefinition | No | - | Defines the schema for `vehicle_properties` on instances |
| `vehicle_range` | Integer | No | - | Range in km/mi |
| `range_unit` | Selection | **Yes** | `km` | `km` / `mi` |
| `drive_type` | Selection | No | - | `fwd` / `awd` / `rwd` / `4wd` |

### Key Methods

#### `_search_display_name()`
Searches by `name` OR `brand_id.name` (via Domain NEGATIVE_OPERATORS guard). Allows searching "Toyota Corolla" and finding by brand alone.

#### `_compute_vehicle_count()` + `_search_vehicle_count()`
The vehicle count uses `_read_group` for efficient counting. The search method (`search_fetch` + `filtered_domain`) enables `vehicle_count > 0` domain filters in the UI.

#### `_load_fields_from_model()` — Not on the model
This method lives on `fleet.vehicle`, not here. It is the inverse of the pattern: `fleet.vehicle.model` defines the defaults, and `fleet.vehicle` reads them via `_load_fields_from_model()`.

---

## fleet.vehicle.model.brand

**File:** `~/odoo/odoo19/odoo/addons/fleet/models/fleet_vehicle_model_brand.py`
**Order:** `name asc`

### Fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `name` | Char | **Yes** | |
| `active` | Boolean | No | Default: `True` |
| `image_128` | Image | No | Logo; max 128x128 px |
| `model_count` | Integer | No | Computed via `_read_group`; `store=True` |
| `model_ids` | One2many | No | `fleet.vehicle.model` → `brand_id` |

Data: `fleet_cars_data.xml` loads 50+ brands (Abarth, Audi, BMW, Tesla, Toyota, etc.) with base64-encoded logos. `noupdate="0"` so demo data is refreshed on upgrades.

---

## fleet.vehicle.model.category

**File:** `~/odoo/odoo19/odoo/addons/fleet/models/fleet_vehicle_model_category.py`
**Order:** `sequence asc, id asc`

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `name` | Char | **Yes** | Unique constraint enforced |
| `sequence` | Integer | No | Ordering |

**Constraint:** `UNIQUE(name)`

---

## fleet.vehicle.log.contract

**File:** `~/odoo/odoo19/odoo/addons/fleet/models/fleet_vehicle_log_contract.py`
**Inherits:** `mail.thread`, `mail.activity.mixin`
**Order:** `state desc, expiration_date`

### Fields

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `vehicle_id` | Many2one `fleet.vehicle` | **Yes** | `check_company=True`, `tracking=True` |
| `cost_subtype_id` | Many2one `fleet.service.type` | No | Domain: `category='contract'` |
| `amount` | Monetary | No | One-time cost; `tracking=True` |
| `date` | Date | No | When cost was incurred | |
| `company_id` | Many2one `res.company` | No | `self.env.company` |
| `currency_id` | Many2one `res.currency` | No | related via `company_id` |
| `name` | Char | No | computed+stored | `{cost_subtype_id.name} {vehicle_id.name}` |
| `active` | Boolean | No | `True` | |
| `user_id` | Many2one `res.users` | No | defaults from fleet vehicle's `manager_id` context | |
| `start_date` | Date | No | `today` | |
| `expiration_date` | Date | No | `today + 1 year` | |
| `days_left` | Integer | No | computed | Negative values: -1 = closed, 0 = expired/overdue |
| `expires_today` | Boolean | No | computed | |
| `has_open_contract` | Boolean | No | computed | Per-vehicle open contract existence |
| `insurer_id` | Many2one `res.partner` | No | Vendor/insurer | |
| `purchaser_id` | Many2one `res.partner` | No | `related='vehicle_id.driver_id'` | |
| `ins_ref` | Char | No | Reference number; `copy=False` | |
| `state` | Selection | **Yes** | `open` | `futur/open/expired/closed` |
| `notes` | Html | No | `copy=False` | Terms and conditions |
| `cost_generated` | Monetary | No | - | Recurring cost amount |
| `cost_frequency` | Selection | **Yes** | `monthly` | `no/daily/weekly/monthly/yearly` |
| `service_ids` | Many2many `fleet.service.type` | No | - | Services included in contract |

### State Machine

```
futur (New) --[date reaches today]--> open (Running) --[expiration_date passes]--> expired (Expired)
     |                                        |                                       |
     +-------[action_close]--------> closed (Cancelled) <-----------[action_close]------+
```

Four explicit action methods: `action_draft()` → `futur`, `action_open()` → `open`, `action_expire()` → `expired`, `action_close()` → `closed`.

### `write()` — Automatic State Transitions on Date Edit

When `start_date` or `expiration_date` is changed in vals, `write()` recomputes the state:
- If `start_date > today`: `action_draft()`
- If `start_date <= today <= expiration_date`: `action_open()`
- If `today > expiration_date`: `action_expire()`

Also reschedules any `fleet.mail_act_fleet_contract_to_renew` activities to the new `expiration_date` and/or `user_id`.

### Scheduler Cron — `scheduler_manage_contract_expiration()`

Registered as `ir.cron` `ir_cron_contract_costs_generator` (runs daily as `base.user_root`):
1. Creates `fleet.mail_act_fleet_contract_to_renew` activities for open contracts expiring within `delay_alert_contract` days, but only if no such activity already exists for that contract.
2. Transitions all `state not in ['expired', 'closed']` with `expiration_date < today` to `expired`.
3. Transitions all `state not in ['futur', 'closed']` with `start_date > today` to `futur`.
4. Transitions all `state = 'futur'` with `start_date <= today` to `open`.

**Performance note:** Uses `filtered()` against an already-searched recordset to avoid re-querying for the activity type check.

### `days_left` Compute Logic

| Condition | `days_left` | `expires_today` |
|-----------|-------------|-----------------|
| `state` in `['open', 'expired']` and has `expiration_date` | `expiration_date - today` (min 0) | `True` if diff == 0 |
| `state = 'closed'` | `-1` | `False` |
| `state = 'futur'` | `-1` | `False` |

---

## fleet.vehicle.log.services

**File:** `~/odoo/odoo19/odoo/addons/fleet/models/fleet_vehicle_log_services.py`
**Inherits:** `mail.thread`, `mail.activity.mixin`
**Rec Name:** `service_type_id`
**Order:** default (id desc)

### Fields

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `active` | Boolean | No | `True` | |
| `vehicle_id` | Many2one `fleet.vehicle` | **Yes** | - | |
| `model_id` | Many2one | No | related | |
| `brand_id` | Many2one | No | related | |
| `manager_id` | Many2one `res.users` | No | related | |
| `amount` | Monetary | No | - | |
| `description` | Char | No | - | |
| `odometer_id` | Many2one `fleet.vehicle.odometer` | No | - | The odometer record at time of service |
| `odometer` | Float | No | computed/inverse | Via `_get_odometer` / `_set_odometer` |
| `odometer_unit` | Selection | No | related | |
| `date` | Date | No | `today` | |
| `company_id` | Many2one `res.company` | No | `self.env.company` | |
| `currency_id` | Many2one `res.currency` | No | related | |
| `purchaser_id` | Many2one `res.partner` | No | computed | `vehicle_id.driver_id` |
| `inv_ref` | Char | No | - | Vendor reference |
| `vendor_id` | Many2one `res.partner` | No | - | |
| `notes` | Text | No | - | |
| `service_type_id` | Many2one `fleet.service.type` | **Yes** | `fleet.type_service_service_7` (if exists) | |
| `state` | Selection | No | `new` | `new/running/done/cancelled` |

### State Values

| Value | Label | Group Expand |
|-------|-------|--------------|
| `new` | New | Yes |
| `running` | Running | Yes |
| `done` | Done | Yes |
| `cancelled` | Cancelled | Yes |

### Inverse Odometer on Service Log

When `odometer` is set via the inverse (`_set_odometer`), a new `fleet.vehicle.odometer` record is **created** (not updated), linking the reading to the service log via `odometer_id`. The service log's `date` is used as the odometer reading date. If `odometer` is 0, the field is stripped from vals before `create()` to prevent creation of zero-value odometer records.

### `create()` — Strip Zero Odometer

```python
for data in vals_list:
    if 'odometer' in data and not data['odometer']:
        del data['odometer']
```

This prevents a gap in odometer history (a 0 reading would distort interpolation in `fleet.vehicle.odometer.report`).

---

## fleet.vehicle.odometer

**File:** `~/odoo/odoo19/odoo/addons/fleet/models/fleet_vehicle_odometer.py`
**Order:** `date desc`

### Fields

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `name` | Char | No | computed | `{vehicle_id.name} / {date}` |
| `date` | Date | No | `today` | |
| `value` | Float | No | - | Odometer reading; `aggregator="max"` |
| `vehicle_id` | Many2one `fleet.vehicle` | **Yes** | - | |
| `unit` | Selection | No | related | Inherited from `vehicle_id.odometer_unit` |
| `driver_id` | Many2one `res.partner` | No | computed | `vehicle_id.driver_id` if not set |

`aggregator="max"` on `value` enables `_read_group` to use `value:max` as an aggregate in cost reporting.

### `_compute_vehicle_log_name()`
Name is constructed as `{vehicle.name}` if set, or just `{date}` if vehicle has no name, or `{vehicle.name} / {date}` if both are set.

### `_onchange_vehicle()`
When the vehicle changes in the UI form, `unit` is synced from the vehicle's `odometer_unit`. This is an `onchange`, not a computed field.

---

## fleet.vehicle.assignation.log

**File:** `~/odoo/odoo19/odoo/addons/fleet/models/fleet_vehicle_assignation_log.py`
**Order:** `create_date desc, date_start desc`

### Fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `vehicle_id` | Many2one `fleet.vehicle` | **Yes** | |
| `driver_id` | Many2one `res.partner` | **Yes** | |
| `date_start` | Date | No | Start of assignment |
| `date_end` | Date | No | End of assignment (set when driver leaves) |

Created automatically by `fleet.vehicle.write()` when `driver_id` changes, and by `fleet.vehicle.create()` if `driver_id` is provided at creation time.

**Note:** `date_end` is never set automatically — the UI or a scheduled activity prompts the manager to set it manually.

---

## fleet.service.type

**File:** `~/odoo/odoo19/odoo/addons/fleet/models/fleet_service_type.py`

### Fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `name` | Char | **Yes** | Translatable |
| `category` | Selection | **Yes** | `contract` / `service` |

Service types with `category='contract'` appear in `fleet.vehicle.log.contract.cost_subtype_id`. Service types with `category='service'` (or both) appear in `fleet.vehicle.log.services.service_type_id`. Pre-loaded types include: "Omnium" (contract), "Leasing" (contract), and many via demo data.

---

## fleet.vehicle.state

**File:** `~/odoo/odoo19/odoo/addons/fleet/models/fleet_vehicle_state.py`
**Order:** `sequence asc`

### Fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `name` | Char | **Yes** | Translatable; unique constraint |
| `sequence` | Integer | No | Kanban ordering |
| `fold` | Boolean | No | Collapse in Kanban view |

### Default States (from `fleet_data.xml`)

| XMLID | Name | Sequence |
|-------|------|----------|
| `fleet.fleet_vehicle_state_new_request` | New Request | 4 |
| `fleet.fleet_vehicle_state_to_order` | To Order | 5 |
| `fleet.fleet_vehicle_state_registered` | Registered | 7 |
| `fleet.fleet_vehicle_state_downgraded` | Downgraded | 8 |

**Note:** Sequence values 4, 5, 7, 8 suggest intermediate states (1–3, 6) may be defined by `hr_fleet` or other extensions.

**Constraint:** `unique(name)`

---

## fleet.vehicle.tag

**File:** `~/odoo/odoo19/odoo/addons/fleet/models/fleet_vehicle_tag.py`

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `name` | Char | **Yes** | Translatable; unique |
| `color` | Integer | No | Kanban color index |

**Constraint:** `unique(name)`

---

## fleet.vehicle.cost.report

**File:** `~/odoo/odoo19/odoo/addons/fleet/report/fleet_report.py`
**Type:** Auto-created SQL View (`_auto = False`)
**Order:** `date_start desc`

### Fields (all readonly)

| Field | Type | Notes |
|-------|------|-------|
| `company_id` | Many2one `res.company` | |
| `vehicle_id` | Many2one `fleet.vehicle` | |
| `name` | Char | `fleet.vehicle.name` (denormalized at report time) |
| `driver_id` | Many2one `res.partner` | |
| `fuel_type` | Char | |
| `date_start` | Date | Month-start date |
| `vehicle_type` | Selection | `car` / `bike` |
| `cost` | Float | Monthly aggregated cost |
| `cost_type` | Selection | `contract` / `service` |

### SQL View Architecture

The view uses two CTEs:

**`service_costs` CTE:**
- `CROSS JOIN generate_series()` from `min(date)` of `fleet_vehicle_log_services` to `CURRENT_DATE + 1 month`, monthly intervals.
- `LEFT JOIN` services grouped by vehicle and truncated month.
- Filters: `ve.active AND se.active AND se.state != 'cancelled'`
- Aggregate: `COALESCE(sum(se.amount), 0)`

**`contract_costs` CTE:**
- `CROSS JOIN generate_series()` from `min(acquisition_date)` of `fleet_vehicle` to `CURRENT_DATE + 1 month`, monthly intervals.
- Joins four contract cost patterns: `amount` (one-time), `cost_generated` daily (prorated over days in month), `cost_generated` monthly, `cost_generated` yearly (prorated).
- Filter: `ve.active` (no active filter on contract — closed contracts still appear, which is intentional for historical cost reporting)

**Performance Implications:**
- `generate_series()` creates one row per vehicle per month from first service/vehicle to current date. For a 5-year-old vehicle with 60 months, this generates 60 rows.
- The view is `UNION ALL` of service and contract rows — not a single unified row per vehicle per month.
- Inherited by `fleet_account` for `account.move.line` generation.

---

## fleet.vehicle.odometer.report

**File:** `~/odoo/odoo19/odoo/addons/fleet/report/odometer_report.py`
**Type:** Auto-created SQL View (`_auto = False`)
**Order:** `recorded_date desc`

### Fields (all readonly)

| Field | Type | Notes |
|-------|------|-------|
| `vehicle_id` | Many2one `fleet.vehicle` | |
| `category_id` | Many2one | related to `vehicle_id` |
| `model_id` | Many2one | related to `vehicle_id` |
| `fuel_type` | Selection | related to `vehicle_id` |
| `mileage_delta` | Float | Monthly interpolated mileage |
| `odometer_value` | Float | Cumulative odometer value |
| `recorded_date` | Date | Month-start date |

### SQL View Architecture (14 CTE Steps)

1. **vehicle_odometer**: Raw join of `fleet_vehicle_odometer` with `fleet_vehicle` for acquisition dates.
2. **vehicle_odometer_single_date**: `DISTINCT ON (vehicle_id, date)` picks the max-value reading per date.
3. **vehicle_odometer_acquisition_date**: Unions actual readings with a synthetic 0km reading at `acquisition_date` if it predates all readings.
4. **vehicle_odometer_prev_and_next**: Window `LAG`/`LEAD` over value and date per vehicle.
5. **vehicle_odometer_date_range**: Date range from min acquisition date to max reading date.
6. **vehicle_odometer_date_range_min_date**: `CROSS JOIN LATERAL GENERATE_SERIES()` creates monthly entries, `FIRST_VALUE` fills forward missing readings.
7. **vehicle_odometer_prev_next_date**: Re-computes prev/next for generated rows.
8. **vehicle_odometer_prev_next_complete**: Fills in actual prev/next values for generated readings.
9. **vehicle_odometer_strict_prev**: `LAG` of date to compute strict previous reading.
10. **vehicle_odometer_filled_gaps**: Linear interpolation of missing odometer values using ratio of days.
11. **vehicle_odometer_interpolated**: Cumulative sum of raw mileage deltas.
12. **vehicle_odometer_days_diff**: Days between readings for weighting.
13. **vehicle_weighted_mileage**: Splits mileage across month boundaries (pro-rata by days).
14. **final_results**: Cumulative odometer = running sum of `mileage_delta`.

**L4 Edge Cases:**
- If a vehicle has one reading only, interpolation uses only the `prev_value IS NULL` branch (returns the raw value as-is).
- `NULLIF(..., 0)` guards division by zero when days_span is 0 (same-day readings).
- The synthetic 0km row at `min_month_minus_one` anchors the cumulative sum correctly.
- Rows without a previous reading are handled by `COALESCE(LAG(...), 0)` for the delta computation.

---

## fleet.vehicle.send.mail

**File:** `~/odoo/odoo19/odoo/addons/fleet/wizard/fleet_vehicle_send_mail.py`
**Type:** Transient Model
**Inherits:** `mail.composer.mixin`

### Fields

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `vehicle_ids` | Many2many `fleet.vehicle` | **Yes** | |
| `author_id` | Many2one `res.partner` | **Yes** | Default: current user |
| `template_id` | Many2one `mail.template` | No | Filtered to `fleet.vehicle` model |
| `attachment_ids` | Many2many `ir.attachment` | No | `bypass_search_access=True` |

### Key Methods

#### `action_send()`
Renders the email body/subject per vehicle (not batched — one `message_post` per vehicle). Validates that all selected vehicles have a driver with an email address. Uses `mail.mail_notification_light` layout. `partner_ids` = `vehicle.driver_id.ids`.

If `template_id` is set, renders subject/body via `_render_field()`. Otherwise uses wizard's own `subject` and `body`.

#### `action_save_as_template()`
Creates a `mail.template` record linked to `fleet.vehicle`, copies subject/body and attachments. Attachments are re-parented to the template (`res_model=mail.template`, `res_id=template.id`).

**Security note:** Only attachments created by the current user are included (`filtered(lambda a: a.create_uid.id == self.env.uid)`).

---

## mail.activity.type — fleet extension

**File:** `~/odoo/odoo19/odoo/addons/fleet/models/mail_activity_type.py`

### `_get_model_info_by_xmlid()`
Overrides the super method to add `fleet.mail_act_fleet_contract_to_renew`:
```python
info['fleet.mail_act_fleet_contract_to_renew'] = {
    'res_model': 'fleet.vehicle.log.contract',
    'unlink': False,   # don't auto-unlink duplicate activities
}
```
This is consumed by the scheduler to avoid creating duplicate renewal activities for the same contract.

---

## Security Model

### Access Groups

| Group | Name | Implied By | Privilege Level |
|-------|------|-----------|----------------|
| `fleet.fleet_group_user` | Officer: Manage all vehicles | `base.group_user` | Read-only on models; full on vehicles, contracts, odometer |
| `fleet.fleet_group_manager` | Administrator | `fleet_group_user` | Full CRUD on all models |

### Access Control Matrix (ir.model.access.csv)

| Model | fleet_group_user | fleet_group_manager |
|-------|-----------------|---------------------|
| `fleet.vehicle` | CRUD | CRUD |
| `fleet.vehicle.model` | R | CRUD |
| `fleet.vehicle.model.brand` | R | CRUD |
| `fleet.vehicle.model.category` | R | CRUD |
| `fleet.vehicle.state` | R | CRUD |
| `fleet.vehicle.tag` | R | CRUD |
| `fleet.vehicle.log.contract` | CRUD | CRUD |
| `fleet.vehicle.log.services` | R | CRUD |
| `fleet.vehicle.odometer` | CRUD | CRUD |
| `fleet.service.type` | R | CRUD |
| `fleet.vehicle.assignation.log` | CRUD | CRUD |
| `fleet.vehicle.cost.report` | R | - |
| `mail.activity.type` | - | CRUD |
| `fleet.vehicle.send.mail` | - | CRUD |
| `fleet.vehicle.odometer.report` | - | CRUD |

**Officer read-only gap:** `fleet_group_user` cannot write `fleet.vehicle.model`, `fleet.vehicle.model.brand`, `fleet.vehicle.model.category`, `fleet.vehicle.state`, `fleet.vehicle.tag`, `fleet.service.type`, `fleet.vehicle.log.services`. Officers can only log services and contracts — they cannot edit service types or vehicle catalog data.

### Record Rules (ir.rule)

| Rule | Model | Scope |
|------|-------|-------|
| Admin all-rights | `fleet.vehicle.log.contract` | `fleet_group_manager` — no domain |
| Admin all-rights | `fleet.vehicle.log.services` | `fleet_group_manager` |
| Admin all-rights | `fleet.vehicle.odometer` | `fleet_group_manager` |
| Admin all-rights | `fleet.vehicle` | `fleet_group_manager` |
| Multi-company | `fleet.vehicle` | Global: `company_id in company_ids + [False]` |
| Multi-company | `fleet.vehicle.log.contract` | Global: `company_id in company_ids + [False]` |
| Multi-company | `fleet.vehicle.cost.report` | Global: same |
| Multi-company | `fleet.vehicle.odometer` | Global: `vehicle_id.company_id in company_ids + [False]` |
| Multi-company | `fleet.vehicle.log.services` | Global: `company_id in company_ids + [False]` |

---

## Cron Jobs

| Cron | Model | Frequency | Action |
|------|-------|-----------|--------|
| `ir_cron_contract_costs_generator` | `fleet.vehicle.log.contract` | Daily | `run_scheduler()` → manages contract states and renewal activities |

---

## Odoo 18 → 19 Key Changes

1. **`default_fuel_type` default changed from `'gasoline'` to `'electric'`** — Odoo 19 defaults new vehicle models to electric, reflecting the shift in fleet composition.

2. **`avatar.mixin`** added to `fleet.vehicle` and `fleet.vehicle.model` — enables image avatars on vehicle records and model records via the standard avatar mixin.

3. **`electric_assistance` field** added to both `fleet.vehicle` and `fleet.vehicle.model` — tracks whether a vehicle (especially bike) has electric motor assistance.

4. **`drive_type` field** added to `fleet.vehicle.model` — captures FWD/AWD/RWD/4WD.

5. **`frame_type` and `frame_size` fields** added to `fleet.vehicle` — dedicated fields for bike frame type (diamant/trapez/wave) and frame size.

6. **`vehicle_properties_definition` / `vehicle_properties`** — PropertiesDefinition on model and Properties on vehicle enable custom per-vehicle or per-model properties (e.g., insurance class, emission band). This is an Odoo 18+ feature.

7. **`plan_to_change_car` / `plan_to_change_bike` flags** — HR-facing flags that trigger driver reassignment workflow. These are toggled automatically when a `future_driver_id` is assigned to a vehicle that the future driver already drives elsewhere.

8. **`co2_standard` field** — New field on both model and vehicle capturing the regulatory test procedure (e.g., WLTP, NEDC).

9. **`MODEL_FIELDS_TO_VEHICLE` propagation pattern** — The field copying mechanism from model to vehicle was enhanced; the map is defined centrally in `fleet_vehicle.py` and consumed by `_load_fields_from_model()`, which caches writes per `model_id` to avoid redundant updates.

10. **`generate_series` in cost.report SQL view** — The CTE uses `generate_series` to fill in monthly rows even when no cost record exists for a given month, ensuring complete time-series data for charts.

11. **`vehicle_range` / `range_unit`** added to both model and vehicle — supports electric vehicle range tracking with km/mi unit.

12. **`power_unit` selection** changed default from `'horsepower'` to `'power'` (kW) — reflecting EV power notation.

13. **`_auto = False` on report models** — Explicitly disables ORM auto-view creation; the `init()` method runs raw SQL on module install/update.

---

## Cross-Module Integration

### With `mail`
- `mail.thread` on `fleet.vehicle`, `fleet.vehicle.log.contract`, `fleet.vehicle.log.services`, `fleet.vehicle.model` — Chatter and tracking.
- `mail.activity.mixin` — Activity scheduling (contract renewal reminders, driver end-date prompting).
- `mail.activity.type` extended to register the `fleet.mail_act_fleet_contract_to_renew` activity type.

### With `hr` / `hr_fleet` (separate module)
- `plan_to_change_car` / `plan_to_change_bike` flags signal HR when a vehicle replacement should be planned.
- `future_driver_id` + `next_assignation_date` coordinate handover scheduling.

### With `fleet_account` (separate module)
- `fleet.vehicle.cost.report` SQL view aggregates costs that `fleet_account` uses to generate `account.move.line` entries for each contract/service.
- `_get_analytic_name()` on `fleet.vehicle` returns `license_plate` for analytic account naming.
- `car_value`, `net_car_value`, `residual_value` fields feed into asset depreciation entries.

### With `base` / `base_calendar` (implicit)
- `mail.composer.mixin` used by `fleet.vehicle.send.mail` wizard.

---

## Performance Considerations

| Area | Concern | Mitigation |
|------|---------|-----------|
| `_compute_count_all()` | Called on every form open | Uses single `_read_group` per aggregate type |
| `scheduler_manage_contract_expiration()` | Runs daily, searches full contract table | Filters to active non-closed contracts; uses `filtered()` over search results |
| `fleet.vehicle.cost.report` | `generate_series` per vehicle per month | Scales with vehicle count × months in fleet lifetime |
| `fleet.vehicle.odometer.report` | 14-CTE SQL view with window functions | Views are materialised on init; not queried live unless accessed |
| `_load_fields_from_model()` | Called on create and on `model_id` change | Caches model values per `model_id.id` to avoid redundant `model_id[id]` lookups |
| `model_count` on brand | `_read_group` per brand | Uses `_read_group` aggregate efficiently |

---

## Edge Cases and Failure Modes

1. **Odometer rollback prevention:** `write()` raises `UserError` if new odometer < current. The inverse setter also raises if attempting to set to 0.

2. **Zero odometer on service create:** `create()` strips `odometer=0` from vals before calling `super()`, preventing zero-value odometer records from being created via the service form.

3. **Contract state auto-transition:** If a contract's dates are edited, `write()` automatically transitions the state — even if manually set to a different state. Order: futur check before open check before expired.

4. **Closed contract cascade:** Setting `fleet.vehicle.active=False` deactivates all related contracts and services. This is a one-way soft-delete pattern.

5. **Duplicate renewal activities:** The scheduler checks `reminder_activity_type not in nec.activity_ids.activity_type_id` to avoid scheduling multiple renewal activities for the same contract. The `unlink: False` in `mail_activity_type._get_model_info_by_xmlid()` is part of this guard.

6. **Vehicle without model:** `model_id` is required — a vehicle cannot exist without a model reference.

7. **Future driver assignment to already-assigned vehicle:** If a `future_driver_id` is already driving another vehicle of the same type, that other vehicle gets `plan_to_change_* = True` flagged. The `action_accept_driver_change()` clears the old vehicle's driver.

8. **Multi-company odometer visibility:** The `ir.rule` on `fleet.vehicle.odometer` uses `vehicle_id.company_id`, meaning odometer records are visible if the **vehicle** is in the user's company — not the odometer's own company (which is inherited from the vehicle anyway).

9. **Brand with no models:** `model_count` correctly returns 0 for brands with no active models.

10. **Service log `state='cancelled'` excluded from cost report:** `fleet.vehicle.cost.report` filters `se.state != 'cancelled'` in the service_costs CTE.

---

## Related Modules

- [Modules/account_fleet](Modules/account_fleet.md) — Accounting integration for fleet costs
- [Modules/HR](Modules/HR.md) — HR module (driver management, plan_to_change flags)
- [Modules/mail](Modules/mail.md) — Mail and activity tracking
- [Core/API](Core/API.md) — @api.depends, @api.onchange patterns
- [Patterns/Workflow Patterns](Patterns/Workflow Patterns.md) — State machine patterns (e.g., contract states)

---

## See Also

- [Modules/Stock](Modules/Stock.md) — warehouse/location tracking
- [Modules/Purchase](Modules/Purchase.md) — vendor contracts
- [Modules/Account](Modules/Account.md) — accounting entries from fleet costs
