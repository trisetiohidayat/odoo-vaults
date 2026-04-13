# Spreadsheet Dashboard for Point of Sale

## Overview
- **Name**: Spreadsheet dashboard for point of sale
- **Category**: Productivity/Dashboard
- **Summary**: Pre-built spreadsheet dashboard for POS and HR performance metrics
- **Depends**: `spreadsheet_dashboard`, `pos_hr`
- **Auto-install**: Yes (when `pos_hr` is installed)
- **License**: LGPL-3

## Description

Provides a pre-configured [Modules/spreadsheet_dashboard](modules/spreadsheet_dashboard.md) template for POS managers to track sales performance per employee and session. Combines POS order data from [Modules/point_of_sale](modules/point_of_sale.md) with employee attribution from [Modules/pos_hr](modules/pos_hr.md).

This is a **data-only module**: contains only a `data/dashboards.xml` file that creates a sample POS-HR dashboard record.

## Key Features
- Sales per employee/cashier
- Session reconciliation (expected vs. actual cash)
- Order count and average ticket size
- Per-category product sales breakdown
- Auto-installs when `pos_hr` is active

## Related
- [Modules/spreadsheet_dashboard](modules/spreadsheet_dashboard.md) — Dashboard framework
- [Modules/pos_hr](modules/pos_hr.md) — POS employee login and per-cashier reporting
- [Modules/point_of_sale](modules/point_of_sale.md) — Point of Sale base
