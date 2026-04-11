---
Module: onboarding
Version: 18.0.0
Type: addon
Tags: #odoo18 #onboarding
---

## Overview
Onboarding Toolbox. Generic framework for managing onboarding panels (step-by-step setup wizards shown in the Odoo interface). Ships 4 models: `onboarding.onboarding` (the container), `onboarding.onboarding.step` (individual steps), `onboarding.progress` (company-level progress tracker), `onboarding.progress.step` (step-level progress tracker). Supports per-company and global onboardings. Used by most Odoo apps to register their setup checklists.

## Models

### onboarding.onboarding
Inherits from: `base.model`
File: `~/odoo/odoo18/odoo/addons/onboarding/models/onboarding_onboarding.py`
`_name = 'onboarding.onboarding'`

| Field | Type | Description |
|-------|------|-------------|
| name | Char | Name of the onboarding; `translate=True` |
| route_name | Char | One-word identifier for URL routing (`/onboarding/{route_name}`); UNIQUE |
| step_ids | Many2many(onboarding.onboarding.step) | Steps in this onboarding |
| text_completed | Char | Message shown on completion; default="Nice work!..." |
| is_per_company | Boolean | `compute='_compute_is_per_company'`, `store=False`; True if any step or existing progress is per-company |
| panel_close_action_name | Char | Action name to call when panel is closed |
| current_progress_id | Many2one | `compute='_compute_current_progress'`; progress for current company |
| current_onboarding_state | Selection | `compute`: `'not_done'`, `'just_done'`, `'done'` |
| is_onboarding_closed | Boolean | `compute`: whether panel was closed |
| progress_ids | One2many | All progress records across companies |
| sequence | Integer | Default=10; ordering |

**SQL Constraints:**
```
UNIQUE(route_name)
```

**Methods:**
| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _compute_is_per_company | self | None | True if any step has `is_per_company=True` OR any progress has `company_id` set |
| _compute_current_progress | self | None | Filters `progress_ids` to `company_id IN {False, env.company.id}` |
| write | vals | bool | On step_ids change: triggers `_recompute_progress_step_ids` on related progress |
| action_close | self | bool | Closes the panel via `current_progress_id.action_close()` |
| action_close_panel | xmlid | None | Static method: closes onboarding by XML ID |
| action_refresh_progress_ids | self | None | For per-company onboardings with orphaned progress: unlinks old progress, recreates |
| action_toggle_visibility | self | bool | Toggles panel visibility |
| _search_or_create_progress | self | record | Creates progress record if missing for current company |
| _create_progress | self | records | Creates `onboarding.progress` for each onboarding; links per-company steps |
| _prepare_rendering_values | self | dict | Returns values for QWeb template: `close_method`, `steps`, `state`, `text_completed` |

### onboarding.onboarding.step
Inherits from: `base.model`
File: `~/odoo/odoo18/odoo/addons/onboarding/models/onboarding_onboarding_step.py`
`_name = 'onboarding.onboarding.step'`

| Field | Type | Description |
|-------|------|-------------|
| onboarding_ids | Many2many(onboarding.onboarding) | Reverse link |
| title | Char | Step title; `translate=True` |
| description | Char | Description; `translate=True` |
| button_text | Char | Button label; `translate=True`; default="Let's do it" |
| done_icon | Char | Font Awesome icon when completed; default='fa-star' |
| done_text | Char | Completion text; `translate=True`; default='Step Completed!' |
| step_image | Binary | Optional image |
| step_image_filename | Char | Filename |
| step_image_alt | Char | Alt text; `translate=True` |
| panel_step_open_action_name | Char | Action to execute when opening this step |
| current_progress_step_id | Many2one | `compute='_compute_current_progress'` |
| current_step_state | Selection | `compute`: `'not_done'`, `'just_done'`, `'done'` |
| progress_ids | One2many | All progress step records |
| is_per_company | Boolean | Default=True |
| sequence | Integer | Default=10 |

