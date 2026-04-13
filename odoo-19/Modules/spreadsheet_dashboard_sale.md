# Spreadsheet Dashboard for Sales

## Overview
- **Name**: Spreadsheet dashboard for sales
- **Category**: Productivity/Dashboard
- **Summary**: Pre-built spreadsheet dashboard with sales KPIs
- **Depends**: `spreadsheet_dashboard`, `sale`
- **Auto-install**: Yes (when `sale` is installed)
- **License**: LGPL-3

## Description

Provides a pre-configured [Modules/spreadsheet_dashboard](spreadsheet_dashboard.md) template for sales managers with live sales metrics sourced from sale orders, invoices, and deliveries.

This is a **data-only module**: contains only a `data/dashboards.xml` file that creates a sample sales dashboard record.

## Key Features
- Sales order volume and revenue (by period, salesperson, team)
- Average order value and order count
- Pipeline conversion rates
- Top-selling products and categories
- Auto-installs when `sale` is active

## Related
- [Modules/spreadsheet_dashboard](spreadsheet_dashboard.md) — Dashboard framework
- [Modules/Sale](Sale.md) — Sales management base
- [Modules/spreadsheet_account](spreadsheet_account.md) — Accounting formulas for financial sheets
