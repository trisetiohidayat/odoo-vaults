---
tags: [odoo, odoo17, module, project, research_depth]
research_depth: deep
---

# Project Module — Deep Research

**Source:** `addons/project/models/` (Odoo 17)

## Module Architecture

```
project.project
    ├── project.task              (main model, ~1800 lines)
    │   ├── project.task.type    (kanban pipeline columns/stages)
    │   ├── project.milestone    (delivery checkpoints)
    │   ├── project.tags         (colored labels)
    │   ├── project.update       (periodic status updates)
    │   ├── project.collaborator (portal project sharing)
    │   ├── project.task.recurrence (recurring task rules)
    │   └── project.task.stage.personal (per-user stage tracking)
    └── project.project.stage    (project lifecycle stages)
```

Supporting models (minor): `account_analytic_account.py`, `digest_digest.py`, `ir_ui_menu.py`, `mail_message.py`, `res_partner.py`, `res_config_settings.py`.

---

## project.project — Project Container

**File:** `project_project.py`

### Class Definition (Line 16)

```python
class Project(models.Model):
    _name = "project.project"
    _description = "Project"
    _inherit = [
        'portal.mixin',        # access_url for /my/projects/{id}
        'mail.alias.mixin',   # each project gets an email alias
        'rating.parent.mixin',  # 30-day satisfaction window
        'mail.thread',        # messaging
        'mail.activity.mixin',   # activities
    ]
    _order = "sequence, name, id"
    _rating_satisfaction_days = 30  # Line 21
    _systray_view = 'activity'
```

### rating.parent.mixin — 30-Day Satisfaction Window (Line 21)

```python
_rating_satisfaction_days = 30
```

The `_rating_satisfaction_days = 30` attribute sets the satisfaction window for `rating.parent.mixin`. During this window, ratings are counted as "active" for satisfaction statistics. The project-level rating request deadline is computed based on `rating_status_period` (lines 278-282):

```python
periods = {'daily': 1, 'weekly': 7, 'bimonthly': 15, 'monthly': 30, 'quarterly': 90, 'yearly': 365}
for project in self:
    project.rating_request_deadline = fields.datetime.now() + timedelta(days=periods.get(project.rating_status_period, 0))
```

### mail.alias.mixin — Email Alias Per Project (Line 143-144)

```python
alias_id = fields.Many2one(
    help="Internal email associated with this project. Incoming emails are automatically "
         "synchronized with Tasks (or optionally Issues if the Issue Tracker module is installed)."
)
```

Each project gets a dedicated `mail.alias` record. When `alias_id` is set, the alias creates tasks from incoming emails automatically. The alias uses `mail.alias.mixin` infrastructure:
- `alias_name`, `alias_defaults`, `alias_parent_thread_model` are managed by the mixin
- The project's `name` is used as the alias name by default
- `alias_id` is automatically created when the project is created (via mixin)

