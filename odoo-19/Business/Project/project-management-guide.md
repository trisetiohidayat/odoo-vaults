---
type: guide
title: "Project Management Guide"
module: project
audience: business-consultant, project-manager
level: 2
prerequisites:
  - project_settings_configured
  - stages_defined
  - users_active
  - project_tags_created
estimated_time: "~20 minutes"
related_flows:
  - "[Flows/Project/project-creation-flow](Flows/Project/project-creation-flow.md)"
  - "[Flows/Project/task-lifecycle-flow](Flows/Project/task-lifecycle-flow.md)"
related_guides:
  - "[Business/HR/leave-management-guide](Business/HR/leave-management-guide.md)"
  - "[Business/Stock/warehouse-setup-guide](Business/Stock/warehouse-setup-guide.md)"
source_module: project
created: 2026-04-07
version: "1.0"
---

# Project Management Guide

> **Quick Summary:** Complete walkthrough for project managers to create projects with teams, create and assign tasks, track progress via stages, and log time on tasks — covering the three core daily workflows in the Odoo 19 Project app.

**Actor:** Project Manager / Team Lead
**Module:** Project
**Use Case:** Day-to-day project and task management — create projects, assign team members, manage task lifecycle, and track time against tasks
**Difficulty:** ⭐ Easy / ⭐⭐ Medium

---

## Prerequisites Checklist

Before starting, ensure the following are configured. Skipping these will cause errors or missing features.

- [ ] **[Project Settings Configured]** — Navigate to **Project → Configuration → Settings**. Enable: "Task Dependencies", "Milestones", "Recurring Tasks", and "Project Stages" as needed. Set default privacy visibility.
- [ ] **[Stages Defined]** — Navigate to **Project → Configuration → Stages**. Create stages matching your workflow (e.g., "To Do", "In Progress", "Review", "Done"). Assign colors and folding behavior for kanban.
- [ ] **[Users Active]** — Navigate to **Settings → Users**. Ensure all team members have active Odoo user accounts with `Project User` or `Project Manager` group assigned.
- [ ] **[Project Tags Created]** — Navigate to **Project → Configuration → Tags**. Create tags for categorizing projects and tasks (e.g., "Engineering", "Design", "Urgent").
- [ ] **[Analytic Account Plan]** *(Optional — for cost tracking)* — Navigate to **Accounting → Configuration → Analytic Accounting → Analytic Plans**. Create a plan if you need per-project cost tracking.
- [ ] **[Rating Templates]** *(Optional — for customer satisfaction)* — Navigate to **Email → Templates**. Ensure rating email templates exist in `project.mail_template_task_rating_request`.

> **⚠️ Critical:** If **Users** are not set up with correct groups, they will not appear in the assignee picker (`user_ids` field) when creating tasks, and will get an `AccessError` when trying to access project data.

---

## Quick Access

| Type | Link | Description |
|------|------|-------------|
| 🔀 Technical Flow | [Flows/Project/project-creation-flow](Flows/Project/project-creation-flow.md) | Full method chain for project creation |
| 🔀 Technical Flow | [Flows/Project/task-lifecycle-flow](Flows/Project/task-lifecycle-flow.md) | Full method chain for task creation and stage changes |
| 📖 Module Reference | [Modules/Project](Modules/project.md) | Complete field and method reference |
| 🔧 Configuration | [Modules/Project](Modules/project.md) → Settings section | Project app configuration options |
| 📋 Related Guide | [Business/HR/leave-management-guide](Business/HR/leave-management-guide.md) | Team availability and leave tracking |

---

## Use Cases Covered

This guide covers the following use cases. Jump to the relevant section:

