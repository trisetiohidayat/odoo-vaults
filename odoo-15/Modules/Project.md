# Project — Project Management

Dokumentasi Odoo 15 untuk Project module. Source: `addons/project/models/`

## Models

| Model | File | Description |
|---|---|---|
| `project.project` | `project.py` | Project |
| `project.task` | `project_task.py` | Task |
| `project.task.type` | `project_task_type.py` | Stage |
| `project.tags` | `project_tags.py` | Tags |
| `project.analytic.account` | `account_analytic_default.py` | Analytic Account |
| `project.update` | `project_update.py` | Project Update |
| `project.milestone` | `project_milestone.py` | Milestone |

## Project Fields

```python
class Project(models.Model):
    _name = "project.project"
    _description = "Project"
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin', 'rating.parent.mixin']
```

### Key Fields

| Field | Type | Description |
|---|---|---|
| `name` | Char | Project name |
| `description` | Html | Description |
| `active` | Boolean | Active |
| `state` | Selection | Deploy/Rollout (template) |
| `partner_id` | Many2one(res.partner) | Customer |

### Planning Fields

| Field | Type | Description |
|---|---|---|
| `date_start` | Date | Start date |
| `date` | Date | Deadline |
| `close_date` | Date | Closing date |

### Stages & Tasks

| Field | Type | Description |
|---|---|---|
| `type_ids` | Many2many(project.task.type) | Task stages |
| `task_ids` | One2many(project.task) | Tasks |
| `task_count` | Integer | Task count |
| `task_count_with_subtasks` | Integer | Tasks + subtasks |

### Resource Fields

| Field | Type | Description |
|---|---|---|
| `user_id` | Many2one(res.users) | Project Manager |
| `alias_id` | Many2one(mail.alias) | Email alias |
| `privacy_visibility` | Selection | visibility/portal/employees/public |

### Commercial Fields

| Field | Type | Description |
|---|---|---|
| `analytic_account_id` | Many2one(account.analytic.account) | Analytic Account |
| `currency_id` | Many2one(res.currency) | Currency |
| `budget` | Float | Budget |

### Multi-company

| Field | Type | Description |
|---|---|---|
| `company_id` | Many2one(res.company) | Company |
| `favorite_user_ids` | Many2many(res.users) | Favorites |

## Task Fields

```python
class Task(models.Model):
    _name = "project.task"
    _description = "Task"
    _order = "priority desc, sequence, id desc"
```

### Identification Fields

| Field | Type | Description |
|---|---|---|
| `name` | Char | Task name |
| `description` | Html | Description |
| `active` | Boolean | Active |
| `sequence` | Integer | Sequence |
| `priority` | Selection | 0/Normal, 1/High |

### Project & Stage

| Field | Type | Description |
|---|---|---|
| `project_id` | Many2one(project.project) | Project |
| `stage_id` | Many2one(project.task.type) | Stage |
| `parent_id` | Many2one(project.task) | Parent task (subtask) |
| `child_ids` | One2many(project.task) | Subtasks |

### Dates

| Field | Type | Description |
|---|---|---|
| `date_deadline` | Date | Deadline |
| `date_assign` | Datetime | Assigned date |
| `date_end` | Datetime | End date |
| `date_last_stage_update` | Datetime | Last stage change |
| `planned_hours` | Float | Planned hours |
| `date_start` | Date | Start date |

### Resource Assignment

| Field | Type | Description |
|---|---|---|
| `user_id` | Many2one(res.users) | Assigned to |
| `partner_id` | Many2one(res.partner) | Customer contact |
| `email_from` | Char | Email |
| `stage_published` | Boolean | Published in portal |

### Work & Progress

| Field | Type | Description |
|---|---|---|
| `planned_hours` | Float | Estimated hours |
| `late_count` | Integer | Late tasks |
| `effective_hours` | Float | Hours spent |
| `progress` | Float | Progress % |
| `closed` | Boolean | Is closed |

### Milestone

| Field | Type | Description |
|---|---|---|
| `milestone_id` | Many2one(project.milestone) | Milestone |

### Subtask (recursion pattern)

```python
# Task with subtasks
parent_id = fields.Many2one('project.task', 'Parent Task', index=True, ondelete='cascade')
child_ids = fields.One2many('project.task', 'parent_id', 'Sub-tasks')
```

## Task Type (Stage)

```python
class ProjectTaskType(models.Model):
    _name = "project.task.type"
    _description = "Task Stage"
```

### Key Fields

| Field | Type | Description |
|---|---|---|
| `name` | Char | Stage name |
| `sequence` | Integer | Sequence |
| `project_ids` | Many2many(project.project) | Projects (shared stages) |
| `legend_blocked` | Char | Blocked icon |
| `legend_normal` | Char | Normal icon |
| `legend_done` | Char | Done icon |
| `mail_template_id` | Many2one('mail.template') | Mail on stage change |
| `fold` | Boolean | Folded in kanban |
| `is_closed` | Boolean | Is closed stage |

## Project Update

```python
class ProjectUpdate(models.Model):
    _name = "project.update"
    _description = "Project Update"
```

### Key Fields

| Field | Type | Description |
|---|---|---|
| `name` | Char | Update title |
| `project_id` | Many2one(project.project) | Project |
| `status` | Selection | Planned/In Progress/Launched/Ended |
| `progress` | Float | Progress % (0-100) |
| `description` | Html | Update body |
| `date` | Date | Date of update |

## Rating Mixin

```python
# Both project and task inherit from rating.parent.mixin / rating.mixin
class RatingMixin(models.AbstractModel):
    _name = "rating.parent.mixin"
    rating_ids = fields.One2many('rating.rating', 'res_id',
        domain=lambda self: [('res_model', '=', self._name)])
```

## Action Methods

```python
# Task actions
def action_assign_to_me(self):
    """Assign task to current user"""
    self.write({'user_id': self.env.uid})

def action_close_dialog(self):
    """Close task (mark done)"""
    return {
        'name': _('Close Task'),
        'type': 'ir.actions.act_window',
        'res_model': 'project.task.closed',
        'view_mode': 'form',
        'target': 'new',
    }

def action_recurring_dialog(self):
    """Create recurring tasks"""
    ...
```

## See Also
- [Modules/Sale](Sale.md) — Sale Project
- [Modules/Project](Project.md) — Timesheet integration
- [Modules/CRM](CRM.md) — Project from opportunity
- [Modules/HR](Modules/hr.md) — Employee timesheets