# Spreadsheet Dashboard for Expenses

## Overview
- **Name**: Spreadsheet dashboard for expenses
- **Category**: Productivity/Dashboard
- **Summary**: Pre-built spreadsheet dashboard for expense reporting metrics
- **Depends**: `spreadsheet_dashboard`, `sale_expense`
- **Auto-install**: Yes (when `sale_expense` is installed)
- **License**: LGPL-3

## Description

Provides a pre-configured [[Modules/spreadsheet_dashboard]] template for finance/HR teams to monitor expense submissions, approvals, and re-invoicing. Uses data from expense reports and sale order expense tracking via [[Modules/sale_expense]].

This is a **data-only module**: contains only a `data/dashboards.xml` file that creates a sample expense dashboard record.

## Key Features
- Expense submission totals by employee and department
- Expense approval funnel (draft, submitted, approved, paid)
- Expense-to-invoice reconciliation tracking
- Re-invoiced expense margin analysis
- Auto-installs when `sale_expense` is active

## Related
- [[Modules/spreadsheet_dashboard]] — Dashboard framework
- [[Modules/hr_expense]] — HR expense management
- [[Modules/sale_expense]] — Expense re-invoicing via sales orders
