---
type: module
name: project
version: Odoo 18
models_count: ~15
documentation_date: 2026-04-11
tags: [project, task, timesheet, milestone, collaboration, recurrence]
source: ~/odoo/odoo18/odoo/addons/project/
---

# Project

Project management with tasks, subtasks, milestones, timesheets, task dependencies, recurrence, and customer portal access. Core module for all project-related functionality across Odoo.

## Source Path

`~/odoo/odoo18/odoo/addons/project/`

## Models

### project.project

**Key Mixins:** `portal.mixin`, `mail.alias.mixin`, `rating.parent.mixin`, `mail.thread`, `mail.activity.mixin`, `mail.tracking.duration.mixin`, `analytic.plan.fields.mixin`.

**Key Fields:**
- `name`: Char, required, translated, trigram-indexed.
- `partner_id` (`res.partner`): Customer.
- `active`: Boolean (default True).
- `sequence`: Display order.
- `stage_id` (`project.project.stage`): Project stage (pipeline status). Group-expanded.
- `color`: Kanban color index.
- `user_id` (`res.users`): Project manager.
- `privacy_visibility`: `followers` (invite only) / `employees` (all internal) / `portal` (customers + internal). Default `portal`.
- `privacy_visibility_warning`: Computed warning when sharing issues exist.
- `access_instruction_message`: Computed portal access instructions.
- `date_start` / `date` (expiration): Date range.
- `account_id` (`account.analytic.account`): Linked analytic account for financial tracking.
- `analytic_account_balance`: Related to `account_id.balance`.
- `type_ids` (`project.task.type`): Available stages for this project.
- `task_count` / `open_task_count` / `closed_task_count`: Computed via `__compute_task_count()`.
- `task_ids`: One2many — all non-closed tasks.
- `favorite_user_ids`: M2M to `res.users` for favorites.
- `is_favorite`: Computed boolean, searchable.
- `label_tasks`: Custom label for tasks (e.g., "Tickets", "Sprints").
- `milestone_ids`: One2many to `project.milestone`.
- `milestone_count` / `milestone_count_reached` / `milestone_progress`: Milestone statistics.
- `next_milestone_id` / `can_mark_milestone_as_done` / `is_milestone_deadline_exceeded`: Next milestone state.
- `is_milestone_exceeded`: Boolean — any overdue unreached milestone.
- `allow_task_dependencies`: Feature flag, defaults to current user's group.
- `allow_milestones`: Feature flag, defaults to `group_project_milestone`.
- `tag_ids`: M2M `project.tags`.
- `collaborator_ids`: One2many `project.collaborator`.
- `collaborator_count`: Computed collaborator count.
- `update_ids`: Project status updates (one2many).
- `last_update_id` / `last_update_status` / `last_update_color`: Latest status update.
- `rating_active`: Boolean — customer ratings enabled.
- `rating_status`: `stage` (on stage change) / `periodic` (on interval).
- `rating_status_period`: `daily` / `weekly` / `bimonthly` / `monthly` / `quarterly` / `yearly`.
- `rating_request_deadline`: Computed from `rating_status_period`.
- `duration_tracking`: JSON field for time tracking state.
- `resource_calendar_id`: Computed from company or project.

**SQL Constraints:**
- `project_date_greater`: `CHECK(date >= date_start)`.

**L3 Key Methods:**
- `__compute_task_count(count_field, additional_domain)`: Generic read_group counter. Uses `display_in_project=True` filter.
- `_compute_is_favorite()` / `_set_favorite_user_ids()`: Favorites management.
- `_change_privacy_visibility()`: Cascades privacy change; logs partners who lose access.
- `_compute_company_id()` / `_inverse_company_id()`: Company sync.
- `_compute_currency_id()`: From analytic account currency.
- `_compute_resource_calendar_id()`: Falls back to company calendar.
- `_compute_percent_done()`: Uses `stage_id.fold` for closed task counting.
- `_get_stat_buttons()`: Dashboard button definitions for actions.
- `action_view_tasks(view_type)`: Returns act_window for kanban/list/gantt/form.
- `action_open_timesheet_report()`: Opens `hr_timesheet.hr_timesheet_action_report` filtered to project.
- `action_open_burndown_chart()`: Opens burndown report.
- `map_tasks(target_project_id)`: Copies all tasks (with subtasks) to another project.
- `_onchange_company_id()`: Clears stage if stage is company-specific.
- `_search_is_favorite()`: Search function for favorites field.

