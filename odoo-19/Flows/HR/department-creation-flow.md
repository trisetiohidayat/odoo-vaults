---
type: flow
title: "Department Creation Flow"
primary_model: hr.department
trigger: "User action — HR → Departments → Create"
cross_module: false
models_touched:
  - hr.department
  - hr.employee
  - hr.job
  - res.users
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[[Flows/HR/employee-creation-flow]]"
  - "[[Flows/HR/employee-transfer-flow]]"
source_module: hr
created: 2026-04-07
version: "1.0"
---

## 1. Overview

This flow covers the end-to-end process of creating and managing a department in Odoo 19 via the HR app. Department creation establishes an organizational unit, assigns a manager, builds the hierarchy via parent-child relationships, computes employee counts, links open job positions, and optionally creates a dedicated discussion channel. The flow enforces Odoo's recursion guard to prevent circular department hierarchies and automatically links the manager to a system user if one does not already exist.

Key outcomes:
- A record in `hr_department` with a valid name and manager reference
- A `res.users` record created for the manager if `user_id` is not already set
- Parent-child hierarchy established via `parent_id` / `child_ids`
- `employee_count` computed on the department
- Open `hr.job` positions linked via `department_id`
- `mail.channel` created for department discussions when the Discuss app is installed

---

## 2. Trigger

**User action**: Navigate to **HR → Departments → Create**.

The form requires at minimum a department **Name**. Optional fields include:
- **Manager** (`manager_id`) — an `hr.employee` record
- **Parent Department** (`parent_id`) — for hierarchy building
- **Company** (`company_id`) — for multi-company setups

A second trigger path exists via **import**: bulk-importing departments through **Settings → Import CSV** calls `hr.department.create(vals)` in batch for each row.

---

## 3. Method Chain

### 3.1 Entry Point: `hr.department.create(vals)`

```
hr.department.create(vals)
│
├── vals = {
│       'name': 'Engineering',
│       'manager_id': hr.employee(42),
│       'parent_id': hr.department(3),
│       'company_id': res.company(1),
│   }
│
├── orm/create()
│   └── calls __init__() then _compute_default_values()
│
├── _onchange_manager_id()        [if manager_id changed]
│   └── sets 'department_responsible_contact_id' (responsible user)
│
├── _onchange_parent_id()         [if parent_id changed]
│   └── cascades name_search context, reads parent path
│
├── _check_recursion()            [called by ORM on write, not create by default]
│   └── raises ValidationError on circular reference
│
└── write() completes → record created
```

### 3.2 Manager User Auto-Creation

If `manager_id` is set but the linked `hr.employee` has no `user_id`:

```
hr.employee (manager_id) — user_id = False
│
└── on first department assignment:
    res.users.create({
        'name': employee.name,
        'login': employee.work_email,
        'partner_id': employee.address_home_id.id,
        'company_ids': [company_id],
        'groups_id': [...],       # default user groups
    })
    │
    └── hr.employee.write({
            'user_id': res.users.new_id
        })
```

This is handled in `hr.models.HrEmployee._compute_user()` and triggered when the employee's `department_id` is updated to a department whose manager they become.

### 3.3 Hierarchy: `child_ids` Computed

```
hr.department
│
├── parent_id = 3  (Parent Dept)
│   └── one2many: 'child_ids'
│       └── returns all hr.department records where parent_id = self.id
│
└── parent_path computed field
    └── stores '/1/3/7/' for recursive breadcrumb display
```

### 3.4 Employee Count Computation

```
_compute_employee_count()
│
├── self.employee_count =
│       hr.employee.search_count([
│           ('department_id', '=', self.id),
│           ('active', '=', True),
│       ])
│
└── triggered by:
        hr.employee.create()
        hr.employee.write('department_id')
        hr.employee.unlink()
        hr.employee.write('active')
```

### 3.5 Job Openings Linked

