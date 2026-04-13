---
type: flow
title: "Project Creation Flow"
primary_model: project.project
trigger: "User action — Project → Create → Save"
cross_module: true
models_touched:
  - project.project
  - project.project.stage
  - project.task.type
  - project.tags
  - account.analytic.account
  - mail.alias
  - mail.followers
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[Flows/Project/task-lifecycle-flow](task-lifecycle-flow.md)"
  - "[Flows/HR/employee-creation-flow](employee-creation-flow.md)"
related_guides:
  - "[Business/Project/project-management-guide](project-management-guide.md)"
source_module: project
source_path: ~/odoo/odoo19/odoo/addons/project/
created: 2026-04-07
version: "1.0"
---

# Project Creation Flow

## Overview

Complete end-to-end method chain when a new project is created through the Project app UI (Project → Create). Covers all cross-module triggers: stage assignment, mail alias setup for incoming email-to-task conversion, analytic account linkage, privacy visibility defaults, and follower/collaborator registration. The flow runs as the current logged-in user with ACL checks at each write operation.

## Trigger Point

**User:** Opens **Project → Create**, fills the form, clicks **Save**.

**Method:** `project.project.create(vals)`

**Context:** Runs as the current logged-in user. The user must belong to `project.group_project_user` (or higher) to create projects. Record rules and multi-company ACL are enforced.

---

## Complete Method Chain

```
1. project.project.create(vals)
   │
   ├─► 2. mail_create_nosubscribe context applied
   │      └─► suppresses auto-subscribe on mail.thread create
   │
   ├─► 3. label_tasks normalization
   │      IF vals.get('label_tasks') is falsy:
   │      └─► label_tasks = _("Tasks")  [translated default]
   │
   ├─► 4. Stage assignment — group_project_stages enabled?
   │      │
   │      ├─► YES: user has project.group_project_stages
   │      │      │
   │      │      ├─► 4a. IF 'default_stage_id' in context:
   │      │      │      └─► stage = stage from context
   │      │      │            └─► IF stage.company_id:
   │      │      │                  └─► company_id = stage.company_id
   │      │      │
   │      │      └─► 4b. ELSE: stage search by company + sequence
   │      │             └─► stage = project.project.stage
   │      │                   filtered by matching company_id
   │      │                   ordered by sequence ASC
   │      │                   [:1]  (lowest sequence)
   │      │             └─► vals['stage_id'] = stage.id
   │      │
   │      └─► NO: stage_id not set (nullable — defaults to False)
   │
   ├─► 5. is_favorite handling
   │      IF vals.pop('is_favorite', False) == True:
   │      └─► vals['favorite_user_ids'] = [Command.link(uid)]
   │            └─► project.project.write({'favorite_user_ids': [...]})
   │                  └─► _set_favorite_user_ids()
   │
   ├─► 6. super().create(vals)  [BaseModel.create → SQL INSERT]
   │      └─► INSERT INTO project_project (...)
   │            └─► 7. ORM field triggers (computed fields)
   │                  ├─► _compute_company_id()
   │                  ├─► _compute_currency_id()
   │                  ├─► _compute_resource_calendar_id()
   │                  ├─► _compute_task_count() / _compute_open_task_count()
   │                  ├─► _compute_collaborator_count()
   │                  ├─► _compute_milestone_count()
   │                  ├─► _compute_last_update_status()
   │                  └─► _compute_privacy_visibility_warning()
   │
   ├─► 8. RETURN project record (new ID)
   │
   ├─► 9. OUTSIDE transaction: mail.alias record auto-created
   │      [triggered by mail.alias.mixin inheritance]
   │      └─► _alias_get_creation_values() called
   │            ├─► alias_model_id = ir.model('project.task')
   │            ├─► alias_defaults = {"project_id": project.id}
   │            └─► alias_name auto-generated from project name
   │
   └─► 10. mail.followers auto-registration
          [triggered by mail.thread on project.project.create]
          ├─► project.user_id (manager) subscribed
          └─► project.partner_id subscribed (if set)
```

---

## Decision Tree

```
User clicks Save on project.project form
│
├─► name set?
│   └─► NO → ValidationError: "name is required"
│
├─► partner_id assigned?
│   ├─► YES → partner email pre-filled in alias_defaults
│   └─► NO → partner_id left empty
│
├─► privacy_visibility set in vals?
│   ├─► YES → use provided value
│   └─► NO → default = 'portal'
│        └─► privacy_visibility_warning computed
│
├─► user_id (project manager) assigned?
│   ├─► YES → manager subscribed as follower
│   └─► NO → default = env.user (current user)
│
├─► allow_milestones toggled?
│   ├─► YES (True) → _inverse_allow_milestones()
│   │             └─► _check_project_group_with_field(
│   │                   'allow_milestones',
│   │                   'project.group_project_milestone'
│   │                 )
│   └─► NO (False) → no-op
│
├─► company_id set?
│   ├─► YES → currency_id computed from company
│   └─► NO → currency_id from default company
│
└─► ALWAYS:
    ├─► Mail alias created (via mail.alias.mixin)
    ├─► Record rules applied
    └─► stage_id assigned (lowest-sequence stage or context default)
```

