---
Module: hr_livechat
Version: Odoo 18
Type: Integration
Tags: #hr #livechat #im #discuss #integration
Related Modules: hr, im_livechat, discuss
---

# hr_livechat — HR Live Chat Integration

**Addon Key:** `hr_livechat`
**Depends:** `hr`, `im_livechat`
**Auto-install:** `True`
**Category:** Human Resources
**License:** LGPL-3

## Purpose

`hr_livechat` bridges the **HR** and **Livechat** modules. It links livechat operators to `hr.employee` records and adds a **"My Team"** filter to the livechat session list so that operators can view sessions from employees in their department.

The module does **not** add new fields to `hr.employee` or create new models. Instead it:
1. Adds a "My Team" filter to `discuss.channel` (livechat sessions) by joining through the operator's employee record → department → manager
2. Can implicitly link livechat operators to employees (via `res.partner` → `hr.employee` through `work_contact_id`)

---

## Models Extended

### `im_livechat.channel` (via `discuss.channel` search view)

**Base model:** `discuss.channel`
**View extended:** `im_livechat.discuss_channel_view_search`

#### Filter Added

```xml
<filter name="filter_my_team"
    domain="[('channel_member_ids.partner_id.user_ids.employee_id.member_of_department', '=', True)]"
    string="My Team"/>
```

**Domain logic:**
```
discuss.channel
    └── channel_member_ids (discuss.channel.member)
            └── partner_id (res.partner)
                └── user_ids (res.users)
                    └── employee_id (hr.employee)
                        └── member_of_department (computedBoolean from hr.employee)
```

`member_of_department` is a computed boolean field on `hr.employee` (in the `hr` module) that checks if the employee is a member of a department where the current user (`uid`) is the manager.

This filter shows only livechat sessions where at least one channel member belongs to a department managed by the current user.

**Note:** `hr_livechat` has no Python model files — all logic is expressed as an XML domain filter on the search view. There is no `models/` directory in this module.

---

### `hr.employee` — Implicit Link

`hr_livechat` does not extend `hr.employee` with new fields. The implicit link to livechat is:

```
hr.employee
    └── work_contact_id (res.partner)  ← inherited from hr
            └── user_ids (res.users)
                    └── livechat_username (res.users field: user_livechat_username)
                            └── used in discuss.channel.livechat_operator_id
```

This means an employee who has a user account with a `user_livechat_username` set can receive livechat sessions routed to them.

The `im_livechat` module's `discuss.channel` model has:
```python
livechat_operator_id = fields.Many2one('res.partner', string='Operator', index='btree_not_null')
# SQL constraint:
# CHECK((channel_type = 'livechat' and livechat_operator_id is not null)
#       or (channel_type != 'livechat'))
```

The operator is a `res.partner`, not an `hr.employee` directly. The bridge through `hr_livechat` allows the system to navigate from a livechat session → operator partner → user → employee → department → manager for access control filtering.

---

## L4 — How Operator Identification Works

### Livechat Session Routing Flow

```
Customer starts livechat
    → im_livechat.channel (queue/bot rules)
        → assigns livechat_operator_id (res.partner)
            → discuss.channel created
                → channel.livechat_operator_id = operator_partner
                → channel.livechat_channel_id = channel_rule.channel_id
```

### The "My Team" Filter Explained

The domain `('channel_member_ids.partner_id.user_ids.employee_id.member_of_department', '=', True)` works as follows:

1. **Start from `discuss.channel`** (the livechat session record)
2. **Follow `channel_member_ids`** → all channel members (operator + visitor are members)
3. **Filter to `partner_id`** → the partner record of each member
4. **Through `user_ids`** → the system user linked to each partner
5. **To `employee_id`** → the HR employee record linked to that user
6. **Check `member_of_department`** → a computed boolean on `hr.employee` that is `True` when:
   - The employee belongs to a department
   - And the current user (`uid`) is the manager of that department

This filter is therefore **context-sensitive to the current user**: an HR manager will see sessions from their team; other users will see no results.

### How `member_of_department` Works (from `hr` module)

The field `member_of_department` on `hr.employee` (computed in `hr.models.HrEmployeeBase`):
```python
def _compute_member_of_department(self):
    ...
    department_managed_by_uid = self.department_id.manager_id.user_id == self.env.user
    ...
```

It is true when the employee's department manager is the current user.

### Operator Avatar and Name in Livechat

In `im_livechat`, the livechat session view shows:
- `channel.livechat_operator_id.name` or `channel.livechat_operator_id.user_livechat_username`
- Avatar from `livechat_operator_id`

The operator's `user_livechat_username` is the public-facing name shown to website visitors. It is set on `res.users`, which is linked to the employee's user account.

---

## Key Design Notes

- **`hr_livechat` is thin by design.** It contains no Python model code, no computed fields, and no controllers. Its sole purpose is to add the XML filter and implicitly document the `employee ↔ livechat` relationship.
- The module is `auto_install: True` so that when both `hr` and `im_livechat` are installed, the team-filter appears automatically.
- The "My Team" filter does **not** grant any new access rights — it only filters the list view. Access to livechat sessions is controlled by the `im_livechat` and `discuss` access rules.
- No changes are made to the livechat operator selection logic — routing is still handled entirely by `im_livechat.channel` rules.

---

## File Reference

| File | Purpose |
|------|---------|
| `__manifest__.py` | Module declaration; depends on `hr` + `im_livechat`; auto_install |
| `views/discuss_channel_views.xml` | Extends `im_livechat.discuss_channel_view_search` with "My Team" filter |
| `i18n/` | Full i18n translations (26+ languages) |