```
hr.job
│
└── department_id = self.id
    └── inverse on hr.job._compute_job_count()
        returns search_count of hr.job with department_id = self.id

    Fields on hr.department:
    └── 'job_count' — computed number of active jobs in department
```

### 3.6 Discussion Channel Creation (Discuss Module)

```
if 'hr' in config['init_modules']:
    mail.channel.create({
        'name': 'Department: Engineering',
        'channel_type': 'channel',
        'group_public_id': None,
        'hr_department_id': hr.department.id,
    })
```

Triggered by `hr_department` creation signal in the `mail` module observer. The channel is visible to department members.

---

## 4. Decision Tree

```
START: User clicks "Create" in HR → Departments
│
├── [A] Name provided?
│       NO  → ValidationError: "Name is required"
│       YES ↓
│
├── [B] Manager assigned (manager_id)?
│       NO  → department created WITHOUT manager
│              (count computed, jobs linked, hierarchy built — done)
│       YES ↓
│
├── [C] Manager has user_id (user linked)?
│       NO  → res.users.create() for manager
│              hr.employee.write(user_id=user_id) — link created
│       YES ↓
│
├── [D] Parent Department set (parent_id)?
│       NO  → top-level department (root node)
│              child_ids computed for sub-departments
│       YES ↓
│
├── [E] Circular hierarchy check: _check_recursion()
│       ├── parent_id == self.id
│       │       → ValidationError: "Department cannot be its own parent"
│       ├── parent_id in (child_ids of self)
│       │       → ValidationError: "Circular hierarchy detected"
│       └── passed ↓
│
├── [F] Parent department active?
│       NO  → Warning displayed: "Parent department is archived"
│             (still allows creation; active flag on self can be set)
│       YES ↓
│
├── [G] Compute employee_count
│       └── counts active employees with department_id = self.id
│
├── [H] Link job openings
│       └── job_count = count of hr.job with department_id = self.id
│
├── [I] mail.channel created for department discussions?
│       NO  → done (Discuss not installed)
│       YES → channel created with hr_department_id linked
│
└── END: Department saved, ORM returns browse record
```

---

## 5. DB State

### 5.1 `hr_department`

| Column | Type | Notes |
|---|---|---|
| id | SERIAL | Primary key |
| name | VARCHAR | Required |
| active | BOOLEAN | Default TRUE |
| manager_id | INTEGER (FK hr.employee) | Nullable |
| parent_id | INTEGER (FK hr_department) | Nullable (root if null) |
| parent_path | VARCHAR | Computed '/id1/id2/id3/' |
| company_id | INTEGER (FK res.company) | From env.company |
| color | INTEGER | Kanban view color index |
| note | TEXT | Department description |
| department_responsible_contact_id | INTEGER (FK res.partner) | Onchange manager |
| create_uid / create_date | INTEGER / TIMESTAMP | Audit |
| write_uid / write_date | INTEGER / TIMESTAMP | Audit |

### 5.2 `hr_employee` (employee_count source)

| Column | Type | Notes |
|---|---|---|
| id | SERIAL | Primary key |
| name | VARCHAR | Employee name |
| department_id | INTEGER (FK hr_department) | Nullable |
| manager | BOOLEAN | True if is a manager |
| active | BOOLEAN | Default TRUE |
| user_id | INTEGER (FK res.users) | Nullable |
| job_id | INTEGER (FK hr.job) | Current position |

### 5.3 `res_users` (manager user, if auto-created)

| Column | Type | Notes |
|---|---|---|
| id | SERIAL | Primary key |
| name | VARCHAR | From employee.name |
| login | VARCHAR | From employee.work_email |
| partner_id | INTEGER (FK res.partner) | From work address |
| company_id | INTEGER (FK res.company) | Current company |
| groups_id | O2M | Default user groups |
| create_date | TIMESTAMP | Audit |

### 5.4 `hr_job` (job openings linked to department)

