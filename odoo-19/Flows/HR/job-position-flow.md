---
type: flow
title: "Job Position Flow"
primary_model: hr.job
trigger: "User action — HR → Jobs → Create"
cross_module: true
models_touched:
  - hr.job
  - hr.department
  - hr.applicant
  - hr.employee
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[Flows/HR/department-creation-flow](department-creation-flow.md)"
  - "[Flows/HR/recruitment-applicant-flow](recruitment-applicant-flow.md)"
source_module: hr
created: 2026-04-07
version: "1.0"
---

## 1. Overview

This flow covers the end-to-end lifecycle of a job position (vacancy) in Odoo 19 — from creation to publication on the careers page, applicant tracking, employee hiring, and eventual closure. The job position acts as a recruitment target: it tracks how many employees should fill the role (`no_of_recruitment`), how many are already hired (`no_of_employee`), and how many applicants are in the pipeline (`no_of_applicant`). Cross-module integration with `website` (careers page publishing), `hr_recruitment` (applicant linking), and `website_hr_recruitment` (public-facing vacancy form) makes this a multi-module flow.

Key outcomes:
- A record in `hr_job` with department, hiring manager, and target headcount
- `no_of_employee` computed from actual `hr.employee` records with matching `job_id`
- `no_of_applicant` computed from `hr.applicant` records in active stages
- Vacancy surplus/deficit computed: `expected_employees` vs `no_of_recruitment`
- Optional website publication via `website.published.mixin` (`is_published`)
- `hr.applicant` auto-linked to job via `job_id` or `dept_id` on creation
- `hr.job.set_close()` transitions state to 'close', blocking further applicants

---

## 2. Trigger

**Primary trigger**: User navigates to **HR → Jobs → Create**.

Form fields required / optional:
- **Job Title** (`name`) — required, the position name
- **Department** (`department_id`) — optional, links to `hr.department`
- **Target Headcount** (`no_of_recruitment`) — default 1, how many to hire
- **Hiring Manager** (`user_id`) — optional, receives applicant notifications
- **Company** (`company_id`) — auto-set from context in multi-company setups
- **Expected Employees** (`expected_employees`) — computed from `no_of_employee` + `no_of_applicant`

**Secondary triggers**:
- **Website form submission**: A candidate applies via the public careers page (`website_hr_recruitment`), auto-creating `hr.applicant` with `job_id` linked.
- **Import**: Bulk import of job positions via CSV.
- **Module install**: `hr_recruitment` installs and creates default "Generic - Not Colorizable" job for onboarding.

---

## 3. Method Chain

### 3.1 Entry Point: `hr.job.create(vals)`

```
hr.job.create(vals)
│
├── vals = {
│       'name': 'Senior Python Developer',
│       'department_id': hr.department(5),
│       'no_of_recruitment': 2,
│       'user_id': res.users(42),
│       'company_id': res.company(1),
│   }
│
├── _onchange_department_id()
│   └── recomputes context for employee count, resets expected_employees
│
├── _compute_employee_count()
│   └── sets no_of_employee = count of hr.employee with job_id = self.id
│
├── _compute_application_count()
│   └── sets no_of_applicant = count of hr.applicant with job_id = self.id
│
└── INSERT hr_job → returns browse record
```

### 3.2 Onchange: Department Assignment

```
_onchange_department_id()
│
├── triggered by: department_id field change in form view
│
├── sets 'department_id' on self
│
├── recomputes:
│       self.name  (unchanged, but department context changes)
│       self.expected_employees (triggers downstream computed)
│
└── no DB write — pure onchange signal
```

### 3.3 Employee Count Computation

```
_compute_employee_count()
│
├── self.no_of_employee =
│       hr.employee.search_count([
│           ('job_id', '=', self.id),
│           ('state', 'in', ['done', 'contractual']),
│       ])
│
└── Note: Only employees in 'done' or 'contractual' state counted.
         Employees in 'trial', 'probation' also counted.
         'draft' state employees are NOT counted.
```

### 3.4 Application Count Computation

```
_compute_application_count()
│
├── self.no_of_applicant =
│       hr.applicant.search_count([
│           ('job_id', '=', self.id),
│           ('stage_id.is_default', '=', False),  # not in initial "new" stage
│           ('active', '=', True),
│       ])
│
└── triggered when:
        hr.applicant.create()
        hr.applicant.write('job_id' or 'stage_id')
        hr.applicant.unlink()
```

