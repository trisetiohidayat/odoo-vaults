# survey - Surveys, Assessments, and Certifications

## Overview

The `survey` module provides a comprehensive survey and assessment system for Odoo. It supports multiple question types, scoring, certifications, conditional questions, and live survey sessions.

## Module Information

- **Technical Name**: `survey`
- **Location**: `addons/survey/`
- **Depends**: `website`, `gamification`
- **License**: LGPL-3

---

## Models

### survey.survey

**File**: `models/survey_survey.py`

Main survey configuration:

```python
class Survey(models.Model):
    _name = 'survey.survey'
    _description = 'Survey'
    _inherit = ['mail.thread', 'mail.activity.mixin']
```

**Survey Type Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `survey_type` | Selection | survey/live_session/assessment/custom |
| `title` | Char | Survey title (required, translatable) |
| `description` | Html | Introduction text |
| `description_done` | Html | Completion message |
| `color` | Integer | Color index |

**Layout Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `question_and_page_ids` | One2many | All questions and pages |
| `questions_layout` | Selection | page_per_question/page_per_section/one_page |
| `questions_selection` | Selection | all/random |
| `progression_mode` | Selection | percent/number |
| `background_image` | Image | Background image |

**Access Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `access_mode` | Selection | public/token |
| `access_token` | Char | Public access token |
| `users_login_required` | Boolean | Require authentication |
| `users_can_go_back` | Boolean | Allow backward navigation |
| `restrict_user_ids` | Many2many | Users who can access |

**Scoring Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `scoring_type` | Selection | no_scoring/scoring_with_answers/scoring_without_answers |
| `scoring_success_min` | Float | Passing score percentage (default 80%) |
| `scoring_max_obtainable` | Float | Maximum possible score (computed) |

**Certification Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `certification` | Boolean | Is certification |
| `certification_mail_template_id` | Many2one | Success email template |
| `certification_report_layout` | Selection | modern_purple/blue/gold, classic variants |
| `certification_give_badge` | Boolean | Award badge on completion |
| `certification_badge_id` | Many2one | Badge to award |

**Attempt Management**:

| Field | Type | Description |
|-------|------|-------------|
| `is_attempts_limited` | Boolean | Limit number of attempts |
| `attempts_limit` | Integer | Max attempts per user |
| `is_time_limited` | Boolean | Time-limited survey |
| `time_limit` | Float | Time limit in minutes |

**Live Session Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `session_available` | Boolean | Live session available |
| `session_state` | Selection | ready/in_progress |
| `session_code` | Char | Attendee join code |
| `session_link` | Char | Session URL (computed) |
| `session_question_id` | Many2one | Current question |
| `session_show_leaderboard` | Boolean | Show leaderboard |
| `session_speed_rating` | Boolean | Reward quick answers |
| `session_speed_rating_time_limit` | Integer | Speed reward window (seconds) |

**Conditional Questions**:

| Field | Type | Description |
|-------|------|-------------|
| `has_conditional_questions` | Boolean | Contains conditional questions |

**Statistics Fields** (computed):

| Field | Type | Description |
|-------|------|-------------|
| `answer_count` | Integer | Total responses |
| `answer_done_count` | Integer | Completed responses |
| `answer_score_avg` | Float | Average score percentage |
| `answer_duration_avg` | Float | Average duration (hours) |
| `success_count` | Integer | Passed certifications |
| `success_ratio` | Integer | Success percentage |

---

### survey.question

**File**: `models/survey_question.py`

Questions and pages:

```python
class SurveyQuestion(models.Model):
    _name = 'survey.question'
    _description = 'Survey Question'
```

**Note**: Pages and questions use the same model. Pages have `is_page=True`.

**Basic Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `title` | Char | Question/p页 title |
| `description` | Html | Additional instructions |
| `survey_id` | Many2one | Parent survey |
| `sequence` | Integer | Display order |
| `is_page` | Boolean | Is this a page (section) |

**Question Type Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `question_type` | Selection | simple_choice/multiple_choice/text_box/char_box/numerical_box/scale/date/datetime/matrix |
| `is_scored_question` | Boolean | Count toward quiz score |
| `answer_score` | Float | Score for correct answer |

