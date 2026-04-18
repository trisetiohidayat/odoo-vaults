---
title: HR Gamification
description: Bridge module connecting the Gamification framework with the HR module. Enables HR officers to create challenges, goals, and grant badges to employees rather than just generic users.
tags: [odoo19, hr, gamification, badge, challenge, goal, employee, module]
model_count: 5
models:
  - hr.employee
  - hr.employee.public
  - gamification.badge.user
  - gamification.badge
  - res.users
dependencies:
  - gamification
  - hr
category: Human Resources
source: odoo/addons/hr_gamification/
created: 2026-04-14
uuid: e5f6a7b8-c9d0-1234-ef01-345678901234
---

# HR Gamification

## Overview

**Module:** `hr_gamification`
**Category:** Human Resources
**Depends:** `gamification`, `hr`
**Auto-install:** True
**License:** LGPL-3
**Author:** Odoo S.A.
**Module directory:** `odoo/addons/hr_gamification/`

`hr_gamification` bridges the Odoo Gamification framework with the Human Resources module, enabling HR officers to manage employee engagement through challenges, goals, and badges -- not just for generic portal users, but specifically for employees on the HR roster.

The module makes three fundamental changes to the gamification ecosystem:

1. **Employees can receive badges**: HR officers can grant recognition badges to employees through the employee form, not just through the gamification dashboard.
2. **Employee goals are tracked**: HR-specific challenges create goals linked to the employee's user account, visible on the employee profile.
3. **Badge visibility on employee profiles**: The employee public form and internal form both display a "Badges" page showing all badges received by the employee.

The module extends four models and creates two menu items in the HR configuration menu. It does not create new business logic for gamification itself -- it only wires the existing gamification infrastructure to the HR data model.

## Module Structure

```
hr_gamification/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── gamification.py           # gamification.badge.user and gamification.badge extensions
│   ├── hr_employee.py            # hr.employee extension with badge and goal fields
│   ├── hr_employee_public.py     # hr.employee.public extension (public badge display)
│   └── res_users.py             # res.users extension (goal and badge links)
├── views/
│   ├── gamification_views.xml    # Badge form, employee list action, menu items
│   └── hr_employee_views.xml     # Badges page on employee form and public form
├── wizard/
│   └── gamification_badge_user_wizard_views.xml  # Badge grant wizard (employee-aware)
└── security/
    ├── gamification_security.xml  # Record rules for challenge/goals visibility
    └── ir.model.access.csv        # ACL entries for gamification models in HR context
```

## Dependency Chain

```
hr_gamification
├── gamification           # Core gamification: badges, challenges, goals, leaderboards
│   └── base              # Odoo base module
└── hr                   # Human resources: employees, departments, contracts
    └── res_users        # User management
        └── base          # Odoo base module
```

The module sits at the intersection of two substantial systems. `gamification` defines the badge/challenge/goal infrastructure; `hr` provides the employee data model. This module connects them so that badges and challenges can target employees.

## The Gamification Framework (from gamification)

To understand this module, it is essential to know what `gamification` provides.

### Core Models in gamification

| Model | Description |
|-------|-------------|
| `gamification.badge` | Badge definitions: name, description, image, challenge rules |
| `gamification.badge.user` | A badge granted to a user: badge + user + comment + date |
| `gamification.challenge` | A challenge: a set of goals assigned to users |
| `gamification.goal` | A single measurable goal for a user: definition, value, state |

### The Badge Flow

```
1. HR officer creates a badge (gamification.badge) with name, image, description
      ↓
2. HR officer or manager grants badge to employee (gamification.badge.user)
      → Linked to hr.employee via employee_id field
      → Also linked to res.users via user_id field
      → Comment explains what the employee did
      ↓
3. Badge appears on:
      → Employee profile (hr_gamification)
      → Employee public profile (hr_gamification)
      → Gamification dashboard (gamification)
      → User's Discuss channel (mail)
      ↓
4. Gamification tracks badges per user for leaderboards and achievements
```

### The Challenge/Goal Flow

