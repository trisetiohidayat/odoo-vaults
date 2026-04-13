---
description: Guided user onboarding tours with pointer overlays, step sequencing, and auto-open triggers on first login.
tags:
  - odoo
  - odoo19
  - web
  - onboarding
  - user-experience
  - modules
---

# web_tour — Guided Onboarding Tours

## Module Overview

| Property | Value |
|----------|-------|
| **Technical Name** | `web_tour` |
| **Category** | Hidden |
| **Depends** | `web` |
| **Auto-install** | `True` |
| **License** | LGPL-3 |
| **Odoo Version** | 19.0 CE |

`web_tour` provides a framework for building guided onboarding tours inside the Odoo Web client. Tours consist of sequenced steps that highlight UI elements via a pointer overlay and display tooltips. The module integrates with the session-info endpoint so the web client can auto-start tours on first login for admin users who have not yet consumed them.

## Architecture

### Module Structure

```
web_tour/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── tour.py           # web_tour.tour + web_tour.tour.step
│   ├── ir_http.py        # Injects tour data into session_info
│   └── res_users.py      # Adds tour_enabled field on res.users
├── views/
│   └── tour_views.xml     # Form, list, search, action, menu, server action
├── security/
│   └── ir.model.access.csv
├── static/
│   ├── src/js/           # tour_service, tour_state, tour_pointer, recorder, interactive, automatic
│   ├── src/scss/
│   └── src/views/
│       └── *.xml          # QWeb templates
└── tests/
    └── test_tours.py
```

### Key Design Principles

1. **Tours are data, not code** — tour definitions (steps, triggers, URLs) live as database records in `web_tour.tour` and `web_tour.tour.step`, not as compiled JS files.
2. **JS registry pattern** — at runtime, Odoo's JS asset system generates a module registration in `registry.category("web_tour.tours")` from the DB records.
3. **Consumption tracking** — each internal user tracks which non-custom tours they have consumed via a `user_consumed_ids` M2m field.
4. **Admin-only auto-open** — `tour_enabled` on `res.users` is automatically `True` only for admin users, and only when no demo data is loaded.

---

## L1 — Tour Definition and Trigger Mechanism

### The Tour Model (`web_tour.tour`)

The central record type. Each record represents one guided tour.

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char (required) | Unique identifier for the tour. Used in JS registry. |
| `url` | Char | Starting URL for the tour. Default: `/odoo`. Can be a full path like `/odoo/web#action=...` |
| `step_ids` | One2many | Child `web_tour.tour.step` records, ordered by `sequence` |
| `sequence` | Integer | Controls the display order of tours in the list view and also the auto-start priority |
| `custom` | Boolean | `True` for tours created in the UI by administrators; `False` for "built-in" tours bundled as static JS |
| `rainbow_man_message` | Html | Completion message shown as a dismissible banner. Default: `<b>Good job!</b> You went through all steps of this tour.` |
| `sharing_url` | Char (computed) | A shareable URL `/{base}/odoo?tour={name}` that a user can open to replay the tour |
| `user_consumed_ids` | Many2many | `res.users` records that have completed this tour |

### The Tour Step Model (`web_tour.tour.step`)

Each step defines a single interaction within a tour.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `trigger` | Char (required) | — | CSS selector (e.g. `button`, `input.o_input`) that `hoot-dom` waits for before showing the tooltip |
| `content` | Char | — | Tooltip text displayed when the step is active |
| `tooltip_position` | Selection | `"bottom"` | Where the tooltip arrow points relative to the target element |
| `run` | Char | — | Action to execute automatically when the step activates. Common values: `click`, `edit <text>`, `wait 5000` |
| `sequence` | Integer | — | Order of this step within the tour |
| `tour_id` | Many2one | — | Parent tour; cascades delete on parent unlink |

### How Tours Are Triggered (Workflow)

```
User logs in
    ↓
ir_http.session_info() is called (via /web/session/info endpoint)
    ↓
Checks: user.tour_enabled == True AND user is internal
    ↓
search([("custom", "=", False), ("user_consumed_ids", "not in", uid)])
    ↓
Returns first unread non-custom tour as JSON to web client
    ↓
Web client (tour_service.js) starts that tour
    ↓
User completes steps → JS calls /web/tour/consume
    ↓
consume() adds user to user_consumed_ids
    ↓
get_current_tour() returns next unread tour or False
```

---

## L2 — Field Types, Defaults, Constraints

### `web_tour.tour` Field Inventory

| Field | Odoo Type | Stored | Default | Notes |
|-------|-----------|--------|---------|-------|
| `name` | Char | Yes | — | Required; unique via `_uniq_name` SQL constraint |
| `step_ids` | One2many | No | — | Virtual relation to `web_tour.tour.step` |
| `url` | Char | Yes | `/odoo` | Starting route for the tour |
| `sharing_url` | Char | No (compute) | — | `f"{base}/odoo?tour={name}"` |
| `rainbow_man_message` | Html | Yes | `<b>Good job!</b> ...` | `translate=True` |
| `sequence` | Integer | Yes | `1000` | Lower = higher priority |
| `custom` | Boolean | Yes | `False` | `True` for UI-created tours |
| `user_consumed_ids` | Many2many | Yes | — | Links to `res.users` |

