---
tags: [odoo, odoo17, module, survey]
research_depth: medium
---

# Survey Module — Deep Reference

**Source:** `addons/survey/models/`

## Overview
Survey, quiz, and assessment builder. Create multi-page questionnaires with conditional logic, scoring, certification, and live session mode for real-time audience participation. All three main models inherit `mail.thread` for notifications.

## Architecture

### Models
- `survey.survey` — survey definition and settings
- `survey.question` — questions and pages (same model, distinguished by `is_page`)
- `survey.question.answer` — answer options for choice/matrix questions
- `survey.user_input` — a response session (one record per attempt)
- `survey.user_input.line` — individual answer lines
- `survey.survey_template` — pre-built templates
- `survey.badge` / `survey.challenge` — gamification for certifications

---

## survey.survey

**File:** `survey_survey.py`

Survey definition — like a form template. Tracks all response sessions via `user_input_ids`.

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `title` | Char (required, translate) | Survey name |
| `survey_type` | Selection | `survey` / `live_session` / `assessment` / `custom` |
| `active` | Boolean | Active state |
| `color` | Integer | Color index for kanban |
| `description` | Html | Intro text displayed on start page |
| `description_done` | Html | Completion/end message |
| `background_image` | Image | Background image |
| `background_image_url` | Char (computed) | URL for background image |
| `user_id` | Many2one `res.users` | Responsible (not share users) |
| `question_and_page_ids` | One2many `survey.question` | All sections and questions |
| `page_ids` | One2many (computed) | Pages only (`is_page=True`) |
| `question_ids` | One2many (computed) | Questions only (`is_page=False`) |
| `question_count` | Integer (computed) | Count of non-page questions |
| `questions_layout` | Selection | `page_per_question` / `page_per_section` / `one_page` |
| `questions_selection` | Selection | `all` / `random` (randomized per section) |
| `progression_mode` | Selection | `percent` / `number` |
| `is_attempts_limited` | Boolean (computed) | Limited attempts (disabled if conditional questions) |
| `attempts_limit` | Integer | Max attempts per user |
| `is_time_limited` | Boolean | Time-limited survey |
| `time_limit` | Float | Time limit in minutes |
| `users_can_go_back` | Boolean | Allow backward page navigation |
| `users_can_signup` | Boolean (computed) | Signup allowed based on auth setting |
| `users_login_required` | Boolean | Require login even with valid token |
| `access_mode` | Selection | `public` (link) / `token` (invited only) |
| `access_token` | Char | UUID for public access links |
| `user_input_ids` | One2many `survey.user_input` | All response sessions |
| `answer_count` | Integer (computed) | Total registrations |
| `answer_done_count` | Integer (computed) | Completed attempts |
| `answer_score_avg` | Float (computed) | Average score percentage |
| `answer_duration_avg` | Float (computed) | Average duration in hours |
| `success_count` | Integer (computed) | Passed attempts |
| `success_ratio` | Integer (computed) | Pass rate percentage |
| `scoring_type` | Selection | `no_scoring` / `scoring_with_answers_after_page` / `scoring_with_answers` / `scoring_without_answers` |
| `scoring_success_min` | Float | Minimum pass percentage (default 80.0) |
| `scoring_max_obtainable` | Float (computed) | Sum of all question max scores |
| `certification` | Boolean (computed) | Is a certification (requires scoring) |
| `certification_mail_template_id` | Many2one `mail.template` | Certificate email template |
| `certification_report_layout` | Selection | `modern_purple`/`modern_blue`/`modern_gold`/`classic_purple`/`classic_blue`/`classic_gold` |
| `certification_give_badge` | Boolean | Award badge on passing |
| `certification_badge_id` | Many2one `gamification.badge` | Badge to award |
| `session_state` | Selection | `ready` / `in_progress` (live sessions) |
| `session_code` | Char | Join code for live sessions (auto-generated) |
| `session_link` | Char (computed) | Full session URL |
| `session_question_id` | Many2one `survey.question` | Current live question |
| `session_start_time` | Datetime | When the session started |
| `session_question_start_time` | Datetime | When current question started |
| `session_answer_count` | Integer (computed) | Active session participants |
| `session_question_answer_count` | Integer (computed) | Answers to current question |
| `session_show_leaderboard` | Boolean (computed) | Show leaderboard in live session |
| `session_speed_rating` | Boolean | Reward quick answers with more points |
| `has_conditional_questions` | Boolean (computed) | Has conditional questions |

### SQL Constraints
- `access_token_unique`: access token must be unique
- `session_code_unique`: session code must be unique
- `certification_check`: certification requires a scoring type (not `no_scoring`)
- `scoring_success_min_check`: pass percentage between 0 and 100
- `time_limit_check`: positive time limit if time-limited
- `attempts_limit_check`: positive attempts limit if limited
- `badge_uniq`: one badge per survey

