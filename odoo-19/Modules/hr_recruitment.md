---
type: module
module: hr_recruitment
tags: [odoo, odoo19, hr, recruitment, applicant, crm]
created: 2026-04-06
---

# Recruitment

## Overview

| Property | Value |
|----------|-------|
| **Name** | Recruitment |
| **Technical** | `hr_recruitment` |
| **Category** | Human Resources/Recruitment |
| **Version** | 1.1 |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description

Track the recruitment pipeline from job posting to hired employee. Manages job positions, applicants, recruitment stages, sources, and talent pools. Supports email aliases for each job, activities, documents, and talent pool management.

## Dependencies

| Module | Role |
|--------|------|
| `hr` | Base HR model (hr.employee, hr.department, hr.job base) |
| `calendar` | Interview meeting scheduling |
| `utm` | Source/medium/campaign tracking |
| `attachment_indexation` | Attachment full-text search |
| `web_tour` | Guided tour for onboarding |
| `digest` | Periodic KPI email digests |

## Models (22 model files)

| Model | File | Description |
|-------|------|-------------|
| `hr.applicant` | `models/hr_applicant.py` (1112 lines) | Core applicant model |
| `hr.job` | `models/hr_job.py` (418 lines) | Job position with alias |
| `hr.recruitment.degree` | `models/hr_recruitment_degree.py` | Education ranking |
| `hr.recruitment.source` | `models/hr_recruitment_source.py` | UTM source link per job |
| `hr.recruitment.stage` | `models/hr_recruitment_stage.py` | Pipeline stages |
| `hr.applicant.category` | `models/hr_applicant_category.py` | Applicant tags |
| `hr.applicant.refuse.reason` | `models/hr_applicant_refuse_reason.py` | Rejection reasons |
| `hr.talent.pool` | `models/hr_talent_pool.py` | Grouped candidates |
| `hr.department` | `models/hr_department.py` | Department (extended) |
| `hr.employee` | `models/hr_employee.py` | Employee (extended) |
| `calendar.event` | `models/calendar.py` | Meeting (extended) |
| `res.partner` | `models/res_partner.py` | Partner (extended) |
| `hr.job.platform` | `models/hr_job_platform.py` | Email-to-applicant routing |
| `mail.activity.plan` | `models/mail_activity_plan.py` | Activity plan (extended) |
| `digest.digest` | `models/digest.py` | Digest KPI (extended) |
| `utm.source` | `models/utm_source.py` | UTM source (extended) |
| `utm.campaign` | `models/utm_campaign.py` | UTM campaign (extended) |
| `res.company` | `models/res_company.py` | Company (extended) |
| `res.config.settings` | `models/res_config_settings.py` | Config (extended) |
| `ir.attachment` | `models/ir_attachment.py` | Attachment index init |
| `ir.ui.menu` | `models/ir_ui_menu.py` | (base extension) |
| `res.users` | `models/res_users.py` | (base extension) |

---

## L2: Field Types, Defaults, Constraints

### `hr.applicant`

**File:** `models/hr_applicant.py`
**Inherits:** `mail.thread.cc`, `mail.thread.main.attachment`, `mail.thread.blacklist`, `mail.thread.phone`, `mail.activity.mixin`, `utm.mixin`, `mail.tracking.duration.mixin`
**Mail tracking:** `_track_duration_field = 'stage_id'`
**_primary_email:** `'email_from'`
**_mailing_enabled:** `True`

#### Own Fields

