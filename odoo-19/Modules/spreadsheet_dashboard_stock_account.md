# Spreadsheet Dashboard for Stock

## Overview
- **Name**: Spreadsheet dashboard for stock
- **Category**: Productivity/Dashboard
- **Summary**: Pre-built spreadsheet dashboard for inventory valuation and stock metrics
- **Depends**: `spreadsheet_dashboard`, `stock_account`
- **Auto-install**: Yes (when `stock_account` is installed)
- **License**: LGPL-3

## Description

Provides a pre-configured [Modules/spreadsheet_dashboard](Modules/spreadsheet_dashboard.md) template for warehouse managers and controllers to monitor inventory levels, valuation, and stock-valuation accounting entries.

This is a **data-only module**: contains only a `data/dashboards.xml` file that creates a sample stock dashboard record.

## Key Features
- Current stock valuation (from `stock.valuation.layer`)
- Inventory value by warehouse and category
- Stock moves and turnover rates
- Valuation adjustment entries (from `stock_account`)
- Low stock alerts and reorder analysis
- Auto-installs when `stock_account` is active

## Related
- [Modules/spreadsheet_dashboard](Modules/spreadsheet_dashboard.md) — Dashboard framework
- [Modules/stock_account](Modules/stock_account.md) — Stock valuation and accounting entries
- [Modules/Stock](Modules/stock.md) — Inventory management base