### All Fields (project.project)

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Project name, required, trigram indexed, translate, tracking |
| `description` | Html | Full HTML description |
| `active` | Boolean | Archive flag, default True |
| `sequence` | Integer | Sort order, default 10 |
| `partner_id` | Many2one res.partner | Customer, auto_join, tracking |
| `company_id` | Many2one res.company | Computed from analytic_account or partner; inverse enforces consistency |
| `currency_id` | Many2one res.currency | Computed from company |
| `analytic_account_id` | Many2one account.analytic.account | Links project + tasks + timesheets for cost/revenue tracking |
| `analytic_account_balance` | Monetary | `related=analytic_account_id.balance` |
| `favorite_user_ids` | Many2many res.users | Users who marked as favorite; default = current user |
| `is_favorite` | Boolean | Computed/inverse/search; shows on dashboard |
| `label_tasks` | Char | Label for tasks (e.g. "Tasks", "Tickets", "Sprints"), default "Tasks" |
| `tasks` | One2many project.task | All tasks |
| `task_ids` | One2many project.task | Only open tasks — `domain=lambda self: [('state', 'in', self.env['project.task'].OPEN_STATES)]` |
| `resource_calendar_id` | Many2one resource.calendar | Computed from company |
| `type_ids` | Many2many project.task.type | Kanban pipeline stages; shared across projects |
| `task_count` | Integer | Total task count (computed via `_compute_task_count`) |
| `open_task_count` | Integer | Open tasks (computed) |
| `closed_task_count` | Integer | Closed tasks (computed) |
| `color` | Integer | Kanban color index |
| `user_id` | Many2one res.users | Project manager, default=current user, tracking |
| `alias_id` | Many2one mail.alias | Project email alias for task creation from inbound email |
| `privacy_visibility` | Selection | `followers`/`employees`/`portal`, default `portal` |
| `privacy_visibility_warning` | Char | Warning when sharing restricted projects |
| `access_instruction_message` | Char | Access instructions for portal users |
| `doc_count` | Integer | Attachment count (project + all tasks via SQL query) |
| `date_start` | Date | Project start date |
| `date` | Date | Expiration / end date, indexed, tracked |
| `allow_task_dependencies` | Boolean | Enable dependency blocking, default from user group |
| `allow_milestones` | Boolean | Enable milestones, default from user group |
| `tag_ids` | Many2many project.tags | Project-level tags |
| `task_properties_definition` | PropertiesDefinition | Custom task property schema |
| `collaborator_ids` | One2many project.collaborator | Portal collaborators |
| `collaborator_count` | Integer | Computed collaborator count |
| `rating_request_deadline` | Datetime | Computed deadline based on rating period |
| `rating_active` | Boolean | Customer ratings enabled |
| `allow_rating` | Boolean | Current user in rating group |
| `rating_status` | Selection | `stage` or `periodic` rating trigger |
| `rating_status_period` | Selection | `daily`/`weekly`/`bimonthly`/`monthly`/`quarterly`/`yearly` |
| `stage_id` | Many2one project.project.stage | Project lifecycle stage (New/In Progress/...), grouped |
| `update_ids` | One2many project.update | All status updates |
| `last_update_id` | Many2one project.update | Most recent status update (set on create/update of project.update) |
| `last_update_status` | Selection | Computed from last_update_id; defaults to `to_define` |
| `last_update_color` | Integer | Computed from STATUS_COLOR map |
| `milestone_ids` | One2many project.milestone | All milestones |
| `milestone_count` | Integer | Total milestone count |
| `milestone_count_reached` | Integer | Reached milestone count |
| `is_milestone_exceeded` | Boolean | Any unreached milestone past deadline |

### Stages vs Tags (Two-Level Stage System)

**`project.project.stage`** (referenced by `stage_id` field, line 198): Project-level lifecycle stage — e.g. "New", "In Progress", "Completed", "On Hold". Controlled by `group_project_stages` security group. These are single-value per project.

**`project.task.type`** (referenced by `type_ids` Many2many, line 134): Per-task Kanban pipeline stages — e.g. "To Do", "In Progress", "Review", "Done". These are the kanban columns a task moves through. Can be shared across multiple projects or project-specific.

**`project.tags`** (referenced by `tag_ids` Many2many, line 171): Color-coded labels that cross-cut stages and can tag both projects and tasks. Color defaults to random 1-11 on creation.

---

## project.task — THE MAIN MODEL

**File:** `project_task.py` (~1800 lines)

### Class Definition (Line 66)

```python
class Task(models.Model):
    _name = "project.task"
    _description = "Task"
    _date_name = "date_assign"           # used for date-based filtering/ordering
    _inherit = [
        'portal.mixin',               # grants access_url /my/tasks/{id}
        'mail.thread.cc',            # CC handling on emails
        'mail.activity.mixin',
        'rating.mixin',
        'mail.tracking.duration.mixin'  # tracks time spent in each stage
    ]
    _mail_post_access = 'read'
    _order = "priority desc, sequence, date_deadline asc, id desc"
    _primary_email = 'email_from'
    _systray_view = 'activity'
    _track_duration_field = 'stage_id'   # mail.tracking.duration.mixin config
```

### CLOSED_STATES (Lines 60-63)

```python
CLOSED_STATES = {
    '1_done': 'Done',
    '1_canceled': 'Canceled',
}
```

`OPEN_STATES` (lines 315-318) is dynamically computed as all state values minus CLOSED_STATES. Used throughout for task count queries, state-based filtering, and milestone progress calculation.

### PROJECT_TASK_READABLE_FIELDS / PROJECT_TASK_WRITABLE_FIELDS (Lines 18-58)