### 3.5 Expected Employees / Surplus Deficit

```
expected_employees = no_of_employee + no_of_applicant

job_overflow = no_of_recruitment - expected_employees

# Examples:
no_of_recruitment = 3
no_of_employee    = 1  (Python devs hired)
no_of_applicant   = 1  (applicants in pipeline)
# expected_employees = 2
# job_overflow       = 1  → 1 more hire needed
```

Displayed as a smart banner on the job kanban card:
- Red: `job_overflow < 0` → "Over-recruited: X more than planned"
- Green: `job_overflow > 0` → "Hiring: X positions open"
- Grey: `job_overflow == 0` → "Positions filled"

### 3.6 Website Publication (`website.published.mixin`)

```
hr.job inherits website.published.mixin
│
├── is_published = Boolean (default False)
│   └── controls visibility on public website
│
├── website_url = Char (computed)
│   └── returns /jobs/detail/<job_id>
│
├── action_publish()
│   └── flips is_published = True
│       └── also sets website_id on job
│
├── action_unpublish()
│   └── flips is_published = False
│
└── website_id = Many2one(website)
    └── restricts visibility to specific website in multi-site setup
```

Publication status shown on job kanban card with a globe icon.

### 3.7 Applicant Auto-Link on `hr.applicant` Creation

```
hr.applicant.create({
    'name': 'John Doe Application',
    'partner_id': res.partner(100),
    'job_id': hr.job(42),       # explicit
    # OR
    'dept_id': hr.department(5), # department-level, searches for job
})
│
├── If 'job_id' provided:
│       job_id set directly
│
└── If only 'dept_id' provided:
        hr.job.search([
            ('department_id', '=', dept_id),
            ('state', '=', 'open'),
        ], limit=1)
        │
        └── job_id = found_job or False
            (if no open job in dept, applicant is "speculative")
```

### 3.8 Employee Hired — Job Counter Updated

```
hr.employee.create({
    'name': 'Jane Smith',
    'job_id': hr.job(42),
    'department_id': hr.department(5),
    'state': 'done',   # confirmed employee
})
│
├── triggers: hr.employee._compute_job_id()
│   └── writes job_id on the employee record
│
├── hr.job(42)._compute_employee_count() recalculates
│   └── no_of_employee increments
│
└── expected_employees auto-updated
    └── kanban card status updates
```

### 3.9 Job Closure

```
hr.job.set_close()
│
├── self.write({'state': 'close'})
│   └── state field: selection [('draft','New'),('open','Open'),('close','Closed')]
│
├── no_of_recruitment frozen
│   └── still visible for reporting
│
├── hr.applicant.pipeline: applicants remain in place
│   └── but "Close Job" wizard can archive them:
│       wizard: hr.recruitment.close.wizard
│       └── action_close_job():
│               for each applicant: write({'active': False})
│
└── website.published.mixin:
        is_published → False (auto-unpublish on close)
```

---

## 4. Decision Tree

```
START: User clicks "Create" in HR → Jobs
│
├── [A] Job Title (name) provided?
│       NO  → ValidationError: "Job title is required"
│       YES ↓
│
├── [B] Department assigned (department_id)?
│       NO  → job created without department
│              (still functional, employees can be linked by job_id only)
│       YES ↓
│
├── [C] Target headcount (no_of_recruitment) set?
│       NO  → defaults to 1
│       YES ↓
│
├── [D] Hiring Manager assigned (user_id)?
│       NO  → no notification recipient set
│              (applicants enter pipeline without a point of contact)
│       YES ↓
│
├── [E] Publish on website?
│       NO  → is_published = False (default)
│              not visible on careers page
│       YES → is_published = True
│              visible at /jobs/detail/<id>
│              (requires website_hr_recruitment module) ↓
│
├── [F] Compute initial employee count
│       └── no_of_employee = count(job_id matches in hr_employee)
│
├── [G] Compute initial applicant count
│       └── no_of_applicant = count(job_id matches in hr_applicant)
│
├── [H] Calculate expected_employees and overflow
│       └── job_overflow = no_of_recruitment - (employee + applicant)
│
├── [I] Applicants apply (via website or internal)
│       │   hr.applicant.create({job_id: self.id})
│       │   → _compute_application_count() triggered
│       │   → expected_employees updated
│       │
│       └── [loop: each applicant moves through stages]
│               stage_id changes → pipeline count updates
│
├── [J] Employee hired from applicant
│       │   hr.applicant.action_recruit()
│       │   → hr.employee.create({job_id: self.id})
│       │   → no_of_employee +1
│       │
│       └── [K] Job still open?
│               no_of_employee + no_of_applicant >= no_of_recruitment?
│                   YES → still open (if user hasn't closed)
│                   NO  → continues accepting applicants
│
└── [L] Job closed
        hr.job.set_close()
        │   is_published → False
        │   state → 'close'
        │   applicants can be archived via close wizard
        END
```

