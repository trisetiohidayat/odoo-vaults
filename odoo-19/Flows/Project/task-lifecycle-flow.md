---
type: flow
title: "Task Lifecycle Flow"
primary_model: project.task
trigger: "User action — Task → Create / Stage Change / Close"
cross_module: true
models_touched:
  - project.task
  - project.project
  - project.task.type
  - project.milestone
  - mail.message
  - mail.followers
  - rating.rating
  - project.task.recurrence
audience: ai-reasoning, developer
level: 1
related_flows:
  - "[Flows/Project/project-creation-flow](odoo-19/Flows/Project/project-creation-flow.md)"
  - "[Flows/Project/project-creation-flow](odoo-19/Flows/Project/project-creation-flow.md)"
related_guides:
  - "[Business/Project/project-management-guide](odoo-19/Business/Project/project-management-guide.md)"
source_module: project
source_path: ~/odoo/odoo19/odoo/addons/project/
created: 2026-04-07
version: "1.0"
---

# Task Lifecycle Flow

## Overview

Complete end-to-end method chain from task creation through stage progression to closure. Covers all cross-module triggers: project assignment with stage auto-selection, assignee subscription, parent-child subtask hierarchy via recursive SQL, stage-change rating email dispatch, and portal access URL generation. The flow runs as the current logged-in user with full ACL checks; portal users have restricted write access via `_ensure_fields_write()`.

## Trigger Point

**User:** Opens **Project → Tasks → Create**, fills the form, clicks **Save**.

**Method:** `project.task.create(vals)` (via `project.task` form)

**Alternative triggers:** Email-to-task via mail gateway, subtask creation via parent task action, recurrence generation via `project.task.recurrence`.

**Context:** Runs as the current logged-in user. Portal users can create tasks in shared projects (via Project Sharing) using the `default_create_in_project_id` context.

---

## Complete Method Chain

### Phase A — Task Creation

```
1. project.task.create(vals_list)
   │
   ├─► 2. Context preprocessing
   │      ├─► default_personal_stage = context.pop('default_personal_stage_type_ids')
   │      ├─► default_project_id = context.pop('default_project_id')
   │      └─► IF no project_id in vals:
   │             └─► parent_id from vals → parent_task.sudo().project_id
   │                   └─► default_project_id = parent_task.project_id.id
   │
   ├─► 3. Access check
   │      └─► check_access('create')
   │
   ├─► 4. Per-vals preprocessing (loop over vals_list)
   │      │
   │      ├─► 4a. user_ids set?
   │      │      ├─► date_assign = fields.Datetime.now()
   │      │      └─► IF current user not in user_ids:
   │      │             └─► user_ids = [Command.set(list(cache) + [env.user.id])]
   │      │
   │      ├─► 4b. default_personal_stage set + no personal_stage_type_id:
   │      │      └─► additional_vals['personal_stage_type_id'] = default_personal_stage[0]
   │      │
   │      ├─► 4c. name empty + display_name set:
   │      │      └─► vals['name'] = vals['display_name']
   │      │
   │      ├─► 4d. portal user + not su:
   │      │      └─► _ensure_fields_write(vals, defaults=True)
   │      │             └─► restrict to PROJECT_TASK_WRITABLE_FIELDS
   │      │
   │      ├─► 4e. project_id set + no company_id:
   │      │      └─► company_id = project.project.company_id
   │      │
   │      ├─► 4f. no project_id + stage_id in vals:
   │      │      └─► vals['stage_id'] = False  (private task has no stage)
   │      │
   │      ├─► 4g. project_id set + no stage_id:
   │      │      └─► stage_id = default_get(['stage_id'])
   │      │            └─► calls _get_default_stage_id()
   │      │                  └─► stage_find(project_id, order="fold, sequence, id")
   │      │
   │      ├─► 4h. stage_id set:
   │      │      └─► additional_vals['date_end'] = update_date_end(stage_id)
   │      │            └─► IF stage_id.fold == True → date_end = now()
   │      │                ELSE → date_end = False
   │      │      └─► additional_vals['date_last_stage_update'] = now()
   │      │
   │      └─► 4i. recurring_task == True:
   │             └─► project.task.recurrence.create(recurrence_fields)
   │                   └─► vals['recurrence_id'] = new_recurrence.id
   │
   ├─► 5. super().create(vals_list)  [mail_create_nosubscribe + mail_notrack]
   │      └─► INSERT INTO project_task (...)
   │            └─► ORM field triggers
   │                  ├─► _compute_state() — depends on depend_on_ids, stage_id
   │                  ├─► _compute_is_closed()
   │                  ├─► _compute_partner_id()
   │                  ├─► _compute_milestone_id()
   │                  └─► _compute_subtask_count()
   │
   ├─► 6. sudo().write(computed_vals) for inaccessible fields
   │
   ├─► 7. _populate_missing_personal_stages()
   │      └─► IF personal_stage_id missing:
   │            ├─► search project.task.stage.personal
   │            └─► ELSE: create default personal stages for user
   │                  └─► project.task.type.create([
   │                        {name: 'Inbox', sequence: 1, user_id: uid},
   │                        {name: 'Today', sequence: 2, user_id: uid},
   │                        ...
   │                        {name: 'Done', sequence: 6, user_id: uid},
   │                      ])
   │
   ├─► 8. _task_message_auto_subscribe_notify({task: new_assignees})
   │      └─► For each task: notify new user_ids (excluding current user)
   │            └─► mail.notification sent to assignees
   │
   ├─► 9. Email-CC processing
   │      └─► res.partner.search([('email', 'in', all_cc_emails)])
   │            └─► partners filtered: internal users only
   │                  └─► _send_email_notify_to_cc(partners)
   │                  └─► message_subscribe(internal_partner_ids)
   │
   ├─► 10. Project-level effects
   │       ├─► IF project_id: _set_stage_on_project_from_task()
   │       └─► IF privacy_visibility in ['invited_users', 'portal']:
   │              └─► _portal_ensure_token()
   │
   └─► 11. Parent task follower cascade
           └─► For each task:
                 For each parent_id.message_follower_ids:
                   └─► task.message_subscribe(follower.partner_id.ids, follower.subtype_ids.ids)
           └─► Current user's partner auto-subscribed
```

