# Project Module - L4 Documentation

## Quick Access

| Resource | Type | Description |
|---------|------|-------------|
| [Flows/Project/project-creation-flow](project-creation-flow.md) | Technical Flow | Project creation method chain |
| [Flows/Project/task-lifecycle-flow](task-lifecycle-flow.md) | Technical Flow | Task lifecycle with stages |
| [Business/Project/project-management-guide](project-management-guide.md) | Business Guide | Step-by-step PM guide |

---

## Module Overview

| Property | Value |
|----------|-------|
| **Technical Name** | `project` |
| **Name** | Project |
| **Version** | 1.3 |
| **Category** | Services/Project |
| **Application** | Yes |
| **Author** | Odoo S.A. |
| **License** | LGPL-3 |
| **`_mail_post_access`** | `read` — Users need read (not write) access to post messages on tasks |

### Dependencies

```
project
├── analytic          # Analytic accounting — account_id, profitability tracking
├── base_setup       # Initial setup wizard
├── mail             # Messaging, notifications, alias routing, tracking
├── portal           # Portal access, collaborator sharing
├── rating           # Customer satisfaction ratings
├── resource         # Resource calendars, working time calculations
├── web              # Web interface
├── web_tour         # Guided tours
└── digest           # Dashboard digest emails (open task KPIs)
```

### Key Features

1. **Project Management** — Create and manage projects with lifecycle stages, milestones, and status updates
2. **Task Management** — Hierarchical tasks with subtasks, cross-project dependencies, and recurring tasks
3. **Collaboration** — Project sharing with external portal collaborators via `project.collaborator`
4. **Time Tracking** — Integration with `project_timesheet` via `timesheet_ids` on tasks
5. **Customer Ratings** — Automated satisfaction surveys per task stage, with auto-validation
6. **Milestones** — Track project progress through key deliverables with deadline tracking
7. **Project Updates** — Status reporting with traffic-light indicators (on_track/at_risk/off_track/on_hold/done)
8. **Project Templates** — Create projects from templates with role-based task dispatching
9. **Project Sharing** — Fine-grained portal access with collaborator-level permissions

---

## 1. project.project (Main Project Model)

**File:** `~/odoo/odoo19/odoo/addons/project/models/project_project.py`

### Class Signature

```python
class ProjectProject(models.Model):
    _name = 'project.project'
    _description = "Project"
    _inherit = [
        'portal.mixin',              # Portal access, access_token, access_url
        'mail.alias.mixin',          # Email alias for project inbox → task creation
        'rating.parent.mixin',       # Parent ratings: aggregates from child task ratings
        'mail.activity.mixin',       # Activities & reminders on project
        'mail.tracking.duration.mixin',  # Stage transition duration tracking
        'analytic.plan.fields.mixin',    # Analytic account plan fields
    ]
    _order = "sequence, name, id"
    _rating_satisfaction_days = 30  # Rating aggregation window
    _track_duration_field = 'stage_id'  # Duration tracked per project lifecycle stage
```

### Database Indexes

| Index | Type | Purpose |
|-------|------|---------|
| `project_project__is_template_idx` | Partial index (`WHERE is_template IS TRUE`) | Fast lookup of project templates |

### Fields

#### Core Identification
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | Char | required | Project name. Indexed with trigram index for fast search. Translateable. |
| `description` | Html | — | Project description rendered in the UI. |
| `active` | Boolean | `True` | Archival flag. Archiving a project cascades `active=False` to all tasks. |
| `sequence` | Integer | `10` | Manual ordering across projects. |
| `color` | Integer | — | Kanban card color index (0–11). Used for visual grouping. |

#### Customer & Company
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `partner_id` | Many2one (res.partner) | — | Customer/client. `bypass_search_access=True` for fast partner lookup. Domain restricts to same company or no company. Indexed `btree_not_null`. |
| `company_id` | Many2one (res.company) | computed | Company derived from `account_id.company_id` or `partner_id.company_id`. Inverse writes back to both. **Changing company is blocked** if the analytic account has analytic lines OR multiple projects share the same account. |
| `currency_id` | Many2one (res.currency) | computed from company | Currency for monetary display fields. |

#### Project Manager
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `user_id` | Many2one (res.users) | `env.user` | Project Manager. Tracked. `falsy_value_label="👤 Unassigned"`. |
| `favorite_user_ids` | Many2many (res.users) | — | Users who marked the project as favorite. Stored in `project_favorite_user_rel`. |
| `is_favorite` | Boolean | computed | Whether current user has marked project as favorite. Read via sudo. Searchable. The `_order_field_to_sql` override makes favorited projects sort first via SQL `INNER JOIN`. |
| `label_tasks` | Char | translated "Tasks" | Custom label for tasks (e.g., "Tickets", "Issues", "Sprints"). Translateable. |

#### Analytic Account
| Field | Type | Description |
|-------|------|-------------|
| `account_id` | Many2one (account.analytic.account) | Linked analytic account. `ondelete='set null'`. Domain restricts to same company or no company. |
| `analytic_account_balance` | Monetary (related) | `related="account_id.balance"` — computed from analytic account. |

#### Tasks & Stages
| Field | Type | Description |
|-------|------|-------------|
| `tasks` | One2many (project.task) | All task records (`inverse` on `project_id`). |
| `task_ids` | One2many (project.task) | Non-closed tasks only (`domain=[('is_closed','=',False)]`). Used in dashboard. |
| `type_ids` | Many2many (project.task.type) | Task stages/columns shared across projects via `project_task_type_rel`. |
| `task_count` | Integer | Total task count (computed via `read_group`). |
| `open_task_count` | Integer | Non-closed tasks where `state in OPEN_STATES` (computed). |
| `closed_task_count` | Integer | Tasks where `state in ['1_done', '1_canceled']` (computed). |
| `task_completion_percentage` | Float | `1 - open_task_count / task_count` (computed, 0 if no tasks). |

#### Milestones
| Field | Type | Description |
|-------|------|-------------|
| `allow_milestones` | Boolean | Feature toggle. Inverse calls `_check_project_group_with_field(..., 'project.group_project_milestone')` — dynamically adds/removes group from `base.group_user`. |
| `milestone_ids` | One2many (project.milestone) | Project milestones. `copy=True` (milestones are cloned on project copy). |
| `milestone_count` | Integer | Total milestone count. |
| `milestone_count_reached` | Integer | Reached milestone count. |
| `milestone_progress` | Integer | Percentage reached: `milestone_count_reached * 100 // milestone_count`. |
| `is_milestone_exceeded` | Boolean | True if any unreached milestone has `deadline <= today`. Searchable via SQL subquery. |
| `is_milestone_deadline_exceeded` | Boolean | True if the next unreached milestone's deadline is passed. |
| `next_milestone_id` | Many2one | Next unreached milestone with earliest deadline. |
| `can_mark_milestone_as_done` | Boolean | True if all tasks done (no open tasks) and at least one closed task. |
| `is_milestone_deadline_exceeded` | Boolean | Recomputed from milestone deadlines. |

#### Updates & Status
| Field | Type | Description |
|-------|------|-------------|
| `update_ids` | One2many (project.update) | Project status updates (newest first: `_order = 'id desc'`). |
| `update_count` | Integer | Count of updates. |
| `last_update_id` | Many2one (project.update) | Most recent update. Set via `sudo()` on update creation. |
| `last_update_status` | Selection | `on_track/at_risk/off_track/on_hold/to_define/done`. Stored (`store=True`). Defaults to `to_define`. |
| `last_update_color` | Integer | Color computed from `STATUS_COLOR` map. |

**Status Color Mapping (`project_update.py`):**
| Status | Color | Bootstrap Context |
|--------|-------|-----------------|
| `on_track` | 20 | green / success |
| `at_risk` | 22 | orange / warning |
| `off_track` | 23 | red / danger |
| `on_hold` | 21 | light blue / info |
| `done` | 24 | purple |
| `to_define` / `False` | 0 | grey (default) |

#### Collaboration & Sharing
| Field | Type | Description |
|-------|------|-------------|
| `privacy_visibility` | Selection | `followers/invited_users/employees/portal`. Default `portal`. **L4: Changing from `portal`/`invited_users` to a more restrictive visibility automatically unsubscribes portal users, clears access tokens, and cascades to tasks.** |
| `privacy_visibility_warning` | Char | Warning displayed when switching to/from `portal`/`invited_users`. |
| `access_instruction_message` | Char | Dynamic instructions shown based on current privacy setting. |
| `collaborator_ids` | One2many (project.collaborator) | External collaborators. |
| `collaborator_count` | Integer | Count (computed, sudo). Only computed for `invited_users`/`portal` projects. |
| `access_token` | Char | Used for portal access. Cleared when visibility becomes non-portal. |

#### Dates & Planning
| Field | Type | Description |
|-------|------|-------------|
| `date_start` | Date | Project start date. `copy=False`. |
| `date` | Date | Project end/deadline date. `copy=False`. **Constraint**: `date >= date_start`. Changing `date` to `False` also clears `date_start` (and vice versa), preventing partial date states. |
| `resource_calendar_id` | Many2one (resource.calendar) | Working hours template. Computed from `company_id` → `resource_calendar_id`, falling back to `env.company`. Used to compute `working_hours_open/close` on tasks. |

#### Feature Toggles (L4: Dynamic Group Management)
| Field | Type | Description |
|-------|------|-------------|
| `allow_task_dependencies` | Boolean | Feature toggle. Inverse `_inverse_allow_task_dependencies` manages the `project.group_project_task_dependencies` implied group. When enabled, open tasks with open blocking dependencies are set to `04_waiting_normal`. When disabled, all waiting tasks revert to `01_in_progress`. |
| `allow_milestones` | Boolean | Feature toggle. Inverse manages `project.group_project_milestone` group. |
| `allow_recurring_tasks` | Boolean | Feature toggle. Inverse manages `project.group_project_recurring_tasks` group. When disabled, all recurring tasks have `recurring_task` set to `False`. |

**L4 — Dynamic Group Pattern**: `_check_project_group_with_field(field_name, group_name)` searches whether any project has the feature enabled. If enabled but user lacks group → adds implied group to `base.group_user`. If disabled and user has group → removes it and clears group members. This keeps permissions synchronized with actual usage.

#### Tags & Templates
| Field | Type | Description |
|-------|------|-------------|
| `tag_ids` | Many2many (project.tags) | Project tags. Relation table `project_project_project_tags_rel`. |
| `task_properties_definition` | PropertiesDefinition | Custom task property schema (Studio-compatible). |
| `is_template` | Boolean | Marks project as a reusable template. Templates cannot be created as a project from a collaborator. |
| `stage_id` | Many2one (project.project.stage) | Project lifecycle stage (Planning/In Progress/On Hold/Complete). `ondelete='restrict'`. Defaults to lowest-sequence stage. |
| `stage_id_color` | Integer (related) | Stage color. |

#### Ratings
| Field | Type | Description |
|-------|------|-------------|
| `rating_active` | Boolean (related) | From stage settings. |
| `show_ratings` | Boolean | True if any assigned stage has `rating_active=True`. |
| `rating_avg` | Float (parent mixin) | Average rating over `_rating_satisfaction_days` (30 days). |
| `rating_count` | Integer (parent mixin) | Total rating count. |