**Simple/Multiple Choice Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `suggested_answer_ids` | One2many | Answer options |
| `comments_allowed` | Boolean | Allow comments |
| `comments_message` | Char | Comment prompt |
| `comment_count_as_answer` | Boolean | Count comment as answer |

**Matrix Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `matrix_subtype` | Selection | simple/multiple |
| `matrix_row_ids` | One2many | Row labels |

**Scale Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `scale_min` | Integer | Minimum value (default 0) |
| `scale_max` | Integer | Maximum value (default 10) |
| `scale_min_label` | Char | Min label |
| `scale_mid_label` | Char | Mid label |
| `scale_max_label` | Char | Max label |

**Time Limit Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `is_time_limited` | Boolean | Time-limited question |
| `time_limit` | Integer | Seconds per question |

**Validation Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `validation_required` | Boolean | Enable validation |
| `validation_email` | Boolean | Must be valid email |
| `validation_length_min` | Integer | Min text length |
| `validation_length_max` | Integer | Max text length |
| `validation_min_float_value` | Float | Min numeric value |
| `validation_max_float_value` | Float | Max numeric value |
| `validation_min_date` | Date | Min date |
| `validation_max_date` | Date | Max date |
| `constr_mandatory` | Boolean | Required |
| `constr_error_msg` | Char | Error message |

**Conditional Question Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `triggering_question_ids` | Many2many | Questions triggering this |
| `triggering_answer_ids` | Many2many | Answers that trigger display |
| `allowed_triggering_question_ids` | Many2many | Valid trigger questions |
| `is_placed_before_trigger` | Boolean | Misplaced warning |

**Answer Options (survey.question.answer)**:

| Field | Type | Description |
|-------|------|-------------|
| `question_id` | Many2one | Parent question |
| `value` | Char | Answer text |
| `sequence` | Integer | Display order |
| `is_correct` | Boolean | Correct answer |
| `answer_score` | Float | Score for this answer |

---

### survey.user_input

**File**: `models/survey_user_input.py`

User's survey response:

```python
class SurveyUserInput(models.Model):
    _name = "survey.user_input"
    _description = "Survey User Input"
    _inherit = ['mail.thread', 'mail.activity.mixin']
```

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `survey_id` | Many2one | Survey taken |
| `state` | Selection | new/in_progress/done |
| `start_datetime` | Datetime | When started |
| `end_datetime` | Datetime | When completed |
| `deadline` | Datetime | Latest submission time |
| `access_token` | Char | Unique access token |
| `invite_token` | Char | Invitation token |
| `partner_id` | Many2one | Responding partner |
| `email` | Char | Response email |
| `nickname` | Char | Attendee nickname |
| `user_input_line_ids` | One2many | Answers |
| `predefined_question_ids` | Many2many | Questions to answer |

**Scoring Fields** (computed):

| Field | Type | Description |
|-------|------|-------------|
| `scoring_percentage` | Float | Score percentage |
| `scoring_total` | Float | Total points scored |
| `scoring_success` | Boolean | Passed certification |

**Attempt Management**:

| Field | Type | Description |
|-------|------|-------------|
| `is_attempts_limited` | Boolean | Limited attempts |
| `attempts_limit` | Integer | Max attempts |
| `attempts_count` | Integer | Total attempts made |
| `attempts_number` | Integer | Current attempt # |
| `survey_time_limit_reached` | Boolean | Time expired |

**Key Methods**:

```python
def _mark_in_progress(self):
    """Set state to in_progress and record start time"""

def _mark_done(self):
    """Complete the survey submission"""
    # Mark done
    # Send certification email if applicable
    # Award badge if configured
    # Notify subscribers

def action_print_answers(self):
    """Open print view of answers"""
    return {
        'type': 'ir.actions.act_url',
        'url': '/survey/print/{access_token}?answer_token={access_token}'
    }
```

---

### survey.user_input.line

**File**: `models/survey_user_input.py`

Individual answer:

```python
class SurveyUserInputLine(models.Model):
    _name = 'survey.user_input.line'
```

**Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `user_input_id` | Many2one | Parent response |
| `question_id` | Many2one | Question answered |
| `answer_type` | Char | Type: choice/char_box/text_box/number/date/datetime |
| `value_char_box` | Char | Text answer |
| `value_text` | Text | Multi-line text |
| `value_number` | Float | Numeric answer |
| `value_date` | Date | Date answer |
| `value_datetime` | Datetime | Datetime answer |
| `value_free_text` | Text | Free text comment |
| `suggested_answer_id` | Many2one | Selected answer option |
| `matrix_row_id` | Many2one | Matrix row selected |
| `skipped` | Boolean | Not answered |
| `answer_score` | Float | Points for this answer |

---

## Question Types

| Type | Description | Scoring |
|------|-------------|---------|
| `simple_choice` | Radio buttons (one answer) | Per-option |
| `multiple_choice` | Checkboxes (multiple answers) | Per-option |
| `text_box` | Multi-line text | None |
| `char_box` | Single-line text | None |
| `numerical_box` | Numeric input | Exact match or range |
| `scale` | 0-10 scale slider | Range match |
| `date` | Date picker | Exact date |
| `datetime` | Datetime picker | Exact datetime |
| `matrix` | Grid (rows x columns) | Per-cell or per-row |

---

## Scoring System

### Certification Score Calculation

```python
def _compute_scoring_values(self):
    """Calculate total possible score and user's score"""
    for question in self.predefined_question_ids:
        if question.question_type == 'simple_choice':
            # Max score = max correct answer score
            max(score for answer in suggestions if answer.is_correct)
        elif question.question_type == 'multiple_choice':
            # Sum of all positive scores
            sum(score for answer in suggestions if score > 0)
        elif question.is_scored_question:
            # Direct answer score
            question.answer_score

    # User's score = sum of answer_score from user_input_line_ids
    user_input.scoring_total = sum(line.answer_score)
    user_input.scoring_percentage = (total / possible) * 100
```

### Pass/Fail

```python
def _compute_scoring_success(self):
    user_input.scoring_success = (
        user_input.scoring_percentage >= survey.scoring_success_min
    )
```

---

## Conditional Questions

### Setup
1. Question A: Multiple choice with "Yes/No" options
2. Question B: `triggering_answer_ids` = Question A's "Yes" option

### Behavior
- Question B only displays if Question A's "Yes" is selected
- Works across pages and sections
- Multiple triggers supported (OR logic)

---

## Live Sessions

### Configuration
1. Set `survey_type = 'live_session'`
2. Configure `session_code`
3. Enable `session_show_leaderboard`
4. Optionally enable `session_speed_rating`

### Flow
1. Start session from survey form
2. Attendees join via code/link
3. Display question to all simultaneously
4. Collect answers in real-time
5. Show leaderboard after each question
6. End session and show final results

---

## Certification Workflow

1. Create survey with `certification = True`
2. Set `scoring_type` to enable scoring
3. Configure `scoring_success_min` (default 80%)
4. Optionally set `certification_mail_template_id`
5. Optionally set `certification_badge_id`
6. On completion:
   - If passed: Send email, award badge
   - If failed: Show results only

---

## Access Control

### Access Modes
- **Public**: Anyone with link can take
- **Token**: Must have valid invite token

### Authentication Options
- `users_login_required = True`: Must be logged in
- `restrict_user_ids`: Only these users can access

### Individual Access
- `access_token`: Unique URL per response
- `invite_token`: Group responses by invitation

---

## Website Routes

| Route | Description |
|-------|-------------|
| `/survey/{access_token}` | Take survey |
| `/survey/print/{access_token}` | Print answers |
| `/survey/results/{access_token}` | View results |
| `/survey/start/{invite_token}` | Start with invitation |

---

## Key Extension Points

1. **Custom Question Types**: Extend `question_type` selection
2. **Scoring Algorithms**: Override `_compute_scoring_values`
3. **Custom Validation**: Extend validation fields
4. **Certification Logic**: Override `_mark_done()`
5. **Live Session**: Extend controller for custom displays