Portal user access control for Project Sharing:

```python
PROJECT_TASK_READABLE_FIELDS = {
    'id', 'active', 'priority', 'project_id', 'display_in_project',
    'color', 'subtask_count', 'email_from', 'create_date', 'write_date',
    'company_id', 'displayed_image_id', 'display_name', 'portal_user_names',
    'user_ids', 'display_parent_task_button', 'allow_milestones', 'milestone_id',
    'has_late_and_unreached_milestone', 'date_assign', 'dependent_ids',
    'message_is_follower', 'recurring_task', 'closed_subtask_count', 'partner_id',
}

PROJECT_TASK_WRITABLE_FIELDS = {
    'name', 'description', 'date_deadline', 'date_last_stage_update',
    'tag_ids', 'sequence', 'stage_id', 'child_ids', 'parent_id',
    'priority', 'state',
}
```

Used in `fields_get()` override (line 731), `_ensure_fields_are_accessible()` (line 804), and `_ensure_portal_user_can_write()` (line 887).

### All Fields — Complete Table

| Field | Type | Line | Description |
|-------|------|------|-------------|
| `active` | Boolean | 126 | Default True |
| `name` | Char | 127 | Title, tracking, required, trigram index |
| `description` | Html | 128 | Full HTML description, sanitize_attributes=False |
| `priority` | Selection | 129 | `'0'` Low, `'1'` High |
| `sequence` | Integer | 133 | Sort order, default 10 |
| `stage_id` | Many2one | 134 | Kanban column, compute+store, domain by project, group_expand |
| `tag_ids` | Many2many | 138 | project.tags labels |
| `state` | Selection | 140 | Full workflow state (see State Machine) |
| `create_date` | Datetime | 148 | Creation timestamp, readonly, indexed |
| `write_date` | Datetime | 149 | Last update timestamp, readonly |
| `date_end` | Datetime | 150 | Stage-fold closing date |
| `date_assign` | Datetime | 151 | When task was last assigned (tracks SLA) |
| `date_deadline` | Datetime | 153 | Due date, indexed, tracked |
| `date_last_stage_update` | Datetime | 155 | Last state/stage change timestamp |
| `project_id` | Many2one | 162 | Parent project, domain by company |
| `display_in_project` | Boolean | 163 | Show in project kanban, default True |
| `task_properties` | Properties | 164 | Custom properties from project definition |
| `allocated_hours` | Float | 165 | Planned time (tracking) |
| `subtask_allocated_hours` | Float | 166 | Sum of sub-task allocated hours |
| `user_ids` | Many2many | 169 | **Multiple assignees** (key differentiator from CRM) |
| `portal_user_names` | Char | 172 | Computed names of all assignees for portal display |
| `personal_stage_type_ids` | Many2many | 175 | Per-user personal stage assignments |
| `personal_stage_id` | Many2one | 179 | Current user's personal stage record |
| `personal_stage_type_id` | Many2one | 184 | Current user's personal stage type |
| `partner_id` | Many2one | 188 | Customer contact, recursive compute |
| `email_cc` | Char | 191 | CC'd email addresses from inbound emails |
| `company_id` | Many2one | 192 | Computed from project/parent, recursive |
| `color` | Integer | 193 | Kanban color index |
| `rating_active` | Boolean | 194 | Related from project |
| `attachment_ids` | One2many | 195 | Computed main attachments (excludes message attachments) |
| `displayed_image_id` | Many2one | 198 | Cover image attachment |
| `parent_id` | Many2one | 200 | Parent task (self-referential, domain prevents child_of self) |
| `child_ids` | One2many | 201 | Sub-tasks (domain: non-recurring only) |
| `subtask_count` | Integer | 202 | Total sub-task count |
| `closed_subtask_count` | Integer | 203 | Done + canceled subtasks |
| `project_privacy_visibility` | Selection | 204 | Related from project |
| `working_hours_open` | Float | 206 | Working hours until assigned (calendar) |
| `working_hours_close` | Float | 207 | Working hours until closed |
| `working_days_open` | Float | 208 | Working days until assigned |
| `working_days_close` | Float | 209 | Working days until closed |
| `website_message_ids` | One2many | 211 | Portal-visible messages |
| `allow_milestones` | Boolean | 212 | Related from project |
| `milestone_id` | Many2one | 213 | Milestone checkpoint, btree_not_null indexed |
| `has_late_and_unreached_milestone` | Boolean | 224 | Any unreached milestone past deadline |
| `allow_task_dependencies` | Boolean | 229 | Related from project |
| `depend_on_ids` | Many2many | 231 | Tasks blocking this task |
| `dependent_ids` | Many2many | 234 | Tasks blocked by this task |
| `dependent_tasks_count` | Integer | 237 | Count of tasks blocked by this one |
| `display_parent_task_button` | Boolean | 240 | Show parent task button in portal |
| `recurring_task` | Boolean | 243 | Is part of a recurrence |
| `recurring_count` | Integer | 244 | Total tasks in this recurrence |
| `recurrence_id` | Many2one | 245 | Recurrence rule |
| `repeat_interval` | Integer | 246 | Repeat every N units |
| `repeat_unit` | Selection | 247 | `day`/`week`/`month`/`year` |
| `repeat_type` | Selection | 253 | `forever`/`until` |
| `repeat_until` | Date | 257 | End date for `until` recurrence |
| `analytic_account_id` | Many2one | 260 | From project (computed, writable) |
| `display_name` | Char | 267 | Quick-create shortcut — `#tag @user !priority` in title |

