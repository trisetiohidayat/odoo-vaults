---
Module: website_membership
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_membership #membership
---

## Overview

**Module:** `website_membership`
**Depends:** `website`, `membership`
**Location:** `~/odoo/odoo18/odoo/addons/website_membership/`
**Purpose:** Displays public members list on website and allows filtering by company membership lines.

## Models

### `membership.membership_line` (website_membership/models/membership.py)

Inherits: `membership.membership_line`

| Method | Decorator | Description |
|---|---|---|
| `_get_published_companies(limit=None)` | raw SQL | Returns `partner_id` list of companies that are: published, marked as company, and have a membership line in `self`. Uses raw SQL with `JOIN` for performance. |

### `website` (website_membership/models/website.py)

Inherits: `website`

| Method | Decorator | Description |
|---|---|---|
| `get_suggested_controllers()` | override | Appends `(_('Members'), '/members', 'website_membership')` to the website navigation |

## Security / Data

`ir.model.access.csv` present.

Data files:
- `website_membership.xml` — QWeb template for members page
- `membership_demo.xml` — demo membership lines

## Critical Notes

- v17→v18: No breaking changes.
- `_get_published_companies` uses raw SQL for performance when listing many members on the website.
- The `/members` page is served by this module's controller (check for `controllers/` directory).