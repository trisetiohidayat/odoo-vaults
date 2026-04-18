---
type: module
module: hr_presence
tags: [odoo, odoo19, hr, attendance, presence]
uuid: 2a1b2c3d-4e5f-6a7b-8c9d-0e1f2a3b4c5d
created: 2026-04-06
---

# Employee Presence (hr_presence)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Employee Presence |
| **Technical** | `hr_presence` |
| **Category** | Human Resources/Attendance & Time Off |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Module** | `hr_presence` |

## Description

This module tracks employee presence and availability status in real-time, complementing the attendance check-in/check-out system. While `hr_attendance` records explicit clock-in/clock-out events, `hr_presence` passively monitors employee activity through multiple channels:

1. **IP-based detection**: Employees working from the office (within known IP ranges) are marked as "present"
2. **Email threshold**: Employees who send or receive emails above a threshold are marked as "present"
3. **Manual override**: Employees can manually set their own presence state
4. **Time-based fallback**: Employees expected to be working based on their schedule

The module runs a daily cron job (`hr.presence.check.presence`) that computes each employee's presence state and updates their status accordingly. The computed presence is used by other modules (e.g., Discuss, VoIP) to show real-time availability.

## Dependencies

```
hr
hr_attendance
```

- `hr`: Provides `hr.employee` model
- `hr_attendance`: Provides attendance records for time-based presence

## Module Structure

```
hr_presence/
├── models/
│   └── hr_employee.py          # Presence fields and methods
├── data/
│   └── hr_presence_data.xml    # Demo data: presence states
├── views/
│   └── hr_employee_views.xml   # Kanban view with presence indicator
└── __manifest__.py
```

## Data Flow

### Presence Computation (Cron)

```
CRON: hr.presence.check.presence (runs daily)
      │
      ▼
For each active employee:
      │
      ▼
_compute_presence_state()
  1. Check IP-based detection:
     Is employee's IP in company's allowed IPs?
     ├──► Yes: presence = 'present'
     │
     ▼
  2. Check email threshold:
     Count emails sent/received today
     If count >= threshold (default: 10):
       └── presence = 'present'
     │
     ▼
  3. Check manual override:
     Has employee set manual presence?
     ├──► Yes: use that state (may differ from computed)
     │
     ▼
  4. Check attendance (time-based):
     Is employee currently checked in?
     If attendance record exists and not checked out:
       └── presence = 'present'
     │
     ▼
  5. Check time-based:
     Is current time within employee's working hours?
     ├──► Yes: presence = 'to_define'
     │
     ▼
  6. Fallback:
     └── presence = 'absent'
```

### Manual Presence Override

```
Employee sets presence manually (action_set_presence)
      │
      ▼
_action_set_manual_presence(new_state)
  - Sets employee.manual_presence = True
  - Sets employee.presence_state = new_state
  - Sets employee.manual_presence_date = today
      │
      ▼
Override expires after N days (configurable)
      │
      ▼
Next cron run checks if override is still valid
  If expired: reset manual_presence = False
```

### Presence State Changes

```
Employee state changes to 'absent'
      │
      ▼
_check_absence_conditions()
  - Employee has been absent for N consecutive days
  - Send notification to manager (if configured)
  - Optionally send SMS to employee
      │
      ▼
HR can click "Open Leave Request" from employee form
      │
      ▼
Creates a draft leave request for the employee
```

## Key Models

### hr.employee (Inherited)

**File:** `models/hr_employee.py`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `presence_state` | Selection | Computed presence state |
| `manual_presence` | Boolean | Whether employee manually set their presence |
| `manual_presence_date` | Date | When manual presence was last set |
| `email_sent` | Integer | Number of emails sent today |
| `email_received` | Integer | Number of emails received today |
| `last_activity` | Datetime | Last known activity time |

**Presence States:**

| State | Meaning |
|-------|---------|
| `present` | Employee is active and available |
| `absent` | Employee is not working / not available |
| `to_define` | Presence cannot be determined (needs review) |

#### Key Methods

##### `_check_presence()`

The cron method that computes presence state for all employees. This is the main entry point for automated presence detection.

