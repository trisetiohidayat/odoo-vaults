---
type: module
module: l10n_in_hr_holidays
tags: [odoo, odoo19, accounting, localization]
created: 2026-04-06
---

# India Accounting Localization (`l10n_in_hr_holidays`)

## Overview
| Property | Value |
|----------|-------|
| **Name** | The Indian Time Off module provides additional features to the application. With it, you'll be able to define Sandwich Leaves on your time off type, including weekends or holidays in the duration of t |
| **Technical** | `l10n_in_hr_holidays` |
| **Category** | Human Resources/Time Off |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
The Indian Time Off module provides additional features to the application. With it, you'll be able to define Sandwich Leaves on your time off type, including weekends or holidays in the duration of the employee leave's request.

## Dependencies
| Module | Purpose |
|--------|---------|
| `hr_holidays` | Dependency |

## Technical Notes
- Country code: `in` (India)
- Localization type: HR/Time Off (Indian leave management)
- Custom model files: hr_leave.py, hr_employee.py, l10n_in_hr_leave_optional_holiday.py, hr_leave_type.py

## Models

### `hr.leave` (Extended)
Extends leave with Indian-specific rules:
- Sandwich leave support: includes weekends/holidays in leave duration
- `l10n_in_count_public_holidays_in_leave_duration()` — Counts public holidays in leave period

### `hr.leave.type` (Extended)
Extends leave type with Indian-specific settings.

### `hr.employee` (Extended)
Employee-specific holiday configurations for India.

## Related
- [Modules/l10n_in](l10n_in.md) — Core Indian accounting
- [Modules/hr_holidays](hr_holidays.md) — Base leave management