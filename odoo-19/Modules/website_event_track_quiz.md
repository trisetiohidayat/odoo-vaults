---
description: Quizzes embedded in event tracks — question/answer models, scoring, leaderboard, visitor tracking, and submission/reset flows.
tags:
  - odoo
  - odoo19
  - modules
  - website
  - events
  - gamification
---

# website_event_track_quiz — Event Track Quizzes

## Module Overview

| Property | Value |
|----------|-------|
| **Technical Name** | `website_event_track_quiz` |
| **Category** | Marketing/Events |
| **Depends** | `website_profile`, `website_event_track` |
| **License** | LGPL-3 |
| **Odoo Version** | 19.0 CE |

`website_event_track_quiz` enables interactive quizzes attached to individual event tracks. Attendees answer multiple-choice questions, earn points, and see themselves on an event-wide leaderboard. The module defines a three-tier data model (`event.quiz`, `event.quiz.question`, `event.quiz.answer`) and extends `event.track` and `event.track.visitor` with quiz-related fields and computed states.

## Architecture

### Module Structure

```
website_event_track_quiz/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── event_quiz.py        # event.quiz, event.quiz.question, event.quiz.answer
│   ├── event_track.py       # quiz_id, quiz_questions_count, is_quiz_completed, quiz_points on event.track
│   ├── event_track_visitor.py  # quiz_completed + quiz_points on event.track.visitor
│   └── event_event.py       # _compute_community_menu override
├── controllers/
│   ├── __init__.py
│   ├── event_track_quiz.py  # Quiz submit + reset endpoints
│   └── community.py         # Leaderboard rendering
├── views/
│   ├── event_quiz_views.xml        # Quiz form/list/search + action
│   ├── event_quiz_question_views.xml  # Questions list/form + action
│   ├── event_track_views.xml       # Inherit track form to add quiz tab
│   ├── event_track_visitor_views.xml  # Visitor list/form/tree with quiz fields
│   ├── event_event_views.xml       # Inherit event form
│   ├── event_type_views.xml        # Inherit event type form
│   ├── event_leaderboard_templates.xml  # Leaderboard QWeb template
│   ├── event_quiz_templates.xml    # Quiz UI QWeb template
│   └── event_track_templates_page.xml  # Page template override
├── security/
│   └── ir.model.access.csv
├── data/
│   └── quiz_demo.xml
└── static/
    ├── src/
    │   ├── interactions/*.js  # Frontend quiz interactions
    │   ├── xml/*.xml           # QWeb templates
    │   └── scss/*.scss
    └── description/
```

### Key Design Principles

1. **Quiz per track** — each `event.track` can have at most one `event.quiz` record (accessed via the computed `quiz_id` field). A quiz contains multiple questions.
2. **Scoring at the question level** — points are awarded per answer choice, not per question. The sum of all correct answer points equals the question's `awarded_points`. The total `quiz_points` on a visitor is the sum across all questions answered.
3. **Visitor-aware** — the quiz tracks both authenticated attendees (via `partner_id`) and anonymous visitors (via `visitor_id`). The `_compute_quiz_data` method merges both sources.
4. **Completion gate** — once an attendee submits all answers, `quiz_completed` is set to `True`. Subsequent visits show the score; re-taking requires a reset.

---

## L1 — How Quizzes Are Embedded in Event Tracks

### Quiz Creation Flow

```
Event manager opens event.track form
    ↓
Clicks "Add Quiz" button → opens event.quiz form (action_add_quiz)
    ↓
Enters quiz name + questions with answer choices
    ↓
Each question has exactly ONE correct answer (enforced by @api.constrains)
    ↓
Saves → quiz record linked to track via event_track_id
    ↓
Computed quiz_id, quiz_questions_count auto-populate on track
    ↓
Track page on website shows quiz UI after track content
```

### Attendee Submission Flow

```
Attendee navigates to track page
    ↓
Sees quiz questions rendered via QWeb template
    ↓
Selects one answer per question, clicks Submit
    ↓
JS sends /event_track/quiz/submit JSON-RPC with answer_ids
    ↓
Server validates answer count matches question count
    ↓
Points are summed from awarded_points of chosen answers
    ↓
event.track.visitor record updated: quiz_completed=True, quiz_points=N
    ↓
Result returned: per-question correctness, total points, completion status
```

### Leaderboard Flow

```
Attendee completes a quiz → quiz_points stored on event.track.visitor
    ↓
Leaderboard page aggregates quiz_points across all track.visitor records
    ↓
event.track.visitor read_group sums quiz_points by visitor_id
    ↓
Grouped and ranked by position (1, 2, 3, ...)
    ↓
Current visitor's position calculated and highlighted
    ↓
Paginated display (30 visitors per page)
```

