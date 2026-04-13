# Spreadsheet Dashboard for Events

## Overview
- **Name**: Spreadsheet dashboard for events
- **Category**: Productivity/Dashboard
- **Summary**: Pre-built spreadsheet dashboard for event sales metrics
- **Depends**: `spreadsheet_dashboard`, `event_sale`
- **Auto-install**: Yes (when `event_sale` is installed)
- **License**: LGPL-3

## Description

Provides a pre-configured [Modules/spreadsheet_dashboard](odoo-18/Modules/spreadsheet_dashboard.md) template for event managers showing event sales performance. Dashboard content is sourced from `event.registration`, `event.ticket`, and sale order data via [Modules/spreadsheet_dashboard](odoo-18/Modules/spreadsheet_dashboard.md).

This is a **data-only module**: contains only a `data/dashboards.xml` file that creates a sample event sales dashboard record.

## Key Features
- Event registration counts and revenue
- Ticket sales breakdown by event and ticket type
- Sales order-linked event revenue
- Attendee conversion metrics
- Auto-installs when `event_sale` is active

## Related
- [Modules/spreadsheet_dashboard](odoo-18/Modules/spreadsheet_dashboard.md) — Dashboard framework
- [Modules/event_sale](odoo-17/Modules/event_sale.md) — Event ticket sales
- [Modules/event](odoo-18/Modules/event.md) — Event management base
