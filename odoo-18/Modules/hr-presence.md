---
Module: hr_presence
Version: Odoo 18
Type: Integration
Tags: #odoo #odoo18 #hr #presence #attendance #ip-detection #email-tracking
Related Modules: [Modules/HR](Modules/HR.md), [hr_holidays](modules/hr-holidays.md), [hr_work_entry](modules/hr-work-entry.md)
---

# Employee Presence (`hr_presence`)

## Overview

`hr_presence` tracks whether employees are present at work based on three detection signals: IP address (VPN/office network), email activity (sending emails through Odoo), and manual HR actions. It extends `hr.employee.base` with presence fields and provides automated HR actions (SMS, logging, time-off requests) for employees detected as absent without justification.

**Depends:** `hr`, `hr_holidays`, `sms`
**Cron:** `ir_cron_presence_control` — runs every 1 hour
**Models:** 2 (both extended)

## Models

### `hr.employee.base` — Presence Mixin (EXTENDED)

Abstract model extended by `hr.employee`. Adds presence detection fields and automated actions.

**File:** `~/odoo/odoo18/odoo/addons/hr_presence/models/hr_employee.py`

#### Fields

| Field | Type | Description |
|---|---|---|
| `email_sent` | Boolean (default False) | Set to True if the employee sent >= `hr_presence_control_email_amount` emails today. Reset each cron run. |
| `ip_connected` | Boolean (default False) | Set to True if the employee's user logged in from an IP in `hr_presence_control_ip_list` today. Reset each cron run. |
| `manually_set_present` | Boolean (default False) | Manager manually marked the employee as present today. Reset each cron run. |
| `manually_set_presence` | Boolean (default False) | Manager manually set presence (present or absent). When True, overrides automatic detection. |
| `hr_presence_state_display` | Selection | Stored copy of `hr_presence_state` used in kanban grouping. Values: `out_of_working_hour` / `present` / `absent`. Default `out_of_working_hour`. |

#### `hr.employee.base` Base Fields (Inherited)

The following are defined in the core `hr` module's `hr.employee.base` and overridden by this module:

| Field | Type | Description |
|---|---|---|
| `hr_presence_state` | Selection | Computed presence state: `present` / `absent` / `archive` / `out_of_working_hour`. Default `out_of_working_hour`. Computed via `_compute_presence_state`. |
| `hr_icon_display` | Selection | `'presence_present'` / `'presence_out_of_working_hour'` / `'presence_absent'` / `'presence_archive'` / `'presence_undetermined'`. |
| `last_activity` | Date | Related from `user_id.last_activity`. |
| `last_activity_time` | Char | Related from `user_id.last_activity`. |

#### Key Methods

- **`_check_presence()`** — `@api.model` cron job entry point. Runs every hour via `ir_cron_presence_control`.

  Resets all presence flags at the start of each run, then re-detects:

  **Step 1: Reset**
  ```python
  employees.write({
      'email_sent': False,
      'ip_connected': False,
      'manually_set_present': False,
      'manually_set_presence': False,
  })
  ```

  **Step 2: IP Detection** (`company.hr_presence_control_ip`)
  ```python
  ip_list = company.hr_presence_control_ip_list.split(',')  # comma-separated IPs
  for employee in employees:
      employee_ips = res_users_log.sudo().search([
          ('create_uid', '=', employee.user_id.id),
          ('ip', '!=', False),
          ('create_date', '>=', today 00:00:00)
      ]).mapped('ip')
      if any(ip in ip_list for ip in employee_ips):
          ip_employees |= employee
  ip_employees.write({'ip_connected': True})
  ```

  **Step 3: Email Detection** (`company.hr_presence_control_email`)
  ```python
  threshold = company.hr_presence_control_email_amount  # minimum emails
  for employee in employees:
      sent_emails = mail.message.search_count([
          ('author_id', '=', employee.user_id.partner_id.id),
          ('date', '>=', today 00:00:00),
          ('date', '<=', now)
      ])
      if sent_emails >= threshold:
          email_employees |= employee
  email_employees.write({'email_sent': True})
  ```

  **Step 4: Write computed `hr_presence_state_display`**
  ```python
  for employee in all_employees:
      employee.hr_presence_state_display = employee.hr_presence_state
  ```

- **`_compute_presence_state()`** — Overrides core `hr.employee.base` computation. **Runs after the base computation** (`super()._compute_presence_state()`).

  Logic flow:
  ```
  if manually_set_presence:
      hr_presence_state = hr_presence_state_display  # manager override
  elif company.hr_presence_control_email OR company.hr_presence_control_ip:
      if working_now AND (email_sent OR ip_connected OR manually_set_present):
          hr_presence_state = 'present'
      elif working_now AND is_absent AND NOT (email_sent OR ip_connected OR manually_set_present):
          hr_presence_state = 'absent'
      else:
          hr_presence_state = 'out_of_working_hour'
  ```

  Uses `_get_employee_working_now()` from the base module to determine if the current time falls within the employee's working hours.

- **`get_presence_server_action_data()`** — Returns available server actions for the presence panel:
  - `action_hr_employee_presence_present`
  - `action_hr_employee_presence_absent`
  - `action_hr_employee_presence_log`
  - `action_hr_employee_presence_sms`
  - `action_hr_employee_presence_time_off`

- **`_action_set_manual_presence(state)`** — Manager sets presence manually.
  ```python
  def _action_set_manual_presence(self, state):
      # Requires hr.group_hr_manager
      self.write({
          'manually_set_present': state,
          'manually_set_presence': True,
          'hr_presence_state_display': 'present' if state else 'absent',
      })
  ```
  Called by `action_set_present()` (state=True) and `action_set_absent()` (state=False).

