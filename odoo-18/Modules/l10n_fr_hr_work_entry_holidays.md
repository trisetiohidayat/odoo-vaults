---
Module: l10n_fr_hr_work_entry_holidays
Version: 18.0
Type: l10n/fr
Tags: #odoo18 #l10n #hr #holidays
---

# l10n_fr_hr_work_entry_holidays

## Overview
French HR extension that fills work entry gaps for part-time employees on leave. When a part-time employee's calendar differs from the company calendar, days where the company works but the employee doesn't generate no default work entries. This module detects those gaps and creates additional `leave` work entries for them. Requires `l10n_fr_hr_holidays` and `hr_work_entry_holidays`.

## Country
[France](odoo-18/Modules/account.md) 🇫🇷

## Dependencies
- l10n_fr_hr_holidays
- hr_work_entry_holidays

## Key Models

### HrContract
`models/hr_contract.py` — extends `hr.contract`
- `_get_contract_work_entries_values()` — override: for FR contracts where employee calendar differs from company calendar, searches for validated leaves with `l10n_fr_date_to_changed = True` (from [l10n_fr_hr_holidays](odoo-18/Modules/l10n_fr_hr_holidays.md)), computes company calendar attendances minus employee attendances for the leave period, and creates additional `leave` work entries for the difference. Result includes both standard employee work entries and these supplemental company-calendar entries.

### HrWorkEntry
`models/hr_work_entry.py` — extends `hr.work.entry`
- `_filter_french_part_time_entries()` — filters work entries where company is FR and employee calendar != company calendar
- `_mark_leaves_outside_schedule()` — override: skips gap detection for French part-time entries (handled by contract method instead)
- `_get_duration_batch()` — override: for French part-time entries where computed duration is 0, falls back to raw time delta `(date_stop - date_start).seconds/3600` (for gaps between company schedule and employee schedule)

## Data Files
No data files.

## Chart of Accounts
Not applicable (HR module, no accounting).

## Tax Structure
Not applicable.

## Fiscal Positions
Not applicable.

## EDI/Fiscal Reporting
Not applicable.

## Installation
`auto_install: True` — auto-installed with `hr_work_entry_holidays` when dependencies are present.

## Historical Notes

**Odoo 17 → 18 changes:**
- Version 1.0; the two-module combination (l10n_fr_hr_holidays + l10n_fr_hr_work_entry_holidays) was restructured in Odoo 16 with the introduction of `l10n_fr_date_to_changed` flag on leaves
- Part-time gap work entries are essential for French payroll compliance — payslips must reflect company calendar hours, not just employee contract hours
- The `_filter_french_part_time_entries` pattern is used across both `l10n_fr_hr_holidays` and this module for consistent filtering

**Performance Notes:**
- Work entry generation runs on contract batch generation; only processes FR contracts
- Leave search limited to active date range — efficient for typical payroll runs