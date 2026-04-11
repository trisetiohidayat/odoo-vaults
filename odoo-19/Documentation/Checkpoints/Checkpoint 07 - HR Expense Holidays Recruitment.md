# Checkpoint 7: HR Expense, Holidays, Recruitment

**Date:** 2026-04-06
**Modules Completed:** 10

---

## Modules Documented

### hr_attendance (2.0)
Attendance tracking with check-in/check-out, overtime rules, kiosk mode, GPS tracking, auto check-out, absence detection.

### hr_contract
Module not found in source addons. Was referenced in original task but does not exist at the expected path. Skipped.

### hr_expense (2.1)
Expense submission, approval workflow, accounting integration, payment registration.

### hr_fleet (1.0)
Links fleet vehicles to HR employees. Synchronizes driver contact with employee. Tracks mobility cards, license plates.

### hr_holidays (1.6)
Time off management. Leave requests, allocations, accrual plans, mandatory days, calendar sync.

### hr_recruitment (1.1)
Recruitment pipeline. Job positions, applicants, stages, sources, talent pools, interviewer management.

### hr_recruitment_survey (1.0)
Interview forms via survey integration. Send surveys to applicants, track responses.

### hr_skills (1.0)
Skills and resume management. Skill types/levels, employee skills, certifications, resume lines, job skill requirements.

### hr_timesheet (1.0)
Timesheet tracking on projects. Employee time logging, cost calculation, favorite project, portal access.

### hr_work_entry (1.0)
Work entry management for payroll. Conflict detection, validation, splitting entries, work entry types.

---

## Key Models Per Module

| Module | Primary Models |
|--------|--------------|
| hr_attendance | hr.attendance, hr.attendance.overtime.line, hr.attendance.overtime.rule, hr.attendance.overtime.ruleset |
| hr_expense | hr.expense, hr.expense.sheet |
| hr_fleet | fleet.vehicle, hr.employee (extends) |
| hr_holidays | hr.leave, hr.leave.type, hr.leave.allocation, hr.leave.accrual.plan, hr.leave.mandatory.day |
| hr_recruitment | hr.applicant, hr.job, hr.recruitment.stage, hr.recruitment.source, hr.talent.pool |
| hr_recruitment_survey | hr.applicant (extends), survey.user_input |
| hr_skills | hr.skill.type, hr.skill, hr.skill.level, hr.employee.skill, hr.job.skill, hr.resume.line |
| hr_timesheet | account.analytic.line (extends) |
| hr_work_entry | hr.work.entry, hr.work.entry.type |

---

## Statistics

- **Fields documented:** 150+
- **Methods documented:** 80+
- **State flows:** 7
- **New models from source:** hr_skills mixins, work entry conflict detection, overtime rules

---

## Related Checkpoints

- [[Documentation/Checkpoints/Checkpoint 04 - POS Mail Event Gamification]] - Core HR, Calendar, Project, Product, Stock
- [[Documentation/Checkpoints/Checkpoint 06 - Website Fleet Rating Web Delivery]] - Rating, Fleet, Web, Delivery, SMS, Barcodes

---

## Next Steps

- hr_calendar, hr_homeworking, hr_homeworking_calendar
- hr_holidays_attendance, hr_holidays_homeworking, hr_work_entry_holidays
- hr_maintenance, hr_org_chart, hr_presence
- hr_recruitment_skills, hr_recruitment_sms
- hr_skills_event, hr_skills_slides, hr_skills_survey
- hr_hourly_cost, hr_livechat
