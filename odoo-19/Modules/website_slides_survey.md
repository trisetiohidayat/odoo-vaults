---
type: module
module: website_slides_survey
tags: [odoo, odoo19, website, elearning, slides, certification, survey, gamification]
created: 2026-04-11
l4: true
---

# website_slides_survey — Course Certifications (L4 Depth)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Course Certifications |
| **Technical Name** | `website_slides_survey` |
| **Category** | Website/eLearning |
| **Version** | 1.0 |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Application** | No |
| **Auto Install** | Yes |

## Description

This module bridges `website_slides` and `survey` to add certification capabilities to eLearning courses. A certification is a `survey.survey` (with `certification = True`) embedded as a `slide.slide` with `slide_category = 'certification'`. Learners who score at or above `scoring_success_min` on the survey earn the certification. Failed attempts with no remaining attempts result in automatic course unenrollment.

## Dependencies

| Dependency | Type | Role |
|-----------|------|------|
| `website_slides` | Hard | Course, slide, and channel models |
| `survey` | Hard | Survey/quiz/certification model |

Both are marked `auto_install = True`, so installing either `website_slides` or `survey` automatically pulls in `website_slides_survey`.

## Module Structure

```
website_slides_survey/
├── __init__.py              # Imports models + controllers; defines uninstall_hook
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── slide_channel.py      # slide.channel, slide.channel.partner extensions
│   ├── slide_slide.py        # slide.slide, slide.slide.partner extensions
│   ├── survey_survey.py      # survey.survey extension
│   └── survey_user.py        # survey.user_input extension
├── controllers/
│   ├── __init__.py
│   ├── slides.py             # Main integration: certification URL, create_slide override
│   ├── survey.py             # Survey finish/retry with slide context
│   └── website_profile.py    # Certification tab on user profile
├── security/
│   ├── ir.model.access.csv   # Read-only ACLs for slide channel officers
│   └── website_slides_survey_security.xml  # ir.rule records
├── views/
│   ├── slide_channel_partner_views.xml
│   ├── slide_channel_views.xml
│   ├── slide_slide_partner_views.xml
│   ├── slide_slide_views.xml
│   ├── survey_survey_views.xml
│   ├── website_slides_menu_views.xml
│   ├── website_slides_templates_course.xml
│   ├── website_slides_templates_lesson.xml
│   ├── website_slides_templates_lesson_fullscreen.xml
│   ├── website_slides_templates_homepage.xml
│   ├── website_slides_templates_utils.xml
│   ├── survey_templates.xml
│   ├── website_profile.xml
│   └── res_config_settings_views.xml
└── data/
    ├── gamification_data.xml         # Badge + goal definition
    ├── mail_template_data.xml        # Certification failure email
    ├── survey_demo.xml
    ├── slide_slide_demo.xml
    └── survey.user_input.line.csv
```

---

## Models

All four model files contain extensions (no standalone models). Inheritance pattern is `_inherit` (classic extension).

---

### `slide.channel` — Course Model Extension

**File:** `models/slide_channel.py`
**Inheritance:** Classic (`_inherit = 'slide.channel'`)

#### Fields Added

| Field | Type | Stored | Description |
|-------|------|--------|-------------|
| `members_certified_count` | Integer | No | Computed count of channel members with `survey_certification_success = True`. Recomputes on any `slide.channel.partner` change. |
| `nbr_certification` | Integer | Yes | Count of slides in this channel with `slide_category = 'certification'`. Derived from `_compute_slides_statistics` (shared with `slide.slide`). |

#### Methods

##### `_compute_members_certified_count()`
```
@api.depends('channel_partner_ids')
def _compute_members_certified_count(self)
```
Uses `_read_group` with `sudo()` on `slide.channel.partner` to count members where `survey_certification_success = True`. The `sudo()` is necessary because slide channel officers may not have direct read access to partner records in the channel.

**Performance implication:** Uses `_read_group` aggregation (single SQL query) rather than `search_count`, avoiding N+1.

##### `action_redirect_to_certified_members()`
Returns the standard member action window (`action_redirect_to_members('certified')`) filtered to certified members. Sets contextual help message: *"No Attendee passed this course certification yet!"*.