---

## 5. DB State

### 5.1 `hr_job`

| Column | Type | Notes |
|---|---|---|
| id | SERIAL | Primary key |
| name | VARCHAR | Required |
| state | VARCHAR | ('draft','open','close'), default 'draft' |
| department_id | INTEGER (FK hr.department) | Nullable |
| no_of_recruitment | INTEGER | Target headcount, default 1 |
| no_of_employee | INTEGER | Computed count of hired employees |
| no_of_applicant | INTEGER | Computed count of active applicants |
| expected_employees | INTEGER | Computed: no_of_employee + no_of_applicant |
| is_published | BOOLEAN | Website.published.mixin flag |
| website_id | INTEGER (FK website) | Restrict to specific website |
| website_url | CHAR | Computed absolute_url |
| user_id | INTEGER (FK res.users) | Hiring manager |
| description | HTML | Rich text job description |
| requirements | TEXT | Job requirements |
| company_id | INTEGER (FK res.company) | Multi-company |
| create_uid / create_date | INTEGER / TIMESTAMP | Audit |
| write_uid / write_date | INTEGER / TIMESTAMP | Audit |

### 5.2 `hr_department` (referenced from hr_job)

| Column | Type | Notes |
|---|---|---|
| id | SERIAL | Primary key |
| name | VARCHAR | Department name |
| manager_id | INTEGER (FK hr.employee) | Department head |
| parent_id | INTEGER (FK hr_department) | Hierarchy |

### 5.3 `hr_applicant` (applicant pipeline)

| Column | Type | Notes |
|---|---|---|
| id | SERIAL | Primary key |
| name | VARCHAR | Applicant name |
| partner_id | INTEGER (FK res.partner) | Contact person |
| job_id | INTEGER (FK hr_job) | Target job position |
| dept_id | INTEGER (FK hr_department) | Department (if no job) |
| stage_id | INTEGER (FK hr.recruitment.stage) | Pipeline stage |
| priority | INTEGER | Star rating (0-5) |
| active | BOOLEAN | Default TRUE (archive not delete) |
| user_id | INTEGER (FK res.users) | Assigned recruiter |
| company_id | INTEGER (FK res.company) | Multi-company |

### 5.4 `hr_employee` (hired count source)

| Column | Type | Notes |
|---|---|---|
| id | SERIAL | Primary key |
| name | VARCHAR | Employee name |
| job_id | INTEGER (FK hr_job) | Position held |
| department_id | INTEGER (FK hr_department) | Department |
| state | VARCHAR | ('draft','trial','probation','done','contractual') |
| active | BOOLEAN | Default TRUE |
| user_id | INTEGER (FK res.users) | Linked user |
| company_id | INTEGER (FK res.company) | Multi-company |

### 5.5 `website_careers` / `website.page` (published job page)

| Column | Type | Notes |
|---|---|---|
| id | SERIAL | Primary key |
| name | VARCHAR | Page title = job name |
| url | VARCHAR | /jobs/detail/<job_id> |
| is_published | BOOLEAN | Mirrors job.is_published |
| job_id | INTEGER (FK hr_job) | Linked job record |

---

## 6. Error Scenarios

### 6.1 No Department Assigned

