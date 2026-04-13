---
Module: sales_team
Version: 18.0
Type: addon
Tags: #crm #sales #team
---

# sales_team

Sales team management. Provides `crm.team` (sales team), `crm.team.member` (membership), and `crm.tag` (team tagging), plus user-level sales team fields.

## Module Overview

**Category:** Sales/Sales
**Depends:** `base`, `mail`
**Version:** 1.1
**License:** LGPL-3

## What It Does

Core sales team infrastructure. Manages team membership, default team assignment on documents, dashboard graphs, and optional multi-team membership mode.

## Models

### `crm.team`

The main sales team model. Inherits `mail.thread` for chatter.

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Team name (required, translatable) |
| `user_id` | Many2one | Team leader |
| `member_ids` | Many2many | Computed/inverse from `crm_team_member_ids` |
| `crm_team_member_ids` | One2many | Active membership records |
| `crm_team_member_all_ids` | One2many | All membership records (incl. inactive) |
| `company_id` | Many2one | Company |
| `currency_id` | Many2one | Derived from company |
| `color` | Integer | Kanban color |
| `sequence` | Integer | Sort order |
| `is_favorite` | Boolean | Show on dashboard (computed from favorite users) |
| `dashboard_graph_data` | Text | JSON graph for dashboard |

**Multi-membership mode:** Controlled by `ir.config_parameter` key `sales_team.membership_multi`. When disabled, users may belong to only one active team; adding a user to a new team auto-archives their previous membership.

**Dashboard graph:** `_get_dashboard_graph_data()` generates weekly bar chart data for the last 4 weeks, using `_graph_data()` to run a raw SQL query against the configured graph model. Designed to be overridden by `crm` and `sale` modules.

**Key methods:**
- `_get_default_team_id()` — 5-step heuristic for default team assignment (my teams by domain, my teams, context, company by domain, company first)
- `_add_members_to_favorites()` — auto-adds new members to the team's favorites

**Protected from deletion:** Default teams `salesteam_website_sales` and `pos_sales_team` cannot be deleted.

### `crm.team.member`

Join table between `crm.team` and `res.users` with additional state (active/inactive).

| Field | Type | Description |
|-------|------|-------------|
| `crm_team_id` | Many2one | Sales team |
| `user_id` | Many2one | Salesperson |
| `active` | Boolean | Active membership |
| `is_membership_multi` | Boolean | Inherits config from team |

**Constrains:** `@api.constrains` prevents duplicate active membership for the same `(user_id, crm_team_id)` pair in mono-membership mode.

**Lifecycle:** In mono-membership mode, creating a new membership archives other memberships for that user. `write()` with `active=True` also triggers auto-archiving.

### `crm.tag`

Simple colored tag model for labeling deals/teams.

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Tag name (required, translatable, unique) |
| `color` | Integer | Kanban color (random default 1-11) |

### `res.users` (Extended)

| Field | Type | Description |
|-------|------|-------------|
| `crm_team_ids` | Many2many | Computed from `crm_team_member_ids` |
| `sale_team_id` | Many2one | First active team membership (sorted by create_date) |

`action_archive()` cascades to archive all `crm.team.member` records for the user.

## Data

| File | Purpose |
|------|---------|
| `data/crm_team_data.xml` | Default sales teams (Website Sales, etc.) |
| `security/sales_team_security.xml` | Record rules for team access |
| `security/ir.model.access.csv` | ACLs |
| `views/crm_team_views.xml` | Form, list, kanban, search views |
| `views/crm_team_member_views.xml` | Form/list for membership |
| `views/crm_tag_views.xml` | Form/list for tags |
| `views/mail_activity_views.xml` | Activity views for teams |
| `demo/crm_team_demo.xml` | Demo team data |
| `demo/crm_tag_demo.xml` | Demo tags |

## Static Assets

- `sales_team/static/**/*` — backend JS/CSS assets

## Key Details

- Team dashboard graph model is a skeleton; `crm` and `sale` override `_graph_get_model()`, `_graph_y_query()`, etc.
- Mono vs multi membership is a global switch via `ir.config_parameter`, not per-team.
- The `favorite_user_ids` Many2many on `crm.team` drives the `is_favorite` computed field.

---

*See also: [Modules/CRM](CRM.md), [Modules/sale](sale.md), [Modules/sale_management](sale_management.md)*
