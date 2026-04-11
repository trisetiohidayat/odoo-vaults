---
Module: website_event_track_live_quiz
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_event_track_live_quiz
---

## Overview

No Python models. This module combines live streaming (`website_event_track_live`) with quiz functionality (`website_event_track_quiz`), enabling quizzes to appear alongside YouTube live streams on track pages.

**Note:** As of Odoo 18, this module has no `models/` directory. The actual models are in the dependency modules.

**Key Dependencies:** `website_event_track_live`, `website_event_track_quiz`

---

## Critical Notes

- This is a thin dependency/transitive module — it exists to aggregate dependencies
- Quiz for live tracks uses the same `event.quiz` / `event.quiz.question` / `event.quiz.answer` models from `website_event_track_quiz`
- Live streaming quiz rendering is done through QWeb template composition
- In v18 the architecture was simplified — no ORM models needed in this module
