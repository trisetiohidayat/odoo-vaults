---
Module: website_event_meet_quiz
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_event_meet_quiz
---

## Overview

No Python models. This module exists solely to add quiz functionality to meeting rooms (linking `event.meeting.room` with the quiz system) and to ensure the meet quiz QWeb templates are loaded.

**Note:** As of Odoo 18, this module has no `models/` directory. Quiz features for event tracks are handled by `website_event_track_quiz`.

**Key Dependencies:** `website_event_meet`, `website_event_track_quiz`

---

## Critical Notes

- The module is a thin dependency layer — the actual quiz models (`event.quiz`, `event.quiz.question`, `event.quiz.answer`) are defined in `website_event_track_quiz`
- Meeting room quiz integration is achieved through QWeb template inheritance (in `views/`)
- In v17 this module had a different structure; in v18 the architecture was simplified with no ORM models
