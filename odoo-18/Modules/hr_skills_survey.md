---
Module: hr_skills_survey
Version: 18.0.0
Type: addon
Tags: #odoo18 #hr_skills_survey
---

## Overview
Skills Certification. Bridge between `hr_skills` and `survey`. When an employee completes a survey certification, a `hr.resume.line` of type 'certification' is added to their resume with expiration tracking. Supports validity periods (months) after which the certification expires. Auto-installs with `hr_skills` + `survey`.

## Models

### survey.survey (Extension)
Inherits from: `survey.survey`
File: `~/odoo/odoo18/odoo/addons/hr_skills_survey/models/survey_survey.py`

| Field | Type | Description |
|-------|------|-------------|
| certification_validity_months | Integer | Validity period in months. `0` = never expires. Added to existing certification fields |

### survey.user_input (Extension)
Inherits from: `survey.user_input`
File: `~/odoo/odoo18/odoo/addons/hr_skills_survey/models/survey_user.py`

**Methods:**
| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _mark_done | self | bool | Extends parent: if survey is a certification AND user succeeded, creates or updates `hr.resume.line` (display_type='certification') for the employee. Reads `certification_validity_months` to set `date_end`; skips if validity=0 (no expiry) |

**`_mark_done` Logic:**
1. Filters to `survey_id.certification=True` and `scoring_success=True`
2. Groups by `partner_id`; searches linked `hr.employee` via `user_id.partner_id`
3. For each (employee, survey) pair:
   - If existing `hr.resume.line` with same survey: overwrites it (handles retakes)
   - Else: creates new resume line with `date_start=today`, `date_end=today+validity_months`
4. Uses `html2plaintext(survey.description)` for resume description

### hr.resume.line (Extension)
Inherits from: `hr.resume.line`
File: `~/odoo/odoo18/odoo/addons/hr_skills_survey/models/hr_resume_line.py`

| Field | Type | Description |
|-------|------|-------------|
| display_type | Selection | Adds `('certification', 'Certification')` to existing types |
| department_id | Many2one | Related from `employee_id.department_id`, `store=True` |
| survey_id | Many2one(survey.survey) | Linked certification survey; `readonly=True` |
| expiration_status | Selection | `('expired' | 'expiring' | 'valid')`; `compute='_compute_expiration_status'`, `store=True` |

**Methods:**
| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _compute_expiration_status | self | None | `expired` if `date_end <= today`; `expiring` if `date_end - 3 months <= today`; else `valid`. Handles `False` date_end as always valid |

## Data Files
- `data/hr_resume_data.xml`: Creates `hr.resume.line.type` record for 'certification' display type (referenced as `hr_skills_survey.resume_type_certification`)
- `data/hr_resume_demo.xml`: Demo data for certification resume lines

## Security
- No custom ACL files — relies on `hr_skills` and `survey` ACLs
- Resume lines are created `sudo()` in `_mark_done` to avoid ACL issues

## Critical Notes
- **Idempotent retakes:** When an employee retakes and passes a certification, `_mark_done` finds the existing `hr.resume.line` for that (employee, survey) pair and updates it — effectively resetting the validity period
- **`certification_validity_months=0`:** Means no expiry — `date_end` is `False`, which is always `'valid'`
- **Expiring status:** Certification is "expiring" 3 months before expiry (`date_end + relativedelta(months=-3) <= today`)
- **`department_id` related+stored:** Convenience field for filtering certifications by department
- **v17→v18:** `certification_validity_months` field on `survey.survey` is new in v18; previously certification expiry was managed differently
