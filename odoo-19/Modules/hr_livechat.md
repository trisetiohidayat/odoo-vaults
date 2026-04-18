---
type: module
module: hr_livechat
tags: [odoo, odoo19, hr, livechat, im_livechat, crm, reporting]
created: 2026-04-06
uuid: f6a7b8c9-0d1e-2345-efab-123456789bcd
---

# HR Livechat

## Overview

| Property | Value |
|----------|-------|
| **Name** | HR - Livechat |
| **Technical** | `hr_livechat` |
| **Category** | Human Resources |
| **Depends** | `hr`, `im_livechat` |
| **Version** | 1.0 |
| **License** | LGPL-3 |
| **Auto-install** | True |

## What It Does

`hr_livechat` is a bridge module that connects the [Modules/im_livechat](Modules/im_livechat.md) live chat system with the [Modules/HR](Modules/HR.md) employee management module. It does not add any Python model code. Instead, it extends three search view XML definitions to add a **"My Team" filter** to each view. This filter allows HR managers and team leaders to narrow the livechat session list to show only sessions handled by employees who are members of their department -- enabling team-level performance reporting on livechat activity without exposing all employees' livechat statistics.

The module is `auto_install: True`. When a database has both `hr` and `im_livechat` installed but not `hr_livechat`, Odoo automatically installs it to provide the team-scoped filtering capability.

## Module Structure

```
hr_livechat/
├── __init__.py                        # Empty -- no Python code
├── __manifest__.py                    # Metadata: depends hr + im_livechat
├── models/
│   └── im_livechat_channel.py         # Empty __init__ + this file (no model additions)
└── views/
    ├── discuss_channel_views.xml                # Adds "My Team" filter to discuss.channel search
    ├── im_livechat_channel_member_history_views.xml   # Adds "My Team" filter to member history search
    └── im_livechat_report_channel_views.xml            # Adds "My Team" filter to livechat report search
```

### `__manifest__.py`

```python
{
    'name': 'HR - Livechat',
    'version': '1.0',
    'category': 'Human Resources',
    'description': """
Bridge between HR and Livechat.""",
    'depends': ['hr', 'im_livechat'],
    'data': [
        'views/discuss_channel_views.xml',
        'views/im_livechat_channel_member_history_views.xml',
        'views/im_livechat_report_channel_views.xml',
    ],
    'auto_install': True,
    'author': 'Odoo S.A.',
    'license': 'LGPL-3',
}
```

Note that there is no `security/` directory. The module does not add any ACL records because it does not introduce new models -- it merely extends the search domains of existing views. Access control for livechat and HR data is managed entirely by the base `im_livechat` and `hr` modules.

## The Core Concept: Linking Livechat to Employees

Before diving into the view extensions, it is important to understand the data model relationship between livechat sessions and employees.

### Data Model (from `im_livechat`)

```
discuss.channel
  └── channel_member_ids — One2many → discuss.channel.member
        └── partner_id — Many2one → res.partner
              └── user_ids — One2many → res.users
                    └── employee_id — Many2one → hr.employee
                          └── department_id — Many2one → hr.department
```

The chain is:
1. A **livechat session** is a `discuss.channel` with `channel_type = 'livechat'`.
2. The session has **members** (both the customer and the operator) stored in `discuss.channel.member`.
3. The **operator** (the internal user handling the chat) is linked through:
   - `discuss.channel.member.partner_id` -> `res.partner`
   - `res.partner.user_ids` -> `res.users`
   - `res.users.employee_id` -> `hr.employee`
   - `hr.employee.department_id` -> `hr.department`

This multi-step chain is what the "My Team" filter uses to determine whether a livechat session belongs to the current user's team.

### `im_livechat_channel` Model (Empty Extension)

The `models/im_livechat_channel.py` file exists but is empty (the module has no Python model code). The presence of the `models/` directory structure is a convention for Odoo modules that plan to add Python code, but `hr_livechat` achieves its goals entirely through XML view modifications.