### Session Code Generation
`_get_default_session_code()` generates codes starting at 4 digits, expanding to 5, 6... up to 10 digits if collisions occur. Returns `False` if no unique code can be found after 10-digit attempts.

---

## survey.question

**File:** `survey_question.py`

Questions and pages use the same model (`survey.question`). Pages are marked `is_page=True`. Questions reference pages via `page_id`.

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `title` | Char (required, translate) | Question or page title |
| `description` | Html | Help text, images, or video |
| `question_placeholder` | Char (computed, translate) | Placeholder text |
| `background_image` | Image | Section background |
| `background_image_url` | Char (computed) | Background image URL |
| `survey_id` | Many2one `survey.survey` | Parent survey (cascade delete) |
| `sequence` | Integer | Display order |
| `is_page` | Boolean | Marks this record as a section/page |
| `page_id` | Many2one `survey.question` (computed) | Parent page for questions |
| `question_ids` | One2many `survey.question` (computed) | Questions within this page |
| `random_questions_count` | Integer | Random questions to pick from this section |
| `questions_selection` | Selection (related) | `all` or `random` |
| `question_type` | Selection | Type of question (see below) |
| `is_scored_question` | Boolean | Contributes to quiz score |
| `answer_numerical_box` | Float | Correct answer for numerical questions |
| `answer_date` | Date | Correct date answer |
| `answer_datetime` | Datetime | Correct datetime answer |
| `answer_score` | Float | Score for a correct answer |
| `suggested_answer_ids` | One2many `survey.question.answer` | Answer options for choice/matrix |
| `matrix_subtype` | Selection | `simple` (one per row) / `multiple` (multi per row) |
| `matrix_row_ids` | One2many `survey.question.answer` | Matrix row labels |
| `save_as_email` | Boolean | Save text answer as user email |
| `save_as_nickname` | Boolean | Save text answer as nickname |
| `is_time_limited` | Boolean | Per-question time limit (live sessions only) |
| `time_limit` | Integer | Time limit in seconds |
| `comments_allowed` | Boolean | Show comments field |
| `comments_message` | Char | Comment field label |
| `comment_count_as_answer` | Boolean | Comment text counts as a valid answer |
| `validation_required` | Boolean | Enable validation rules |
| `validation_email` | Boolean | Must be valid email |
| `validation_length_min` / `validation_length_max` | Integer | Text length range |
| `validation_min_float_value` / `validation_max_float_value` | Float | Numeric range |
| `validation_min_date` / `validation_max_date` | Date | Date range |
| `validation_min_datetime` / `validation_max_datetime` | Datetime | Datetime range |
| `validation_error_msg` | Char (translate) | Validation error message |
| `constr_mandatory` | Boolean | Answer is required |
| `constr_error_msg` | Char (translate) | Mandatory question error message |
| `triggering_answer_ids` | Many2many `survey.question.answer` | Answers that trigger this question |
| `triggering_question_ids` | Many2many (computed) | Questions containing triggering answers |
| `allowed_triggering_question_ids` | Many2many (computed) | Valid trigger questions (must precede this one) |
| `is_placed_before_trigger` | Boolean (computed) | Misplaced question warning |
| `user_input_line_ids` | One2many `survey.user_input.line` | All answer lines |

### Question Types

| Value | Label | Scoring |
|-------|-------|---------|
| `simple_choice` | Multiple choice: only one answer | Via `suggested_answer_ids.is_correct` |
| `multiple_choice` | Multiple choice: multiple answers | Via `suggested_answer_ids.answer_score` |
| `text_box` | Multiple lines text | No scoring |
| `char_box` | Single line text | No scoring |
| `numerical_box` | Numerical value | Via `answer_numerical_box` |
| `date` | Date | Via `answer_date` |
| `datetime` | Datetime | Via `answer_datetime` |
| `matrix` | Matrix (grid) | Via `suggested_answer_ids.answer_score` |

### Scoring Logic

`is_scored_question` is computed based on:
- `no_scoring` survey type: always `False`
- `date`/`datetime`: `True` if a correct answer is set
- `numerical_box`: `True` if `answer_numerical_box` is non-zero
- `simple_choice`/`multiple_choice`: `True` if any answer has `is_correct=True`
- All others: `False`

### SQL Constraints
```sql
CHECK (validation_length_min >= 0)
CHECK (validation_length_min <= validation_length_max)
CHECK (validation_min_float_value <= validation_max_float_value)
CHECK (validation_min_date <= validation_max_date)
CHECK (validation_min_datetime <= validation_max_datetime)
CHECK (answer_score >= 0)  -- non-multiple-choice questions
CHECK (is_scored_question != True OR question_type != 'datetime' OR answer_datetime is not null)
CHECK (is_scored_question != True OR question_type != 'date' OR answer_date is not null)
```

---

## survey.question.answer

**File:** `survey_question.py`

