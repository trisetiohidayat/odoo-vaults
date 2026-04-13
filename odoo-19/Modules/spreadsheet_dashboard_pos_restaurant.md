# Spreadsheet Dashboard for Restaurants

## Overview
- **Name**: Spreadsheet dashboard for restaurants
- **Category**: Productivity/Dashboard
- **Summary**: Pre-built spreadsheet dashboard for restaurant POS performance
- **Depends**: `spreadsheet_dashboard`, `pos_hr`, `pos_restaurant`
- **Auto-install**: Yes (when `pos_hr` and `pos_restaurant` are installed)
- **License**: LGPL-3

## Description

Provides a pre-configured [Modules/spreadsheet_dashboard](odoo-18/Modules/spreadsheet_dashboard.md) template tailored for restaurant POS operators. Combines POS order data with restaurant-specific dimensions (floors, tables, courses) and employee attribution.

This is a **data-only module**: contains only a `data/dashboards.xml` file that creates a sample restaurant dashboard record.

## Key Features
- Table turnover and revenue per table/floor
- Average order value and covers per shift
- Server/cashier performance breakdown
- Course timing analysis (time from order to delivery)
- Split-bill revenue tracking
- Auto-installs when `pos_hr` and `pos_restaurant` are active

## Related
- [Modules/spreadsheet_dashboard](odoo-18/Modules/spreadsheet_dashboard.md) — Dashboard framework
- [Modules/pos_restaurant](odoo-18/Modules/pos_restaurant.md) — Restaurant POS (floors, tables, splitbill)
- [Modules/pos_hr](odoo-17/Modules/pos_hr.md) — POS employee login
