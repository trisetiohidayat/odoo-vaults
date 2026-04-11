---
Module: website_event_exhibitor
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_event_exhibitor
---

## Overview

Enables exhibitor pages on event websites. Adds sponsor/exhibitor management to events with rich profiles, contact info, images, and opening hours. Integrates with `website_jitsi` (chat room mixin) for online exhibitor meeting rooms.

**Key Dependencies:** `website_event`, `event_sale`, `website_jitsi`

**Python Files:** 5 model files

---

## Models

### event_sponsor_type.py — EventSponsorType

**Inheritance:** `BaseModel` (standalone — `_name = 'event.sponsor.type'`)

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `name` | Char | Yes | Sponsor level name (e.g., Gold, Silver) |
| `sequence` | Integer | Yes | Display order; default computed as max+1 |
| `display_ribbon_style` | Selection | Yes | `'no_ribbon'`, `'Gold'`, `'Silver'`, `'Bronze'` |

**Methods:**

| Method | Description |
|--------|-------------|
| `_default_sequence()` | Returns `(max existing sequence) + 1` as default |

---

### event_sponsor.py — EventSponsor

**Inheritance:** `mail.thread`, `mail.activity.mixin`, `website.seo.metadata`, `website.published.mixin`, `chat.room.mixin`

**Model:** `_name = 'event.sponsor'`, `_order = 'sequence, sponsor_type_id'`

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `event_id` | Many2one | Yes | `event.event`, required, auto_join |
| `sponsor_type_id` | Many2one | Yes | `event.sponsor.type`, required, default = highest sequence type |
| `url` | Char | Yes | Website URL, computed from partner, readonly=False |
| `sequence` | Integer | Yes | Sort order |
| `active` | Boolean | Yes | Default True |
| `subtitle` | Char | Yes | Slogan |
| `exhibitor_type` | Selection | Yes | `'sponsor'` (footer logo), `'exhibitor'` (full page), `'online'` (with chat room) |
| `website_description` | Html | Yes | Translated, sanitize_form=True |
| `partner_id` | Many2one | Yes | `res.partner`, required, auto_join |
| `partner_name` | Char | Yes | Related `partner_id.name` |
| `partner_email` | Char | Yes | Related `partner_id.email` |
| `partner_phone` | Char | Yes | Related `partner_id.phone` |
| `partner_mobile` | Char | Yes | Related `partner_id.mobile` |
| `name` | Char | Yes | Sponsor name, computed from partner, writable |
| `email` | Char | Yes | Sponsor email, computed from partner, writable |
| `phone` | Char | Yes | Sponsor phone, computed from partner, writable |
| `mobile` | Char | Yes | Sponsor mobile, computed from partner, writable |
| `image_512` | Image | Yes | Logo, computed from partner, writable |
| `image_256` | Image | Yes | Related `image_512`, max 256px |
| `image_128` | Image | Yes | Related `image_512`, max 128px |
| `website_image_url` | Char | No | Computed URL for template rendering |
| `hour_from` | Float | Yes | Opening hour (default 8.0) |
| `hour_to` | Float | Yes | Closing hour (default 18.0) |
| `event_date_tz` | Selection | No | Related `event_id.date_tz` |
| `is_in_opening_hours` | Boolean | No | True if current time is within sponsor's hours |
| `chat_room_id` | Many2one | Yes | Inherited from `chat.room.mixin` |
| `room_name` | Char | Yes | Inherited from mixin, readonly=False |
| `country_id` | Many2one | No | Related `partner_id.country_id` |
| `country_flag_url` | Char | No | Computed flag URL |

**Compute Methods (all `@api.depends('partner_id')`):**

| Method | Description |
|--------|-------------|
| `_compute_url()` | Sets url from partner.website if no explicit url |
| `_compute_name()` | Synchronizes name from partner |
| `_compute_email()` | Synchronizes email from partner |
| `_compute_phone()` | Synchronizes phone from partner |
| `_compute_mobile()` | Synchronizes mobile from partner |
| `_compute_image_512()` | Synchronizes image from partner |
| `_compute_website_image_url()` | Returns URL for templates: uses stored image, partner image, or default SVG |
| `_compute_website_description()` | Falls back to partner.website_description if sponsor description is empty |
| `_compute_is_in_opening_hours()` | Compares current time (in event TZ) to sponsor's opening hours |
| `_compute_country_flag_url()` | Returns partner country flag URL |
| `_compute_website_url()` | Returns `/event/{slug}/exhibitor/{slug}` |

**CRUD:**

| Method | Description |
|--------|-------------|
| `create(values_list)` | Auto-sets `room_name` for online exhibitors if `is_exhibitor` flag set |
| `write(values)` | For exhibitors without room, sets `room_name = 'odoo-exhibitor-{name}'` sequentially |

**Actions:**

| Method | Description |
|--------|-------------|
| `get_backend_menu_id()` | Returns `event.event_main_menu` |
| `open_website_url()` | Returns relative URL action for `/event/{slug}/exhibitor/{slug}` |

---

### event_event.py — EventEvent

**Inheritance:** `event.event`

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `sponsor_ids` | One2many | Yes | `event.sponsor` records for this event |
| `sponsor_count` | Integer | No | Computed count of sponsors |
| `exhibitor_menu` | Boolean | Yes | Show "Exhibitors" menu on website |
| `exhibitor_menu_ids` | One2many | Yes | Related website.event.menu records |

**Methods:** `_compute_sponsor_count`, `_compute_exhibitor_menu`, `toggle_exhibitor_menu`, `_get_menu_update_fields`, `_update_website_menus`, `_get_menu_type_field_matching`, `_get_website_menu_entries`

---

### event_type.py — EventType

**Inheritance:** `event.type`

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `exhibitor_menu` | Boolean | Yes | Computed from `website_menu` |

---

### website_event_menu.py — EventMenu

**Inheritance:** `website.event.menu`

| Field | Type | Notes |
|-------|------|-------|
| `menu_type` | Selection | Adds `'exhibitor'` to selection, ondelete cascade |

---

## Security / Data

**Security File:** `security/security.xml`

- `event_sponsor_rule_share`: Public/portal users can only READ sponsors where `website_published = True`

**Access Control:**
- `model_event_sponsor_type`: Manager full access
- `model_event_sponsor`: Public read, Portal read, Employee read, Manager CRUD
- `chat.room`: Manager full access (via `event.group_event_manager`)

**Data Files:**
- `data/event_sponsor_data.xml`: Default sponsor types
- `data/event_sponsor_demo.xml`: Demo sponsor records
- `data/event_demo.xml`: Demo event with exhibitors

---

## Critical Notes

- Exhibitor type `'online'` triggers chat room creation via `chat.room.mixin`; `room_name` is auto-generated as `'odoo-exhibitor-{name}'`
- `_synchronize_with_partner()` only fills empty fields — manually set values are preserved
- `is_in_opening_hours` uses event timezone (`date_tz`) not server timezone for correct local time comparison
- `_onchange_exhibitor_type` sets default `room_name` and `room_max_capacity='8'` for online exhibitors
- Sponsor images: `image_512` is stored on sponsor, `image_256`/`image_128` are derived on the fly
- v17→v18: Chat room mixin integration for online exhibitors was added; sponsors now have native opening hours support