Predefined answer options for choice and matrix questions.

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `question_id` | Many2one `survey.question` | Parent question (XOR with matrix_question_id) |
| `matrix_question_id` | Many2one `survey.question` | Matrix row parent (XOR with question_id) |
| `question_type` | Selection (related) | Parent question type |
| `sequence` | Integer | Display order within question |
| `value` | Char (required, translate) | Label for the answer option |
| `value_image` | Image | Optional image |
| `value_image_filename` | Char | Image filename |
| `is_correct` | Boolean | Correct answer flag (simple/multiple choice) |
| `answer_score` | Float | Score for this answer (+ or -) |

---

## survey.user_input

**File:** `survey_user_input.py`

A response session — one record per person attempting the survey. Inherits `mail.thread` and `mail.activity.mixin`.

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `survey_id` | Many2one `survey.survey` (required, cascade) | Survey being taken |
| `scoring_type` | Selection (related) | Inherited from survey |
| `start_datetime` | Datetime (readonly) | When the attempt started |
| `end_datetime` | Datetime (readonly) | When the attempt was submitted |
| `deadline` | Datetime | Must complete before this time |
| `state` | Selection | `new` / `in_progress` / `done` |
| `test_entry` | Boolean | Is this a test/preview entry |
| `last_displayed_page_id` | Many2one `survey.question` | Last page the user saw |
| `is_attempts_limited` | Boolean (related) | Limited attempts flag |
| `partner_id` | Many2one `res.partner` | Logged-in respondent |
| `email` | Char | Email (for public access) |
| `nickname` | Char | Saved nickname |
| `token` | Char | Access token for public survey |
| `scoring_percentage` | Float | Computed score percentage |
| `scoring_success` | Boolean (computed) | Passed the survey |
| `attempts_count` | Integer | Number of attempts by this user |
| `user_input_line_ids` | One2many `survey.user_input.line` | All answer lines |

### State Machine

`new` -> `in_progress` (via `button_main`) -> `done` (via `_mark_done()`)

### Scoring Computation

`scoring_percentage` and `scoring_success` are computed by iterating all `user_input_line_ids`, summing `answer_is_correct` lines weighted by their question's answer score, then dividing by the survey's `scoring_max_obtainable`.

---

## survey.user_input.line

**File:** `survey_user_input.py`

Individual answer to a single question.

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `user_input_id` | Many2one `survey.user_input` (required) | Parent response session |
| `question_id` | Many2one `survey.question` | Question being answered |
| `answer_type` | Char | Type of answer provided |
| `value_text` | Char | Text answer (`text_box`, `char_box`) |
| `value_numerical_box` | Float | Numeric answer |
| `value_date` | Date | Date answer |
| `value_datetime` | Datetime | Datetime answer |
| `value_char_box` | Char | Single-line text answer |
| `suggested_answer_id` | Many2one `survey.question.answer` | Selected choice |
| `matrix_row_id` | Many2one `survey.question.answer` | Matrix row selected |
| `skipped` | Boolean | Question was skipped |
| `answer_is_correct` | Boolean (computed) | Answer is correct for scoring |
| `score` | Float (computed) | Points earned |

### Answer Types Per Question Type

| Question Type | Answer Column |
|---------------|---------------|
| `text_box` / `char_box` | `value_text` or `value_char_box` |
| `numerical_box` | `value_numerical_box` |
| `date` | `value_date` |
| `datetime` | `value_datetime` |
| `simple_choice` / `multiple_choice` | `suggested_answer_id` |
| `matrix` | `suggested_answer_id` + `matrix_row_id` |

---

## Survey Flow

### Public Survey (No Login)

1. User visits public URL with `access_token`
2. `survey.user_input` created in `new` state (or resumed if deadline not passed)
3. User navigates pages, answers stored in `survey.user_input.line`
4. On submit: `_mark_done()` called, state = `done`, score computed
5. `scoring_success` set based on `scoring_success_min` threshold

### Certified Survey

1. Same flow as above
2. If `scoring_success = True`:
   - Certificate PDF generated (via `certification_report_layout`)
   - `certification_mail_template_id` email sent with certificate attachment
   - `certification_give_badge` triggers `gamification.badge` award

### Live Session

1. Instructor starts session (`session_state = 'in_progress'`)
2. Participants join with `session_code`
3. Instructor controls question progression (`session_question_id`)
4. `session_speed_rating` adjusts scores based on answer timing
5. `session_show_leaderboard` displays ranking

### Conditional Questions

Questions with `triggering_answer_ids` are hidden until the triggering answer is selected. `triggering_answer_ids` are validated to only reference earlier questions (`survey.question` sequence order). Misplaced questions are flagged via `is_placed_before_trigger`.

---

## See Also
- [Modules/portal](modules/portal.md) — public survey access without login
- [Modules/mail](modules/mail.md) — email notifications
- [Modules/gamification](modules/gamification.md) — badges and challenges for certifications
- [Modules/website_survey](modules/website_survey.md) — public-facing survey pages
