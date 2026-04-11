---
Module: website_jitsi
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_jitsi
---

## Overview

Jitsi video conferencing integration for website events. Provides the `chat.room` model and `chat.room.mixin` that enable Jitsi Meet rooms on event sponsors (online exhibitors), meeting rooms, and any model that includes the mixin. Rooms track participant counts, peak attendance, and last activity.

**Key Dependencies:** `website`

**Python Files:** 3 model files

---

## Models

### chat_room.py — ChatRoom

**Inheritance:** Base (standalone `_name = 'chat.room'`)

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `name` | Char | Yes | Required, copy=False, default = `odoo-room-{uuid[:8]}` |
| `is_full` | Boolean | No | Computed: True if `participant_count >= int(max_capacity)` |
| `jitsi_server_domain` | Char | No | From config param `website_jitsi.jitsi_server_domain`, default `'meet.jit.si'` |
| `lang_id` | Many2one | Yes | `res.lang`, default = current user's lang |
| `max_capacity` | Selection | Yes | `"4"`, `"8"`, `"12"`, `"16"`, `"20"`, `"no_limit"`, default `"8"` |
| `participant_count` | Integer | Yes | Current participants, default 0 |
| `last_activity` | Datetime | Yes | Last activity time, default `Datetime.now()` |
| `max_participant_reached` | Integer | Yes | Peak attendance |

**Compute Methods:**

| Method | Description |
|--------|-------------|
| `_compute_is_full()` | True unless `max_capacity == 'no_limit'` and count < limit |
| `_compute_jitsi_server_domain()` | Reads `website_jitsi.jitsi_server_domain` from `ir.config_parameter` |

---

### chat_room_mixin.py — ChatRoomMixin

**Inheritance:** Base abstract (`_name = 'chat.room.mixin'`)

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `chat_room_id` | Many2one | Yes | `chat.room`, readonly, ondelete=set null |
| `room_name` | Char | No | Related `chat_room_id.name` |
| `room_is_full` | Boolean | No | Related `chat_room_id.is_full` |
| `room_lang_id` | Many2one | No | Related `chat_room_id.lang_id` |
| `room_max_capacity` | Selection | No | Related `chat_room_id.max_capacity` |
| `room_participant_count` | Integer | No | Related `chat_room_id.participant_count` |
| `room_last_activity` | Datetime | No | Related `chat_room_id.last_activity` |
| `room_max_participant_reached` | Integer | No | Related `chat_room_id.max_participant_reached` |

**Mixin Fields Constant:**
- `ROOM_CONFIG_FIELDS`: `[('room_name','name'), ('room_lang_id','lang_id'), ('room_max_capacity','max_capacity'), ('room_participant_count','participant_count')]`

**Methods:**

| Method | Description |
|--------|-------------|
| `create(values_list)` | Auto-creates `chat.room` if any room config field is set and no `chat_room_id` exists |
| `write(values)` | Creates `chat.room` for records missing one, on room config field update |
| `copy_data(default)` | Copies chat room (with sanitized name) when record is duplicated |
| `unlink()` | Unlinks the associated `chat.room` before deleting the record |
| `_jitsi_sanitize_name(name)` | Replaces non-alphanumeric chars with `-`, lowercases, deduplicates |

---

## Security / Data

**Access Control (`ir.model.access.csv`):**
- `model_chat_room`: No access (blank — implies no direct access), User read-only, System full access

---

## Critical Notes

- `chat.room` is auto-created when any mixin record sets room config fields
- `_jitsi_sanitize_name` prevents duplicate room names by appending counters
- `room_participant_count` and `last_activity` are updated by the JS widget on the client side
- `max_participant_reached` tracks peak attendance across the room's lifetime
- `jitsi_server_domain` is shared across all rooms — configured once via `website_jitsi.jitsi_server_domain` config param
- The actual Jitsi Meet URL is built client-side from `room_name` + `jitsi_server_domain`
- Multiple models use this mixin: `event.sponsor` (online exhibitors), `event.meeting.room`
- v17→v18: No major changes to the room model structure
