---
Module: website_event_booth
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_event_booth
---

## Overview

Adds paid or free booth booking functionality to the website event pages. Allows exhibitors to reserve booths within an event, optionally creating a corresponding `event.sponsor` record. Depends on `website_event_exhibitor` for sponsor creation.

**Key Dependencies:** `event_booth`, `website_event`

**Python Files:** 4 model files

---

## Models

### event_type.py — EventType

**Inheritance:** `event.type`

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `booth_menu` | Boolean | Yes | Computed from `website_menu` — activates booth menu on website |

**Methods:**

| Method | Decorator | Description |
|--------|-----------|-------------|
| `_compute_booth_menu()` | `@api.depends('website_menu')` | Sets `booth_menu = website_menu` |

---

### event_event.py — Event (event.event)

**Inheritance:** `event.event`

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `exhibition_map` | Image | Yes | Max 1024x1024px — map of the venue |
| `booth_menu` | Boolean | Yes | Computed: from event_type or `website_menu` toggling |
| `booth_menu_ids` | One2many | Yes | Related `website.event.menu` records with `menu_type='booth'` |

**Methods:**

| Method | Decorator | Description |
|--------|-----------|-------------|
| `_compute_booth_menu()` | `@api.depends('event_type_id', 'website_menu')` | Syncs booth_menu from type or activates with website_menu |
| `_get_menu_update_fields()` | — | Adds `'booth_menu'` to menu update fields |
| `_update_website_menus()` | — | Creates/updates the "Get A Booth" menu entry |
| `_get_menu_type_field_matching()` | — | Maps `'booth'` menu type to `'booth_menu'` field |
| `_get_website_menu_entries()` | — | Returns `(_('Get A Booth'), '/event/{slug}/booth', ...)` |
| `toggle_booth_menu(val)` | — | Toggle action for UI |

---

### website_event_menu.py — EventMenu

**Inheritance:** `website.event.menu`

| Field | Type | Notes |
|-------|------|-------|
| `menu_type` | Selection | Adds `'booth'` to selection, ondelete cascade |

---

## Security / Data

**Security File:** `security/event_booth_security.xml`

- `ir_rule_event_booth_public`: Public/portal users can only READ booths where `event_id.website_published = True`
- All booth write/create/unlink restricted to event managers

**Data Files:**
- `data/event_demo.xml`: Demo data
- `ir.model.access.csv`: Booth model access grants

---

## Critical Notes

- `exhibition_map` stores a venue floor plan image (max 1024x1024px)
- `booth_menu` is auto-activated when `website_menu` is enabled, unless manually disabled
- Booth booking flow is implemented in the website controller (Python controller in `controllers/`)
- When a booth is confirmed and `use_sponsor=True`, a sponsor is auto-created via `website_event_booth_exhibitor` linkage
- v17→v18: Booth sponsorship integration was enhanced; the `event.booth` model now tracks `sponsor_id` through related `event.sponsor`