## View Extensions

All three view extensions add the same pattern: a named filter called **"My Team"** that uses a domain to restrict records to sessions handled by employees in the current user's department.

### 1. Discuss Channel Search View

**File:** `views/discuss_channel_views.xml`

```xml
<record id="discuss_channel_view_search" model="ir.ui.view">
    <field name="name">discuss.channel.search.inherit.hr.livechat</field>
    <field name="model">discuss.channel</field>
    <field name="inherit_id" ref="im_livechat.discuss_channel_view_search"/>
    <field name="arch" type="xml">
        <xpath expr="//*[@name='filter_my_sessions']" position="after">
            <filter name="filter_my_team"
                domain="[('channel_member_ids.partner_id.user_ids.employee_id.member_of_department', '=', True)]"
                string="My Team"/>
        </xpath>
    </field>
</record>
```

**What it does:** Adds a "My Team" filter to the `discuss.channel` search view. When activated, this filter narrows the list of channels to only those where at least one channel member's linked employee is a member of a department that the current user manages or belongs to.

**Domain breakdown:**

| Expression Part | Meaning |
|----------------|---------|
| `channel_member_ids` | Go through the channel's members (operators + customers) |
| `partner_id` | From each member, go to their partner |
| `user_ids` | From the partner, go to their user accounts (a partner can have multiple users) |
| `employee_id` | From the user, go to their employee record |
| `member_of_department` | A computed/related boolean on `hr.employee` that is `True` if the employee belongs to a department that the current user has access to |

The `member_of_department` field is provided by the `hr` module. It is a boolean computed field on `hr.employee` that checks whether the employee's `department_id` is one that the current user (the person running the search) can access. This provides a natural "team filter" without requiring explicit department membership configuration.

**Usage context**: This view is used in the Discuss (mail) application's channel list. HR managers or team leads can use the "My Team" filter to see only the livechat channels handled by their team's operators.

### 2. Livechat Channel Member History Search View

**File:** `views/im_livechat_channel_member_history_views.xml`

```xml
<record id="website_livechat_agent_history_view_search" model="ir.ui.view">
    <field name="name">website_livechat.agent.history.search</field>
    <field name="model">im_livechat.channel.member.history</field>
    <field name="inherit_id" ref="im_livechat.im_livechat_agent_history_view_search"/>
    <field name="arch" type="xml">
        <xpath expr="//*[@name='my_session']" position="after">
            <filter name="my_team"
                domain="[('partner_id.user_ids.employee_id.member_of_department', '=', True)]"
                string="My Team"/>
        </xpath>
    </field>
</record>
```

**What it does:** Adds "My Team" to the **agent history** view (`im_livechat.channel.member.history`). This model stores the historical record of when each operator joined or left a livechat session.

**Model:** `im_livechat.channel.member.history` -- this is the aggregated/statistical model for livechat operator session history. It is essentially a read-only denormalized table recording each operator's participation in each session (session start time, end time, duration, messages sent, etc.).

**Domain simplification**: Because `im_livechat.channel.member.history` already has a direct `partner_id` field (not requiring navigation through `discuss.channel.member`), the domain is slightly shorter than the discuss channel version.

### 3. Livechat Report Channel Search View

**File:** `views/im_livechat_report_channel_views.xml`

```xml
<record id="im_livechat_report_channel_view_search" model="ir.ui.view">
    <field name="name">im_livechat.report.channel.search</field>
    <field name="model">im_livechat.report.channel</field>
    <field name="inherit_id" ref="im_livechat.im_livechat_report_channel_view_search"/>
    <field name="arch" type="xml">
        <xpath expr="//*[@name='my_session']" position="after">
            <filter name="my_team"
                domain="[('partner_id.user_ids.employee_id.member_of_department', '=', True)]"
                string="My Team"/>
        </xpath>
    </field>
</record>
```

**What it does:** Adds "My Team" to the **livechat reporting view** (`im_livechat.report.channel`). This is the analytical/reporting model for livechat statistics, aggregating metrics like total sessions, average response time, total messages, and customer satisfaction per channel/operator/date.