| Field | Type | Attr | Default | Description |
|-------|------|------|---------|-------------|
| `sequence` | Integer | `index=True` | `10` | Sort order |
| `active` | Boolean | `index=True` | `True` | Archive vs delete |
| `partner_id` | Many2one | `index='btree_not_null'`, `copy=False` | — | Contact partner |
| `partner_name` | Char | — | — | Applicant name |
| `email_from` | Char | `compute='_compute_partner_phone_email'`, `inverse='_inverse_partner_email'`, `store=True`, `index='trigram'` | — | Email (synced from partner) |
| `email_normalized` | Char | `index='trigram'` | — | Inherited via `mail.thread.blacklist` |
| `partner_phone` | Char | `compute/inverse`, `store=True`, `index='btree_not_null'` | — | Phone (synced from partner) |
| `partner_phone_sanitized` | Char | `compute`, `store=True`, `index='btree_not_null'` | — | Phone after `_phone_format()` |
| `linkedin_profile` | Char | `index='btree_not_null'` | — | LinkedIn URL |
| `type_id` | Many2one | — | — | `hr.recruitment.degree` (education) |
| `availability` | Date | `tracking=True` | — | Available from date |
| `color` | Integer | — | `0` | Kanban color index |
| `employee_id` | Many2one | `index='btree_not_null'`, `copy=False` | — | Hired employee |
| `emp_is_active` | Boolean | `related='employee_id.active'` | — | Employee active |
| `employee_name` | Char | `related='employee_id.name'`, `readonly=False` | — | Synced from employee |
| `probability` | Float | — | — | (pipeline probability) |
| `stage_id` | Many2one | `compute='_compute_stage'`, `store=True`, `domain` | — | Current pipeline stage |
| `last_stage_id` | Many2one | — | — | Previous stage (for lost analysis) |
| `categ_ids` | Many2many | — | — | `hr.applicant.category` tags |
| `company_id` | Many2one | `compute='_compute_company'`, `store=True` | — | Company |
| `user_id` | Many2one | `compute='_compute_user'`, `store=True` | — | Recruiter |
| `date_closed` | Datetime | `compute='_compute_date_closed'`, `store=True`, `tracking=True`, `copy=False` | — | Hire date |
| `date_open` | Datetime | — | — | When `user_id` assigned |
| `date_last_stage_update` | Datetime | `index=True` | `fields.Datetime.now()` | Last stage change |
| `priority` | Selection | — | `'0'` | `0/1/2/3` (Normal/Good/Very Good/Excellent) |
| `job_id` | Many2one | `index=True`, `copy=False` | — | Job position |
| `salary_proposed_extra` | Char | `groups='group_hr_recruitment_user'` | — | Extra proposed conditions |
| `salary_expected_extra` | Char | `groups='group_hr_recruitment_user'` | — | Extra expected conditions |
| `salary_proposed` | Float | `aggregator="avg"` | — | Proposed salary |
| `salary_expected` | Float | `aggregator="avg"` | — | Expected salary |
| `department_id` | Many2one | `compute='_compute_department'`, `store=True` | — | Department (from job) |
| `day_open` | Float | `compute='_compute_day'`, `compute_sudo=True` | — | Days since creation to open |
| `day_close` | Float | `compute='_compute_day'`, `compute_sudo=True` | — | Days from creation to close |
| `delay_close` | Float | `compute="_compute_delay"`, `store=True`, `aggregator="avg"` | — | `day_close - day_open` |
| `kanban_state` | Selection | `copy=False` | `'normal'` | `normal/done/waiting/blocked` |
| `refuse_reason_id` | Many2one | `tracking=True` | — | Rejection reason |
| `meeting_ids` | One2many | — | — | `calendar.event` |
| `meeting_display_text` | Char | `compute` | — | "1 Meeting" / "Next Meeting" / "Last Meeting" / "No Meeting" |
| `meeting_display_date` | Date | `compute` | — | Next or last meeting date |
| `campaign_id` | Many2one | `ondelete='set null'` | — | UTM campaign |
| `medium_id` | Many2one | `ondelete='set null'` | — | UTM medium |
| `source_id` | Many2one | `ondelete='set null'` | — | UTM source |
| `interviewer_ids` | Many2many | `index=True`, `tracking=True`, `copy=False` | — | Interviewers (res.users) |
| `application_status` | Selection | `compute="_compute_application_status"`, `search="_search_application_status"` | — | `ongoing/hired/refused/archived` |
| `application_count` | Integer | `compute` | — | Related apps count |
| `applicant_properties` | Properties | — | — | Job-defined properties |
| `applicant_notes` | Html | — | — | Recruiter notes |
| `refuse_date` | Datetime | — | — | When refused |
| `talent_pool_ids` | Many2many | — | — | `hr.talent.pool` links |
| `pool_applicant_id` | Many2one | `index='btree_not_null'` | — | Talent pool master applicant |
| `is_pool_applicant` | Boolean | `compute` | — | `True` if `talent_pool_ids` set |
| `is_applicant_in_pool` | Boolean | `compute`, `search` | — | Direct or indirect pool membership |
| `talent_pool_count` | Integer | `compute` | — | Number of pools via email/phone/linkedin match |

**Indexes:**
- `_job_id_stage_id_idx = models.Index("(job_id, stage_id) WHERE active IS TRUE")` — composite partial index for pipeline queries

#### Key Methods

