---
title: "Hr Recruitment Survey"
module: hr_recruitment_survey
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Hr Recruitment Survey

## Overview

Module `hr_recruitment_survey` — auto-generated from source code.

**Source:** `addons/hr_recruitment_survey/`
**Models:** 4
**Fields:** 6
**Methods:** 6

## Models

### hr.applicant (`hr.applicant`)

If response is available then print this response otherwise print survey form (print template of the survey)

**File:** `hr_applicant.py` | Class: `HrApplicant`

#### Fields (2)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `survey_id` | `Many2one` | — | — | Y | — | — |
| `response_ids` | `One2many` | — | — | — | — | — |


#### Methods (2)

| Method | Description |
|--------|-------------|
| `action_print_survey` | |
| `action_send_survey` | |


### hr.job (`hr.job`)

—

**File:** `hr_job.py` | Class: `HrJob`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `survey_id` | `Many2one` | — | — | — | — | — |


#### Methods (2)

| Method | Description |
|--------|-------------|
| `action_test_survey` | |
| `action_new_survey` | |


### survey.survey (`survey.survey`)

—

**File:** `survey_survey.py` | Class: `SurveySurvey`

#### Fields (2)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `survey_type` | `Selection` | Y | — | — | — | — |
| `hr_job_ids` | `One2many` | Y | — | — | — | — |


#### Methods (2)

| Method | Description |
|--------|-------------|
| `get_formview_id` | |
| `action_survey_user_input_completed` | |


### survey.user_input (`survey.user_input`)

—

**File:** `survey_user_input.py` | Class: `SurveyUser_Input`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `applicant_id` | `Many2one` | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |




## Related

- [Modules/Base](base.md)
- [Modules/HR](HR.md)
