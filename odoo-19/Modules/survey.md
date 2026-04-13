---
type: module
module: survey
tags: [odoo, odoo19, survey, quiz, assessment, certification, scoring, gamification, live-session]
created: 2026-04-11
updated: 2026-04-11
---

# Survey Module (survey)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Surveys |
| **Technical Name** | `survey` |
| **Category** | Marketing/Surveys |
| **Version** | 19.0 (manifest v3.7) |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Website** | https://www.odoo.com/app/surveys |
| **Application** | Yes |
| **Sequence** | 220 |

## Description

The Survey module enables creation of professional surveys, quizzes, assessments, and certifications. It supports multi-page surveys with various question types, conditional logic, scoring, live sessions, and certification with badges. Respondents access surveys via public links or personalized invitations with token-based tracking.

---

## Dependencies

| Dependency | Module | Purpose |
|------------|--------|---------|
| `auth_signup` | auth_signup | User self-registration for survey participants |
| `http_routing` | web | Website routing and URL management |
| `mail` | mail | Email notifications and messaging |
| `web_tour` | web_tour | Interactive onboarding tours |
| `gamification` | gamification | Badges and challenges for certifications |

---

## Models Inventory

| Model | Technical Name | Description |
|-------|----------------|-------------|
| Survey | `survey.survey` | Survey template with settings, pages, and questions |
| Question | `survey.question` | Questions AND pages (same model, `is_page` distinguishes) |
| Question Answer | `survey.question.answer` | Answer options for choice questions and matrix rows |
| User Input | `survey.user_input` | Single survey attempt/response session |
| User Input Line | `survey.user_input.line` | Individual answer per question |
| Survey Invite | `survey.invite` | Transient wizard for sending survey invitations |
| Certification Badge | `gamification.badge` | Certification badges (extended via badge.py) |
| Certification Challenge | `gamification.challenge` | Challenge category `certification` added |

---

## survey.survey

**File:** `~/odoo/odoo19/odoo/addons/survey/models/survey_survey.py`
**Inherits:** `mail.thread`, `mail.activity.mixin`
**Order:** `create_date DESC`
**Rec Name:** `title`

### L1 — All Field Signatures

```python
# --- Identification ---
title = fields.Char('Survey Title', required=True, translate=True)
color = fields.Integer('Color Index', default=0)  # Kanban color
active = fields.Boolean("Active", default=True)

# --- Localization ---
lang_ids = fields.Many2many(
    'res.lang', string='Languages',
    default=lambda self: self.env['res.lang']._lang_get(
        self.env.context.get('lang') or self.env['res.lang'].get_installed()[0][0]),
    domain=lambda self: [('id', 'in', [lang.id for lang in self.env['res.lang']._get_active_by('code').values()])],
    help="Leave the field empty to support all installed languages."
)

# --- Description ---
survey_type = fields.Selection([
    ('survey', 'Survey'),
    ('live_session', 'Live session'),
    ('assessment', 'Assessment'),
    ('custom', 'Custom')], string='Survey Type', required=True, default='custom')

description = fields.Html(
    "Description", translate=True, sanitize=True, sanitize_overridable=True,
    help="Displayed on the survey home page before starting.")
description_done = fields.Html(
    "End Message", translate=True,
    help="Displayed when survey is completed.")
background_image = fields.Image("Background Image")
background_image_url = fields.Char('Background Url', compute="_compute_background_image_url")

# --- Ownership ---
user_id = fields.Many2one('res.users', string='Responsible',
    domain=[('share', '=', False)], tracking=1,
    default=lambda self: self.env.user)
restrict_user_ids = fields.Many2many('res.users', string='Restricted to',
    domain=[('share', '=', False)], tracking=2)

# --- Question Structure ---
question_and_page_ids = fields.One2many(
    'survey.question', 'survey_id', string='Sections and Questions', copy=True)
page_ids = fields.One2many('survey.question', string='Pages',
    compute="_compute_page_and_question_ids")
question_ids = fields.One2many('survey.question', string='Questions',
    compute="_compute_page_and_question_ids")
question_count = fields.Integer('# Questions',
    compute="_compute_page_and_question_ids")

questions_layout = fields.Selection([
    ('page_per_question', 'One page per question'),
    ('page_per_section', 'One page per section'),
    ('one_page', 'One page with all the questions')],
    string="Pagination", required=True, default='page_per_question')

questions_selection = fields.Selection([
    ('all', 'All questions'),
    ('random', 'Randomized per Section')],
    string="Question Selection", required=True, default='all',
    help="If randomized, configure random_questions_count per section. "
         "Ignored in live sessions.")

progression_mode = fields.Selection([
    ('percent', 'Percentage left'),
    ('number', 'Number')],
    string='Display Progress as', default='percent',
    help="Number mode shows 'X of Y questions answered'.")

# --- Access Control ---
access_mode = fields.Selection([
    ('public', 'Anyone with the link'),
    ('token', 'Invited people only')],
    string='Access Mode', default='public', required=True)

access_token = fields.Char('Access Token',
    default=lambda self: self._get_default_access_token(), copy=False)

users_login_required = fields.Boolean(
    'Require Login',
    help="If checked, users must login before answering even with a valid token.")

users_can_go_back = fields.Boolean('Users can go back',
    help="If checked, users can go back to previous pages.")

users_can_signup = fields.Boolean('Users can signup',
    compute='_compute_users_can_signup')
    # Derives from `res.users._get_signup_invitation_scope() == 'b2c'`

# --- Scoring ---
scoring_type = fields.Selection([
    ('no_scoring', 'No scoring'),
    ('scoring_with_answers_after_page', 'Scoring with answers after each page'),
    ('scoring_with_answers', 'Scoring with answers at the end'),
    ('scoring_without_answers', 'Scoring without answers')],
    string='Scoring', required=True, store=True, readonly=False,
    compute='_compute_scoring_type', precompute=True)

scoring_success_min = fields.Float('Required Score (%)', default=80.0)
scoring_max_obtainable = fields.Float('Maximum obtainable score',
    compute='_compute_scoring_max_obtainable')

# --- Certification ---
certification = fields.Boolean('Is a Certification',
    compute='_compute_certification', readonly=False, store=True, precompute=True)
    # False if scoring_type == 'no_scoring', else follows user input.
    # Automatically set True when survey_type becomes 'assessment'.

certification_mail_template_id = fields.Many2one(
    'mail.template', 'Certified Email Template',
    domain="[('model', '=', 'survey.user_input')]",
    help="Automated email sent on certification success, containing the PDF document.")

certification_report_layout = fields.Selection([
    ('modern_purple', 'Modern Purple'),
    ('modern_blue', 'Modern Blue'),
    ('modern_gold', 'Modern Gold'),
    ('classic_purple', 'Classic Purple'),
    ('classic_blue', 'Classic Blue'),
    ('classic_gold', 'Classic Gold')],
    string='Certification template', default='modern_purple')

certification_give_badge = fields.Boolean('Give Badge',
    compute='_compute_certification_give_badge', readonly=False, store=True, copy=False)
    # Automatically False if certification is False, users_login_required is False,
    # or certification is False.

certification_badge_id = fields.Many2one('gamification.badge',
    'Certification Badge', copy=False, index='btree_not_null')
certification_badge_id_dummy = fields.Many2one(related='certification_badge_id',
    string='Certification Badge ')
    # _badge_uniq constraint: each badge can be assigned to only one survey.

# --- Attempts and Time Limiting ---
is_attempts_limited = fields.Boolean('Limited number of attempts',
    help="Limit attempts per user",
    compute="_compute_is_attempts_limited", store=True, readonly=False)
    # Automatically False if access_mode is 'public' without login,
    # or if survey has conditional questions.

attempts_limit = fields.Integer('Number of attempts', default=1)
is_time_limited = fields.Boolean('The survey is limited in time')
time_limit = fields.Float("Time limit (minutes)", default=10)

# --- Live Sessions ---
session_available = fields.Boolean('Live session available',
    compute='_compute_session_available')
    # True when survey_type in ('live_session', 'custom') and not certification.

session_state = fields.Selection([
    ('ready', 'Ready'),
    ('in_progress', 'In Progress')],
    string="Session State", copy=False)

session_code = fields.Char('Session Code', copy=False,
    compute="_compute_session_code", precompute=True, store=True, readonly=False,
    help="Customizable short code attendees use to join, e.g. 'CONF2024'.")
session_link = fields.Char('Session Link', compute='_compute_session_link')

session_question_id = fields.Many2one('survey.question',
    string="Current Question", copy=False,
    help="The current question of the survey session.")
session_start_time = fields.Datetime("Current Session Start Time", copy=False)
session_question_start_time = fields.Datetime("Current Question Start Time", copy=False,
    help="Used to handle per-question timer for attendees.")
session_answer_count = fields.Integer("Answers Count",
    compute='_compute_session_answer_count')
session_question_answer_count = fields.Integer("Question Answers Count",
    compute='_compute_session_question_answer_count')

session_show_leaderboard = fields.Boolean("Show Session Leaderboard",
    compute='_compute_session_show_leaderboard',
    help="True when scoring_type != 'no_scoring' and any question has save_as_nickname.")
session_speed_rating = fields.Boolean("Reward quick answers",
    help="Attendees get more points if they answer quickly.")
session_speed_rating_time_limit = fields.Integer("Time limit (seconds)",
    help="Default time given to receive additional points for right answers.")

# --- Conditional Questions ---
has_conditional_questions = fields.Boolean("Contains conditional questions",
    compute="_compute_has_conditional_questions")

# --- Statistics (Computed) ---
answer_count = fields.Integer("Registered", compute="_compute_survey_statistic")
answer_done_count = fields.Integer("Attempts", compute="_compute_survey_statistic")
answer_score_avg = fields.Float("Avg Score (%)", compute="_compute_survey_statistic")
answer_duration_avg = fields.Float("Average Duration",
    compute="_compute_answer_duration_avg",
    help="Average duration of the survey (in hours)")
success_count = fields.Integer("Success", compute="_compute_survey_statistic")
success_ratio = fields.Integer("Success Ratio (%)", compute="_compute_survey_statistic")
allowed_survey_types = fields.Json(string='Allowed survey types',
    compute="_compute_allowed_survey_types")
    # Returns full list for survey.group_survey_user members, False otherwise.
```

