# HR Skills Slides

## Overview
- **Name**: Skills e-learning (`hr_skills_slides`)
- **Category**: Human Resources/Employees
- **Depends**: `hr_skills`, `website_slides`
- **Version**: 1.0
- **License**: LGPL-3
- **Auto-install**: True

Automatically adds completed eLearning courses to employee resumes. Posts notifications when employees subscribe to or complete courses.

## Models

### `hr.employee` (extends)
| Field | Type | Description |
|-------|------|-------------|
| `subscribed_courses` | Many2many | Channels the employee (via user partner) is subscribed to |
| `has_subscribed_courses` | Boolean | Has at least one subscribed course |
| `courses_completion_text` | Char | "X / Y courses completed" text |

- `_compute_courses_completion_text`: Computes completion ratio text
- `action_open_courses`: Opens `/profile/user/{user_id}`

### `hr.employee.public` (extends)
| Field | Type | Description |
|-------|------|-------------|
| `has_subscribed_courses` | Boolean | Related |
| `courses_completion_text` | Char | Related |
| `action_open_courses` | Action | Opens courses for internal users |

### `hr.resume.line` (extends)
| Field | Type | Description |
|-------|------|-------------|
| `channel_id` | Many2one | Linked slide channel (elearning type only) |
| `course_url` | Char | Channel website URL (related) |
| `duration` | Integer | Course duration in minutes (related to channel total time) |
| `course_type` | Selection | Added `elearning` option |
| `color` | Integer | eLearning lines colored #00a5b7 |

- `_compute_channel_id`: Clears channel if type is not 'elearning'
- `_compute_duration`: Auto-fills from channel total time
- `_compute_color`: Sets color for elearning entries
- `_onchange_channel_id`: Auto-fills name from channel

### `slide.channel.partner` (extends)
- `_post_completion_update_hook`: On course completion, creates `hr.resume.line` with elearning type for employee's linked user
- `_send_completed_mail`: Additional chatter message to user's employee when course completed

### `slide.channel` (extends)
- `_action_add_members`: Posts message to employee when subscribed to a course
- `_remove_membership`: Posts message when employee leaves a course
- `_message_employee_chatter`: Helper to post to employee's internal chatter

## Key Features
- Completed eLearning courses auto-added to employee resume (with channel link, duration, description)
- Completion notification posted to employee's internal chatter
- Subscription/unsubscription events posted to chatter
- eLearning resume entries colored #00a5b7
- Course completion counts shown on employee kanban

## Related
- [Modules/hr_skills](hr_skills.md) - Core skills module
- [Modules/website_slides](website_slides.md) - eLearning platform