| Method | Description |
|--------|-------------|
| `_compute_partner_phone_email()` | Sync email/phone from `partner_id` |
| `_inverse_partner_email()` | Write partner_id and sync email/phone on applicant |
| `_compute_partner_phone_sanitized()` | Apply `_phone_format()` to partner_phone |
| `_compute_talent_pool_count()` | Count pools via direct + indirect (email/phone/linkedin) link |
| `_get_similar_applicants_domain()` | Build Domain for duplicate detection |
| `_compute_is_applicant_in_pool()` | Compute direct + indirect pool membership |
| `_search_is_applicant_in_pool()` | SQL-based search for pool membership |
| `_compute_day()` | Compute `day_open` and `day_close` |
| `_compute_delay()` | Compute `delay_close = day_close - day_open` |
| `_get_rotting_depends_fields()` | Extends mixin: adds `application_status`, `date_closed` to rotting dependencies |
| `_get_rotting_domain()` | Extends mixin: `ongoing` + `date_closed = False` filter for rotting |
| `_compute_meeting_display()` | Compute `meeting_display_text`/`date` from meetings |
| `_compute_application_status()` | Derive status from `refuse_reason_id`, `active`, `date_closed` |
| `_search_application_status()` | `Domain.OR` search across all status conditions |
| `_read_group_stage_ids()` | `group_expand` for stage_id — respects job-specific stage domain |
| `_compute_company()` | Company from department or job |
| `_compute_department()` | Department from job |
| `_compute_stage()` | Auto-set first non-fold stage on job change |
| `_compute_user()` | Recruiter from job's `user_id` |
| `_compute_date_closed()` | Auto-set `date_closed` when `stage_id.hired_stage=True`; clear when `hired_stage=False` |
| `create(vals_list)` | Set `date_open` on user assignment; auto-link talent pool; create interviewer access; notify interviewers |
| `write(vals)` | Track last stage; manage `no_of_recruitment`; talent pool sync (email, phone, linkedin, type_id); interviewer notification |
| `_track_template()` | Post stage template if not just_moved/just_unarchived |
| `_creation_subtype()` | Return `mt_talent_new` for pool applicants, `mt_applicant_new` for regular |
| `_track_subtype()` | Return `mt_applicant_stage_changed` on stage change |
| `_notify_get_reply_to()` | Alias = job's alias |
| `_get_customer_information()` | Fill from email/phone |
| `message_new(msg_dict, custom_values)` | Mail gateway: parse email, handle job platform routing, set stage from job |
| `_message_post_after_hook()` | Auto-link partner from chatter message |
| `create_employee_from_applicant()` | Create employee, copy attachments, write job/department |
| `_get_employee_create_vals()` | Return vals dict for employee creation (called by `action_create_employee`) |
| `_check_interviewer_access()` | Block interviewers (non-officers) from hire action |
| `archive_applicant()` | Open refuse reason wizard |
| `reset_applicant()` | Re-insert to first non-fold stage, clear refuse reason |
| `action_archive()` | Pass `just_unarchived` context |
| `action_unarchive()` | Pass `just_unarchived`, then `reset_applicant()` |
| `action_create_meeting()` | Open calendar with applicant partners and attachments |
| `action_open_attachments()` | Open ir.attachment list for applicant |
| `action_open_employee()` | Open hired employee form |
| `action_open_applications()` | Open similar applicants (same email/phone/linkedin/pool) |
| `action_talent_pool_stat_button()` | Navigate to pool master applicant |
| `link_applicant_to_talent()` | Set `pool_applicant_id` from matching talent |
| `action_talent_pool_add_applicants()` | Open talent pool wizard |
| `action_job_add_applicants()` | Open job add applicants wizard |
| `action_send_email()` | Open applicant send mail wizard |
| `_get_duration_from_tracking()` | Subtract refuse_date duration from stage tracking |
| `_compute_display_name()` | Use `partner_name` when `show_partner_name` context is set |

---

### `hr.job` (extends `hr.job`)

**File:** `models/hr_job.py`
**Inherits:** `mail.alias.mixin`, `hr.job`, `mail.activity.mixin`

#### Additional Fields

| Field | Type | Attr | Default | Description |
|-------|------|------|---------|-------------|
| `expected_employees` | Integer | groups | — | Target headcount |
| `no_of_employee` | Integer | groups | — | Current employee count |
| `requirements` | Text | groups | — | Job description |
| `user_id` | Many2one | groups | — | Recruiter responsible |
| `address_id` | Many2one | — | `_default_address_id()` | Job location address |
| `application_ids` | One2many | groups | — | Applications for this job |
| `application_count` | Integer | `compute` | — | Total active applicants |
| `open_application_count` | Integer | `compute` | — | Non-hired applicants |
| `all_application_count` | Integer | `compute` | — | All applicants (active + refused with reason) |
| `new_application_count` | Integer | `compute` | — | At first stage |
| `old_application_count` | Integer | `compute` | — | Not at first stage |
| `applicant_hired` | Integer | `compute` | — | Hired count |
| `manager_id` | Many2one | `related='department_id.manager_id'`, `store=True` | — | Department manager |
| `document_ids` | One2many | `compute` | — | Job + applicant attachments |
| `documents_count` | Integer | `compute` | — | Attachment count |
| `employee_count` | Integer | `compute` | — | Employees currently in job |
| `alias_id` | Many2one | groups | — | Email alias for inbound applications |
| `color` | Integer | — | — | Kanban color |
| `is_favorite` | Boolean | `compute`, `inverse` | — | Current user favorited |
| `favorite_user_ids` | Many2many | — | `[(6,0,[uid])]` | Users who favorited |
| `interviewer_ids` | Many2many | groups | — | Interviewers for this job |
| `extended_interviewer_ids` | Many2many | `compute`, `store=True` | — | All interviewers from job + all applicants |
| `industry_id` | Many2one | groups, tracking | — | Partner industry |
| `expected_degree` | Many2one | groups | — | Required degree for matching |
| `activity_count` | Integer | `compute` | — | Pending activities (SQL query) |
| `job_properties` | Properties | groups | — | Job properties definition |
| `applicant_properties_definition` | PropertiesDefinition | groups | — | Per-job applicant properties |
| `no_of_hired_employee` | Integer | `compute`, `store=True` | — | Hired during recruitment |
| `job_source_ids` | One2many | groups | — | `hr.recruitment.source` records |