```
1. HR officer creates a challenge (gamification.challenge) with challenge_category='hr'
      → Sets challenge period (ongoing, monthly, weekly)
      → Defines participant scope (specific employees or user groups)
      ↓
2. Challenge generates goals (gamification.goal) for each participant
      → Goals have definitions: "Complete 5 training courses", "Log 100% timesheet"
      → Goals have states: draft, in_progress, reached, cancelled
      ↓
3. Employees see their goals in:
      → Employee profile (hr_gamification adds badge_ids page)
      → Personal dashboard (gamification)
      ↓
4. When goals are reached:
      → Badges can be automatically granted (defined in challenge)
      → Leaderboard updates
```

## Models

### `hr.employee` (extends `hr.employee`)

**File:** `models/hr_employee.py`

The `hr.employee` model is extended with computed fields that aggregate gamification data.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `goal_ids` | One2many (computed) | Employee HR goals, filtered by `challenge_category = 'hr'` |
| `badge_ids` | One2many (computed) | All badges linked to the employee (directly or via user) |
| `has_badges` | Boolean (computed) | Whether the employee has any badges |
| `direct_badge_ids` | One2many | Badges directly linked to the employee (not via user) |

#### `_compute_employee_goals()`

```python
@api.depends('user_id.goal_ids.challenge_id.challenge_category')
def _compute_employee_goals(self):
    for employee in self:
        employee.goal_ids = self.env['gamification.goal'].search([
            ('user_id', '=', employee.user_id.id),
            ('challenge_id.challenge_category', '=', 'hr'),
        ])
```

**Purpose:** Finds all gamification goals linked to the employee's user account where the challenge category is 'hr'.

**Dependencies:** The `@api.depends` on `'user_id.goal_ids.challenge_id.challenge_category'` ensures the goals are re-computed whenever any of those fields change -- including when the employee is linked to a different user.

**Why filter by `challenge_category = 'hr'`?**
The `gamification` module uses `challenge_category` to classify challenges into different domains (e.g., 'hr', 'sales', 'gamification'). HR-specific challenges have `challenge_category = 'hr'`. Without this filter, the employee would see all goals across all challenge categories, including sales goals they should not have.

#### `_compute_employee_badges()`

```python
@api.depends('direct_badge_ids', 'user_id.badge_ids.employee_id')
def _compute_employee_badges(self):
    for employee in self:
        badge_ids = self.env['gamification.badge.user'].search([
            '|', ('employee_id', 'in', employee.ids),
                 '&', ('employee_id', '=', False),
                      ('user_id', 'in', employee.user_id.ids)
        ])
        employee.has_badges = bool(badge_ids)
        employee.badge_ids = badge_ids
```

**Purpose:** Finds all badges linked to the employee through either a direct `employee_id` link or through the employee's user account.

**Domain logic breakdown:**

| Condition | Meaning |
|-----------|---------|
| `('employee_id', 'in', employee.ids)` | Badges directly granted to this employee |
| `('employee_id', '=', False)` | Badges where `employee_id` is not set |
| `('user_id', 'in', employee.user_id.ids)` | Badges granted to the employee's linked user |

The OR domain `'|', A, '&', B, C` evaluates as: (A) OR (B AND C). This means:
- Include badges directly assigned to this employee.
- Include badges assigned to the employee's user account where no employee is specified.

**Why the second condition?**
Some gamification users may not have an employee record (e.g., external consultants, board members). If they receive a badge without an `employee_id`, the badge is linked only to `user_id`. This search catches those badges too.

#### `direct_badge_ids` vs `badge_ids`

| Field | What it includes | Who can see it |
|-------|-----------------|---------------|
| `direct_badge_ids` | Badges with `employee_id = self` | HR users only (group: `hr.group_hr_user`) |
| `badge_ids` (computed) | Direct badges + user badges | HR users only |
| `has_badges` | Boolean flag | HR users only |

The `direct_badge_ids` field has `groups="hr.group_hr_user"`, meaning only HR officers see it. Regular managers do not have access.

### `hr.employee.public` (extends `hr.employee.public`)

**File:** `models/hr_employee_public.py`

The public employee model is a read-only view of employee data intended for portal users. It is exposed through the website portal. This extension adds badge display to the public employee profile.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `badge_ids` | One2many (computed) | Public badge display for portal users |
| `has_badges` | Boolean (computed) | Whether the employee has badges |