### State Machine (Lines 140-146)

```python
state = fields.Selection([
    ('01_in_progress', 'In Progress'),
    ('02_changes_requested', 'Changes Requested'),
    ('03_approved', 'Approved'),
    ('04_waiting_normal', 'Waiting'),
    ('1_done', 'Done'),
    ('1_canceled', 'Canceled'),
], default='01_in_progress')
```

State transitions:
- `04_waiting_normal` is **automatically set** by `_compute_state()` (lines 300-313) when any task in `depend_on_ids` is in an open state
- It auto-resets to `01_in_progress` when all dependencies are closed
- `auto_validation_state` on the stage can force `03_approved` or `02_changes_requested` based on rating responses
- `_inverse_state()` (lines 328-332) triggers the next recurrence occurrence when a recurring task is closed

### user_ids vs user_id — The Key Difference from CRM

**CRM leads use `user_id` (single Many2one)**. **Project tasks use `user_ids` (multiple Many2many)**.

```python
# Line 169 — multiple assignees
user_ids = fields.Many2many(
    'res.users',
    relation='project_task_user_rel',
    column1='task_id',
    column2='user_id',
    string='Assignees',
    context={'active_test': False},
    tracking=True,
    default=_default_user_ids,  # defaults to current user on create
    domain="[('share', '=', False), ('active', '=', True)]"
)
```

Key behaviors:
- `portal_user_names` (line 172): sudo-fetches all user names for project sharing views
- `_message_get_suggested_recipients` (line 1494): Suggests all assignees as email recipients
- `_rating_get_operator` override (line 1743): "Overwrite since we have user_ids and not user_id" — returns single assignee's partner if exactly one user assigned
- `_message_auto_subscribe_followers` override (line 1332): Subscribes all assignees to the mail thread
- `date_assign` (line 927): Set when `user_ids` is first populated on create (line 927)
- If user clears all assignees: `date_assign` is reset to False (line 1158)
- Portal users can only write fields in `PROJECT_TASK_WRITABLE_FIELDS`

### Subtasks — child_ids / parent_id (Lines 200-202, 514-525, 1534-1579)

```python
parent_id = fields.Many2one(
    'project.task',
    domain="['!', ('id', 'child_of', id)]"   # prevents self-reference
)
child_ids = fields.One2many(
    'project.task',
    'parent_id',
    domain="[('recurring_task', '=', False)]"  # subtasks cannot be recurrent
)
subtask_count = fields.Integer(compute='_compute_subtask_count')
closed_subtask_count = fields.Integer(compute='_compute_subtask_count')
```