**Privacy Visibility (L3):**
- `followers`: Only explicitly invited followers access project and tasks.
- `employees`: All internal users can access project and all tasks.
- `portal`: Portal customers see tasks where `partner_id` matches their partner. Internal users see all.
- ACL checks via `ir.rule` on `project.project`.

---

### project.task

**Key Mixins:** `portal.mixin`, `mail.thread.cc`, `mail.activity.mixin`, `rating.mixin`, `mail.tracking.duration.mixin`, `html.field.history.mixin`.

**Dual-State System:**
- `state`: Kanban column (stage). Managed via `stage_id`. Common values include `01_in_progress`, `02_changes_requested`, `03_approved`, `1_done`, `1_canceled`, `04_waiting_normal`.
- `kanban_state`: Block status: `normal` (green) / `blocked` (red) / `done` (blue).
- `is_closed`: Computed — `True` if `state` in `CLOSED_STATES` (configured: `1_done`, `1_canceled`).

**Key Fields:**
- `name`: Char, required, trigram-indexed.
- `project_id` (`project.project`): Parent project.
- `parent_id`: Parent task (for subtasks).
- `child_ids`: One2many child tasks.
- `parent_left` / `parent_right`: MPTT fields for subtask hierarchy.
- `display_project_id`: Redirect subtasks to a different project in kanban.
- `display_in_project`: Computed — is this task visible in the project kanban.
- `displayed_image_id`: Image shown in kanban.
- `active`: Boolean.
- `priority`: `0` (normal) / `1` (high).
- `sequence`: Drag order.
- `kanban_state`: Block status.
- `stage_id` (`project.task.type`): Kanban column.
- `date_deadline`: Deadline date.
- `date_assign`: When task was assigned.
- `date_end`: When task was completed.
- `date_last_stage_update`: Track stage changes for analytics.
- `closed_subtask_count`: Computed count of closed children.
- `partner_id` / `email_cc`: Customer contact.
- `user_ids`: M2M `res.users` — multiple assignees.
- `owner_id`: Primary responsible person.
- `personal_stage_type_id`: User-specific stage for personal kanban views.
- `personal_user_ids`: Personal assignees.
- `allow_timesheets`: Feature flag — timesheet entries allowed.
- `allow_timesheet_timer`: Feature flag — timer button available.
- `planned_hours`: Planned duration (hours).
- `remaining_hours`: Computed from `planned_hours - effective_hours`.
- `effective_hours`: Sum of timesheet `unit_amount`.
- `subtask_effective_hours`: Sum of all subtask `effective_hours`.
- `progress`: 0-100% completion.
- `timesheet_ids`: One2many `account.analytic.line` (timesheet entries).
- `total_hours_spent`: Computed — `effective_hours + subtask_effective_hours`.
- `allow_subtasks`: Feature flag.
- `allow_task_dependencies`: Feature flag.
- `depend_on_ids`: M2M tasks this task is blocked by.
- `dependent_ids`: Reverse M2M (tasks blocked by this task).
- `blocked_by` / `depend_on`: Same as above (different names used in different views).
- `is_blocked`: Computed — `True` if any `blocked_by` task is not in `done` state.
- `allow_milestones`: Feature flag.
- `milestone_id`: Linked milestone.
- `has_late_and_unreached_milestone`: Boolean.
- `recurring_task`: Is this a recurring task template?
- `recurrence_id`: Linked `project.task.recurrence`.
- `recurring_count`: Number of generated occurrences.
- `repeat_unit` / `repeat_type` / `repeat_interval` / `repeat_until` / `repeat_count` / `repeat_on_month` / `repeat_on_year` / `repeat_week`: Recurrence configuration.
- `tag_ids`: M2M `project.tags`.
- `color`: Display color.
- `rating_ids`: From `rating.mixin`.
- `portal_user_names`: Computed string of portal assignee names.
- `privacy_visibility_warning`: Computed warning for sharing issues.
- `company_id`: Company assignment.
- `analytic_distribution`: JSON analytic distribution (from `analytic.mixin`).
- `sale_line_id`: Linked sale order line (from `sale_project`).
- `offer_line_ids`: Sale order lines offered for this task.

