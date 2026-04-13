---
Module: web_tour
Version: 18.0
Type: addon
Tags: #web, #tour, #onboarding, #guide, #walkthrough
---

# web_tour — Interactive Onboarding Tours

## Module Overview

**Category:** Hidden
**Depends:** `web`
**License:** LGPL-3
**Installable:** True

Provides the Odoo interactive tour/guided walkthrough system. Tours guide users through UI steps with highlighted elements, tooltips, and automatic clicking. Tours are defined as `web_tour.tour` records with `web_tour.tour.step` children, and can be exported as JavaScript files or consumed dynamically.

## Data Files

- `data/tour_data.xml` — Default tour definitions (usually empty, tours are added by other modules)

## Static Assets (web.assets_backend)

- `web_tour/static/src/js/tour_interactive.js` — Interactive tour manager (OWL component)
- `web_tour/static/src/js/tour_interactive.tour_utils.js` — Tour utilities
- `web_tour/static/src/js/tour_interactive.anchor_utils.js` — Anchor/selector utilities
- `web_tour/static/src/js/tour_pointer.js` — Tour pointer/highlight overlay
- `web_tour/static/src/scss/tour_interactive.scss` — Tour UI styles
- `web_tour/static/tests/**/*` — QUnit tests

## Models

### `web_tour.tour` (`web_tour.models.tour`)

**Inheritance:** `base` (no `_name` override — this IS the model)

**Fields:**

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `name` | Char | Yes | Unique tour identifier (SQL constraint) |
| `step_ids` | One2many `web_tour.tour.step` | Yes | Child steps; `cascade` delete |
| `url` | Char | Yes | Starting URL for the tour (default `'/odoo'`) |
| `sharing_url` | Char | Yes | Computed URL with `?tour=<name>` param appended |
| `rainbow_man_message` | Html | Yes | Completion message (default `'<b>Good job!</b>'`) |
| `sequence` | Integer | Yes | Tour priority order (default 1000) |
| `custom` | Boolean | Yes | If True, excluded from auto-run |
| `user_consumed_ids` | Many2many `res.users` | Yes | Tracks which users have completed the tour |

**Methods:**

**`_compute_sharing_url()`** `@api.depends('name')`
Returns `{base_url}/odoo?tour={name}`. The `base_url` is fetched from `web.base.url`.

**`consume(tour_name)`** `@api.model`
Marks the current user as having consumed the named tour by adding them to `user_consumed_ids`. Called from JS on tour completion.

**`get_current_tour()`** `@api.model`
Returns tour JSON for the first non-consumed, non-custom tour applicable to the current user (or all users if no specific user context). Called on page load to check if any tours should auto-start.

**`get_tour_json_by_name(tour_name)`** `@api.model`
Looks up a tour by `name`, returns `_get_tour_json()` dict, or raises `UserError` if not found.

**`_get_tour_json()`** `@api.depends('step_ids')`
Returns a dict with:
- `name`: tour name
- `url`: starting URL
- `custom`: custom flag
- `steps`: list from `step_ids.get_steps_json()`
- `rainbowManMessage`: HTML completion message

**`export_js_file()`**
Creates an `ir.attachment` record containing an ES module JS file that registers the tour via `tourService.addFromDefinition()`. Used for exporting tours from database records to static JS files.

---

### `web_tour.tour.step` (`web_tour.models.tour`)

**Inheritance:** `base` (standalone model)

**Fields:**

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `tour_id` | Many2one `web_tour.tour` | Yes | Parent tour; `ondelete='cascade'` |
| `trigger` | Char | Yes | CSS selector for the element to highlight |
| `content` | Char | Yes | Tooltip text shown on the step |
| `run` | Char | Yes | JS expression to auto-execute when step triggers (e.g., `"click"`, `"edit"`) |
| `sequence` | Integer | Yes | Step order within the tour (default 0) |

**Methods:**

**`get_steps_json()`**
Returns a list of step dicts (one entry per record): `{id, trigger, content, run}`.

---

### `res.users` (`web_tour.models.res_users`)

**Inheritance:** `res.users`

**Methods:**

**`_check_tour_consumed()`**
Called on user record change. For each completed tour in `tour_ids`, ensures the user is in that tour's `user_consumed_ids`. Used to sync tour state when user assignments change.

---

### `ir.http` (`web_tour.models.ir_http`)

**Inheritance:** `ir.http`

**Methods:**

**`_get_translation_frontend_modules_name()`**
Adds `'web_tour'` to the list of modules for frontend translation extraction.

---

## Tour JSON Format

```json
{
  "name": "my_tour",
  "url": "/odoo",
  "custom": false,
  "steps": [
    {"id": 1, "trigger": ".o_form_button_edit", "content": "Click Edit", "run": "click"},
    {"id": 2, "trigger": "input[name=name]", "content": "Enter name", "run": "edit"}
  ],
  "rainbowManMessage": "<b>Good job!</b>"
}
```

## Tour Execution (Frontend JS)

- Tours are registered via the tour service from either static JS files or database records via `get_current_tour()`
- `consume(tourName)` RPC call is made after the user completes all steps
- `rainbow_man_message` is shown in a Rainbow Man notification on completion
- Sharing URL (`?tour=<name>`) allows launching a specific tour directly
- The `run` attribute JS expression is evaluated in the browser:
  - `"click"` — auto-click the trigger element
  - `"edit"` — enter edit mode on the trigger element
  - Any other JS expression is evaluated directly

## What It Extends

- `res.users` — tour consumption tracking
- `ir.http` — translation module registration

---

## Key Behavior

- Tours can be defined either as database records (`web_tour.tour`) or as static JS files using `tourService.addFromDefinition()`.
- `export_js_file()` bridges the gap: it converts a database tour into an `ir.attachment` ES module JS file.
- A tour's `url` determines which page it activates on. Tours are started automatically when the browser navigates to their URL (unless `custom=True`).
- The `sharing_url` feature allows administrators to share a direct link (`/odoo?tour=tour_name`) that launches a specific tour when opened.
- `user_consumed_ids` is a Many2many to `res.users` — a user who has completed a tour will not be shown that tour again.
- The `trigger` selector supports CSS selectors with Odoo's element matching (e.g., `.o_form_button_edit`, `[name='field_name']`).
- Steps are shown as tooltips anchored to the trigger element; the pointer/highlight overlay draws attention to the element.
- v17 to v18: No significant architectural changes.

---

## See Also

- [Modules/onboarding](odoo-18/Modules/onboarding.md) — Step-based setup checklists (server-side)
- [Modules/html_editor](odoo-18/Modules/html_editor.md) — Rich text editor
- [Modules/web_hierarchy](odoo-18/Modules/web_hierarchy.md) — Hierarchy view