| # | Use Case | Page | Difficulty |
|---|----------|------|-----------|
| 1 | Create a project with a team and configure settings | [#use-case-a-create-a-project-with-team](#use-case-a-create-a-project-with-team.md) | ⭐ |
| 2 | Create tasks and assign team members | [#use-case-b-create-tasks-and-assign](#use-case-b-create-tasks-and-assign.md) | ⭐⭐ |
| 3 | Track time on a task | [#use-case-c-track-time-on-task](#use-case-c-track-time-on-task.md) | ⭐⭐⭐ |

---

## Use Case A: Create a Project with Team

*[Standard flow: project creation with team assignment, privacy settings, and feature configuration]*

### Scenario

A project manager needs to create a new project for a software development sprint. The project should be visible to the internal team (employees), use a specific task stage pipeline, and have the project manager and several team members assigned as followers.

### Steps

#### Step 1 — Create a New Project

Navigate to: `Project → Create`

Click **Create**.

> **⚡ System Behavior:** Odoo opens a blank project form. The project ID is not yet assigned — it will be generated on save. The current user is pre-filled as the Project Manager (`user_id`).

#### Step 2 — Fill Basic Project Information

| Field | Value | Required | Auto-filled |
|-------|-------|----------|-------------|
| **Project Name** | "Q2 Sprint — Mobile App" | ✅ Yes | — |
| **Description** | HTML description | No | — |
| **Customer** | Select partner (res.partner) | No | — |
| **Project Manager** | Select user | No | Default: current user |
| **Start Date** | e.g., 2026-04-01 | No | — |
| **Expiration Date** | e.g., 2026-06-30 | No | — |

> **⚡ System Trigger:** When you set the **Customer** (`partner_id`), Odoo does NOT auto-fill the email address — but the customer's email is used for the mail alias (`alias_defaults`). The partner's followers are NOT automatically added as project followers.

> **⚡ Side Effect:** When **Project Manager** (`user_id`) is set, Odoo auto-subscribes the manager's partner as a `mail.follower` on the project. The manager receives all task notifications.

#### Step 3 — Configure Privacy Visibility

| Privacy Option | Access Level | Use When |
|---------------|-------------|-----------|
| **All internal users and invited portal users** (default: `portal`) | All employees + invited portal | External customer collaboration |
| **Invited internal and portal users** (`invited_users`) | Only followers + portal | Customer portal access with following |
| **Invited internal users** (`followers`) | Only followers | Strict internal with selective sharing |
| **All internal users** (`employees`) | All employees | Company-wide visible projects |

> **⚡ System Trigger:** Changing `privacy_visibility` triggers `_change_privacy_visibility()`. If visibility is tightened (e.g., from `portal` to `employees`), portal followers are unsubscribed via `message_unsubscribe()`. If visibility is expanded, no auto-subscription occurs.

#### Step 4 — Enable Project Features

| Feature | Field | Default | Effect When Enabled |
|---------|-------|---------|---------------------|
| Task Dependencies | `allow_task_dependencies` | False | Tasks can block other tasks (`depend_on_ids`) |
| Milestones | `allow_milestones` | False | Milestone tracking with deadline monitoring |
| Recurring Tasks | `allow_recurring_tasks` | False | Tasks auto-generate future copies |

> **⚡ System Trigger:** Toggling `allow_task_dependencies = True` triggers `_inverse_allow_task_dependencies()`. Tasks in `04_waiting_normal` state are reviewed — tasks without open dependencies are set to `01_in_progress`. Toggling `allow_milestones` triggers `_inverse_allow_milestones()` which may add the `group_project_milestone` security group to base users.

#### Step 5 — Assign Stages (Task Pipeline)

Navigate to: `project.project → Stages` tab (right side of form)

Select stages from the available `project.task.type` records. Hold **Ctrl/Cmd + Click** to select multiple.

> **⚡ System Trigger:** Stages are stored as a `Many2many` (`type_ids`). The first non-folded stage in sequence order becomes the default `stage_id` for new tasks via `stage_find()`.

> **⚡ Side Effect:** When a stage is assigned to a project, that stage's `mail_template_id` and `rating_template_id` are used for notifications and rating requests.

#### Step 6 — Set Project Tags

In the form's `Tags` field, select tags to categorize this project.

> **⚡ Side Effect:** Tags are stored in `project_tags` table and linked via `project_project_project_tags_rel`. Tags help filter projects in list views.

#### Step 7 — Save and Verify

Click **Save**.

**Expected Results Checklist:**
- [ ] Project appears in **Project → All** list
- [ ] Project Manager (user_id) appears in **Internal Followers** tab
- [ ] Mail alias auto-created: `Q2-Sprint---Mobile-App@your-domain.com`
- [ ] Incoming emails to alias create tasks in this project
- [ ] Task pipeline shows configured stages in Kanban view
- [ ] Tags visible in project list filter

---

## Use Case B: Create Tasks and Assign

*[Standard flow: task creation, assignee management, subtask hierarchy, and stage progression]*

### Scenario

The project manager creates tasks for the sprint. Each task is assigned to a team member, linked to a milestone, and has a deadline. Subtasks are created for complex tasks. As work progresses, tasks move through stages toward completion.

### Steps

#### Step 1 — Create a Task

Navigate to: `Project → Q2 Sprint — Mobile App → Tasks → Create`

Click **Create**.

> **⚡ System Behavior:** The `project_id` is pre-filled from the current project context. The `stage_id` is auto-selected via `stage_find()` — typically the first non-folded stage by sequence. The `state` defaults to `01_in_progress`.

#### Step 2 — Fill Task Details

| Field | Value | Required | Auto-filled |
|-------|-------|----------|-------------|
| **Task Name** | "Implement login screen" | ✅ Yes | — |
| **Description** | HTML task description | No | — |
| **Assignees** | Select users | No | Default: current user (if personal stage context) |
| **Tags** | Select task tags | No | — |
| **Milestone** | Select milestone | No | — |
| **Deadline** | Set date/time | No | — |
| **Allocated Time** | Hours (float) | No | — |

> **⚡ System Trigger:** When **Assignees** (`user_ids`) are set:
> - `date_assign` is set to `fields.Datetime.now()` (if first assignment)
> - Assignee partners are auto-subscribed to `mail.followers` via `_task_message_auto_subscribe_notify()`
> - Personal stages (`project_task_stage_personal`) are created for each assignee
>
> When **Milestone** is set:
> - `milestone_id` written to task
> - Parent task's milestone cascades to subtasks without milestones

#### Step 3 — Configure Task Dependencies

> **⚡ Conditional Step:** Only available if `allow_task_dependencies = True` on the project.

In the **Dependencies** section (right panel), use the **Blocked By** field to select tasks that must be completed first.

> **⚡ System Trigger:** `depend_on_ids` stored in `task_dependencies_rel` junction table. Odoo automatically computes `blocked` state: if any dependency is not in `CLOSED_STATES`, this task's `state` is set to `04_waiting_normal` (blocked).

> **⚡ Constraint:** A cyclic dependency check prevents setting Task A as blocked by Task B while Task B is blocked by Task A. This raises `ValidationError("Two tasks cannot depend on each other.")`.

#### Step 4 — Create Subtasks

Click **Add a Line** in the **Sub-tasks** section (bottom of form), or click **Create Subtasks** in the Activity tab.

> **⚡ System Trigger:** Subtasks inherit the parent's `project_id` and `partner_id` via `_compute_partner_id()`. When a subtask is saved:
> - Parent task's followers are auto-subscribed to the subtask via `message_subscribe()` cascade
> - Parent task's `subtask_count` is recomputed
> - `parent_id` set via `_inverse_parent_id()` — prevents circular reference
>
> **Constraint:** A subtask cannot itself have subtasks if `recurring_task = True`. This raises `ValidationError` via `_recurring_task_has_no_parent` constraint.

#### Step 5 — Move Task Through Stages

In the **Kanban view**, drag the task card from one stage column to another.

> **⚡ System Trigger:** Dragging triggers `write({'stage_id': new_stage_id})`:
> - `date_last_stage_update` → `fields.Datetime.now()`
> - If target stage has `fold = True`: `date_end` → `now()`
> - If target stage has `rating_active = True` AND `rating_status = 'stage'`: `_send_task_rating_mail(force_send=True)` — customer rating email dispatched
> - If `stage_id.rating_active` AND `auto_validation_state`: task `state` auto-updated based on rating

#### Step 6 — Mark Task as Done

In the task form, click the **Done** button (or change `state` to `1_done`).

> **⚡ System Trigger:** `write({'state': '1_done'})` triggers `_inverse_state()`:
> - Subtasks checked: if all subtasks in `CLOSED_STATES` → proceed
> - If task has `recurrence_id`: `_create_next_occurrences()` generates next task in recurrence
> - Rating request already sent (on stage entry) — customer can respond
> - `closed_subtask_count` updated

**Expected Results Checklist:**
- [ ] Task appears in correct Kanban stage column
- [ ] Assignees appear in task form header and receive notifications
- [ ] Milestone progress updated in **Project → Milestones** view
- [ ] Subtasks show under parent task in Activity tab
- [ ] Blocked tasks show with "Waiting" state indicator
- [ ] Rating email sent to customer (if milestone stage has rating enabled)

---

## Use Case C: Track Time on Task

*[Advanced flow: time logging, timesheet integration, and deadline management]*

### Scenario

Team members need to log time against tasks for billing and capacity planning. The project uses either Odoo's native time tracking or the `hr_timesheet` module for integration with HR and invoicing.

### Steps

#### Step 1 — Enable Time Tracking

Navigate to: `Project → Q2 Sprint — Mobile App → Settings tab`

Toggle **Timesheet** to enabled (requires `hr_timesheet` module).

> **⚡ System Trigger:** Enabling timesheet creates a link between `project.project` and `account.analytic.account`. Each task becomes trackable via `account.analytic.line` entries.

> **⚡ Alternative:** For native time tracking without `hr_timesheet`, use the **Time Tracking** toggle (no module dependency). Time is tracked via `project.task` duration fields: `working_hours_open`, `working_hours_close`, `working_days_open`, `working_days_close`.

#### Step 2 — Log Time on a Task (Native Tracking)

Navigate to: `Project → Q2 Sprint — Mobile App → Task → "Implement login screen"`

Click the **Time Tracking** button (clock icon) in the form header.

| Field | Value | Notes |
|-------|-------|-------|
| **Date** | Select date | Defaults to today |
| **Duration** | e.g., 2.5 hours | Float in hours |
| **Description** | Work description | Optional |

Click **Log** to save.

> **⚡ System Trigger:** When **Timesheet** is enabled:
> - `account.analytic.line` created with: `account_id` from project, `product_id` from user's timesheet product, `unit_amount` = hours, `date`, `user_id`
> - Task's `allocated_hours` compared against logged hours
> - `project_project.analytic_account_balance` updated
>
> When using **Native Time Tracking** (no timesheet module):
> - Duration stored in `project_task.duration_tracking` JSON field
> - `working_hours_open` / `working_days_open` computed from creation → now

#### Step 3 — Set Allocated Hours and Monitor Progress

Navigate to: `Project → Q2 Sprint — Mobile App → Task → "Implement login screen" → Details tab`

Set **Allocated Time**: 8.0 hours.

> **⚡ System Trigger:** `allocated_hours` is a tracked field. As timesheet entries are logged:
> - Progress percentage computed: `sum(hours_logged) / allocated_hours`
> - Task color may change (red) if `date_deadline` is exceeded
> - If using `project.update` milestones: update progress reflected in project status

#### Step 4 — Monitor Team Capacity

Navigate to: `Project → Q2 Sprint — Mobile App → Reporting → Timesheet`

> **⚡ System Behavior:** Shows `account.analytic.line` entries grouped by user and task. Displays:
> - Total hours per user
> - Total hours per task
> - Billable vs. non-billable breakdown
> - Variance against allocated hours

> **⚡ Conditional Step:** Only available when `hr_timesheet` module is installed and enabled on the project.

#### Step 5 — Set Task Deadline and Monitor Overdue

Navigate to: `Project → Q2 Sprint — Mobile App → Task → "Implement login screen" → Scheduling tab`

Set **Deadline**: 2026-04-15.

> **⚡ System Trigger:** `date_deadline` is a tracked field. When deadline passes with task not in `CLOSED_STATES`:
> - Task card shows red border in Kanban
> - `has_late_and_unreached_milestone = True` if linked to a milestone with past deadline
> - In project list: tasks with overdue deadlines appear with warning icon

**Expected Results Checklist:**
- [ ] Time entries appear in **Reporting → Timesheet**
- [ ] Task `allocated_hours` vs. logged hours shown in task form
- [ ] Overdue tasks highlighted in Kanban
- [ ] Analytic account balance updated in project form header
- [ ] Team capacity visible in **Reporting → Timesheet by User**
- [ ] Milestone deadline warnings shown in project milestone view

---

## Common Pitfalls

| # | Mistake | Symptom | How to Avoid |
|---|---------|---------|-------------|
| 1 | Forgetting to assign a project stage | Tasks default to lowest-sequence stage regardless of workflow | Always assign `type_ids` (stages) to new projects |
| 2 | Setting `privacy_visibility = 'followers'` without adding followers | Project appears empty for team members | Add team members as followers before saving |
| 3 | Creating subtasks before parent task has a project | `ValidationError: Private tasks cannot have parent` | Always set `project_id` on the parent task first |
| 4 | Enabling milestones without creating any milestones | Milestone features appear broken | Create milestones in **Project → Milestones** tab before expecting deadline tracking |
| 5 | Assigning task to user who is not an Odoo user | User not appearing in `user_ids` picker | Ensure user has `Active = True` in **Settings → Users** |
| 6 | Circular task dependency | `ValidationError: Two tasks cannot depend on each other` | Check `depend_on_ids` carefully before saving |
| 7 | Logging time without enabling timesheet module | Time entries not creating analytic lines | Install and enable `hr_timesheet` module before time logging |
| 8 | Closing task with open subtasks | Parent task closes but subtasks remain open | Always close subtasks before closing parent task |
| 9 | Changing project on a task with existing dependencies | Dependency relationships broken | Clear `depend_on_ids` before changing `project_id` |
| 10 | Creating tasks in archived projects | Task creation silently succeeds but task hidden | Always activate project before adding tasks |

---

## Configuration Deep Dive

### Related Configuration Paths

| Configuration | Menu Path | Controls |
|--------------|-----------|----------|
| Project Settings | `Project → Configuration → Settings` | Default privacy, rating, task dependencies, milestones |
| Task Stages | `Project → Configuration → Stages` | Stage names, sequence, colors, fold behavior, rating templates |
| Project Stages | `Project → Configuration → Project Stages` | Project lifecycle stages (if `group_project_stages` enabled) |
| Tags | `Project → Configuration → Tags` | Tag names and colors for filtering |
| Rating Templates | `Email → Templates → Rating` | Customer rating email content |
| Users & Companies | `Settings → Users` | User accounts, groups, active status |
| Analytic Plans | `Accounting → Configuration → Analytic Accounting → Analytic Plans` | Cost tracking structure |
| Timesheet Settings | `Project → Configuration → Settings` | Billable vs. non-billable, rounding |

### Advanced Options

| Option | Field Name | Default | Effect When Enabled |
|--------|-----------|---------|---------------------|
| Task Dependencies | `allow_task_dependencies` | False | Enables `Blocked By` and `Blocking` fields on tasks |
| Milestones | `allow_milestones` | False | Enables **Milestones** tab and deadline tracking |
| Recurring Tasks | `allow_recurring_tasks` | False | Enables repeat configuration on tasks |
| Project Stages | `group_project_stages` | False | Enables `project.project.stage` lifecycle stages |
| Auto-validation by Rating | `auto_validation_state` on stage | False | Moves task to Approved/Changes Requested based on customer rating |
| Folded Kanban Stage | `fold` on `project.task.type` | False | Tasks in folded stages show `date_end` automatically |
| Rating Request on Stage | `rating_active` on `project.task.type` | False | Sends rating email when task enters this stage |
| Rotting Threshold | `rotting_threshold_days` on stage | 0 (disabled) | Tasks in stage without activity auto-move to next stage |

---

## Troubleshooting

| Problem | Likely Cause | Solution |
|---------|-------------|----------|
| Tasks not appearing in Kanban | Task `active = False` or wrong project filter | Check `active_test` in context; verify project filter in search |
| Assignee not in user picker | User not in `project.group_project_user` group | Add user to the group in **Settings → Users → Access Rights** |
| Mail alias not created | Missing `mail.alias.mixin` inheritance or alias_domain not set | Check **Settings → Email → Domains**; ensure alias domain configured |
| Rating email not sent | `rating_active = False` on stage or no `rating_template_id` | Enable rating on stage; assign rating template |
| Subtask shows "Private task" error | Parent task has no `project_id` | Set `project_id` on parent task first |
| Milestone not selectable on task | `allow_milestones = False` on project | Toggle milestones on in project Settings tab |
| Task stuck in `Waiting` state | Unresolved `depend_on_ids` | Complete or remove blocking tasks |
| Time entries not showing in reporting | `hr_timesheet` module not installed | Install `hr_timesheet` or use native time tracking |
| Portal user cannot see task | `privacy_visibility` too restrictive | Change to `portal` or add user as collaborator |
| Duplicate stages in Kanban | Multiple `project.task.type` records with same name | Deduplicate in **Project → Configuration → Stages** |

---

## Related Documentation

| Type | Link | Description |
|------|------|-------------|
| 🔀 Technical Flow | [Flows/Project/project-creation-flow](Flows/Project/project-creation-flow.md) | Full method chain for project creation — for developers |
| 🔀 Technical Flow | [Flows/Project/task-lifecycle-flow](Flows/Project/task-lifecycle-flow.md) | Full method chain for task lifecycle — for developers |
| 📖 Module Reference | [Modules/Project](Modules/project.md) | Complete field and method list |
| 📋 Related Guide | [Business/HR/leave-management-guide](Business/HR/leave-management-guide.md) | Team availability management |
| 🔧 Patterns | [Patterns/Workflow Patterns](odoo-18/Patterns/Workflow Patterns.md) | Workflow design patterns for stage-based flows |
| 🛠️ Snippets | [Snippets/Model Snippets](odoo-18/Snippets/Model Snippets.md) | Code snippets for Project customization |
| 📋 Related Guide | [Modules/hr_timesheet](Modules/hr_timesheet.md) | Timesheet integration with project |
