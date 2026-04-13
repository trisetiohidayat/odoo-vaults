---
Module: spreadsheet_dashboard_website_sale_slides
Version: 18.0
Type: addon
Tags: #spreadsheet #dashboard #elearning #website
---

# spreadsheet_dashboard_website_sale_slides

Spreadsheet dashboard for eLearning (website + sale slides) reporting.

## Module Overview

**Category:** Hidden
**Depends:** `spreadsheet_dashboard`, `website_sale_slides`
**Auto-Install:** `website_sale_slides`
**License:** LGPL-3

## What It Does

Provides a `spreadsheet.dashboard` record named "eLearning" for course/slide sales. Uses `sale.order` as the primary data model. Group-restricted to `website_slides.group_website_slides_manager`. Auto-installs when `website_sale_slides` is present.

## Extends

- [Modules/spreadsheet_dashboard](spreadsheet_dashboard.md) — base dashboard framework
- `website_sale_slides` — eLearning paid courses

## Data

| File | Purpose |
|------|---------|
| `data/dashboards.xml` | Registers dashboard "eLearning", group-restricted to `website_slides.group_website_slides_manager` |

## Key Details

- Dashboard group: `spreadsheet_dashboard_group_website`
- Sequence: 200
- Published by default

---

*See also: [Modules/spreadsheet_dashboard](spreadsheet_dashboard.md), [Modules/website_slides](website_slides.md)*
