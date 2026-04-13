---
Module: pos_hr
Version: Odoo 18
Type: Integration
Tags: #pos #hr #employees #cashier #shifts
Related: [Modules/PointOfSale](Modules/PointOfSale.md), [Modules/HR](Modules/hr.md)
---

# pos_hr — Point of Sale User Management

## Overview

**Category:** Hidden | **Auto-install:** `True`
**Depends:** `point_of_sale`, `hr`
**Summary:** Links the Point of Sale to the HR module, enabling employee-based login, cashier tracking, per-employee sales reports, and shift management.

`pos_hr` extends Odoo's POS to support **employee login** (not just Odoo user login). Employees can log into a POS terminal using a **barcode**, **PIN**, or both. Every POS operation — orders, payments, cash moves — is then attributed to the specific employee who performed it.

---

## Architecture

### Module Chain

```
hr.employee              (base — name, barcode, pin, user_id)
        ↑
        │  _inherit
        │
pos_hr                    (barcode+pin loading, POS role, deletion guard)
        ↑
        │  (no model, just JS loading of hr.employee)
        │
point_of_sale.pos.config  (base POS config)
        ↑
        │  _inherit
        │
pos_hr                    (basic_employee_ids, advanced_employee_ids, _employee_domain)
        ↑
        │
point_of_sale.pos.session (base session)
        ↑
        │  _inherit
        │
pos_hr                    (employee_id field, per-employee closing aggregates)
        ↑
        │
point_of_sale.pos.order   (base order)
        ↑
        │  _inherit
        │
pos_hr                    (employee_id, cashier compute)
        ↑
        │
point_of_sale.pos.payment (base payment)
        ↑
        │  _inherit
        │
pos_hr                    (employee_id related from order, cashier compute)
        ↑
        │
account.bank.statement.line (base)
        ↑
        │  _inherit
        │
pos_hr                    (employee_id on cash move lines)
```

---

## Models

### `pos.config` (EXTENDED by pos_hr)

> Base model: `point_of_sale.pos.config`.

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `basic_employee_ids` | `Many2many(hr.employee)` | Employees allowed to log in to this POS as **cashiers**. If empty, **all employees** can log in (subject to company check). Mutually exclusive with `advanced_employee_ids`. |
| `advanced_employee_ids` | `Many2many(hr.employee)` | Employees allowed to log in as **managers**. If empty, only Odoo users with `group_pos_manager` have manager rights. Always includes the POS manager group's employees via `write()`. |

#### Methods

**`write(vals)`**

> Overrides write to **auto-append** all employees linked to `group_pos_manager` users into `advanced_employee_ids`. This ensures POS managers are always in the advanced list:

```python
if 'advanced_employee_ids' not in vals:
    vals['advanced_employee_ids'] = []
vals['advanced_employee_ids'] += [(4, emp_id) for emp_id in self._get_group_pos_manager().users.employee_id.ids]
return super().write(vals)
```

**`_onchange_basic_employee_ids()`**

> Onchange handler. When an employee is added to `basic_employee_ids`, they are automatically removed from `advanced_employee_ids`. Exception: if the employee is a POS manager (via `user_id._has_group('point_of_sale.group_pos_manager')`), they are only removed from `basic`.

**`_onchange_advanced_employee_ids()`**

> Onchange handler. When an employee is added to `advanced_employee_ids`, they are automatically removed from `basic_employee_ids`. Enforces mutual exclusivity at the UI level.

**`_employee_domain(user_id)`**

> Builds the domain filter for which employees can log in to this POS config. Returns:
- Company-matched employees (all configs must match the company)
- If `basic_employee_ids` is non-empty: only employees in `basic + advanced` lists OR Odoo users
- If `basic_employee_ids` is empty: all employees in the company can log in

```python
domain = self._check_company_domain(self.company_id)
if len(self.basic_employee_ids) > 0:
    domain = AND([
        domain,
        ['|', ('user_id', '=', user_id), ('id', 'in', self.basic_employee_ids.ids + self.advanced_employee_ids.ids)]
    ])
```

---

### `hr.employee` (EXTENDED by pos_hr)

> Base model: `hr.hr_employee_base_user` (or `hr.employee`).

#### Methods

**`_load_pos_data_domain(data)`** (`@api.model`)

> Returns the domain used to filter which employees are loaded into the POS front-end. Calls `config_id._employee_domain(config_id.current_user_id.id)`. This ensures:
- Only employees matching the POS config's company are loaded
- Only employees in `basic_employee_ids`/`advanced_employee_ids` are loaded (if those lists are non-empty)

**`_load_pos_data_fields(config_id)`** (`@api.model`)

> Returns `['name', 'user_id', 'work_contact_id']` as the fields loaded for each employee into the POS. `work_contact_id` is included so the POS can potentially display the employee's contact photo.

**`_load_pos_data(data)`** (`@api.model`)

> Builds the employee dataset sent to the POS session. For each employee:

1. Determines role: `'manager'` if employee is in the POS config's manager group OR in `advanced_employee_ids`; otherwise `'cashier'`
2. Retrieves barcode and PIN via `get_barcodes_and_pin_hashed()`
3. Hashes both values with SHA-1 before sending to the front-end