---

## Database State After Completion

| Table | Record Created/Updated | Key Fields |
|-------|----------------------|------------|
| `project_project` | **Created** | name, active=True, privacy_visibility, stage_id, user_id, partner_id, sequence=10, date_start, date |
| `project_project_stage` | **Referenced** | stage_id FK set on project_project |
| `mail_alias` | **Created** (via mixin) | alias_model_id=project.task, alias_defaults={project_id: id}, alias_name from project name |
| `mail_followers` | **Created** | res_model='project.project', partner_id=user_id.partner_id subscribed |
| `res_partner` | **Referenced** | partner_id FK on project_project |
| `project_tags` | **Referenced** | tag_ids Many2many link |
| `account_analytic_account` | **Referenced (optional)** | account_id FK if manually set in vals |
| `ir.model.data` | **Created (optional)** | alias_id xmlid if name_create pattern used |
| `project_task_type` | **Created (via name_create)** | If created via name_create() — "New" stage auto-created |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Reason |
|----------|-------------|---------------------|
| `name` not provided | `ValidationError` (ORM) | Field `name` has `required=True` |
| `partner_id` on internal-only project | Silent warning | `privacy_visibility_warning` computed; partner still accepted |
| Invalid `privacy_visibility` value | `ValidationError` | Selection field validates against allowed values |
| `date` (end) < `date_start` | `ValidationError` | `_project_date_greater` SQL constraint: `check(date >= date_start)` |
| Stage company mismatch | `UserError` | `_ensure_stage_has_same_company` constrains stage_id.company_id == project.company_id |
| User lacks `project.group_project_user` | `AccessError` | Record rule on project_project |
| Duplicate analytic account name (with plan uniqueness) | Depends on `account.analytic.account` constraint | Check at analytic account level |
| `company_id` change with existing tasks | Silent cascade | Project tasks' company_id not auto-updated |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Mail alias auto-created | `mail.alias` | Incoming emails to alias address auto-create tasks in this project |
| Project manager subscribed | `mail.followers` | Manager (user_id.partner_id) added as follower — receives all notifications |
| Task count recomputed | `project.project.task_count` | Counts tasks with `is_template=False` on this project |
| Favorite membership updated | `project_favorite_user_rel` | Current user added to favorite_user_ids if `is_favorite=True` |
| Company propagation | `res.company` | `company_id` written; `currency_id` computed from it |
| Milestone feature group toggled | `res.groups` | `_check_project_group_with_field` may add `group_project_milestone` to base users |
| Project tasks visibility changed | `mail.followers` | If privacy_visibility = 'employees', portal followers unsubscribed |

---

## Security Context

> *Which user context the flow runs under, and what access rights are required at each step.*

| Step | Security Mode | Access Required | Notes |
|------|-------------|----------------|-------|
| `project.project.create()` | Current user | `project.group_project_user` | Respects record rules |
| `stage_id` assignment | Current user / sudo (if stage has company) | Read on `project.project.stage` | Uses lowest-sequence stage |
| `super().create()` (SQL INSERT) | `sudo()` not used | `create` ACL on `project_project` | Portal users cannot create |
| `_compute_company_id()` | Current user | Read on `res.company` | Context-dependent |
| `mail.alias` creation | `sudo()` via mixin | System | Mixin creates alias without user ACL |
| `favorite_user_ids` write | `sudo()` via `_set_favorite_user_ids()` | `write` on `project_project` | Bypassed for non-admin users |
| `stage_id.company_id` constraint check | Current user | Read on stage | Raises `UserError` if company mismatch |
| `account_id` write (if manual) | Current user | `account.analytic.account` write ACL | Requires analytic module access |

**Key principle:** Most steps run as the **current logged-in user**. Only the mail alias creation (a system-level mixin operation) uses an elevated context. The `_set_favorite_user_ids()` method uses `sudo()` deliberately to allow non-admin users to mark projects as favorites.

---

## Transaction Boundary

```
Steps 1–6  ✅  INSIDE transaction  — atomic (all or nothing)
Step 7     ✅  INSIDE transaction  — ORM field recomputation within same write
Step 8     ✅  INSIDE transaction  — project record returned
Step 9     ❌  OUTSIDE transaction — mail.alias created via mixin after_commit hook
Step 10    ❌  INSIDE transaction — mail.followers written as part of super().create()
```