### L2 — Field Types, Defaults, Constraints

**SQL Constraints:**

```python
_access_token_unique = models.Constraint(
    'unique(access_token)', 'Access token should be unique')
_session_code_unique = models.Constraint(
    'unique(session_code)', 'Session code should be unique')
_certification_check = models.Constraint(
    "CHECK( scoring_type!='no_scoring' OR certification=False )",
    'You can only create certifications for surveys that have a scoring mechanism.')
_scoring_success_min_check = models.Constraint(
    'CHECK( scoring_success_min IS NULL OR (scoring_success_min>=0 AND scoring_success_min<=100) )',
    'The percentage of success has to be defined between 0 and 100.')
_time_limit_check = models.Constraint(
    'CHECK( (is_time_limited=False) OR (time_limit is not null AND time_limit > 0) )',
    'The time limit needs to be a positive number if the survey is time limited.')
_attempts_limit_check = models.Constraint(
    'CHECK( (is_attempts_limited=False) OR (attempts_limit is not null AND attempts_limit > 0) )',
    'The attempts limit needs to be a positive number if the survey has a limited number of attempts.')
_badge_uniq = models.Constraint(
    'unique (certification_badge_id)',
    'The badge for each survey should be unique!')
_session_speed_rating_has_time_limit = models.Constraint(
    'CHECK (session_speed_rating != TRUE OR session_speed_rating_time_limit IS NOT NULL AND session_speed_rating_time_limit > 0)',
    'A positive default time limit is required when the session rewards quick answers.')
```

**API Constraints:**

```python
@api.constrains('scoring_type', 'users_can_go_back')
def _check_scoring_after_page_availability(self):
    # Prevents combining 'scoring_with_answers_after_page' with users_can_go_back
    # because revealing correct answers per page would let users go back and change answers.
    if survey.scoring_type == 'scoring_with_answers_after_page' and survey.users_can_go_back:
        raise ValidationError

@api.constrains('user_id', 'restrict_user_ids')
def _check_survey_responsible_access(self):
    # Survey officers (non-managers) must be in restrict_user_ids if access is restricted.
    # Prevents accidentally locking yourself out of your own survey.
```

### L3 — Cross-Model Relationships, Override Patterns, Workflow Triggers

**Survey Type Onchange Side Effects:**

```python
@api.onchange('survey_type')
def _onchange_survey_type(self):
    if self.survey_type == 'survey':
        self.certification = False
        self.is_time_limited = False
        self.scoring_type = 'no_scoring'
    elif self.survey_type == 'live_session':
        self.access_mode = 'public'
        self.is_attempts_limited = False
        self.is_time_limited = False
        self.progression_mode = 'percent'
        self.questions_layout = 'page_per_question'
        self.questions_selection = 'all'
        self.scoring_type = 'scoring_with_answers'
        self.users_can_go_back = False
    elif self.survey_type == 'assessment':
        self.access_mode = 'token'
        self.scoring_type = 'scoring_with_answers'
```

**Certification Badge Creation Flow:**
When `certification_give_badge` becomes True:
1. `certification_badge_id.action_unarchive()` — unarchives or creates badge
2. `_create_certification_badge_trigger()` creates:
   - A `gamification.goal.definition` with domain `[('survey_id', '=', id), ('scoring_success', '=', True)]` on `survey.user_input`
   - A `gamification.challenge` in `inprogress` state, `period: once`, `challenge_category: certification`, `reward_realtime: True`
   - A `gamification.challenge.line` linking goal to challenge with `target_goal: 1`
3. On `_mark_done()`, badge is awarded via `Challenge._cron_update()` (sudos)