**Methods:**
| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _compute_current_progress | self | None | Filters `progress_ids` by current company; sets state or `'not_done'` |
| check_step_on_onboarding_has_action | self | None | `@constrains`: steps in an onboarding MUST have `panel_step_open_action_name` |
| write | vals | bool | On `is_per_company` change: unlinks progress (resets); refreshes parent onboarding progress |
| action_set_just_done | self | records | Creates missing progress step records, then sets state to `'just_done'` |
| action_validate_step | xml_id | str | Class method: looks up by XML ID, calls `action_set_just_done()`; returns `'NOT_FOUND'`, `'JUST_DONE'`, or `'WAS_DONE'` |
| _create_progress_steps | self | records | Creates `onboarding.progress.step` records for current company |

### onboarding.progress
Inherits from: `base.model`
File: `~/logmodels/onboarding_progress.py`
`_name = 'onboarding.progress'`

| Field | Type | Description |
|-------|------|-------------|
| onboarding_state | Selection | `compute='_compute_onboarding_state'`, `store=True` |
| is_onboarding_closed | Boolean | User-settable; whether panel is closed |
| company_id | Many2one(res.company) | Optional; null = global |
| onboarding_id | Many2one(onboarding.onboarding) | Required, `ondelete='cascade'` |
| progress_step_ids | Many2many(onboarding.progress.step) | Progress records for each step |

**SQL:**
- Partial unique index: `ONboarding_progress (onboarding_id, COALESCE(company_id, 0))` — prevents duplicate per-company progress

**Methods:**
| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _compute_onboarding_state | self | None | `'done'` if ALL steps are in `'just_done'` or `'done'`; else `'not_done'` |
| _recompute_progress_step_ids | self | None | Syncs `progress_step_ids` with `onboarding_id.step_ids.current_progress_step_id` |
| action_close | self | bool | Sets `is_onboarding_closed=True` |
| action_toggle_visibility | self | bool | Toggles `is_onboarding_closed` |
| _get_and_update_onboarding_state | self | dict | Core rendering method: computes per-step state, transitions `'just_done'` → `'done'`, returns full state dict for JS |

### onboarding.progress.step
Inherits from: `base.model`
File: `~/odoo/odoo18/odoo/addons/onboarding/models/onboarding_progress_step.py`
`_name = 'onboarding.progress.step'`

| Field | Type | Description |
|-------|------|-------------|
| progress_ids | Many2many(onboarding.progress) | Reverse link |
| step_state | Selection | `default='not_done'`; values: `'not_done'`, `'just_done'`, `'done'` |
| step_id | Many2one(onboarding.onboarding.step) | Required, `ondelete='cascade'` |
| company_id | Many2one(res.company) | `ondelete='cascade'` |

**SQL:**
- Partial unique index: `ONboarding_progress_step (step_id, COALESCE(company_id, 0))`

**Methods:**
| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| action_consolidate_just_done | self | records | Transitions `'just_done'` → `'done'`; returns affected records |
| action_set_just_done | self | records | Transitions `'not_done'` → `'just_done'`; returns affected records |

## Critical Notes
- **Per-company vs global:** `is_per_company=True` (default for steps) means each company has its own progress. `progress_step.company_id= False` means a single record covers all companies
- **Unique indexes:** Both `onboarding.progress` and `onboarding.progress.step` have DB-level unique indexes using `COALESCE(company_id, 0)` to handle NULL company gracefully
- **`'just_done'` state:** Exists to allow JS to briefly show "completed!" animation before transitioning to `'done'` — `_get_and_update_onboarding_state` does the transition on next read
- **`action_validate_step`:** A `@api.model` class method accepting XML ID — used by apps to mark steps done programmatically from their setup code
- **`route_name` uniqueness:** Enforced at SQL level; used for URL routing in the onboarding controller
- **v17→v18:** `company_id` added to `onboarding.progress` and `onboarding.progress.step` for multi-company isolation; v18 significantly strengthened per-company support
