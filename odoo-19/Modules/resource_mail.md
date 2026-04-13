---
uuid: resource_mail-001
tags:
  - odoo
  - odoo19
  - modules
  - resource
  - calendar
  - mail
created: 2026-04-11
---

# resource_mail

> Integrate Mail features with resource scheduling. Adds avatar data and IM status to resource resources for use in calendar/event views.

**Module**: `resource_mail` | **Path**: `odoo/addons/resource_mail/` | **Version**: 1.0
**Category**: Hidden | **Depends**: `resource`, `mail` | **Auto-install**: True | **License**: LGPL-3

---

## Overview

The `resource_mail` module bridges the gap between Odoo's resource/calendar infrastructure and its messaging system. Since resource resources (meeting rooms, equipment) are stored in `resource.resource` rather than `res.users`, they lack the IM status and avatar display that calendar views rely on for user presence indicators. This module adds those missing fields, enabling resource records to display avatar cards with color and online/offline status inside the calendar/scheduling UI.

---

## Architecture

```
resource_mail
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   └── resource_resource.py    # Extends resource.resource
├── static/
│   ├── src/
│   └── tests/
└── i18n/
```

---

## L1: Core Functionality — How Resource Booking Integrates with Mail

The `resource_mail` module solves a specific problem: calendar views (specifically the avatar card widget used in resource scheduling) need presence data (color, IM status) that only exists on `res.users`, but resources live in `resource.resource`. Without this module, a resource-booking calendar would render a blank/uncolored avatar for any resource, regardless of whether that resource is linked to a user.

The module's entire implementation is this Python file (`models/resource_resource.py`, 18 lines total):

```python
from random import randint
from odoo import fields, models

class ResourceResource(models.Model):
    _inherit = 'resource.resource'

    def _default_color(self):
        return randint(1, 11)

    color = fields.Integer(default=_default_color)
    im_status = fields.Char(related='user_id.im_status')

    def get_avatar_card_data(self, fields):
        return self.read(fields)
```

**How it works end-to-end:**

1. A `resource.resource` record is created (e.g., a meeting room "Conference Room A").
2. The `_default_color` method assigns a random integer 1–11 as the `color` field.
3. If the resource has a `user_id` (e.g., an employee who manages the room), `im_status` mirrors `user_id.im_status`.
4. The front-end avatar card widget calls `get_avatar_card_data(['name', 'color', 'im_status'])` via RPC.
5. The result populates the resource's avatar card in the calendar scheduling UI.

**Why `resource.resource` needs this glue module:**

| Aspect | `res.users` | `resource.resource` |
|--------|--------------|---------------------|
| Avatar image | `avatar_128` computed from `user_id.avatar_128` | None |
| Background color | Randomly assigned at user creation | None until `resource_mail` |
| IM status | Stored on user record | None until `resource_mail` |
| Calendar presence indicator | Read from `im_status` | Mirrors `user_id.im_status` via `resource_mail` |

---

## L2: Field Types, Defaults, Constraints

### `color` — Integer

| Property | Value |
|----------|-------|
| Type | `Integer` (database `INTEGER`) |
| Default | `_default_color()` → `randint(1, 11)` |
| Stored | Yes (database column) |
| Indexed | No |
| Required | No |

**Constraint:** No SQL constraint. The field is optional — a resource can be created without a color (it would get `NULL`), and the avatar widget would fall back to a default color. The random assignment only happens at create if no value is passed.

**Creation behavior:**
```python
# When color is NOT explicitly passed in vals:
self.env['resource.resource'].create({'name': 'Room A'})  # color gets randint(1,11)

# When color IS explicitly passed:
self.env['resource.resource'].create({'name': 'Room B', 'color': 5})  # color = 5
```

The `_default_color` method is defined as a bound method, not a lambda or separate function, so it is callable as a default callable. Odoo's ORM recognizes `default=_default_color` as a method reference and calls it with `(self, cr, user, context)` during record creation.

### `im_status` — Char (related, readonly)

| Property | Value |
|----------|-------|
| Type | `Char` (not `Selection`) |
| Related | `user_id.im_status` |
| Storage | Not stored — computed on access |
| Readonly | Implicit (related fields are readonly by default) |
| Value when `user_id` is unset | Empty string `''` |
| Value when `user_id` is set | Whatever `res.users.im_status` stores (typically: `'online'`, `'offline'`, `'away'`) |

**Why Char not Selection:** `res.users.im_status` is a `Char` field (not `Selection`), so this related field must also be `Char`. The `im_status` on `res.users` is managed by the `bus.bus` presence system and updated by the longpolling mechanism.