**Critical Fields for Portals:**
- `display_parent_task_button`: Show parent task button in portal.
- `current_user_same_company_partner`: Used for company-based access checks.

**Computed Fields:**
- `_compute_is_blocked()`: Any `blocked_by` task not in `done` state → blocked.
- `_compute_is_closed()`: `state in CLOSED_STATES`.
- `_compute_state()`: Auto-sets to `04_waiting_normal` when dependencies block task. If all blockers done, returns to previous non-waiting state.
- `_compute_display_name()`: Formatted display.
- `_compute_rating_stats()`: From `rating.mixin`.
- `_compute_email_from()`: Computed from `partner_id.email` or `email_from`.

**Key Methods:**
- `stage_find(project_id, order)`: Finds stage by fold/sequence/id.
- `_get_default_partner_id(project, parent)`: Inherits from parent task or project.
- `_onchange_project_id()`: Resets stage_id when project changes.
- `_onchange_kanban_state()`: Handles state reset from kanban drag.
- `_compute_access_url()` / `_compute_access_token()`: From `portal.mixin`.
- `_rating_get_grades()`: Maps `rating.POSITIVE` → `done`, `rating.NEUTRAL` → `normal`, `rating.BAD` → `blocked`.
- `_send_rating_mail()`: Sends rating request.
- `action_rating_reset()`: Resets rating.
- `_message_auto_subscribe_notify()`: Skips notification for subtasks (avoids spam cascade).

**Task Dependencies (L3):**
- `blocked_by` and `depend_on` are the same M2M relation viewed from different directions.
- `is_blocked` computed via SQL constraint for circular detection.
- When a blocker moves to `done`, the blocked task's `_compute_state()` may auto-resume it.

**Subtask Hierarchy (L3):**
- `parent_id` + MPTT (`parent_left`, `parent_right`).
- `display_project_id` overrides which project subtasks appear under in kanban.
- `subtask_effective_hours` = sum of all subtask `effective_hours` recursively.
- Creating subtask: inherits `project_id` from parent unless `display_project_id` set.

**Task Recurrence (L3):**
- Via `project.task.recurrence` mixin.
- `repeat_unit`: `day` / `week` / `month` / `year`.
- `repeat_type`: `forever` / `until` (date) / `after` (count).
- `_get_recurring_tasks()` cron: generates up to 366 occurrences. Uses `relativedelta` for date arithmetic.
- Weekly: `repeat_week` bitmask (Mon=0, Sun=6). Monthly: `repeat_day` or `repeat_on_month` + weekday. Yearly: `repeat_on_year` month index.

**Portal Access (L3):**
- `PROJECT_TASK_READABLE_FIELDS`: Fields readable by portal users.
- `PROJECT_TASK_WRITABLE_FIELDS`: Fields writable by portal users.
- `check_access_for_portal()`: Validates read/write access for portal users.
- Portal users can only write tasks shared with them.

---

### project.task.type

