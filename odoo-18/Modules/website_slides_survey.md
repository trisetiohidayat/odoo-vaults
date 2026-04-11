---
Module: website_slides_survey
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_slides_survey #elearning #certification
---

## Overview

**Module:** `website_slides_survey`
**Depends:** `website_slides`, `survey` (auto_install: True)
**Location:** `~/odoo/odoo18/odoo/addons/website_slides_survey/`
**License:** LGPL-3
**Purpose:** Attaches certification surveys to eLearning course slides. Learners complete the linked survey to earn certification. Failing the last available attempt removes course membership.

---

## Models

### `slide.slide.partner` (models/slide_slide.py, 8–45)

Inherits: `slide.slide.partner`

| Field | Type | Line | Description |
|---|---|---|---|
| `user_input_ids` | One2many (`survey.user_input`) | 11 | "Certification attempts" — all survey attempts for this member's certification slide. |
| `survey_scoring_success` | Boolean (computed, stored) | 12 | "Certification Succeeded" — `True` if any linked `user_input` has `scoring_success=True`. |

| Method | Decorator | Line | Description |
|---|---|---|---|
| `_compute_survey_scoring_success()` | `@api.depends` | 14 | Searches `survey.user_input` (sudo) for `slide_partner_id in self.ids` and `scoring_success=True`. Sets `True` if any match. |
| `_compute_field_value(field)` | override | 24 | When `survey_scoring_success=True` is set: marks the record as `completed=True`. |
| `_recompute_completion()` | override | 31 | After parent completion recompute: finds certified members (`survey_scoring_success=True` with `survey_certification_success=False`) and sets `survey_certification_success=True` on their `slide.channel.partner` record. |

### `slide.slide` (models/slide_slide.py, 46–169)

Inherits: `slide.slide`

| Field | Type | Line | Description |
|---|---|---|---|
| `name` | Char (computed, store) | 49 | Computed from `survey_id.title` if unset; `readonly=False` allows override. |
| `slide_category` | Selection | 50 | Extended: adds `('certification', 'Certification')`; `ondelete='set default'` |
| `slide_type` | Selection | 53 | Extended: adds `('certification', 'Certification')`; `ondelete='set null'` |
| `survey_id` | Many2one (`survey.survey`) | 56 | "Certification" — the survey this slide embeds. |
| `nbr_certification` | Integer (computed, stored) | 57 | Count of certification slides from `_compute_slides_statistics`. |
| `is_preview` | Boolean (computed, store) | 59 | Auto-unchecks for certification slides (cannot be previewed). |

| SQL Constraints | Line | Description |
|---|---|---|
| `check_survey_id` | 61 | `CHECK(slide_category != 'certification' OR survey_id IS NOT NULL)` |
| `check_certification_preview` | 62 | `CHECK(slide_category != 'certification' OR is_preview = False)` |

| Method | Decorator | Line | Description |
|---|---|---|---|
| `_compute_name()` | `@api.depends('survey_id')` | 66 | Sets `name = survey_id.title` if no name and survey exists. |
| `_compute_mark_complete_actions()` | override | 72 | Disables `can_self_mark_completed` and `can_self_mark_uncompleted` for certification slides. |
| `_compute_is_preview()` | `@api.depends('slide_category')` | 79 | Forces `is_preview = False` for `slide_category == 'certification'`. |
| `_compute_slide_icon_class()` | `@api.depends('slide_type')` | 84 | Sets `fa-trophy` icon for `slide_type == 'certification'`. |
| `_compute_slide_type()` | override | 91 | Forces `slide_type = 'certification'` when `slide_category == 'certification'`. |
| `create(vals_list)` | `@api.model_create_multi` | 97 | Auto-sets `slide_category='certification'` for slides with `survey_id`. Calls `_ensure_challenge_category()`. |
| `write(values)` | override | 105 | If `survey_id` changes, calls `_ensure_challenge_category` for old surveys no longer linked. |
| `unlink()` | override | 112 | Calls `_ensure_challenge_category` for current surveys with `unlink=True`. |
| `_ensure_challenge_category(old_surveys=None, unlink=False)` | private | 118 | Sets badge challenge category to `'slides'` so badges appear in certification list. Resets old/unlinked surveys to `'certification'`. |
| `_generate_certification_url()` | business | 129 | Returns dict `{slide_id: url}`. For members: reuses existing user_input or creates new. For non-members: creates test entry. Uses `_generate_invite_token()` to differentiate enrollment pools. |