**ACL groups on most fields:** `group_hr_recruitment_interviewer`

#### Key Methods

| Method | Description |
|--------|-------------|
| `_default_address_id()` | Last used address or company partner |
| `_address_id_domain()` | Private addresses in user's companies |
| `_get_default_favorite_user_ids()` | Default `favorite_user_ids = [uid]` |
| `_compute_no_of_hired_employee()` | Count of closed applicants via `_read_group` |
| `_compute_activities()` | Raw SQL count of pending activities per job |
| `_compute_extended_interviewer_ids()` | `search_read` with SUPERUSER to collect all applicant interviewers |
| `_compute_is_favorite()` / `_inverse_is_favorite()` | Toggle favorite via `job_favorite_user_rel` table |
| `_compute_document_ids()` | Attachments for job and its applicants |
| `_compute_all_application_count()` | Active + refused with reason |
| `_compute_application_count()` | Active applicants via `_read_group` |
| `_compute_open_application_count()` | Non-hired stages via `_read_group` |
| `_compute_employee_count()` | SUDO `_read_group` on `hr.employee` |
| `_get_first_stage()` | First non-fold stage for this job |
| `_compute_new_application_count()` | SQL with recursive CTE — counts applicants at first stage |
| `_compute_applicant_hired()` | Via hired_stage lookup |
| `_compute_old_application_count()` | `application_count - new_application_count` |
| `_alias_get_creation_values()` | Set `alias_model_id = hr.applicant`, `alias_defaults` includes job defaults |
| `create()` | Set `favorite_user_ids` default; `_create_recruitment_interviewers()` via SUDO |
| `write()` | On `interviewer_ids` change: `_remove_recruitment_interviewers()` + `_create_recruitment_interviewers()`; recruiter change: unsubscribe old, reassign ongoing apps |
| `_order_field_to_sql()` | Custom SQL ordering for `is_favorite` (subquery on `job_favorite_user_rel`) |
| `_creation_subtype()` | Return `mt_job_new` |
| `action_open_attachments()` | Open attachments for job and applicants |
| `action_open_activities()` | Open applicant list with activity filter |
| `action_open_employees()` | Open employee list scoped to this job |
| `_action_load_recruitment_scenario()` | Load demo scenario XML via `convert_file` |

---

### `hr.recruitment.degree`

| Field | Type | Attr | Description |
|-------|------|------|-------------|
| `name` | Char | `required=True`, `translate=True` | Degree name |
| `score` | Float | `required=True`, default `0` | Score 0-1, used in skill matching |
| `sequence` | Integer | default `1` | Sort order |

**Constraints:**
- `unique (name)` — name must be unique
- `check(score >= 0 and score <= 1)` — score is 0.0 to 1.0

---

### `hr.recruitment.source`

**Inherits:** `utm.source.mixin` (provides `source_id` field via UTM)

| Field | Type | Description |
|-------|------|-------------|
| `email` | Char (related) | Alias display name (readonly) |
| `has_domain` | Char (compute) | Whether alias has domain |
| `job_id` | Many2one | Job position, `ondelete='cascade'` |
| `alias_id` | Many2one | Mail alias, `ondelete='restrict'` |
| `medium_id` | Many2one | UTM medium, default `website` |
| `campaign_id` | Many2one | UTM campaign |

**Key Methods:**
- `_compute_has_domain()`: Check alias domain or company domain
- `create_alias()`: Creates `mail.alias` with `alias_name = job.alias_name or job.name + source.name`, defaults for UTM fields
- `create_and_get_alias()`: Create alias and return email string
- `unlink()`: Cascade delete alias via sudo

---

### `hr.recruitment.stage`

| Field | Type | Attr | Default | Description |
|-------|------|------|---------|-------------|
| `name` | Char | `required=True`, `translate=True` | Stage name |
| `sequence` | Integer | — | `10` | Sort order |
| `job_ids` | Many2many | — | — | Job-specific stages (empty = global) |
| `requirements` | Text | — | — | Requirements notes |
| `template_id` | Many2one | — | — | Mail template to post on entry |
| `fold` | Boolean | — | — | Fold in kanban (empty stages) |
| `hired_stage` | Boolean | — | — | Marks hire date when entered |
| `rotting_threshold_days` | Integer | — | `0` | Days before applicant rots (0 = disabled) |
| `legend_blocked` | Char | — | `'Blocked'` | Red kanban label |
| `legend_waiting` | Char | — | `'Waiting'` | Orange kanban label |
| `legend_done` | Char | — | `'Ready for Next Stage'` | Green kanban label |
| `legend_normal` | Char | — | `'In Progress'` | Grey kanban label |
| `is_warning_visible` | Boolean | `compute` | — | Warning when unchecking hired_stage with existing applicants |