```python
employee['_role'] = role           # 'manager' or 'cashier'
employee['_barcode'] = hashed_barcode
employee['_pin'] = hashed_pin
```

**`get_barcodes_and_pin_hashed()`**

> Returns a list of dicts with `id`, `barcode` (SHA-1 hashed), and `pin` (SHA-1 hashed) for each employee. Both fields are hashed before transmission — the plain PIN never leaves the server. Access gated by `group_pos_user`.

```python
e['barcode'] = hashlib.sha1(e['barcode'].encode('utf8')).hexdigest() if e['barcode'] else False
e['pin'] = hashlib.sha1(e['pin'].encode('utf8')).hexdigest() if e['pin'] else False
```

> **L4: Security note**: The PIN is stored in plain text in `hr.employee.pin` (no hashing at write time). This method hashes it on read before sending to POS. The front-end compares the user's entered PIN (hashed client-side) against this value.

**`_unlink_except_active_pos_session()`** (`@api.ondelete(at_uninstall=False)`)

> Prevents deleting an employee if they are associated with an active POS session. Guard logic:
- If `basic_employee_ids` AND `advanced_employee_ids` are both empty for a config → all employees could use it → block deletion of any employee that could be active
- If `basic_employee_ids` or `advanced_employee_ids` is non-empty → only specific employees are blocked

---

### `pos.session` (EXTENDED by pos_hr)

> Base model: `point_of_sale.pos.session`.

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `employee_id` | `Many2one(hr.employee)` | The employee **currently logged in** to this POS session. Tracked with `tracking=True` so changes are logged in the chatter. This is set when an employee logs in (via POS front-end action), not at session creation. |

#### Methods

**`_load_pos_data_models(config_id)`** (`@api.model`)

> Extends the POS data load to include `'hr.employee'` when `module_pos_hr=True`. Without this, the employee data would not be sent to the POS front-end.

**`set_opening_control(cashbox_value, notes)`**

> Extends base. Posts an "Opened register" message to the session chatter, attributing it to the logged-in employee via `_get_message_author()`.

**`post_close_register_message()`**

> Extends base. Posts a "Closed Register" message when closing. If no employee is logged in, falls back to `super()` (base behavior). Otherwise attributes the close to the employee.

**`_get_message_author()`**

> Returns the `res.partner` record of the logged-in employee. Uses `employee_id._get_related_partners()` to find the employee's linked partner. Falls back to `user_id.partner_id` if no related partners exist.

**`_aggregate_payments_amounts_by_employee(payments)`**

> Groups a recordset of `pos.payment` records by `employee_id` and sums the amounts. Returns a sorted list of `{id, name, amount}` dicts. "Others" (payments with no employee) is always last.

Used in `get_closing_control_data()` to show **cash amounts per employee** at session close.

**`_aggregate_moves_by_employee()`**

> Groups cash move lines (`account.bank.statement.line` records linked to this session) by `employee_id`. Returns sorted list of `{id, name, amount}` dicts sorted by descending amount.

**`get_closing_control_data()`** (extends base)

> Extends the base closing control data with per-employee breakdowns:
- `data['default_cash_details']['amount_per_employee']`: cash payments split by employee
- `data['default_cash_details']['moves_per_employee']`: cash moves split by employee
- Per non-cash payment method: `amount_per_employee` split

This allows the closing screen to show exactly how much cash each employee handled.

**`_prepare_account_bank_statement_line_vals(session, sign, amount, reason, extras)`**

> Extends base. If `extras` contains `employee_id`, that value is written onto the statement line. This means when a cashier performs a cash move (float entry, cash withdrawal), the statement line is attributed to them.

---

### `pos.order` (EXTENDED by pos_hr)

> Base model: `point_of_sale.pos.order`.

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `employee_id` | `Many2one(hr.employee)` | The employee who used the cash register to create this order. Set from the POS front-end at order creation time. |
| `cashier` | `Char` (computed + stored) | Display name of the cashier. Computed: `employee_id.name` if `employee_id` exists, else `user_id.name`. |

#### Methods

**`_compute_cashier()`**

> If `employee_id` is set, `cashier = employee_id.name`. Otherwise falls back to the Odoo user who created the order. Stored so it persists even if the employee is later deleted.

**`_post_chatter_message(body)`**

> Extends base chatter posting. Appends `"Cashier: {name}"` to every chatter message on the order. This ensures every order's discussion thread shows who created it, regardless of whether an employee or user was the author.

---

### `pos.payment` (EXTENDED by pos_hr)

> Base model: `point_of_sale.pos.payment`.

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `employee_id` | `Many2one(hr.employee)` | Related from `pos_order_id.employee_id`, stored and indexed. Links the payment to the same employee who created the order. |
| `cashier` | `Char` (computed) | Display name of the cashier. Mirrors the same logic as `pos.order.cashier`. |

---

### `account.bank.statement.line` (EXTENDED by pos_hr)

> Base model: `account.bank.statement.line`.

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `employee_id` | `Many2one(hr.employee)` | The employee who performed a cash move (float entry, cash withdrawal, payment). Set via `_prepare_account_bank_statement_line_vals` on the session. Used for audit trail and per-employee cash reporting. |