##### `_remove_membership(partner_ids)`
```python
def _remove_membership(self, partner_ids)
```
Overrides the parent method. Before calling `super()`, it clears `slide_partner_id` from all `survey.user_input` records linked to `slide.slide.partner` entries being removed. This is critical — it prevents stale FK violations and ensures that re-enrollment starts a fresh attempt pool (each enrollment creates new `slide_partner_id` records, each with its own `invite_token` batch).

**Edge case:** Uses `Domain.OR(...)` over all channels in `self` to build a single efficient search query for all affected `slide_partner_id` records across all channels being processed in one call.

---

### `slide.channel.partner` — Course Membership Extension

**File:** `models/slide_channel.py`
**Inheritance:** Classic (`_inherit = 'slide.channel.partner'`)

#### Fields Added

| Field | Type | Stored | Description |
|-------|------|--------|-------------|
| `nbr_certification` | Integer | No | Related field: `channel_id.nbr_certification`. Used to conditionally show `survey_certification_success` in tree view (invisible when zero). |
| `survey_certification_success` | Boolean | Yes | Set to `True` by `_recompute_completion()` when any certification slide in the course is passed (`survey_scoring_success = True`). Never reset automatically (would require explicit re-attempt and failure). |

**Workflow:** This field is the authoritative "has this learner passed this course's certification" flag. It is set in `_recompute_completion` in `slide_slide.py` and is the basis for `members_certified_count` on the channel.

---

### `slide.slide.partner` — Slide Membership Extension

**File:** `models/slide_slide.py`
**Inheritance:** Classic (`_inherit = 'slide.slide.partner'`)

#### Fields Added

| Field | Type | Stored | Description |
|-------|------|--------|-------------|
| `user_input_ids` | One2many | No | All `survey.user_input` records linked to this slide membership via `slide_partner_id`. Used to track certification attempts. `index='btree_not_null'` on the inverse `slide_partner_id` speeds up deletions. |
| `survey_scoring_success` | Boolean | Yes | `True` if at least one `user_input_ids` record has `scoring_success = True`. |

#### Methods

##### `_compute_survey_scoring_success()`
```
@api.depends('partner_id', 'user_input_ids.scoring_success')
def _compute_survey_scoring_success(self)
```
Searches for any `survey.user_input` with `scoring_success = True` linked to this `slide_partner_id`. Sets `True` if found, `False` otherwise. Runs `sudo()` to bypass access restrictions on user inputs.

**Critical design:** This is a stored `Boolean` (not computed on the fly). Once a learner passes the certification, `survey_scoring_success` stays `True` even if the passed survey user input is later deleted. This matches the semantics of "passed at least once."

##### `_compute_field_value(field)` — Side Effect
When the computed field `survey_scoring_success` evaluates to `True`, it immediately writes `completed = True` on the `slide.slide.partner` record. This is triggered via `super()._compute_field_value()` — the base model's ORM hook fires for every computed field, and this override specifically handles the certification case.

**Edge case:** This means passing a certification simultaneously marks the slide as completed for the learner. The `completed` flag on `slide.slide.partner` controls course completion progress.

##### `_recompute_completion()`
Called by the base `website_slides` module to recompute completion state after slide interactions. This override:
1. Calls `super()` to run base completion logic.
2. Filters slides where `survey_scoring_success == True`.
3. Builds a domain for all `(partner_id, channel_id)` pairs of those slides.
4. Searches for `slide.channel.partner` records where `survey_certification_success == False` AND the pair matches — sets them to `True`.

**This is the actual certification propagation:** The slide-level success bubbles up to the channel membership level, which is what drives `members_certified_count` on the channel and the "Certified" badge on the course overview.

---

### `slide.slide` — Slide Model Extension

**File:** `models/slide_slide.py`
**Inheritance:** Classic (`_inherit = 'slide.slide'`)

#### Fields Added / Modified