Key behaviors:
- SQL constraint: subtasks cannot be recurrent (line 276)
- SQL constraint: private tasks cannot have parents (line 277)
- `_compute_subtask_count` uses `_read_group` with `state:array_agg` to count total and closed subtasks in one query
- `_get_subtask_ids_per_task_id()` uses a **recursive CTE** (`WITH RECURSIVE task_tree`) to find all descendants
- On project change: subtasks without explicit project follow parent, with `display_in_project=False`
- On parent_id unset: `display_in_project` is set back to True
- Subtasks inherit milestone from parent when `parent_id.project_id == project_id` (line 1259)
- Subtasks cascade milestone changes from parent (write lines 1084-1104)

### Milestones — project.milestone Integration (Lines 213-227, 1256-1285)

```python
milestone_id = fields.Many2one(
    'project.milestone',
    domain="[('project_id', '=', project_id)]",
    compute='_compute_milestone_id',
    readonly=False, store=True,
    tracking=True,
    index='btree_not_null',
)
```

- Subtasks auto-inherit parent's milestone via `_compute_milestone_id` (line 1259): `task.milestone_id = task.parent_id.project_id == task.project_id and task.parent_id.milestone_id`
- `_compute_has_late_and_unreached_milestone` (lines 226, 1261): Flags tasks with unreached milestones past their deadline
- Custom search domain `_search_has_late_and_unreached_milestone` (line 1273) allows filtering in views
- `has_late_and_unreached_milestone` uses a sudo search (needed for portal users in Project Sharing)

### mail.tracking.duration.mixin (Line 75, 81)

```python
_track_duration_field = 'stage_id'
```

This mixin automatically records how long a task spends in each stage. It writes `mail.tracking.duration` records on every stage transition. Combined with `date_last_stage_update`, this enables working time statistics (`working_hours_open`, `working_hours_close`, etc.).

### Key Methods

| Method | Lines | Description |
|--------|-------|-------------|
| `_compute_state` | 300-313 | Auto-sets `04_waiting_normal` when deps open; resets to `01_in_progress` |
| `_inverse_state` | 328-332 | On close: creates next recurrence occurrence |
| `_compute_personal_stage_id` | 336-341 | Loads current user's `project.task.stage.personal` record |
| `_get_default_personal_stage_create_vals` | 357-366 | Default stages: Inbox, Today, This Week, This Month, Later, Done, Canceled |
| `_populate_missing_personal_stages` | 368-384 | Creates personal stage records for newly assigned users |
| `message_subscribe` | 386-395 | Mirrors project followers as task followers |
| `_check_no_cyclic_dependencies` | 397-400 | `CHECK(m2m_recursion)` validates no A→B→A cycle |
| `_compute_repeat` | 412-423 | Syncs repeat fields with recurrence_id |
| `_compute_elapsed` | 469-496 | Working hours/days to assign and close using calendar |
| `_compute_portal_user_names` | 549-565 | sudo-fetch all user names for project sharing views |
| `_extract_tags_and_users` | 606-628 | Parses `@user` and `#tag` patterns from display_name |
| `_inverse_display_name` | 641-652 | Quick-create: sets name, user_ids, tag_ids, priority from title |
| `_ensure_fields_are_accessible` | 804-824 | Portal user field access enforcement |
| `_set_stage_on_project_from_task` | 892-899 | Adds task's stage to project's `type_ids` if missing |
| `create` | 914-1012 | Portal handling, defaults, personal stages, mail subscribe, parent cascade |
| `write` | 1014-1178 | Full write: project changes, milestone cascade, personal stages, recurrence |
| `unlink` | 1180-1187 | Deletes subtasks (via `_get_all_subtasks`) and recurrence |
| `update_date_end` | 1189-1193 | Sets date_end if stage.fold=True, clears otherwise |
| `_get_all_subtasks` | 1534-1535 | Returns all descendant subtasks via recursive CTE |
| `_get_subtask_ids_per_task_id` | 1537-1573 | SQL recursive CTE: `WITH RECURSIVE task_tree AS (...)` |
| `action_dependent_tasks` | 1648-1663 | Opens blocked-by or blocking tasks |
| `action_recurring_tasks` | 1665-1673 | Opens all tasks in this recurrence |
| `_send_task_rating_mail` | 1714-1719 | Sends rating request via stage's `rating_template_id` |
| `_rating_get_operator` | 1743-1746 | Single assignee's partner; falls back to project's partner |
| `message_new` | 1453-1485 | Mail gateway: creates task from email with auto-partner creation |
| `rating_apply` | 1727-1735 | On rating: auto-sets state based on `auto_validation_state` |