- **`action_set_present()`** — Smart button to mark employee present. Calls `_action_set_manual_presence(True)`.

- **`action_set_absent()`** — Smart button to mark employee absent. Calls `_action_set_manual_presence(False)`.

- **`action_open_leave_request()`** — Opens leave request form.
  - Single employee: opens `hr.leave` form with `default_employee_id`
  - Multiple employees: opens multi-generation wizard (`hr.leave.generate.multi.wizard`) with defaults pre-filled.

- **`action_send_sms()`** — Sends SMS to absent employees.
  - Requires `hr.group_hr_manager`
  - Uses `sms.composer` with default body or a template (`hr_presence.sms_template_presence`)
  - Default message: notification that the employee is not present and has no recorded time off

- **`action_send_log()`** — Posts a message on the employee's record noting their presence state.
  ```python
  employee.message_post(body=_("%(name)s has been noted as %(state)s today", ...))
  ```

---

## Presence Detection Architecture

### Three Detection Signals

| Signal | Source | Config Field | Threshold |
|---|---|---|---|
| **IP-based** | `res.users.log.ip` — last IP of user's login session today | `hr_presence_control_ip` + `hr_presence_control_ip_list` | Any matching IP |
| **Email-based** | `mail.message` — emails sent today via Odoo | `hr_presence_control_email` + `hr_presence_control_email_amount` | Configurable minimum count |
| **Manual** | HR Manager action via smart button | None | N/A |

### Company-Level Configuration

These settings are on `res.company`:

- `hr_presence_control_email` — Boolean, enable email tracking
- `hr_presence_control_email_amount` — Integer, minimum emails to consider present (default: 1)
- `hr_presence_control_ip` — Boolean, enable IP tracking
- `hr_presence_control_ip_list` — String, comma-separated IP addresses (e.g., office VPN IPs)
- `hr_presence_last_compute_date` — Datetime, set by `_check_presence()` to avoid redundant recomputation within the same day

### Presence State Machine

```
                (manually_set_presence = True)
                ┌──────────────────────────────────┐
                │                                  │
         ┌──────▼──────────┐              ┌───────▼──────────┐
         │   out_of_working_hour              present          │
         │                                     (manual)        │
         └──────┬──────────┘              └───────┬──────────┘
                │                                   │
        ┌───────┴────────────────────────────┐    │
        │         working_hours = True         │    │
        │  ┌────────────────────────────┐     │    │
        │  │ email_sent OR ip_connected  │     │    │
        │  │ OR manually_set_present     │     │    │
        │  └──────────────┬─────────────┘     │    │
        │                 │                   │    │
        │    ┌────────────▼───────┐          │    │
        │    │      present       │          │    │
        │    │   (automated)      │          │    │
        │    └────────────┬───────┘          │    │
        │                 │                   │    │
        │    ┌────────────▼───────┐          │    │
        │    │      absent        │          │    │
        │    │  (is_absent AND    │          │    │
        │    │  no signal)        │          │    │
        │    └────────────────────┘          │    │
        └────────────────────────────────────┘    │
                                                   │
                               (after midnight reset → out_of_working_hour)
```

---

## L4: How Presence Detection Works

### Cron Execution Flow

```
ir_cron_presence_control (every 1 hour, as base.user_root)
  └── hr.employee._check_presence()
        ├── Reset all flags (email_sent, ip_connected, manually_set_present, manually_set_presence)
        ├── IP check (if company.hr_presence_control_ip)
        │     └─ res.users.log: auth data from user sessions
        ├── Email check (if company.hr_presence_control_email)
        │     └─ mail.message: Odoo internal emails only (not external SMTP)
        ├── Update hr_presence_last_compute_date
        └── Sync hr_presence_state_display = hr_presence_state
```

### Important Constraints

1. **Email tracking only covers Odoo-sent emails** — Does NOT track emails sent via external email clients (IMAP/SMTP). Uses `mail.message` table which only contains messages sent through Odoo's messaging system.

2. **IP tracking only covers Odoo session logins** — Uses `res.users.log` which captures the IP address of users when they log into Odoo. Does NOT track device presence on the corporate network.

3. **Both signals require the user to be active in Odoo** — Passive presence at the office (not using Odoo) is not detected.

4. **Manually_set_presence overrides everything** — Once an HR manager sets presence manually, the automatic detection is bypassed until the next cron reset at midnight.

5. **`hr_presence_state_display` is the stored copy** — Used in views that group/filter by state. The actual `hr_presence_state` is a transient computed value; `hr_presence_state_display` is the persisted snapshot.

### Extension Pattern

`hr_presence` extends `hr.employee.base` (abstract). `hr.employee` inherits `hr.employee.base` and `hr.employee.public` also inherits it. This means presence fields are available on:
- `hr.employee` (full record, requires HR access)
- `hr.employee.public` (simplified record, broader access)

### Relation to Attendance and Time Off

- Employees detected as `absent` can have a time-off request created via `action_open_leave_request()`
- Absent employees without a leave request can receive an SMS notification via `action_send_sms()`
- The presence state affects the employee's `hr_icon_display` shown across the Odoo interface

### Smart Button Actions

| Action | Who Can Do It | Effect |
|---|---|---|
| Set Present | HR Manager | Sets `manually_set_present=True`, `manually_set_presence=True` |
| Set Absent | HR Manager | Sets `manually_set_present=False`, `manually_set_presence=True` |
| Send SMS | HR Manager | Opens SMS composer with absence notification template |
| Log | HR Manager | Posts a message on the employee record |
| Time Off | Anyone | Opens leave request form |