When `certification_give_badge` becomes False:
- Challenges and goal definitions are deleted in cascade
- Badge is archived (not deleted, preserving ownership records)

**Scoring Max Computation Logic:**
```python
# For each question: max of suggested_answer_ids positive scores OR question.answer_score
scoring_max_obtainable = sum(
    question.answer_score or
    max(answer.answer_score for answer in question.suggested_answer_ids if answer.answer_score > 0)
    for question in survey.question_ids
)
```

### L4 — Performance, Odoo 18→19 Changes, Security, Edge Cases

**Performance Considerations:**
- `scoring_percentage`, `scoring_total`, `scoring_success` are **stored** on `survey.user_input` (`store=True, compute_sudo=True`) — avoids recomputation on large result sets.
- `answer_duration_avg` uses raw SQL with `extract(epoch FROM ...)` for sub-second precision rather than ORM aggregation.
- `_compute_attempts_info` uses raw SQL with a window function to count all attempts per user/email/invite_token in a single query instead of N+1 ORM calls.
- `predefined_question_ids` is stored on each `user_input` at creation time. For randomized surveys, randomization is baked in at `_create_answer()` time via `random.sample()`, not at render time.
- `_prepare_statistics()` on `survey.user_input` builds the full statistics dict server-side to avoid repeated client RPC calls during result rendering.

**Odoo 18 → 19 Key Changes:**
1. `survey_type` field (new in 19) replaces any prior `state`-based survey categorization.
2. `lang_ids` Many2many replaces single-language survey support.
3. `certification` became a computed+stored field (was plain Boolean).
4. `certification_give_badge` became computed+stored.
5. `is_attempts_limited` became computed+stored — conditional questions now automatically disable attempt limiting since they create inconsistent attempt pools.
6. `session_available` is a new computed field derived from `survey_type`.
7. `color` field added for kanban view organization.
8. `questions_selection: random` and `random_questions_count` per section are new (Odoo 18 may have had random questions but the per-section count configuration is 19-specific).
9. `progression_mode` field added for flexible progress display.

**Security Considerations:**
- Survey officers (`group_survey_user`) are filtered by `restrict_user_ids` unless that field is empty (public surveys).
- Attempt counting groups by `invite_token` for token-mode surveys — meaning each invite batch gets its own attempt pool. For public-mode surveys with `is_attempts_limited`, the entire pool is shared globally since no invite_token is generated.
- `test_entry=True` user_inputs are excluded from success counts and certification emails.
- The `res.partner` model is extended with certifications counts, available in the partner form view.
- Badge creation uses `sudo()` because the responsible user may not have gamification rights.

**Edge Cases:**
- Attempt counting: if `invite_token` is present in the SQL join, only attempts sharing that same invite_token count. This means two different invite batches for the same survey count separately.
- `is_attempts_limited` auto-disables when conditional questions are present because conditional logic changes which questions are shown, making attempt comparison unreliable across different paths.
- `scoring_with_answers_after_page` is incompatible with `users_can_go_back` — raising a `ValidationError` at write time.
- `_is_time_limited_have_time_limit` constraint on `survey.question`: a question with `is_time_limited=True` must have a positive `time_limit`.
- `certification` auto-disables if `scoring_type` is later changed to `'no_scoring'` — due to the `certification_check` constraint.
- If a certification badge is already awarded to users (has owners), it is archived rather than deleted to preserve history.

---

## survey.question

**File:** `~/odoo/odoo19/odoo/addons/survey/models/survey_question.py`
**Inherits:** None (base `BaseModel`)
**Rec Name:** `title`
**Order:** `sequence, id`

### L1 — All Field Signatures