---

## L2 — Field Types, Defaults, Constraints

### `event.quiz` Field Inventory

| Field | Odoo Type | Stored | Default | Notes |
|-------|-----------|--------|---------|-------|
| `name` | Char | Yes | — | Required; translatable |
| `question_ids` | One2many | No | — | `event.quiz.question` records |
| `event_track_id` | Many2one | Yes | — | Parent track; indexed `btree_not_null` |
| `event_id` | Many2one | Yes (related, stored) | — | Related through `event_track_id.event_id` |
| `repeatable` | Boolean | Yes | — | If `True`, attendees can re-take; if `False`, only event managers can reset |

### `event.quiz.question` Field Inventory

| Field | Odoo Type | Stored | Default | Notes |
|-------|-----------|--------|---------|-------|
| `name` | Char | Yes | — | Question text; required; translatable |
| `sequence` | Integer | Yes | — | Ordering |
| `quiz_id` | Many2one | Yes | — | Parent quiz; cascade delete |
| `correct_answer_id` | One2many | No (compute) | — | Computed from `answer_ids.filtered(lambda e: e.is_correct)` |
| `awarded_points` | Integer | No (compute) | — | Sum of all answer `awarded_points` |
| `answer_ids` | One2many | No | — | `event.quiz.answer` records |

### `event.quiz.answer` Field Inventory

| Field | Odoo Type | Stored | Default | Notes |
|-------|-----------|--------|---------|-------|
| `sequence` | Integer | Yes | — | Ordering |
| `question_id` | Many2one | Yes | — | Parent question; cascade delete |
| `text_value` | Char | Yes | — | Answer text; required; translatable |
| `is_correct` | Boolean | Yes | `False` | Exactly one answer per question must be `True` |
| `comment` | Text | Yes | — | Feedback shown after submission; translatable |
| `awarded_points` | Integer | Yes | `0` | Points awarded when this answer is selected |

### `event.track` Quiz Fields (Extensions)

| Field | Odoo Type | Stored | Compute Dependence | Notes |
|-------|-----------|--------|-------------------|-------|
| `quiz_id` | Many2one | No (compute) | `quiz_ids.event_track_id` | First quiz in `quiz_ids` O2M |
| `quiz_ids` | One2many | No | — | `event.quiz` records linked to this track |
| `quiz_questions_count` | Integer | No (compute) | `quiz_id.question_ids` | Count of questions |
| `is_quiz_completed` | Boolean | No (compute) | context-dependent | Visitor/partner state |
| `quiz_points` | Integer | No (compute) | context-dependent | Visitor/partner score |

### `event.track.visitor` Quiz Fields (Extensions)

| Field | Odoo Type | Stored | Default | Notes |
|-------|-----------|--------|---------|-------|
| `quiz_completed` | Boolean | Yes | — | Tracks if visitor has submitted this track's quiz |
| `quiz_points` | Integer | Yes | `0` | Points earned on this track's quiz |

### Constraints

**`@api.constrains` on `event.quiz.question`:**
```python
@api.constrains('answer_ids')
def _check_answers_integrity(self):
    for question in self:
        if len(question.correct_answer_id) != 1:
            raise ValidationError(
                _('Question "%s" must have 1 correct answer to be valid.', question.name))
        if len(question.answer_ids) < 2:
            raise ValidationError(
                _('Question "%s" must have 1 correct answer and at least 1 incorrect answer to be valid.', question.name))
```
This constraint enforces **exactly 1 correct answer** and **at least 2 total answers** before a question can be saved.

**No SQL constraints** in this module.

---

## L3 — Cross-Model Relationships, Override Patterns, Workflow Triggers

### Cross-Model Relationships

| Related Model | Relationship | Direction | Purpose |
|---------------|-------------|-----------|---------|
| `event.track` | One2many → Quiz | Track → quiz | A track holds multiple quiz objects (though UI limits to 1 via `quiz_id` compute) |
| `event.track` | quiz_id (compute) | Track → single quiz | First quiz as singular accessor |
| `event.track` | quiz_ids (O2M) | Track → many quizzes | Raw one2many relation |
| `event.track.visitor` | Fields added | Track visitor → quiz state | Tracks quiz completion and points per attendee |
| `event.event` | Related field | Quiz → event | `event_id` (stored related through `event_track_id`) |
| `website.visitor` | Via track.visitor | Used for leaderboard | Visitor identity for anonymous quiz attempts |
| `res.partner` | Via track.visitor | Used for leaderboard | Partner identity for authenticated quiz attempts |
| `event.quiz.question` | One2many | Quiz → questions | Quiz → questions → answers hierarchy |
| `event.quiz.answer` | One2many (via question) | Question → answers | Answers belong to questions |

