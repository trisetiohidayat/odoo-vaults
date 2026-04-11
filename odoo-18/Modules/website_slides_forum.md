---
Module: website_slides_forum
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_slides_forum #elearning #forum
---

## Overview

**Module:** `website_slides_forum`
**Depends:** `website_slides`, `website_forum` (auto_install: True)
**Location:** `~/odoo/odoo18/odoo/addons/website_slides_forum/`
**License:** LGPL-3
**Purpose:** Attaches a forum to each eLearning course. Each course gets one dedicated forum whose privacy and image sync from the course record.

---

## Models

### `forum.forum` (models/forum_forum.py, 1–27)

Inherits: `forum.forum`

| Field | Type | Line | Description |
|---|---|---|---|
| `slide_channel_ids` | One2many (`slide.channel`) | 10 | "Courses" — all courses linked to this forum. `help` text directs to course form for editing. |
| `slide_channel_id` | Many2one (`slide.channel`) | 11 | Computed from `slide_channel_ids`; store=True. Returns first channel or `False`. |
| `visibility` | Selection (related) | 12 | Related to `slide_channel_id.visibility` — read-only. Inherited from the linked course. |
| `image_1920` | Image (computed) | 13 | Inherits course image when forum has no own image set. `readonly=False` allows override. |

| Method | Decorator | Line | Description |
|---|---|---|---|
| `_compute_slide_channel_id()` | `@api.depends('slide_channel_ids')` | 16 | Sets to first element of `slide_channel_ids` or `False` if empty. |
| `_compute_image_1920()` | `@api.depends('slide_channel_id', 'slide_channel_id.image_1920')` | 23 | Copies channel image to forum if `not forum.image_1920 and channel.image_1920`. |

### `slide.channel` (models/slide_channel.py, 1–46)

Inherits: `slide.channel`

| Field | Type | Line | Description |
|---|---|---|---|
| `forum_id` | Many2one (`forum.forum`) | 10 | "Course Forum"; `copy=False` — a forum cannot be shared across courses. |
| `forum_total_posts` | Integer (related) | 11 | Related to `forum_id.total_posts` — live count of active forum posts. |

| SQL Constraint | Line | Description |
|---|---|---|
| `forum_uniq`: `unique(forum_id)` | 14 | Only one course can link to a given forum. |

| Method | Line | Description |
|---|---|---|
| `action_redirect_to_forum()` | 17 | Opens `forum.post` list filtered to `forum_id=self.forum_id.id`. Sets `create=False` in context. Single result → form view. |
| `create(vals_list)` | 28 | On creation, sets `forum_id.privacy = False` so forum is publicly accessible. |
| `write(vals)` | 34 | When `forum_id` changes: sets new forum `privacy = False`; if old forum differs, sets old forum to `privacy='private'` restricted to `group_website_slides_officer`. |

---

## Security / Data

`ir.model.access.csv` present.
Security XML: `website_slides_forum_security.xml`
Data: `data/slide_channel_demo.xml` — demo courses with linked forums.

---

## Critical Notes

- A forum can only belong to one course (unique constraint). Assigning a forum to a course is a one-time operation.
- When a course's forum is changed, the old forum becomes private (restricted to slide officers).
- Forum visibility and image are automatically synced from the course but can be overridden on the forum.
- v17→v18: No breaking changes.