```python
# --- Generic ---
title = fields.Char('Title', required=True, translate=True)
description = fields.Html('Description', translate=True, sanitize=True,
    sanitize_overridable=True,
    help="Additional explanations, pictures, or video.")
question_placeholder = fields.Char("Placeholder", translate=True,
    compute="_compute_question_placeholder", store=True, readonly=False)
background_image = fields.Image("Background Image",
    compute="_compute_background_image", store=True, readonly=False)
    # Only stored for pages (is_page=True); questions always clear it.
background_image_url = fields.Char("Background Url",
    compute="_compute_background_image_url")
survey_id = fields.Many2one('survey.survey', string='Survey',
    ondelete='cascade', index='btree_not_null')
scoring_type = fields.Selection(related='survey_id.scoring_type',
    string='Scoring Type', readonly=True)
sequence = fields.Integer('Sequence', default=10)

# --- Page-specific ---
is_page = fields.Boolean('Is a page?')
    # Pages have no question_type, no suggested_answer_ids.
question_ids = fields.One2many('survey.question', string='Questions',
    compute="_compute_question_ids")
    # For pages: all questions belonging to this page.
    # For questions: empty recordset.
questions_selection = fields.Selection(
    related='survey_id.questions_selection', readonly=True)
random_questions_count = fields.Integer('# Questions Randomly Picked', default=1,
    help="In randomized sections, pick this many random questions from the section.")

# --- Question-specific ---
page_id = fields.Many2one('survey.question', string='Page',
    compute="_compute_page_id", store=True)
    # For pages: always None.
    # For questions: the nearest preceding page in sequence order.
    # Implemented as iterative search through sorted question_and_page_ids.

question_type = fields.Selection([
    ('simple_choice', 'Multiple choice: only one answer'),
    ('multiple_choice', 'Multiple choice: multiple answers allowed'),
    ('text_box', 'Multiple Lines Text Box'),
    ('char_box', 'Single Line Text Box'),
    ('numerical_box', 'Numerical Value'),
    ('scale', 'Scale'),
    ('date', 'Date'),
    ('datetime', 'Datetime'),
    ('matrix', 'Matrix')],
    string='Question Type',
    compute='_compute_question_type', readonly=False, store=True)
    # Default: 'simple_choice' for new questions.
    # Pages (is_page=True) always have question_type=False.

is_scored_question = fields.Boolean('Scored',
    compute='_compute_is_scored_question', readonly=False, store=True, copy=True,
    help="Include in quiz scoring. Requires correct answer and score to be configured.")
has_image_only_suggested_answer = fields.Boolean(
    "Has image only suggested answer", compute='_compute_has_image_only_suggested_answer')

# --- Correct answers for scored questions ---
answer_numerical_box = fields.Float('Correct numerical answer')
answer_date = fields.Date('Correct date answer')
answer_datetime = fields.Datetime('Correct datetime answer')
answer_score = fields.Float('Score',
    help="Points awarded for a correct answer (non-choice questions).")

# --- Char box options ---
save_as_email = fields.Boolean("Save as user email",
    compute='_compute_save_as_email', readonly=False, store=True, copy=True,
    help="Saves the answer as the respondent's email (on first submission).")
save_as_nickname = fields.Boolean("Save as user nickname",
    compute='_compute_save_as_nickname', readonly=False, store=True, copy=True,
    help="Saves the answer as the respondent's nickname (on first submission).")

# --- Choice / Matrix answers ---
suggested_answer_ids = fields.One2many(
    'survey.question.answer', 'question_id', string='Types of answers', copy=True,
    help="Labels for simple choice, multiple choice, and matrix columns.")
matrix_row_ids = fields.One2many(
    'survey.question.answer', 'matrix_question_id', string='Matrix Rows', copy=True,
    help="Row labels for matrix questions.")
matrix_subtype = fields.Selection([
    ('simple', 'One choice per row'),
    ('multiple', 'Multiple choices per row')],
    string='Matrix Type', default='simple')

# --- Scale ---
scale_min = fields.Integer("Scale Minimum Value", default=0)
scale_max = fields.Integer("Scale Maximum Value", default=10)
scale_min_label = fields.Char("Scale Minimum Label", translate=True)
scale_mid_label = fields.Char("Scale Middle Label", translate=True)
scale_max_label = fields.Char("Scale Maximum Label", translate=True)

# --- Time Limits (Live Sessions) ---
is_time_limited = fields.Boolean("The question is limited in time",
    help="Currently only supported for live sessions.")
is_time_customized = fields.Boolean("Customized speed rewards")
    # True if question's time limit differs from survey-level default.
time_limit = fields.Integer("Time limit (seconds)")

# --- Comments ---
comments_allowed = fields.Boolean('Show Comments Field')
comments_message = fields.Char('Comment Message', translate=True)
comment_count_as_answer = fields.Boolean('Comment is an answer')
    # If True, a text comment counts as a valid (non-skipped) answer.

# --- Validation ---
validation_required = fields.Boolean('Validate entry',
    compute='_compute_validation_required', readonly=False, store=True)
validation_email = fields.Boolean('Input must be an email')
validation_length_min = fields.Integer('Minimum Text Length', default=0)
validation_length_max = fields.Integer('Maximum Text Length', default=0)
validation_min_float_value = fields.Float('Minimum value', default=0.0)
validation_max_float_value = fields.Float('Maximum value', default=0.0)
validation_min_date = fields.Date('Minimum Date')
validation_max_date = fields.Date('Maximum Date')
validation_min_datetime = fields.Datetime('Minimum Datetime')
validation_max_datetime = fields.Datetime('Maximum Datetime')
validation_error_msg = fields.Char('Validation Error', translate=True)
constr_mandatory = fields.Boolean('Mandatory Answer')
constr_error_msg = fields.Char('Error message', translate=True)

# --- Conditional Questions ---
triggering_answer_ids = fields.Many2many(
    'survey.question.answer', string="Triggering Answers", copy=False, store=True,
    domain="""[
        ('question_id.survey_id', '=', survey_id),
        '&', ('question_id.question_type', 'in', ['simple_choice', 'multiple_choice']),
             '|',
                 ('question_id.sequence', '<', sequence),
                 '&', ('question_id.sequence', '=', sequence), ('question_id.id', '<', id)
    ]""",
    help="Selecting any of these answers triggers this question to appear. "
         "Leave empty for unconditional display.")
allowed_triggering_question_ids = fields.Many2many(
    'survey.question', string="Allowed Triggering Questions", copy=False,
    compute="_compute_allowed_triggering_question_ids")
is_placed_before_trigger = fields.Boolean('Is misplaced?',
    compute="_compute_allowed_triggering_question_ids",
    help="True if any triggering answer belongs to a question that comes AFTER this question.")
triggering_question_ids = fields.Many2many(
    'survey.question', string="Triggering Questions",
    compute="_compute_triggering_question_ids", store=False)

# --- Session-related ---
session_available = fields.Boolean(related='survey_id.session_available',
    string='Live Session available', readonly=True)
survey_session_speed_rating = fields.Boolean(related="survey_id.session_speed_rating")
survey_session_speed_rating_time_limit = fields.Integer(
    related="survey_id.session_speed_rating_time_limit",
    string="General Time limit (seconds)")

# --- Statistics ---
user_input_line_ids = fields.One2many(
    'survey.user_input.line', 'question_id', string='Answers',
    domain=[('skipped', '=', False)], groups='survey.group_survey_user')
```

### L2 — SQL Constraints

```python
_positive_len_min = models.Constraint(
    'CHECK (validation_length_min >= 0)', 'A length must be positive!')
_positive_len_max = models.Constraint(
    'CHECK (validation_length_max >= 0)', 'A length must be positive!')
_validation_length = models.Constraint(
    'CHECK (validation_length_min <= validation_length_max)',
    'Max length cannot be smaller than min length!')
_validation_float = models.Constraint(
    'CHECK (validation_min_float_value <= validation_max_float_value)',
    'Max value cannot be smaller than min value!')
_validation_date = models.Constraint(
    'CHECK (validation_min_date <= validation_max_date)',
    'Max date cannot be smaller than min date!')
_validation_datetime = models.Constraint(
    'CHECK (validation_min_datetime <= validation_max_datetime)',
    'Max datetime cannot be smaller than min datetime!')
_positive_answer_score = models.Constraint(
    'CHECK (answer_score >= 0)',
    'An answer score for a non-multiple choice question cannot be negative!')
_scored_datetime_have_answers = models.Constraint(
    "CHECK (is_scored_question != True OR question_type != 'datetime' OR answer_datetime is not null)",
    'All "Is a scored question = True" and "Question Type: Datetime" questions need an answer')
_scored_date_have_answers = models.Constraint(
    "CHECK (is_scored_question != True OR question_type != 'date' OR answer_date is not null)",
    'All "Is a scored question = True" and "Question Type: Date" questions need an answer')
_scale = models.Constraint(
    "CHECK (question_type != 'scale' OR (scale_min >= 0 AND scale_max <= 10 AND scale_min < scale_max))",
    'The scale must be a growing non-empty range between 0 and 10 (inclusive)')
_is_time_limited_have_time_limit = models.Constraint(
    'CHECK (is_time_limited != TRUE OR time_limit IS NOT NULL AND time_limit > 0)',
    'All time-limited questions need a positive time limit')
```

**API Constraint:**
```python
@api.constrains("is_page")
def _check_question_type_for_pages(self):
    # Pages cannot have a question_type set — prevents invalid configuration.
    # Raises ValidationError listing invalid page titles.
```

### L3 — is_scored_question Computation Logic

```python
@api.depends('question_type', 'scoring_type', 'answer_date', 'answer_datetime',
             'answer_numerical_box', 'suggested_answer_ids.is_correct')
def _compute_is_scored_question(self):
    for question in self:
        if question.is_scored_question is None or question.scoring_type == 'no_scoring':
            question.is_scored_question = False
        elif question.question_type == 'date':
            question.is_scored_question = bool(question.answer_date)
        elif question.question_type == 'datetime':
            question.is_scored_question = bool(question.answer_datetime)
        elif question.question_type == 'numerical_box' and question.answer_numerical_box:
            question.is_scored_question = True
            # Note: numerical answer of exactly 0.0 does NOT trigger scoring
        elif question.question_type in ['simple_choice', 'multiple_choice']:
            question.is_scored_question = any(
                question.suggested_answer_ids.mapped('is_correct'))
        else:
            question.is_scored_question = False
```

