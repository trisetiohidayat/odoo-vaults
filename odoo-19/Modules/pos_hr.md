---
date: 2026-04-11
tags:
  - odoo
  - odoo19
  - modules
  - pos_hr
  - point_of_sale
  - hr
---

# pos_hr — Point of Sale HR Integration

> **Technical name:** `pos_hr`
> **Category:** Sales/Point of Sale
> **Depends:** `point_of_sale`, `hr`
> **Auto-install:** `True`
> **License:** LGPL-3
> **Author:** Odoo S.A.`

Links the Point of Sale module to the HR module, enabling **employee-based POS authentication** (barcode + PIN), **three-tier role-based access control per POS config**, and **per-cashier revenue attribution** on orders, payments, and cash moves. The POS session tracks the currently logged-in employee (cashier). All orders, payment records, and cash move lines are attributed to the responsible employee.

---

## L1 — Conceptual Model and Module Map

### Core Concept

Traditional POS authentication requires a named Odoo user to log in. The `pos_hr` module decouples POS access from user accounts: an unlimited number of employees can log in to a single POS session using a **barcode scan** (or manual entry) plus a **PIN**, while the session itself runs under a single Odoo user account. Each sale order is then attributed to the employee who processed it.

**Three access tiers** are configurable per `pos.config`:

| Tier | Field on `pos.config` | Role ID (frontend) | Meaning |
|---|---|---|---|
| Manager | `advanced_employee_ids` | `manager` | Can open/close sessions, process refunds, access reports |
| Basic | `basic_employee_ids` | `cashier` | Standard POS operations |
| Minimal | `minimal_employee_ids` | `minimal` | Restricted operations (configurable per deployment) |
| Default | Unlisted employees | `cashier` | Standard POS operations (when no restrict list set) |

### Module File Map

```
~/odoo/odoo19/odoo/addons/pos_hr/
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── pos_config.py          # pos.config extension: 3-tier employee access
│   ├── pos_session.py         # pos.session extension: cashier tracking
│   ├── pos_order.py          # pos.order extension: employee attribution
│   ├── pos_payment.py        # pos.payment extension: employee on payments
│   ├── account_bank_statement.py  # account.bank.statement.line extension
│   ├── hr_employee.py        # hr.employee extension: POS data loading + PIN hashing
│   ├── product_product.py    # product.product: all_product_tag_ids in POS data
│   ├── res_config_settings.py # res.config.settings extension
│   └── single_employee_sales_report.py  # POS report per employee
├── views/
│   ├── pos_config.xml         # Employee access lines in POS config form
│   ├── pos_order_view.xml     # employee_id + cashier fields on order form
│   ├── pos_payment_view.xml   # cashier field on payment form
│   ├── pos_order_report_view.xml  # report action for per-employee report
│   ├── single_employee_sales_report.xml  # wizard action
│   └── res_config_settings_views.xml
├── wizard/
│   └── pos_daily_sales_reports.xml  # Daily sales report wizard
└── static/src/
    └── app/
        ├── screens/login_screen/      # Employee login screen
        ├── components/navbar/         # Cashier name display in navbar
        ├── components/popups/         # Cashier selection + closing popups
        └── components/ticket_screen/ # Ticket screen cashier display