### `get_avatar_card_data(fields)` — Method

| Property | Value |
|----------|-------|
| Decorator | None (plain method) |
| Parameter | `fields` — list of field names (e.g., `['name', 'color', 'im_status']`) |
| Return | `recordset.read(fields)` — list of dicts |
| Access rights | Respects current user's ACL (no `sudo()`) |
| Multi-record | Returns a list; called on a single record via `self.ensure_one()` implicitly |

```python
def get_avatar_card_data(self, fields):
    return self.read(fields)
```

This is equivalent to `self.sudo(False).read(fields)` with the current user's access rights. It does NOT bypass ACL — if the current user cannot read certain fields on `resource.resource`, those fields are silently omitted from the returned dict (standard Odoo behavior for `read()`).

---

## L3: Cross-Model, Override Patterns, Workflow Triggers

### Cross-Model Relationships

```
res.users
    └── im_status (Char)          ← source of im_status
    └── avatar_128 (Image)         ← source of resource.avatar_128 in resource module
    └── resource_ids (One2many)   ← inverse of resource.resource.user_id

resource.resource (base)
    ├── user_id (Many2one)
    ├── avatar_128 (Image, computed from user_id.avatar_128)
    └── calendar_id (Many2one → resource.calendar)

resource.resource (resource_mail extended)
    ├── color (Integer)           ← NEW: random color for avatar
    └── im_status (Char, related) ← NEW: mirrors user_id.im_status

calendar.event / calendar.event (resource extension)
    └── resource_ids (Many2many)   ← linked resources for a meeting
         └── Each resource displays avatar via get_avatar_card_data()
```

**Cross-model call chain:**
```
Calendar View (JS widget)
    → RPC: model.exec_kw('resource.resource', 'get_avatar_card_data', [id], ['name','color','im_status'])
    → self.read(['name', 'color', 'im_status'])
    → self.color            → database column
    → self.im_status        → self.user_id.im_status (delegated to res.users)
    → self.name             → database column
    → Returns dict to front-end
    → Widget renders colored avatar + presence dot
```

### Override Pattern

`resource_mail` uses **classical single-inheritance** (`_inherit = 'resource.resource'`). This means it adds fields and methods to the existing `resource.resource` model without creating a new model. All other modules that extend `resource.resource` (including the base `resource` module itself) share the same table (`resource_resource`).

**Method extension:** `get_avatar_card_data` is a new method on the model (not an override of an existing method). No parent `super()` call is needed. This is a pure addition.

**Field extension:** `color` and `im_status` are new fields appended to the existing `resource.resource` table. They do not override any existing fields.

### Workflow Triggers

This module has no button actions, state machines, or workflow triggers. It is purely a data-enrichment layer. The fields it adds are consumed by:

1. **Front-end avatar card widget** — reads `color`, `im_status`, `name` via `get_avatar_card_data()`
2. **Calendar scheduling view** — uses avatar card to display resource presence in meeting room bookings

### Version History: Odoo 18 → Odoo 19

**No behavioral changes** between Odoo 18 and Odoo 19 for `resource_mail`. The module's implementation has remained stable:

- The `_default_color` random integer approach is identical.
- The `im_status` related field mechanism is identical.
- The `get_avatar_card_data` RPC method is unchanged.
- The `auto_install: True` behavior is unchanged.

The module was introduced in Odoo 16 as a glue module between `resource` and `mail`. In Odoo 18 and 19, it has remained structurally identical with only version string updates in the manifest (`1.0`).

**What changed in Odoo 19 core `resource` module** (affects how `resource_mail` works):
- Odoo 19 introduced `_is_fully_flexible()` and `_is_flexible()` methods on `resource.resource` for distinguishing fully flexible resources (no calendar) from flexible-calendar resources.
- These methods are unrelated to `resource_mail` — the avatar card logic does not depend on resource flexibility status.

---

## L4: Deep Analysis — Design Rationale and Security

### Why `get_avatar_card_data` Is Just a `read()` Wrapper

The method could have been implemented as:
```python
def get_avatar_card_data(self, fields):
    return {
        'name': self.name,
        'color': self.color,
        'im_status': self.user_id.im_status if self.user_id else False,
    }
```

Instead it uses `self.read(fields)`. The `read()` approach is superior because:
1. It respects field-level access control (ACL) — if a user cannot read `user_id`, `im_status` is silently excluded.
2. It automatically handles computed/related fields in the same way as stored fields.
3. It is generic — any field name passed in `fields` is returned if readable.
4. It defers to the ORM's standard read pipeline, ensuring consistency with the rest of Odoo's data access patterns.