```python
def _check_presence(self):
    """
    Cron job: Compute presence state for all active employees.
    Runs daily via ir.cron.
    
    This method orchestrates all presence detection methods
    and updates each employee's presence_state.
    """
    employees = self.search([('active', '=', True)])
    
    for employee in employees:
        previous_state = employee.presence_state
        
        # Step 1: Check if manual override is still valid
        if employee.manual_presence:
            override_validity_days = employee.company_id.presence_control_presence_state_delay or 7
            days_since_override = (
                fields.Date.today() - employee.manual_presence_date
            ).days
            
            if days_since_override > override_validity_days:
                # Override expired — recompute
                employee.write({
                    'manual_presence': False,
                    'manual_presence_date': False,
                })
            else:
                # Keep manual override
                continue  # Skip automated computation
        
        # Step 2: Compute presence state
        new_state = employee._compute_presence_state()
        
        # Step 3: Write new state if changed
        if new_state != previous_state:
            employee.write({'presence_state': new_state})
            
            # Step 4: Check if new state is 'absent' (trigger notifications)
            if new_state == 'absent':
                employee._check_absence_conditions()
        
        _logger.debug(
            "Presence check: %s was '%s', now '%s'",
            employee.name, previous_state, new_state
        )
```

##### `_compute_presence_state()`

Determines the presence state using all available detection methods. Returns the most relevant presence indicator.

```python
def _compute_presence_state(self):
    """
    Compute presence state using multiple detection methods.
    Returns 'present', 'absent', or 'to_define'.
    """
    self.ensure_one()
    company = self.company_id
    
    # Priority 1: IP-based detection
    if company.presence_control_ip_allowlist:
        employee_ip = self.env['res.users'].sudo().browse(
            self.user_id.id
        ).mapped('login_datas.presence_control_ip_allowlist')
        
        if self._is_in_office_ip(employee_ip):
            return 'present'
    
    # Priority 2: Email-based detection
    if company.presence_control_email_amount:
        email_threshold = company.presence_control_email_amount
        total_emails = self.email_sent + self.email_received
        
        if total_emails >= email_threshold:
            self.last_activity = fields.Datetime.now()
            return 'present'
    
    # Priority 3: Manual override (checked in cron)
    # Already handled before this method is called
    
    # Priority 4: Attendance-based (check if currently checked in)
    attendance = self.env['hr.attendance'].search([
        ('employee_id', '=', self.id),
        ('check_in', '<=', fields.Datetime.now()),
    ], order='check_in desc', limit=1)
    
    if attendance:
        if not attendance.check_out:
            # Currently checked in
            self.last_activity = fields.Datetime.now()
            return 'present'
        else:
            # Checked out earlier today
            self.last_activity = attendance.check_out
            return 'present'
    
    # Priority 5: Time-based (within working hours)
    if self._is_working_hours():
        return 'to_define'
    
    # Fallback: Absent
    return 'absent'
```

**Detection Method Priority:**
1. IP address match → `present`
2. Email threshold met → `present`
3. Manually set → (used before calling this method)
4. Currently checked in → `present`
5. Within working hours → `to_define`
6. Outside working hours → `absent`

##### `_is_in_office_ip()`

Checks if the employee is connecting from an office IP address.

```python
def _is_in_office_ip(self, employee_ip=None):
    """
    Check if the employee is connecting from a known office IP.
    
    IP allowlist is configured on the company:
      company.presence_control_ip_allowlist = '192.168.1.0/24, 10.0.0.0/8'
    """
    if not employee_ip:
        # Get IP from current user's HTTP request
        employee_ip = request.httprequest.remote_addr
    
    company = self.company_id
    allowed_ips = company.presence_control_ip_allowlist or ''
    
    if not allowed_ips:
        return False
    
    # Parse comma-separated IP ranges
    allowed_ranges = allowed_ips.split(',')
    employee_ip_obj = ipaddress.ip_address(employee_ip)
    
    for ip_range in allowed_ranges:
        ip_range = ip_range.strip()
        if '/' in ip_range:
            # CIDR notation: 192.168.1.0/24
            if employee_ip_obj in ipaddress.ip_network(ip_range):
                return True
        else:
            # Exact match
            if str(employee_ip_obj) == ip_range:
                return True
    
    return False
```

##### `_is_working_hours()`

Determines if the current time falls within the employee's scheduled working hours.

```python
def _is_working_hours(self):
    """
    Check if current time is within employee's working schedule.
    Uses the resource.calendar to determine working hours.
    """
    today = fields.Date.context_today(self)
    resource = self.resource_id
    
    if not resource.calendar_id:
        # No schedule defined — assume standard working hours
        return True
    
    # Get working hours for today
    work_hours = self.env['resource.calendar'].get_working_hours(
        resource=resource,
        start_datetime=fields.Datetime.to_datetime(today),
        end_datetime=fields.Datetime.to_datetime(today) + timedelta(days=1),
    )
    
    if not work_hours:
        return False
    
    # Get current time
    current_time = fields.Datetime.now().time()
    
    # Check if current time is within any work interval
    for start, stop in work_hours:
        if start <= current_time <= stop:
            return True
    
    return False
```

