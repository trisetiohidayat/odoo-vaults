---
Module: hr_recruitment_survey
Version: 18.0.0
Type: addon
Tags: #odoo18 #hr_recruitment_survey
---

## Overview
Recruitment - Interview Forms. Integrates the Survey module with Recruitment. Allows defining an interview form (survey) per job position, sending it to applicants, tracking responses, and printing results. Introduces a `survey_type = 'recruitment'` category and extensive access rules scoped to recruitment surveys.

## Models

### survey.survey (Extension)
Inherits from: `survey.survey`
File: `~/odoo/odoo18/odoo/addons/hr_recruitment_survey/models/survey_survey.py`

| Field | Type | Description |
|-------|------|-------------|
| survey_type | Selection | Adds `('recruitment', 'Recruitment')` to existing types; `ondelete='recruitment': 'set default'` |
| hr_job_ids | One2many(hr.job) | Jobs using this survey; `related` via `hr_job.survey_id` |

**Methods:**
| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _compute_allowed_survey_types | self | None | Adds `'recruitment'` to allowed types for users in `hr_recruitment.group_hr_recruitment_interviewer` or `survey.group_survey_user` |
| get_formview_id | access_uid=None | int | Returns `hr_recruitment_survey.survey_survey_view_form` for non-survey-user recruiters accessing recruitment surveys |
| action_survey_user_input_completed | self | action | Opens completed responses filtered to `survey_type == 'recruitment'` |

### hr.job (Extension)
Inherits from: `hr.job`
File: `~/odoo/odoo18/odoo/addons/hr_recruitment_survey/models/hr_job.py`

| Field | Type | Description |
|-------|------|-------------|
| survey_id | Many2one(survey.survey) | Interview form for this job |

**Methods:**
| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| action_test_survey | self | action | Opens the survey in test mode |
| action_new_survey | self | action | Creates a new survey titled "Interview Form: {job_name}" and links it to this job |

### hr.applicant (Extension)
Inherits from: `hr.applicant`
File: `~/odoo/odoo18/odoo/addons/hr_recruitment_survey/models/hr_applicant.py`

| Field | Type | Description |
|-------|------|-------------|
| survey_id | Many2one | Related from `job_id.survey_id`; readonly |
| response_ids | One2many(survey.user_input) | Survey responses for this applicant |

**Methods:**
| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| action_print_survey | self | action | Prints most recent 'done' response if available; falls back to latest draft; falls back to survey template |
| action_send_survey | self | action | Creates partner if missing; opens `survey.invite` wizard with applicant pre-filled; deadline = now + 15 days |

### survey.user_input (Extension)
Inherits from: `survey.user_input`
File: `~/odoo/odoo18/odoo/addons/hr_recruitment_survey/models/survey_user_input.py`

| Field | Type | Description |
|-------|------|-------------|
| applicant_id | Many2one(hr.applicant) | Linked applicant; `index='btree_not_null'` |

**Methods:**
| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _mark_done | self | bool | Overrides parent: posts a chatter message on the applicant when the survey is completed |

### survey.invite (Extension — Wizard)
Inherits from: `survey.invite`
File: `~/odoo/odoo18/odoo/addons/hr_recruitment_survey/wizard/survey_invite.py`

| Field | Type | Description |
|-------|------|-------------|
| applicant_id | Many2one(hr.applicant) | Single applicant being invited |

**Methods:**
| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _get_done_partners_emails | existing_answers | tuple | Extends parent: excludes already-completed applicant from resend |
| _send_mail | answer | mail | Also posts the sent email body as a chatter message on the applicant |
| action_invite | self | bool | Creates survey answer record for applicant, posts chatter notification, then calls `super()` |

## Security
Extensive survey-specific access rules in `security/hr_recruitment_survey_security.xml`:
- **Recruitment Manager:** CRUD on all recruitment-type surveys, questions, answers, user_inputs
- **Recruitment Officer:** Read all recruitment survey responses; send invites for unrestricted or self-assigned surveys
- **Interviewer:** Read-only on survey questions/answers for jobs they are assigned to as interviewer; send invites for those jobs

## Critical Notes
- **`survey_type` `ondelete='set default'`:** If a recruitment survey is deleted, the survey type reverts to the default (not deleted)
- **Response tracking:** `response_ids` on applicant accumulates all survey attempts; `action_print_survey` prioritizes completed (done) responses
- **Email gateway:** Survey invite creates a `survey.user_input` linked to the applicant; the `applicant_id` link enables the `_mark_done` chatter notification
- **Applicant auto-creation:** `action_send_survey` creates a `res.partner` for the applicant if `partner_id` is missing
- **v17→v18:** `hr.applicant` link to `survey.user_input` via `applicant_id` field (indexed `btree_not_null`) is new in v18 for efficient joining