| Column | Type | Notes |
|---|---|---|
| id | SERIAL | Primary key |
| name | VARCHAR | Job title |
| department_id | INTEGER (FK hr_department) | Links to department |
| no_of_recruitment | INTEGER | Target headcount |
| no_of_employee | INTEGER | Computed: actual hired |
| state | VARCHAR | ('open', 'close') |
| is_published | BOOLEAN | Careers page visibility |
| user_id | INTEGER (FK res.users) | Hiring manager |

---

## 6. Error Scenarios

### 6.1 Circular Hierarchy (`_check_recursion`)

```
Attempted write:
    hr.department.write({
        'parent_id': self.id          # self = 7
    })
    # or parent_id = 10 where 10 is a child of 7

Error raised:
    ValidationError(
        'Error! You cannot create recursive hierarchy.\n'
        'A department cannot be its own parent or ancestor.'
    )
```

**Prevention**: `_check_recursion()` reads `parent_path` string field which stores `/ancestor_ids/self_id/`. Before write, it traverses up to detect cycles. Called by `write()` ORM hook.

### 6.2 No Manager Assigned

```
hr.department.create({'name': 'Security'})  # no manager_id

Result:
    - Department created
    - manager_id = False (nullable)
    - No res.users created
    - WARNING displayed in form:
        "This department has no manager."
```

**Impact**: Employee count still computed. Children can still be assigned. Manager-based access rules will not restrict visibility.

### 6.3 Duplicate Name

```
hr.department.create({'name': 'Engineering'})
hr.department.create({'name': 'Engineering'})

Result:
    - Both created (no UNIQUE constraint on name alone)
    - Kanban view may show both under same label
    - Odoo's UI shows a "Duplicate Name" warning on save:
        "A department with this name may already exist."
```

### 6.4 Inactive Parent Department

```
parent = hr.department.create({'name': 'Old Org', 'active': False})
child  = hr.department.create({'name': 'Team A', 'parent_id': parent.id})

Result:
    - Child created successfully
    - Warning notification on form:
        "Parent department 'Old Org' is not active."
    - parent_path stored: '/old_org_id/child_id/'
    - All child employees still visible under inactive parent tree
```

### 6.5 Cross-Company Department Assignment

```
hr.department.create({
    'name': 'Finance EU',
    'company_id': res.company(2),
    'parent_id': hr.department(1).id  # belongs to company(1)
})

Result:
    ValidationError:
        "You cannot assign a department to a parent in a different company."
```

Enforced by `hr.models.HrDepartment._check_company_id()` using SQL constraint.

---

## 7. Side Effects

### 7.1 `mail.channel` Creation
When `mail` module is active, a discussion channel is auto-created with `hr_department_id` set. This enables:
- Department announcements
- Member auto-sync on employee join/leave
- Channel visible in Discuss app under "Channels"

### 7.2 Manager's `is_manager` Flag
When an employee is assigned as `manager_id` on a department:
```
hr.employee.write([manager_id], {'manager': True})
```
This grants them visibility into the department's employees and leaves.

### 7.3 `parent_path` Update
Changing `parent_id` on a department with existing children updates the `parent_path` of all descendants via:
```
for child in self.mapped('child_ids'):
    child.write({'parent_path': new_parent_path})
```
This is done through the ORM's `write()` override.

### 7.4 Employee Count Cascade
When an employee's `department_id` changes:
```
old_department._compute_employee_count()  # -1
new_department._compute_employee_count()  # +1
```
Both counts are recomputed, triggering an `exchange` message on the employee's `message_follower_ids`.

### 7.5 Department Dashboard Updates
The HR dashboard view (`hr.department.kanban`) reads `employee_count` and `job_count` in a single query. Changes trigger a re-render of all open Kanban cards.

---

## 8. Security Context

### 8.1 Record Rules

```
ir.rule: hr_department.rule_department_user
    ├── active: True
    ├── model_id: hr.department
    ├── domain_force: [
            '|',
            ('company_id', 'in', user.company_ids.ids),
            ('company_id', '=', False),
        ]
    └── groups: hr.group_hr_manager, hr.group_hr_user

ir.rule: hr_department.rule_department_manager
    ├── domain_force: [
            ('id', 'in',
                user.employee_ids.department_id.child_ids.ids +
                user.employee_ids.department_id.ids
            )
        ]
    └── groups: base.group_user
```