**_compute_is_warning_visible:** Reads `_read_group` to count applicants at stage. Sets `is_warning_visible = True` when unchecking `hired_stage` if applicants exist at that stage.

---

### `hr.applicant.category`

| Field | Type | Attr | Description |
|-------|------|------|-------------|
| `name` | Char | `required=True` | Tag name |
| `color` | Integer | — | Color index, default `randint(1,11)` |

**Constraint:** `unique (name)`

---

### `hr.applicant.refuse.reason`

| Field | Type | Attr | Description |
|-------|------|------|-------------|
| `sequence` | Integer | default `10` | Sort order |
| `name` | Char | `required=True`, `translate=True` | Reason description |
| `template_id` | Many2one | domain `[('model', '=', 'hr.applicant')]` | Email template for refusal |
| `active` | Boolean | default `True` | Soft delete |

---

### `hr.talent.pool`

**Inherits:** `mail.thread`

| Field | Type | Description |
|-------|------|-------------|
| `active` | Boolean | default `True` |
| `name` | Char (required) | Pool title |
| `company_id` | Many2one | Company |
| `pool_manager` | Many2one | Manager user, default `env.user` |
| `talent_ids` | Many2many | `hr.applicant` talents |
| `no_of_talents` | Integer (compute) | Count via `_read_group` |
| `description` | Html | Pool description |
| `color` | Integer | default `randint(1,11)` |
| `categ_ids` | Many2many | Tags, `store=True` |

---

### `hr.department` (extends `hr.department`)

| Field | Type | Attr | Description |
|-------|------|------|-------------|
| `new_applicant_count` | Integer | `compute`, `compute_sudo=True` | Applicants at stage sequence <= 1 |
| `new_hired_employee` | Integer | `compute` | `no_of_hired_employee` sum via `_read_group` |
| `expected_employee` | Integer | `compute` | `no_of_recruitment` sum via `_read_group` |

---

### `calendar.event` (extends `calendar.event`)

| Field | Type | Attr | Description |
|-------|------|------|-------------|
| `applicant_id` | Many2one | `index='btree_not_null'`, `ondelete='set null'` | Link to applicant |

**`default_get()`:** Sets `default_res_model='hr.applicant'` and `default_res_id` from context.
**`create()`:** Copies applicant attachments to new calendar events.
**`_compute_is_highlighted()`:** Highlights events matching active applicant.

---

### `hr.job.platform`

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Platform name |
| `email` | Char | Email for inbound routing |
| `regex` | Char | Regex to extract applicant name from subject/body |

**Constraint:** `unique (email)`
**`create()` / `write()`:** Normalize email via `email_normalize()`

---

## L3: Cross-Module Integration, Override Patterns, Workflow Triggers

### Cross-Module Dependency Map

```
UTM (utm.source, utm.medium, utm.campaign)
  └─ hr.recruitment.source (links source to job)
  └─ utm_source.py (prevents source deletion when linked)
  └─ utm_campaign.py (prevents default campaign deletion)

Mail (mail.thread, mail.activity)
  └─ hr.applicant: full chatter, activity scheduling, tracking duration
  └─ hr.job: mail alias, activity count
  └─ mail.activity.plan: enables applicant plans

Calendar (calendar.event)
  └─ calendar.py: applicant_id on events, attachment copying

HR (hr.employee, hr.department)
  └─ hr_employee.py: applicant_ids on employee, hired log message
  └─ hr_department.py: recruitment stats on department

Digest (digest.digest)
  └─ digest.py: kpi_hr_recruitment_new_colleagues KPI

res.partner
  └─ res_partner.py: applicant_ids on partner

ir.attachment
  └─ ir_attachment.py: GIN trigram index on index_content for applicants

hr_recruitment_skills
  └─ Skill matching on applicants, talent pool skill sync
  └─ hr.job expected_degree (used for matching)
```

### Mail Gateway Flow

```
Inbound email to job alias (mail.alias alias_model_id=hr.applicant)
  --> MailGateway.message_new()
  --> Parse email (partner_name, email_from)
  --> Check hr.job.platform (email_normalized match)
     --> If platform match: extract name via regex from subject/body
  --> Set job_id from alias_defaults
  --> Call _compute_stage() from job's first non-fold stage
  --> super().message_new() creates hr.applicant record
  --> _compute_partner_phone_email() syncs from partner
  --> _create_recruitment_interviewers() grants interviewer access
```

