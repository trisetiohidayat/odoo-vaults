# Spreadsheet Dashboard for Timesheets

## Overview
- **Name**: Spreadsheet dashboard for time sheets
- **Category**: Productivity/Dashboard
- **Summary**: Pre-built spreadsheet dashboard for timesheet and project time tracking
- **Depends**: `spreadsheet_dashboard`, `hr_timesheet`
- **Auto-install**: Yes (when `hr_timesheet` is installed)
- **License**: LGPL-3

## Description

Provides a pre-configured [Modules/spreadsheet_dashboard](odoo-18/Modules/spreadsheet_dashboard.md) template for project managers and HR to visualize timesheet data — hours logged per employee, project, and task. Data is sourced from `account.analytic.line` records created by [Modules/hr_timesheet](odoo-18/Modules/hr_timesheet.md).

This is a **data-only module**: contains only a `data/dashboards.xml` file that creates a sample timesheet dashboard record.

## Key Features
- Hours logged per employee and project
- Task-level time breakdown
- Utilization rate calculations
- Billable vs. non-billable time analysis
- Auto-installs when `hr_timesheet` is active

## Related
- [Modules/spreadsheet_dashboard](odoo-18/Modules/spreadsheet_dashboard.md) — Dashboard framework
- [Modules/hr_timesheet](odoo-18/Modules/hr_timesheet.md) — Timesheet entry and project time tracking
- [Modules/Project](odoo-18/Modules/project.md) — Project management