### Key Methods

#### Task Counting (L4: Generic Read-Group Pattern)
```python
def __compute_task_count(self, count_field='task_count', additional_domain=None):
    """Generic helper. Validates count_field name against declared count fields.
    Uses _read_group for efficient DB aggregation.
    Context `active_test` forwarded based on whether ANY project in self is active."""
```

The three standard counters use `read_group` domain:
- `task_count`: `[('project_id', 'in', self.ids), ('is_template', '=', False)]`
- `open_task_count`: adds `('state', 'in', OPEN_STATES)`
- `closed_task_count`: adds `('state', 'in', ['1_done', '1_canceled'])`

#### Milestone Computation (L4: SQL Window Function)
```python
def _search_is_milestone_exceeded(self, operator, value):
    # Uses SQL ANY subquery to avoid self-join:
    # SELECT P.id FROM project_project P LEFT JOIN project_milestone M ...
    # WHERE M.is_reached IS false AND P.allow_milestones IS true AND M.deadline <= today
```

#### Company Consistency (L4: Multi-Level Validation)
```python
def _inverse_company_id(self):
    # 1. Partner must share company with project
    # 2. If analytic account has >1 project OR has any analytic lines → block company change
    # 3. Otherwise write company back to analytic account
    for project in self:
        if account.company_id != new_company and (account.line_ids or account.project_count > 1):
            raise UserError("Cannot change company: analytic account has lines or multiple projects")
```

#### Project Creation Flow (L4)
1. `create()` — strips `is_favorite` from vals, converts to `favorite_user_ids` Command
2. If `group_project_stages` enabled and stage has company → validates stage.company_id matches project company
3. Otherwise picks first stage matching company or no-company stage
4. `name_create()` (quick create) auto-creates a default "New" stage if none exist
5. `copy()` duplicates project, optionally milestones, runs `map_tasks()`, and copies follower subscriptions

#### Privacy Change Flow (L4)
```python
def _change_privacy_visibility(self, new_visibility):
    if new_visibility in ['invited_users', 'portal']:
        # Subscribe project + task partners as followers
        project.message_subscribe(partner_ids=project.partner_id.ids)
        for task in project.task_ids.filtered('partner_id'):
            task.message_subscribe(partner_ids=task.partner_id.ids)
    elif old in ['invited_users', 'portal']:
        # Unsubscribe portal users, revoke access tokens
        project.tasks._unsubscribe_portal_users()
        project.tasks.mapped('access_token').unlink()
        project.mapped('access_token').unlink()
```

#### Template Creation (L4)
- `is_template=True` projects can be copied with `copy_from_template=True`
- `_get_template_field_blacklist()` excludes `partner_id` from template copy
- `action_create_from_template()` optionally applies role→user mapping from `role_ids` on tasks
- After template creation, `role_ids` are cleared from all copied tasks

#### `_alias_get_creation_values`
```python
# Alias model → project.task so emails sent to project alias create tasks
values['alias_model_id'] = ir.model._get('project.task').id
values['alias_defaults'] = {'project_id': self.id}  # auto-link to project
```

### Constraints

```python
_project_date_greater = models.Constraint(
    'check(date >= date_start)',
    "The project's start date must be before its end date.",
)
```

### Performance Considerations (L4)

- **`_read_group` over `search_count`**: All task count methods use `_read_group` which is a single SQL `GROUP BY` query rather than N `search_count` calls.
- **`read_group` with `state:array_agg`**: Milestone task counts use `array_agg` to get both total and closed counts in one query per milestone group.
- **Partial index on `is_template`**: Only templates trigger this index, keeping it lean.
- **`trigram index` on `name`**: Enables fast `ILIKE` searches in the project kanban/list view.
- **Collaborator count**: Only computed for `invited_users`/`portal` projects — avoids wasted computation for `employees`-only projects.
- **Milestone exceeded search**: Uses raw SQL subquery with LEFT JOIN to avoid ORM self-joins.

---

## 2. project.task (Task Model)

**File:** `~/odoo/odoo19/odoo/addons/project/models/project_task.py`

### Class Signature

```python
class ProjectTask(models.Model):
    _name = 'project.task'
    _description = "Task"
    _date_name = "date_assign"           # Gantt view uses date_assign as reference
    _inherit = [
        'portal.mixin',                 # Portal access token & URL
        'mail.thread.cc',              # Email CC handling on tasks
        'mail.activity.mixin',          # Activities on tasks
        'rating.mixin',                 # Task-level ratings
        'mail.tracking.duration.mixin',  # Stage transition duration tracking
        'html.field.history.mixin',    # Description change history (versioned)
    ]
    _mail_post_access = 'read'          # Only read access needed to post messages
    _mail_thread_customer = True         # Enables customer field tracking
    _order = "priority desc, sequence, date_deadline asc, id desc"
    _primary_email = 'email_from'        # Used for partner matching in mail gateway
    _systray_view = 'list'              # Systray shows task as list, not kanban
    _track_duration_field = 'stage_id'
    _is_template_idx = models.Index('(is_template) WHERE is_template IS TRUE')
```

### Constants

```python
CLOSED_STATES = {
    '1_done': 'Done',
    '1_canceled': 'Cancelled',
}

# OPEN_STATES is a dynamic property:
@property
def OPEN_STATES(self):
    """Returns all state values minus CLOSED_STATES"""
    return list(set(self._fields['state'].get_values(self.env)) - set(CLOSED_STATES))
```

### Task State Machine (L4: Full State Diagram)

The `state` field is a **computed+stored selection** with `recursive=True` and its own inverse method:

| State Value | Label | Kanban Indicator | Entry Condition | Exit Condition |
|-------------|-------|-----------------|-----------------|----------------|
| `01_in_progress` | In Progress | Blue dot | Default on create. Task has no open blockers. | Blockers added OR project changes |
| `02_changes_requested` | Changes Requested | Orange dot | `auto_validation_state` + rating < 4 | New rating applied |
| `03_approved` | Approved | Green check | `auto_validation_state` + rating >= 4 | New lower rating applied |
| `1_done` | Done | Green bullet | Task closed complete | Inverse (recurrence creation) |
| `1_canceled` | Cancelled | Red X | Task closed cancelled | Inverse (recurrence creation) |
| `04_waiting_normal` | Waiting | Grey clock | Blockers added OR feature toggled on with open blockers | All blockers closed OR feature toggled off |

**L4 — State Computation Logic (`_compute_state`):**
1. If `allow_task_dependencies` is True and any `depend_on_ids` are not in `CLOSED_STATES` → set `04_waiting_normal`
2. If task is already in a closed state → do not overwrite (preserves done/cancelled)
3. Otherwise → set `01_in_progress`

**L4 — State Inverse Logic (`_inverse_state`):**
When a task is moved to a closed state (`1_done` or `1_canceled`) and it is the **last occurrence** of its recurrence (`id == max(task_ids.ids)`), the recurrence engine creates the next occurrence.

### Priority Values

| Value | Label | Sort Impact |
|-------|-------|-------------|
| `0` | Low priority | Lowest priority sort (default) |
| `1` | Medium priority | 1 star |
| `2` | High priority | 2 stars |
| `3` | Urgent | 3 stars + red background |

### Fields (Complete Reference)

#### Core Identification
| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | Char | required | Task title. Indexed `trigram`. Tracked. |
| `description` | Html | — | Task description. `sanitize_attributes=False` (allows scripts in trusted content). Tracked via `html.field.history.mixin`. |
| `active` | Boolean | `True` | Archival flag. Subtasks with `display_in_project=False` are also archived when parent is. |
| `priority` | Selection | `'0'` | 0–3 as string selection values (not integer). |
| `sequence` | Integer | `10` | Manual ordering within project. |
| `color` | Integer | — | Per-task color for kanban grouping. |

#### Stage & State
| Field | Type | Description |
|-------|------|-------------|
| `stage_id` | Many2one (project.task.type) | Kanban stage. Compute+inverse from project. Domain restricts to project's shared stages. `ondelete='restrict'`. Tracked. `group_expand='_read_group_stage_ids'` — returns all stages applicable to the project context. |
| `stage_id_color` | Integer (related) | `related="stage_id.color"` |
| `state` | Selection | Computed+stored+recursive+inverse. Default `01_in_progress`. |
| `is_closed` | Boolean | `True` if `state in CLOSED_STATES`. Searchable via `_search_is_closed`. |
| `date_last_stage_update` | Datetime | Timestamp of last stage OR state change. Used for rotting detection and statistics. |
| `date_assign` | Datetime | Set to `now` when first user assigned (not when last user removed). Cleared when all users removed. |
| `date_end` | Datetime | Set when task enters a folded stage (`fold=True`). Cleared on stage change. |
| `date_deadline` | Datetime | Task due date. Tracked. `copy=False`. |

#### Project & Customer (L4: Complex Company Resolution)
| Field | Type | Description |
|-------|------|-------------|
| `project_id` | Many2one (project.project) | Parent project. Compute+inverse+recursive+precompute. `falsy_value_label="🔒 Private"` — tasks without project are private to assignees. Domain: same company or no company. `change_default=True` allows URL-based default. |
| `display_in_project` | Boolean | True if task should appear in project kanban. False if subtask hidden in parent project. Computed: True unless `project_id == parent_id.project_id`. |
| `partner_id` | Many2one (res.partner) | Customer contact. Compute+inverse+recursive. Falls back to `parent_id.partner_id` or `project_id.partner_id` if not set. Cannot conflict with task's company. |
| `partner_phone` | Char | Phone from related partner. Inverse writes back to partner. |
| `email_from` | Char | Primary email used for mail gateway partner matching. `_primary_email` on model. |
| `email_cc` | Char | CC addresses from incoming emails not matched to partners. Internal users matching CC are assigned as followers and notified. |
| `company_id` | Many2one (res.company) | Compute+inverse+recursive. Falls back: `project_id.company_id` or `parent_id.company_id`. If company changes on project → project field is cleared. |
| `project_privacy_visibility` | Selection (related) | Project visibility. |

