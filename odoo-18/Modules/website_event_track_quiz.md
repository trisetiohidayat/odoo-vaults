---
Module: website_event_track_quiz
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_event_track_quiz
---

## Overview

Adds quiz functionality to event tracks. Event organizers create quizzes (event.quiz) with multiple-choice questions attached to tracks. Attendees take quizzes through the website; their results (completion, points) are stored in `event.track.visitor`.

**Key Dependencies:** `website_event_track`, `survey`

**Python Files:** 4 model files

---

## Models

### event_quiz.py — Quiz Models

**Three models defined:**

#### event.quiz

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `name` | Char | Yes | Required, translated |
| `question_ids` | One2many | Yes | `event.quiz.question` |
| `event_track_id` | Many2one | Yes | `event.track`, readonly |
| `event_id` | Many2one | No | Related `event_track_id.event_id`, stored |
| `repeatable` | Boolean | Yes | Allow unlimited quiz retakes |

#### event.quiz.question

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `name` | Char | Yes | Required, translated |
| `sequence` | Integer | Yes | Default order |
| `quiz_id` | Many2one | Yes | Parent quiz, cascade delete |
| `answer_ids` | One2many | Yes | `event.quiz.answer` |
| `correct_answer_id` | One2many | No | Computed — answers where `is_correct=True` |
| `awarded_points` | Integer | No | Sum of `answer_ids.awarded_points` |

**Constraints:**
- `@api.constrains('answer_ids')`: Must have exactly 1 correct answer and at least 2 total answers

#### event.quiz.answer

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `sequence` | Integer | Yes | Display order |
| `question_id` | Many2one | Yes | Parent question, cascade delete |
| `text_value` | Char | Yes | Answer text, required, translated |
| `is_correct` | Boolean | Yes | Exactly 1 must be True per question |
| `comment` | Text | Yes | Explanation shown after submission, translated |
| `awarded_points` | Integer | Yes | Points for selecting this answer |

---

### event_track.py — EventTrack (extension)

**Inheritance:** `event.track`

| Field | Type | Store | Groups | Notes |
|-------|------|-------|--------|-------|
| `quiz_id` | Many2one | Yes | Event User | First quiz from `quiz_ids`, readonly |
| `quiz_ids` | One2many | Yes | Event User | All quizzes attached to this track |
| `quiz_questions_count` | Integer | No | Event User | Count of quiz questions |
| `is_quiz_completed` | Boolean | No | — | Current user's completion status |
| `quiz_points` | Integer | No | — | Current user's quiz points |

**Methods:**

| Method | Decorator | Description |
|--------|-----------|-------------|
| `_compute_quiz_id()` | `@api.depends('quiz_ids.event_track_id')` | Returns first quiz in `quiz_ids` |
| `_compute_quiz_questions_count()` | `@api.depends('quiz_id.question_ids')` | Counts questions |
| `_compute_quiz_data()` | `@api.depends('quiz_id', 'event_track_visitor_ids.*', ...)` | Loads visitor's quiz completion and points from `event.track.visitor` |
| `action_add_quiz()` | — | Opens quiz creation form (create=False) |
| `action_view_quiz()` | — | Opens existing quiz form for this track |

---

### event_track_visitor.py — TrackVisitor (extension)

**Inheritance:** `event.track.visitor`

| Field | Type | Store | Notes |
|-------|------|-------|-------|
| `quiz_completed` | Boolean | Yes | Attendee completed the quiz |
| `quiz_points` | Integer | Yes | Points scored, default 0 |

---

### event_event.py — Event (extension)

**Inheritance:** `event.event`

| Method | Decorator | Description |
|--------|-----------|-------------|
| `_compute_community_menu()` | `@api.depends(...)` | Syncs community_menu from type or activates with website_menu |

---

## Security / Data

**Access Control (`ir.model.access.csv`):**
- `event.quiz`: Event user full access
- `event.quiz.question`: Event user full access
- `event.quiz.answer`: Event user full access

**Data Files:**
- `data/quiz_demo.xml`: Demo quiz questions and answers

---

## Critical Notes

- Multiple quizzes per track are supported via `quiz_ids` (One2many), but `quiz_id` (first one) is used for display
- `is_quiz_completed` and `quiz_points` are computed for the current visitor/user via `_compute_quiz_data()`
- The quiz data compute depends on `uid` context — different values per logged-in user
- `@api.depends_context('uid')` on `_compute_quiz_data` ensures proper cache invalidation per user
- `_compute_quiz_data` uses `expression.AND` to combine visitor and partner domains
- `repeatable` field on quiz allows users to reset and retry (controls frontend, not ORM)
- v17→v18: Quiz architecture was redesigned — the `event.quiz` model is new in v18; v17 used the `survey` module's survey/question models
