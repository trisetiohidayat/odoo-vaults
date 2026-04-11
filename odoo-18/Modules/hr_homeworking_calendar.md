---
Module: hr_homeworking_calendar
Version: 18.0.0
Type: addon
Tags: #odoo18 #hr_homeworking_calendar
---

## Overview
Remote Work with Calendar. Bridge between `hr_homeworking` and `calendar` that makes work location exceptions (e.g., "working from home on Tuesday") visible in the calendar view. Extends `res.partner` with a worklocation RPC method and `hr.employee.base` with a `_get_worklocation` helper. Also provides a `homework.location.wizard` for setting work locations per day.

## Models

### res.partner (Extension)
Inherits from: `res.partner`
File: `~/odoo/odoo18/odoo/addons/hr_homeworking_calendar/models/res_partner.py`

**Methods:**
| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| get_worklocation | start_date, end_date | dict | Searches employee by `work_contact_id` matching self, then delegates to `employee._get_worklocation(start_date, end_date)` |

### hr.employee.base (Extension)
Inherits from: `hr.employee.base`
File: `~/odoo/odoo18/odoo/addons/hr_homeworking_calendar/models/hr_employee.py`

**Methods:**
| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _get_worklocation | start_date, end_date | defaultdict | Returns per-employee dict with: `user_id`, `employee_id`, `partner_id`, `employee_name`, and per-day location (mon-sun) from employee fields. Also includes `exceptions` dict: `{date_str: {location details}}` from `hr.employee.location` records in the date range |

**`_get_worklocation` Output Structure:**
```python
{
  employee_id: {
    'user_id': int,
    'employee_id': int,
    'partner_id': int,
    'employee_name': str,
    'monday': {'location_type': str, 'location_name': str, 'work_location_id': int},
    'tuesday': {...},
    ...
    'sunday': {...},
    'exceptions': {
      '2026-04-15': {'hr_employee_location_id': int, 'location_type': str, ...}
    }
  }
}
```

### homework.location.wizard (Transient)
Inherits from: `base.TransientModel`
File: `~/odoo/odoo18/odoo/addons/hr_homeworking_calendar/wizard/homework_location_wizard.py`

| Field | Type | Description |
|-------|------|-------------|
| work_location_id | Many2one(hr.work.location) | Required |
| work_location_name | Char | Related |
| work_location_type | Selection | Related |
| employee_id | Many2one(hr.employee) | Default=`env.user.employee_id`; required |
| employee_name | Char | Related |
| user_can_edit | Boolean | `compute='_compute_user_can_edit'` |
| weekly | Boolean | Default=False; if True, applies to all future occurrences |
| date | Date | Target date; optional |
| day_week_string | Char | `compute`: `date.strftime('%A')` |

**Methods:**
| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| set_employee_location | self | bool | If `weekly=True`: deletes exceptions and updates the user's default weekly location. If specific date: creates/updates `hr.employee.location` record for that date; deletes exception if it matches the new location |

## Security
File: `security/security.xml`
- `homework.location.wizard` own rule: users can only see/edit their own wizard
- `homework.location.wizard` admin rule: HR officers can see/edit all

## Critical Notes
- **`DAYS` import:** References `DAYS` from `hr_homeworking.models.hr_homeworking` — a list constant of weekday field names (`['monday', 'tuesday', ...]`)
- **Exception date format:** Uses `DEFAULT_SERVER_DATE_FORMAT` ('%Y-%m-%d') for exception keys — matches JS date formatting
- **`user_can_edit`:** Related to `self.env.user.can_edit` — controlled by `hr_homeworking` module's `can_edit` field on `res.users`
- **Wizard `weekly` flag:** If True, removes exception and sets the weekly default (mon-sun) location for the user
- **Location comparison:** If the selected location matches the weekly default, the exception record is deleted (not created)
- **v17→v18:** New module in v18; `hr_homeworking` was significantly revamped in v17→v18, and this calendar integration is new
