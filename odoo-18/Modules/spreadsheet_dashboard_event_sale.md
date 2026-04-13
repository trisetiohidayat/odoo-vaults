---
Module: spreadsheet_dashboard_event_sale
Version: 18.0
Type: addon
Tags: #spreadsheet #dashboard #events
---

# spreadsheet_dashboard_event_sale

Spreadsheet dashboard providing pre-configured reporting for event sales.

## Module Overview

**Category:** Hidden
**Depends:** `spreadsheet_dashboard`, `event_sale`
**Auto-Install:** `event_sale`
**License:** LGPL-3

## What It Does

Provides a `spreadsheet.dashboard` record that embeds a pre-built spreadsheet with event sales KPIs (registrations, revenue, ticket types). The dashboard uses `event.event` as its primary data model. It auto-installs when `event_sale` is present.

## Extends

- [Modules/spreadsheet_dashboard](Modules/spreadsheet_dashboard.md) — base dashboard framework
- `event_sale` — event ticket sales

## Data

| File | Purpose |
|------|---------|
| `data/dashboards.xml` | Registers `spreadsheet.dashboard` with name "Events", group-restricted to `event.group_event_manager` |

## Key Details

- Dashboard group: `spreadsheet_dashboard_group_marketing`
- Sequence: 60
- Published by default

---

*See also: [Modules/spreadsheet_dashboard](Modules/spreadsheet_dashboard.md)*
