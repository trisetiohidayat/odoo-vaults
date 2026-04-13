---
Module: utm
Version: 18.0
Type: addon
Tags: #utm #marketing #tracking
---

# utm

UTM tracking module for marketing campaigns. Provides models to track the source, medium, and campaign of marketing-generated leads/opportunities.

## Module Overview

**Category:** Hidden
**Depends:** `base`, `web`
**Version:** 1.1
**License:** LGPL-3

## What It Does

Central UTM infrastructure consumed by CRM, mass mailing, website links, and other marketing modules. Tracks `campaign_id`, `source_id`, and `medium_id` on any record that mixes in `utm.mixin`. URL parameters (`utm_campaign`, `utm_source`, `utm_medium`) are captured from HTTP requests and stored in browser cookies for 31 days.

## Models

### `utm.campaign`

| Field | Type | Description |
|-------|------|-------------|
| `title` | Char | Human-readable campaign name (required) |
| `name` | Char | Computed unique identifier (stored, from `title`) |
| `user_id` | Many2one | Responsible user |
| `stage_id` | Many2one | Campaign stage (`utm.stage`) |
| `tag_ids` | Many2many | Campaign tags (`utm.tag`) |
| `is_auto_campaign` | Boolean | Mark automatically generated campaigns |
| `color` | Integer | Kanban color |

`name` is computed from `title` via `_get_unique_names()` to ensure uniqueness with counter appending (e.g., "Fall Drive [2]").

### `utm.medium`

Represents the delivery method (Email, Direct, Website, etc.). Enforces immutability of built-in mediums via `_unlink_except_utm_medium_record()`. Provides `_fetch_or_create_utm_medium()` for dynamically creating mediums from code. Has a SQL unique constraint on `name`.

### `utm.source`

Represents the traffic source (Search engine, Newsletter, LinkedIn, etc.). Supports auto-generation of source names from the content of the record being tracked (e.g., a mailing name). Has a SQL unique constraint on `name`.

### `utm.stage`

Simple sequence-ordered stage for campaign Kanban workflow (New, In Progress, Done, etc.).

### `utm.tag`

Colored tags for categorizing campaigns (Marketing, Newsletter, etc.).

### `utm.mixin` (AbstractModel)

Used as a mixin on models that need UTM tracking:

```python
class MyModel(models.Model):
    _name = 'my.model'
    _inherit = ['utm.mixin']
```

Fields added by the mixin:

| Field | Type | Description |
|-------|------|-------------|
| `campaign_id` | Many2one | `utm.campaign` |
| `source_id` | Many2one | `utm.source` |
| `medium_id` | Many2one | `utm.medium` |

Key methods:
- `tracking_fields()` — returns `[('utm_campaign', 'campaign_id', 'odoo_utm_campaign'), ...]`
- `_find_or_create_record()` — searches by name (case-insensitive), creates if not found
- `_get_unique_names()` — generates unique names with counter appending
- `_split_name_and_count()` — static parser for `"Name [N]"` format

### `ir.http` (Extended)

`_set_utm()` post-dispatch hook reads URL params from `request.params` and sets matching cookies on the response with 31-day max-age if values differ from existing cookies.

## Data

| File | Purpose |
|------|---------|
| `data/utm_medium_data.xml` | 10 default mediums (Email, Direct, Website, Phone, Banner, X, Facebook, LinkedIn, Television, GoogleAdwords) |
| `data/utm_source_data.xml` | 9 default sources (Search engine, Newsletter, LinkedIn, etc.) |
| `data/utm_stage_data.xml` | Campaign stages |
| `data/utm_tag_data.xml` | Campaign tags |
| `data/utm_campaign_demo.xml` | Demo campaigns |
| `views/utm_campaign_views.xml` | Form, list, kanban, search views + action for UTM campaigns |
| `views/utm_medium_views.xml` | Form/list views for mediums |
| `views/utm_source_views.xml` | Form/list views for sources |
| `views/utm_stage_views.xml` | Form/list views for stages |
| `views/utm_tag_views.xml` | Form/list views for tags |
| `views/utm_menus.xml` | UTM menus under Configuration |
| `security/ir.model.access.csv` | ACLs for all UTM models |

## Static Assets

- `static/src/scss/utm_views.scss` — Kanban styling for UTM campaigns
- `static/src/js/utm_campaign_kanban_examples.js` — Sample data for kanban examples

## Key Details

- Built-in mediums are protected from deletion via `@api.ondelete(at_uninstall=False)`
- UTM fields are auto-populated from cookies on `default_get()` for non-salesmen
- Salespeople (`sales_team.group_sale_salesman`) are excluded from automatic UTM capture to avoid polluting campaign data

---

*See also: [Modules/CRM](CRM.md), [Modules/mass_mailing](mass_mailing.md), [Patterns/Workflow Patterns](Workflow Patterns.md)*
