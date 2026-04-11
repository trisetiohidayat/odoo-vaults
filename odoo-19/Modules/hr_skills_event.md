# HR Skills Event

## Overview
- **Name**: Skills Events (`hr_skills_event`)
- **Category**: Hidden
- **Depends**: `hr_skills`, `event`
- **Version**: 1.0
- **License**: LGPL-3
- **Auto-install**: True

Adds completed onsite training events to employee resumes. Links multi-slot events with attendee employees.

## Models

### `hr.resume.line` (extends)
| Field | Type | Description |
|-------|------|-------------|
| `event_id` | Many2one | Linked event (onsite type only) |
| `course_type` | Selection | Added `onsite` option |
| `color` | Integer | Onsite courses colored #714a66 |

- `_compute_event_id`: Clears event_id if course_type is not 'onsite'
- `_compute_color`: Sets color for onsite entries
- `_onchange_event_id`: Auto-fills name from event

## Key Features
- Resume line type for onsite training courses
- Links `event.event` (multi-slot events with employee attendees) to resume lines
- Onsite type displayed with distinct color (#714a66) in resume kanban
- Auto-fills resume line name from event name

## Related
- [[Modules/hr_skills]] - Core skills and resume module
- [[Modules/event]] - Event management