```

### Model Inventory

| # | Internal ID | File | Role |
|---|---|---|---|
| 1 | `pos.session` | `pos_session.py` | `employee_id` (current cashier), message author, per-employee closing aggregation |
| 2 | `pos.order` | `pos_order.py` | `employee_id` and `cashier` on orders |
| 3 | `pos.payment` | `pos_payment.py` | `employee_id` on payments, `_compute_cashier` |
| 4 | `account.bank.statement.line` | `account_bank_statement.py` | `employee_id` on cash moves |
| 5 | `pos.config` | `pos_config.py` | Three-tier employee access: `minimal/basic/advanced_employee_ids` |
| 6 | `hr.employee` | `hr_employee.py` | POS data loading, barcode/PIN hashing, delete protection |
| 7 | `res.config.settings` | `res_config_settings.py` | Settings mirror for employee access fields |
| 8 | `report.pos_hr.single_employee_sales_report` | `single_employee_sales_report.py` | Per-employee sales detail report |
| 9 | `product.product` | `product_product.py` | Adds `all_product_tag_ids` to POS data load |

---

## L2 — Field Inventory, Defaults, Constraints

### `pos.session` — Extension Fields

> **File:** `models/pos_session.py`
> **Inherits:** `pos.session`

| Field | Type | Default | Notes |
|---|---|---|---|
| `employee_id` | `Many2one hr.employee` | — | The employee currently using the cash register. `tracking=True`. Set by the POS frontend on employee login. |

### `pos.order` — Extension Fields

> **File:** `models/pos_order.py`
> **Inherits:** `pos.order`

| Field | Type | Default | Notes |
|---|---|---|---|
| `employee_id` | `Many2one hr.employee` | — | The cashier who created the order. Set from the session's `employee_id` at order creation time. |
| `cashier` | `Char` | computed | Display name of the cashier. `compute='_compute_cashier'`, `store=True`. Prefers `employee_id.name` over `user_id.name`. |

**Note on `pos.order.line`:** The task description references `is_employee_count` and `employee_id` on `pos.order.line`. These fields **do not exist** in the Odoo 19 source code. Employee attribution in Odoo 19 is placed at the **order level** (`pos.order.employee_id`), not the line level. There is no `is_employee_count` field anywhere in the `pos_hr` module.

### `pos.payment` — Extension Fields

> **File:** `models/pos_payment.py`
> **Inherits:** `pos.payment`

| Field | Type | Default | Notes |
|---|---|---|---|
| `employee_id` | `Many2one hr.employee` | related → `pos_order_id.employee_id` | `store=True`, `index=True`. Inherited from the parent order. |
| `cashier` | `Char` | computed | Overrides base `_compute_cashier`. Prefers `employee_id.name` over `user_id.name`. |

### `account.bank.statement.line` — Extension Fields

> **File:** `models/account_bank_statement.py`
> **Inherits:** `account.bank.statement.line`

| Field | Type | Default | Notes |
|---|---|---|---|
| `employee_id` | `Many2one hr.employee` | — | The employee who made the cash move (cash in/out during the POS session). Set via `_prepare_account_bank_statement_line_vals()` from frontend extras. |

### `pos.config` — Extension Fields

> **File:** `models/pos_config.py`
> **Inherits:** `hr.mixin`, `pos.config`

| Field | Type | Default | Notes |
|---|---|---|---|
| `minimal_employee_ids` | `Many2many hr.employee` | — | Employees with minimal access. If empty, all employees can log in. Mutually exclusive with other tiers. |
| `basic_employee_ids` | `Many2many hr.employee` | — | Employees with basic access. Mutually exclusive with other tiers. |
| `advanced_employee_ids` | `Many2many hr.employee` | — | Employees with manager access. Auto-populated from `group_pos_manager` members on every `write()`. Mutually exclusive with other tiers. |

### `hr.employee` — Extension Fields

> **File:** `models/hr_employee.py`
> **Inherits:** `hr.employee`, `pos.load.mixin`

No new persistent fields. All new fields are transient (returned to the POS frontend only):

| Return Field | Type | Notes |
|---|---|---|
| `_role` | string | Frontend role: `'manager'`, `'minimal'`, `'cashier'` |
| `_user_role` | string | Only `'admin'` when employee's user has `group_pos_manager`. Used for full backend feature access. |
| `_barcode` | string | SHA1 hash of employee barcode (or `False`) |
| `_pin` | string | SHA1 hash of employee PIN (or `False`) |

### `res.config.settings` — Mirror Fields

> **File:** `models/res_config_settings.py`

All three `pos_hr` fields on `pos.config` are mirrored here with `readonly=False` to allow setting from the Settings app:

```python
pos_basic_employee_ids    = fields.Many2many(related='pos_config_id.basic_employee_ids',    readonly=False)
pos_advanced_employee_ids = fields.Many2many(related='pos_config_id.advanced_employee_ids', readonly=False)
pos_minimal_employee_ids = fields.Many2many(related='pos_config_id.minimal_employee_ids', readonly=False)
```

### Constraints

| Location | Constraint | Logic |
|---|---|---|
| `pos_config.onchange` | Mutual exclusion | `_onchange_minimal/basic/advanced_employee_ids`: if an employee is moved to one tier, it is removed from the other two. Manager-group employees are removed from `minimal` and `basic` automatically. |
| `hr_employee._unlink_except_active_pos_session` | Delete protection | Raises `UserError` if the employee could be checked in to an active POS session. Two threat models: (1) configs with no restrict list block all employees; (2) configs with restrict lists only block listed employees. |

### POS Data Loading Fields (`_load_pos_data_fields`)

Only these `hr.employee` fields are transmitted to the POS frontend during session initialization:

```python
['name', 'user_id', 'work_contact_id']
```

Plus the transient `_role`, `_user_role`, `_barcode`, `_pin` computed by `_load_pos_data_read()`.

---

## L3 — Cross-Model Integration, Override Patterns, Workflow Triggers, Failure Modes

### Cross-Model: POS ↔ HR Integration Map

```
pos_hr bridges three separate systems:

HR System                    POS System                    Accounting System
─────────────────────        ────────────────────          ──────────────────────
hr.employee ──────────────────► pos.config ──────────────────────► pos.session
(record: employee)             (access control)               (who is working)
                               │                                │
                               │                                ▼
                               │                         pos.order
                               │                    (employee_id = cashier)
                               │                                │
                               ▼                                ▼
                         pos.session              pos.payment         account.bank.statement.line
                    (employee_id = current     (employee_id from     (employee_id on
                     cashier, session start)   parent order)       cash moves)
```

The flow is unidirectional: `hr.employee` is read (loaded into POS), but `pos.session.employee_id` and `pos.order.employee_id` are written by the POS frontend when an employee logs in.

### Override Patterns

#### Pattern: `hr.mixin` multiple inheritance on `pos.config`

```python
class PosConfig(models.Model):
    _name = 'pos.config'
    _inherit = ['hr.mixin', 'pos.config']   # Multiple inheritance
```

`hr.mixin` is the standard Odoo mixin that provides `company_id` from the active user/company context. `pos_hr` inherits it to ensure the config's company is properly tracked alongside HR data.

#### Pattern: `sudo()` for corecord writes

```python
def write(self, vals):
    # ... process vals ...
    sudo_vals = {field_name: vals.pop(field_name) ...}
    res = super().write(vals)
    if sudo_vals:
        super(PosConfig, self.sudo()).write(sudo_vals)  # elevated write
    return res
```

Employee Many2many fields are written in `sudo()` because regular users may not have read access to all `hr.employee` records referenced in the config. The `sudo()` call is scoped to only the three employee ID fields.

#### Pattern: Force-repopulate on every write

```python
def write(self, vals):
    if 'advanced_employee_ids' not in vals:
        vals['advanced_employee_ids'] = []   # Reset first
    vals['advanced_employee_ids'] += [
        (4, emp_id) for emp_id in self._get_group_pos_manager().user_ids.employee_id.ids
    ]
    # ...
```

Every `write()` to `pos.config` unconditionally resets and repopulates `advanced_employee_ids` from current `group_pos_manager` members. This keeps the manager list in sync with the permission group without requiring manual maintenance. It also means explicitly clearing `advanced_employee_ids` in a write call requires both setting it to `[]` AND removing `group_pos_manager` from the user.

#### Pattern: Frontend-driven employee attribution

The POS frontend (JavaScript) sets `employee_id` on the session and on each order. The backend only validates through the `_employee_domain()` filter — it does not independently set `employee_id`. This means a correctly authenticated POS session will attribute all subsequent orders to the logged-in employee.

### Workflow Triggers

#### Trigger 1: POS session start — employee domain filter

```
pos.session._load_pos_data()
  → loads hr.employee records filtered by config._employee_domain()
  → hr.employee._load_pos_data_read()
    → assigns role per employee (cashier/manager/minimal)
    → attaches SHA1-hashed barcode + PIN
  → POS frontend displays cashier selection popup
  → Employee scans barcode + enters PIN
  → Frontend validates SHA1(PIN) match
  → pos.session.employee_id set to logged-in employee