| Field | Modification | Description |
|-------|-------------|-------------|
| `slide_category` | Selection extended | Added `'certification'` as a new category. `ondelete='set default'` — if a certification slide is deleted, category resets to default (probably `'document'`). |
| `slide_type` | Selection extended | Added `'certification'` as a new slide type. `ondelete='set null'` — type becomes `NULL` if the certification slide category is removed. |
| `survey_id` | New field | `Many2one('survey.survey')`. `index='btree_not_null'` — index on survey FK. Required for certification slides (enforced by `_check_survey_id` constraint). |
| `nbr_certification` | New field | Integer, stored. Count of certification slides in the same channel (from `_compute_slides_statistics`). |
| `is_preview` | Override (compute+store) | Force-set to `False` for certification slides. Cannot be previewed — enforced by both DB constraint `_check_certification_preview` and `_compute_is_preview`. |
| `name` | Override (compute+store) | Auto-fills from `survey_id.title` if `name` is empty. |

#### Constraints Added

```python
_CHECK_SURVEY_ID = models.Constraint(
    "CHECK(slide_category != 'certification' OR survey_id IS NOT NULL)",
    "A slide of type 'certification' requires a certification.",
)
_CHECK_CERTIFICATION_PREVIEW = models.Constraint(
    "CHECK(slide_category != 'certification' OR is_preview = False)",
    'A slide of type certification cannot be previewed.',
)
```

Both are DB-level constraints protecting data integrity against direct SQL writes.

#### Methods

##### `_compute_mark_complete_actions()`
Sets `can_self_mark_completed = False` and `can_self_mark_uncompleted = False` for certification slides. This prevents manual "mark complete" on a certification — it can only be completed by passing the survey.

##### `_compute_is_preview()`
Forces `is_preview = False` whenever `slide_category == 'certification'`. Also forces `False` if already `False` (irreversible for certification).

##### `_compute_slide_icon_class()`
Sets icon class to `'fa-trophy'` for certification slides (trophy font icon in the slides list).

##### `_compute_slide_type()`
Sets `slide_type = 'certification'` whenever `slide_category == 'certification'`.

##### `create(vals_list)` — `@api.model_create_multi`
1. Calls `super().create()`.
2. For each created slide with a `survey_id`: sets `slide_category = 'certification'` and calls `_ensure_challenge_category()`.

This means setting `survey_id` on any slide automatically upgrades it to a certification slide.

##### `write(vals)`
1. Captures `old_surveys = self.mapped('survey_id')` before the write.
2. Executes `super().write(vals)`.
3. If `survey_id` changed: calls `_ensure_challenge_category(old_surveys=old_surveys - new_surveys)`.

**Edge case:** The set subtraction `old_surveys - self.mapped('survey_id')` gives surveys that were removed from the slide. Only those are passed as `old_surveys` to reset their challenge category to `'certification'`.

##### `unlink()`
Captures old surveys, calls `super().unlink()`, then resets challenge category to `'certification'` for deleted surveys.

##### `_ensure_challenge_category(old_surveys=None, unlink=False)`
Manages the `challenge_category` of the badge challenges linked to surveys:

- **Slide created/updated with survey:** sets `challenge_category = 'slides'` on the badge's challenges. This makes the badge appear in the "Certification Badges" section on the ranks/badges page.
- **Slide deleted or survey unlinked:** resets `challenge_category = 'certification'` on the old badge's challenges. This moves them back to the "normal" certification badge section.

**L4 insight:** This is the gamification integration point. The `survey.survey` model has a `certification_badge_id` (One2one to `gamification.badge`). When a certification slide is linked, that badge's challenges get their category switched from `'certification'` to `'slides'`, routing them to the course badge page. This happens at slide write time, not at certification completion time.

##### `_generate_certification_url()`
```python
def _generate_certification_url(self) -> dict[int, str]
```
Returns a dict mapping `slide.id` to the survey start URL. Three scenarios:

1. **Member with existing `user_input_ids`:** Returns URL from the most recent user input (sorted by `create_date` descending). Reuses the same attempt.
2. **Member with no existing attempts:** Creates a new `survey.user_input` via `survey_id._create_answer()` with `check_attempts=False`, `slide_partner_id=user_membership_id_sudo.id`, and a freshly generated `invite_token`. Returns start URL.
3. **Non-member:** Creates a test entry (`test_entry=True`) with no `slide_partner_id`. No membership needed; allows preview of the certification.

**`invite_token` generation:** Each enrollment creates a distinct `invite_token` batch via `survey.user_input._generate_invite_token()`. This allows the system to track "attempts since last enrollment" separately from total attempts. The `_check_for_failed_attempt()` method uses `survey_id._has_attempts_left()` to determine if the user's current batch of attempts (grouped by `invite_token`) has remaining tries.