##### `_action_set_manual_presence()`

Allows an employee to manually set their presence state.

```python
def _action_set_manual_presence(self, state):
    """
    Set presence state manually.
    
    Args:
        state: 'present', 'absent', or 'to_define'
    
    When manually set:
      - manual_presence = True
      - manual_presence_date = today
      - presence_state = state
    """
    self.ensure_one()
    
    if state not in ('present', 'absent', 'to_define'):
        raise ValidationError(_("Invalid presence state"))
    
    self.write({
        'presence_state': state,
        'manual_presence': True,
        'manual_presence_date': fields.Date.today(),
    })
    
    _logger.info(
        "Manual presence set for %s: %s",
        self.name, state
    )
    
    # Post a message in the employee chatter
    self.message_post(
        body=_("Presence manually set to: %s") % state,
        message_type='notification',
    )
```

##### `action_open_leave_request()`

Opens a leave request form for an absent employee, pre-filled with today's date.

```python
def action_open_leave_request(self):
    """
    Create a draft leave request for this employee,
    starting from today.
    
    Used by HR when they notice an employee is absent
    but hasn't submitted a leave request.
    """
    self.ensure_one()
    
    leave_type = self.env['hr.leave.type'].search([], limit=1)
    
    return {
        'name': _('New Leave Request'),
        'type': 'ir.actions.act_window',
        'res_model': 'hr.leave',
        'view_mode': 'form',
        'context': {
            'default_employee_id': self.id,
            'default_date_from': fields.Date.today(),
            'default_holiday_status_id': leave_type.id if leave_type else False,
        },
    }
```

##### `action_send_sms()`

Sends an SMS reminder to an absent employee.

```python
def action_send_sms(self):
    """
    Send an SMS to the employee reminding them to:
    1. Check in via attendance
    2. Or submit a leave request
    
    Requires SMS module (sms) to be installed.
    """
    self.ensure_one()
    
    if not self.mobile_phone:
        raise UserError(_("No mobile phone number for employee %s") % self.name)
    
    # Compose SMS message
    message = _(
        "You haven't checked in today. "
        "Please submit a leave request or contact your manager."
    )
    
    # Send SMS
    try:
        self.env['sms.api']._send_sms(
            numbers=[self.mobile_phone],
            message=message,
        )
        
        # Log in chatter
        self.message_post(
            body=_("SMS reminder sent: %s") % message,
            message_type='notification',
        )
        
        _logger.info(
            "SMS reminder sent to %s (%s)",
            self.name, self.mobile_phone
        )
    except Exception as e:
        _logger.error("Failed to send SMS to %s: %s", self.name, str(e))
        raise UserError(_("Failed to send SMS: %s") % str(e))
```

##### `action_send_log()`

Logs a presence note for the employee (e.g., "visited client", "working remotely").

```python
def action_send_log(self):
    """
    Add a presence log entry for this employee.
    Used to track non-standard work situations.
    
    Examples:
      - "Working from home"
      - "Client visit"
      - "Business trip"
    """
    self.ensure_one()
    
    return {
        'name': _('Add Presence Log'),
        'type': 'ir.actions.act_window',
        'res_model': 'hr.employee.presence.log',
        'view_mode': 'form',
        'context': {
            'default_employee_id': self.id,
            'default_date': fields.Date.today(),
        },
        'target': 'new',
    }
```

## Presence Detection Methods

### 1. IP-Based Detection

**How it works:** The company configures a list of IP ranges (CIDR notation). If an employee's IP address falls within these ranges, they are marked as "present".

**Configuration:**
```
company.presence_control_ip_allowlist = '192.168.1.0/24, 10.0.0.0/8, 172.16.0.0/12'
```

**Use case:** Employees working from the office will have office IPs. Employees working remotely will have non-office IPs and won't be marked present via IP.

### 2. Email Threshold Detection

**How it works:** The system counts emails sent and received by the employee. If the total exceeds a threshold, they are marked as "present".

**Configuration:**
```
company.presence_control_email_amount = 10
```

**How emails are counted:** This requires the `fetchmail` module or a similar email integration that tracks mail per user. Without such integration, email counts won't update.