```
hr.job.create({
    'name': 'Software Architect',
    # no department_id
    'no_of_recruitment': 1,
})

Result:
    - Job created with department_id = False (nullable)
    - Kanban view shows "No Department" label
    - Applicant creation: dept_id can still be set separately
    - Job will NOT appear under any department filter in HR dashboard
    - WARNING: "Job is not assigned to a department" on form
```

**Impact**: Harder to filter/track job by department in reports. Applicant routing based on `dept_id` still works.

### 6.2 Duplicate Job Name

```
hr.job.create({'name': 'Software Architect', 'department_id': 5})
hr.job.create({'name': 'Software Architect', 'department_id': 5})

Result:
    - Both created (no unique constraint on name alone)
    - website URL slug collision may occur:
        /jobs/detail/23-Software-Architect
        /jobs/detail/24-Software-Architect
    - Odoo does NOT deduplicate — HR manager must rename
```

### 6.3 Negative Vacancy Count

```
hr.job.create({
    'name': 'QA Lead',
    'no_of_recruitment': -2,
})

Result:
    - Record created with no_of_recruitment = -2
    - job_overflow = no_of_recruitment - expected = -2 - 0 = -2
    - Form validation warning: "Negative recruitment target"
    - Kanban card: red "Over-recruited: 2 more than planned"
    - No hard block in ORM (integer field allows negative)
```

**Recommendation**: Override `create()` or `write()` to add a `check` constraint:
```
@api.constrains('no_of_recruitment')
def _check_recruitment_target(self):
    if any(job.no_of_recruitment < 0 for job in self):
        raise ValidationError("Target headcount cannot be negative.")
```

### 6.4 Over-Recruitment (Hire More Than Vacancy)

```
hr.job(42): no_of_recruitment = 2, no_of_employee = 1

# A second employee is hired:
hr.employee.create({'name': 'Dev 2', 'job_id': 42, 'state': 'done'})
│
├── hr.job(42).no_of_employee → 2
├── expected_employees → 2
├── job_overflow → 2 - 2 = 0
│
# A third employee is hired:
hr.employee.create({'name': 'Dev 3', 'job_id': 42, 'state': 'done'})
│
├── hr.job(42).no_of_employee → 3
├── expected_employees → 3
├── job_overflow → 2 - 3 = -1
│
# Red banner: "Over-recruited: 1 more than planned"
```

**No hard block**: Odoo allows over-recruitment. The red banner is a warning. HR manager can update `no_of_recruitment` to match reality or hire additional employees.

### 6.5 Closed Job Receiving Applicants

```
hr.job(42).set_close()  # state → 'close', is_published → False

# Applicant still applies (form submitted before closure):
hr.applicant.create({'name': 'Late Applicant', 'job_id': 42})
│
├── Applicant created successfully (no hard block)
├── no_of_applicant → 3 (count increases)
├── expected_employees → 4 (employee + 3 applicants)
├── No error raised, but job kanban shows:
│       "Closed — 3 applications pending"
│
# Close wizard can batch-close these applicants:
│   wizard = self.env['hr.recruitment.close.wizard'].create({
│       'applicant_ids': [(6, 0, late_applicants.ids)],
│       'close_date': fields.Date.today(),
│   })
│   wizard.action_close()
│       └── for each: write({'active': False})
```

### 6.6 Website Publication Without `website_hr_recruitment`

```
hr.job.create({
    'name': 'Backend Engineer',
    'is_published': True,   # set manually
})
│
├── Record saved with is_published = True
├── BUT no website page is auto-generated
│       (module website_hr_recruitment provides the page creation logic)
│
└── Result: flag is True but no public page exists
            Careers page template will not list this job
```

---

## 7. Side Effects

### 7.1 Website Page Auto-Creation

When `website_hr_recruitment` is installed and `is_published` is set to True via the form button:
```
website_hr_recruitment.create_job_page(job_id)
│
└── website.page.create({
        'name': job.name,
        'url': f'/jobs/detail/{job.id}-{slug(job.name)}',
        'is_published': True,
        'website_published': True,
        'job_id': job.id,
    })
```

### 7.2 Applicant Notification to Hiring Manager

When `hr.applicant.create()` is called and `user_id` (recruiter) is set:
```
hr.applicant.create({..., 'user_id': recruiter_id})
│
├── Mail activity generated for recruiter
├── inbox notification sent to recruiter's res.users partner
└── applicant count on job kanban updated
```