---

## project.task.type — Task Stages (Kanban Columns)

**File:** `project_task_type.py`

### Class Definition (Line 10)

```python
class ProjectTaskType(models.Model):
    _name = 'project.task.type'
    _description = 'Task Stage'
    _order = 'sequence, id'
```

### All Fields

| Field | Type | Description |
|-------|------|-------------|
| `active` | Boolean | Archive flag; cascades to tasks |
| `name` | Char | Stage name, required, translate |
| `description` | Text | Stage description |
| `sequence` | Integer | Sort order, default 1 |
| `project_ids` | Many2many project.project | Projects sharing this stage |
| `mail_template_id` | Many2one mail.template | Email sent when task enters stage |
| `fold` | Boolean | Folded in kanban (collapsed column) |
| `rating_template_id` | Many2one mail.template | Rating request email for this stage |
| `auto_validation_state` | Boolean | Auto-Kanban: good rating→Approved, bad→Changes Requested |
| `disabled_rating_warning` | Text | Warns if projects using this stage have ratings disabled |
| `user_id` | Many2one res.users | Stage owner; cleared when shared with projects |

### Key Behaviors

- `fold` → When a task enters a folded stage, `date_end` is set (line 1191-1192 in project_task.py)
- **Personal stages** (line 184-187): Stages with a `user_id` are personal-only. `_constrains('user_id', 'project_ids')` ensures personal stages cannot be linked to projects.
- `auto_validation_state` (line 43): When rating response received, if rating >=满意 threshold → `03_approved`, else → `02_changes_requested`. Controlled by `rating.mixin` and `rating_apply()` (line 1727).
- **Personal stage deletion** (lines 88-144 `_unlink_if_remaining_personal_stages`): Tasks reassigned to nearest available stage by sequence before deletion.
- **Stage owner** (`user_id`): A personal stage's owner is the only user who can see it. When a stage is shared with a project, `user_id` is cleared (line 182).

---

## project.milestone — Delivery Checkpoints

**File:** `project_milestone.py`

### Class Definition (Line 10)

```python
class ProjectMilestone(models.Model):
    _name = 'project.milestone'
    _description = "Project Milestone"
    _inherit = ['mail.thread']
    _order = 'deadline, is_reached desc, name'
```

### All Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Milestone name, required |
| `project_id` | Many2one project.project | Required, cascade delete |
| `deadline` | Date | Target date, tracking enabled |
| `is_reached` | Boolean | Marked as reached |
| `reached_date` | Date | Computed: today when `is_reached=True` |
| `task_ids` | One2many project.task | Tasks in this milestone |
| `is_deadline_exceeded` | Boolean | Computed: deadline < today and not reached |
| `is_deadline_future` | Boolean | Computed: deadline > today |
| `task_count` | Integer | Total tasks (group: `project.group_project_milestone`) |
| `done_task_count` | Integer | Done + Canceled tasks |
| `can_be_marked_as_done` | Boolean | All tasks closed and at least one closed |

### `can_be_marked_as_done` Logic (Lines 61-84)

```python
def _compute_can_be_marked_as_done(self):
    # Two code paths: single-record vs multi-record
    # Multi-record: uses _read_group to count open/closed per milestone
    task_read_group = self.env['project.task']._read_group(
        [('milestone_id', 'in', unreached_milestones.ids)],
        ['milestone_id', 'state'], ['__count'],
    )
    # Groups by state: closed_task_count, opened_task_count
    # Sets can_be_marked_as_done = closed_task_count > 0 and not opened_task_count
```

A milestone can be marked done only when it has at least one closed task and zero open tasks.

---

## project.update — Status Updates

**File:** `project_update.py`

### STATUS_COLOR Map (Lines 12-21)

```python
STATUS_COLOR = {
    'on_track': 20,     # green / success
    'at_risk': 22,      # orange
    'off_track': 23,    # red / danger
    'on_hold': 21,      # light blue
    'done': 24,         # purple
    False: 0,           # default grey (Studio)
    'to_define': 0,
}
```

### Class Definition (Line 23)

```python
class ProjectUpdate(models.Model):
    _name = 'project.update'
    _order = 'id desc'  # newest first
    _inherit = ['mail.thread.cc', 'mail.activity.mixin']
```