### Hierarchy Diagram

```
event.event
    └── event.track
            ├── event.quiz          (one2many → quiz_ids on track)
            │       └── event.quiz.question (one2many)
            │               └── event.quiz.answer (one2many)
            │                       └── is_correct = True/False
            │                       └── awarded_points = N
            └── event.track.visitor (one2many)
                    ├── quiz_completed = True/False
                    └── quiz_points = N
```

### Override Patterns

**Pattern 1: Extending `event.track` with quiz fields**
```python
# models/event_track.py
class EventTrack(models.Model):
    _inherit = 'event.track'

    quiz_id = fields.Many2one('event.quiz', compute='_compute_quiz_id', store=True, ...)
    quiz_ids = fields.One2many('event.quiz', 'event_track_id', ...)
    quiz_questions_count = fields.Integer(compute='_compute_quiz_questions_count', ...)
    is_quiz_completed = fields.Boolean(compute='_compute_quiz_data', ...)
    quiz_points = fields.Integer(compute='_compute_quiz_data', ...)
```
Pure field additions; no method overrides on the base model.

**Pattern 2: Controller prepend-override of `EventTrackController`**
```python
# controllers/event_track_quiz.py
class WebsiteEventTrackQuiz(EventTrackController):
    @http.route('/event_track/quiz/submit', ...)
    def event_track_quiz_submit(self, event_id, track_id, answer_ids):
        # Validate before super()
        # Call parent to fetch track
        # Write quiz_completed + quiz_points
        # Return result dict
```
Uses `sudo()` to access quiz questions/answers that may not be accessible to public users.

**Pattern 3: `_compute_quiz_data` with public-user fallback**
```python
if self.env.user._is_public() and not current_visitor:
    for track in tracks_quiz:
        track.is_quiz_completed = False
        track.quiz_points = 0
else:
    # Normal case: look up via partner_id or visitor_id
```
The method explicitly handles the anonymous visitor case, defaulting to uncompleted/no points rather than raising an access error.

**Pattern 4: Extending `event.track.visitor` with new fields**
```python
# models/event_track_visitor.py
class EventTrackVisitor(models.Model):
    _inherit = 'event.track.visitor'
    quiz_completed = fields.Boolean('Completed')
    quiz_points = fields.Integer("Quiz Points", default=0)
```
Simple field addition; no method overrides.

**Pattern 5: Community controller override**
```python
# controllers/community.py
class WebsiteEventTrackQuizCommunityController(EventCommunityController):
    @http.route()
    def community(self, event, **kwargs):
        values = self._get_community_leaderboard_render_values(...)
        return request.render('website_event_track_quiz.event_leaderboard', values)
```
Overrides the `community` route to redirect all community views to the quiz leaderboard template.

### Workflow Triggers

| Trigger | Mechanism | Result |
|---------|-----------|--------|
| **Quiz submission** | HTTP POST to `/event_track/quiz/submit` JSON-RPC | Sets `quiz_completed=True`, `quiz_points=N` on visitor record |
| **Quiz reset** | HTTP POST to `/event_track/quiz/reset` | Clears `quiz_completed` and `quiz_points`; allows re-take |
| **Track page load** | `_compute_quiz_data` evaluates at read time | Shows completion state and points for current user/visitor |
| **Leaderboard page load** | `/event/<id>/community/leaderboard` | `read_group` aggregates quiz points by visitor |
| **Adding quiz to track** | "Add Quiz" button → `action_add_quiz` | Opens quiz creation form with `default_event_track_id` pre-filled |
| **Event date change** | Computed fields re-evaluate when dates change | No direct quiz effect; track state changes independently |

### Quiz Reset Permission Logic

```
User requests /event_track/quiz/reset
    ↓
Check: request.env.user.has_group('event.group_event_manager')?
    ↓ YES → Reset allowed
    ↓ NO  → Check: track.quiz_id.repeatable?
              ↓ YES → Reset allowed
              ↓ NO  → Forbidden (HTTP 403)
```

This means event managers can always reset any quiz, while regular attendees can only reset if the quiz has `repeatable=True`.

---

## L4 — Odoo 18 → 19 Changes, Performance

### Odoo 18 → 19 Changes

Based on source analysis:

| Change | Detail |
|--------|--------|
| **`event.track` quiz fields use `Domain` class** | The `_compute_quiz_data` method uses `Domain.AND(...)` from `odoo.fields` for building complex search domains. This was already in use in Odoo 18 for this module. |
| **`readonly=True` on `event_track_id`** | The `event_track_id` field on `event.quiz` is `readonly=True` in the form view (set in XML). In Odoo 19, this prevents moving a quiz between tracks after creation. |
| **`index='btree_not_null'` on `event_track_id`** | The index on the FK to `event.track` is a partial index excluding NULL values, making lookups by track efficient without penalizing quiz records not yet linked to a track. |
| **Leaderboard via `_read_group`** | The leaderboard uses `sudo()._read_group(...)` to aggregate `quiz_points:sum` grouped by `visitor_id`, which is the Odoo 17+ pattern. |
| **No breaking API changes** | The quiz submission/reset endpoints remain `type="jsonrpc"` with `auth="public"` and `website=True`. |
| **`_get_quiz_answers_details` returns full answer objects** | The method returns the ORM records directly (not just IDs), and the controller maps them to a result dict in the response. |

### Performance Considerations

| Area | Analysis |
|------|----------|
| **`_compute_quiz_data` complexity** | This compute depends on `quiz_id`, `event_track_visitor_ids`, plus all visitor fields, and `uid` via `depends_context`. For tracks with many visitor records, the `search_read` on `event.track.visitor` could become expensive. `sudo()` is used correctly to bypass ACL. |
| **`_compute_quiz_data` re-evaluated per request** | The compute is not stored (`store=False`). For public users with no visitor, this cheap-paths immediately. For authenticated users, it always runs the visitor lookup. |
| **Leaderboard `read_group` on all event tracks** | `read_group` with `visitor_id` as groupby and `quiz_points:sum` as aggregate executes a single SQL `GROUP BY` query against `event_track_visitor` filtered by the event's tracks. For large events with thousands of attendees, the query is efficient (single DB round-trip). |
| **Pagination on leaderboard** | The leaderboard limits display to 30 visitors per page, reducing the data returned. `top3_visitors` is pre-sliced from the full leaderboard list in Python. |
| **Constraint on every answer check** | `_check_answers_integrity` runs on every write to `answer_ids`. The `len()` calls on filtered recordsets are cheap. |
| **Answer lookup on submit** | `search([('id', 'in', answer_ids)])` fetches all submitted answers in one query. Then `mapped('question_id')` is efficient (single JOIN). |
| **No N+1 in quiz submission** | The controller fetches all answers in one `search()`, then maps question IDs and points in memory. No per-answer database round-trips. |

### Security Notes

| Aspect | Implementation |
|--------|----------------|
| **Public submission** | `/event_track/quiz/submit` uses `auth="public"` — any website visitor can submit answers. Points are tracked against their `visitor_id` or `partner_id`. |
| **`sudo()` for answer lookup** | `self._get_quiz_answers_details(track_sudo, ...)` uses `track.sudo()` to fetch questions/answers that may not be accessible to the public. This is safe because the data is read-only in this context. |
| **Reset permission gate** | The `quiz_reset` endpoint raises `Forbidden()` via `werkzeug.exceptions.Forbidden` if a non-manager tries to reset a non-repeatable quiz. |
| **ACL** | `ir.model.access.csv` grants `base.group_user` (internal users) CRUD on `event.quiz`, `event.quiz.question`, and `event.quiz.answer`. Public users get no direct ORM access. |
| **`create=False` in quiz action** | The `action_add_quiz` window action sets `context: {'create': False}` — prevents creating a quiz from scratch outside the track form. New quizzes are created via the track form's button. |
| **Leaderboard visibility** | The leaderboard is public (`auth="public"`). Any website visitor can see all attendee scores. No personal data beyond display name is exposed. |

---

## Related Models

| Model | Module | Relationship |
|-------|--------|--------------|
| `event.track` | `website_event_track` | Extended with quiz fields |
| `event.track.visitor` | `website_event_track` | Extended with quiz fields |
| `event.quiz` | This module | Primary quiz container |
| `event.quiz.question` | This module | Question definitions |
| `event.quiz.answer` | This module | Answer options per question |
| `event.event` | `event` | Extended `_compute_community_menu` |
| `website.visitor` | `website_livechat` / `website` | Used for anonymous quiz tracking |
| `res.partner` | `base` | Used for authenticated attendee tracking |

## See Also

- [Modules/website_event_track](website_event_track.md) — Base event track module
- [Modules/website_event_track_live](website_event_track_live.md) — Live streaming for event tracks
- [Modules/event](event.md) — Event management core
- [Core/Fields](Fields.md) — One2many, Many2one, computed fields, constraints
- [Core/API](API.md) — @api.depends, @api.constrains, @api.depends_context