### L3 — Validation Methods (L4 Detail)

```python
def validate_question(self, answer, comment=None):
    """
    Returns dict {question_id: error_message} or empty dict {}.
    Handles: char_box, numerical_box, date, datetime, simple_choice,
             multiple_choice, matrix, scale.
    """
    # Mandatory check for non-choice types: if constr_mandatory and not users_can_go_back
    # Note: if users_can_go_back, mandatory is NOT enforced on submit (user can skip).

def _validate_char_box(self, answer):
    # Email normalize check if validation_email=True
    # Length range check if validation_required=True
    # validation_length_min <= len(answer) <= validation_length_max

def _validate_numerical_box(self, answer):
    # ValueError if not float-convertible
    # Range check: validation_min_float_value <= answer <= validation_max_float_value

def _validate_date(self, answer):
    # ValueError if not date/datetime parseable
    # Range check using validation_min_date/max_date or validation_min_datetime/max_datetime
    # contextlib.suppress prevents error on None boundary values

def _validate_choice(self, answer, comment):
    # Simple choice: exactly 1 answer required if constr_mandatory
    # comment_count_as_answer: comment adds to answer count
    # Returns error if valid_answers_count == 0 and mandatory

def _validate_matrix(self, answers):
    # All rows must be answered if constr_mandatory

def _validate_scale(self, answer):
    # Only enforces mandatory; scale range is enforced by _scale SQL constraint
```

### L4 — Conditional Questions: Triggering Logic

The `triggering_answer_ids` domain enforces that triggers can only come from **earlier** questions (lower `sequence`, or same sequence with lower database `id`). This prevents circular or forward references.

`_compute_allowed_triggering_question_ids` uses a raw SQL query to avoid cascading RPC calls during drag-and-drop reordering in the web client. It bypasses ORM dependencies for sequence-based computation.

When `_clear_inactive_conditional_answers()` runs (on submit), it removes any answers to questions that were conditionally hidden at submission time. This is critical for scoring correctness — a user who answered a question, then unchecked its trigger, must have that answer erased.

---

## survey.question.answer

**File:** `~/odoo/odoo19/odoo/addons/survey/models/survey_question.py`
**Inherits:** None
**Rec Name:** `value`
**Order:** `question_id, sequence, id`

### L1 — All Field Signatures

```python
MAX_ANSWER_NAME_LENGTH = 90  # UI dropdown truncation limit

question_id = fields.Many2one('survey.question', string='Question',
    ondelete='cascade', index='btree_not_null')
matrix_question_id = fields.Many2one('survey.question',
    string='Question (as matrix row)', ondelete='cascade', index='btree_not_null')
    # Used for matrix row definitions (when question is a matrix type).
question_type = fields.Selection(related='question_id.question_type', readonly=True)
scoring_type = fields.Selection(related='question_id.scoring_type', readonly=True)
sequence = fields.Integer('Label Sequence order', default=10)

value = fields.Char('Suggested value', translate=True)
    # Required unless value_image is provided (enforced by SQL constraint).
value_image = fields.Image('Image', max_width=1024, max_height=1024)
value_image_filename = fields.Char('Image Filename')
value_label = fields.Char('Value Label', compute='_compute_value_label',
    help="The value itself if not empty, or letter A/B/C... based on sequence index.")
is_correct = fields.Boolean('Correct')
    # For simple/multiple choice: marks the correct answer(s).
    # A question can have zero, one, or multiple correct answers.
answer_score = fields.Float('Score',
    help="Positive = correct; negative or zero = wrong/invalid choice.")
    # Constraint: `answer_score >= 0` — negative scores not allowed on choice answers.
```

### L2 — SQL Constraint

```python
_value_not_empty = models.Constraint(
    'CHECK (value IS NOT NULL OR value_image_filename IS NOT NULL)',
    'Suggested answer value must not be empty (a text and/or an image must be provided).'
)
```

### L3 — Value Label Computation

```python
@api.depends('question_id.suggested_answer_ids', 'sequence', 'value')
def _compute_value_label(self):
    for answer in self:
        if answer.value:
            answer.value_label = answer.value
        else:
            # Derive label from sequence: 1=A, 2=B, etc. (chr(64+n))
            answer.value_label = chr(64 + answer.sequence) if answer.sequence <= 26 else str(answer.sequence)
```

### L4 — Scoring Implications

For **simple choice**: only the single highest-scoring suggested answer counts toward total possible score. Selecting a correct answer with a lower score yields partial credit.

For **multiple choice**: all suggested answer scores are summed as total possible. `is_correct=True` on a multiple-choice answer primarily drives `_compute_answer_score` on the line, but does NOT affect total possible score. Negative `answer_score` is stored on choice lines but the `_positive_answer_score` constraint prevents negative values for non-choice question types.

For **matrix**: each cell intersection (row answer + column suggestion) can be independently scored.

---

## survey.user_input

**File:** `~/odoo/odoo19/odoo/addons/survey/models/survey_user_input.py`
**Inherits:** `mail.thread`, `mail.activity.mixin`
**Rec Name:** `survey_id`
**Order:** `create_date DESC`

### L1 — All Field Signatures