```

#### Trigger 2: Order creation — employee attribution

```
POS frontend creates pos.order
  → pos.order.employee_id = session.employee_id
  → pos.order.cashier computed from employee_id
  → pos.payment.employee_id inherited from parent order
  → pos.payment.cashier computed from employee_id
```

#### Trigger 3: Cash move — employee on statement line

```
POS frontend calls /pos_session/pack_multiple_products
  → with extras: {employee_id: <id>}
  → pos.session._prepare_account_bank_statement_line_vals()
    → reads extras.get('employee_id')
    → injects into statement line vals
```

#### Trigger 4: Session close — per-employee aggregation

```
Manager triggers session close
  → pos.session.get_closing_control_data()
    → _aggregate_payments_amounts_by_employee()
      → groups orders.payment_ids by employee_id
      → sums amounts per employee per payment method
    → _aggregate_moves_by_employee()
      → groups statement_line_ids by employee_id
      → sums cash move amounts per employee
    → closing popup shows amount_per_employee for each payment method
  → post_close_register_message()
    → _get_message_author() resolves employee → work contact partner
    → "Closed Register" message posted to session chatter
```

### Failure Modes

| Failure Mode | Cause | Behavior |
|---|---|---|
| **Wrong employee PIN** | Frontend compares SHA1 hashes. If PIN wrong, authentication fails. | Employee cannot log in. No backend state change. |
| **Deleting employee with active POS session** | `hr.employee._unlink_except_active_pos_session()` checks active sessions | Raises `UserError` listing affected POS configs and employee name. Must close session first. |
| **Empty restrict lists (`basic_employee_ids` empty)** | No employees in `basic_employee_ids` | Domain becomes empty for restrict check → all employees in the company can log in. This is intentional. |
| **Employee in multiple access tiers** | Onchange guards prevent this | Onchanges automatically remove employee from other tiers when added to one. |
| **Manager removed from `group_pos_manager`** | Done via Users app | On next `pos.config` write, `advanced_employee_ids` is reset and repopulated — employee is automatically removed from manager tier. |
| **Employee with no user linked** | HR setup gap | Employee's barcode/PIN are still hashed and sent. They can log in to POS but there is no user to associate with. The `_employee_domain` check includes `('user_id', '=', user_id)` as one option. |
| **PIN hashed with SHA1 — rainbow table attack** | If database is compromised, SHA1(PIN) can be looked up in precomputed tables | SHA1 is used for hardware compatibility and frontend parity, not cryptographic security. Treat database access as equivalent to PIN exposure. See L4 Security. |
| **`module_pos_hr = False` but employees configured** | Config setting disabled | `_employee_domain()` returns standard company domain (no employee filter). Employee-based login is bypassed. The `employee_id` fields on session/order are still set from the POS frontend if an employee is logged in. |
| **Employee deleted while POS session running** | Employee record removed from DB | Session continues with stale `employee_id` in database. Orders created will have stale FK. This is a data integrity risk — the delete protection prevents it under normal conditions. |

---

## L4 — Version Changes, Security, Performance

### Odoo 18 → 19 Changes

| Change | Detail |
|---|---|
| **PIN security redesign** | In Odoo 18, the raw PIN was transmitted to the server for comparison. In Odoo 19, both the database (`hr.employee.pin` stored as SHA1) and the frontend (hashes scanned PIN before sending) use SHA1 comparison. Raw PIN never crosses the wire. This was implemented via the new `get_barcodes_and_pin_hashed()` method on `hr.employee` and `_load_pos_data_read()` role assignment. |
| **`_get_message_author()` on `pos.session`** | New method for resolving message author from `employee_id`. In Odoo 18, messages were posted under the session user's partner. Odoo 19 uses the employee's work contact partner for better attribution when an employee (not a direct user) is logged in. |
| **`_aggregate_moves_by_employee()`** | New method aggregating cash move statement lines by employee. Used in `get_closing_control_data()` to show cash move breakdown per employee on the closing screen. |
| **Employee per cash move** | `account.bank.statement.line.employee_id` is new in Odoo 19. In Odoo 18, cash moves did not track which employee made them. |
| **`_prepare_account_bank_statement_line_vals()` override** | New override that injects `employee_id` from frontend extras into statement line vals. Enables per-employee cash move attribution. |
| **`post_close_register_message()` override** | New override that skips calling `super()` when an `employee_id` is set. The parent's behavior (full session close sequence) is replaced with direct message posting using `_get_message_author()`. |
| **`get_cash_in_out_list()` — `cashier_name` per move** | Cash-in/out list now includes `cashier_name` (the partner name of the employee who made the cash move) when `module_pos_hr` is enabled. |
| **`product.product` POS data: `all_product_tag_ids`** | New field added to POS data load via `_load_pos_data_fields()`. The `pos_hr` module adds this to the standard POS product data. |
| **`_load_pos_data_models()` — `hr.employee` added** | `pos.session` now explicitly adds `hr.employee` to the POS data models list when `module_pos_hr` is enabled, ensuring employee records are loaded during session initialization. |

### Security Analysis

#### Authentication Security

**Barcode and PIN are hashed with SHA1 before transmission.** The database stores `hr.employee.barcode` and `hr.employee.pin` as SHA1 hex digests. The POS frontend hashes the scanned barcode and entered PIN with the same algorithm before sending to the server for comparison.

```python
# Database storage (get_barcodes_and_pin_hashed)
e['barcode'] = hashlib.sha1(e['barcode'].encode('utf8')).hexdigest() if e['barcode'] else False
e['pin']     = hashlib.sha1(e['pin'].encode('utf8')).hexdigest()     if e['pin']     else False