### 7.3 Stage Change and Hiring Pipeline

```
hr.applicant.write({'stage_id': stage_id})

If stage_id.is_hired_stage = True:
    └── action_recruit() triggered automatically
            hr.employee.create({
                'name': applicant.partner_id.name,
                'job_id': applicant.job_id.id,
                'department_id': applicant.department_id.id,
                'address_id': applicant.partner_id.address_home_id,
            })
            no_of_employee +1 on job
            no_of_applicant -1 on job
```

### 7.4 `mail.thread` Updates on Job

`hr.job` inherits `mail.thread`, enabling:
- Followers on the job record
- Chatter log for stage changes
- Automatic emails to followers when job is closed

### 7.5 Recruitment Dashboard (`hr_recruitment.report`)
The report `hr_recruitment.report_hr_recruitment_stage` aggregates:
```
hr_applicant:
    COUNT by job_id, stage_id, company_id
    SUM of days in each stage (avg duration)
```

Job closure updates this report's historical snapshot.

### 7.6 Auto-Unpublish on Closure

```
hr.job.set_close()
│
└── is_published = False
    (auto-triggered via `website.published.mixin` write override)
    │
    └── website.page: url still accessible but shows 404
            or page unpublishes if linked
```

---

## 8. Security Context

### 8.1 Record Rules

```
ir.rule: hr_job.hr_job_recruiter
    ├── model_id: hr.job
    ├── domain_force: [
            '|',
            ('user_id', '=', user.id),
            ('company_id', 'in', user.company_ids.ids),
        ]
    └── groups: base.group_user

ir.rule: hr_job.hr_job_manager
    ├── domain_force: [(1, '=', 1)]   # all records
    └── groups: hr.group_hr_manager
```

**Effect**: Recruiters see only jobs they own or jobs in their company. HR managers see all jobs.

### 8.2 Applicant Access

```
ir.rule: hr_applicant.hr_applicant_recruiter
    ├── domain_force: [
            '|',
            ('user_id', '=', user.id),
            ('company_id', 'in', user.company_ids.ids),
        ]
    └── groups: base.group_user
```

Recruiters see applicants assigned to them or in their company. Others see no applicants.

### 8.3 Field Groups

```
name, department_id, no_of_recruitment
    → base.group_user (everyone)

state, user_id (hiring manager)
    → hr.group_hr_user

is_published, website_id
    → website.group_website_publisher

description, requirements
    → hr.group_hr_user (editors)
    → base.group_user (read-only if portal enabled)
```

### 8.4 Portal Access

With `hr_recruitment_portal` installed, applicants can access their own applicant record via the portal using a unique token (`access_token` field on `hr.applicant`). They cannot see other applicants or the job's full applicant count.

### 8.5 Cross-Company Applicant Routing

When `company_id` is set on the job and applicants are created:
```
hr.applicant.create({'job_id': job.id, ...})
│
└── applicant.company_id auto-set from job.company_id
        (enforced by _compute_company_id() on create)
```

---

## 9. Transaction Boundary

### 9.1 Single Job Creation

```
BEGIN (db transaction)
│
├── INSERT hr_job
│       └── triggers _compute_employee_count (0)
│       └── triggers _compute_application_count (0)
│       └── expected_employees = 0
│
├── [IF website_hr_recruitment]
│       INSERT website_page
│
└── COMMIT on success / ROLLBACK on any error
```

### 9.2 Hiring Action (Applicant → Employee)

This is the most complex cross-record transaction:

```
BEGIN
│
├── hr.applicant.action_recruit()
│   │
│   ├── validates stage.is_hired_stage = True
│   │
│   ├── hr.employee.create({
│           'name': applicant.partner_id.name,
│           'job_id': applicant.job_id.id,
│           'department_id': applicant.job_id.department_id.id,
│           'address_home_id': applicant.partner_id.address_home_id.id,
│           'work_email': applicant.partner_id.email,
│           'phone': applicant.partner_id.phone,
│       })
│   │
│   └── hr.applicant.write({
│           'emp_id': new_employee_id,
│       })
│
├── hr.job(42)._compute_employee_count()
│       └── UPDATE hr_job.no_of_employee
│
├── hr.job(42)._compute_application_count()
│       └── UPDATE hr_job.no_of_applicant
│
└── COMMIT
```