```python
# --- Core ---
survey_id = fields.Many2one('survey.survey', string='Survey',
    required=True, readonly=True, index=True, ondelete='cascade')
scoring_type = fields.Selection(string="Scoring", related="survey_id.scoring_type")
state = fields.Selection([
    ('new', 'New'),
    ('in_progress', 'In Progress'),
    ('done', 'Completed')],
    string='Status', default='new', readonly=True)

# --- Timing ---
start_datetime = fields.Datetime('Start date and time', readonly=True)
end_datetime = fields.Datetime('End date and time', readonly=True)
deadline = fields.Datetime('Deadline',
    help="Datetime until respondent can open and submit the survey.")
lang_id = fields.Many2one('res.lang', string='Language')

# --- Test and Navigation ---
test_entry = fields.Boolean(readonly=True)
    # True for test-mode survey attempts (created via /survey/test/ route).
    # Excluded from statistics and certification awards.
last_displayed_page_id = fields.Many2one('survey.question',
    string='Last displayed question/page')

# --- Identification / Access ---
access_token = fields.Char('Identification token',
    default=lambda self: str(uuid.uuid4()), readonly=True, required=True, copy=False)
    # Unique per attempt (UNIQUE constraint enforced at DB level).
invite_token = fields.Char('Invite token', readonly=True, copy=False)
    # Groups attempts from the same invite batch.
    # No unique constraint — all attempts sharing an invite_token are a pool.
partner_id = fields.Many2one('res.partner', string='Contact',
    readonly=True, index='btree_not_null')
email = fields.Char('Email', readonly=True)
nickname = fields.Char('Nickname',
    help="Attendee nickname used in survey session leaderboard.")

# --- Questions and Answers ---
user_input_line_ids = fields.One2many('survey.user_input.line',
    'user_input_id', string='Answers', copy=True)
predefined_question_ids = fields.Many2many('survey.question',
    string='Predefined Questions', readonly=True)
    # Frozen set of questions shown to this respondent.
    # For randomized surveys: populated at create() time via
    # survey._prepare_user_input_predefined_questions() using random.sample().
    # For live sessions: recalculated to reflect most-voted path.

# --- Scoring (Stored) ---
scoring_percentage = fields.Float("Score (%)",
    compute="_compute_scoring_values", store=True, compute_sudo=True)
scoring_total = fields.Float("Total Score",
    compute="_compute_scoring_values", store=True, compute_sudo=True, digits=(10, 2))
scoring_success = fields.Boolean('Quiz Passed',
    compute='_compute_scoring_success', store=True, compute_sudo=True)
    # True when scoring_percentage >= survey_id.scoring_success_min.

survey_first_submitted = fields.Boolean(string='Survey First Submitted')
    # True once first submission is made. Used to handle "go back" resumption.

# --- Attempts ---
is_attempts_limited = fields.Boolean("Limited number of attempts",
    related='survey_id.is_attempts_limited')
attempts_limit = fields.Integer("Number of attempts",
    related='survey_id.attempts_limit')
attempts_count = fields.Integer("Attempts Count",
    compute='_compute_attempts_info')
    # Total number of completed, non-test attempts by this user for this invite.
attempts_number = fields.Integer("Attempt n°",
    compute='_compute_attempts_info')
    # 1-based index of this attempt within the invite pool.

# --- Time Limit Tracking ---
survey_time_limit_reached = fields.Boolean("Survey Time Limit Reached",
    compute='_compute_survey_time_limit_reached')
    # True when now() >= start_datetime + survey_id.time_limit (in minutes).
    # Not applied to session answers (is_session_answer=False for timed surveys).

question_time_limit_reached = fields.Boolean("Question Time Limit Reached",
    compute='_compute_question_time_limit_reached')
    # Only used for live session per-question timing.

# --- Session ---
is_session_answer = fields.Boolean('Is in a Session',
    help="Is that user input part of a survey session or not.")
```

### L2 — Key Computed Field Logic

**`_compute_attempts_info` SQL Query Logic:**

```sql
-- Counts ALL completed, non-test attempts from the same partner/email in the invite pool.
-- invite_token IS NULL means public-mode survey (global pool).
SELECT
    user_input.id,
    COUNT(all_attempts.id) AS attempts_count,
    COUNT(CASE WHEN all_attempts.id < user_input.id THEN all_attempts.id END) + 1 AS attempts_number
FROM survey_user_input user_input
LEFT OUTER JOIN survey_user_input all_attempts ON
    user_input.survey_id = all_attempts.survey_id
    AND all_attempts.state = 'done'
    AND all_attempts.test_entry IS NOT TRUE
    AND (user_input.invite_token IS NULL OR user_input.invite_token = all_attempts.invite_token)
    AND (user_input.partner_id = all_attempts.partner_id OR user_input.email = all_attempts.email)
WHERE user_input.id IN (...)
GROUP BY user_input.id;
```

**`attempts_number` computation**: counts all prior attempts by the same user within the same invite pool + 1. This means if you retake a survey 3 times, `attempts_number` would be 1, 2, 3 respectively.

### L3 — `_mark_done` Full Workflow

```python
def _mark_done(self):
    # 1. Set state='done', end_datetime=now()
    # 2. For each user_input:
    #    a. If certification AND scoring_success AND NOT test_entry:
    #       - Send certification_mail_template_id (if configured)
    #    b. If certification_give_badge:
    #       - Collect badge IDs for batch awarding
    #    c. Clear inactive conditional question answers
    # 3. _notify_new_participation_subscribers() — posts message to survey followers
    # 4. Batch-award badges via gamification.challenge._cron_update()
```

### L3 — Predefined Questions Randomization

```python
def _prepare_user_input_predefined_questions(self):
    # 1. Collect all questions without a page (root-level)
    # 2. For each page:
    #    - If questions_selection == 'all': add all page questions
    #    - If questions_selection == 'random': random.sample(page.question_ids, random_questions_count)
    # 3. Return merged question recordset (deterministic within one transaction)
```

### L4 — Performance, Edge Cases

- `predefined_question_ids` is a `Many2many` stored on the record — avoids re-randomizing on each access.
- `_compute_scoring_values` uses `predefined_question_ids` (not `survey_id.question_ids`) to correctly compute denominator for randomized surveys.
- For `numerical_box`: `answer_numerical_box = 0.0` does NOT trigger `is_scored_question = True` (falsy check), meaning a question with correct answer 0 must be set up as simple_choice or the scoring logic must handle this.
- `_save_lines` with `overwrite_existing=True` (default): re-creates choice answer lines (unlink + create) rather than writing, to maintain data consistency for multiple-choice.
- `skipped=True` is only valid when `answer_type` is `False`/`None` — enforced by `_check_answer_type_skipped` constraint.

---

## survey.user_input.line

**File:** `~/odoo/odoo19/odoo/addons/survey/models/survey_user_input.py`
**Inherits:** None
**Rec Name:** `user_input_id`
**Order:** `question_sequence, id`

### L1 — All Field Signatures

```python
# --- Core ---
user_input_id = fields.Many2one('survey.user_input', string='User Input',
    ondelete='cascade', required=True, index=True)
survey_id = fields.Many2one(related='user_input_id.survey_id',
    string='Survey', store=True, readonly=False)
question_id = fields.Many2one('survey.question', string='Question',
    ondelete='cascade', required=True, index=True)
page_id = fields.Many2one(related='question_id.page_id', string="Section",
    readonly=False)
question_sequence = fields.Integer('Sequence', related='question_id.sequence',
    store=True)
lang_id = fields.Many2one(related="user_input_id.lang_id")

# --- Answer Value ---
skipped = fields.Boolean('Skipped')
    # True when no answer was provided. Mutually exclusive with answer_type.
answer_type = fields.Selection([
    ('text_box', 'Free Text'),
    ('char_box', 'Text'),
    ('numerical_box', 'Number'),
    ('scale', 'Number'),
    ('date', 'Date'),
    ('datetime', 'Datetime'),
    ('suggestion', 'Suggestion')],
    string='Answer Type')
    # 'suggestion' = choice-based answer (simple/multiple choice, matrix)

# Value fields (mutually exclusive based on answer_type):
value_char_box = fields.Char('Text answer')
value_text_box = fields.Text('Free Text answer')
value_numerical_box = fields.Float('Numerical answer')
value_scale = fields.Integer('Scale value')
value_date = fields.Date('Date answer')
value_datetime = fields.Datetime('Datetime answer')
suggested_answer_id = fields.Many2one('survey.question.answer',
    string="Suggested answer")
    # For simple/multiple choice selections.
matrix_row_id = fields.Many2one('survey.question.answer',
    string="Row answer")
    # For matrix selections: which row was selected.

# --- Scoring (Stored, Precompute) ---
answer_score = fields.Float('Score',
    compute='_compute_answer_score', precompute=True, store=True)
answer_is_correct = fields.Boolean('Correct',
    compute='_compute_answer_score', precompute=True, store=True)
```