### `slide.channel` (models/slide_channel.py — verify exact file)

Inherits: `slide.channel`

| Field | Type | Description |
|---|---|---|
| `forum_id` | Many2one (`forum.forum`) | "Course Forum"; copy=False |
| `forum_total_posts` | Integer | Related to `forum_id.total_posts` |

| Method | Decorator | Description |
|---|---|---|
| `action_redirect_to_forum()` | action | Opens forum post list filtered to this forum |
| `create()` | `@api.model_create_multi` | Sets `forum_id.privacy = False` on creation |
| `write()` | override | When `forum_id` changes: syncs privacy, makes old forum private |

### `survey.survey` (models/survey_survey.py, 12–77)

Inherits: `survey.survey`

| Field | Type | Groups | Line | Description |
|---|---|---|---|---|
| `slide_ids` | One2many (`slide.slide`) | — | 15 | "Certification Slides" — slides in any course linked to this survey. |
| `slide_channel_ids` | Many2many (`slide.channel`) | `group_website_slides_officer` | 18 | Computed `_compute_slide_channel_data` — courses using this as certification. |
| `slide_channel_count` | Integer | `group_website_slides_officer` | 22 | Computed — number of courses. |

| Method | Decorator | Line | Description |
|---|---|---|---|
| `_compute_slide_channel_data()` | `@api.depends('slide_ids.channel_id')` | 24 | Maps `slide_ids.mapped('channel_id')`; counts distinct channels. |
| `_unlink_except_linked_to_course()` | `@api.ondelete(at_uninstall=False)` | 30 | Prevents deletion of surveys used as certification. Raises `ValidationError` with certification name and associated course names. Runs as sudo. |
| `action_survey_view_slide_channels()` | action | 52 | Opens channel list (or single form if count=1) filtered to courses using this survey. |
| `_prepare_challenge_category()` | override | 74 | Returns `'slides'` if survey has linked slides, else `'certification'`. Ensures badge appears in the right rank page. |

### `survey.user_input` (models/survey_user.py)

Inherits: `survey.user_input`

| Field | Type | Description |
|---|---|---|
| `slide_id` | Many2one (`slide.slide`) | Related certification slide (when no membership). |
| `slide_partner_id` | Many2one (`slide.slide.partner`) | Member info; `index='btree_not_null'` for efficient joins. |

| Method | Decorator | Description |
|---|---|---|
| `create()` | `@api.model_create_multi` | Calls `_check_for_failed_attempt` after creation |
| `write()` | override | Calls `_check_for_failed_attempt` if `state` changed |
| `_check_for_failed_attempt()` | private | On `state='done'`, `scoring_success=False`, and `slide_partner_id` set: if user has no remaining attempts, sends failure email and removes them from course membership. |

---

## Views

**XML:** `views/slide_slide_views.xml`, `views/slide_channel_views.xml`, `views/survey_survey_views.xml`, `views/survey_user_views.xml`

---

## Data

- `data/gamification_data.xml` — certification badge and challenge definitions
- `data/survey_demo.xml` — demo certification surveys
- `data/survey_user_input_line.csv` — demo attempt answer data
- `data/mail_template_data.xml` — failure notification email
- `data/slide_slide_demo.xml` — demo certification slides

---

## Critical Notes

- **Certification slides cannot be previewed** — enforced by SQL constraint `check_certification_preview`.
- **Failed last attempt = membership removal** — `_check_for_failed_attempt` removes member from course, requiring re-purchase/re-enrollment.
- Badge challenge category: `certification` (default) → `slides` (when linked to a slide) so badges appear in both certification and slides rank pages.
- `slide_partner_id` index is `btree_not_null` for efficient cascade operations in `_remove_membership`.
- `_generate_certification_url` uses `invite_token` to differentiate pools of attempts when the same course is enrolled multiple times.
- v17→v18: No breaking changes.