### Why Not Store `im_status`?

`im_status` is intentionally not stored (`related` fields are never stored unless `store=True` is explicitly set, which is not done here). Storing it would create a sync problem: `res.users.im_status` changes dynamically via the longpolling bus mechanism, potentially several times per minute. A stored column would become stale immediately after being written.

Making it a computed field with `depends` would require depending on `user_id.im_status`, which is itself a computed/updated field. The related field approach is the correct pattern — Odoo resolves the value at read time directly from the `res.users` record.

### Why Random Color, Not User Color?

A resource's `color` is randomly assigned at creation, not derived from the linked `user_id.color`. This is intentional: a resource is an independent entity. A meeting room's avatar color should be stable (always the same room has the same color) but independent from the managing user's avatar color. If the managing user changes, the resource's color should not change.

The random assignment ensures that even two resources managed by the same user get different colors, making them visually distinguishable in the calendar.

### Security Model

| Aspect | Analysis |
|--------|----------|
| **ACL** | Standard `resource.resource` ACL applies. Any user who can read a resource can read `color` and `im_status`. No elevated `sudo()` in this module. |
| **Field access** | `read()` respects field-level ACL. If a group restricts access to `user_id`, the front-end receives `im_status: False` without error. |
| **Public access** | The `get_avatar_card_data` method is not exposed as a controller route — it is called via the ORM's RPC mechanism (typically through the web client), which already enforces authentication. |
| **Data leakage** | None. Only two fields are added. `color` is not sensitive. `im_status` reveals whether a user is online/offline, which is a low-severity disclosure (similar to "last seen" in messaging apps). |
| **Injection** | Not possible — `read()` only returns existing field values. The method accepts no SQL or domain input. |

### Dependency Graph

```
resource_mail (this module)
    ├── dependency: resource
    │       └── dependency: base, web
    │              resource.resource model
    │              resource.calendar model
    │              resource.mixin (abstract)
    │              resource.calendar.attendance
    │              resource.calendar.leaves
    │
    └── dependency: mail
            └── dependency: base, bus
                   res.users model (im_status source)
                   bus.bus (presence/longpolling)
```

### Asset Loading and Front-End Contract

The manifest registers:
```python
'assets': {
    'web.assets_backend': ['resource_mail/static/src/**/*'],
}
```

The front-end expects:
- A `color` integer (1–11) for the avatar background
- An `im_status` string (`'online'`, `'offline'`, `'away'`, or `''`)
- A `name` string for the avatar label
- The `get_avatar_card_data(fields)` RPC method to supply these

The JS assets in `static/src/` implement the avatar card widget that calls this method. The contract is: pass a list of fields, get back a dict with those field values.

### Extension Points for Custom Implementations

If a developer wants to override the avatar card behavior:
1. **Override `get_avatar_card_data`** to return custom data or filter fields:
   ```python
   def get_avatar_card_data(self, fields):
       # Remove sensitive fields for portal users
       if self.env.user.share:
           fields = [f for f in fields if f not in ('im_status',)]
       return super().get_avatar_card_data(fields)
   ```
2. **Override `_default_color`** to assign colors by category or company policy:
   ```python
   def _default_color(self):
       # Assign colors based on resource type
       if self.resource_type == 'material':
           return randint(1, 5)  # muted palette for equipment
       return randint(6, 11)      # bright palette for human resources
   ```

---

## Related Models

- `resource.resource` — Core resource model (extended)
- `res.users` — Source of IM status via `user_id` link; source of avatar_128 for `resource.resource.avatar_128`
- `calendar.event` — Events that book resources via `resource_ids`
- `mail.thread` — Messaging mixin used by resource models for chatter
- `bus.bus` — Presence/longpolling system that updates `res.users.im_status`

---

## Related Documentation

- [Modules/Resource](Modules/Resource.md) — Core resource scheduling: calendars, attendances, leaves, flexible hours
- [Modules/Mail](Modules/Mail.md) — Messaging: IM status, presence, bus longpolling
- [Modules/Calendar](Modules/Calendar.md) — Calendar/event booking that consumes resource avatars

---

## Notes

- The module is intentionally minimal — 18 lines of Python. It serves as a thin integration layer.
- The `get_avatar_card_data()` method does not implement access control filtering — it relies on Odoo's standard `read()` behavior.
- The `im_status` field is `Char` (not `Selection`) because it mirrors `res.users.im_status`, which is stored as `Char`.
- No SQL constraints, no `@api.constrains`, no `@api.onchange`, no computed fields — only one stored field (`color`), one related field (`im_status`), and one RPC method.