---

### `survey.survey` — Survey Model Extension

**File:** `models/survey_survey.py`
**Inheritance:** Classic (`_inherit = 'survey.survey'`)

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `slide_ids` | One2many(`slide.slide`, `survey_id`) | All slides linked to this survey as certifications. |
| `slide_channel_ids` | One2many(`slide.channel`) computed | Courses that have at least one slide linked to this survey. Used in UI to show course context. |
| `slide_channel_count` | Integer computed | Count of distinct courses. |

#### Methods

##### `_compute_slide_channel_data()`
Maps `survey.slide_ids.mapped('channel_id')` to get unique channels. Both fields recompute whenever a linked slide's `channel_id` changes.

##### `_unlink_except_linked_to_course()` — `@api.ondelete(at_uninstall=False)`
Prevents deletion of any `survey.survey` that is linked to a certification slide (`slide_type == 'certification'`). Raises `ValidationError` with a detailed message listing all courses that use the survey.

**`at_uninstall=False`:** This constraint is NOT enforced during module uninstall — only during normal operation. This allows cleanup scripts and module removal to proceed.

**Security note:** Uses `sudo()` to fetch certification names because a slide channel officer deleting a survey might not have access to the survey record itself.

##### `action_survey_view_slide_channels()`
Returns an action window for the related courses. If only one course uses the survey, opens directly in form view. If multiple courses use it, opens a list view filtered to those courses.

##### `_prepare_challenge_category()`
Checks if any slide exists with `survey_id = self.id`. Returns `'slides'` if yes (badge should appear on course ranks/badges page), `'certification'` otherwise (default behavior for standalone certifications not linked to a course).

---

### `survey.user_input` — Survey Response Extension

**File:** `models/survey_user.py`
**Inheritance:** Classic (`_inherit = 'survey.user_input'`)

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `slide_id` | Many2one(`slide.slide`) | The certification slide this user input is associated with. Set even for non-members (test entries). |
| `slide_partner_id` | Many2one(`slide.slide.partner`) | The slide membership record. Only set for enrolled members. `index='btree_not_null'` enables efficient FK-based deletion in the slide partner model. |

Both fields use `check=False` implicitly (no `ondelete` specified means `CASCADE` is typical for Many2one, but since these are informational links, explicit cascade is not required for business logic).

#### Hooked Methods

##### `create(vals_list)` — `@api.model_create_multi`
After creating records, calls `self._check_for_failed_attempt()`.

##### `write(vals)`
After writing, if `'state'` is in `vals`, calls `self._check_for_failed_attempt()`. Triggered when state changes to `'done'` (survey submitted).

#### `_check_for_failed_attempt()`
This is the core certification failure and unenrollment logic. It fires when:
- A `survey.user_input` is created with `state = 'done'` (immediate submit), OR
- An existing `user_input` transitions to `state = 'done'`.

**Algorithm:**

```
1. Search all inputs in self where state=done AND scoring_success=False AND slide_partner_id!=False
2. For each failed input:
   a. Call survey_id._has_attempts_left(partner, email, invite_token)
      - If True (attempts remain): skip (user can retry)
      - If False (no attempts left): proceed to unenroll
   b. Send failure email via mail_template_user_input_certification_failed
   c. Collect (partner, channel) pairs to unenroll
3. Call channel._remove_membership(partner_ids) for collected pairs
```

**`_has_attempts_left()`** checks the `invite_token` grouping — meaning only attempts with the same `invite_token` count toward the limit. New enrollment creates a new `invite_token` batch, giving the learner a fresh set of attempts. This is the "re-enroll and retry" pattern.

**Edge cases:**
- Multiple failed attempts across different channels: each channel's `_remove_membership` is called separately.
- A user who is enrolled in multiple courses with the same certification survey: each `slide_partner_id` is handled independently (the survey could be embedded in multiple courses).
- Test entries (`test_entry=True`) have no `slide_partner_id`, so they never trigger unenrollment.

---

## Controllers

Three controller classes extend `website_slides` and `survey` controllers.

---

### `WebsiteSlidesSurvey` (extends `WebsiteSlides`)