### Stage-to-Hire Workflow

```
Applicant moves to stage where stage_id.hired_stage = True
  --> write() sees stage_id change + new_stage.hired_stage
  --> date_last_stage_update = now
  --> last_stage_id = old_stage_id
  --> If job_id.no_of_recruitment > 0: no_of_recruitment -= 1
  --> _compute_date_closed() fires: date_closed = now
  --> _track_template() posts stage template email
  --> action_create_employee() button available (creates hr.employee)
```

### Talent Pool Linkage Mechanism

```
talent_pool_ids (Many2many) set on applicant
  --> create() sets pool_applicant_id = self (makes this the talent master)
  --> _compute_is_pool() = True, _compute_is_applicant_in_pool() = True

Non-pool applicant created with matching email/phone/linkedin:
  --> _search_is_applicant_in_pool() SQL recursive CTE:
      - Direct: pool_applicant_id IS NOT NULL OR talent_pool_ids IS NOT NULL
      - Indirect: email_normalized, partner_phone_sanitized, linkedin_profile match
  --> _compute_is_applicant_in_pool() sets True for matches

Talent pool count computation (_compute_talent_pool_count):
  - Direct pool applicants: pool_applicant_id.talent_pool_ids length
  - Indirect: email/phone/linkedin match with pool applicants
```

### Interviewer Access Pattern

```
Job.create() or Applicant.create()
  --> interviewer_ids._create_recruitment_interviewers()
  --> Grants Interviewer group to each user in interviewer_ids
  --> Respects domain [('share', '=', False), ('company_ids', '=?', company_id)]

Job.write() or Applicant.write() on interviewer_ids:
  --> interviewers_to_clean._remove_recruitment_interviewers()
  --> self.sudo().interviewer_ids._create_recruitment_interviewers()

get_view() for form view:
  --> If user has group_hr_recruitment_interviewer but NOT group_hr_recruitment_user
  --> Use hr_applicant_view_form_interviewer (limited view)
```

### `no_of_recruitment` Counter Logic

```
Inside hr.applicant.write():
  if stage_id change:
    if new_stage.hired_stage and not old_stage.hired_stage:
        applicant.job_id.no_of_recruitment -= 1
    elif not new_stage.hired_stage and old_stage.hired_stage:
        applicant.job_id.no_of_recruitment += 1
```
Used in tandem with `_compute_no_of_hired_employee` (which counts `date_closed != False` applicants) to give a full picture of recruitment progress vs. target.

### UTM Protection on Uninstall

```
utm.source unlink():
  --> _unlink_except_linked_recruitment_sources() prevents deletion
      if hr.recruitment.source records reference the source

utm.campaign unlink():
  --> Prevents deletion of hr_recruitment.utm_campaign_job (default campaign)
```

---

## L4: Performance, Version Change Odoo 18->19, Security, Kanban

### Performance: Key Patterns

**1. Composite Partial Index**
```python
_job_id_stage_id_idx = models.Index("(job_id, stage_id) WHERE active IS TRUE")
```
Targets the kanban view query `WHERE job_id = X AND active = True`. PostgreSQL uses this index for pipeline filtering without scanning all records.

**2. SQL-Based `new_application_count` with Recursive CTE**
`_compute_new_application_count()` runs raw SQL:
```sql
WITH job_stage AS (
    SELECT DISTINCT ON (j.id) j.id AS job_id, s.id AS stage_id, s.sequence AS sequence
    FROM hr_job j
    LEFT JOIN hr_job_hr_recruitment_stage_rel rel ON rel.hr_job_id = j.id
    JOIN hr_recruitment_stage s ON s.id = rel.hr_recruitment_stage_id
        OR s.id NOT IN (SELECT hr_recruitment_stage_id FROM hr_job_hr_recruitment_stage_rel ...)
    WHERE j.id in %s
    ORDER BY 1, 3 asc
)
SELECT s.job_id, COUNT(a.id) AS new_applicant
FROM hr_applicant a
JOIN job_stage s ON s.job_id = a.job_id AND a.stage_id = s.stage_id AND a.active IS TRUE
WHERE a.company_id in %s OR a.company_id is NULL
GROUP BY s.job_id
```
Finds each job's first-stage (lowest sequence) and counts active applicants at that stage. Bypasses ORM overhead for this batch calculation.

**3. Raw SQL for Activity Count**
`_compute_activities()` runs direct SQL instead of ORM `_read_group`:
```sql
SELECT app.job_id, COUNT(*) AS act_count
FROM mail_activity act
JOIN hr_applicant app ON app.id = act.res_id
JOIN hr_recruitment_stage sta ON app.stage_id = sta.id
WHERE act.user_id = %s AND act.res_model = 'hr.applicant'
  AND app.active AND app.job_id IN %s
  AND sta.hired_stage IS NOT TRUE
  AND COALESCE(act.active, TRUE) = TRUE
GROUP BY app.job_id
```
Filters out hired-stage activities and inactive activities in a single pass.

