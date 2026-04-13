# Spreadsheet Dashboard for Accounting

## Overview
- **Name**: Spreadsheet dashboard for accounting
- **Category**: Productivity/Dashboard
- **Summary**: Pre-built spreadsheet dashboard with accounting KPIs
- **Depends**: `spreadsheet_dashboard`, `account`
- **Auto-install**: Yes (when `account` is installed)
- **License**: LGPL-3

## Description

Provides a pre-configured [Modules/spreadsheet_dashboard](Modules/spreadsheet_dashboard.md) template tailored for accounting and finance teams. The dashboard uses accounting spreadsheet formulas from [Modules/spreadsheet_account](Modules/spreadsheet_account.md) to display live financial data including totals, balances, and period comparisons — all sourced directly from `account.move.line`.

This is a **data-only module**: it contains no Python models, only a `data/dashboards.xml` file that creates a sample dashboard record pre-populated with accounting spreadsheet content.

## Key Features
- Pre-built accounting KPI dashboard (revenue, expenses, balance)
- Live account balance formulas using account codes
- Period comparison (current month vs. prior month vs. YTD)
- Partner receivable/payable balance breakdowns
- Auto-installs when the Accounting app is active

## Related
- [Modules/spreadsheet_dashboard](Modules/spreadsheet_dashboard.md) — Dashboard framework
- [Modules/spreadsheet_account](Modules/spreadsheet_account.md) — Accounting formulas
- [Modules/Account](Modules/account.md) — Accounting base