**File:** `controllers/slides.py`

#### `slide_get_certification_url()`
```
@http.route('/slides_survey/slide/get_certification_url', auth='user', website=True)
def slide_get_certification_url(self, slide_id, **kw)
```
1. Fetches the slide via `_fetch_slide()` (checks membership, access).
2. If the user is a channel member, calls `action_set_viewed()` to mark the slide as viewed.
3. Generates the certification URL via `slide._generate_certification_url()`.
4. Redirects to the survey start URL.

**Auth:** `'user'` means authenticated user. Portal users count as `'user'` with limited access.

#### `slides_certification_search_read()`
```
@http.route('/slides_survey/certification/search_read', auth='user',
            methods=['POST'], type='jsonrpc', website=True)
def slides_certification_search_read(self, fields)
```
JSONRPC endpoint for the frontend to fetch available certifications. Returns `survey.survey` records where `certification = True`. Also returns whether the current user can create new surveys (`has_access('create')`).

#### `create_slide()` — Override
Intercepts slide creation via the course editor. When `slide_category == 'certification'`:

1. **New survey:** If `post['survey']` has no `id`, checks `create` access on `survey.survey`, then creates a survey with pre-filled certification settings:
   - `questions_layout = 'page_per_question'`
   - `is_attempts_limited = True`, `attempts_limit = 1`
   - `scoring_type = 'scoring_without_answers'`
   - `certification = True`
   - `scoring_success_min = 70.0`
   - `certification_mail_template_id = survey.mail_template_certification`

2. **Existing survey:** If `post['survey']['id']` is provided, reads it to verify access, then links it.

3. **Redirect URL:** For certification slides, returns URL pointing to the slide in fullscreen mode.

**Important:** The survey creation happens BEFORE the slide creation in `super()`, because the slide's `_check_survey_id` constraint requires `survey_id` to be present.

#### `_slide_mark_completed(slide)` — Override
Raises `Forbidden` for certification slides. Certifications cannot be manually marked complete — only the survey result triggers completion.

#### `_get_valid_slide_post_values()` — Override
Adds `'survey_id'` to the list of accepted POST values when creating/editing slides.

#### `_prepare_user_slides_profile(user)` — Override
Adds `certificates` to profile values by calling `_get_users_certificates()`.

#### `_prepare_all_users_values(users)` — Override
Adds `certification_count` to each user's values dict for the public user directory.

#### `_get_users_certificates(users)`
Searches for `survey.user_input` records where:
- `slide_partner_id.partner_id` matches any user in the input set
- `scoring_success = True`
- `slide_partner_id.survey_scoring_success = True`

Returns a dict: `{user_id: [certificate_records]}`.

#### `_prepare_ranks_badges_values(**kwargs)` — Override
Filters and reorganizes badges for the ranks/badges page:
1. Searches `gamification.badge` linked to a `survey_id` (certification badges).
2. Filters to only those with `challenge_category = 'slides'` (course-linked badges).
3. Sorts by `granted_users_count` descending.
4. Looks up the course URL for each badge by finding the certification slide's channel.
5. Adds `certification_badges`, `certification_badge_urls` to template values.

---

### `Survey` (extends `survey.controllers.main.Survey`)

**File:** `controllers/survey.py`

#### `_prepare_survey_finished_values(survey, answer, token=False)` — Override
Adds `channel_id` to the finished survey template context when `answer.slide_id` is set. This enables the "Go back to course" button in the completion template.

#### `_prepare_retry_additional_values(answer)` — Override
Preserves `slide_id` and `slide_partner_id` on the retry answer so the retry maintains the course context and attempt tracking.

---

### `WebsiteSlidesSurvey` (extends `WebsiteProfile`)

**File:** `controllers/website_profile.py`

#### `_prepare_user_profile_values(user, **kwargs)` — Override
Loads the certification tab data for the user's profile page:

- `show_certification_tab = True` only if: viewing own profile OR `group_survey_manager`.
- Domain: `survey_id.certification = True` AND `state = 'done'` AND (matching email OR matching partner_id).
- If `certification_search` kwarg present: adds ILIKE filter on `survey_id.title`.

---

## Security

### ACL (`ir.model.access.csv`)

