---
title: "Hr Skills Survey"
module: hr_skills_survey
type: module
generated: 2026-04-17
generator: orchestrator.py
---

# Hr Skills Survey

## Overview

Module `hr_skills_survey` — auto-generated from source code.

**Source:** `addons/hr_skills_survey/`
**Models:** 3
**Fields:** 4
**Methods:** 1

## Models

### hr.resume.line (`hr.resume.line`)

—

**File:** `hr_resume_line.py` | Class: `HrResumeLine`

#### Fields (3)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `department_id` | `Many2one` | — | — | Y | Y | — |
| `survey_id` | `Many2one` | Y | — | — | Y | — |
| `expiration_status` | `Selection` | Y | — | — | Y | — |


#### Methods (1)

| Method | Description |
|--------|-------------|
| `copy_data` | |


### survey.survey (`survey.survey`)

—

**File:** `survey_survey.py` | Class: `SurveySurvey`

#### Fields (1)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| `certification_validity_months` | `Integer` | — | — | — | — | Y |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |


### survey.user_input (`survey.user_input`)

Will add certification to employee's resume if
        - The survey is a certification
        - The user is linked to an employee
        - The user succeeded the test

**File:** `survey_user.py` | Class: `SurveyUser_Input`

#### Fields (0)

| Field | Type | Computed | Onchange | Related | Store | Required |
|-------|------|----------|----------|---------|-------|----------|
| — | — | — | — | — | — | — |


#### Methods (0)

| Method | Description |
|--------|-------------|
| — | — |




## Related

- [Modules/Base](base.md)
- [Modules/HR](HR.md)
