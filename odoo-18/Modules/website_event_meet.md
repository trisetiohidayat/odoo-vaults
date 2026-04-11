---
Module: website_event_meet
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_event_meet
---

## Overview

Adds meeting room functionality to event websites. Attendees can create and join video meeting rooms (powered by Jitsi via `chat.room.mixin`) directly from the event page. Supports room pinning, capacity limits, auto-archiving of inactive rooms, and per-event room creation permissions.

**Key Dependencies:** `website_event`, `website_jitsi`

**Python Files:** 4 model files

---

## Models

### event_meeting_room.py — EventMeetingRoom

**Inheritance:** `chat.room.mixin`, `website.published.mixin`

**Model:** `_name = 'event.meeting.room'`, `_order = 'is_pinned DESC, id'`

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `name` | Char | Yes | Room topic, required, translated |
| `active` | Boolean | Yes | Default True |
| `is_published` | Boolean | Yes | Inherited from mixin, made copyable |
| `event_id` | Many2one | Yes | `event.event`, required, cascade delete |
| `is_pinned` | Boolean | Yes | Pinned rooms are not auto-archived |
| `chat_room_id` | Many2one | Yes | `chat.room`, required, ondelete=restrict |
| `room_max_capacity` | Selection | Yes | Default `"8"`, inherited from mixin |
| `summary` | Char | Yes | Short room description, translated |
| `target_audience` | Char | Yes | Target audience description, translated |
| `room_name` | Char | No | Related from `chat_room_id` (from mixin) |
| `room_is_full` | Boolean | No | Related from mixin |
| `room_lang_id` | Many2one | No | Related from mixin |
| `room_participant_count` | Integer | No | Related from mixin |
| `room_last_activity` | Datetime | No | Related from mixin |
| `room_max_participant_reached` | Integer | No | Related from mixin |
| `website_url` | Char | No | Computed URL `/event/{slug}/meeting_room/{slug}` |

**Constants:**
- `_DELAY_CLEAN`: `datetime.timedelta(hours=4)` — inactivity threshold before auto-archive

**Methods:**

| Method | Decorator | Description |
|--------|-----------|-------------|
| `_compute_website_url()` | `@api.depends('name', 'event_id.name')` | Returns event meeting room URL |
| `create(values_list)` | `@api.model_create_multi` | Auto-sets `room_name = 'odoo-room-{name}'` if not provided |
| `_archive_meeting_rooms()` | `@api.autovacuum` | Archives non-pinned rooms with 0 participants and no activity for >4 hours |
| `open_website_url()` | — | Returns website client action URL; uses relative URL when no `event_id.website_id` |

---

### event_event.py — Event

**Inheritance:** `event.event`

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `meeting_room_ids` | One2many | Yes | `event.meeting.room` records |
| `meeting_room_count` | Integer | No | Count of rooms |
| `meeting_room_allow_creation` | Boolean | Yes | Allow attendees to create rooms; computed from type/community_menu |

**Methods:**
- `_compute_community_menu()`: Syncs from event_type or activates with website_menu
- `_compute_meeting_room_count()`: Uses `_read_group` to aggregate room counts
- `_compute_meeting_room_allow_creation()`: Propagates from type; activates when community_menu toggled on

---

### event_type.py — EventType

**Inheritance:** `event.type`

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `meeting_room_allow_creation` | Boolean | Yes | Computed from `community_menu` |

---

### website_event_menu.py — EventMenu

**Inheritance:** `website.event.menu`

| Field | Type | Notes |
|-------|------|-------|
| `menu_type` | Selection | Adds `'meeting_room'` to selection, ondelete cascade |

---

## Security / Data

No dedicated security XML files in this module.

---

## Critical Notes

- Rooms auto-generate `room_name = 'odoo-room-{name}'` if not explicitly provided
- `@api.autovacuum` method `_archive_meeting_rooms` runs via the autovacuum cron and only archives rooms that are: not pinned, active, have 0 participants, and inactive for >4 hours
- `is_pinned` rooms are excluded from auto-archiving
- The `_compute_website_url()` extends the parent method to generate event-specific room URLs
- `open_website_url()` returns a relative URL via `website.get_client_action()` when the event has no specific website (multi-website support)
- v17→v18: `meeting_room_allow_creation` now propagates from event type and is tied to `community_menu` rather than a separate field