### Phase B — Stage Change (via write)

```
12. project.task.write({'stage_id': new_stage_id})
    │
    ├─► 13. check_access('write')
    │
    ├─► 14. update_date_end(new_stage_id)
    │      └─► IF fold=True → date_end = now()
    │          ELSE → date_end = False
    │
    ├─► 15. additional_vals['date_last_stage_update'] = now()
    │
    ├─► 16. Milestone processing [milestone_id in vals]
    │       ├─► milestone = project.milestone.browse(vals['milestone_id'])
    │       ├─► invalid_milestone_tasks → reset milestone_id = False
    │       └─► valid_milestone_tasks → update milestone_id
    │
    ├─► 17. super().write(vals) [ORM write → SQL UPDATE]
    │       └─► state inverse triggered: _inverse_state()
    │
    ├─► 18. _populate_missing_personal_stages() for user_ids change
    │
    ├─► 19. date_assign update
    │       └─► IF user_ids removed: date_assign = False
    │           IF user_ids added: date_assign = now()
    │
    ├─► 20. Rating email — IF stage.rating_active + rating_status='stage':
    │       └─► _send_task_rating_mail(force_send=True)
    │             ├─► rating_template = task.stage_id.rating_template_id
    │             ├─► partner = task.partner_id
    │             └─► IF partner and not current user:
    │                   └─► rating_send_request(template, lang=partner.lang)
    │                         └─► mail.mail created + queued
    │                         └─► rating.rating record created (tokenized)
    │
    ├─► 21. State → closed check
    │       └─► IF state in CLOSED_STATES ('1_done', '1_canceled'):
    │             └─► subtasks recursively: check all child_ids.is_closed
    │
    ├─► 22. Task dependency state fix
    │       └─► IF state changed to non-closed + is_blocked_by_dependences():
    │             └─► state = '04_waiting_normal'
    │
    └─► 23. _task_message_auto_subscribe_notify(new_assignees)
```

---

## Decision Tree