### `web_tour.tour.step` Field Inventory

| Field | Odoo Type | Stored | Default | Notes |
|-------|-----------|--------|---------|-------|
| `trigger` | Char | Yes | — | Required; CSS selector string |
| `content` | Char | Yes | `False` (empty) | Tooltip text; omitted from JSON if empty |
| `tooltip_position` | Selection | Yes | `"bottom"` | Enum: bottom, top, right, left |
| `tour_id` | Many2one | Yes | — | Required; indexed; cascade delete |
| `run` | Char | Yes | — | Auto-action string |
| `sequence` | Integer | Yes | — | Step ordering |

### Constraints

**SQL Constraint on `web_tour.tour`:**
```python
_uniq_name = models.Constraint(
    'unique(name)',
    "A tour already exists with this name . Tour's name must be unique!",
)
```
Enforced at the PostgreSQL level — attempting to create a duplicate `name` raises a database-level violation error.

### Computed Fields

- `sharing_url` — `_compute_sharing_url`, depends on `name`. Reads `get_base_url()` at access time.
- `tour_json` (via `_get_tour_json`) — aggregates `name`, `url`, `custom`, `steps`, and `rainbowManMessage` into a dict for the JS side.

---

## L3 — Cross-Model Relationships, Override Patterns, Workflow Triggers, Failure Modes

### Cross-Model Relationships

`web_tour` touches **three other models** beyond its own:

| Related Model | Relationship | Direction | Purpose |
|---------------|-------------|-----------|---------|
| `res.users` | Many2many | ← `user_consumed_ids` on tour | Track which users have consumed each tour |
| `res.users` | `tour_enabled` field | → on user record | Gate auto-open behavior |
| `ir.http` | Method override | Extends `session_info()` | Inject `tour_enabled` and `current_tour` into web session |
| `ir.attachment` | Created by `export_js_file()` | tour → attachment | Export a tour as a static `.js` file |

### Override Patterns

**Pattern 1: Extending `ir.http.session_info()`**
```python
# models/ir_http.py
class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    def session_info(self):
        result = super().session_info()
        result["tour_enabled"] = self.env.user.tour_enabled
        result['current_tour'] = self.env["web_tour.tour"].get_current_tour()
        return result
```
This is a **prepend-override** (not using `super()` before or after convention explicitly, but the pattern is clear): the module injects two extra keys into the session payload returned to the web client.

**Pattern 2: Extending `res.users` with a writeable computed field**
```python
# models/res_users.py
class ResUsers(models.Model):
    _inherit = "res.users"

    tour_enabled = fields.Boolean(
        compute='_compute_tour_enabled',
        store=True,          # Stored! Default is store=False
        readonly=False,      # User-editable (not readonly)
    )
```
The compute stores its result (unlike most computed fields), making the value persist without needing to recompute on every access. The `readonly=False` allows an admin to toggle it manually.

### Workflow Trigger Mechanism

| Trigger | Mechanism | Where |
|---------|-----------|-------|
| **Auto-open on login** | `session_info()` → `get_current_tour()` | Server-side, on every authenticated page load |
| **Step progression** | `consume()` called by JS on step completion | Client-side calls `/web/tour/consume` |
| **Manual start** | "Start tour" button (widget) calls `get_tour_json_by_name()` | Client-side tour_service.js |
| **Sharing link** | URL param `?tour={name}` loaded by tour_state.js on page load | Client-side bootstrap |
| **Reset for admin** | `switch_tour_enabled(True)` via JS RPC | Client-side toggle |

### `failure_mode` and Error Handling

The module does **not** have a `failure_mode` field or explicit failure handling configuration. However, the JS tour engine (`hoot-dom`) provides behavior when a step's trigger is not found:

- The step waits indefinitely (or respects a `wait Xms` run command)
- Console error is logged if trigger selector resolves to zero elements
- Tour state is stored client-side and survives page refresh via `tour_state.js`

### `override_pattern`

There is **no generic override pattern field**. Custom tours can be created in the UI (setting `custom=True`) or by subclassing `web_tour.tour` in Python and defining steps there. The static JS asset system also allows bundling tours as JS modules via the `registry.category("web_tour.tours").add(...)` pattern.

---

## L4 — Performance, Odoo 18/19 Changes, Security, Auto-Open Mechanism

### Performance Considerations