#### `_compute_badge_ids()` and `_compute_has_badges()`

```python
def _compute_badge_ids(self):
    self._compute_from_employee('badge_ids')

def _compute_has_badges(self):
    self._compute_from_employee('has_badges')
```

**Purpose:** Delegates badge computation to the `_compute_from_employee()` method, which is a helper in the `hr.employee.public` model that computes fields from the related `hr.employee` record.

**Why `_compute_from_employee`?**
The `hr.employee.public` model is not a real database table -- it is a view that reads from `hr.employee` with a different access policy. It does not have direct field storage. The `_compute_from_employee()` helper maps public fields to their employee counterparts.

**Portal user visibility:** If an employee is published on the portal, portal users can see their badges. This creates a public-facing achievement display for employees.

### `gamification.badge.user` (extends `gamification.badge.user`)

**File:** `models/gamification.py`

This model represents a badge that has been granted to a specific user. The extension adds an `employee_id` link and access control.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `employee_id` | Many2one | Linked HR employee |
| `has_edit_delete_access` | Boolean (computed) | Whether the current user can edit or delete this badge grant |

#### `_check_employee_related_user()` constraint

```python
@api.constrains('employee_id')
def _check_employee_related_user(self):
    for badge_user in self:
        if badge_user.employee_id and badge_user.employee_id not in badge_user.user_id\
            .with_context(allowed_company_ids=badge_user.user_id.company_ids.ids).employee_ids:
            raise ValidationError(_('The selected employee does not correspond to the selected user.'))
```

**Purpose:** Ensures the badge's `employee_id` and `user_id` are consistent. An employee can only be linked to a badge if that employee is linked to the badge's user account.

**Business logic:** An employee record (`hr.employee`) is linked to a user account (`res.users`) via the `user_id` field on `hr.employee`. If `employee_id` is set on a badge, it must belong to the same employee that `user_id.employee_ids` returns.

**Multi-company context:** The check uses `with_context(allowed_company_ids=badge_user.user_id.company_ids.ids)` to ensure company-based employee restrictions are respected.

#### `_compute_has_edit_delete_access()`

```python
def _compute_has_edit_delete_access(self):
    is_hr_user = self.env.user.has_group('hr.group_hr_user')
    for badge_user in self:
        badge_user.has_edit_delete_access = is_hr_user or self.env.uid == self.create_uid.id
```

**Purpose:** Determines whether the current user can edit the badge grant (change the comment) or delete it.

| Condition | Can edit/delete? |
|-----------|-----------------|
| Current user is in HR group | Yes |
| Current user created the badge grant | Yes |
| Any other user | No |

This allows the badge granter (whoever created the `badge_user` record) to edit the comment, while HR officers have full control.

#### `action_open_badge()`

```python
def action_open_badge(self):
    self.ensure_one()
    return {
        'name': _('Received Badge'),
        'type': 'ir.actions.act_window',
        'res_model': 'gamification.badge.user',
        'res_id': self.id,
        'target': 'new',
        'view_mode': 'form',
        'view_id': self.env.ref("hr_gamification.view_current_badge_form").id,
        'context': {"dialog_size": "medium"},
    }
```

**Purpose:** Opens the badge grant form in a dialog from the employee profile kanban card.

**Use:** Called from the kanban view of badge_ids on the employee form. When an HR officer clicks a badge in the employee's badges page, this action opens the badge grant form in a popup dialog (`target='new'`).

#### `_notify_get_recipients_groups()`

```python
def _notify_get_recipients_groups(self, message, model_description, msg_vals=False):
    groups = super()._notify_get_recipients_groups(message, model_description, msg_vals)
    self.ensure_one()
    base_url = self.get_base_url()
    for group in groups:
        if group[0] == 'user':
            if self.employee_id:
                employee_form_url = (
                    f"{base_url}/web#action=hr.hr_employee_public_action"
                    f"&id={self.employee_id.id}&open_badges_tab=true&user_badge_id={self.id}"
                )
                group[2]['button_access'] = {
                    'url': employee_form_url,
                    'title': _('View Your Badge'),
                }
                group[2]['has_button_access'] = True
            else:
                group[2]['has_button_access'] = False
    return groups
```

