---
Module: hr_skills_slides
Version: 18.0.0
Type: addon
Tags: #odoo18 #hr_skills_slides
---

## Overview
Skills e-learning. Bridge between `hr_skills` and `website_slides`. When an employee completes an e-learning course (slides channel), a `hr.resume.line` of type 'course' is automatically added to their resume. Also shows subscribed/completed courses on the employee form and sends chatter notifications when employees subscribe or complete courses.

## Models

### hr.employee (Extension)
Inherits from: `hr.employee`
File: `~/odoo/odoo18/odoo/addons/hr_skills_slides/models/hr_employee.py`

| Field | Type | Description |
|-------|------|-------------|
| subscribed_courses | Many2many(slide.channel) | Related from `user_partner_id.slide_channel_ids` |
| has_subscribed_courses | Boolean | `compute='_compute_courses_completion_text'` |
| courses_completion_text | Char | `compute`; format: "{completed} / {total}" |

**Methods:**
| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _compute_courses_completion_text | self | None | Sets `courses_completion_text = "{n}/{total}"` and `has_subscribed_courses` |
| action_open_courses | self | action | Opens `/profile/user/{user_id}` URL in new tab |

### slide.channel.partner (Extension)
Inherits from: `slide.channel.partner`
File: `~/odoo/odoo18/odoo/addons/hr_skills_slides/models/slide_channel.py`

**Methods:**
| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _recompute_completion | self | bool | Overrides parent: after marking membership as completed, creates `hr.resume.line` records for each newly completed channel if not already present. Uses `sudo()` for `hr.employee` and `hr.resume.line` |
| _send_completed_mail | self | bool | Extends parent: posts a chatter message to the employee's wall: "The employee has completed the course {name}" |

### slide.channel (Extension)
Inherits from: `slide.channel`
File: `~/odoo/odoo18/odoo/addons/hr_skills_slides/models/slide_channel.py`

**Methods:**
| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _action_add_members | target_partners, member_status | records | Overrides parent: for 'joined' status, posts chatter message to each partner's employee: "The employee subscribed to the course {name}" |
| _remove_membership | partner_ids | bool | Overrides parent: posts chatter message: "The employee left the course {name}" |
| _message_employee_chatter | msg, partners | None | Internal helper: finds `hr.employee` linked to each partner and posts the message to their chatter |

### hr.resume.line (Extension)
Inherits from: `hr.resume.line`
File: `~/odoo/odoo18/odoo/addons/hr_skills_slides/models/hr_resume_line.py`

| Field | Type | Description |
|-------|------|-------------|
| display_type | Selection | Adds `('course', 'Course')` to existing types |
| channel_id | Many2one(slide.channel) | Linked course; `index='btree_not_null'` |
| course_url | Char | `compute='_compute_course_url'`; derived from `channel_id.website_url` |

**Methods:**
| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _compute_course_url | self | None | Sets `channel_id.website_url` if `display_type == 'course'`, else False |

## Security
- No custom ACL files — uses `hr_skills` and `website_slides` ACLs
- `sudo()` is used in `_recompute_completion` to create resume lines — bypasses record rules

## Critical Notes
- **`_recompute_completion` idempotency:** Checks `lines_for_channel_by_employee` to avoid duplicate resume lines per (employee, channel) pair
- **Resume line creation:** Creates a line with `date_start = date_end = today()` and description from `channel.description` (html2plaintext)
- **`display_type='course'`:** Differentiates course resume lines from certification lines (certification is in `hr_skills_survey`)
- **Chatter messages:** Uses `sudo()` + `message_post` to notify employee via their user account
- **v17→v18:** `_recompute_completion` uses `sudo()` on employee search; no other breaking changes
