# HR Presence

## Overview
- **Name**: Employee Presence Control (`hr_presence`)
- **Category**: Human Resources
- **Depends**: `hr`, `hr_holidays`, `sms`
- **Version**: 1.0
- **License**: LGPL-3

Monitors employee presence via IP address, email activity, and manual settings. Sends SMS notifications for unjustified absences.

## Models

### `hr.employee` (extends)
| Field | Type | Description |
|-------|------|-------------|
| `email_sent` | Boolean | Employee sent emails today |
| `ip_connected` | Boolean | Employee IP in allowed list today |
| `manually_set_present` | Boolean | Manually marked present today |
| `manually_set_presence` | Boolean | Presence manually overridden |
| `hr_presence_state_display` | Selection | Stored state for kanban grouping (out_of_working_hour/present/absent) |

- `_check_presence`: Cron action that checks IP and email presence
- `_compute_presence_state`: Computes presence based on IP/email/manual flags
- `action_set_present`, `action_set_absent`: Manager can override presence
- `action_open_leave_request`: Open leave request form
- `action_send_sms`: Send SMS to employee about absence
- `action_send_log`: Post a message noting the presence state
- `get_presence_server_action_data`: Returns available server actions

### `hr.employee.public` (extends)
Mirrors the presence fields for public access.

### `res.company` (extends)
| Field | Type | Description |
|-------|------|-------------|
| `hr_presence_last_compute_date` | Datetime | When presence was last computed |

### `res.users.log` (extends)
| Field | Type | Description |
|-------|------|-------------|
| `ip` | Char | IP address of login |

### `ir.websocket` (extends)
- `_update_mail_presence`: Records IP address for authenticated internal users on each request

### `res.config.settings` (extends)
- `create`: Triggers `_check_presence` when IP or email presence control is enabled

## Key Features
- IP-based presence detection (configurable whitelist)
- Email-sent threshold presence detection
- Manual presence override by managers
- SMS notifications to absent employees
- Presence state kanban view
- Cron-based daily computation

## Related
- [Modules/HR](odoo-18/Modules/hr.md) - Core HR module
- [Modules/hr_holidays](odoo-18/Modules/hr_holidays.md) - Leave tracking
- [Modules/sms](odoo-18/Modules/sms.md) - SMS sending