# Frontend comparison (POS JavaScript)
const pinHash = sha1(sanitize夏ML(request.pin));
const barcodeHash = sha1(sanitize夏ML(request.barcode));
```

**Risk:** SHA1 is a fast, unsalted hash. If an attacker gains read access to the `hr_employee` table, they can crack short PINs (e.g., 4-digit) using precomputed rainbow tables within seconds. The PIN is not a secret in the cryptographic sense — it is a convenience credential similar to a username. The actual security boundary is database access control.

**Mitigation:** The `pin` field should be considered low-security. For high-security environments, supplement with barcode hardware that communicates directly with Odoo over TLS, or implement additional application-layer checks.

#### `sudo()` in `get_barcodes_and_pin_hashed()`

```python
visible_emp_ids = self.search([('id', 'in', self.ids)])   # Respects record rules
employees_data = self.sudo().search_read([...], ['barcode', 'pin'])
```

The `sudo()` is preceded by a visibility-filtered search. Only employees visible to the current user are queried under sudo. This is a deliberate design to bypass `hr.employee` ACL restrictions for barcode/PIN data, which are not sensitive in the same way as salary or personal data. The risk is scoped: a user who can open a POS session can see the barcodes/PINs of all employees in the same company.

#### Delete protection

`_unlink_except_active_pos_session()` prevents removal of employees who could be logged in to an active session. This prevents data corruption where an order or payment references a deleted employee. However, it does not prevent the reverse: an employee can be deleted after their session closes but before orders are reconciled.

#### ACL Implications

`pos_hr` does not define its own `ir.model.access.csv`. All access control is inherited from `point_of_sale` and `hr`. Users who can access POS can see employee names and roles. Only users with `hr` group access can see employee personal data (barcode/PIN are not personal data under GDPR — they are access credentials).

#### Session vs. User distinction

The critical security property: a POS session runs under one Odoo user, but any number of employees can log in to it. All operations (orders, payments, cash moves) are attributed to the logged-in employee, not the session user. This means:

- Audit trail is per-employee (who sold what)
- Cash drawer responsibility is per-employee (who put cash in/out)
- Manager actions (refunds, discounts) require manager-role employee login

The session user acts as a system service account. If the session user has elevated permissions (e.g., can process refunds), those permissions apply to all employees logged in to that session unless the frontend restricts them.

### Performance Considerations

#### POS data load: employee list

`_load_pos_data_domain()` on `hr.employee` applies the three-tier filter before loading. If no restrict lists are set (`basic_employee_ids` empty), all employees in the company are loaded. For large organizations (1000+ employees), this can increase session initialization time. Mitigation: always set at least one restrict list.

#### Per-order field computation: `_compute_cashier`

`pos.order.cashier` is a stored computed field. Its compute is trivial (string assignment). There is no N+1 risk here because `employee_id` is set on the same record.

#### Per-payment `employee_id` inheritance

`pos.payment.employee_id` is `related='pos_order_id.employee_id'` with `store=True`. When a payment is created from an order, the ORM automatically stores the `employee_id` without requiring an explicit write. This is efficient.

#### SQL queries during session close

`get_closing_control_data()` aggregates payments and moves by employee using Python-side `.grouped()` on ORM recordsets:

```python
all_payments.grouped('employee_id')   # Python dict, not SQL GROUP BY
```

This loads all payment records into Python memory and groups them in-process. For sessions with thousands of payments, this can be memory-intensive. However, at POS scale (a session typically handles dozens to hundreds of transactions), this is acceptable.

**N+1 risk in `_aggregate_moves_by_employee()`:** The method uses `sudo()` to browse `statement_line_ids` and then accesses `.partner_id` on each employee without prefetching. The `partner_id` access for each employee may trigger individual queries. This is a minor N+1 pattern that only fires at session close time.

#### `get_barcodes_and_pin_hashed()` — double search

The method first searches with record-rule filtering (`visible_emp_ids = self.search(...)`), then searches again under `sudo()` with the filtered IDs. This is two queries instead of one. For configurations with few employees, this is negligible.

---

## `single_employee_sales_report` — Per-Employee Report

> **File:** `models/single_employee_sales_report.py`
> **Inherits:** `report.point_of_sale.report_saledetails`

Extends the standard POS sales detail report to support per-employee filtering.

| Method | Role |
|---|---|
| `_get_domain(date_start, date_stop, config_ids, session_ids, employee_id)` | Adds `('employee_id', '=', employee_id)` to the parent domain when `employee_id` is provided. |
| `_prepare_get_sale_details_args_kwargs(data)` | Injects `employee_id` from report data into `kwargs`. |
| `get_sale_details(date_start, date_stop, config_ids, session_ids, employee_id)` | Calls parent, then injects `employee_name` from the resolved `hr.employee` record. |

This report is invoked from the POS HR dashboard wizard with `employee_id` filter, producing a standard sales detail report scoped to a single employee's transactions.

---

## Design Patterns Summary

| Pattern | Location | Purpose |
|---|---|---|
| **Delegated attribution** | `pos.order.employee_id`, `pos.payment.employee_id`, `account.bank.statement.line.employee_id` | All POS financial activity attributed to the specific cashier |
| **Dynamic role resolution** | `hr_employee._load_pos_data_read()` | Roles checked at load time: group membership first, then config lists |
| **Manager auto-sync** | `pos_config.write()` | `advanced_employee_ids` always repopulated from `group_pos_manager` |
| **SHA1 credential hashing** | `hr_employee.get_barcodes_and_pin_hashed()` | Raw credentials never transmitted; frontend + backend both hash |
| **Mutual exclusion onchanges** | `pos_config._onchange_*_employee_ids()` | Prevents one employee in multiple access tiers |
| **Work-contact author resolution** | `pos_session._get_message_author()` | Prefers employee's work contact partner over session user for message attribution |
| **sudo() scoped to corecords** | `pos_config.write()` | Elevated write only for employee ID fields, not for config settings |

---

## Related

- [Modules/point_of_sale](Modules/point_of_sale.md) — Base POS module
- [Modules/HR](Modules/hr.md) — Human Resources module
- [Modules/Stock](Modules/stock.md) — Warehouse (used by POS for product availability)
