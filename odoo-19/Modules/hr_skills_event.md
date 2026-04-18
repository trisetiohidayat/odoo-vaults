---
title: HR Skills Event
description: Links completed onsite training events to employee resumes. Adds an "Onsite" course type that auto-populates resume lines when employees attend multi-slot events.
tags: [odoo19, hr, skills, event, resume, training, module]
model_count: 2
models:
  - hr.resume.line (extends)
dependencies:
  - hr_skills
  - event
category: Hidden
source: odoo/addons/hr_skills_event/
created: 2026-04-14
uuid: b7e4d2a1-9c3f-4e8b-8d1c-5a2f6b8e0d3c
---

# HR Skills Event

## Overview

**Module:** `hr_skills_event`
**Category:** Hidden
**Depends:** `hr_skills`, `event`
**Auto-install:** True
**License:** LGPL-3
**Author:** Odoo S.A.

`hr_skills_event` bridges Odoo's [Modules/event](event.md) and [Modules/hr_skills](hr_skills.md) modules to automatically populate employee resumes with completed onsite training events. Where `hr_skills` provides the general resume framework (`hr.resume.line`, resume types, skill tracking), this module adds a specialized "Onsite" course type that links directly to `event.event` records.

The core scenario it enables: when employees attend a multi-slot event (a multi-day training workshop, a conference, or an onsite seminar), the system can automatically create a resume line on each attendee's HR profile. This creates a complete training history without manual data entry.

Key design decisions:
- Only **multi-slot events** (`is_multi_slots = True`) can be linked to resume lines. Single-session events (one-off webinars) are excluded because they are not considered formal training.
- Only attendees who are **employees** (not just contacts) generate resume lines. This prevents creating spurious resume entries for non-employee event attendees.
- The `course_type = 'onsite'` is a distinct resume category with its own color (`#714a66`) in the resume kanban view, making onsite training visually distinct from e-learning and certification courses.

## Module Structure

```
hr_skills_event/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   └── hr_resume_line.py   # event_id, onsite course_type, color
└── views/
    ├── hr_resume_line_views.xml  # Onsite course type in resume form
    ├── event_event_views.xml     # Attendee list on event form
    └── hr_views.xml              # Resume tab visibility
```

## Extended Models

### `hr.resume.line` (extends)

File: `models/hr_resume_line.py`

The `hr.resume.line` model is extended with three additions: a Many2one to `event.event`, a new course type option, and a computed color.

**New Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `event_id` | Many2one `event.event` | The training event this resume line represents. Computed, stored, indexed `btree_not_null`. Only events with `is_multi_slots = True` and employee attendees are shown. |
| `course_type` | Selection | Added `'onsite'` option with `ondelete='cascade'`. When a resume line's type is deleted, the onsite resume lines are cascade-deleted. |

**`event_id` Field Definition:**

```python
event_id = fields.Many2one(
    'event.event',
    string="Onsite Course",
    compute='_compute_event_id',
    store=True,
    readonly=True,
    index='btree_not_null',
    domain=([
        ('is_multi_slots', '=', True),
        ('registration_ids', 'any', [('partner_id.employee', '=', True)])
    ])
)
```

The domain restriction is critical: it ensures only relevant events appear when manually linking a resume line. The `registration_ids.any` check verifies the event has at least one registration where the contact is marked as an employee.

**`_compute_event_id`:**

```python
@api.depends('course_type')
def _compute_event_id(self):
    for resume_line in self:
        if resume_line.course_type != 'onsite':
            resume_line.event_id = False
```

This method enforces a critical business rule: the `event_id` field is only populated for `'onsite'` course type resume lines. When the course type changes to anything else (e.g., 'certification', 'course', or 'internal'), the `event_id` is cleared. This prevents orphaned event references.

**`_compute_color`:**

```python
def _compute_color(self):
    super()._compute_color()
    for resume_line in self:
        if resume_line.course_type == 'onsite':
            resume_line.color = '#714a66'
```

The color assignment uses the parent class's `_compute_color()` method first, then overrides the color specifically for onsite courses. The hex color `#714a66` (a muted purple-brown) is used to visually distinguish onsite training entries in the resume kanban view.

The parent class (`hr_skills` module) likely defines the base color logic for other course types, ensuring each resume type has a distinct color in the kanban display.

**`_onchange_event_id`:**

```python
@api.onchange('event_id')
def _onchange_event_id(self):
    if not self.name and self.event_id:
        self.name = self.event_id.name
```

This convenience method auto-fills the resume line's display name from the linked event's name. It only triggers if `name` is currently empty, preventing accidental overwrites of custom names. For example, if `event_id` is set to "Advanced Forklift Safety Certification 2025", the name field automatically populates with that value.

## Resume Line Lifecycle for Onsite Events