| Step | Boundary | Behavior on Failure |
|------|----------|---------------------|
| Steps 1–8 (project.create) | ✅ Atomic | Rollback on any error — no orphan records |
| Mail alias creation | ❌ After commit | If alias creation fails, alias missing; project still exists |
| Mail followers | ✅ Within super().create() | Rolled back with project |
| `_check_project_group_with_field` | ✅ Within write() | Raises UserError before commit |
| Constraint `_project_date_greater` | ✅ DB-level | Raises on INSERT if date_end < date_start |

**Rule of thumb:** The `project.project` record and its `mail.followers` entries are written atomically in the same transaction. The `mail.alias` record is created by the `mail.alias.mixin` after the transaction commits.

---

## Idempotency

| Scenario | Behavior |
|----------|----------|
| Double-click Save button | ORM deduplicates via browser — only one `project.project.create()` call |
| Re-save with same values | `write()` re-runs with no semantic change — no duplicate records |
| Create project with identical name | Allowed — no unique constraint on `name` field |
| Duplicate `partner_id` on same company | Allowed — `partner_id` is not unique-constrained |
| Network timeout + retry | If browser retries POST, new record created each time; no idempotency key |

**Common patterns:**
- **Idempotent:** `create()` on same vals without unique constraints creates new records each time (expected behavior)
- **Idempotent:** `write()` re-running with same values is a no-op
- **Non-idempotent:** Mail alias name generated each time (uses project name — collision handled by database unique constraint on `mail.alias` `alias_name` + `alias_domain_id`)

---

## Extension Points

| Step | Hook Method | Purpose | Arguments | Override Pattern |
|------|-------------|---------|-----------|-----------------|
| Pre-stage assignment | `_default_stage_id()` | Custom default stage logic | self | Override to return different stage |
| Pre-create validation | Override `create()` | Add pre-creation checks | vals_list | Call `super().create()` then post-process |
| Post-create side effect | Override `create()` after `super()` | e.g., create milestones, assign default tasks | vals_list | Extend create() override |
| Favorite handling | `_set_favorite_user_ids()` | Custom favorite behavior | is_favorite bool | Extend method with `super()` |
| Alias customization | `_alias_get_creation_values()` | Custom alias name pattern | self | Override to change alias_defaults or alias_model_id |
| Company assignment | `_onchange_company_id()` | Update stage when company changes | self | Extend with `super()` |

**Standard override pattern:**
```python
# project_project.py
@api.model_create_multi
def create(self, vals_list):
    # Pre-processing
    for vals in vals_list:
        if not vals.get('my_custom_field'):
            vals['my_custom_field'] = self.env['my.model'].default_value()
    # Call super
    projects = super().create(vals_list)
    # Post-processing
    for project in projects:
        if not project.account_id:
            project._my_custom_side_effect()
    return projects
```

---

## Reverse / Undo Flow

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| `project.project.create()` | `unlink()` | `project.unlink()` | Cascades to tasks, updates, milestones, mail_alias |
| `stage_id` assignment | Edit project → Change stage | `project.write({'stage_id': new_id})` | Stage history not tracked |
| Favorite marking | Unmark favorite | `_set_favorite_user_ids(False)` | Removes user from `favorite_user_ids` |
| Mail alias creation | Not directly reversible | Delete alias manually | Tasks already created via alias remain |
| `account_id` assignment | Clear analytic account | `write({'account_id': False})` | Only if no `account.move.line` entries exist |

**Important:** `unlink()` cascades to `project.task` (all tasks deleted), `project.update`, `project.milestone` (cascade delete), and `mail_followers`. The `mail.alias` record is also deleted via cascade. Analytic account is deleted only if it has no `line_ids`.

---

## Alternative Triggers

| Trigger Type | Method / Endpoint | Context | Frequency |
|-------------|------------------|---------|-----------|
| User action | `project.project.create()` | Interactive | Manual |
| Quick create (name only) | `name_create(name)` | Via search input | Manual |
| Project duplication | `action_copy()` | Via More button | Manual |
| Project template → Project | `action_create_project()` | Via template context | Manual |
| Import (CSV/XLS) | `import` action | Via Data menu | Batch |
| Onchange cascade | Form onchange methods | Field change | On demand |
| Automated action | `base.automation` | Rule triggered | On rule match |

---

## Related

- [Modules/Project](Project.md) — Module reference
- [Flows/Project/task-lifecycle-flow](task-lifecycle-flow.md) — Task lifecycle flow
- [Business/Project/project-management-guide](project-management-guide.md) — Business guide
- [Patterns/Workflow Patterns](Workflow Patterns.md) — Workflow pattern reference
- [Core/API](API.md) — @api decorator patterns
