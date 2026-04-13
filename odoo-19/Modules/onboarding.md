# Onboarding Toolbox

**Module:** `onboarding`
**Category:** Hidden/Tools
**Depends:** `web`
**License:** LGPL-3

## Overview

Framework for in-app onboarding panels. Displays step-by-step setup guides that guide users through initial Odoo configuration. Each onboarding consists of steps with target actions; progress is tracked per company and persists across sessions.

## Dependencies

- [Modules/web](modules/web.md) - Web framework

## Models

### `onboarding.onboarding`

Container for an onboarding panel (a group of related setup steps).

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Display name |
| `route_name` | Char | One-word identifier for URL routing (`/onboarding/{route_name}`) |
| `step_ids` | Many2many | Steps in this onboarding |
| `text_completed` | Char | Message shown when onboarding is completed |
| `is_per_company` | Boolean | Whether steps are company-specific |
| `panel_close_action_name` | Char | Action to run when panel is closed |
| `current_progress_id` | Many2one | Active `onboarding.progress` for current company |
| `current_onboarding_state` | Selection | `not_done`, `just_done`, `done` |
| `is_onboarding_closed` | Boolean | Whether user closed the panel |

### `onboarding.onboarding.step`

Individual step within an onboarding.

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Step title |
| `description` | Char | Step description |
| `action_id` | Many2one | ir.actions.act_window to trigger |
| `is_per_company` | Boolean | Step is company-specific |
| `panel_state` | Selection | `not_done`, `just_done`, `done` |
| `onboarding_ids` | Many2many | Onboardings containing this step |

### `onboarding.progress`

Tracks progress of an onboarding for a specific company.

| Field | Type | Description |
|-------|------|-------------|
| `onboarding_id` | Many2one | Parent onboarding |
| `company_id` | Many2one | Company (optional, for per-company onboardings) |
| `progress_step_ids` | Many2many | Individual step progress records |
| `onboarding_state` | Selection | `not_done`, `just_done`, `done` (computed) |
| `is_onboarding_closed` | Boolean | Panel dismissed by user |

**SQL constraint:** Unique index on `(onboarding_id, COALESCE(company_id, 0))`

**Key Methods:**
| Method | Description |
|--------|-------------|
| `_compute_onboarding_state()` | `done` if all steps are done/just_done |
| `_recompute_progress_step_ids()` | Sync step progress when steps change |
| `_get_and_update_onboarding_state()` | Called by controller; transitions `just_done` -> `done` |
| `action_close()` | Marks panel as closed |
| `action_toggle_visibility()` | Toggle panel visibility |

### `onboarding.progress.step`

Tracks completion of individual steps.

| Field | Type | Description |
|-------|------|-------------|
| `step_id` | Many2one | Parent step |
| `progress_id` | Many2one | Parent progress record |
| `step_state` | Selection | `not_done`, `just_done`, `done` |

---

## Onboarding States

| State | Meaning |
|-------|---------|
| `not_done` | Step/onboarding not yet completed |
| `just_done` | Just completed, shown once |
| `done` | Completed |

---

## Related

- [Modules/web](modules/web.md) - Web framework