**4. `extended_interviewer_ids` uses `SUPERUSER_ID`**
`_compute_extended_interviewer_ids()` runs `search_read` with `with_user(SUPERUSER_ID)` because `hr_referral` module may restrict applicant read access. Collecting all applicant interviewers requires bypassing that restriction.

**5. GIN Trigram Index on Attachments**
`ir_attachment.init()` creates a partial GIN index:
```sql
CREATE INDEX ir_attachment_index_content_applicant_trgm_idx
ON ir_attachment USING gin (unaccent(index_content) gin_trgm_ops)
WHERE res_model = 'hr.applicant'
```
Enables fast trigram search within applicant attachment content.

**Performance Risk Points:**
- `_compute_matching_skill_ids` (in `hr_recruitment_skills`) calls `filtered()` per applicant batch. Large applicant lists with `matching_job_id` context force per-row recomputation.
- `_compute_talent_pool_count` indirect lookup does multiple SQL searches per applicant batch.

---

### Version Change: Odoo 18 -> 19

**Manifest:** Version bumped from `1.0` to `1.1`.

**Key additions in Odoo 19:**

| Feature | Details |
|---------|---------|
| **Talent Pool System** | New model `hr.talent.pool` with `talent_pool_ids`, `pool_applicant_id`, `_compute_is_applicant_in_pool`, `_search_is_applicant_in_pool` SQL CTE |
| **Rotting Mechanism** | `mail.tracking.duration.mixin` integration with `_get_rotting_depends_fields` + `_get_rotting_domain`; `rotting_threshold_days` per stage |
| **Application Status** | New computed/searchable field `application_status` (ongoing/hired/refused/archived) with `Domain.OR` search |
| **`Domain` ORM Class** | Used throughout for composable domain building (`Domain.FALSE`, `Domain.OR`, `Domain(...)`) |
| **Talent Pool Count** | New `talent_pool_count` computed field with indirect email/phone/linkedin linking |
| **`refuse_date` field** | Records when applicant was refused |
| **`interviewer_ids` on applicant** | Direct assignment on applicant (not just via job) |
| **`extended_interviewer_ids`** | Aggregates all interviewers from job + all applicants via `search_read` |
| **`no_of_hired_employee`** | New computed stored field counting hired applicants during recruitment |
| **`applicant_properties_definition`** | Per-job applicant properties schema |
| **`hr.job.platform`** | Email-to-applicant routing with regex name extraction |
| **Mail Activity Plan** | `mail.activity.plan` extended: `department_assignable` for applicants |
| **`is_starting` field** | Present in stage model |
| **`create_and_get_alias()`** | Method to create source alias and retrieve email |
| **`reset_applicant()`** | Re-insert archived applicants to first non-fold stage |
| **Interviewer form view** | Separate `hr_applicant_view_form_interviewer` for interviewer-only users |
| **`_compute_date_closed`** | Auto-sets hire date when `hired_stage` entered |
| **`_order_field_to_sql`** | Custom SQL ordering for `is_favorite` field |
| **UTM source protection** | Prevents UTM source deletion when linked to recruitment source |

---

### Security

**Group Hierarchy:**
```
base.group_user
    └─ hr_recruitment.group_hr_recruitment_interviewer (Interviewer)
            └─ hr_recruitment.group_hr_recruitment_user (Officer)
                    └─ hr_recruitment.group_hr_recruitment_manager (Administrator)
```

**Record Rules:**

| Rule | Model | Group | Domain | Access |
|------|-------|-------|--------|--------|
| `hr_applicant_comp_rule` | `hr.applicant` | `global` | `[('company_id', 'in', company_ids + [False])]` | All authenticated users |
| `hr_applicant_interviewer_rule` | `hr.applicant` | `group_hr_recruitment_interviewer` | `[('job_id.interviewer_ids', 'in', user.id), ('interviewer_ids', 'in', user.id)]` | Read+Write, no Create+Unlink |
| `hr_applicant_user_rule` | `hr.applicant` | `group_hr_recruitment_user` | `[(1, '=', 1)]` | Full access |
| `hr_job_user_rule` | `hr.job` | `group_hr_recruitment_user` | `[(1, '=', 1)]` | Full access |
| `hr_talent_pool_user_rule` | `hr.talent.pool` | `group_hr_recruitment_user` | `[(1, '=', 1)]` | Full access |
| `mail_message_user_rule` | `mail.message` | `group_hr_recruitment_user` | `[(1, '=', 1)]` | Full access (chatter) |
| `mail_plan_rule` | `mail.activity.plan` | `group_hr_recruitment_manager` | `[('res_model', '=', 'hr.applicant')]` | No Read (manage only) |
| `mail_plan_templates_rule` | `mail.activity.plan.template` | `group_hr_recruitment_manager` | `[('plan_id.res_model', '=', 'hr.applicant')]` | No Read (manage only) |