```
User saves task form
│
├─► project_id set?
│   ├─► YES → company_id auto-filled from project
│   │        stage_id auto-selected (fold→done stage, else first by sequence)
│   │        privacy_visibility from project
│   └─► NO → private task (no project)
│
├─► user_ids (assignees) set?
│   ├─► YES → date_assign = now()
│   │        message_subscribe(assignee partners)
│   │        _populate_missing_personal_stages()
│   └─► NO → task left unassigned
│
├─► parent_id (subtask) set?
│   ├─► YES → project_id inherited from parent
│   │        partner_id inherited from parent.project_id
│   │        parent task's followers auto-subscribed
│   └─► NO → standalone task
│
├─► recurring_task == True?
│   ├─► YES → project.task.recurrence.create(recurrence vals)
│   └─► NO → normal task
│
Stage progression:
│
├─► stage_id changed?
│   ├─► YES → date_last_stage_update = now()
│   │        date_end set if fold=True
│   │        IF stage.rating_active + rating_status='stage':
│   │              └─► _send_task_rating_mail()
│   └─► NO → no stage-related effects
│
├─► state → '1_done' (done)?
│   ├─► YES → subtasks checked recursively
│   │        rating request dispatched
│   │        IF blocked by dependencies:
│   │              └─► state = '04_waiting_normal' (auto-fixed)
│   └─► NO → continue normal state
│
├─► state → '1_canceled' (cancelled)?
│   └─► YES → subtasks remain but parent is closed
│
└─► portal user creating?
    ├─► YES → restricted to PROJECT_TASK_WRITABLE_FIELDS
    └─► NO → full field access
```

---

## Database State After Completion

| Table | Record Created/Updated | Key Fields |
|-------|----------------------|------------|
| `project_task` | **Created** | name, project_id, stage_id, state='01_in_progress', user_ids, partner_id, parent_id, priority='0', sequence=10, date_assign, date_last_stage_update |
| `project_task_type` | **Referenced** | stage_id FK |
| `project_project` | **Updated (computed)** | task_count, open_task_count recomputed |
| `project_task_stage_personal` | **Created** (per user) | user_id, task_id, stage_id — for personal kanban view |
| `mail_followers` | **Created/Updated** | res_model='project.task', partner_id for each user_ids member, parent task's followers cascaded |
| `mail_message` | **Created** | subtype='mt_project_task_new' — task creation notification |
| `mail_mail` | **Queued** | rating request email (if rating enabled, async via queue) |
| `rating_rating` | **Created** | res_model='project.task', res_id=task.id, partner_id=task.partner_id, token generated |
| `project_task_recurrence` | **Created (optional)** | repeat_interval, repeat_unit, repeat_type, repeat_until |
| `project_milestone` | **Referenced (optional)** | milestone_id FK if set |
| `project_task` (parent) | **Updated** (optional) | subtask_count, subtask_completion_percentage recomputed |

---

## Error Scenarios

| Scenario | Error Raised | Constraint / Reason |
|----------|-------------|---------------------|
| `name` not provided | `ValidationError` | Field `name` has `required=True` + `index='trigram'` |
| Circular subtask reference | `UserError` | `_check_parent_id()` domain: `[('id', 'child_of', id)]` prevents self-reference |
| `parent_id` set on recurring task | `ValidationError` | `_recurring_task_has_no_parent` constraint |
| `parent_id` set on private task (no project) | `ValidationError` | `_private_task_has_no_parent` constraint |
| Task without project + stage_id set | `UserError` | `if not project_id in vals and stage_id in vals: vals["stage_id"] = False` enforced pre-write; or in write: "You can only set a personal stage on a private task" |
| Task in closed state with open dependencies | Auto-fixed | `_inverse_state()` + write() — state reset to `04_waiting_normal` |
| `depend_on_ids` creates cycle | `ValidationError` | `_check_no_cyclic_dependencies()` — `_has_cycle('depend_on_ids')` |
| Portal user writes non-writable field | Silent drop | `_ensure_fields_write()` strips non-writable fields from vals |
| Stage change on archived task | `AccessError` | Record rule: `active=True` required for write |
| Duplicate stage assignment (batch) | No error | Batch processing deduplicates per project |

---

## Side Effects

| Effect | Model | What Happens |
|--------|-------|-------------|
| Assignee subscribed | `mail.followers` | Each `user_ids` member's `partner_id` added as follower |
| Parent task followers cascaded | `mail.followers` | Parent task's followers auto-follow subtask |
| Current user auto-subscribed | `mail.followers` | Current user's `partner_id` added as follower |
| Date assign recorded | `project_task.date_assign` | Set to `now()` when first assignee assigned |
| Date last stage update | `project_task.date_last_stage_update` | Set on stage_id change and state change |
| Stage fold → task end date | `project_task.date_end` | Set when stage has `fold=True` |
| Rating request dispatched | `rating.rating` + `mail.mail` | Customer rating email queued when stage has `rating_active=True` |
| Subtask count updated | `project_task.subtask_count` | Computed via recursive SQL on `child_ids` |
| Project task count updated | `project_project.task_count` | Counted via `_read_group` on tasks with `is_template=False` |
| Personal stage created | `project_task_stage_personal` | One record per user per task for kanban view |
| Task portal token generated | `project_task.access_token` | UUID generated when project is portal-accessible |
| Recurrence next occurrence | `project_task_recurrence` | Generates next task when last task closed |
| Milestone task count updated | `project_milestone.task_count` | Recomputed when task milestone changes |

