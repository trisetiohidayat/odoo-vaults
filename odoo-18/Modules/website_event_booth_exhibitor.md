---
Module: website_event_booth_exhibitor
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_event_booth_exhibitor
---

## Overview

Links confirmed booth bookings to exhibitor (sponsor) records. When a booth with `use_sponsor=True` is confirmed, this module auto-creates or reuses an `event.sponsor` record attached to the booth's partner.

**Key Dependencies:** `website_event_booth`, `event_booth`, `event_sale` (optional), `website_event_exhibitor`

**Python Files:** 3 model files

---

## Models

### event_booth_category.py — EventBoothCategory

**Inheritance:** `event.booth.category`

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `use_sponsor` | Boolean | Yes | If True, booking a booth auto-creates a sponsor for the user |
| `sponsor_type_id` | Many2one | Yes | `event.sponsor.type` — sponsor level/grade |
| `exhibitor_type` | Selection | Yes | Derives from `event.sponsor.exhibitor_type` selection |

**Methods:**

| Method | Decorator | Description |
|--------|-----------|-------------|
| `_get_exhibitor_type()` | `@api.model` | Returns `event.sponsor._fields['exhibitor_type'].selection` |
| `_onchange_use_sponsor()` | `@api.onchange('use_sponsor')` | Auto-sets default sponsor_type and exhibitor_type when toggled on |

---

### event_booth.py — EventBooth

**Inheritance:** `event.booth`

| Field | Type | Store | Related |
|-------|------|-------|---------|
| `use_sponsor` | Boolean | Yes | `booth_category_id.use_sponsor` (related) |
| `sponsor_type_id` | Many2one | Yes | `booth_category_id.sponsor_type_id` (related) |
| `sponsor_id` | Many2one | Yes | `event.sponsor` — created on confirmation |
| `sponsor_name` | Char | Yes | Related `sponsor_id.name` |
| `sponsor_email` | Char | Yes | Related `sponsor_id.email` |
| `sponsor_mobile` | Char | Yes | Related `sponsor_id.mobile` |
| `sponsor_phone` | Char | Yes | Related `sponsor_id.phone` |
| `sponsor_subtitle` | Char | Yes | Related `sponsor_id.subtitle` |
| `sponsor_website_description` | Html | Yes | Related `sponsor_id.website_description` |
| `sponsor_image_512` | Image | Yes | Related `sponsor_id.image_512` |

**Methods:**

| Method | Decorator | Description |
|--------|-----------|-------------|
| `action_view_sponsor()` | — | Opens the linked sponsor form view |
| `_get_or_create_sponsor(vals)` | — | Searches for existing sponsor by partner+type+event, creates if not found. Sets `room_name` for online exhibitors |
| `_action_post_confirm(write_vals)` | — | Hook called after booth confirmation: sets `sponsor_id` if `use_sponsor` and partner exists |

---

## Security / Data

**Security:** No dedicated security XML; relies on parent `event.booth` and `event.sponsor` rules

**Data Files:**
- `data/event_booth_category_data.xml`: Demo booth categories with sponsor defaults

---

## Critical Notes

- `_get_or_create_sponsor()` uses sudo() to create the sponsor record, bypassing standard ACL for the partner
- For online exhibitors (`exhibitor_type == 'online'`), sets `room_name = 'odoo-exhibitor-{partner_name}'`
- Sponsor creation merges booth registration field values (name, email, mobile, etc.) into the sponsor record
- `_action_post_confirm` is the post-confirmation hook — called after booth state transitions to `reserved`
- v17→v18: Integration between booth booking and exhibitor sponsorship is more tightly coupled
