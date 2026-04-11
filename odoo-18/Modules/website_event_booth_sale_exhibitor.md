---
Module: website_event_booth_sale_exhibitor
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_event_booth_sale_exhibitor
---

## Overview

Bridges booth sale and exhibitor sponsor creation. Passes sponsor fields collected during the website checkout (name, email, mobile, phone, subtitle, description, logo) through the sale order line registration values, so that when a booth is confirmed, a complete sponsor record is created.

**Key Dependencies:** `website_event_booth_sale`, `website_event_booth_exhibitor`

**Python Files:** 1 model file

---

## Models

### event_booth_registration.py — EventBoothRegistration

**Inheritance:** `event.booth.registration`

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `sponsor_name` | Char | Yes | Sponsor display name |
| `sponsor_email` | Char | Yes | Sponsor contact email |
| `sponsor_mobile` | Char | Yes | Sponsor mobile number |
| `sponsor_phone` | Char | Yes | Sponsor phone number |
| `sponsor_subtitle` | Char | Yes | Sponsor slogan/tagline |
| `sponsor_website_description` | Html | Yes | Sponsor about text |
| `sponsor_image_512` | Image | Yes | Sponsor logo image |

**Methods:**

| Method | Decorator | Description |
|--------|-----------|-------------|
| `_get_fields_for_booth_confirmation()` | — | Returns list of all sponsor fields to pass through to booth confirmation (used by parent `_action_post_confirm`) |

---

## Security / Data

No dedicated security XML or data files.

---

## Critical Notes

- All sponsor fields are stored on `event.booth.registration` — the intermediate model between sale order line and confirmed booth
- On booth confirmation, `_action_post_confirm()` in `event.booth` (from `website_event_booth_exhibitor`) reads these registration fields and passes them to `_get_or_create_sponsor()`
- The `sponsor_image_512` field stores the uploaded logo from the website checkout form
- `_get_fields_for_booth_confirmation()` extends the parent method by adding the sponsor fields to the list
- v17→v18: The registration model now holds rich sponsor profile data (images, HTML description) enabling full exhibitor profiles from the website
