# Spreadsheet Dashboard for Sale Timesheet

## Overview
- **Name**: Spreadsheet dashboard for time sheets
- **Category**: Productivity/Dashboard
- **Summary**: Pre-built spreadsheet dashboard for timesheet-billed sales metrics
- **Depends**: `spreadsheet_dashboard`, `sale_timesheet`
- **Auto-install**: Yes (when `sale_timesheet` is installed)
- **License**: LGPL-3

## Description

Provides a pre-configured [Modules/spreadsheet_dashboard](Modules/spreadsheet_dashboard.md) template combining sales order data with timesheet billing metrics. Shows revenue recognized from time-and-materials sales alongside project time tracking.

This is a **data-only module**: contains only a `data/dashboards.xml` file that creates a sample sale-timesheet dashboard record.

## Key Features
- Timesheet-billed revenue per project and salesperson
- Hours sold vs. hours delivered analysis
- Profit margin on time-and-materials sales
- Milestone completion tracking
- Auto-installs when `sale_timesheet` is active

## Related
- [Modules/spreadsheet_dashboard](Modules/spreadsheet_dashboard.md) — Dashboard framework
- [Modules/sale_timesheet](Modules/sale_timesheet.md) — Timesheet-based billing on sales orders
- [Modules/hr_timesheet](Modules/hr_timesheet.md) — Timesheet entry
- [Modules/Project](Modules/Project.md) — Project management
