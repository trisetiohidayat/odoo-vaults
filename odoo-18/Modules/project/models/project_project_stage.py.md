# Project Project Stage - L3 Documentation

**Source:** `/Users/tri-mac/odoo/odoo18/odoo/addons/project/models/project_project_stage.py`
**Lines:** ~82

---

## Model Overview

`project.project.stage` represents a lifecycle stage for projects (e.g., Planning, In Progress, Completed). This is distinct from task Kanban stages (`project.task.type`).

---

## Fields

| Field | Type | Notes |
|---|---|---|
| `name` | Char | Required; stage name |
| `sequence` | Integer | Sort order |
| `active` | Boolean | Archive/unarchive |
| `mail_template_id` | Many2one | `mail.template`; email sent when project reaches this stage |
| `fold` | Boolean | Folded in Kanban (project considered closed) |
| `company_id` | Many2one | `res.company`; company-specific stages |

---

## Key Methods

### `write(vals)`
**Handles:**
- `company_id` change: validates no projects in this stage have a different company. If so, raises `UserError`.
- `active` change to `False`: archives all projects in this stage.

### `toggle_active()`
**Override:** After `super()` call, checks for inactive projects in the now-active stage.
**If found:** Opens `project.project.stage.delete.wizard` to offer unarchiving.

---

## Company Consistency Validation

When `company_id` is changed on a stage:

```python
project = self.env['project.project'].search([
    '&', ('stage_id', 'in', self.ids),
         ('company_id', '!=', vals['company_id'])
], limit=1)
```

**Raises `UserError` if:** Any project in this stage has a different `company_id` than the target company.

**Rationale:** A stage cannot cover multiple companies' projects.

---

## Edge Cases & Failure Modes

1. **Stage deletion with projects:** Standard `unlink()` raises a `ForeignKey` constraint error if any `project.project` references the stage.
2. **Changing company with projects:** The validation only checks the first project with a mismatched company. If multiple projects have mismatched companies, only the first is reported in the error message.
3. **`fold=True` and project closure:** Setting `fold=True` marks the stage as folded (collapsed) in Kanban. Projects in folded stages are visually grouped as closed.
4. **Archive cascade:** When a stage is deactivated, all projects in it are archived. The unarchive wizard offers to reactivate projects when the stage is reactivated.
5. **No default stages:** Unlike `project.task.type` which has default stages created per user, `project.project.stage` requires manual creation of stages.
6. **Stage without company:** `company_id=False` means the stage is available to all companies. Projects in any company can use this stage.
7. **Multi-company and stage visibility:** A stage with `company_id=A` is only visible/usable by projects in company A. Users from company B cannot see this stage.