**Purpose:** When a badge is granted and the notification message is sent, this method customizes the notification's action button.

**What it does:**
- If the badge is linked to an employee, the notification includes a "View Your Badge" button that opens the employee profile with the badges tab active.
- If the badge has no employee, the button is disabled (fallback to the generic badge view).
- The URL includes `open_badges_tab=true` and `user_badge_id={self.id}` as query parameters so the form can highlight the specific badge.

### `gamification.badge` (extends `gamification.badge`)

**File:** `models/gamification.py`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `granted_employees_count` | Integer (computed) | Count of employees (not just users) who received this badge |

#### `_compute_granted_employees_count()`

```python
@api.depends('owner_ids.employee_id')
def _compute_granted_employees_count(self):
    user_count = dict(
        self.env['gamification.badge.user']._read_group(
            [('badge_id', 'in', self.ids), ('employee_id', '!=', False)],
            ['badge_id'], ['__count'],
        ),
    )
    for badge in self:
        badge.granted_employees_count = user_count.get(badge._origin, 0)
```

**Purpose:** Counts how many employees have received each badge. This is different from `granted_count` (from the base `gamification` module) because that counts all users, including those without an employee record.

**Why this distinction matters:**
A badge might be granted to 50 users total, but only 30 of them have employee records. HR officers want to see the 30-employee count. The `hr_gamification` module provides this metric.

#### `get_granted_employees()`

```python
def get_granted_employees(self):
    employee_ids = self.mapped('owner_ids.employee_id').ids
    return {
        'type': 'ir.actions.act_window',
        'name': 'Granted Employees',
        'view_mode': 'kanban,list,form',
        'res_model': 'hr.employee.public',
        'domain': [('id', 'in', employee_ids)]
    }
```

**Purpose:** Returns a window action that opens the list of employees who have been granted this badge.

**Target model:** `hr.employee.public` -- the public-facing employee view. This allows both internal HR users and portal users to see which employees have a specific badge.

### `res.users` (extends `res.users`)

**File:** `models/res_users.py`

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `goal_ids` | One2many | All gamification goals for this user |
| `badge_ids` | One2many | All badge grants for this user |

These fields mirror the gamification module's goal/badge links on the user model. The `hr_gamification` module explicitly redefines them to ensure they are accessible in the HR context.

## Views

### Employee Form View Modification

**File:** `views/hr_employee_views.xml`

```xml
<xpath expr="//page[@name='hr_settings']" position="before">
    <page string="Badges" name="received_badges" invisible="not user_id">
        <field name="has_badges" invisible="1"/>
        <!-- Empty state -->
        <div class="o_field_nocontent" invisible="has_badges">
            <p class="o_view_nocontent_neutral_face"></p>
            <p>There are no badges for this employee.<br/>It's time to allow the first one.</p>
        </div>
        <!-- Badge kanban + grant button -->
        <div class="mt-2">
            <field name="badge_ids" mode="kanban"/>
            <div class="d-flex justify-content-center">
                <button class="mt-2 grant_badge_btn" string="Grant a Badge"
                        type="action" name="%(action_reward_wizard)d"/>
            </div>
        </div>
    </page>
</xpath>
```

**Location:** Inserted before the "HR Settings" page on the employee form.

**Visibility condition:** `invisible="not user_id"` -- the page is only shown if the employee has a linked user account. Employees without user accounts (e.g., contractors) cannot receive badges through this interface.

**Empty state:** A friendly empty state message is shown when `has_badges` is False, encouraging the HR officer to grant the first badge.

**Content:**
- A kanban view of `badge_ids` showing badge images, names, grant dates, and granters.
- A "Grant a Badge" button that opens the badge wizard.

### Employee Public Form View Modification

```xml
<page name="resume" position="after">
    <page string="Badges" name="received_badges" invisible="not user_id">
        <!-- Same empty state and kanban as above -->
        <field name="badge_ids" mode="kanban" widget="many2many"/>
        <button class="mt-2 grant_badge_btn" string="Grant a Badge"
                type="action" name="%(action_reward_wizard)d"/>
    </page>
</xpath>
```