**Field-Level Groups:**
- Most `hr.job` fields: `group_hr_recruitment_interviewer`
- Salary fields on `hr.applicant`: `group_hr_recruitment_user`
- `applicant_ids` on `hr.employee`: `hr.group_hr_user`
- `talent_ids` on `hr.talent.pool`: `base.group_user`

**Interviewer Access Restriction:**
- Interviewers get their own form view (`hr_applicant_view_form_interviewer`) via `get_view()`
- `_check_interviewer_access()` blocks interviewers from `create_employee_from_applicant()`
- Interviewers CAN: see assigned applicants, view attachments, schedule meetings (with `create: True` context)
- Interviewers CANNOT: create applicants, refuse applicants, create employees, see all applicants

---

### Kanban Stage Mechanism

The kanban view for `hr.applicant` uses these stage fields:

| Field | Kanban Effect |
|-------|---------------|
| `fold` | Stage column hidden when empty |
| `legend_blocked/normal/waiting/done` | Color labels shown in stage header |
| `hired_stage` | Marks this stage as the "hired" stage; triggers `date_closed` auto-set and employee creation |
| `rotting_threshold_days` | Days before rotting activity (per `mail.activity.mixin` rotting mechanism) — visible as warning badge in kanban |
| `is_warning_visible` | Shown when unchecking `hired_stage` if applicants exist at stage |
| `template_id` | Email auto-sent via `_track_template()` when applicant enters stage |

**Applicant kanban state colors:**
- `normal` (grey): In Progress
- `done` (green): Ready for Next Stage
- `waiting` (orange): Waiting
- `blocked` (red): Blocked

**Stage transition behavior (write):**
- `stage_id` change: `kanban_state` resets to `'normal'`, `last_stage_id` saved, `date_last_stage_update` refreshed
- `kanban_state` change: `date_last_stage_update` refreshed
- Hiring stage entry: `job_id.no_of_recruitment -= 1` (counter decrement)
- Leaving hired stage: `job_id.no_of_recruitment += 1` (counter increment)

---

### Refuse/Hire Actions

**Refuse Flow (`archive_applicant`):**
```
Applicant clicks "Refuse"
  --> Opens wizard: applicant.get.refuse.reason
  --> Refuse reason (required) + optional email template + optional duplicate handling
  --> action_refuse_reason_apply():
      - Set refuse_reason_id, active=False, refuse_date=now()
      - If duplicates + duplicates flag: refuse duplicate applicants too
      - If send_mail: _prepare_send_refusal_mails() via message_post
```

**Hire Flow (`create_employee_from_applicant`):**
```
Applicant at hired_stage (stage_id.hired_stage = True)
  --> User clicks "Create Employee"
  --> _check_interviewer_access() (only officers/managers)
  --> Create res.partner if missing (requires partner_name)
  --> _get_employee_create_vals() builds employee vals dict
  --> Create hr.employee in clean context
  --> Copy applicant attachments to employee (unique by datas)
  --> Write job_id, department_id, work_email, work_phone on employee
  --> Return action opening employee form
```

---

## State Flow

```
Inbound email
  --> mail.alias (hr.applicant model)
  --> message_new() parses contact, sets job_id, stage from job
  --> create() sets date_open, notifies interviewers, auto-links talent pool

Applicant Created
  --> stage_id = job's first non-fold stage
  --> application_status = 'ongoing'
  --> company_id from department or job
  --> user_id from job.user_id
  --> interviewer_ids = job.interviewer_ids (via _create_recruitment_interviewers)

Stage Progression
  --> user drags kanban card to next stage
  --> write(): last_stage_id = old, date_last_stage_update = now, kanban_state = normal
  --> if template_id: _track_template() posts email
  --> if hired_stage: date_closed = now, no_of_recruitment -= 1

Hire
  --> user clicks "Create Employee"
  --> employee record created, attachments copied, job_id/dept set
  --> hr.employee.create() logs message via applicant_hired_template

Refuse
  --> user clicks "Refuse"
  --> archive_applicant() opens wizard
  --> action_refuse_reason_apply(): active=False, refuse_reason_id, refuse_date
  --> application_status = 'refused'
  --> if send_mail: refusal email sent

Archive (no reason)
  --> action_archive(): just_unarchived context, standard archive
  --> application_status = 'archived'

Unarchive
  --> action_unarchive(): just_unarchived context, then reset_applicant()
  --> Resets stage to first non-fold stage, clears refuse_reason_id
  --> application_status back to 'ongoing'
```

---

## Related

- [Modules/hr](HR.md)
- [Modules/calendar](calendar.md)
- [Modules/utm](utm.md)
- [Modules/hr_recruitment_survey](hr_recruitment_survey.md)
- [Modules/hr_recruitment_skills](hr_recruitment_skills.md)
- [Modules/digest](digest.md)