| Area | Analysis |
|------|----------|
| **DB reads on every login** | `session_info()` calls `get_current_tour()` which executes `self.search([...])` on every page load for authenticated users. This is one `search()` + one `read()` per session, which is cheap but not free. |
| **Stored computed on `res.users`** | `tour_enabled` is `store=True`, so after initial computation it becomes a regular column read — no recompute cost on subsequent logins. |
| **One2many step loading** | `step_ids.get_steps_json()` reads all step fields for all steps of a tour. For tours with many steps (20+), this could add latency to the session_info response. The `get_current_tour()` only returns one tour at a time, bounding the cost. |
| **No N+1 in test code** | The test code correctly uses `.read()` with explicit field lists when building the tour JSON, avoiding loading unrelated fields. |
| **Asset bundles** | Tours load via separate `web_tour.automatic` and `web_tour.interactive` bundles. These are lazy-loaded only when a tour is active, not on every page. |

### Odoo 18 → 19 Changes for `web_tour`

Based on source analysis, `web_tour` in Odoo 19 includes:

| Change | Detail |
|--------|--------|
| **Test tag normalization** | Tests use `@tagged('post_install', '-at_install')` — the Odoo 16-era `at_install` tag is explicitly excluded; only `post_install` runs, matching Odoo 17+ test runner behavior. |
| **`tour_enabled` store pattern** | The stored, writable computed field pattern was introduced to avoid recomputing on every page load. |
| **JS registry pattern** | Uses `@web/core/registry` for tour registration (Odoo 17+ Web Framework). |
| **`web_tour.automatic` bundle** | The automatic/onboarding tour bundle was separated from the interactive recorder bundle. |
| **No `pointer_option` field** | The module has no `pointer_option` field in Odoo 19. The pointer is controlled entirely by the JS tour engine. |
| **`failure_mode` absent** | No `failure_mode` field exists. |
| **`override_pattern` absent** | No `override_pattern` field. |

### Security Model

| Aspect | Implementation |
|--------|----------------|
| **ACL on `web_tour.tour`** | All access in `ir.model.access.csv` — `base.group_user` gets full CRUD, `base.group_public` gets none. The form view has `create="0"` (no UI creation) but ACL still allows `create()` via Python. |
| **Internal user only** | `get_current_tour()` checks `user._is_internal()` before returning a tour — portal/public users are excluded. |
| **`custom=True` tours** | Custom tours are excluded from auto-open (only `custom=False` tours are returned by `get_current_tour()`). This prevents user-created tours from automatically launching. |
| **Sharing URL** | The sharing URL (`/odoo?tour=name`) is a GET parameter — anyone with the link could replay a tour, but no write access is granted via the URL. |
| **`sudo()` in `consume()`** | `tour_id.sudo().user_consumed_ids = [Command.link(uid)]` uses `sudo()` to ensure the link operation succeeds even if the current user lacks direct write access on the `user_consumed_ids` field (possible due to field group restrictions). |

### Auto-Open Mechanism (Deep Dive)

```
Startup condition check (in _compute_tour_enabled):
    demo_modules_count == 0
    AND user._is_admin()
    AND NOT modules.module.current_test

If all TRUE → tour_enabled = True (stored)
```

This means:
- **Demo data loaded** (e.g. in a test/demo database): tours are suppressed
- **Non-admin users**: `tour_enabled` stays `False` even if manually set (the compute recalculates on every write and overwrites the value)
- **`current_test` active**: tours suppressed to prevent interference with automated tests

The `switch_tour_enabled(val)` model method provides a server-side toggle:
```python
@api.model
def switch_tour_enabled(self, val):
    self.env.user.sudo().tour_enabled = val
    return self.env.user.tour_enabled
```
This is called from a JS RPC from the onboarding UI widget. The `sudo()` ensures it works regardless of field group restrictions.

### Export JS File Feature

The server action `tour_export_js_action` serializes a tour's definition into a static `.js` module:
```python
registry.category("web_tour.tours").add("{name}", {
    url: "{url}",
    steps: () => [ ... steps JSON ... ]
})
```
This bridges the gap between data-defined tours and the JS module registry — a tour can be exported, committed as a static file, and loaded as a bundled tour (with `custom=False`) on another system.

---

## Related Models

| Model | Module | Relationship |
|-------|--------|--------------|
| `res.users` | `base` | Holds `tour_enabled` field; source of user identity for consumption tracking |
| `ir.http` | `base` | Extended to inject tour state into web client session |
| `ir.attachment` | `base` | Created by `export_js_file()` to store exported `.js` content |
| `event.track` | `website_event_track` | Uses `web_tour` internally for its own onboarding tour |

## See Also

- [Modules/web](Modules/web.md) — Web client architecture
- [Modules/website_event_track](Modules/website_event_track.md) — Event track module (uses web_tour for onboarding)
- [Core/API](Core/API.md) — @api.depends, computed fields, stored computed patterns
- [Patterns/Inheritance Patterns](odoo-18/Patterns/Inheritance Patterns.md) — Classical _inherit patterns used in web_tour
