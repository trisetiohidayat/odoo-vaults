---
Module: resource_mail
Version: 18.0
Type: addon
Tags: #resource_mail, #resource, #mail, #collaboration
---

# resource_mail — Resource Mail Integration

> Integrates mail/chat features into the `resource` module. Adds `im_status` (presence) tracking to `resource.resource` and provides avatar components for displaying resource records in the mail/chatter UI.

Auto-installs on top of `resource` and `mail`.

## Module Overview

| Property | Value |
|---|---|
| Category | Hidden |
| Version | 1.0 |
| Depends | `resource`, `mail` |
| Auto-install | Yes |
| License | LGPL-3 |

## What It Extends

- `resource.resource` — adds `im_status` field and avatar card data method
- Frontend: JavaScript components for `many2one_avatar_resource` and `many2many_avatar_resource` field widgets (similar to `many2one_avatar_partner`)

## Model: `resource.resource`

```python
class ResourceResource(models.Model):
    _inherit = 'resource.resource'
```

**Fields Added:**

| Field | Type | Description |
|---|---|---|
| `im_status` | Char (related) | Related to `user_id.im_status`. Reflects the linked user's mail presence: `online`, `away`, or `offline`. |

**Methods:**

- `get_avatar_card_data(fields)` → delegates to `_read_format(fields)`. Returns a dict of field values for the resource, used by the frontend avatar component to populate the popover/card view.

## Frontend Components

The module ships QWeb + JavaScript components for displaying resource records with avatars in mail-related views.

### `many2one_avatar_resource` Field Widget

Files:
- `static/src/views/fields/many2one_avatar_resource/many2one_avatar_resource_field.js`
- `static/src/views/fields/many2one_avatar_resource/many2one_avatar_resource_field.xml`
- `static/src/views/fields/many2one_avatar_resource/many2one_avatar_resource_field.scss`

A `Many2one` field widget that renders a clickable avatar chip (avatar image + name + presence dot) for `resource.resource` records, with a popover showing full card data.

### `many2many_avatar_resource` Field Widget

Files:
- `static/src/views/fields/many2many_avatar_resource/many2many_avatar_resource_field.js`
- `static/src/views/fields/many2many_avatar_resource/many2many_avatar_resource_field.xml`
- `static/src/views/fields/many2many_avatar_resource/many2many_avatar_resource_field.scss`

A `Many2many` variant of the above — displays multiple resource avatars with overflow count.

### `avatar_card_resource` Popover Component

File:
- `static/src/components/avatar_card_resource/avatar_card_resource_popover.js`
- `static/src/components/avatar_card_resource/avatar_card_resource_popover.xml`

Popover card shown when clicking a resource avatar. Calls `get_avatar_card_data()` to fetch record details.

## Tests

- `static/tests/many2one_avatar_resource.test.js` — QUnit test for the many2one avatar field
- `static/tests/many2many_avatar_resource.test.js` — QUnit test for the many2many avatar field
- `static/tests/resource_mail_test_helpers.js` — Test utility functions
- `static/tests/legacy/` — Legacy test fixtures

## Relationship to `resource`

This module bridges the gap between the pure-scheduling `resource.resource` model and the real-time collaboration layer of `mail`. Without it, resource records are invisible to the mail/chat presence system. With it, managers and employees see their colleagues' availability status alongside resource bookings in relevant chatter threads.

## See Also

- [Core/Fields](odoo-18/Core/Fields.md) — Many2one, Many2many, and related field types
- [Modules/Resource](odoo-18/Modules/resource.md) — Base resource/calendar module
- [Modules/Mail](odoo-18/Modules/mail.md) — Mail and chatter system
- [Modules/Mail Bot HR](Modules/Mail-Bot-HR.md) — `mail_bot_hr` for OdooBot presence in HR user forms