| ID | Model | Group | R | W | C | D |
|----|-------|-------|---|---|---|---|
| `access_survey_slides_officer` | `survey.survey` | `website_slides.group_website_slides_officer` | 1 | 0 | 0 | 0 |
| `access_survey_question_slides_officer` | `survey.question` | same | 1 | 0 | 0 | 0 |
| `access_survey_question_answer_slides_officer` | `survey.question_answer` | same | 1 | 0 | 0 | 0 |
| `access_survey_user_input_slides_officer` | `survey.user_input` | same | 1 | 0 | 0 | 0 |
| `access_survey_user_input_line_slides_officer` | `survey.user_input_line` | same | 1 | 0 | 0 | 0 |

All are **read-only** for slide channel officers. They can view survey questions and answers for certification slides but cannot modify them.

### Record Rules (`website_slides_survey_security.xml`)

Five `ir.rule` records, all scoped to `website_slides.group_website_slides_officer`:

| Rule | Model | Scope |
|------|-------|-------|
| `survey_rule_slide_channel_officer` | `survey.survey` | `certification = True` AND survey_type in (`survey`, `live_session`, `assessment`, `custom`) AND (no user restriction OR user in restrict_user_ids) |
| `survey_question_rule_slide_channel_officer` | `survey.question` | Same scope via `survey_id` |
| `survey_question_answer_slide_channel_officer` | `survey.question_answer` | Scope via `question_id.survey_id` OR `matrix_question_id.survey_id` |
| `survey_user_input_rule_slide_channel_officer` | `survey.user_input` | Scope via `survey_id` |
| `survey_user_input_line_rule_slide_channel_officer` | `survey.user_input_line` | Scope via `survey_id` |

All rules set `perm_write = 0`, `perm_create = 0`, `perm_unlink = 0` — pure read access.

---

## Gamification Integration

### Badge Goal Definition

**File:** `data/gamification_data.xml`

The `website_slides.badge_data_certification_goal` goal definition (created by `website_slides`) is modified:
- **Default domain** (from `website_slides`): `[('completed', '=', True)]` — any completed slide.
- **Modified domain** (after `website_slides_survey` installed): `[('survey_scoring_success', '=', True), ('slide_id.slide_category', '=', 'certification')]` — only certification slides with passed survey.

This means badges/ranks are earned by passing certification surveys, not just viewing slides.

### Badge Challenge Category Switch

When a slide is linked to a survey that has a certification badge:
- `slide.slide._ensure_challenge_category()` sets the badge's `challenge_category = 'slides'`.
- This causes the badge to appear in the course ranks/badges page (in the "Certification Badges" section, separate from normal badges).
- When unlinked: resets to `'certification'` (normal certification badge page).

---

## Certification Flow (End-to-End)

```
Learner Enrolls
      │
      ▼
[slide.channel.partner] created
      │
      ▼
Learner Views Course (all content)
      │
      ▼
Learner Clicks "Begin Certification"
  → /slides_survey/slide/get_certification_url
  → action_set_viewed() marks slide viewed
  → _generate_certification_url()
    └─ Creates survey.user_input (slide_partner_id set, invite_token generated)
      │
      ▼
Learner Takes Survey
  → Survey answered and submitted
  → survey.user_input state → 'done'
  → _check_for_failed_attempt() triggered
      │
      ├── scoring_success == True
      │     └─ survey_slide_partner.survey_scoring_success = True  (computed)
      │           └─ _compute_field_value: completed = True
      │                 └─ _recompute_completion()
      │                       └─ slide.channel.partner.survey_certification_success = True
      │                             └─ members_certified_count recomputes
      │                                   └─ Badge awarded (via gamification)
      │
      └── scoring_success == False
            └─ _has_attempts_left()?
                  ├─ True:  User can retry (same invite_token batch)
                  └─ False: _remove_membership() called
                              └─ slide_partner_id cleared on user_inputs
                              └─ Failure email sent
                              └─ Partner unenrolled
                                    └─ Must re-enroll to get fresh attempts
```

---

## Key Design Patterns

### Attempt Pooling via `invite_token`
Each course enrollment creates a fresh `invite_token` for the certification survey. The survey's `attempts_limit` counts only within the same token batch. Re-enrollment grants a new batch. This prevents learners from being permanently locked out after failing an old attempt.

