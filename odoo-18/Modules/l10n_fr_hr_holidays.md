---
Module: l10n_fr_hr_holidays
Version: 18.0
Type: l10n/fr
Tags: #odoo18 #l10n #hr #holidays
---

# l10n_fr_hr_holidays

## Overview
French time-off (HR) localization for part-time workers. When an employee works fewer days than the company calendar (e.g., Mon-Wed employee in a Mon-Fri company), taking a holiday ending on a day the company works but the employee doesn't should count until the next company rest day. Adjusts both the leave `date_to` duration and the legal duration computation. Auto-installs with `hr_holidays`.

## Country
[France](odoo-18/Modules/account.md) 🇫🇷

## Dependencies
- hr_holidays

## Key Models

### ResCompany
`models/res_company.py` — extends `res.company`
- `l10n_fr_reference_leave_type` (Many2one `hr.leave.type`) — company reference leave type; must be set for French leave rules to apply
- `_get_fr_reference_leave_type()` — returns reference leave type; raises `ValidationError` if not configured

### ResConfigSettings
`models/res_config_settings.py` — extends `res.config.settings`
- `l10n_fr_reference_leave_type` — related field to company for settings UI

### HrLeave
`models/hr_leave.py` — extends `hr.leave`
- `l10n_fr_date_to_changed` (Boolean) — flag indicating whether date_to was extended by French rule logic

#### `_l10n_fr_leave_applies()`
Returns `True` only when ALL conditions met: single employee affected, company country = FR, employee's calendar differs from company's, leave type = company's reference leave type.

#### `_get_fr_date_from_to(date_from, date_to)`
Computes adjusted date_from and date_to for part-time employees. Logic:
1. If not half-day/hourly leave, adjusts using company's working schedule to find correct period boundaries
2. If half-day AM in 3-day week where afternoon is also worked: returns original (no push needed)
3. While start date is not a work day for employee: push forward
4. While next day after date_target is not a company work day: push date_target forward
Returns tuple of adjusted (date_from, date_to).

#### `_compute_date_from_to()`
`@api.depends` on date fields, employee. For French leave applies: computes adjusted dates and sets `l10n_fr_date_to_changed` flag.

#### `_get_durations()`
Override: for part-time employees, extends end date to next company work day, then counts legal days in company calendar vs actual hours in employee calendar. Returns (legal_days, hours) for each French leave.

## Data Files
- `data/l10n_fr_hr_holidays_demo.xml` — demo data for French HR scenario

## Chart of Accounts
Not applicable (HR module, no accounting).

## Tax Structure
Not applicable.

## Fiscal Positions
Not applicable.

## EDI/Fiscal Reporting
Not applicable.

## Installation
`auto_install: True` — auto-installed with hr_holidays. Requires `l10n_fr_reference_leave_type` to be set on company.

## Historical Notes

**Odoo 17 → 18 changes:**
- Version 1.0; French part-time leave extension has existed since earlier Odoo HR versions
- The `_get_durations` override with calendar comparison is the core algorithm — ensures correct leave balance deduction for part-time workers
- Company reference leave type is a required configuration gate (raises ValidationError if missing)
- Two-weeks calendar support added in recent versions for complex working schedules

**Performance Notes:**
- Calendar iteration is O(n) where n = days in leave period; acceptable for typical leave durations
- `_l10n_fr_leave_applies()` is a cheap check; early return avoids expensive computation