**Key Fields:**
- `name`, `sequence`, `fold` (column collapsed).
- `project_ids`: M2M to projects (shared stages). If empty, stage appears in all projects.
- `legend_blocked` / `legend_normal` / `legend_done`: Kanban color indicators.
- `feedback`: HTML text shown on entry to stage.
- `user_id`: Responsible person for tasks in this stage.
- `image`: Icon or image for stage.

**L3:**
- Personal stages: `project.task.type` with `user_id` set. Used in personal kanban views.
- `_unlink_if_remaining_personal_stages()`: Prevents deleting last personal stage for a user.

---

### project.collaborator

Links portal partners to projects with `limited_access` flag.

**Key Fields:**
- `project_id`: Must have `privacy_visibility = 'portal'`.
- `partner_id`: Portal partner.
- `partner_email`: Related from partner.
- `limited_access`: Boolean — whether access is restricted.

**SQL Constraints:**
- `unique_collaborator`: `UNIQUE(project_id, partner_id)`.

**L3:** `_toggle_project_sharing_portal_rules(active)` — when first collaborator added, enables portal ACL + ir.rule for project sharing feature. When last collaborator removed, disables them.

---

### project.milestone

**Key Fields:**
- `name`: Required, translated.
- `project_id`: Parent project.
- `deadline`: Target date.
- `is_reached`: Boolean — has milestone been achieved.
- `reached_date`: When `is_reached` was set.
- `state`: `pending` / `done` / `cancelled`.
- `task_ids`: One2many linked tasks.
- `product_id`: For subscription integration.
- `sale_line_id`: Linked sale order line.

**Computed Fields:**
- `_compute_can_be_marked_as_done()`: All non-cancelled linked tasks must be in `done` kanban_state.

**Key Methods:**
- `toggle_is_reached()`: Toggles `is_reached`, sets `reached_date` on achieve.

---

### project.tags

**Key Fields:**
- `name`: Unique (globally or per project).
- `color`: Display color index.
- `project_ids`: M2M to `project.project` (project-specific tags).
- `task_ids`: M2M to `project.task`.

**L3 Optimizations:**
- `name_search()`: When `project_id` in context, uses SQL with LIMIT 1000 to find tags used on recent tasks. Completes with fallback search if < limit found.
- `search_read()` / `read_group()`: Filtered to tags used in project context.
- `arrange_tag_list_by_id()`: O(n) re-ordering by id sequence.

---

### project.task.recurrence

Mixin for recurring tasks.

**Key Fields:**
- `recurring_task`: Boolean — is this a template.
- `repeat_interval`: Every N periods.
- `repeat_unit`: `day` / `week` / `month` / `year`.
- `repeat_type`: `forever` / `until` / `after`.
- `repeat_until`: End date for `until` type.
- `repeat_count`: Max occurrences for `after` type.
- `repeat_on_month`: `1`/`2`/`3`/`4` (first/second/third/fourth) / `-1` (last) — day-of-week occurrence in month.
- `repeat_on_year`: Month index (1-12) for yearly recurrence.
- `repeat_week`: Bitmask for weekdays (Mon=bit 0, Sun=bit 6) — used for weekly recurrence.

**L3 `_create_next_occurrence()`:** Copies task with postponed deadline. Uses `relativedelta` for date arithmetic. Increments `recurring_count`.

---

### project.project.stage

Project pipeline stage.

**Key Fields:**
- `name`, `sequence`, `fold`.
- `company_id`: Validated against project company.

**L3:** Unique per `project_id` per company.

---

### project.update

Project status updates.

**Key Fields:**
- `name`, `project_id`, `status` (on_track/at_risk/off_track/on_hold/to_define/done).
- `color`: Computed from status.
- `description`: HTML update text.

---

### project.alias (inherited via mail.alias.mixin)

Email integration for project.

**Key Fields:**
- `alias_name`: Email prefix (e.g., `project-acme` → `project-acme@domain`).
- `alias_model_id`: Default model (`project.task`).
- `alias_parent_thread_id`: Allow parent threading.

---

## Cross-Model Relationships