**Location:** After the "Resume" page on the public employee form (used in the portal).

**Note:** The "Grant a Badge" button is visible on the public form too. Clicking it as a portal user would typically trigger access control (portal users cannot grant badges), but the button is present for internal HR users accessing the public form.

### Badge Form Action and View

The module defines two views and one action for the badge grant dialog:

**Badge form view (`view_current_badge_form`):**
- Shows badge image, name, and grant details.
- Comment field (editable if `has_edit_delete_access`).
- Grant date and granter.
- Delete button (if `has_edit_delete_access`).

**Grant badge wizard action (`action_reward_wizard`):**
- Opens as a dialog with context `{'default_employee_id': active_id}`.
- The wizard shows a badge selector and comment field.
- On confirmation, creates a `gamification.badge.user` record with `employee_id` set.

### Gamification Action Views

**File:** `views/gamification_views.xml`

The module creates dedicated actions and menu items for HR gamification:

| Action | Model | Domain | Purpose |
|--------|-------|--------|---------|
| `challenge_list_action2` | `gamification.challenge` | `challenge_category = 'hr'` | View HR-specific challenges |
| `goals_menu_groupby_action2` | `gamification.goal` | `challenge_category = 'hr'` | View HR goal history |
| Badge list action (from gamification) | `gamification.badge` | None | View all badges |