**Model:** `im_livechat.report.channel` -- a read-only SQL view (auto-generated by the `im_livechat` module's `init()` method) that aggregates livechat channel statistics. It is used for the livechat dashboard in the Reporting section.

## The "My Team" Domain Explained

All three views use the same core domain pattern. The key expression is:

```python
('partner_id.user_ids.employee_id.member_of_department', '=', True)
```

This is an Odoo domain operating on a **dot-notation path** across many2one relations. It works as follows:

```
For each record in the current model (e.g., discuss.channel):
    For each channel_member in record.channel_member_ids:
        For each user in channel_member.partner_id.user_ids:
            For each employee in user.employee_id:
                if employee.member_of_department:
                    INCLUDE this record
```

This is equivalent to a SQL JOIN chain:

```sql
SELECT dc.*
FROM discuss_channel dc
JOIN discuss_channel_member dcm ON dcm.channel_id = dc.id
JOIN res_partner rp ON rp.id = dcm.partner_id
JOIN res_users ru ON ru.partner_id = rp.id
JOIN hr_employee he ON he.user_id = ru.id
JOIN hr_department hd ON hd.id = he.department_id
WHERE hd.manager_id = %current_user_id%
   OR hd.member_ids = %current_user_id%
   OR he.id IN (
       SELECT member_id FROM hr_department_member
       WHERE department_id IN (
           SELECT department_id FROM hr_department_manager
           WHERE manager_id = %current_user_id%
       )
   )
```

The `member_of_department` computed field handles this SQL complexity behind the scenes.

## HR Reporting Context

When an HR manager opens the **Livechat Reporting** dashboard (Reporting > Livechat), they can use the "My Team" filter to:

1. **Filter by their own department**: See only sessions handled by employees in the HR manager's department.
2. **Compare team performance**: See total sessions, average response time, and CSAT for their team versus other teams.
3. **Identify training needs**: Spot team members with high response times or low CSAT scores.

This bridges two previously siloed modules: `im_livechat` provides the raw livechat data, while `hr` provides the employee-department hierarchy. `hr_livechat` connects them to enable HR-level reporting.

## Access Control Considerations

| Aspect | Detail |
|--------|--------|
| **Who can see livechat data?** | `im_livechat` restricts access via `discuss.channel` ACLs. Internal users (with `base.group_user`) can see channels they participate in or that are assigned to them. |
| **Who can use "My Team"?** | Any user with access to the livechat reporting views can use the filter. The `member_of_department` domain automatically adapts to what the user has access to. |
| **HR officers vs. regular users** | `im_livechat.channel.member.history` may be restricted to livechat administrators. The "My Team" filter is still useful for those with access. |
| **Privacy** | The module does NOT expose individual employee performance to unauthorized users. The reporting views aggregate data at the channel or operator level; individual chat message content is never exposed through these views. |

## Relationship with `im_livechat` Channel Linking

The `im_livechat` module itself provides a separate integration: **livechat channels can be linked to `hr.department`** via the `department_id` field on `im_livechat.channel`. This allows routing rules to assign incoming livechat visitors to operators in specific departments.

`hr_livechat` extends the reporting layer (not the routing layer). The routing between departments and livechat operators is managed by the `im_livechat` module's channel configuration, not by `hr_livechat`.

## Related

- [Modules/im_livechat](Modules/im_livechat.md) -- Livechat channel model, chatbot scripts, operator routing, session history
- [Modules/HR](Modules/HR.md) -- `hr.employee`, `hr.department`, `member_of_department` computed field
- [Modules/mail](Modules/mail.md) -- `discuss.channel`, `discuss.channel.member`, messaging system
- [Modules/hr_org_chart](Modules/hr_org_chart.md) -- Organizational chart for department hierarchy visualization
- [Modules/report_mail_channel](report_mail_channel.md) -- Mail/livechat channel statistics and reporting