### Completion Cascade
`survey.user_input` (done, success) → `slide.slide.partner.survey_scoring_success` → `slide.slide.partner.completed` → `slide.channel.partner.survey_certification_success`. Three stored fields ensure this state survives record deletion at lower levels.

### sudo() Usage
Used in `_compute_members_certified_count()` (officer needs to see partner records) and `_compute_survey_scoring_success()` (survey scoring may be restricted). Never used in `slide_partner_id` writes where partner context matters.

### Certification Cannot Be Previewed
`is_preview = False` is forced for all certification slides (both via `_compute_is_preview` and `_check_certification_preview` DB constraint). Non-members can still take a test entry but cannot preview the slide in the course sidebar before enrollment.

---

## Uninstall Hook

```python
def uninstall_hook(env):
    dt = env.ref('website_slides.badge_data_certification_goal', raise_if_not_found=False)
    if dt:
        dt.domain = "[('completed', '=', True), (0, '=', 1)]"
```

Resets the gamification goal definition back to the base `website_slides` default, which only checks `completed = True` (no survey fields). The `(0, '=', 1)` is a dummy condition that always evaluates false, keeping the domain technically valid but inactive for certification-specific logic.

---

## Performance Considerations

| Operation | Concern |
|-----------|---------|
| `_compute_members_certified_count()` | Uses `_read_group` — single aggregate SQL, not N+1. |
| `_compute_survey_scoring_success()` | Searches `survey.user_input` per `slide_partner_id`. With many attempts per user, consider adding a `slide_partner_id` index on `survey.user_input` (already done via `index='btree_not_null'` on `slide_partner_id`). |
| `_get_users_certificates()` | Searched in sudo with no domain limit on partner_ids — fetches all success records for all requested users. For large user lists this can be expensive. Called only on profile/ranking pages. |
| `_check_for_failed_attempt()` | Searches `survey.user_input` with `state='done'`, `scoring_success=False`, `slide_partner_id!=False` on every create and state-write. With high-volume certification attempts, consider batching or async. |

---

## L4 Insights: Odoo 18 → 19 Changes

Based on code patterns in Odoo 19:
- The `Domain` class from `odoo.fields` is used throughout (Odoo 16+ introduced `Domain` as a proper type for expression building).
- The `_has_attempts_left()` method on `survey.survey` is called with an explicit `invite_token` parameter — this allows per-enrollment attempt counting (introduced when the re-enrollment retry pattern was stabilized).
- The `at_uninstall=False` on `_unlink_except_linked_to_course` avoids uninstall blocking — a necessary pattern when modules may need to be removed for migration purposes.
- `challenge_category = 'slides'` routing for course-linked certification badges is an Odoo 18/19 pattern that separates course-earned badges from standalone certification badges.

---

## Related Models Summary

| Model | Role in module |
|-------|---------------|
| `slide.channel` | Course container. Holds `members_certified_count` and `nbr_certification`. |
| `slide.channel.partner` | Membership. Holds `survey_certification_success`. |
| `slide.slide` | Slide content. Adds `survey_id` and `slide_category='certification'`. |
| `slide.slide.partner` | Slide attendance. Holds `survey_scoring_success` and `user_input_ids`. |
| `survey.survey` | Certification exam. Linked to slide via `slide.slide.survey_id`. |
| `survey.user_input` | Attempt record. Holds `slide_id` and `slide_partner_id` for context. |
| `gamification.badge` | Awarded on certification pass. `challenge_category` routes to course badge page. |
| `gamification.goal.definition` | Goal domain triggers badge award. Modified to require `survey_scoring_success`. |

---

## Related Documentation

- [Modules/website_slides](odoo-18/Modules/website_slides.md) — Full eLearning course management (slides, channels, karma, ratings)
- [Modules/survey](odoo-18/Modules/survey.md) — Survey/quiz/certification engine (questions, scoring, certification badges)
- [Patterns/Workflow Patterns](odoo-18/Patterns/Workflow Patterns.md) — State machine patterns used by orders, pickings, and courses
- [Patterns/Security Patterns](odoo-18/Patterns/Security Patterns.md) — ACL CSV and ir.rule configuration demonstrated here
