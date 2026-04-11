# Project Collaborator - L3 Documentation

**Source:** `/Users/tri-mac/odoo/odoo18/odoo/addons/project/models/project_collaborator.py`
**Lines:** ~58

---

## Model Overview

`project.collaborator` represents a portal partner's access to a project via Project Sharing. When a collaborator is added to a project, they can access the project and its tasks (subject to `limited_access`).

---

## Fields

| Field | Type | Notes |
|---|---|---|
| `project_id` | Many2one | `project.project`; target project. Domain: `privacy_visibility='portal'` |
| `partner_id` | Many2one | `res.partner`; collaborator |
| `partner_email` | Char | Related email from `partner_id.email` |
| `limited_access` | Boolean | Restrict to only tasks explicitly shared with this collaborator |

---

## SQL Constraints

```python
UNIQUE(project_id, partner_id)
```
A partner cannot be added twice as a collaborator on the same project.

---

## Key Methods

### `_compute_display_name()`
Returns: `"{project_name} - {partner_name}"`

### `create(vals_list)`
**Special behavior:** On creation of the first collaborator:
1. Calls `_toggle_project_sharing_portal_rules(True)` to enable portal access.
**This activates the Project Sharing feature for the first time.**

### `unlink()`
**Special behavior:** On deletion of the last collaborator:
1. Calls `_toggle_project_sharing_portal_rules(False)` to disable portal access.
**This deactivates Project Sharing when no collaborators remain.**

### `_toggle_project_sharing_portal_rules(active)`
Enables or disables the Project Sharing feature by toggling ACL and ir.rule records.

**Toggled records:**
1. `project.access_project_sharing_task_portal` — access control list for portal task access.
2. `project.project_task_rule_portal_project_sharing` — record rule for portal task visibility.

**Critical:** Both records are security-critical. Disabling them revokes portal access to project tasks.

---

## Edge Cases & Failure Modes

1. **Adding the same collaborator twice:** The `UNIQUE(project_id, partner_id)` constraint prevents duplicates. The second `create()` raises a unique constraint violation error.
2. **Collaborator on non-portal project:** `project_id` domain restricts to `privacy_visibility='portal'`. Collaborators cannot be added to non-portal projects.
3. **Project Sharing ACL activation:** The ACL and rule are shared (singular) resources. If they are deleted independently of this model, `_toggle_project_sharing_portal_rules()` will raise an `AccessError` when trying to write to them.
4. **Last collaborator deletion:** Only the actual last collaborator triggers deactivation. If collaborators are deleted one by one, the feature stays active until the final one is removed.
5. **`limited_access=True`:** The actual access restriction logic is implemented in `ir.rule` definitions on `project.task`, not in this model. This model only stores the flag.
6. **Partner without user:** A collaborator partner can exist without an associated portal user. In this case, the collaborator record exists but the partner cannot log in until a user is created for them.
7. **Multi-company:** Collaborator access may be restricted by company rules on the project. A collaborator in company A cannot access a project in company B.
8. **Partner email changes:** `partner_email` is a related field. If the partner's email changes, the collaborator's `partner_email` updates automatically. The access token-based portal link uses the partner's email.
