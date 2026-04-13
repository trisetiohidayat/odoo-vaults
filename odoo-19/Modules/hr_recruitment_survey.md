---
type: module
module: hr_recruitment_survey
tags: [odoo, odoo19, hr, recruitment, survey, interview]
created: 2026-04-06
---

# Recruitment Survey

## Overview

| Property | Value |
|----------|-------|
| **Name** | Hr Recruitment Interview Forms |
| **Technical** | `hr_recruitment_survey` |
| **Category** | Human Resources |
| **Version** | 1.0 |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description

Integrates survey/questionnaire functionality into the recruitment process. Allows defining interview forms for job positions and sending them to applicants.

## Dependencies

- `survey`
- `hr_recruitment`

## Key Models

| Model | Description |
|-------|-------------|
| `hr.applicant` | Applicant (inherited) |
| `hr.job` | Job position (inherited) |
| `survey.user_input` | Survey responses (linked to applicant) |

## hr.applicant (extends hr_recruitment.hr_applicant)

**File:** `models/hr_applicant.py`

### Additional Fields

| Field | Type | Description |
|-------|------|-------------|
| `survey_id` | Many2one | Survey linked to the job (related) |
| `response_ids` | One2many | Survey responses (survey.user_input) |

### Key Methods

| Method | Description |
|--------|-------------|
| `action_print_survey()` | Print survey (response if available, else template) |
| `action_send_survey()` | Open wizard to send survey to applicant |

### Workflow

1. Define a survey on the job position (`job_id.survey_id`)
2. Recruiter calls `action_send_survey()` on an applicant
3. If no `partner_id`, creates one from applicant name/email/phone
4. Opens `survey.invite` wizard pre-filled with:
   - Survey
   - Applicant partner
   - Applicant as `default_applicant_id`
   - Deadline set to now + 15 days
5. Survey responses are stored in `response_ids`

---

## hr.job (extends hr_recruitment.hr_job)

**File:** `models/hr_job.py`

No additional fields or methods. The survey is referenced through `survey_id` on `hr.applicant` which is computed from `job_id.survey_id`.

## survey.user_input

Linked to `hr.applicant` via `applicant_id` field (added by this module).

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `applicant_id` | Many2one | Applicant (added by this module) |

## Related

- [Modules/hr_recruitment](Modules/hr_recruitment.md)
- [Modules/survey](Modules/survey.md)