The typical flow for creating onsite training resume entries:

```
1. HR Admin creates an Event Type with multi-slot enabled
   └── event.type with is_multi_slots = True

2. Event Manager creates the Event from the type
   └── event.event with is_multi_slots = True
   └── Adds ticket types and sessions

3. HR Admin / Event Manager registers employees
   └── event.registration records created
   └── Each registration: partner_id = employee's contact
   └── partner_id.employee = True (contact is linked to an employee)

4. Event runs and is confirmed complete
   └── event.state = 'done'

5. HR Admin reviews registrations
   └── Creates hr.resume.line records manually OR uses automation
   └── Sets course_type = 'onsite'
   └── Sets event_id to the completed event
   └── name auto-fills from event
   └── Color auto-assigned (#714a66)

6. Employee's Resume (HR app)
   └── Onsite training card appears in kanban
   └── Card shows event name, date, course type color
```

**Note on automatic creation:** The module does not automatically create resume lines when an event ends. This is intentional: some registrations may not represent completed training (no-shows, cancellations). HR administrators are expected to review the attendee list and selectively create resume lines for employees who actually attended.

For fully automatic creation, a separate automation rule or custom code would be needed, triggered by `event.registration` state changes.

## Visual Integration

The `views/hr_resume_line_views.xml` adds the `event_id` field and `course_type = 'onsite'` option to the resume line form. The `views/event_event_views.xml` adds a Smart Button showing the attendee list on the event form, allowing HR to quickly see who attended.

The `course_type = 'onsite'` option is presented alongside the standard types in `hr_skills`:
- `certification` -- From `hr_skills_survey`
- `course` -- General e-learning
- `onsite` -- From `hr_skills_event`
- `skill` -- Skill entries

## Cross-Module Dependencies

| Module | Role | Integration Point |
|--------|------|-------------------|
| [Modules/hr_skills](hr_skills.md) | Base resume model | `hr.resume.line` is the model being extended |
| [Modules/event](event.md) | Event and registration models | `event.event` is the target of `event_id` |
| [Modules/hr_skills_survey](hr_skills_survey.md) | Certification resume lines | Parallel bridge; certification + onsite are both resume categories |
| [Modules/survey](survey.md) | Survey/certification | `hr_skills_survey` depends on survey; `hr_skills_event` does not |

## Security

The module relies on the access control from `hr_skills` and `event`:

- `hr.resume.line`: Controlled by `hr_skills` ACLs
- `event.event`: Controlled by `event` module ACLs
- `event.registration`: Access via `event` module ACLs

Users need read access to `event.event` and `event.registration` to use the `event_id` domain filter in the UI. HR officers and managers typically have this access through the `hr_skills` and `event` groups.

## Extension Points

| Extension Point | How to Extend |
|-----------------|---------------|
| Auto-create resume lines on event close | Override `write()` on `event.event` to auto-create `hr.resume.line` when `state` transitions to `'done'` |
| Filter by event tag/category | Add a tag filter to the `event_id` domain to only allow specific training event categories |
| Auto-name from event + date | Extend `_onchange_event_id()` to also set `date_start` from `event_id.date_begin` |
| Onsite attendance validation | Extend `_compute_event_id()` to check `registration_id.state = 'done'` (attended, not just registered) |

## Related

- [Modules/hr_skills](hr_skills.md) -- Base resume framework, skill tracking, course types
- [Modules/event](event.md) -- Event management, multi-slot events, registration
- [Modules/hr_skills_survey](hr_skills_survey.md) -- Survey certification resume lines
- [Modules/hr](hr.md) -- Employee master data, `partner_id.employee` flag


## Business Flow: Onsite Training to Resume

The complete process of linking an onsite training event to an employee resume involves multiple systems and several steps. Understanding this end-to-end flow clarifies where `hr_skills_event` fits in the broader HR and event management ecosystem.

### Step 1: HR Creates a Training Event

The HR department creates a multi-slot event (e.g., "Workplace Safety Certification Workshop"):

1. HR manager navigates to **Events > Create**
2. Sets event name, date, location, and `is_multi_slots = True` (multi-day or multi-session)
3. Adds ticket types (if paid training) and session tracks
4. Publishes the event

Because `is_multi_slots = True`, the event's registrations can be filtered by the `event_id` domain in the resume line form.

### Step 2: Employees Register via the Portal or Internal Link

Employees self-register for the training through the website portal or an internal link:

1. Employee (as `res.partner` with `employee = True`) registers for the event
2. An `event.registration` record is created: `{partner_id: emp_contact, event_id: training_event}`
3. The employee receives an email or SMS confirmation via `event_mail` or `event_sms`

At this point, the registration exists but no resume line has been created yet.

### Step 3: Training is Conducted

