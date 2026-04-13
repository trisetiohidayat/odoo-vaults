---
Module: spreadsheet_dashboard_hr_timesheet
Version: 18.0
Type: addon
Tags: #spreadsheet #dashboard #timesheet
---

# spreadsheet_dashboard_hr_timesheet

Spreadsheet dashboard for project/task timesheet reporting.

## Module Overview

**Category:** Hidden
**Depends:** `spreadsheet_dashboard`, `hr_timesheet`
**Auto-Install:** `hr_timesheet`
**License:** LGPL-3

## What It Does

Provides a `spreadsheet.dashboard` record named "Project" for tracking project task hours. No `main_data_model_ids` defined (dashboard uses tasks directly). Group-restricted to `hr_timesheet.group_hr_timesheet_approver`. Auto-installs when `hr_timesheet` is present.

## Extends

- [Modules/spreadsheet_dashboard](modules/spreadsheet_dashboard.md) — base dashboard framework
- `hr_timesheet` — HR timesheet tracking

## Data

| File | Purpose |
|------|---------|
| `data/dashboards.xml` | Registers dashboard "Project", group-restricted to `hr_timesheet.group_hr_timesheet_approver` |

## Key Details

- Dashboard group: `spreadsheet_dashboard_group_project`
- Sequence: 100
- Published by default

---

*See also: [Modules/spreadsheet_dashboard](modules/spreadsheet_dashboard.md), [Modules/hr_timesheet](modules/hr_timesheet.md)*
