---
Module: spreadsheet_dashboard_im_livechat
Version: 18.0
Type: addon
Tags: #spreadsheet #dashboard #livechat
---

# spreadsheet_dashboard_im_livechat

Spreadsheet dashboard for live chat channel reporting.

## Module Overview

**Category:** Hidden
**Depends:** `spreadsheet_dashboard`, `im_livechat`
**Auto-Install:** `im_livechat`
**License:** LGPL-3

## What It Does

Provides a `spreadsheet.dashboard` record for live chat metrics. Uses `im_livechat.report.channel` as the primary data model. Group-restricted to `im_livechat.im_livechat_group_manager`. Auto-installs when `im_livechat` is present.

## Extends

- [Modules/spreadsheet_dashboard](odoo-18/Modules/spreadsheet_dashboard.md) — base dashboard framework
- `im_livechat` — live chat channel tracking

## Data

| File | Purpose |
|------|---------|
| `data/dashboards.xml` | Registers dashboard "Live chat", group-restricted to `im_livechat.im_livechat_group_manager` |

## Key Details

- Dashboard group: `spreadsheet_dashboard_group_website`
- Sequence: 100
- Published by default

---

*See also: [Modules/spreadsheet_dashboard](odoo-18/Modules/spreadsheet_dashboard.md)*