Menu items under **HR > Configuration > Challenges**:
- Badges (links to gamification's badge list)
- Challenges (links to HR challenges action)
- Goals History (links to HR goals action)

### Badge Kanban on Form

The `badge_ids` field uses kanban mode (`mode="kanban"`) on the employee form. This displays badge cards in a kanban board layout, showing:
- Badge image (avatar)
- Badge name
- Grant date
- Granting user

Clicking a badge card opens the badge grant form in a dialog via `action_open_badge()`.

## Wizard: Granting Badges to Employees

**File:** `wizard/gamification_badge_user_wizard_views.xml`

### Badge Grant Wizard Form

```xml
<form string="Reward Employee with">
    <field name="employee_id" invisible="1"/>
    <field name="user_id" invisible="1"/>
    <group>
        <group colspan="9">
            <div>
                <div class="mb-3 mt-1">What are you thankful for?</div>
                <field colspan="6" name="badge_id" nolabel="1"
                       domain="[('rule_auth','!=','nobody')]"/>
            </div>
        </group>
        <group colspan="3">
            <field name="badge_id" nolabel="1" class="oe_avatar m-0"
                    widget="image" options="{'preview_image': 'image_1024'}"/>
        </group>
    </group>
    <field name="comment" nolabel="1"
           placeholder="Describe what they did and why it matters (will be public)"/>
    <footer>
        <button string="Grant a badge" type="object" name="action_grant_badge"
                class="btn-primary" data-hotkey="q"/>
        <button string="Discard" special="cancel" data-hotkey="x" class="btn-secondary"/>
    </footer>
</form>
```

**Key features:**
- **Employee context:** The wizard is opened from the employee form, so `employee_id` is pre-set in context and hidden.
- **Badge selector:** A badge field (`badge_id`) with domain `[('rule_auth','!=','nobody')]` -- excludes badges that are auto-granted only (no manual awarding allowed).
- **Badge preview:** Avatar widget showing the selected badge's image.
- **Comment field:** A free-text field for describing what the employee did. The comment is stored on the `gamification.badge.user` record and is shown to the recipient.
- **Hotkeys:** `q` to grant, `x` to cancel.

### Wizard Action

```xml
<record id="action_reward_wizard" model="ir.actions.act_window">
    <field name="name">Grant a badge</field>
    <field name="res_model">gamification.badge.user.wizard</field>
    <field name="view_mode">form</field>
    <field name="view_id" ref="view_badge_wizard_reward"/>
    <field name="target">new</field>
    <field name="context">{'default_employee_id': active_id, 'employee_id': active_id}</field>
</record>
```

**Context:** `default_employee_id` and `employee_id` are set from the active employee (`active_id` from the employee form). The wizard model (`gamification.badge.user.wizard` from the `gamification` module) uses this to create the badge grant with the correct `employee_id`.

## Security

### Access Control List (ir.model.access.csv)

**File:** `security/ir.model.access.csv`

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
challenge_officer,Challenge Officer,gamification.model_gamification_challenge,hr.group_hr_user,1,1,1,1
challenge_line_officer,Challenge Line Officer,gamification.model_gamification_challenge_line,hr.group_hr_user,1,1,1,1
badge_officer,Badge Officer,gamification.model_gamification_badge,hr.group_hr_user,1,1,1,1
badge_user_officer,Badge-user Officer,gamification.model_gamification_badge_user,hr.group_hr_user,1,1,1,1
badge_base_user,Badge-user Employee,model_gamification_badge_user,base.group_user,1,1,1,1
```

**Key points:**

| ACL | Group | Permissions | Purpose |
|-----|-------|-------------|---------|
| `challenge_officer` | `hr.group_hr_user` | CRUD | HR users can manage HR challenges |
| `badge_officer` | `hr.group_hr_user` | CRUD | HR users can create and manage badges |
| `badge_user_officer` | `hr.group_hr_user` | CRUD | HR users can manage badge grants |
| `badge_base_user` | `base.group_user` | CRUD | All users can read/create badge grants (self-grant limited by `rule_auth`) |

### Record Rules

**File:** `security/gamification_security.xml`

The module adds record rules that restrict access to challenges and goals based on the `challenge_category` field:
- Challenges with `challenge_category = 'hr'` are accessible to HR users.
- Goals linked to HR challenges are accessible to HR users.
- Goals linked to employees in the user's department may have additional rules.

## Extension Points

| Extension Point | How |
|----------------|-----|
| Add new badge criteria | Extend `_check_employee_related_user()` or add constraints on `gamification.badge.user` |
| Custom badge grant flow | Override `action_grant_badge()` in the wizard model |
| Add badge categories | Add new `challenge_category` values and filter `_compute_employee_goals()` |
| Extend badge display | Override the kanban template for `badge_ids` in the employee form |
| Add badge approval workflow | Add a state field and approval steps to `gamification.badge.user` |
| Add badge analytics | Create a `report.gamification.badge` model for badge statistics |

## Common Use Cases

### Use Case 1: Employee Recognition Program

```
Company runs a monthly "Star Employee" recognition program:
  1. HR creates a "Star Employee" badge in gamification
  2. HR creates a monthly challenge with goal: "Demonstrate company values"
  3. Managers submit nominations (via gamification or custom module)
  4. HR grants the badge to the nominated employee
  5. Badge appears on employee's internal and public profile
  6. Monthly leaderboard in gamification dashboard shows top badge earners
```

### Use Case 2: Training Completion Rewards

```
Company incentivizes training completion:
  1. HR creates a challenge with challenge_category = 'hr'
  2. Challenge goals: Complete training courses from hr_course module
  3. When an employee completes a course (trigger from hr_course):
     → Goal is updated to 'reached'
     → Badge is automatically granted
  4. Employee sees badge and goal progress on their profile
  5. Gamification tracks completion rates for management reporting
```

### Use Case 3: Performance Milestone Badges

```
Quarterly performance milestones:
  1. HR creates milestone badges (e.g., "Q1 Achiever", "Top Performer")
  2. Badges are granted manually by HR based on performance reviews
  3. The _notify_get_recipients_groups() customization ensures:
     → Email notification includes a "View Badge" button
     → Button links directly to the employee profile with badges tab open
  4. Public-facing employee profiles on the portal show these badges
```

## Related

- [Modules/gamification](gamification.md) -- Core gamification: badges, challenges, goals, leaderboards
- [Modules/HR](HR.md) -- Core HR module: employees, departments, contracts, org chart
- [Modules/hr_skills](hr_skills.md) -- HR Skills: resume lines, skills tracking
- [Modules/hr_skills_event](hr_skills_event.md) -- HR Skills Event: onsite training resume lines
- [Modules/hr_skills_survey](hr_skills_survey.md) -- HR Skills Survey: certification resume lines
- [Modules/mail](mail.md) -- Messaging: Discuss channels, notifications for badge grants