#### Assignees (L4: Multi-Assignee with Personal Stages)
| Field | Type | Description |
|-------|------|-------------|
| `user_ids` | Many2many (res.users) | Multiple assignees. Tracked. Domain excludes share users. `context={'active_test': False}` — shows inactive assignees too. `falsy_value_label="👤 Unassigned"`. Default: current user if no project, empty if in personal stage context. |
| `portal_user_names` | Char | All assignee names for project sharing view (portal users can't see internal user IDs). |
| `personal_stage_type_ids` | Many2many (project.task.type) | Intermediate M2M storing per-user personal stages. Uses `project_task_user_rel` table with `stage_id` column. Domain restricted to `user_id=uid`. |
| `personal_stage_id` | Many2one (project.task.stage.personal) | Current user's personal stage state. Compute+sudo+search. Each `(task_id, user_id)` pair has exactly one `project.task.stage.personal` record. |
| `personal_stage_type_id` | Many2one (project.task.type) | Related to `personal_stage_id.stage_id`. Used for group_expand. |

#### Task Hierarchy — Subtasks (L4: Recursive CTE)
| Field | Type | Description |
|-------|------|-------------|
| `parent_id` | Many2one (project.task) | Parent task. Inverse auto-updates `display_in_project`. Domain prevents self-reference `['!', ('id', 'child_of', id)]`. Constraint prevents private tasks from being parents. |
| `child_ids` | One2many (project.task) | Subtasks. Domain `['recurring_task', '=', False]` — subtasks cannot themselves be recurring. |
| `subtask_count` | Integer | Total subtasks. |
| `closed_subtask_count` | Integer | Closed subtasks. |
| `subtask_completion_percentage` | Float | `closed_subtask_count / subtask_count`. |
| `subtask_allocated_hours` | Float | Sum of `allocated_hours` on all direct child tasks (not recursive). |
| `display_parent_task_button` | Boolean | Whether current user can access parent task (access check via `_filtered_access`). |

**L4 — Recursive Subtask CTE** (`_get_subtask_ids_per_task_id`):
```python
WITH RECURSIVE task_tree AS (
    SELECT id, id as supertask_id FROM project_task WHERE id IN %(ancestor_ids)s
    UNION ALL
    SELECT t.id, tree.supertask_id
    FROM project_task t JOIN task_tree tree ON tree.id = t.parent_id
    WHERE t.parent_id IS NOT NULL
)
SELECT supertask_id, ARRAY_AGG(id) FROM task_tree WHERE id != supertask_id GROUP BY supertask_id
```
This single query handles unlimited nesting depth efficiently.

#### Time Tracking (L4: Calendar-Based)
| Field | Type | Description |
|-------|------|-------------|
| `allocated_hours` | Float | Planned time budget in hours. Tracked. |
| `working_hours_open` | Float | Calendar-adjusted hours from create to assignment. `aggregator="avg"` enables Gantt grouping. |
| `working_hours_close` | Float | Calendar-adjusted hours from create to completion. |
| `working_days_open` | Float | Calendar-adjusted working days to assignment. |
| `working_days_close` | Float | Calendar-adjusted working days to closure. |

**L4 — Calendar Calculation**:
```python
def _compute_elapsed(self):
    # Only tasks with a project+calendar are computed
    # Falls back to 0.0 for tasks without calendar
    duration_data = project.resource_calendar_id.get_work_duration_data(
        start_dt, end_dt, compute_leaves=True
    )
```

#### Task Dependencies (L4: Graph + Cycle Detection)
| Field | Type | Description |
|-------|------|-------------|
| `allow_task_dependencies` | Boolean (related) | Inherited from project. |
| `depend_on_ids` | Many2many (project.task) | Tasks blocking this one. Junction table `task_dependencies_rel`, columns `task_id` (blocked) and `depends_on_id` (blocker). Domain excludes self and tasks without project. |
| `depend_on_count` | Integer | Total blockers (computed). |
| `closed_depend_on_count` | Integer | Closed blockers (computed via `state:array_agg`). |
| `dependent_ids` | Many2many (project.task) | Reverse: tasks this task blocks. |
| `dependent_tasks_count` | Integer | Non-closed dependent tasks (computed). |

**L4 — Cycle Detection**: `_check_no_cyclic_dependencies` uses `_has_cycle('depend_on_ids')` which internally runs a recursive SQL traversal.

#### Recurring Tasks
| Field | Type | Description |
|-------|------|-------------|
| `allow_recurring_tasks` | Boolean (related) | From project setting. |
| `recurring_task` | Boolean | True if task is part of a recurrence. Constrained: cannot have a parent. |
| `recurrence_id` | Many2one (project.task.recurrence) | Parent recurrence. `index='btree_not_null'`. |
| `recurring_count` | Integer | Total occurrences in this recurrence. |
| `repeat_interval` | Integer | Repeat every N units. Compute from recurrence. |
| `repeat_unit` | Selection | `day/week/month/year`. |
| `repeat_type` | Selection | `forever/until`. |
| `repeat_until` | Date | End date for limited recurrence. |

#### Tags & Custom Properties
| Field | Type | Description |
|-------|------|-------------|
| `tag_ids` | Many2many (project.tags) | Task tags. Shared with project tags. |
| `task_properties` | Properties | Custom properties from `project_id.task_properties_definition`. `copy=True`. |
| `displayed_image_id` | Many2one (ir.attachment) | Cover image. Domain: `res_model=project.task`, `res_id=id`, `mimetype ilike image`. |
| `attachment_ids` | One2many | Non-message attachments. Computed as `ir.attachment - message_attachment_ids`. |

#### Templates
| Field | Type | Description |
|-------|------|-------------|
| `is_template` | Boolean | Task is a template. Partial index on `is_template IS TRUE`. |
| `has_project_template` | Boolean (related) | Whether parent project is a template. |
| `has_template_ancestor` | Boolean | True if this task or any ancestor is a template. Computed+stored+searchable. |
| `display_name` | Char (inverse) | Task name with quick-create shortcuts parsed on save. |

**L4 — Quick Create Shortcuts (parsed by `_inverse_display_name`):**
- `#tag` → creates/finds tag in `project.tags`
- `@user` → assigns user via `name_search`
- `!` → sets priority `1` (Medium)
- `!!` → sets priority `2` (High)
- `!!!` → sets priority `3` (Urgent)

Pattern: `re.compile(r'^(?! [#!@\s])((?:\s[#@]%s[^\s]+)*(?:\s!{1,3})?(?:\s|$))*')`

#### Rating Configuration
| Field | Type | Description |
|-------|------|-------------|
| `rating_active` | Boolean (related) | From stage. Controls `mt_task_rating` subtype visibility. |
| `rating_ids` | One2many (rating.rating) | Inherited from `rating.mixin`. Parent res: `project_id`. |

#### Followers & Portal
| Field | Type | Description |
|-------|------|-------------|
| `current_user_same_company_partner` | Boolean | Whether current user shares commercial partner with task's partner. |
| `display_follow_button` | Boolean | For portal users: whether to show Follow/Unfollow. False if collaborator has `limited_access=True`. |
| `website_message_ids` | One2many | Portal-accessible messages. Domain: `message_type in ['email', 'comment', 'email_outgoing', 'auto_comment']`. |
| `access_token` | Char | Portal access token. Set when project is `portal`/`invited_users` and collaborator is added. |
| `access_url` | Char | `/my/tasks/{id}` for portal. |

### Key Methods

#### `_compute_state` (L4: Full Logic)
```python
def _compute_state(self):
    for task in self:
        open_blockers = []
        if task.allow_task_dependencies:
            open_blockers = [t for t in task.depend_on_ids if t.state not in CLOSED_STATES]
        if open_blockers and task.state not in CLOSED_STATES:
            task.state = '04_waiting_normal'
        elif task.state not in CLOSED_STATES:
            task.state = '01_in_progress'
```

#### `_inverse_state` — Recurrence Trigger
```python
def _inverse_state(self):
    # Only the LAST task in a recurrence generates the next occurrence
    last_task_id_per_recurrence = self.recurrence_id._get_last_task_id_per_recurrence_id()
    tasks = self.filtered(
        lambda t: t.state in CLOSED_STATES
        and t.id == last_task_id_per_recurrence.get(t.recurrence_id.id)
    )
    self.env['project.task.recurrence']._create_next_occurrences(tasks)
```

#### `message_subscribe` Override (L4: Project Follower Inheritance)
When a user follows a project, task notification subtypes are inherited from the project's subscription. Internal/default subtypes propagate to task followers automatically.

#### `_create_task_mapping` — Dependency Remapping on Copy
Used by both `copy()` and recurrence copy to maintain dependency graph integrity after copying tasks.

#### `message_new` — Email Gateway Handler (L4)
```python
def message_new(self, msg_dict, custom_values=None):
    # 1. Strips default author to avoid gateway user being responsible
    # 2. Auto-creates partner from email if not existent
    # 3. Sets partner as follower automatically
    # 4. Parses 'to' field to find internal users → assigns them
    # 5. Unmatched emails → added to email_cc field
    # 6. Reply-to address routed via project's alias
```

#### `_message_post_after_hook` (L4: Description Auto-Population)
If task has no description and is created from email where the author matches the task's partner, the email body is sanitized (signatures stripped via xpath) and used as the task description.

#### `_send_task_rating_mail` (L4: Rating Trigger)
- Called on stage entry when `rating_active=True` and `rating_status='stage'`
- Cron-called daily for `rating_status='periodic'` stages via `_send_rating_all`
- Skips templates (`is_template=True`) and tasks with no partner

#### `rating_apply` (L4: Auto-Validation)
```python
def rating_apply(self, rate, ...):
    result = super().rating_apply(...)
    if self.stage_id.auto_validation_state:
        # Good rating (>=4) → state = '03_approved'
        # Neutral/bad (<4) → state = '02_changes_requested'
        state = '03_approved' if rating.rating >= RATING_LIMIT_SATISFIED else '02_changes_requested'
        self.write({'state': state})
    return rating
```

#### `_get_rotting_depends_fields` (L4: Rotting Extension)
Adds `is_closed` to the rotting dependency list, so rotting only tracks open tasks:
```python
def _get_rotting_depends_fields(self):
    return super()._get_rotting_depends_fields() + ['is_closed']
```

### Constraints

```python
# Recurring tasks cannot be subtasks
_recurring_task_has_no_parent = models.Constraint(
    'CHECK (NOT (recurring_task IS TRUE AND parent_id IS NOT NULL))',
    'You cannot convert this task into a sub-task because it is recurrent.',
)

# Private tasks cannot be parents
_private_task_has_no_parent = models.Constraint(
    'CHECK (NOT (project_id IS NULL AND parent_id IS NOT NULL))',
    'A private task cannot have a parent.',
)

# Company consistency
@api.constrains('company_id', 'partner_id')
def _ensure_company_consistency_with_partner(self):
    # Task company must match partner company if partner has a company

# Super-task guard
@api.constrains('child_ids', 'project_id')
def _ensure_super_task_is_not_private(self):
    # A task with subtasks cannot be made private (project_id=None)
```

### Portal Access (L4: Field-Level Security)

**`PROJECT_TASK_READABLE_FIELDS`** (45 fields) — accessible to portal users via `_portal_accessible_fields` ORM cache:

Notable exclusions: `description`, `allocated_hours`, `date_assign`, `date_end`, `date_deadline`, `email_from`, `planned_hours`, `remaining_hours`, `analytic_account_line_ids`, `collection_id`, `grant_business_activity_id`, `planned_date_start`, `planned_date_end`.

**`PROJECT_TASK_WRITABLE_FIELDS`** (17 fields) — portal can write: `name`, `description`, `partner_id`, `date_deadline`, `date_last_stage_update`, `tag_ids`, `sequence`, `stage_id`, `child_ids`, `color`, `parent_id`, `priority`, `state`, `is_closed`.

**L4 — Access Control Flow:**
1. `_get_view_cache_key` appends `self.env.user._is_portal()` to view cache key
2. `fields_get` marks non-readable fields as `readonly=True` for portal
3. `_has_field_access` checks `readable`/`writeable` frozensets
4. `_ensure_fields_write` validates M2O access for portal users

---

## 3. project.task.type (Task Stage)

**File:** `~/odoo/odoo19/odoo/addons/project/models/project_task_type.py`

### Class Signature

```python
class ProjectTaskType(models.Model):
    _name = 'project.task.type'
    _description = 'Task Stage'
    _order = 'sequence, id'
```

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `active` | Boolean | `True` | Archival flag. **L4**: Deactivating a stage also deactivates all tasks in that stage. |
| `name` | Char | required | Stage name. Translateable. |
| `sequence` | Integer | `1` | Ordering within kanban. |
| `project_ids` | Many2many (project.project) | from context | Shared stages across multiple projects via `project_task_type_rel`. When set on a shared stage, `user_id` is cleared. |
| `mail_template_id` | Many2one (mail.template) | — | Email sent when task enters stage. Only sent if user has `group_project_stages`. |
| `color` | Integer | — | Stage kanban color. |
| `fold` | Boolean | — | Folded kanban column. Entering a folded stage sets `date_end` on task. |
| `user_id` | Many2one (res.users) | computed | Stage owner for **personal stages**. Computed+sotable. When `project_ids` is set after creation, `user_id` is cleared. A personal stage cannot have `project_ids`. |
| `rotting_threshold_days` | Integer | `0` | Days until tasks in this stage become stale. `0` disables. Affects `date_last_stage_update` rotting logic. Does not retroactively update rotting status. |
| `rating_template_id` | Many2one (mail.template) | — | Rating request email sent to customer when task enters this stage. |
| `auto_validation_state` | Boolean | `False` | Auto-update task kanban state based on rating feedback. |
| `rating_active` | Boolean | — | Enable customer ratings for this stage. Toggle also hides/shows `mt_project_task_rating` and `mt_task_rating` subtypes and `rating_project_request_email_template`. |
| `rating_status` | Selection | `stage` | `stage` (on enter) or `periodic` (cron-based recurring). |
| `rating_status_period` | Selection | `monthly` | Period for periodic ratings. |
| `rating_request_deadline` | Datetime | computed | `now + timedelta(days=period_days)`. Recomputed after each rating send. |

### Rating Status Period Mapping

```python
periods = {'daily': 1, 'weekly': 7, 'bimonthly': 15, 'monthly': 30, 'quarterly': 90, 'yearly': 365}
```

### Auto-Validation State Machine

When `auto_validation_state=True` on the stage a task moves to:
- `rating.rating >= RATING_LIMIT_SATISFIED (4/5)` → task state becomes `03_approved`
- `rating.rating < RATING_LIMIT_SATISFIED` → task state becomes `02_changes_requested`

### Personal Stages (L4: User-Private Kanban Columns)

A stage with `user_id` set is a **personal stage** — only visible to that user and cannot be shared with any project.

```python
@api.constrains('user_id', 'project_ids')
def _check_personal_stage_not_linked_to_projects(self):
    if any(stage.user_id and stage.project_ids for stage in self):
        raise UserError('A personal stage cannot be linked to a project...')
```

**L4 — Deletion Handling (`_unlink_if_remaining_personal_stages`):**
- When a personal stage is deleted, tasks using it are moved to a replacement stage
- Replacement: closest stage with lower sequence, or closest with higher sequence if none lower
- If user has no remaining personal stages → deletion blocked with UserError

**Default Personal Stages** (created for each new internal user):
1. Inbox (seq: 1)
2. Today (seq: 2)
3. This Week (seq: 3)
4. This Month (seq: 4)
5. Later (seq: 5)
6. Done (seq: 6, fold: True)
7. Cancelled (seq: 7, fold: True)

### Key Methods

**`unlink_wizard`** — Opens a wizard to reassign tasks before stage deletion. Uses `_read_group` to find affected projects (both linked and tasks-in-stage).

**`_send_rating_all`** (L4: Cron Handler):
```python
def _send_rating_all(self):
    # Runs daily via ir.cron
    # Finds stages where rating_active=True, rating_status='periodic',
    # AND rating_request_deadline <= now
    # Then sends to all tasks in those stages across all projects
    # Then recomputes rating_request_deadline for next period
    # CRITICAL: commits to DB after each stage to avoid giant transaction
```

---

## 4. project.milestone (Project Milestones)

**File:** `~/odoo/odoo19/odoo/addons/project/models/project_milestone.py`

### Class Signature

```python
class ProjectMilestone(models.Model):
    _name = 'project.milestone'
    _description = "Project Milestone"
    _inherit = ['mail.thread']  # Notifications on deadline changes
    _order = 'sequence, deadline, is_reached desc, name'
```

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `name` | Char | required | Milestone name. |
| `sequence` | Integer | `10` | Ordering. |
| `project_id` | Many2one (project.project) | from context | Parent project. `ondelete='cascade'`. Domain: `is_template=False`. Indexed. |
| `deadline` | Date | — | Target date. `tracking=True` (chatter notification on change). `copy=False`. |
| `is_reached` | Boolean | `False` | Reached flag. `copy=False`. When set, `reached_date` auto-computes to today. |
| `reached_date` | Date | computed | Date milestone was marked reached. |
| `task_ids` | One2many (project.task) | — | Tasks linked to this milestone. |
| `project_allow_milestones` | Boolean | computed | Whether project has milestones enabled. Searchable. |
| `is_deadline_exceeded` | Boolean | computed | `True` if `not is_reached AND deadline < today`. |
| `is_deadline_future` | Boolean | computed | `True` if `deadline > today`. |
| `task_count` | Integer | computed | Total linked tasks (group: `project.group_project_milestone`). |
| `done_task_count` | Integer | computed | Closed linked tasks (group: `project.group_project_milestone`). |
| `can_be_marked_as_done` | Boolean | computed | `not is_reached AND at least one task done AND no open tasks`. |

### Computed Logic (L4: Bulk vs Record-by-Record)

The `_compute_task_count` method uses `read_group` with `state:array_agg` to count both total and closed tasks in a single SQL query:
```python
all_and_done_task_count_per_milestone = {
    milestone.id: (count, sum(state in CLOSED_STATES for state in state_list))
    for milestone, count, state_list in self.env['project.task']._read_group(
        [('milestone_id', 'in', self.ids), ('allow_milestones', '=', True)],
        ['milestone_id'], ['__count', 'state:array_agg'],
    )
}
```

The `_compute_can_be_marked_as_done` has two code paths:
- **New records** (no IDs): uses Python `all()` on `task_ids.mapped('is_closed')`
- **Existing records**: uses SQL `read_group` with state aggregation for performance

### Display Name Enhancement

```python
def _compute_display_name(self):
    super()._compute_display_name()
    if self.env.context.get('display_milestone_deadline'):
        for milestone in self:
            if milestone.deadline:
                milestone.display_name = f"{milestone.display_name} - {format_date(...) }"
```

### `copy` Method (L4: Context-Based Milestone Mapping)

When copying milestones during project duplication, a `milestone_mapping` context dict maps old IDs to new IDs so task copies can reference the new milestone:

```python
def copy(self, default=None):
    # Called during project copy with milestone_mapping in context
    for old_ms, new_ms in zip(self, new_milestones):
        if old_ms.project_id.allow_milestones:
            milestone_mapping[old_ms.id] = new_ms.id  # stored in context by caller
```

---

## 5. project.task.recurrence (Recurring Tasks)

**File:** `~/odoo/odoo19/odoo/addons/project/models/project_task_recurrence.py`

### Class Signature

```python
class ProjectTaskRecurrence(models.Model):
    _name = 'project.task.recurrence'
    _description = 'Task Recurrence'
```

### Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `task_ids` | One2many (project.task) | — | All occurrences generated by this recurrence. `copy=False`. |
| `repeat_interval` | Integer | `1` | Repeat every N units. `> 0` enforced by constraint. |
| `repeat_unit` | Selection | `'week'` | day/week/month/year. |
| `repeat_type` | Selection | `'forever'` | forever/until. |
| `repeat_until` | Date | — | End date for limited recurrence. Must be `> today` if `repeat_type='until'`. |

### Recurrence Delta Calculation (L4: relativedelta)

```python
def _get_recurrence_delta(self):
    # relativedelta dynamically builds offset: relativedelta(days=N) or weeks=N etc.
    return relativedelta(**{f"{self.repeat_unit}s": self.repeat_interval})
```

### Occurrence Generation (`_create_next_occurrences` — L4: Full Flow)

Called by cron daily. For each recurring task:

1. **Check if occurrence should be created**:
   - `repeat_type != 'until'` → always create
   - OR `date_deadline` is None → create
   - OR `(date_deadline + delta) <= repeat_until` → create

2. **Create occurrence values** (`_create_next_occurrences_values`):
   - Uses `copy_data()` with `copy_project=True, active_test=False` context
   - Overrides: `priority = '0'`, `stage_id = project.type_ids[0]` (first stage)
   - **Date postponement**: `date_deadline += recurrence_delta`
   - **Subtasks**: Recursively copied with same recurrence_id

3. **Dependency resolution** (`_resolve_copied_dependencies`):
   - Creates `task_mapping` via `_create_task_mapping` (guaranteed same-index correspondence)
   - Remaps `depend_on_ids` and `dependent_ids` to new copied task IDs

4. **Inverse state** on original task's write triggers next occurrence creation only if original task is the last in the recurrence.

---

## 6. project.update (Project Status Updates)

**File:** `~/odoo/odoo19/odoo/addons/project/models/project_update.py`

### Class Signature

```python
class ProjectUpdate(models.Model):
    _name = 'project.update'
    _description = 'Project Update'
    _order = 'id desc'  # Newest first
    _inherit = ['mail.thread.cc', 'mail.activity.mixin']
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Update title. Tracked. |
| `status` | Selection | on_track/at_risk/off_track/on_hold/done. Required. Tracked. |
| `color` | Integer | Computed from `STATUS_COLOR` map. |
| `progress` | Integer | Progress percentage 0–100. Tracked. |
| `progress_percentage` | Float | `progress / 100`. |
| `user_id` | Many2one (res.users) | Author. Defaults to current user. |
| `description` | Html | Rich text content. Auto-populated from QWeb template `project.project_update_default_description`. |
| `date` | Date | Update date. Defaults to today. |
| `project_id` | Many2one (project.project) | Parent project. Domain: `is_template=False`. |
| `name_cropped` | Char | Truncated name >60 chars with "...". |
| `task_count` | Integer | Snapshot of project's total task count at creation time. |
| `closed_task_count` | Integer | Snapshot of closed task count at creation time. |
| `closed_task_percentage` | Integer | Computed from snapshots. |

### Default Values (L4: Template Rendering)

When creating an update:
- `progress` ← project's last update's progress (or 0 if first update)
- `status` ← last status (or `on_track` if last was `to_define`)
- `description` ← rendered QWeb template with milestone and profitability data
- `task_count`, `closed_task_count` ← current project counts snapshot

### Default Description Template Data

The `_get_template_values` method fetches:
1. **Milestone section**: milestones with upcoming deadlines, recently updated milestones (via `mail_tracking_value` SQL), newly created milestones
2. **Profitability section**: from `_get_profitability_values()` (requires `project_timesheet` module)

### ORM Overrides

- **`create`**: After insert, updates `project.last_update_id` (via sudo) and writes task count snapshots
- **`unlink`**: After delete, reassigns `last_update_id` to next-most-recent update

---

## 7. project.collaborator (External Collaborators)

**File:** `~/odoo/odoo19/odoo/addons/project/models/project_collaborator.py`

### Class Signature

```python
class ProjectCollaborator(models.Model):
    _name = 'project.collaborator'
    _description = 'Collaborators in project shared'
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `project_id` | Many2one (project.project) | Project. Domain: `privacy_visibility='portal'` and `is_template=False`. Readonly after creation. |
| `partner_id` | Many2one (res.partner) | Collaborator partner. Readonly after creation. |
| `partner_email` | Char (related) | From partner email. |
| `limited_access` | Boolean | `False` = can see all project tasks. `True` = only assigned tasks. |

### Constraint

```python
_unique_collaborator = models.Constraint(
    'UNIQUE(project_id, partner_id)',
    'A collaborator cannot be selected more than once...',
)
```

### Portal Rule Toggle (L4: Lazy Feature Activation)

```python
def create(self, vals_list):
    collaborator = self.env['project.collaborator'].search([], limit=1)
    project_collaborators = super().create(vals_list)
    if not collaborator:  # First ever collaborator
        self._toggle_project_sharing_portal_rules(True)

def unlink(self):
    res = super().unlink()
    collaborator = self.env['project.collaborator'].search([], limit=1)
    if not collaborator:  # Last collaborator deleted
        self._toggle_project_sharing_portal_rules(False)
```

The toggle activates:
1. `access_project_sharing_task_portal` — `ir.model.access` record granting portal users read on `project.task`
2. `project_task_rule_portal_project_sharing` — `ir.rule` allowing portal users to access tasks when project is `portal`/`invited_users` and collaborator exists

This lazy-activation pattern avoids granting unnecessary access when the feature is unused.

---

## 8. project.project.stage (Project Lifecycle Stages)

**File:** `~/odoo/odoo19/odoo/addons/project/models/project_project_stage.py`

### Class Signature

```python
class ProjectProjectStage(models.Model):
    _name = 'project.project.stage'
    _description = 'Project Stage'
    _order = 'sequence, id'
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `active` | Boolean | Archival. Deactivating a stage archives all projects in that stage. |
| `sequence` | Integer | Ordering. |
| `name` | Char | Stage name. Translateable. |
| `mail_template_id` | Many2one (mail.template) | Email sent when project enters this stage. |
| `fold` | Boolean | Folded in kanban view. Projects in folded stages are considered closed. |
| `company_id` | Many2one (res.company) | Stage is company-specific. Changing stage company is blocked if any project in stage has a different company. |
| `color` | Integer | Stage color. |

### Key Behavior: Company Enforcement on Write

```python
def write(self, vals):
    if vals.get('company_id'):
        # Block if any project in this stage has a DIFFERENT company
        project = self.env['project.project'].search([
            '&', ('stage_id', 'in', self.ids), ('company_id', '!=', vals['company_id'])
        ], limit=1)
        if project:
            raise UserError("Not able to switch the company...")
    if 'active' in vals and not vals['active']:
        self.env['project.project'].search([('stage_id', 'in', self.ids)]).write({'active': False})
```

---

## 9. project.task.stage.personal (Personal Stage State)

**File:** `~/odoo/odoo19/odoo/addons/project/models/project_task_stage_personal.py`

### Class Signature

```python
class ProjectTaskStagePersonal(models.Model):
    _name = 'project.task.stage.personal'
    _table = 'project_task_user_rel'  # Same table as task.user_ids M2M
    _rec_name = 'stage_id'
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `task_id` | Many2one (project.task) | Task. `ondelete='cascade'`. |
| `user_id` | Many2one (res.users) | User. `ondelete='cascade'`. |
| `stage_id` | Many2one (project.task.type) | Personal stage for this user/task pair. `ondelete='set null'`. Domain: `user_id=user_id`. |

### Constraint

```python
_project_personal_stage_unique = models.Constraint(
    'UNIQUE(task_id, user_id)',
    'A task can only have a single personal stage per user.',
)
```

**L4 — Table Sharing**: This model shares the same table (`project_task_user_rel`) as the `user_ids` M2M on `project.task`. The `stage_id` column is distinct from `column2='user_id'` used by the M2M, so both use cases coexist. `_populate_missing_personal_stages()` creates records for tasks where the pair is missing.

---

## 10. project.role (Project Roles for Template Dispatching)

**File:** `~/odoo/odoo19/odoo/addons/project/models/project_role.py`

### Class Signature

```python
class ProjectRole(models.Model):
    _name = 'project.role'
    _description = 'Project Role'
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `active` | Boolean | Active flag. |
| `name` | Char | Role name (required, translateable). |
| `color` | Integer | Random color 1–11 for UI. |
| `sequence` | Integer | Ordering. |

Used in project templates: tasks can have `role_ids` pointing to project roles. When creating a project from template, `role_to_users_mapping` maps roles to actual employees, who are then added to `user_ids` on matching tasks.

---

## 11. project.tags (Shared Tags)

**File:** `project_tags.py`

### Fields

| Field | Type |
|-------|------|
| `name` | Char (required, translateable) |
| `color` | Integer |

Used by both `project.project` and `project.task` via `tag_ids` Many2many.

---

## 12. Extensions to Other Models

### res.partner Extension

**File:** `res_partner.py`

| Field | Type | Description |
|-------|------|-------------|
| `project_ids` | One2many | Projects where partner is customer. |
| `task_ids` | One2many | Tasks where partner is customer. |
| `task_count` | Integer | Total tasks across all child contacts. |

**L4 — Recursive Partner Counting**:
```python
def _compute_task_count(self):
    # Uses read_group on all child partners
    # For each parent/child chain, aggregates counts upward
    while partner:
        if partner.id in self_ids:
            partner.task_count += count
        partner = partner.parent_id
```

**Constraints**:
- `_ensure_same_company_than_projects`: Partner's company must match all its projects' companies
- `_ensure_same_company_than_tasks`: Partner's company must match all its tasks' companies

**`action_view_tasks`**: Opens filtered task list for partner and all child contacts.

### res.users Extension

**File:** `res_users.py`

| Field | Type | Description |
|-------|------|-------------|
| `favorite_project_ids` | Many2many (project.project) | Projects user has favorited. Relation: `project_favorite_user_rel`. |

**`_onboard_users_into_project`** (L4: User Creation Hook):
On new internal user creation, automatically creates the 7 default personal task stages in the user's language.

```python
def _onboard_users_into_project(self, users):
    # Creates personal stages for all new internal users
    # Skips portal users (share=True)
    # Uses user.lang for translated stage names
```

### account.analytic.account Extension

**File:** `account_analytic_account.py`

| Field | Type | Description |
|-------|------|-------------|
| `project_ids` | One2many | Projects linked to this analytic account. |
| `project_count` | Integer | Count (computed via read_group). |

**`@api.ondelete` — Deletion Protection**:
```python
def _unlink_except_existing_tasks(self):
    # Blocks deletion of analytic account if any project linked to it has tasks
    if self.env['project.task'].search_count([('project_id.account_id', 'in', self.ids)], limit=1):
        raise UserError("...remove existing tasks first...")
```

### digest.digest Extension

**File:** `digest_digest.py`

| Field | Type | Description |
|-------|------|-------------|
| `kpi_project_task_opened` | Boolean | Toggle for open task KPI in digest emails. |
| `kpi_project_task_opened_value` | Integer | Count of non-folded tasks in projects. `additional_domain`: `stage_id.fold=False`. |

### ir.ui.menu Extension

**File:** `ir_ui_menu.py`

- Non-managers don't see the rating menu (`rating_rating_menu_project`)
- Users with `group_project_stages` see a different menu hierarchy

### mail.message Extension

**File:** `mail_message.py`

| Index | Definition |
|-------|-----------|
| `_date_res_id_id_for_burndown_chart` | `("(date, res_id, id) WHERE model = 'project.task' AND message_type = 'notification'")` |

Used by the burndown chart report for efficient WMS window function queries.

---

## Security & Access Control (L4: Complete)

### Security Groups

| Group | XML ID | Access |
|-------|--------|--------|
| Project User | `project.group_project_user` | Create/edit own tasks and projects |
| Project Manager | `project.group_project_manager` | Full access, delete, manage stages, view profitability |
| Project Stages | `project.group_project_stages` | Manage project lifecycle stages |
| Project Milestone | `project.group_project_milestone` | View milestone task counts |
| Project Task Dependencies | `project.group_project_task_dependencies` | Manage blocking dependencies |
| Project Recurring Tasks | `project.group_project_recurring_tasks` | Manage recurring tasks |

**L4 — Implied Group Pattern**:
`base.group_user` has `group_project_user` implied. The feature toggle fields (`allow_task_dependencies`, `allow_milestones`, `allow_recurring_tasks`) dynamically add/remove their respective groups from `base.group_user` as projects enable/disable those features.

### Record Rules

- Tasks inherit project privacy visibility through `project_privacy_visibility`
- Tasks without project (private) only visible to their assignees (`user_ids`)
- Archived projects/tasks hidden by default (`active_test` context)
- Portal access gated by collaborator record + access token

### Project Sharing Portal Rules (L4: Lazy Activation)

Two ir.model.access / ir.rule records are **deactivated by default** and only enabled when the first collaborator is added:
1. `access_project_sharing_task_portal` — grants portal read on `project.task`
2. `project_task_rule_portal_project_sharing` — ir.rule allowing portal task access

### Portal User Access (L4: Field-Level)

Portal users can only:
- **Read**: 45 specific fields (no description, dates, hours, etc.)
- **Write**: 17 specific fields (name, stage, priority, tags, state, etc.)
- **Create**: tasks in portal-accessible projects
- **Not**: modify company, analytic account, assign internal users, create subtasks

---

## Cron Jobs

| Cron | Model | Frequency | Action |
|------|-------|-----------|--------|
| `project.task.recurrence` (ir_cron_data.xml) | `project.task.recurrence` | Daily | Calls `_create_next_occurrences` to generate new occurrences |
| `_send_rating_all` | `project.task.type` | Daily (via `ir.cron`) | Sends periodic rating requests for stages with `rating_active=True` and `rating_status='periodic'` where `rating_request_deadline <= now` |

---

## Performance Considerations (L4 Summary)

| Operation | Strategy |
|----------|---------|
| Task counting | `_read_group` single SQL `GROUP BY` — O(1) DB round trip |
| Milestone task counting | `state:array_agg` in read_group — single query for all states |
| Closed/dependency counting | SQL `read_group` with `state:array_agg` avoids N queries |
| Subtask tree retrieval | Recursive CTE `WITH RECURSIVE` — single query, any depth |
| Milestone exceeded search | Raw SQL subquery — avoids ORM self-join |
| Collaborator count | Only computed for `portal`/`invited_users` projects |
| Template/favorite ordering | Custom `_order_field_to_sql` with `INNER JOIN` in SQL ORDER BY |
| View cache key | Appends `user._is_portal()` to invalidate cache on access mode change |
| Fields_get for portal | ORM cache (`@ormcache` on `_portal_accessible_fields`) |
| Rating deadline recompute | `cr.commit()` after each stage in cron to avoid long transactions |

---

## Odoo 18 → 19 Changes (L4)

| Area | Change |
|------|--------|
| Task assignees | `user_id` (single) replaced with `user_ids` (many2many) across the board |
| Personal stages | `project.task.type` gained `user_id` field; `project.task.stage.personal` uses same table as `user_ids` M2M |
| State field | Now `store=True` with `recursive=True` — state is persisted and recomputes recursively |
| Privacy visibility | New values `followers` and `invited_users` replace older visibility model |
| Project sharing | Collaborator `limited_access` field added for fine-grained portal task access |
| Template dispatching | Role-based task assignment (`role_ids`) added for template-to-project creation |
| Stage rotting | `rotting_threshold_days` added to stages for proactive stale-task detection |
| Company consistency | Stricter multi-level validation: task ↔ partner ↔ project ↔ analytic account |
| Accessibility | `display_in_project_header` field removed; replaced by computed visibility logic |

---

## Model Relationships Diagram

```
project.project
├── account_id ──────────────────────► account.analytic.account
│                                      (project_ids ←── One2many)
│
├── tasks (task_ids) ───────────────► project.task
│   │                                (child_ids ←── One2many, parent_id)
│   │                                (depend_on_ids ↔ dependent_ids)
│   │                                (recurrence_id ←── One2many)
│   │                                (milestone_id ←── Many2one)
│   │                                (stage_id ─────────► project.task.type)
│   │                                (personal_stage_id ──► project.task.stage.personal)
│   │
│   └── type_ids ───────────────────► project.task.type
│       (shared across projects)
│
├── milestone_ids ───────────────────► project.milestone
│                                    (task_ids ←── One2many)
│
├── update_ids ─────────────────────► project.update
│   (last_update_id ──── Many2one)
│
├── collaborator_ids ────────────────► project.collaborator
│                                    (partner_id ────► res.partner)
│
├── stage_id ────────────────────────► project.project.stage
│
├── partner_id ──────────────────────► res.partner
│   (task_ids, project_ids ─── One2many from res.partner)
│
└── favorite_user_ids ───────────────► res.users
    (favorite_project_ids ←── Many2many from res.users)

project.task.type
├── project_ids ─────────────────────► project.project (shared stages)
└── user_id ────────────────────────► res.users (personal stages)
    └── stage_id ──────────────────► project.task.stage.personal

project.collaborator
└── project_id ─────────────────────► project.project
     (partner_id ──────────────────► res.partner)

project.milestone
└── project_id ─────────────────────► project.project
```

---

## Common Development Patterns

### Task Count Helper (Generic)
```python
def __compute_task_count(self, count_field, additional_domain=None):
    domain = Domain('project_id', 'in', self.ids) & Domain('is_template', '=', False)
    if additional_domain:
        domain &= Domain(additional_domain)
    tasks_count = dict(ProjectTask._read_group(domain, ['project_id'], ['__count']))
    for project in self:
        project.update({count_field: tasks_count.get(project, 0)})
```

### Milestone Task Count (Bulk Read-Group)
```python
all_and_done_task_count_per_milestone = {
    milestone.id: (count, sum(state in CLOSED_STATES for state in state_list))
    for milestone, count, state_list in self._read_group(
        domain, ['milestone_id'], ['__count', 'state:array_agg']
    )
}
```

### Personal Stage Initialization
```python
def _populate_missing_personal_stages(self):
    # Ensures each (task, user) pair has a project.task.stage.personal record
    # Creates default stages for user if none exist
```

### Recursive Subtask Tree (Single Query)
```python
WITH RECURSIVE task_tree AS (
    SELECT id, id FROM project_task WHERE id IN %(ids)s
    UNION ALL
    SELECT t.id, tree.supertask_id
    FROM project_task t JOIN task_tree tree ON tree.id = t.parent_id
)
SELECT supertask_id, ARRAY_AGG(id) FROM task_tree WHERE id != supertask_id GROUP BY supertask_id
```

### Dynamic Group Management
```python
def _check_project_group_with_field(self, field_name, group_name):
    # Returns True (group added), False (group removed), None (no change)
    has_project_field_set = bool(self.search_count([(field_name, '=', True)], limit=1))
    if not has_user_group and has_project_field_set:
        base_group_user.write({'implied_ids': [Command.link(group.id)]})
        return True
    elif has_user_group and not has_project_field_set:
        base_group_user.write({'implied_ids': [Command.unlink(group.id)]})
        return False
```

---

## Key Integrations

| Module | Integration Point |
|--------|-------------------|
| `project_timesheet` | `timesheet_ids` on task (One2many to `account.analytic.line`); `planned_hours`/`remaining_hours` |
| `sale_project` | `sale_line_id` on task for service/SOL tracking |
| `project_purchase` | Tasks can generate purchase requests linked to analytic account |
| `rating` | `rating_ids` via `rating.mixin`; parent rating aggregated on project |
| `resource` | `resource_calendar_id` for working time calculations; `_get_unusual_days` |
| `portal` | `access_token`/`access_url` via `portal.mixin`; collaborator sharing |
| `mail` | Email gateway via `alias_id`; chatter; CC handling; template notifications |
| `html_editor` | Description field with history (`html.field.history.mixin`) |
| `analytic` | `analytic_account_id` on project; plan fields mixin |
| `digest` | `kpi_project_task_opened` in digest emails |

---

## Module Initialization Order (L1)

**File:** `project/models/__init__.py`

The load order is **critical** due to inheritance dependencies:

```python
# Order matters! project_task_stage_personal loaded BEFORE project_project and project_milestone
from . import project_task_stage_personal   # 1st: shared table definition
from . import project_milestone              # 2nd: depends on task stages
from . import project_project                 # 3rd: project references milestones
from . import project_task                   # 4th: task references project, stages, recurrence
```

**Why this matters:**
- `project_task_stage_personal` defines `_table = 'project_task_user_rel'` — the same physical table used by `project.task.user_ids` (M2M). Loading it first ensures the table exists before other models reference it.
- `project_project` and `project_milestone` have `@api.depends` on fields defined in `project_task` (e.g., `allow_milestones` is a related field from `project_id`). Loading `project_task` after ensures all referenced fields exist.
- `project_task_recurrence` is loaded before `project_task` because `project.task` has a `recurrence_id` Many2one field pointing to it.

---

## Wizards (L2-L3)

**Directory:** `project/wizard/`

### Initialization Chain

```python
# __init__.py
from . import project_project_stage_delete
from . import project_task_share_wizard
from . import project_task_type_delete
from . import project_share_wizard
from . import project_share_collaborator_wizard
from . import project_template_create_wizard
from . import portal_share
```

### 13. project.share.wizard (Project Sharing UI)

**File:** `project/wizard/project_share_wizard.py`

```python
class ProjectShareWizard(models.TransientModel):
    _name = 'project.share.wizard'
    _inherit = ['portal.share']  # Inherits portal invite logic
    _description = 'Project Sharing'
```

| Field | Type | Description |
|-------|------|-------------|
| `share_link` | Char | Public read-only access link |
| `collaborator_ids` | One2many | Collaborator entries (from `project.share.collaborator.wizard`) |
| `existing_partner_ids` | Many2many (compute) | Partners already collaborators |

**L3 — Share Wizard Logic:**
1. **`default_get`**: Pre-populates existing collaborators and portal followers as read-only entries
2. **`create`**: Syncs collaborator changes:
   - Adds new collaborators (creates `project.collaborator` records)
   - Updates access mode changes (`limited_access` toggle)
   - Removes collaborators no longer in wizard
   - Manages follower subscriptions
3. **`action_share_record`**: Triggers invitation email flow (creates portal users for new collaborators if needed)
4. **`action_send_mail`**: Sets project `privacy_visibility = 'portal'`, sends invitations

### 14. project.share.collaborator.wizard (Collaborator Line Item)

**File:** `project/wizard/project_share_collaborator_wizard.py`

```python
class ProjectShareCollaboratorWizard(models.TransientModel):
    _name = 'project.share.collaborator.wizard'
```

| Field | Type | Description |
|-------|------|-------------|
| `parent_wizard_id` | Many2one | Parent `project.share.wizard` |
| `partner_id` | Many2one (res.partner) | Collaborator partner |
| `access_mode` | Selection | `read` / `edit_limited` / `edit` |
| `send_invitation` | Boolean | Send invite email (computed, default=True) |

**Access Mode Hierarchy:**
| Mode | What it allows |
|------|---------------|
| `read` | View-only access to followed tasks |
| `edit_limited` | Edit only tasks they follow in Kanban |
| `edit` | Full edit access to all project tasks in Kanban + can follow/unfollow |

### 15. task.share.wizard (Task Sharing UI)

**File:** `project/wizard/project_task_share_wizard.py`

```python
class TaskShareWizard(models.TransientModel):
    _name = 'task.share.wizard'
    _inherit = ['portal.share']
```

Minimal wizard: inherits portal share logic and adds `task_id` / `project_privacy_visibility` references. Shares individual tasks via `portal.share`.

### 16. project.template.create.wizard (Template → Project)

**File:** `project/wizard/project_template_create_wizard.py`

```python
class ProjectTemplateCreateWizard(models.TransientModel):
    _name = 'project.template.create.wizard'
    _description = 'Project Template create Wizard'
```

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | New project name |
| `date_start` | Date | Project start date |
| `date` | Date | Project end date |
| `alias_name` | Char | Email alias prefix |
| `alias_domain_id` | Many2one | Email alias domain |
| `template_id` | Many2one (project.project) | Source template |
| `role_to_users_ids` | One2many | Role → Employee mapping |

**L3 — Template Creation Flow:**
1. Wizard maps template roles to actual employees
2. `_create_project_from_template` calls `template_id.action_create_from_template()`
3. Role-to-user mapping is resolved: tasks with matching `role_ids` get assigned employees added to `user_ids`
4. After dispatch, `role_ids` are cleared from all copied tasks

```python
class ProjectTemplateRoleToUsersMap(models.TransientModel):
    _name = 'project.template.role.to.users.map'
    # Maps project.role → res.users for template dispatching
```

### 17. project.task.type.delete.wizard (Stage Deletion Safety)

**File:** `project/wizard/project_task_type_delete.py`

```python
class ProjectTaskTypeDeleteWizard(models.TransientModel):
    _name = 'project.task.type.delete.wizard'
```

| Field | Type | Description |
|-------|------|-------------|
| `project_ids` | Many2many (project.project) | Affected projects |
| `stage_ids` | Many2many (project.task.type) | Stages to delete |
| `tasks_count` | Integer | Tasks in these stages |
| `stages_active` | Boolean | All stages are active |

**Actions:**
- `action_archive`: Archives all tasks in the stages + deactivates the stages
- `action_unarchive_task`: Unarchives tasks
- `action_confirm`: Deactivates tasks + stages
- `action_unlink`: Hard-deletes the stage records

### 18. project.project.stage.delete.wizard (Project Stage Deletion)

**File:** `project/wizard/project_project_stage_delete.py`

```python
class ProjectProjectStageDeleteWizard(models.TransientModel):
    _name = 'project.project.stage.delete.wizard'
```

| Field | Type | Description |
|-------|------|-------------|
| `stage_ids` | Many2many (project.project.stage) | Stages to delete |
| `projects_count` | Integer | Projects in these stages |
| `stages_active` | Boolean | All stages are active |

**Actions:** Same pattern as task stage delete wizard — archive or unlink stages, cascading to projects.

### 19. portal.share Extension (Task Subscribe on Share)

**File:** `project/wizard/portal_share.py`

```python
class PortalShare(models.TransientModel):
    _inherit = 'portal.share'

    def action_send_mail(self):
        result = super().action_send_mail()
        # Subscribe partners when sharing a task
        if self.res_model == 'project.task':
            self.resource_ref.message_subscribe(partner_ids=self.partner_ids.ids)
        return result
```

Minimal but important: ensures that when a task is shared via portal, the partner is automatically subscribed to task notifications.

---

## L3: Cross-Module Integrations

### Project ↔ Timesheet (AAL — Account Analytic Line)

**Module:** `project_timesheet` (adds timesheet tracking to tasks)

| Field Added to project.task | Type | Description |
|----------------------------|------|-------------|
| `timesheet_ids` | One2many (`account.analytic.line`) | Time entries logged against this task |
| `timesheet_count` | Integer | Count of timesheet lines |
| `effective_hours` | Float | Sum of validated timesheet hours |
| `remaining_hours` | Float | `allocated_hours - effective_hours` |
| `progress` | Float | `effective_hours / allocated_hours * 100` |

**L3 — Timesheet Aggregation Pattern:**
```python
# In project_timesheet: efficient count via read_group
timesheet_count = self.env['account.analytic.line'].search_count([
    ('task_id', 'in', self.ids)
])
# Or via SQL for large datasets:
# SELECT task_id, COUNT(*) FROM account_analytic_line WHERE task_id IN (...) GROUP BY task_id
```

**Timesheet timer** (`_get_timesheet_timer_dict`): Returns current timer state for the task, enabling the Start/Stop timer button in the UI. Project-level timesheet aggregation uses `account_id` from `project_id` to link lines.

### Project ↔ Sale (Task Invoicing)

**Module:** `sale_project` + `sale_timesheet`

| Field | Model | Description |
|-------|-------|-------------|
| `sale_line_id` | `project.task` | Linked SOL (service line) |
| `sale_order_id` | `project.task` (related) | Parent SO |
| `task_invoice_type` | `project.task` | `custom_rate` / `manually` / `ats_fixed` |

**L3 — Invoice Trigger Flow:**
1. When a SOL with `service_type = 'task'` is confirmed → creates a task in the linked project
2. Timesheet entries validated against the task → automatically creates `account.move.line` (invoiceable)
3. If `invoice_policy = 'delivery'` → invoiced when timesheet is validated
4. If `invoice_policy = 'order'` → invoiced at SO confirmation

**Failure mode — no billing rule:**
- Tasks without `sale_line_id` are not invoiced
- `remaining_hours` shows full `allocated_hours` (no deduction)
- Sale line unlinking does NOT cascade-delete tasks

### Project ↔ Purchase (Purchase Orders on Tasks)

**Module:** `project_purchase` (EE in older versions, CE in Odoo 19+)

| Feature | Description |
|---------|-------------|
| Purchase Request | User requests materials/PO from a task |
| `purchase_order_id` | Links task to PO |
| `purchase_order_line_id` | Links task line to PO line |
| `purchase_request_id` | Links task to purchase request |

**L3 — PO Creation from Task:**
- A "Request Purchase" button on tasks opens a wizard to create a purchase request or PO
- The task is linked to the resulting `purchase.order.line`
- When the PO is received, the task's material usage is tracked
- Analytic account from `project_id.account_id` is used on PO lines

### Project ↔ Stock (Materials)

**Module:** `project_stock` + `project_stock_account`

| Feature | Description |
|---------|-------------|
| Material tracking | Track material consumed by task |
| `stock_move_ids` | Stock moves linked to task |
| `stock_valuation` | Cost of materials consumed |
| `qty_delivered` | Materials delivered to task |

**L3 — Material Flow:**
1. Product added to task as material (via `stock.move` wizard)
2. Stock move creates `stock.picking` for delivery
3. When done, `stock.quant` is updated
4. Valuation flows through `project_id.account_id` analytic account

**L3 — Failure Mode (no analytic account):**
- `account_id` is optional on `project.project` (`ondelete='set null'`)
- Without an analytic account:
  - Profitability tracking is **not available** (no `analytic_account_balance`)
  - Project cannot be linked to a `sale.order` for billing
  - Purchase orders cannot auto-link to project's costs
  - `_get_profitability_values()` returns empty `billed` / `expense` sections
  - The "Profitability" tab still renders but shows zero values with "No analytic account configured" hint

---

## L3: Override Patterns

### `_compute_task_count` Pattern

```python
def __compute_task_count(self, count_field='task_count', additional_domain=None):
    """
    Generic counter using read_group aggregation.
    Uses Domain helper for safe SQL construction.
    """
    domain = Domain('project_id', 'in', self.ids) & Domain('is_template', '=', False)
    if additional_domain:
        domain &= Domain(additional_domain)
    ProjectTask = self.env['project.task'].with_context(
        active_test=any(project.active for project in self)
    )
    tasks_count_by_project = dict(
        ProjectTask._read_group(domain, ['project_id'], ['__count'])
    )
    for project in self:
        project.update({count_field: tasks_count_by_project.get(project, 0)})
```

Key points:
- Uses `Domain` helper (safe SQL construction, not string concatenation)
- Forwards `active_test` context: if ANY project in self is active, show active tasks
- Single SQL query regardless of how many projects are in self (avoids N queries)
- Validates `count_field` name against actual declared count fields

### `_get_timesheet_timer_dict` Pattern

```python
def _get_timesheet_timer_dict(self):
    """Returns current timesheet timer state for the current user."""
    # Queries account.analytic.line for running timer (no stop datetime)
    # Returns: {task_id: {'timer_start': datetime, 'timer_hours': float}}
    # Used by the web client to display live timer in the task header
```

### Feature Toggle Dynamic Group Pattern

```python
def _check_project_group_with_field(self, field_name, group_xml_id):
    """
    Dynamically add/remove implied groups from base.group_user
    based on whether ANY project has the feature enabled.

    Returns: True (group added), False (group removed), None (no change)
    """
    has_project_field_set = bool(
        self.search_count([(field_name, '=', True)], limit=1)
    )
    base_group = self.env.ref('base.group_user')
    implied_group = self.env.ref(group_xml_id)

    has_user_group = has_project_field_set and implied_group in base_group.implied_ids

    if not has_user_group and has_project_field_set:
        base_group.write({'implied_ids': [Command.link(implied_group.id)]})
        return True
    elif has_user_group and not has_project_field_set:
        base_group.write({'implied_ids': [Command.unlink(implied_group.id)]})
        return False
```

This pattern keeps permissions synchronized with actual feature usage — no admin action needed when projects enable/disable features.

---

## L3: Workflow Triggers

### Task Creation → Assignment → Completion → Invoicing Flow

```
User creates task
    │
    ├── project_id.auto_assign_partner_as_follower() [if partner set]
    │
    ├── Stage email template triggered (if configured)
    │
    ▼
Assignee set (user_ids)
    │
    ├── date_assign = now
    ├── _populate_missing_personal_stages() → project.task.stage.personal
    │
    ▼
Timesheet logged (project_timesheet)
    │
    ├── account.analytic.line created
    ├── effective_hours += line.unit_amount
    ├── remaining_hours = allocated_hours - effective_hours
    │
    ▼
Task closed (state → '1_done')
    │
    ├── date_end = now
    ├── If has sale_line_id → invoiceable amount finalized
    ├── If last occurrence → recurrence creates next task
    │
    ▼
Rating sent (if stage.rating_active=True)
    │
    ├── email sent via rating_template_id
    │
    ▼
Customer rates (rating_apply)
    │
    ├── If stage.auto_validation_state:
    │     rating >= 4 → state = '03_approved'
    │     rating < 4  → state = '02_changes_requested'
    │
    ▼
Invoice created (sale_project)
    │
    ├── Delivered quantity = effective_hours
    └── account.move created from SOL
```

### Project Creation → Milestone Setup → Status Update Flow

```
Project created
    │
    ├── account_id created (optional) via analytic.plan.fields.mixin
    ├── Stages set (type_ids)
    │
    ▼
Milestone created
    │
    ├── Linked to project_id
    ├── deadline set → tracking notification on change
    │
    ▼
Tasks linked to milestone
    │
    ├── Task completion updates milestone.can_be_marked_as_done
    ├── When all tasks done → can mark milestone.reached = True
    │
    ▼
Project Update created (status report)
    │
    ├── progress snapshot taken
    ├── last_update_status set (on_track/at_risk/off_track/on_hold)
    ├── milestone summary embedded in description
    │
    ▼
Milestone deadline exceeded
    │
    ├── is_milestone_deadline_exceeded = True
    ├── Warning displayed in project dashboard
```

---

## L3: Failure Modes

### Failure Mode 1: Project Without Analytic Account

```python
# project_project.py — field definition
account_id = fields.Many2one(
    'account.analytic.account',
    copy=False,
    ondelete='set null',  # Nulls out instead of blocking deletion
)
analytic_account_balance = fields.Monetary(related="account_id.balance")
```

**Impact:**
| Feature | Behavior without account_id |
|---------|---------------------------|
| Profitability tab | Shows 0.0 for all sections |
| Sale order linking | Cannot link SOL → project |
| Purchase cost tracking | POs won't post to project's costs |
| Task billing | No delivered quantity from timesheets |

**Fix:** Either create an analytic account or acknowledge that cost tracking won't work.

### Failure Mode 2: Personal Stage for Deleted User

```python
# res_users.py — personal stage creation hook
def _onboard_users_into_project(self, users):
    # Creates 7 default stages per new internal user
    for user in internal_users:
        vals = self.env["project.task"]._get_default_personal_stage_create_vals(user.id)
        # Creates: Inbox, Today, This Week, This Month, Later, Done, Cancelled
```

**Problem:** If user is deleted:
- Their `project.task.type` records remain orphaned (user_id still set)
- `project.task.stage.personal` records reference the deleted user
- Tasks with personal stages for deleted users can't auto-reassign

**Fix:** Delete cascade removes personal stages via `ondelete='cascade'` on `user_id`.

### Failure Mode 3: Recurring Task as Subtask

```python
# project_task.py — constraint
_recurring_task_has_no_parent = models.Constraint(
    'CHECK (NOT (recurring_task IS TRUE AND parent_id IS NOT NULL))',
    'You cannot convert this task into a sub-task because it is recurrent.',
)
```

**Why it fails:** Recurring task occurrences share the same `recurrence_id`. Making a recurring task a subtask of a non-recurring parent creates an inconsistent tree.

**Fix:** Convert to non-recurring first, then make it a subtask.

### Failure Mode 4: Cyclic Task Dependencies

```python
# project_task.py
@api.constrains('depend_on_ids')
def _check_no_cyclic_dependencies(self):
    self._has_cycle('depend_on_ids')  # Raises if cycle detected
```

**Why it fails:** A → B → C → A creates an infinite dependency loop where no task can progress.

**Fix:** Remove one dependency to break the cycle.

### Failure Mode 5: Company Mismatch Cascade

```python
# project_task.py — constraint
@api.constrains('company_id', 'partner_id')
def _ensure_company_consistency_with_partner(self):
    # Raises if task company != partner company (when partner has company)
```

**Impact chain:**
```
Company changed on project
    │
    ├── project.company_id ≠ project.partner_id.company_id → blocked
    │
    └── If analytic account has lines OR multiple projects → company change blocked
         │
         └── Even unlinking analytic account is blocked if tasks exist
```

**Fix:** Move all tasks to another project before changing company.

---

## L4 ALERT: task_properties — JSON-Based Task Properties (Odoo 19)

**Field Definition:**

```python
# project_project.py — schema definition (on project level)
task_properties_definition = fields.PropertiesDefinition('Task Properties')
# Stored in ir.model.fields as a JSON schema

# project_task.py — actual properties (on task level)
task_properties = fields.Properties(
    'Properties',
    definition='project_id.task_properties_definition',
    copy=True,
)
```

### What It Does

`task_properties` is an Odoo 19 JSON-based field that lets each project define custom structured data fields for its tasks — without code changes or Studio. Think of it as a dynamic schema per project.

**PropertiesDefinition schema** supports these property types:
| Type | Description |
|------|-------------|
| `char` | Single-line text |
| `text` | Multi-line text |
| `integer` | Whole number |
| `float` | Decimal number |
| `boolean` | True/False |
| `date` | Date picker |
| `datetime` | Date+time picker |
| `selection` | Dropdown from options |
| `many2one` | Link to any model |
| `tags` | Multi-select tags |
| `separator` | UI section divider |
| `header` | Bold section header |

### How Projects Define Them

Administrators configure task properties through the project form:
1. Settings tab → Task Properties → Add property
2. Choose name, type, and optional selection options
3. Properties are stored as a JSON schema in `task_properties_definition`

### How Tasks Use Them

Each task's `task_properties` field:
- Inherits the schema from its project's `task_properties_definition`
- Stores values as JSON: `{"1": {"value": "Custom Value"}, "2": {"value": 42}}`
- Is copied when task is duplicated (`copy=True`)
- Is NOT copied to recurring task occurrences (the recurrence creates fresh copies)

### Why It Matters (L4)

1. **Studio-compatible**: Studio uses `task_properties_definition` to let admins define custom fields in the UI
2. **Project-scoped schema**: Different projects can have different property sets
3. **Computed properties possible**: Via `definition_mutable=True` (used by Studio)
4. **No migration needed**: Stored as JSON, flexible schema evolution
5. **Search/groupby support**: Odoo 19+ allows searching on Properties fields in list views

### Performance Caveat (L4)

Properties are stored as a single JSON column. Searching across all tasks for a property value requires:
```sql
-- Full table scan unless proper indexing is in place
SELECT * FROM project_task WHERE task_properties @> '{"1": {"value": "X"}}';
```
**Recommendation**: For high-volume searches on property values, consider computed stored fields or dedicated columns instead.

---

## L4: Performance — Task Computation Overhead

### Hot Spots Identified

| Operation | Complexity | Strategy |
|-----------|-----------|----------|
| `task_count` / `open_task_count` | O(1) per project | `_read_group` single SQL |
| Subtask tree (recursive CTE) | O(depth) but single query | `WITH RECURSIVE` |
| `depend_on_count` | O(1) per task | `state:array_agg` in read_group |
| `task_properties` serialization | O(1) per task | JSON column, no decomposition |
| Personal stage lookup | O(1) per task | B-tree index on `(task_id, user_id)` |
| Milestone task count | O(milestones) | `read_group` with `state:array_agg` per milestone |
| Project kanban (many projects) | O(n) tasks loaded | `prefetch_id` batching + `display_in_project` filter |
| Portal fields_get | Cached | `@ormcache` on `_portal_accessible_fields` |

### N+1 Risk Areas

**Task list view without `prefetch_fields`:**
```python
# RISKY: Each task triggers a read for project_id.partner_id
for task in tasks:
    print(task.project_id.partner_id.name)  # N queries
# FIX: tasks.mapped('project_id.partner_id.name') — single query
```

**Subtask counts per task in kanban:**
```python
# RISKY: subtask_count computed per task
for task in kanban_tasks:
    task.subtask_count  # N queries
# FIX: Use read_group on subtask tree, or batch in Python
```

### Caching Strategies

| Field | Cache | Key |
|--------|-------|-----|
| `portal_accessible_fields` | ORM cache (`@ormcache`) | `(model_name, is_portal)` |
| `favorite_project_ids` | Record cache | Per-user lookup |
| `personal_stage_id` | Record cache | `(task_id, user_id)` |
| `stage_id` | Record cache | Per-task kanban render |

---

## L4: Version Change — Odoo 18 → 19 Project Sharing

### Breaking Changes

| Area | Odoo 18 | Odoo 19 | Impact |
|------|---------|---------|--------|
| **Assignees** | `user_id` (single Many2one) | `user_ids` (Many2many) | All task assign code must handle multi-assignee |
| **Personal stages** | No dedicated model | `project.task.stage.personal` + `user_id` on `project.task.type` | Personal kanban columns now per-user |
| **Privacy visibility** | `public` / `invited` | `followers` / `invited_users` / `employees` / `portal` | Record rule domains changed |
| **Collaborator access** | Binary collaborator | `limited_access` Boolean for fine-grained control | `edit_limited` mode added |
| **Task state** | Non-stored, computed | `store=True` with `recursive=True` | State now persisted, recalculates recursively |
| **Project sharing action** | Single `project.share.wizard` | Split: `project.share.wizard` + `task.share.wizard` | Separate task sharing UI |
| **Stage rotting** | Not available | `rotting_threshold_days` on stage | Tasks stale-trackable per stage |
| **Template dispatching** | Manual role assignment | `role_ids` on tasks + `project.template.create.wizard` | Role → employee mapping automatic |
| **Favorite ordering** | SQL fallback | Custom `_order_field_to_sql` | Favorited projects sort first via SQL INNER JOIN |

### Compatibility Layer

- `_mail_post_access = 'read'` still means only read access needed for messaging (unchanged)
- `CLOSED_STATES` pattern preserved — only the keys changed (`done` → `1_done`, `cancelled` → `1_canceled`)
- `OPEN_STATES` is now a dynamic property rather than hardcoded list

### Migration Checklist for Custom Code

```python
# BEFORE (Odoo 18):
task.user_id = user_id  # Single user assignment
# AFTER (Odoo 19):
task.user_ids = [Command.link(user_id)]  # Many2many

# BEFORE (Odoo 18):
if task.state == 'done':  # String comparison
# AFTER (Odoo 19):
if task.is_closed:  # Computed Boolean check

# BEFORE (Odoo 18):
stage_ids = project.type_ids.ids  # Direct list
# AFTER (Odoo 19):
# project_ids on stage + personal stages require user filtering
stage_ids = project.type_ids.filtered(lambda s: not s.user_id).ids
```

---

## L4: Security — Project Privilege Levels & Portal Access

### Project Privilege Levels

| Level | XML ID | Capabilities |
|-------|--------|-------------|
| Project User | `group_project_user` | Create tasks, edit own, view assigned |
| Project Manager | `group_project_manager` | Full CRUD, delete, manage stages, delete projects |
| Project Stages | `group_project_stages` | Manage project lifecycle stages, stage mail templates |
| Project Milestone | `group_project_milestone` | View milestone task counts and progress |
| Task Dependencies | `group_project_task_dependencies` | Manage blocking dependencies |
| Recurring Tasks | `group_project_recurring_tasks` | Create and manage recurring task patterns |

### Implied Group Chain

```
base.group_user
    │
    ├── implied_ids → group_project_user (always)
    │
    ├── implied_ids → group_project_task_dependencies (dynamic: added when first project enables allow_task_dependencies)
    │
    ├── implied_ids → group_project_milestone (dynamic: added when first project enables allow_milestones)
    │
    └── implied_ids → group_project_recurring_tasks (dynamic: added when first project enables allow_recurring_tasks)
```

### Portal Task Access (L4: Access Token + Collaborator Check)

```python
# How portal access is verified (portal.mixin pattern):
def _has_access(self, operation):
    if operation == 'read':
        # 1. Check if project is portal/employees visibility
        # 2. Check if task has collaborator record for this partner
        # 3. If limited_access: also check task in collaborator's assigned tasks
        return collaborator.exists() and (
            not collaborator.limited_access or
            task.user_ids & collaborator.partner_id.user_ids
        )
```

### `limited_access` Collaborator Logic

When a collaborator has `limited_access=True`:
- They can only see tasks they are directly assigned to (`task.user_ids` contains their user)
- They cannot see all project tasks in the Kanban view
- The `project.task` `display_follow_button` field becomes `False` for them

### `project_privilege_leaves` Note

There is no explicit `project_privilege_leaves` model in the `project` module. The "leaves" concept is managed via `resource.calendar` / `hr` module (attendance/time-off), not within project itself. Tasks can be assigned to employees, and the resource calendar affects deadline calculations but there is no dedicated "project privilege leaves" feature.

---

## L4: Security — Record Rules Deep Dive

### Task Record Rules (Complete Set)

| Rule | Domain | Scope |
|------|--------|-------|
| `project.project_task_rule_user` | `['\|', ('user_ids', 'in', user.id), ('project_privacy_visibility', '=', 'employees')]` | Internal users: own tasks OR employees-visibility projects |
| `project.project_task_rule_portal_project_sharing` | `project_id.privacy_visibility = 'portal'` AND collaborator exists | Portal: task in portal project with collaborator record |

### Favorite Projects (Security Note)

```python
favorite_user_ids = fields.Many2many(
    'res.users', 'project_favorite_user_rel',
    'project_id', 'user_id',
)
```

Favoriting is **not a security mechanism** — it only controls UI display order. Any user who can access a project can mark it as favorite regardless of project visibility.

### Mail Tracking Duration Index

```python
# mail_message.py — partial index for burndown chart
_date_res_id_id_for_burndown_chart = models.Index(
    "(date, res_id, id) WHERE model = 'project.task' AND message_type = 'notification'"
)
```

This index is used by the burndown chart report for efficient time-series queries on task notification messages. It filters out non-notification message types to keep the index lean.