### L2 — Constraint

```python
@api.constrains('skipped', 'answer_type')
def _check_answer_type_skipped(self):
    # skipped == bool(answer_type) must always be True
    # i.e., a line cannot be both skipped AND have an answer type,
    # and cannot have an answer type while marked skipped.
    # Exception: numerical_box with value 0.0 and scale with value 0 are allowed
    # (since those values are falsy but semantically valid).
```

### L3 — Score Computation Details

```python
@api.depends('answer_type', 'value_text_box', 'value_numerical_box',
             'value_char_box', 'value_date', 'value_datetime',
             'suggested_answer_id.value', 'matrix_row_id.value',
             'user_input_id')
def _compute_answer_score(self):
    for line in self:
        # --- Base scoring (pre speed rating) ---
        if answer_type == 'suggestion':
            answer_score = suggested_answer_id.answer_score
            answer_is_correct = suggested_answer_id.is_correct
        elif question_type in ['date', 'datetime', 'numerical_box']:
            answer_is_correct = (answer == question[f'answer_{answer_type}'])
            answer_score = question.answer_score if answer_is_correct else 0

        # --- Speed rating bonus (live sessions only) ---
        if answer_score > 0 and session_speed_rating and is_session_answer:
            if question_time_limit_reached or question != session_question_id:
                answer_score /= 2  # Late or wrong question: half points
            elif seconds_to_answer > 2:  # Linear decay after 2-second grace
                proportion = (time_limit - seconds_to_answer) / (time_limit - 2)
                answer_score = (answer_score / 2) * (1 + proportion)
            # else: answered within 2 sec, full score
```

### L4 — `_get_answer_matching_domain`

Used for advanced filtering in results: builds a domain to find other respondents who gave the same answer. Handles all answer types including matrix (with row consideration).

---

## survey.invite (Wizard)

**File:** `~/odoo/odoo19/odoo/addons/survey/wizard/survey_invite.py`
**Inherits:** `mail.composer.mixin`
**Type:** Transient Model

### L1 — All Field Signatures

```python
# Inherited from mail.composer.mixin:
#   template_id, subject, body, email_from, reply_to, email_add_signature,
#   force_email_send, author_id

attachment_ids = fields.Many2many('ir.attachment',
    'survey_mail_compose_message_ir_attachments_rel', 'wizard_id', 'attachment_id',
    string='Attachments', compute='_compute_attachment_ids', store=True,
    readonly=False, bypass_search_access=True)
author_id = fields.Many2one('res.partner', 'Author', index=True,
    ondelete='set null', default=_get_default_author)

# --- Recipients ---
partner_ids = fields.Many2many('res.partner', 'survey_invite_partner_ids',
    'invite_id', 'partner_id', string='Recipients',
    domain="[ \
        '|', (survey_users_can_signup, '=', 1), \
        '|', (not survey_users_login_required, '=', 1), \
             ('user_ids', '!=', False), \
    ]")
existing_partner_ids = fields.Many2many('res.partner',
    compute='_compute_existing_partner_ids', readonly=True, store=False)
emails = fields.Text(string='Additional emails')
existing_emails = fields.Text('Existing emails',
    compute='_compute_existing_emails', readonly=True, store=False)
existing_mode = fields.Selection([
    ('new', 'New invite'),
    ('resend', 'Resend invite')],
    string='Handle existing', default='resend', required=True)
existing_text = fields.Text('Resend Comment', compute='_compute_existing_text')

# --- Technical ---
mail_server_id = fields.Many2one('ir.mail_server', 'Outgoing mail server')

# --- Survey ---
survey_id = fields.Many2one('survey.survey', string='Survey', required=True)
survey_start_url = fields.Char('Survey URL', compute='_compute_survey_start_url')
survey_access_mode = fields.Selection(related="survey_id.access_mode", readonly=True)
survey_users_login_required = fields.Boolean(
    related="survey_id.users_login_required", readonly=True)
survey_users_can_signup = fields.Boolean(related='survey_id.users_can_signup')
deadline = fields.Datetime(string="Answer deadline")
send_email = fields.Boolean(compute="_compute_send_email", inverse="_inverse_send_email")
    # True when survey_access_mode == 'token'. Forced on by default for token mode.
```

### L3 — Send Flow

```
action_invite():
  1. Parse emails, normalize with email_normalize()
  2. Search for existing partners by normalized email (1 result unless login_required)
  3. _prepare_answers():
     - Search for existing user_inputs for this survey+partner/email
     - If existing_mode == 'resend': skip already-sent, keep latest per partner/email
     - Create new user_inputs for missing recipients
  4. _send_mail() per answer:
     - Render template fields with answer token
     - Create mail.mail record (sudo for external respondents)
     - auto_delete=True (one-way notification, not stored in inbox)
```

**`existing_mode='new'`**: sends to all selected partners/emails, creating duplicate `user_input` records (for tracking multiple independent invites to same person).

**`existing_mode='resend'`**: for each partner/email with existing attempts, sends to the most recent one. Does not create new `user_input` records.

---

## survey.question (Matrix Row — survey.matrix.row)

Matrix rows are NOT a separate model. They use `survey.question.answer` with `matrix_question_id` set (non-null). The row label is stored in the `value` field of those records. Columns use `suggested_answer_ids` on the matrix question.

---

## Extended Models

### res.partner Extension (res_partner.py)

| Field | Type | Description |
|-------|------|-------------|
| `certifications_count` | Integer | Successful certifications (scoring_success=True) |
| `certifications_company_count` | Integer | Sum of child partners' certifications (for companies) |

Action `action_view_certifications()` opens filtered list of all completed user_inputs where partner is the contact or any child of the company.

### gamification.badge Extension (badge.py)

- `survey_ids`: One2many to `survey.survey` via `certification_badge_id`
- `survey_id`: Many2one computed from `survey_ids[0]` (first/only survey using this badge)

### gamification.challenge Extension (challenge.py)

`challenge_category` Selection adds: `[('certification', 'Certifications')]`

### res.lang Override (res_lang.py)

When a language is deactivated:
1. `survey.user_input` records using that lang get `lang_id` set to False
2. If a survey's `lang_ids` consists ONLY of languages being deactivated: raise `UserError` (cannot remove all languages from a survey)
3. Otherwise: unlink the languages from `survey.lang_ids`

### ir.http Extension (ir_http.py)

- `_is_survey_frontend()`: regex matches URLs starting with optional locale prefix + `/survey/`
- `get_nearest_lang()`: when on survey frontend, forces language selection from installed languages (not active company languages) via `web_force_installed_langs=True` context

---

## Model Relationships (Complete)