| Model | Field | Purpose |
|-------|-------|---------|
| `project.task` | `project_id` | Parent project |
| `project.task` | `parent_id` | Subtask parent |
| `project.task` | `milestone_id` | Linked milestone |
| `project.task` | `timesheet_ids` | Timesheet entries |
| `project.task` | `sale_line_id` | Billable link (sale_project) |
| `project.task` | `depend_on_ids` / `blocked_by` | Task dependencies |
| `project.project` | `account_id` | Analytic account |
| `project.project` | `collaborator_ids` | Portal collaborators |
| `project.project` | `milestone_ids` | Project milestones |
| `project.milestone` | `task_ids` | Milestone tasks |

## Edge Cases & Failure Modes

1. **Subtask without parent project**: `display_project_id` can be set independently of `project_id`. Subtasks appear under `display_project_id` in kanban while belonging to `project_id`.
2. **Circular task dependencies**: SQL constraint prevents creating circular `blocked_by` links. `is_blocked` computed field detects blocking state without cycling.
3. **Auto-resume blocked tasks**: `_compute_state()` auto-sets to `04_waiting_normal` when blocked. When blockers complete, state returns to prior non-waiting state.
4. **MPTT subtree queries**: `parent_left`/`parent_right` enable efficient subtree queries. Subtask creation requires maintaining these fields.
5. **Recurring task with dependency**: Recurrence generates independent copies. Dependencies are NOT copied to new occurrences.
6. **Milestone with no tasks**: `can_be_marked_as_done` = True if no tasks linked. Can be marked done without any task activity.
7. **Portal user write**: Only fields in `PROJECT_TASK_WRITABLE_FIELDS` are writable by portal. Other fields raise `AccessError`.
8. **Private task**: Tasks without `project_id` (private tasks) cannot have timesheets. `create()` raises `ValidationError`.
9. **Timesheet on non-billable task**: Allowed if `allow_timesheets=True`. `sale_line_id` may be absent — cost tracked but not billable.
10. **Project stage cascade**: Stage `fold` (collapsed) used in `_compute_percent_done()` to count closed tasks.

## Security Groups

- `project.group_project_stages`: Access to project stages.
- `project.group_project_manager`: Full project management.
- `project.group_project_rating`: Enable customer ratings.
- `project.group_project_task_dependencies`: Enable task dependencies feature.
- `project.group_project_milestone`: Enable milestones.

## Workflow

```
Task Created (project_id set)
        ↓
Assigned to stage (kanban column)
        ↓
Blocker task completes
        ↓
Blocked task auto-resumes to prior state
        ↓
Stage moves task to done (kanban_state=done)
        ↓
Rating request sent (if enabled)
        ↓
Task closed (state in CLOSED_STATES)
```

**Recurrence workflow:**
```
Template task (recurring_task=True) created
        ↓
Cron: _get_recurring_tasks()
        ↓
Generates occurrence with postponed deadline
recurring_count incremented
        ↓
Occurrence follows normal task workflow
```

## Integration Points

- **hr_timesheet**: Timesheet entries on tasks (`account.analytic.line`). `allow_timesheets` flag.
- **sale_project**: `sale_line_id` on tasks for billing. `offer_line_ids` for pre-sale offerings.
- **project_account**: Profitability from `account.analytic.line` and vendor bills.
- **project_purchase**: Purchase order costs in profitability.
- **rating**: Customer feedback via `rating.rating` linked to tasks.
- **calendar**: Meeting creation from tasks.
- **portal**: `portal.mixin` for customer access. `PROJECT_TASK_READABLE_FIELDS` / `PROJECT_TASK_WRITABLE_FIELDS` control what portal users can see/do.

## Source Files

- `project/models/project_project.py`
- `project/models/project_task.py`
- `project/models/project_milestone.py`
- `project/models/project_tags.py`
- `project/models/project_collaborator.py`
- `project/models/project_task_recurrence.py`