The event runs as scheduled. Attendance is tracked:
- Some employees attended all sessions
- Some attended partial sessions
- Some were no-shows

The HR team reviews the actual attendance list via the attendee Smart Button on the event form.

### Step 4: HR Creates Resume Lines for Attendees

This is where `hr_skills_event` comes in:

1. HR officer opens the Employee Resume: HR app > Employee > Resume tab
2. Clicks "Add an entry" and selects type "Onsite"
3. The `event_id` field appears with the domain filter showing only multi-slot events with employee attendees
4. HR selects the completed training event
5. The `name` auto-fills from the event name via `_onchange_event_id()`
6. HR optionally sets a custom name (the auto-fill only runs if name is currently empty)
7. The `color` is automatically set to `#714a66` via `_compute_color()`
8. Resume line is saved

### Step 5: Resume Line Appears on Employee Profile

The employee profile now shows a kanban card with the purple-brown color, event name, and date range. In the resume list, the entry displays the training course name, course type "Onsite", and dates.

### Key Design Decisions Explained

#### Why `is_multi_slots = True`?

Single-slot events (one-time webinars, brief seminars) are filtered out because they are not considered formal training that belongs on a professional resume. Only multi-session events such as multi-day workshops, conferences, and structured training programs qualify.

#### Why `partner_id.employee = True`?

Non-employee registrations (customers, vendors, external guests) should not create resume entries on employee profiles. The domain `('registration_ids', 'any', [('partner_id.employee', '=', True)])` ensures only events with at least one employee registration are selectable.

#### Why `ondelete='cascade'` on `course_type = 'onsite'`?

When an HR administrator deletes the "Onsite" resume line type via `hr.resume.line.type`, all associated resume lines are cascade-deleted. This prevents orphaned resume lines referencing a deleted type.

## Comparison: Onsite vs Certification Resume Types

| Aspect | Onsite (hr_skills_event) | Certification (hr_skills_survey) |
|--------|--------------------------|----------------------------------|
| Source | `event.event` | `survey.survey` |
| Creation | Manual by HR | Automatic on passing |
| Expiration | None (no validity) | Configurable (`certification_validity_months`) |
| Color | `#714a66` (purple-brown) | Defined by `hr_skills` |
| Prerequisite | `is_multi_slots = True` | `certification = True` on survey |
| Attendance tracking | Via event registration | Via survey completion |

## Relationship to Skills Matrix

The resume lines created by `hr_skills_event` can be used in conjunction with the Skills Matrix (part of `hr_skills`). The Skills Matrix maps employees to competencies and skill levels. An onsite training event might cover specific skills (e.g., "Forklift Operation", "CPR Certification"), and the resume line provides evidence that an employee completed that training.

For full skills matrix integration, additional customization would be needed to link the `event_id` to specific `hr.skill` records. The base `hr_skills_event` provides the linkage to events; mapping to specific skills would be a custom extension.


## View Integration

The module modifies three views via XML inheritance:

### `hr_resume_line_views.xml`

Adds the `event_id` Many2one field to the resume line form, constrained by the domain that filters to multi-slot events with employee attendees. The field appears in the form alongside the standard resume line fields (name, date_start, date_end, description, line_type_id).

### `event_event_views.xml`

Adds a Smart Button (stat button) to the `event.event` form that shows the count of employee registrations. This allows event organizers to quickly see how many registered attendees are actual employees (who will have resume lines created).

### `hr_views.xml`

May include visibility or layout adjustments for the Resume tab in the employee form when viewed in the context of the HR application.

## Extension Example: Auto-Create on Event Close

The most common extension request for `hr_skills_event` is to auto-create resume lines when an event is marked as done. Here is the pattern:

```python
class EventEvent(models.Model):
    _inherit = 'event.event'

    def write(self, vals):
        res = super().write(vals)
        # When event is confirmed as done, create resume lines
        if vals.get('state') == 'done':
            self._create_resume_lines_from_registrations()
        return res

    def _create_resume_lines_from_registrations(self):
        line_type = self.env.ref(
            'hr_skills_survey.resume_type_certification',  # or a specific onsite type
            raise_if_not_found=False
        )
        for event in self:
            # Only multi-slot events create onsite resume lines
            if not event.is_multi_slots:
                continue
            for registration in event.registration_ids:
                if not registration.partner_id.employee:
                    continue
                self.env['hr.resume.line'].create({
                    'employee_id': registration.partner_id.employee_id.id,
                    'name': event.name,
                    'course_type': 'onsite',
                    'date_start': event.date_begin,
                    'date_end': event.date_end,
                    'line_type_id': line_type.id if line_type else False,
                    'event_id': event.id,
                })
```

This pattern respects all the same filters (`is_multi_slots`, `employee = True`) and creates a resume line for each qualifying registration.