---

## Security Context

> *Which user context the flow runs under, and what access rights are required at each step.*

| Step | Security Mode | Access Required | Notes |
|------|-------------|----------------|-------|
| `project.task.create()` | Current user | `project.group_project_user` or Project Sharing | Portal users can create via project sharing |
| `check_access('create')` | Current user | Record rule on `project_task` | Portal: `default_create_in_project_id` context bypasses some checks |
| `_ensure_fields_write()` | Portal user stripped | `PROJECT_TASK_WRITABLE_FIELDS` | Portal can only write listed fields |
| `stage_id` default lookup | Current user | Read on `project.task.type` | `stage_find()` uses domain filtered by project |
| `date_assign` write | `sudo()` on inaccessible fields | System | `sudo().write(computed_vals)` for fields portal cannot write |
| `_portal_ensure_token()` | `sudo()` | System | Portal token generated regardless of ACL |
| `message_subscribe()` | Current user | `read` on `project.task` | Follower subscription respects ACL |
| `_send_task_rating_mail()` | `sudo()` | System | Rating mail sent regardless of task ACL |
| Rating response | Public (token auth) | `rating.rating` write with valid token | External customer access |
| `project.task.write()` | Current user | `write` ACL on `project_task` | Record rules applied |
| `project.task.unlink()` | Current user | `unlink` ACL | Cascade deletes subtasks |

**Key principle:** Portal users can create tasks in projects shared with them (`project_sharing` context), but are restricted to `PROJECT_TASK_WRITABLE_FIELDS`. All other fields (including `stage_id`, `project_id`, `company_id`) are written via `sudo()` after the initial create.

---

## Transaction Boundary

```
Phase A — Creation:
  Steps 1–11  ✅  INSIDE transaction  — atomic

Phase B — Stage Change (separate write call):
  Steps 12–23 ✅  INSIDE transaction  — atomic (single write())
```

| Step | Boundary | Behavior on Failure |
|------|----------|---------------------|
| `project.task.create()` (all steps) | ✅ Atomic | Rollback on any error — no orphan records |
| `_populate_missing_personal_stages()` | ✅ Within create | Rolled back with task |
| `_task_message_auto_subscribe_notify()` | ✅ Within create | Rolled back with task |
| `rating_send_request()` | ❌ Async queue | Queued via `mail.mail`; retried by `ir.mail.server` cron |
| `mail_mail` notification dispatch | ❌ Async queue | Fire-and-forget; retry on failure |
| `rating.rating` token creation | ✅ Within create | Created synchronously with task |
| Recurrence record creation | ✅ Within create | Rolled back with task |
| Subtask cascade unlink | ✅ Within unlink() | All subtasks deleted in same transaction |

**Rule of thumb:** Task creation is fully atomic. Rating email dispatch is queued asynchronously. The `mail.mail` record is created in the same transaction, but actual email sending happens via the `ir.mail.server` cron job.

---

## Idempotency

| Scenario | Behavior |
|----------|----------|
| Double-click Save button | Browser deduplicates — one `create()` call |
| Re-create same task (same name, project) | New record created each time — no unique constraint on name+project |
| Re-save task with same stage_id | `write()` runs `update_date_end()` with same stage; no-op for fold state |
| Re-assign same user | `message_subscribe()` handles duplicates — no duplicate follower |
| Re-trigger `action_close()` on already-closed task | `write({'state': '1_done'})` re-runs — state already '1_done', no change |
| Stage change → rating request on same stage (re-trigger) | `rating_send_request()` runs again — new `rating.rating` record created each time |
| Recurrence: re-trigger on last task done | `_inverse_state()` → `_create_next_occurrences()` creates next task |

**Common patterns:**
- **Idempotent:** `write()` with same field values — ORM skips no-op writes
- **Idempotent:** Stage change to same stage — no-op
- **Non-idempotent:** Rating request — each stage change creates a new `rating.rating` record (unless rating_status is 'periodic')
- **Non-idempotent:** Recurrence next occurrence — creates a new task each time

---

## Extension Points

