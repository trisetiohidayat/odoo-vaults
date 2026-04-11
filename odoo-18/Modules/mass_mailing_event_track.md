---
Module: mass_mailing_event_track
Version: 18.0.0
Type: addon
Tags: #odoo18 #mass_mailing #event #website
---

## Overview

Adds mass mailing capabilities for event track speakers to `event.event`. Introduces the action `action_mass_mailing_track_speakers` that opens a mailing wizard scoped to tracks linked to the current event.

**Depends:** `mass_mailing`, `event`, `website_event_track`

**Key Behavior:** The action targets `event.track` model filtered by event and active stage.

---

## Models

### `event.event` (Inherited)

**Inherited from:** `event.event`

| Method | Returns | Note |
|--------|---------|------|
| `action_mass_mailing_track_speakers()` | `ir.actions.act_window` | Opens `mailing.mailing` form targeting tracks by `event_id`, excluding cancelled |

**Context defaults set:**
- `default_mailing_model_id` → `event.track`
- `default_mailing_domain` → `[('event_id', 'in', self.ids), ('stage_id.is_cancel', '!=', True)]`
- `default_subject` → `"Event: %s" % self.name`

### `event.track` (Inherited)

**Inherited from:** `event.track`

| Field | Type | Note |
|-------|------|------|
| `_mailing_enabled` | Class attr | Marker enabling mailing on track model |

| Method | Returns | Note |
|--------|---------|------|
| `_mailing_get_default_domain(mailing)` | Domain list | Returns `[('stage_id.is_cancel', '=', False)]` |
