# Skills Certification (hr_skills_survey)

## Overview
- **Category:** Human Resources/Employees
- **Depends:** `hr_skills`, `survey`
- **Auto-install:** True
- **License:** LGPL-3

Adds survey certifications to employee resumes. When an employee passes a certification survey, a resume line is created. Supports certification validity periods.

## Models

### `survey.survey` (inherited)
Extends surveys with certification validity:

| Field | Type | Description |
|-------|------|-------------|
| `certification_validity_months` | Integer | Validity period in months. 0 = never expires |

### `hr.resume.line` (inherited via `hr_skills`)
Resume lines are created when a survey certification is awarded (triggered from `survey.user` completion).

### `survey.user` (inherited via `survey`)
Completion records track which employees have completed which certifications.

## Key Features
- Certification validity: `certification_validity_months` field allows time-limited certifications
- Resume lines created from passed surveys (via the `survey` module's completion triggers)
- `hr_resume_data.xml` — demo data for certification resume entries

## Related
- [Modules/hr_skills](Modules/hr_skills.md) — HR Skills base
- [Modules/survey](Modules/survey.md) — Survey/certification module
- [Modules/hr_skills](Modules/hr_skills.md) — Skills + eLearning
- [Modules/hr_skills](Modules/hr_skills.md) — Skills + Events