---

### `product.product` (EXTENDED by pos_hr)

> Base model: `product.product`.

#### Methods

**`_load_pos_data_fields(config_id)`** (`@api.model`)

> Adds `'all_product_tag_ids'` to the list of fields loaded for products into the POS. Ensures product tags are available in the POS front-end when `pos_hr` is installed.

---

## Reports

### `report.pos_hr.single_employee_sales_report`

> Abstract model. Inherits `report.point_of_sale.report_saledetails`.

Extends the base POS sales details report to filter by a specific employee.

**`_get_domain(date_start, date_stop, config_ids, session_ids, employee_id)`**

> If `employee_id` is provided, adds `('employee_id', '=', employee_id)` to the base domain.

**`_prepare_get_sale_details_args_kwargs(data)`**

> Passes `employee_id` from report data into `get_sale_details()` kwargs.

**`get_sale_details(date_start, date_stop, config_ids, session_ids, employee_id)`**

> Calls `super().get_sale_details(...)` then adds `employee_name` to the result dict if `employee_id` is provided.

---

### `report.pos_hr.multi_employee_sales_report`

> Abstract model. Wraps the single-employee report for multiple employees in one report run.

**`_get_report_values(docids, data)`**

> Simply passes through `session_ids`, `employee_ids`, `config_ids`, `date_start`, `date_stop` for the report rendering template to iterate over and call `single_employee_sales_report` for each employee.

---

## Wizard: `wizard.pos_daily_sales_reports`

> Defined in `wizard/pos_daily_sales_reports.xml` (no Python model file found — uses the standard `point_of_sale` wizard mechanism). The XML registers the wizard action and form, which allows printing single-employee or multi-employee sales reports.

---

## L4: Employee Identification at POS

### Login Flow

```
POS Terminal boots → Load session data
    → loads hr.employee records (filtered by config's _employee_domain)
    → each employee has _barcode, _pin, _role ('manager' or 'cashier')
    ↓
Employee selects themselves on login screen (or scans barcode)
    → enters PIN
    → PIN hashed client-side, sent to server
    → server compares with stored SHA-1 hash
    → if match: employee is logged in
    → pos.session.employee_id set to this employee
    ↓
All subsequent actions (orders, payments, cash moves) tagged with employee_id
```

### Barcode vs. PIN

- **Barcode**: Scanned to identify the employee (select their name). Can be used alone if no PIN is set.
- **PIN**: 4-digit (or configured length) code entered after selecting name. Adds security.
- **Both required** is configurable by leaving barcode empty or PIN empty per employee

### Manager vs. Cashier Role

| Action | Cashier | Manager |
|--------|---------|---------|
| Create/save orders | Yes | Yes |
| Apply discounts | Yes (configurable %) | Yes (configurable %) |
| Open cash box | Yes | Yes |
| Close session | No | Yes |
| Print X/Z reports | No | Yes |
| Refund orders | Yes | Yes |
| Custom price | No | Yes |

(Roles are enforced in the POS JavaScript front-end based on `_role` sent from `_load_pos_data`.)

### Per-Employee Closing Data

When a manager closes the POS session, the closing screen shows:

1. **Cash amounts per employee**: How much cash each employee collected
2. **Cash moves per employee**: Float entries and cash withdrawals each employee made
3. **"Others"** category: Payments/operations not attributed to any specific employee

This enables reconciliation and accountability — a manager can see exactly which cashier handled what amount of cash.

### SHA-1 PIN Hashing

The PIN is stored in plain text in `hr.employee.pin`. When sent to the POS, it is hashed server-side with SHA-1:

```python
hashlib.sha1(plain_pin.encode('utf8')).hexdigest()
```

The POS JavaScript also hashes the user-entered PIN before comparing. This prevents the plain PIN from appearing in server logs or network traffic. It is **not** a proper password hashing scheme (no salt, no iterations) — it is obfuscation only.

---

## Key Design Notes

- **`auto_install=True`**: Automatically installs when both `point_of_sale` and `hr` are installed. This makes HR-aware POS available without explicit installation.
- **Employee ≠ Odoo User**: `hr.employee` records can exist without corresponding `res.users`. Non-user employees can still log into POS via barcode/PIN. This is the key value of `pos_hr` — staff who don't need full system access can still operate the POS.
- **`_employee_domain`**: The POS front-end only receives employees matching the domain. The domain includes company check and the config's `basic_employee_ids`/`advanced_employee_ids` restrictions. This prevents unauthorized employees from even seeing the POS.
- **Tracking `employee_id` on session**: The `tracking=True` on `pos.session.employee_id` creates a chatter entry whenever the logged-in employee changes — giving a full audit trail of who operated the terminal throughout the day.
- **`res.config.settings`**: The settings form mirrors `basic_employee_ids` and `advanced_employee_ids` from the POS config, with onchange logic to enforce mutual exclusivity (same as the config form).
- **Print report button**: The `web.assets_backend` asset includes `print_report_button/` — a backend button for printing employee-specific POS reports from the Odoo backend interface.