If `hr.employee.create()` raises (e.g., required field missing), the entire transaction rolls back and the applicant remains in the pipeline.

### 9.3 Job Closure Transaction

```
BEGIN
│
├── hr.job.write({'state': 'close', 'is_published': False})
│       └── UPDATE hr_job
│
├── [OPTIONAL] close wizard:
│       ├── wizard = close_wizard.create({applicant_ids: ...})
│       ├── wizard.action_close()
│       │       └── for each applicant: write({'active': False})
│       └── hr.applicant.unlink() NOT called (archive only)
│
└── COMMIT
```

### 9.4 RPC / Controller Boundary

```
POST /web/dataset/call_kw/hr.job/create
{
    "model": "hr.job",
    "method": "create",
    "args": [[], {
        "name": "DevOps Engineer",
        "department_id": 5,
        "no_of_recruitment": 1,
    }],
    "kwargs": {}
}
```

Each `call_kw` request runs in its own database transaction. Nested calls (`hr.applicant.create` inside a controller) maintain their own transaction boundary unless called within the same `call_kw` chain.

---

## 10. Idempotency

### 10.1 Safe Repeated `create()` Calls

```
hr.job.create({'name': 'Backend Engineer', 'department_id': 5})
hr.job.create({'name': 'Backend Engineer', 'department_id': 5})

Result:
    - Two distinct records created with different IDs
    - no unique constraint on (name, department_id)
    - NOT idempotent — use search_or_create for deduplication
```

**Recommended pattern for imports**:
```
def search_or_create_job(vals):
    domain = [
        ('name', '=', vals.get('name')),
        ('department_id', '=', vals.get('department_id')),
    ]
    job = self.search(domain, limit=1)
    if job:
        return job
    return self.create(vals)
```

### 10.2 `action_publish()` / `action_unpublish()` Idempotency

```
hr.job(42).action_publish()   # is_published: False → True
hr.job(42).action_publish()   # is_published: True  → True (no-op)
│
Result: Safe to call repeatedly.
```

Both methods use `write({'is_published': True/False})` which is idempotent — writing the same value twice has no additional effect.

### 10.3 `set_close()` Idempotency

```
hr.job(42).set_close()   # state: 'open' → 'close', is_published → False
hr.job(42).set_close()   # state: 'close' → 'close' (no-op)
│
Result: Safe to call repeatedly.
        Second call: write() detects no change → no DB update.
```

### 10.4 Employee Count Increment Idempotency

```
# NOT safe — each hire increments counter:
hr.employee.create({'job_id': 42, ...})   # no_of_employee → 1
hr.employee.create({'job_id': 42, ...})   # no_of_employee → 2
hr.employee.create({'job_id': 42, ...})   # no_of_employee → 3
│
# But duplicate employee for same job is blocked by:
@api.constrains('job_id', 'active')
def _check_unique_active_job_employee(self):
    # Only one ACTIVE employee per job per employee_id
```

### 10.5 Applicant Count — Archive/Restore Cycle

```
hr.applicant(100).write({'active': False})
│
├── _compute_application_count() recalculates
│       └── no_of_applicant → decrements
│
hr.applicant(100).write({'active': True})
│
├── _compute_application_count() recalculates
│       └── no_of_applicant → increments
│
└── Idempotent per applicant — archive/restore is a toggle.
```

### 10.6 Onchange Methods

`_onchange_department_id()`, `_compute_employee_count()`, `_compute_application_count()` are all `compute=True` fields. They are **inherently idempotent** — they recalculate from the current database state and write only to the in-memory record. No side effects on repeated evaluation.

### 10.7 Website Slug Collision on Republish

```
# First publish:
hr.job(42).action_publish()
│
└── website.page(100) created with url: /jobs/detail/42-software-dev

# Job renamed:
hr.job(42).write({'name': 'Senior Software Dev'})
│
└── website.page(100).url NOT auto-updated (slug stale)

# Republish:
hr.job(42).action_publish()
│
└── A second website.page may be created if slug uniqueness
    check fails → ERROR: "Page URL already exists"
    Workaround: update name BEFORE republishing, or manually fix slug.
```
