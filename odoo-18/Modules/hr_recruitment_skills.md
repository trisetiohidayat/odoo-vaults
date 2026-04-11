---
Module: hr_recruitment_skills
Version: 18.0.0
Type: addon
Tags: #odoo18 #hr_recruitment_skills
---

## Overview
Recruitment - Skills Management. Extends `hr_recruitment` and `hr_skills` to track skills on candidates and applicants. Introduces a new `hr.candidate.skill` model mirroring `hr.employee.skill` but for candidates. Enables matching candidates to jobs based on skill overlap, showing matching score, missing skills, and matching skills on the candidate form. Auto-installs with `hr_skills` + `hr_recruitment`.

## Models

### hr.candidate.skill (NEW)
Inherits from: `base.model`
File: `~/odoo/odoo18/odoo/addons/hr_recruitment_skills/models/hr_candidate_skill.py`
`_name = 'hr.candidate.skill'` — a new model, not extending an existing one

| Field | Type | Description |
|-------|------|-------------|
| candidate_id | Many2one(hr.candidate) | Required, `ondelete='cascade'` |
| skill_id | Many2one(hr.skill) | `compute='_compute_skill_id'`, `store=True`, `readonly=False`; domain: same `skill_type_id` |
| skill_level_id | Many2one(hr.skill.level) | `compute='_compute_skill_level_id'`, `store=True`, `readonly=False`; domain: same `skill_type_id` |
| skill_type_id | Many2one(hr.skill.type) | Required |
| level_progress | Integer | Related from `skill_level_id.level_progress` |

**SQL Constraints:**
```
unique(candidate_id, skill_id) — "Two levels for the same skill is not allowed"
```

**Methods:**
| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _check_skill_type | self | None | `@constrains`: validates `skill_id` belongs to `skill_type_id.skill_ids` |
| _check_skill_level | self | None | `@constrains`: validates `skill_level_id` belongs to `skill_type_id.skill_level_ids` |
| _compute_skill_id | self | None | Clears `skill_id` if its type doesn't match `skill_type_id` |
| _compute_skill_level_id | self | None | Auto-sets to `default_level` skill level or first available; clears if no skill |

### hr.candidate (Extension)
Inherits from: `hr.candidate`
File: `~/odoo/odoo18/odoo/addons/hr_recruitment_skills/models/hr_candidate.py`

| Field | Type | Description |
|-------|------|-------------|
| candidate_skill_ids | One2many(hr.candidate.skill) | Direct line for skills |
| skill_ids | Many2many(hr.skill) | `compute='_compute_skill_ids'`, `store=True`; derived from `candidate_skill_ids` |
| matching_skill_ids | Many2many(hr.skill) | `compute='_compute_matching_skill_ids'`; intersection with job's `skill_ids` |
| missing_skill_ids | Many2many(hr.skill) | `compute='_compute_matching_skill_ids'`; job skills minus candidate skills |
| matching_score | Float | Percentage: `matching / total_job_skills * 100` |

**Methods:**
| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _compute_matching_skill_ids | self | None | Requires `active_id` context (= job_id). Sets matching, missing, score |
| _compute_skill_ids | self | None | Flattens `candidate_skill_ids.skill_id` into a Many2many |
| _get_employee_create_vals | self | dict | Overrides parent: also copies `candidate_skill_ids` → `employee_skill_ids` on employee creation |
| action_create_application | self | action | Creates `hr.applicant` records for each candidate, then navigates to the applications list |

### hr.applicant (Extension)
Inherits from: `hr.applicant`
File: `~/odoo/odoo18/odoo/addons/hr_recruitment_skills/models/hr_applicant.py`

| Field | Type | Description |
|-------|------|-------------|
| candidate_skill_ids | One2many | Related from `candidate_id.candidate_skill_ids`, `readonly=False` |
| skill_ids | Many2many | Related from `candidate_id.skill_ids`, `readonly=False` |

### hr.job (Extension)
Inherits from: `hr.job`
File: `~/odoo/odoo18/odoo/addons/hr_recruitment_skills/models/hr_job.py`

| Field | Type | Description |
|-------|------|-------------|
| skill_ids | Many2many(hr.skill) | Expected skills for this job |

**Methods:**
| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| action_search_matching_candidates | self | action | Opens a filtered list of candidates whose `skill_ids` overlap with the job's `skill_ids`, excluding candidates who already applied to this job |

## Security
File: `security/hr_recruitment_skills_security.xml`
- `hr.candidate.skill` ACLs via `security/ir.model.access.csv`
- `ir.rule`: Interviewers see skills only for candidates linked to their jobs; Officers see all

## Critical Notes
- **`matching_score` requires context:** `_compute_matching_skill_ids` reads `context['active_id']` as the `job_id`. This means it only computes when the candidate form is opened from a job context (via `action_search_matching_candidates`)
- **`skill_ids` on `hr.applicant`:** Linked via `candidate_id.skill_ids` — changes to candidate skills automatically reflect on applicants
- **`_get_employee_create_vals`:** When converting a candidate to an employee, skills are copied via this method
- **v17→v18:** New module in this form; `hr.candidate.skill` replaces older pattern of storing skills directly on the candidate