```
survey.survey
    ├── question_and_page_ids ──1───────────────────► survey.question
    │       (One2many, cascade delete)                      │
    │       ├── is_page = False ─► question                │
    │       │       ├── suggested_answer_ids ──1───────────► survey.question.answer
    │       │       │       (question_id = parent)              │
    │       │       │       is_correct, answer_score            │
    │       │       │                                         │
    │       │       └── matrix_row_ids ──1──────────────► survey.question.answer
    │       │       (matrix_question_id = parent)              │
    │       │       value = row label                          │
    │       │                                                    │
    │       └── is_page = True ─► section (page)                │
    │                                                        │
    ├── user_input_ids ──1────────────────────────► survey.user_input
    │       (One2many, cascade delete)                    │
    │       ├── predefined_question_ids (Many2many) ──► survey.question
    │       ├── user_input_line_ids ──1───────────────► survey.user_input.line
    │       │       (user_input_id = parent)               │
    │       │       question_id ──────────────────────► survey.question
    │       │       suggested_answer_id ──────────────► survey.question.answer
    │       │       matrix_row_id ────────────────────► survey.question.answer
    │       │                                                │
    │       └── partner_id ──────────────────────────────────► res.partner
    │           email, nickname
    │
    └── certification_badge_id ──1──────────────────► gamification.badge
            certification_give_badge

gamification.badge
    └── survey_ids ──1─────────────────────────────────► survey.survey
            (certification_badge_id backref)

gamification.challenge
    └── challenge_category = 'certification' (added)

res.partner
    ├── certifications_count (computed)
    └── certifications_company_count (computed)
```

---

## SQL Constraints Summary

| Constraint | Model | Check |
|-----------|-------|-------|
| `unique(access_token)` | `survey.survey` | Access token unique across all surveys |
| `unique(session_code)` | `survey.survey` | Session code unique |
| `certification_check` | `survey.survey` | Certification requires scoring |
| `scoring_success_min_check` | `survey.survey` | Score % between 0 and 100 |
| `time_limit_check` | `survey.survey` | Positive time limit if is_time_limited |
| `attempts_limit_check` | `survey.survey` | Positive attempts if is_attempts_limited |
| `badge_uniq` | `survey.survey` | Each badge assigned to one survey max |
| `session_speed_rating_has_time_limit` | `survey.survey` | Speed rating needs positive time limit |
| `UNIQUE(access_token)` | `survey.user_input` | Token unique per attempt |
| `unique(answer_type, skipped)` | Implicit | Skipped XOR answer_type must hold |
| `_positive_len_min/max` | `survey.question` | Text length min/max non-negative |
| `_validation_length/float/date/datetime` | `survey.question` | Min <= max for all ranges |
| `_positive_answer_score` | `survey.question` | Non-negative answer_score |
| `_scored_datetime_have_answers` | `survey.question` | Scored datetime needs answer |
| `_scored_date_have_answers` | `survey.question` | Scored date needs answer |
| `_scale` | `survey.question` | Scale range 0-10, min < max |
| `_is_time_limited_have_time_limit` | `survey.question` | Per-question time limit positive |
| `_value_not_empty` | `survey.question.answer` | value OR value_image required |

---

## Security Architecture

### Access Groups

| Group | XML ID | Inherits | Members |
|-------|--------|----------|---------|
| Survey User | `survey.group_survey_user` | `base.group_user` | Officers who can create surveys |
| Survey Manager | `survey.group_survey_manager` | `group_survey_user` | Full access including delete |

### ir.rule Domains

**`survey.survey` + `survey.question` + `survey.question.answer`:**
- Manager: `[(1, '=', 1)]` — unrestricted access to all records
- User: `['|', ('restrict_user_ids', 'in', user.id), ('restrict_user_ids', '=', False)]`
  — can only access surveys where they are in `restrict_user_ids` OR `restrict_user_ids` is empty

**`survey.user_input` + `survey.user_input.line`:**
- Manager: `survey_type in ('assessment', 'custom', 'live_session', 'survey')`
  — excludes surveys from specialized modules (e.g., `website_slides_survey`)
- User: same survey_type filter + restrict_user_ids check

**`survey.invite`:**
- Manager: `[(1, '=', 1)]`
- User: restrict_user_ids check
- `perm_unlink = False` — invite wizards cannot be deleted by users (only managers)

### Invite Token vs Access Token

- `access_token` (UUID): identifies a single survey attempt. Unique per `survey.user_input`.
- `invite_token` (UUID): identifies an invite batch. Shared by all attempts sent in one invite wizard run. Used for grouping attempts when `is_attempts_limited=True`.

---

## Controller Routes

| Route | Method | Description |
|-------|--------|-------------|
| `GET /survey/start/<token>` | Start | Begin a survey (with optional `answer_token` param) |
| `GET /survey/test/<token>` | Test | Open survey in test mode (`test_entry=True`) |
| `POST /survey/submit/<token>/<answer_token>` | Submit | Submit answers for a page/survey |
| `POST /survey/next_question/<token>/<answer_token>` | Next | Advance to next question (live session) |
| `GET /survey/print/<token>` | Print | Printable/read-only view |
| `GET /survey/results/<survey_id>` | Results | Survey results page |
| `GET /survey/<id>/get_certification` | Download | PDF certification certificate |
| `GET /survey/<id>/certification_preview` | Preview | Preview certification PDF layout |
| `GET /survey/session/manage/<token>` | Manage | Host session management dashboard |
| `POST /survey/session/next_question/<token>` | Next | Advance live session question |
| `GET /s/<code>` | Join | Short URL for session join (6-char prefix of access_token) |
| `GET /survey/<token>/<section_id>/get_background_image` | Image | Serve background image |

---

## Odoo 18 → 19 Migration Notes

| Aspect | Odoo 18 | Odoo 19 |
|--------|---------|---------|
| Survey categorization | `state` field or no equivalent | `survey_type` selection field |
| Multi-language | Single language | `lang_ids` Many2many |
| Certification flag | Plain Boolean | Computed+stored from scoring_type |
| Attempt limiting | Always available | Auto-disabled for surveys with conditional questions |
| `is_attempts_limited` | Plain Boolean | Computed+stored |
| `certification_give_badge` | Plain Boolean | Computed+stored from login_required+certification |
| Session available | Separate logic | `session_available` computed field |
| Progress display | Fixed percentage | `progression_mode` (percent vs number) |
| Live session routing | `survey.session` controller | Dedicated `survey_session_manage` controller |
| Score storage | Computed on-demand | `store=True` on scoring fields |

---

## Related Documentation

- [Modules/mail](odoo-18/Modules/mail.md) — Email notifications, mail composer mixin
- [Modules/gamification](odoo-18/Modules/gamification.md) — Badge and challenge system, certification award flow
- [Core/API](odoo-18/Core/API.md) — ORM decorators: `@api.depends`, `@api.constrains`, `@api.model`, `@api.onchange`
- [Patterns/Workflow Patterns](odoo-18/Patterns/Workflow Patterns.md) — State machine: `new` → `in_progress` → `done`
- [Modules/website_slides](odoo-18/Modules/website_slides.md) — May extend survey with `survey_id` and completion tracking
