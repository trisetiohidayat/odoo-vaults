---
Module: hr_recruitment
Version: Odoo 18
Type: Core
Tags: [#hr, #recruitment, #applicant-tracking, #crm]
---

# hr_recruitment — Recruitment / Applicant Tracking

**Module path:** `odoo/addons/hr_recruitment/`
**Depends:** `hr`, `calendar`, `utm`, `attachment_indexation`, `web_tour`, `digest`
**Data files:** security, mail templates, recruitment stages/degrees, refuse reasons, tags, demo data

Odoo 18's recruitment module tracks the full job application lifecycle from candidate to employee. A key architectural change in Odoo 18: `hr.applicant` now requires a `candidate_id` (Many2one to `hr.candidate`), which serves as the canonical person record. An applicant is one application for one job; a candidate can have multiple applicants across different jobs.

---

## Core Models

### `hr.candidate` — Candidate (canonical person record)

The central record. A candidate is the person; their applicant records are the job-specific applications.

**File:** `addons/hr_recruitment/models/hr_candidate.py`
**Inherit:** `mail.thread.cc`, `mail.thread.main.attachment`, `mail.thread.blacklist`, `mail.thread.phone`, `mail.activity.mixin`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `active` | Boolean | Soft-delete flag, default True |
| `company_id` | Many2one `res.company` | Company scope, default from env |
| `partner_id` | Many2one `res.partner` | Linked contact (copy=False, index btree_not_null) |
| `partner_name` | Char | Candidate's display name |
| `email_from` | Char | Email, trigram indexed, computed from partner_id |
| `email_normalized` | Char | Normalized email, trigram indexed (inherited mail.thread.blacklist) |
| `partner_phone` | Char | Phone, computed from partner_id |
| `partner_phone_sanitized` | Char | Phone formatted for matching (index btree_not_null) |
| `linkedin_profile` | Char | LinkedIn URL |
| `type_id` | Many2one `hr.recruitment.degree` | Education level (Bachelor, Master, etc.) |
| `availability` | Date | When candidate can start, tracking enabled |
| `categ_ids` | Many2many `hr.applicant.category` | Tags |
| `color` | Integer | Color index for kanban, default 0 |
| `priority` | Selection | Computed from applicants' priorities (avg) |
| `user_id` | Many2one `res.users` | Candidate manager, domain: non-share users in company |
| `employee_id` | Many2one `hr.employee` | Hired employee link |
| `emp_is_active` | Boolean | Related to employee_id.active |
| `employee_name` | Char | Related to employee_id.name |
| `applicant_ids` | One2many `hr.applicant` | All applications for this candidate |
| `application_count` | Integer | Computed count of all applications |
| `applications_count` | Integer | Total offers (# Applications) |
| `refused_applications_count` | Integer | # Refused Offers |
| `accepted_applications_count` | Integer | # Accepted Offers |
| `similar_candidates_count` | Integer | Candidates sharing email or phone |
| `meeting_ids` | One2many `calendar.event` | All meetings |
| `meeting_display_text` | Char | "1 Meeting" / "Next Meeting" / "Last Meeting" |
| `meeting_display_date` | Date | Next or last meeting date |
| `attachment_count` | Integer | Document count |
| `candidate_properties` | Properties | Defined per company via `candidate_properties_definition` |
| `attachment_ids` | One2many `ir.attachment` | Documents attached to the candidate |

#### DB Index

```sql
CREATE INDEX hr_candidate_email_partner_phone_mobile
ON hr_candidate(email_normalized, partner_phone_sanitized);
```

#### Key Methods

- `_compute_partner_phone_email()` — syncs email/phone from `partner_id`
- `_inverse_partner_email()` — creates `res.partner` if missing; finds/creates via `find_or_create(candidate.email_from)`
- `_get_similar_candidates_domain()` — returns domain for same email_normalized or partner_phone_sanitized within company
- `_compute_similar_candidates_count()` — raw SQL for performance
- `_compute_applications_count()` — read_group over applicant_ids grouped by application_status
- `_compute_meeting_display()` — returns next/last meeting text + date
- `action_open_similar_candidates()` — opens kanban of similar candidates
- `action_open_applications()` — opens applicant's list
- `action_open_employee()` — opens the linked employee form
- `action_create_meeting()` — calendar view with candidate + recruiter as attendees; passes `create: True` context so interviewers without applicant create rights can still create meetings
- `create_employee_from_candidate()` — creates `hr.employee` from candidate; requires `_check_interviewer_access`
- `_get_employee_create_vals()` — returns dict for employee creation: name, work_contact_id, private address fields, `candidate_id` set on employee, phone
- `_check_interviewer_access()` — raises if user is interviewer but not recruiter user

#### Ondelete Constraints

- `_unlink_except_linked_employee()` — cannot delete candidate linked to an employee; archive instead

#### L4 Notes — Candidate as Person Model

`hr.candidate` is the canonical person record. The candidate record stores contact info and availability independently of any specific job application. When `create_employee_from_candidate()` is called, it creates both the `res.partner` (if missing) and the `hr.employee`, populating private address fields from the partner. The `employee_id` field on candidate is a One2many in reverse (`hr.employee.candidate_id`), allowing the employee record to show its source candidate.

---

### `hr.applicant` — Job Application

**File:** `addons/hr_recruitment/models/hr_applicant.py`
**Inherit:** `mail.thread.cc`, `mail.thread.main.attachment`, `mail.activity.mixin`, `utm.mixin`, `mail.tracking.duration.mixin`
**Track duration field:** `stage_id`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `candidate_id` | Many2one `hr.candidate` | **Required** — the person, index=True |
| `partner_id` | Many2one `res.partner` | Related to candidate_id.partner_id |
| `partner_name` | Char | Computed from candidate, searchable, inverse writes candidate |
| `email_from` | Char | Related to candidate, readonly=False |
| `email_normalized` | Char | Related to candidate |
| `partner_phone` | Char | Related to candidate, readonly=False |
| `partner_phone_sanitized` | Char | Related to candidate |
| `linkedin_profile` | Char | Related to candidate, readonly=False |
| `type_id` | Many2one `hr.recruitment.degree` | Related to candidate, readonly=False |
| `availability` | Date | Related to candidate |
| `color` | Integer | Related to candidate |
| `employee_id` | Many2one `hr.employee` | Related to candidate |
| `emp_is_active` | Boolean | Related to candidate |
| `employee_name` | Char | Related to candidate |
| `active` | Boolean | Soft-delete, default True |
| `stage_id` | Many2one `hr.recruitment.stage` | Pipeline stage, ondelete=restrict |
| `last_stage_id` | Many2one `hr.recruitment.stage` | Previous stage (for lost analysis) |
| `kanban_state` | Selection | normal/done/blocked, default normal |
| `legend_blocked/done/normal` | Char | Related to stage_id fields |
| `job_id` | Many2one `hr.job` | Job position, domain by company |
| `department_id` | Many2one `hr.department` | Computed from job_id, store |
| `company_id` | Many2one `res.company` | Computed from dept then job, store |
| `user_id` | Many2one `res.users` | Recruiter, computed from job_id.user_id |
| `interviewer_ids` | Many2many `res.users` | Interviewers for this applicant |
| `create_date` | Datetime | Applied on (readonly) |
| `date_open` | Datetime | When recruiter assigned |
| `date_closed` | Datetime | Hire date, computed from stage_id.hired_stage |
| `date_last_stage_update` | Datetime | Last stage change time, index=True |
| `priority` | Selection | '0'=Normal, '1'=Good, '2'=Very Good, '3'=Excellent |
| `salary_expected` | Float | Expected salary (aggregator=avg) |
| `salary_proposed` | Float | Proposed salary |
| `salary_expected_extra` | Char | Extra benefits expected |
| `salary_proposed_extra` | Char | Extra benefits proposed |
| `categ_ids` | Many2many `hr.applicant.category` | Tags, computed from candidate + own |
| `campaign_id` | Many2one `utm.campaign` | UTM campaign |
| `medium_id` | Many2one `utm.medium` | UTM medium |
| `source_id` | Many2one `utm.source` | UTM source |
| `refuse_reason_id` | Many2one `hr.applicant.refuse.reason` | Refusal reason |
| `refuse_date` | Datetime | When refused |
| `application_status` | Selection | Computed: ongoing/hired/refused/archived |
| `other_applications_count` | Integer | Applications from same candidate or similar candidates |
| `applicant_properties` | Properties | Inherited from job's applicant_properties_definition |
| `applicant_notes` | Html | Free-form notes |
| `meeting_ids` | One2many `calendar.event` | Meetings (applicant_id on calendar.event) |
| `meeting_display_text` | Char | Computed from meetings |
| `meeting_display_date` | Date | Computed from meetings |
| `probability` | Float | Pipeline probability |
| `day_open` | Float | Days from create to date_open |
| `day_close` | Float | Days from create to date_closed |
| `delay_close` | Float | day_close - day_open (aggregator=avg) |
| `attachment_number` | Integer | Count of attachments |
| `attachment_ids` | One2many `ir.attachment` | Documents |

#### Key Computeds

- `_compute_stage()` — sets default stage from job's first non-folded stage on create; domain: `['|', ('job_ids', '=', False), ('job_ids', '=', job_id)]`
- `_compute_date_closed()` — if `stage_id.hired_stage` is True and no date_closed, sets to now; clears if not hired_stage
- `_compute_application_status()` — refused if refuse_reason_id, archived if not active, hired if date_closed, else ongoing
- `_search_application_status()` — maps status selection to domain (refused=`refuse_reason_id != None`, hired=`date_closed != False`, archived=`active=False`, ongoing=`active AND NOT date_closed`)
- `_compute_categ_ids()` — union of `candidate_id.categ_ids` and own categ_ids

#### Key Methods

- `create(vals_list)` — sets `date_open` if `user_id`, strips email, copies CV attachments from candidate to applicant, notifies new interviewers
- `write(vals)` — tracks stage changes (`last_stage_id`, `date_last_stage_update`, resets `kanban_state` to normal), handles interviewer add/remove notifications, propagates company to candidate
- `create_employee_from_applicant()` — calls `candidate_id.create_employee_from_candidate()`, then writes `job_id`, `job_title`, `department_id`, `work_email`, `work_phone` on the new employee
- `archive_applicant()` — opens `applicant.get.refuse.reason` wizard
- `reset_applicant()` — clears refuse_reason, resets to first non-folded stage
- `toggle_active()` — context `just_unarchived=True` triggers reset after unarchive
- `action_create_meeting()` — similar to candidate; adds department manager to attendees
- `action_open_employee()` — delegates to candidate's action
- `action_open_other_applications()` — domain includes same candidate + similar candidates
- `_track_template()` — posts stage template email (suppressed if `just_moved` or `just_unarchived` context)
- `_track_subtype()` — `mt_applicant_stage_changed` on stage change
- `message_new(msg, custom_values)` — email gateway handler; parses from email, creates/finds candidate, handles job_platform email parsing with regex
- `_message_post_after_hook()` — links new partner to applicants without partner_id with matching email
- `get_empty_list_help()` — renders "add skills to job and search Reserve" link + alias email
- `get_view()` — uses `hr_applicant_view_form_interviewer` form for interviewer group (non-recruiter users)
- `_get_duration_from_tracking()` — subtracts refuse_date duration from tracking for hired stage duration stats

#### DB Index

```sql
CREATE INDEX hr_applicant_job_id_stage_id_idx
ON hr_applicant(job_id, stage_id) WHERE active IS TRUE;
```

#### L4 Notes — Applicant as Application

`hr.applicant` is an application for a specific job. It requires `candidate_id`, which means all applicants are people already in the candidate pool. The `date_closed` is auto-set when `stage_id.hired_stage` is True — this is the "Hire Date". `date_last_stage_update` tracks pipeline velocity. The `application_status` computed field replaces the old pattern of checking state combinations; it directly maps refused/hired/archived/ongoing.

---

### `hr.job` — Job Position

**File:** `addons/hr_recruitment/models/hr_job.py`
**Inherit:** `mail.alias.mixin`, `hr.job` (from base hr module)

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `address_id` | Many2one `res.partner` | Job location, domain by company child contacts |
| `application_ids` | One2many `hr.applicant` | All applications for this job |
| `application_count` | Integer | Active application count |
| `all_application_count` | Integer | All (including archived with refuse_reason) |
| `new_application_count` | Integer | Applications at first non-folded stage |
| `old_application_count` | Integer | application_count - new_application_count |
| `applicant_hired` | Integer | Count of applicants in hired stages |
| `manager_id` | Many2one `hr.employee` | Related to department_id.manager_id (store=True) |
| `user_id` | Many2one `res.users` | Recruiter, default=current user |
| `allowed_user_ids` | Many2many `res.users` | Computed from company — non-share users in company |
| `interviewer_ids` | Many2many `res.users` | Interviewers |
| `extended_interviewer_ids` | Many2many `res.users` | Interviewers from job + all its applicants (store=True, SUPERUSER) |
| `document_ids` | One2many `ir.attachment` | Job docs + applicant docs |
| `documents_count` | Integer | Count of documents |
| `alias_id` | Many2one `mail.alias` | Email alias for incoming applications |
| `color` | Integer | Color for kanban |
| `is_favorite` | Boolean | Current user in favorite_user_ids |
| `favorite_user_ids` | Many2many `res.users` | Users who favorited this job |
| `industry_id` | Many2one `res.partner.industry` | Industry classification |
| `date_from` | Date | Mission start date (updates hired candidate availability) |
| `date_to` | Date | Mission end date |
| `activities_overdue` | Integer | Activities due today for user's applications in this job |
| `activities_today` | Integer | Overdue activities |
| `job_properties` | Properties | Company-defined job properties |
| `applicant_properties_definition` | PropertiesDefinition | Schema for applicant properties |
| `no_of_hired_employee` | Integer | Computed: count of applicants with date_closed, store=True |

#### Key Methods

- `_get_first_stage()` — first non-folded stage for this job or global
- `_compute_new_application_count()` — raw SQL finding first stage per job and counting
- `_compute_extended_interviewer_ids()` — SUPERUSER search_read to collect interviewers from job + all its applicants
- `_compute_allowed_user_ids()` — all non-share users in the job's company
- `_alias_get_creation_values()` — sets alias_model to hr.applicant, defaults: job_id, department_id, company_id, user_id
- `create(vals_list)` — initializes favorite_user_ids, creates LinkedIn recruitment source, calls `_create_recruitment_interviewers()`, subscribes department manager + recruiter to job chatter
- `write(vals)` — deactivates applications when job deactivated, manages interviewer group membership, resubscribes manager/recruiter on change, updates hired candidate availability if date_to changes, syncs alias_defaults
- `_order_field_to_sql()` — special handling for `is_favorite` sort using subquery on job_favorite_user_rel
- `action_open_attachments()` — opens attachment list for job + applicants
- `_action_load_recruitment_scenario()` — loads demo scenario data from XML

#### L4 Notes — Job as Hiring Plan

`hr.job` represents a hiring plan (not just a vacancy). `no_of_recruitment` (inherited from base hr.job) is the target headcount; `no_of_hired_employee` is auto-computed from hired stage applicants. Interviewers on a job automatically get the `group_hr_recruitment_interviewer` group. When date_to changes on a job with hired applicants, those applicants' `availability` is updated to date_to + 1 day.

---

### `hr.recruitment.stage` — Pipeline Stage

**File:** `addons/hr_recruitment/models/hr_recruitment_stage.py`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Stage name, translate=True, required |
| `sequence` | Integer | Order, default 10 |
| `job_ids` | Many2many `hr.job` | Job-specific stages (others use global stages) |
| `requirements` | Text | Internal requirements notes |
| `template_id` | Many2one `mail.template` | Auto-send email template on stage entry |
| `fold` | Boolean | Fold in kanban when empty |
| `hired_stage` | Boolean | Marks this as the hired stage (sets date_closed) |
| `legend_blocked/done/normal` | Char | Kanban label text, defaults: Blocked/Ready for Next Stage/In Progress |
| `is_warning_visible` | Boolean | Computed: shows warning if hired_stage was just unchecked and there are existing applicants |

#### L4 Notes

When `hired_stage` is True, applicants entering this stage get `date_closed` auto-set. Only one stage per job (or globally) should be marked as `hired_stage`. The warning visible when unchecking it helps catch accidental changes.

---

### `hr.recruitment.degree` — Education Level

**File:** `addons/hr_recruitment/models/hr_recruitment_degree.py`

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Degree name, translate=True, required |
| `sequence` | Integer | Order, default 1 |

**SQL constraint:** unique(name)

Used to classify candidate education: Graduate, Bachelor Degree, Master Degree, Doctoral Degree.

---

### `hr.recruitment.source` — Recruitment Source

**File:** `addons/hr_recruitment/models/hr_recruitment_source.py`
**Inherit:** `utm.source.mixin`

| Field | Type | Description |
|-------|------|-------------|
| `source_id` | Many2one `utm.source` | Inherited from mixin |
| `name` | Char | Source name (from utm.source.name) |
| `email` | Char | Related alias display name |
| `has_domain` | Char | Computed: whether alias has a domain configured |
| `job_id` | Many2one `hr.job` | Associated job, ondelete=cascade |
| `alias_id` | Many2one `mail.alias` | Email alias, ondelete=restrict |
| `medium_id` | Many2one `utm.medium` | UTM medium, default=website |

#### Key Methods

- `create_alias()` — creates mail.alias for this source with job defaults (job_id, campaign_id, medium_id, source_id); campaign fixed to `utm_campaign_job`
- `unlink()` — cascades alias deletion to avoid orphaned aliases

---

### `hr.applicant.category` — Applicant Tag

**File:** `addons/hr_recruitment/models/hr_applicant_category.py`

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Tag name, required, unique |
| `color` | Integer | Random color 1-11 on default |

---

### `hr.applicant.refuse.reason` — Refusal Reason

**File:** `addons/hr_recruitment/models/hr_applicant_refuse_reason.py`

| Field | Type | Description |
|-------|------|-------------|
| `sequence` | Integer | Order, default 10 |
| `name` | Char | Reason description, translate=True, required |
| `template_id` | Many2one `mail.template` | Rejection email template |
| `active` | Boolean | Soft-delete, default True |

---

### `hr.job.platform` — Job Platform (external job boards)

**File:** `addons/hr_recruitment/models/hr_job_platform.py`

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Platform name, required |
| `email` | Char | Inbound email address, required, unique, email_normalized |
| `regex` | Char | Regex to extract candidate name from email subject/body |

Used to parse incoming emails from external job boards (LinkedIn, Indeed, Jobsdb). The regex extracts the candidate name from the email subject/body. If the incoming email is from a job platform, no partner is created on the applicant (email field is also not set).

---

## Extended Models

### `hr.employee` — Extended (from `hr`)

**File:** `addons/hr_recruitment/models/hr_employee.py`

| Field | Type | Description |
|-------|------|-------------|
| `candidate_id` | One2many `hr.candidate` | Reverse of `hr.candidate.employee_id` |

#### Methods

- `_get_partner_count_depends()` — adds `candidate_id` to partner count dependencies
- `_get_related_partners()` — includes candidate's partner in related partners
- `create(vals_list)` — if employee has candidate_id, posts `candidate_hired_template` message on the candidate

#### L4 Notes

When an employee is hired via `create_employee_from_candidate()`, a message is posted on the candidate record via the `candidate_hired_template` view. The candidate_id on employee allows looking up all candidate records for a given employee.

---

### `hr.department` — Extended (from `hr`)

**File:** `addons/hr_recruitment/models/hr_department.py`

| Field | Type | Description |
|-------|------|-------------|
| `new_applicant_count` | Integer | Applicants in stage sequence <= 1 (read_group permission check) |
| `new_hired_employee` | Integer | Sum of job no_of_hired_employee |
| `expected_employee` | Integer | Sum of job no_of_recruitment |

---

### `res.company` — Extended (from `base`)

**File:** `addons/hr_recruitment/models/res_company.py`

| Field | Type | Description |
|-------|------|-------------|
| `candidate_properties_definition` | PropertiesDefinition | Candidate property schema |
| `job_properties_definition` | PropertiesDefinition | Job property schema |

---

### `calendar.event` — Extended (from `calendar`)

**File:** `addons/hr_recruitment/models/calendar.py`

| Field | Type | Description |
|-------|------|-------------|
| `applicant_id` | Many2one `hr.applicant` | Linked applicant, index btree_not_null, ondelete=set null |
| `candidate_id` | Many2one `hr.candidate` | Computed from applicant_id.candidate_id, store=True |

#### Methods

- `default_get()` — sets res_model/res_id/res_name for applicant_id or candidate_id contexts
- `create()` — copies applicant/candidate attachments to new calendar events
- `_compute_candidate_id()` — syncs from applicant_id
- `_compute_is_highlighted()` — highlights event matching active applicant in calendar view

---

### `utm.campaign` — Extended (from `utm`)

**File:** `addons/hr_recruitment/models/utm_campaign.py`

- `_unlink_except_utm_campaign_job()` — prevents deletion of `utm_campaign_job` ref

---

### `utm.source` — Extended (from `utm`)

**File:** `addons/hr_recruitment/models/utm_source.py`

- `_unlink_except_linked_recruitment_sources()` — shows which jobs use the source before allowing deletion (already blocked by ondelete='restrict' on the relation)

---

### `res.users` — Extended (from `base`)

**File:** `addons/hr_recruitment/models/res_users.py`

- `_create_recruitment_interviewers()` — adds `group_hr_recruitment_interviewer` to users (except those already in recruitment group) who are set as interviewers on any job
- `_remove_recruitment_interviewers()` — removes group from users who are no longer interviewers on any job or application and not in recruitment group

Called from `hr.job.create()` and `hr.job.write()` when interviewer_ids change.

---

### `ir.ui.menu` — Extended (from `base`)

**File:** `addons/hr_recruitment/models/ir_ui_menu.py`

- `_load_menus_blacklist()` — hides Job menu for non-interviewers; hides Job Position for interviewer-but-not-user; hides Interviewer's submenu for user-level recruiters

---

### `mail.activity.plan` — Extended (from `mail`)

**File:** `addons/hr_recruitment/models/mail_activity_plan.py`

- `_compute_department_assignable()` — adds hr.applicant as department-assignable model

---

### `mail.activity.schedule` — Extended (from `mail`)

**File:** `addons/hr_recruitment/wizard/mail_activity_schedule.py`

- `_compute_plan_department_filterable()` — adds hr.applicant as department-filterable model

---

### `digest.digest` — Extended (from `digest`)

**File:** `addons/hr_recruitment/models/digest.py`

| Field | Type | Description |
|-------|------|-------------|
| `kpi_hr_recruitment_new_colleagues` | Boolean | Enable "New Employees" KPI |
| `kpi_hr_recruitment_new_colleagues_value` | Integer | Computed employee count |

---

### `hr.contract` — Extended (from `hr_contract`)

Referenced in the create flow: `create_employee_from_applicant()` sets `job_id`, `department_id`, `work_email`, `work_phone` on the created employee. The employee can then be linked to a contract via the hr_contract module.

---

## Wizards

### `applicant.get.refuse.reason`

**File:** `addons/hr_recruitment/wizard/applicant_refuse_reason.py`

| Field | Type | Description |
|-------|------|-------------|
| `refuse_reason_id` | Many2one `hr.applicant.refuse.reason` | Required |
| `applicant_ids` | Many2many `hr.applicant` | Selected applicants |
| `send_mail` | Boolean | Compute: has template and no applicants without email |
| `template_id` | Many2one `mail.template` | From refuse_reason_id.template_id |
| `applicant_without_email` | Text | Warning if any applicant has no email |
| `duplicates` | Boolean | Check to auto-refuse duplicate candidates |
| `duplicates_count` | Integer | Count of similar candidates |
| `single_applicant_email` | Char | Editable email for single applicant |

#### `action_refuse_reason_apply()`

1. If duplicates=true and one applicant selected, finds similar candidates and adds their applications to refused set
2. Writes `refuse_reason_id`, `active=False`, `refuse_date=now` on all refused applications
3. Sends email via template (batch for multi, post for single) using `hr_recruitment.mail_notification_light_without_background` layout

---

### `applicant.send.mail`

**File:** `addons/hr_recruitment/wizard/applicant_send_mail.py`
**Inherit:** `mail.composer.mixin`

Sends email to one or more applicants. Creates `res.partner` for applicants without one. Copies attachments to each applicant. Renders subject/body per applicant using template.

---

### `candidate.send.mail`

**File:** `addons/hr_recruitment/wizard/candidate_send_mail.py`
**Inherit:** `mail.composer.mixin`

Mirror of applicant.send.mail for candidates. Creates partner if missing. Renders template per candidate.

---

## Security

**Groups:**
- `group_hr_recruitment_user` — full recruitment access (HR Officer level)
- `group_hr_recruitment_interviewer` — can see applicants in their jobs, schedule meetings, add notes, but cannot refuse or archive (Interviewer level)

The menu system hides menus based on these groups via `ir.ui.menu._load_menus_blacklist()`.

---

## Data — Default Stages

```
sequence 0: New          (template: congratulations email)
sequence 1: Initial Qualification
sequence 2: First Interview
sequence 3: Second Interview
sequence 4: Contract Proposal
sequence 5: Contract Signed  (fold=True, hired_stage=True)
```

## Default Degrees

Graduate (1), Bachelor Degree (2), Master Degree (3), Doctoral Degree (4)

## Default Refuse Reasons

1. Refused by applicant: salary (seq 10, not_interested template)
2. Refused by applicant: job fit (seq 11, not_interested template)
3. Does not fit job requirements (seq 12, refuse template)
4. Job already fulfilled (seq 13, refuse template)
5. Duplicate (seq 14, refuse template)
6. Spam (seq 15, refuse template)

## Job Platforms

- LinkedIn: `jobs-listings@linkedin.com`, regex: `New application:.*from (.*)`
- Jobsdb: `cs@jobsdb.com`, regex: `from (.+?) for`
- Indeed: `no-reply@indeed.com`, regex: `^([^ ]+ [^ ]+)`