### All Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Title, required, tracking |
| `status` | Selection | `on_track`/`at_risk`/`off_track`/`on_hold`/`done`, required, tracking |
| `color` | Integer | From STATUS_COLOR map |
| `progress` | Integer | % complete (0-100), tracking |
| `progress_percentage` | Float | progress / 100 |
| `user_id` | Many2one res.users | Author, required, default=current user |
| `description` | Html | Update content, auto-generated by QWeb template |
| `date` | Date | Date of update, default=today, tracking |
| `project_id` | Many2one project.project | Required |
| `name_cropped` | Char | First 57 chars of name + "..." |
| `task_count` | Integer | Snapshot: total project tasks at creation |
| `closed_task_count` | Integer | Snapshot: closed tasks at creation |
| `closed_task_percentage` | Integer | `closed_task_count * 100 / task_count` |

### Auto-Generated Description (Lines 109-192)

`description` is auto-generated by `_build_description()` using the QWeb template `project.project_update_default_description`. The template renders:
- Milestones with upcoming deadlines (within 1 year)
- Milestones whose deadlines changed since the last update (via `mail_tracking_value` query)
- Milestones created since the last update
- Progress statistics

The milestone tracking query (lines 153-184) uses a SQL window function (`FIRST_VALUE() OVER w_partition`) to find the old deadline value from `mail_message` tracking records.

---

## project.collaborator — Portal Project Sharing

**File:** `project_collaborator.py`

### Class Definition (Line 7)

```python
class ProjectCollaborator(models.Model):
    _name = 'project.collaborator'
    _description = 'Collaborators in project shared'
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `project_id` | Many2one project.project | Domain: `privacy_visibility = 'portal'` only |
| `partner_id` | Many2one res.partner | Collaborator |
| `partner_email` | Char | `related=partner_id.email` |

### Feature Gating Mechanism (Lines 24-57)

The first collaborator added to ANY project globally enables the "Project Sharing" feature:

```python
def _toggle_project_sharing_portal_rules(self, active):
    # Enables access_project_sharing_task_portal ir.model.access
    # Enables project_task_rule_portal_project_sharing ir.rule
    access_project_sharing_portal = self.env.ref('project.access_project_sharing_task_portal').sudo()
    if access_project_sharing_portal.active != active:
        access_project_sharing_portal.write({'active': active})

    task_portal_ir_rule = self.env.ref('project.project_task_rule_portal_project_sharing').sudo()
    if task_portal_ir_rule.active != active:
        task_portal_ir_rule.write({'active': active})
```

The last collaborator removed disables the feature. Without at least one collaborator, portal users cannot access project sharing.

---

## project.tags — Color-Coded Labels

**File:** `project_tags.py`

### Class Definition (Line 10)

```python
class ProjectTags(models.Model):
    _name = "project.tags"
    _description = "Project Tags"
    _order = "name"
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Required, translate, unique |
| `color` | Integer | Random 1-11 default; transparent (color=0) invisible in kanban |
| `project_ids` | Many2many project.project | Projects using this tag |
| `task_ids` | Many2many project.task | Tasks using this tag |

### Key Behaviors

- `_name_search` optimization (lines 72-90): For large projects, first finds tags from the last 1000 tasks of the project (SQL query), then falls back to full search to fill remaining results. O(n) for n <= 1000, O(n) total.
- `name_create` override (lines 93-97): **Case-insensitive deduplication** — if a tag named "Feature" exists and user creates "feature", the existing tag is returned instead of creating a duplicate.
- SQL unique constraint: `('name', 'unique')`
- Color 0 (transparent) tags are invisible in kanban view

---

## See Also

- [Modules/Stock](Modules/stock.md) — stock.quant and inventory valuation
- [Modules/Sale](Modules/sale.md) — task-to-sale-order integration
- [Modules/HR](Modules/hr.md) — timesheets linked via `analytic_account_id`
- [Core/API](Core/API.md) — @api.depends, @api.onchange decorators
- [Patterns/Workflow Patterns](odoo-18/Patterns/Workflow Patterns.md) — state machine patterns
- [Patterns/Security Patterns](odoo-18/Patterns/Security Patterns.md) — ACL CSV, ir.rule, portal.mixin