| Step | Hook Method | Purpose | Arguments | Override Pattern |
|------|-------------|---------|-----------|-----------------|
| Stage selection | `stage_find()` | Custom stage assignment logic | project_id, domain, order | Override to add custom ordering |
| Pre-create | Override `create()` pre-loop | Add per-vals preprocessing | vals_list | Extend before `super().create()` |
| Post-create | Override `create()` after `super()` | Custom side effects | vals_list | Add after `super().create()` |
| Assignee subscription | `_task_message_auto_subscribe_notify()` | Custom notify logic | {task: new_assignees} | Extend with `super()` |
| Stage change side effect | `_on_stage_changed()` (via write override) | Custom stage change behavior | self, vals | Extend write() override |
| Rating mail content | `rating_send_request()` | Custom rating email | template, lang, force_send | Override `_send_task_rating_mail()` |
| Personal stage population | `_populate_missing_personal_stages()` | Custom personal stage creation | self | Extend with `super()` |
| Portal token generation | `_portal_ensure_token()` | Custom token logic | self | Extend with `super()` |
| Subtask cascade | `_get_subtask_ids_per_task_id()` | Custom subtask retrieval | self | Override with `super()` |
| Task closure | `_inverse_state()` | Custom close behavior | self | Extend with `super()` |

**Standard override pattern:**
```python
# project_task.py
@api.model_create_multi
def create(self, vals_list):
    # Pre-processing
    for vals in vals_list:
        vals['my_custom_field'] = self._get_custom_default(vals)
    tasks = super().create(vals_list)
    # Post-processing
    for task in tasks:
        task._my_custom_side_effect()
    return tasks

def write(self, vals):
    result = super().write(vals)
    if 'stage_id' in vals:
        self._my_custom_stage_side_effect()
    return result
```

---

## Reverse / Undo Flow

| Action | Reverse Action | Method | Caveats |
|--------|---------------|--------|---------|
| `project.task.create()` | `unlink()` | `task.unlink()` | Cascades to subtasks, rating.rating records remain |
| Stage change | Reverse stage change | `write({'stage_id': old_stage_id})` | History not tracked; manually revert |
| Assignee added | Remove assignee | `write({'user_ids': [Command.delete(user_id)]})` | Follower remains (manual unsubscribe needed) |
| Subtask created | Delete subtask | `subtask.unlink()` | Parent's subtask_count decremented |
| Task closed (state='1_done') | Reopen task | `write({'state': '01_in_progress'})` | Rating already sent — customer may have responded |
| Rating request sent | Cancel rating | `rating.rating.write({'consumed': False})` | Rating record persists |
| Recurrence created | Remove recurrence | `write({'recurring_task': False})` | Next occurrences not generated |
| Milestone assigned | Clear milestone | `write({'milestone_id': False})` | Milestone task counts updated |
| Parent task set | Clear parent | `write({'parent_id': False})` | Only if task has no own subtasks blocking |

**Important:** Once a rating request email is dispatched (queued in `mail.mail`), it cannot be recalled. The `rating.rating` record can be marked as `consumed=False` to suppress it. Task deletion cascades to subtasks but not to rating records (ratings are preserved for reporting).

---

## Alternative Triggers

| Trigger Type | Method / Endpoint | Context | Frequency |
|-------------|------------------|---------|-----------|
| User action | `project.task.create()` / `write()` | Interactive form | Manual |
| Email-to-task | `_message_new()` | Mail gateway | On incoming email |
| Subtask creation | `parent_id` set in vals | Via task form or `action_convert_to_subtask()` | Manual |
| Recurrence generation | `_create_next_occurrences()` | Via `_inverse_state()` on last task of recurrence | Auto |
| Project stage change cascade | `_set_stage_on_project_from_task()` | When task created in project with auto-stage | Auto |
| CSV/XLS import | `import` action | Via Data menu | Batch |
| Project sharing (portal) | `project_sharing_toggle_is_follower()` | Portal user action | Manual |
| Rating response | `rating_apply()` | External customer submits rating | On demand |
| Onchange cascade | `_onchange_project_id()` | project_id field changed in form | On demand |

---

## Related

- [Modules/Project](odoo-18/Modules/project.md) — Module reference
- [Flows/Project/project-creation-flow](odoo-19/Flows/Project/project-creation-flow.md) — Project creation flow
- [Business/Project/project-management-guide](odoo-19/Business/Project/project-management-guide.md) — Business guide
- [Patterns/Workflow Patterns](odoo-18/Patterns/Workflow Patterns.md) — Workflow pattern reference
- [Core/API](odoo-18/Core/API.md) — @api decorator patterns