**Effect**: Regular users see only departments in their company or departments where they are a member. HR officers see all departments in their company. HR managers see all.

### 8.2 Field Groups (`groups` attribute)

```
name          → base.group_user        (everyone)
manager_id    → hr.group_hr_user       (HR officers+)
parent_id     → hr.group_hr_user
company_id    → base.group_multi_company
department_responsible_contact_id → hr.group_hr_user
```

### 8.3 Manager Access Implications
When an employee is set as manager:
- The manager can approve leave requests for department employees
- The manager receives notifications for employee documents
- `is_manager` flag influences `ir.rule` on `hr.employee`

---

## 9. Transaction Boundary

### 9.1 ORM Transaction

```
BEGIN (db transaction)
│
├── hr.department.create(vals)
│       │
│       ├── INSERT hr_department
│       ├── SELECT parent_path (for recursion check)
│       ├── INSERT mail_channel (if mail installed)
│       └── SELECT hr_employee to compute count
│
├── res.users.create(vals)   [if manager has no user]
│       └── INSERT res_users + res_partner (cascade)
│
├── [OPTIONAL] hr.employee.write({manager: True})
│       └── UPDATE hr_employee
│
└── COMMIT on success / ROLLBACK on error
```

### 9.2 Multi-Database Consideration

In multi-company environments, `company_id` is set from `self.env.company` before `create()` is called. The `company_id` field is `required=True` on `hr_department` and defaults from the current company context. Foreign key constraints ensure parent_id belongs to the same company.

### 9.3 RPC / Controller Boundary

When called via XML-RPC or JSON-RPC:
```
POST /web/dataset/call_kw/hr.department/create
{
    "model": "hr.department",
    "method": "create",
    "args": [[], {'name': 'QA', 'manager_id': 42}],
    "kwargs": {}
}
```
The ORM wraps this in a transaction automatically. If `mail.channel` creation fails mid-way, the entire operation rolls back.

---

## 10. Idempotency

### 10.1 Safe Repeated Calls

```
hr.department.create({'name': 'Engineering'})
hr.department.create({'name': 'Engineering'})

Result:
    - Two distinct records created with different IDs
    - name field has no unique constraint
    - NOT idempotent at the record level (two records)
```

**Idempotency concern**: Calling `create()` with identical `vals` will create multiple records. Use `search_or_create()` pattern for deduplication:
```
self.env['hr.department'].search_or_create({
    'name': 'Engineering',
    'manager_id': manager_id,
})
```
This searches first, then creates only if no match is found.

### 10.2 `search_or_create` Logic

```
def search_or_create(vals):
    domain = [
        ('name', '=', vals.get('name')),
        ('company_id', '=', vals.get('company_id', self.env.company.id)),
    ]
    rec = self.search(domain)
    if rec:
        return rec
    return self.create(vals)
```

### 10.3 Manager Auto-Creation Idempotency

```
# Safe: called multiple times
hr.employee(42).write({'user_id': res.users(10).id})
hr.employee(42).write({'user_id': res.users(10).id})

Result:
    - Second write is a no-op (same value)
    - No duplicate user created
    - ROLLBACK-safe
```

### 10.4 Onchange Idempotency

`_onchange_manager_id()` and `_onchange_parent_id()` are **computed fields** triggered by form onchange events. They do not persist to the database and are therefore inherently idempotent — they recompute from the current form state without side effects.

### 10.5 Re-parenting Idempotency

```
hr.department.write({'parent_id': 3})
hr.department.write({'parent_id': 3})  # same value

Result:
    - Second write: ORM detects no change → returns True, no DB write
    - employee_count unchanged
    - No new mail.channel created
    - Safe to retry
```