**Use case:** Actively working employees typically send/receive many emails. This is a proxy for "being active" even outside office hours.

### 3. Manual Override

**How it works:** Employees can manually set their presence state. This overrides automated detection.

**Limitations:** The manual override expires after a configurable number of days (default: 7 days). After expiry, automated detection resumes.

**Use case:** Employee working from an unusual location (client site, home) that doesn't match office IPs or email thresholds.

### 4. Attendance-Based Detection

**How it works:** If the employee has a currently open attendance record (checked in, not checked out), they are marked as "present".

**Priority:** Attendance detection runs after IP and email detection. If either IP or email marks the employee present, attendance isn't consulted.

**Use case:** Captures employees who explicitly clock in/out via the attendance module.

### 5. Time-Based Detection

**How it works:** If the current time falls within the employee's scheduled working hours (based on their resource calendar), the presence is set to "to_define" (needs review).

**"to_define" meaning:** The employee is expected to be working (it's within their schedule), but we haven't detected any active presence signals. HR or the manager should follow up.

**Use case:** Provides a "catch-all" that flags employees who should be working but haven't shown any activity.

### 6. Fallback: Absent

If none of the above conditions are met, the employee is marked as "absent".

## Cron Configuration

```python
# Cron: hr.presence.check.presence
# Model: hr.employee
# Method: _check_presence
# Schedule: Daily at midnight (or configurable)
# Active: True (by default)
```

The cron can be configured in **Settings > Technical > Scheduled Actions**.

## Architecture Notes

### Presence vs. Attendance

| Aspect | Attendance | Presence |
|--------|-----------|----------|
| **Trigger** | Explicit check-in/check-out | Passive detection |
| **Granularity** | Binary (checked in or not) | Multiple states |
| **Data source** | User action | IP, email, calendar, manual |
| **Real-time** | Yes (event-based) | Yes (cron updates) |
| **Override** | Not allowed | Manual override available |
| **Use case** | Payroll, legal compliance | Real-time availability |

### Integration with Discuss/VoIP

The `presence_state` field is used by Odoo's real-time communication tools:
- Green/yellow/red indicator in the employee Kanban
- Available/Away/Offline status in Discuss
- VoIP call routing based on availability

Other modules query `presence_state` to determine if an employee can take calls or should be considered available.

### Stale Presence Detection

If `last_activity` is older than a threshold, the presence may be stale:
```python
if self.last_activity:
    hours_since_activity = (
        fields.Datetime.now() - self.last_activity
    ).total_seconds() / 3600
    
    if hours_since_activity > 8:  # 8 hours of inactivity
        # Consider changing to 'absent' or 'to_define'
```

## Configuration

### Company Settings

| Setting | Field | Description |
|---------|-------|-------------|
| IP Allowlist | `presence_control_ip_allowlist` | Comma-separated IP addresses/CIDR |
| Email Threshold | `presence_control_email_amount` | Min emails to mark present |
| Override Validity | `presence_control_presence_state_delay` | Days before manual override expires |

Access: **Settings > Users > Companies > Presence Control**

### Employee Settings

| Setting | Field | Description |
|---------|-------|-------------|
| Manual Presence | `manual_presence` | Whether manually set |
| Manual Presence Date | `manual_presence_date` | When manually set |

### Setting Up Email Tracking

Email counting requires additional configuration:
1. Install `fetchmail` module
2. Configure incoming mail servers with user mapping
3. The system will track emails per user via `mail.message`

## Security Analysis

### Access Control

| Action | Who Can Do It |
|--------|--------------|
| View presence state | All employees (own), HR/Manager (all) |
| Set manual presence | Employee (own), HR/Manager (all) |
| Send SMS reminder | HR Officer, HR Manager |
| Create leave from absence | HR Officer, HR Manager |
| Modify company presence settings | System Administrator |

### Privacy Considerations

- Presence data may be considered personal data under GDPR
- Employees should be informed that their presence is being tracked
- Manual override exists specifically to give employees control
- Presence data should not be used for performance evaluation without clear policies

### Audit Trail

- Manual presence changes are logged in the employee chatter
- SMS reminders are logged in the employee chatter
- Cron execution is logged in `ir.cron` logs

## Related

- [Modules/hr_attendance](hr_attendance.md) — Attendance check-in/check-out
- [Modules/hr](hr.md) — Employee management
- [Modules/hr_holidays](hr_holidays.md) — Leave requests
