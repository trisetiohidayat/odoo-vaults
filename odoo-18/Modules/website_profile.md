---
Module: website_profile
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_profile
---

## Overview

User profile pages on the website with karma-based access control, gamification badges, and email validation. Users earn karma by participating in forum, surveys, and other community features.

**Key Dependencies:** `gamification`, `website`

**Python Files:** 3 model files

---

## Models

### res_users.py — Users

**Inheritance:** `res.users`

| Field | Access | Notes |
|-------|--------|-------|
| `karma` | Read (own) | Added to `SELF_READABLE_FIELDS` |
| `country_id`, `city`, `website`, `website_description`, `website_published` | Write (own) | Added to `SELF_WRITABLE_FIELDS` |

**Methods:**

| Method | Decorator | Description |
|--------|-----------|-------------|
| `_generate_profile_token(user_id, email)` | `@api.model` | SHA256 hash of (day, uuid, user_id, email) for email validation — valid for the current day |
| `_send_profile_validation_email()` | — | Sends validation email with token URL to `/profile/validate_email` |
| `_process_profile_validation_token(token, email)` | — | Validates token; if valid and `karma==0`, awards `VALIDATION_KARMA_GAIN = 3` karma |

**Constants:**
- `VALIDATION_KARMA_GAIN = 3` — karma awarded on email validation

---

### gamification_badge.py — GamificationBadge

**Inheritance:** `gamification.badge`, `website.published.mixin`

> No new fields or methods — just inherits both mixins

---

### website.py — Website

**Inheritance:** `website`

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `karma_profile_min` | Integer | Yes | Minimum karma to view other users' profiles, default 150 |

---

## Security / Data

**Access Control (`ir.model.access.csv`):**
- `gamification.karma.rank`: Website restricted editor read/write

**Data Files:**
- `data/mail_template_data.xml`: Email validation template

---

## Critical Notes

- Karma is earned from forum posts, survey completions, badge awards, and email validation
- Profile pages are visible to all, but viewing OTHER users' profiles requires `karma >= karma_profile_min`
- Email validation is one-time: `_process_profile_validation_token` only awards karma when `karma == 0`
- The validation token changes daily (based on day boundary) — prevents token replay
- `website_published` on users controls whether they appear in the public user directory
- v17→v18: Badge model now inherits `website.published.mixin` to allow badge publishing control
