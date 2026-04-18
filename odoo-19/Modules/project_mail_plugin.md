---
type: module
module: project_mail_plugin
tags: [odoo, odoo19, project, mail, outlook, plugin, email, task, crm]
created: 2026-04-14
uuid: a4f7e2b1-3c8d-5f6a-9e2b-1d4c5f6a7b8e
---

# Project Mail Plugin (`project_mail_plugin`)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Project Mail Plugin |
| **Technical** | `project_mail_plugin` |
| **Category** | Services / Project |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Version** | 1.0 |
| **Depends** | `project`, `mail_plugin` |
| **Auto-install** | `True` |

The `project_mail_plugin` module integrates Odoo's Project application with the Outlook (and Gmail) mail plugin. It enables users to view, search, and create project tasks directly from their email client's sidebar panel — without leaving the inbox. The module exposes two layers of functionality: a controller layer (HTTP JSON-RPC endpoints) that the mail plugin client calls, and a data layer that enriches the contact panel with task information.

This module is designed to be consumed by the desktop mail plugin (Outlook add-in or browser extension), not by direct user interaction within Odoo. It extends the contact panel in the mail client to show up to five recent tasks linked to the email's sender or recipient, and allows the user to create new tasks from the same panel.

## Architecture

### Design Philosophy

The module follows a thin-controller pattern: the Python code in the controllers layer is minimal and delegates most logic to the existing `project` and `mail_plugin` models. The module does not create new database tables; instead it extends the `MailPluginController` (from `mail_plugin`) to add project-specific data to the contact panel response, and adds JSON-RPC route handlers to support task creation and project search from the plugin.

### Module Structure

```
project_mail_plugin/
├── __init__.py
├── __manifest__.py
├── controllers/
│   ├── __init__.py
│   ├── mail_plugin.py      # Extends MailPluginController
│   └── project_client.py   # JSON-RPC endpoints for plugin
├── views/
│   └── project_task_views.xml
└── tests/
    ├── __init__.py
    └── test_controller.py
```

The `controllers/` directory is the primary code location. The `views/` directory contains XML definitions for the `project.task` form and tree views referenced by the controller action returns. The `tests/` directory contains integration tests that verify the controller responses.

### Dependency Chain

```
project_mail_plugin
├── project              (project.project, project.task, access control)
└── mail_plugin          (MailPluginController, _get_contact_data, auth mechanisms)
```

The module depends on `mail_plugin` for the base controller infrastructure and on `project` for the task and project models. No direct dependency on `hr` or `crm` exists; the module is purely about connecting project tasks to email contacts.

## Controllers

### `MailPluginController` (Extended)

**File:** `project_mail_plugin/controllers/mail_plugin.py`

The `MailPluginController` class extends `mail_plugin.MailPluginController` — the base controller from the `mail_plugin` module that handles the contact panel data structure. When the Outlook add-in opens an email from a contact, it calls `_get_contact_data(partner)` to retrieve all information to display in the side panel. This module extends that response to include a `tasks` array.

#### `_get_contact_data(partner)`

```python
def _get_contact_data(self, partner):
    contact_values = super()._get_contact_data(partner)

    if not request.env['project.task'].has_access('create'):
        return contact_values

    if not partner:
        contact_values['tasks'] = []
    else:
        partner_tasks = request.env['project.task'].search(
            [('partner_id', '=', partner.id)], offset=0, limit=5)

        accessible_projects = partner_tasks.project_id._filtered_access('read').ids

        tasks_values = [
            {
                'task_id': task.id,
                'name': task.name,
                'project_name': task.project_id.name,
            } for task in partner_tasks
            if task.project_id.id in accessible_projects]

        contact_values['tasks'] = tasks_values
        contact_values['can_create_project'] = request.env['project.project'].has_access('create')

    return contact_values
```

**Step-by-step breakdown:**

1. **Call parent**: Gets the base contact data dict, which includes contact name, email, company, and other standard fields from `res.partner`.

2. **Access check**: Before adding any project data, the method checks whether the current user has `create` access to `project.task`. If not, the base contact data is returned unchanged — the Tasks section simply does not appear in the Outlook panel.

3. **Empty partner handling**: If `partner` is falsy (e.g., the email sender is not in Odoo), the `tasks` key is set to an empty list rather than omitting the key. This ensures the plugin always has a predictable response structure.

4. **Task search**: Searches for up to 5 tasks linked to the partner via `partner_id`. The results are ordered by `create_date` descending by default (standard Odoo ORM behavior). No explicit `order` parameter is needed because the default ordering is appropriate for a "recent tasks" display.

5. **Access-filtered projects**: Even though the search returns tasks linked to the partner, the user may not have read access to every associated project. The method calls `project_id._filtered_access('read')` to get only the project IDs the current user can access. This is a performance optimization — it avoids creating task records in the response dict for projects the user cannot see.

6. **Task value dict**: For each accessible task, the response includes `task_id`, `name`, and `project_name`. The `project_name` is included so the Outlook panel can display which project each task belongs to without making additional requests.

7. **`can_create_project` flag**: The response also includes a boolean indicating whether the user can create new projects. This allows the Outlook panel to show or hide the "Create Project" button without making an additional access check.

#### `_mail_content_logging_models_whitelist()`

```python
def _mail_content_logging_models_whitelist(self):
    models_whitelist = super()._mail_content_logging_models_whitelist()
    if not request.env['project.task'].has_access('create'):
        return models_whitelist
    return models_whitelist + ['project.task']
```

This method extends the whitelist of models that support the mail content logging feature. When the Outlook add-in receives an email and the user clicks "Log email content," the mail plugin checks whether the target model supports mail content logging. By adding `project.task` to the whitelist, the module enables email content to be appended to task descriptions as internal notes.

#### `_translation_modules_whitelist()`

```python
def _translation_modules_whitelist(self):
    modules_whitelist = super()._translation_modules_whitelist()
    if not request.env['project.task'].has_access('create'):
        return modules_whitelist
    return modules_whitelist + ['project_mail_plugin']
```

This method adds `project_mail_plugin` to the list of modules whose translatable terms are loaded for the plugin's translation interface. It ensures that field labels and messages from this module appear in the translation editor within the mail plugin context.

### `ProjectClient` (JSON-RPC Controller)

**File:** `project_mail_plugin/controllers/project_client.py`

The `ProjectClient` controller provides JSON-RPC endpoints that the mail plugin uses for project and task operations. These routes are separate from the contact panel data endpoint and handle specific user actions.

#### `projects_search()`

```python
@http.route('/mail_plugin/project/search', type='jsonrpc', auth='outlook', cors="*")
def projects_search(self, search_term, limit=5):
    projects = request.env['project.project'].search(
        [('name', 'ilike', search_term)], limit=limit)

    return [
        {
            'project_id': project.id,
            'name': project.name,
            'partner_name': project.partner_id.name,
            'company_id': project.company_id.id
        }
        for project in projects.sudo()
    ]
```

**Route:** `GET /mail_plugin/project/search?search_term=<term>&limit=5`
**Auth:** `auth='outlook'` — uses the Outlook OAuth token for authentication
**CORS:** `cORS="*"` — allows cross-origin requests from the Outlook web client

This endpoint searches for projects by name and returns the top N results. The `.sudo()` call is used because the project records may belong to companies the authenticated user does not directly belong to but has access to through the Outlook token. The response includes the project ID, name, partner name (if any), and company ID — all the information needed to display a project in the plugin's dropdown selector.

#### `task_create()`

```python
@http.route('/mail_plugin/task/create', type='jsonrpc', auth='outlook', cors="*")
def task_create(self, email_subject, email_body, project_id, partner_id):
    partner = request.env['res.partner'].browse(partner_id).exists()
    if not partner:
        return {'error': 'partner_not_found'}

    if not request.env['project.project'].browse(project_id).exists():
        return {'error': 'project_not_found'}

    if not email_subject:
        email_subject = _('Task for %s', partner.name)

    record = request.env['project.task'].with_company(partner.company_id).create({
        'name': email_subject,
        'partner_id': partner_id,
        'description': email_body,
        'project_id': project_id,
        'user_ids': [Command.link(request.env.uid)],
    })

    return {'task_id': record.id, 'name': record.name}
```

**Route:** `POST /mail_plugin/task/create`

This endpoint creates a new task from an email. Key behaviors:

- **`exists()` check**: Before creating, the method verifies that the partner and project records actually exist in the database. If either is missing, an error dict is returned.
- **Fallback subject**: If the email has no subject, a default subject is generated using the partner's name.
- **`with_company()`**: The task is created using the partner's company as the context company. This ensures correct multi-company data isolation.
- **`user_ids` assignment**: The task is assigned to the current user (`request.env.uid`) via `Command.link()`, making the user a follower of the task.
- **Email body as description**: The email body is stored in the task's `description` field as plain text (the mail plugin passes sanitized HTML or plain text depending on configuration).
- **Returns task ID and name**: The plugin uses these values to update the UI and confirm task creation.

#### `project_create()`

```python
@http.route('/mail_plugin/project/create', type='jsonrpc', auth='outlook', cors="*")
def project_create(self, name):
    record = request.env['project.project'].create({'name': name})
    return {"project_id": record.id, "name": record.name}
```

**Route:** `POST /mail_plugin/project/create`

A minimal endpoint that creates a new project with only a name. This supports the use case where a user receives an email about a topic not yet covered by an existing project and wants to create a new project inline from the Outlook panel. The returned project ID can then be used in a subsequent `task_create()` call.

## Access Control Model

The module implements a layered access control strategy:

1. **Plugin-level access check**: In `_get_contact_data()`, the first check is whether the user can `create` tasks. If not, no project-related data is returned at all — the plugin behaves as if the project module is not installed.

2. **Per-record project filtering**: Even for users who can create tasks, the tasks list only includes tasks from projects the user can actually read. The `_filtered_access('read')` method applies Odoo's standard record rules.

3. **Existence checks**: The `task_create` and `project_create` endpoints verify record existence before operating, returning descriptive error codes rather than letting the ORM raise exceptions.

4. **Outlook authentication**: All routes use `auth='outlook'`, which delegates authentication to the Outlook OAuth flow configured in the mail plugin. Users must have a valid Outlook session and an associated Odoo account to access these endpoints.

## Data Flow: Email to Task

```
Outlook (User opens email from contact)
    ↓
Mail Plugin Client (calls /mail_plugin/contact/data)
    ↓
MailPluginController._get_contact_data(partner)
    ↓
project_mail_plugin._get_contact_data()  [extends parent]
    - Search project.task for partner_id = contact.id
    - Filter by accessible projects
    - Return tasks list + can_create_project flag
    ↓
Outlook Panel (displays contact + tasks section)
    ↓
User clicks "Create Task"
    ↓
Mail Plugin Client (calls /mail_plugin/task/create)
    ↓
ProjectClient.task_create()
    - Validate partner and project exist
    - Create project.task with email subject, body, partner
    - Return task_id and name
    ↓
Outlook Panel (displays new task in list)
```

## Integration with `project`

The module does not override any `project.task` or `project.project` model methods. All integration is through the controller layer. However, the following project behaviors are relevant:

- **Task-partner linking**: Tasks have a `partner_id` field (from `project`) that links the task to the customer's contact record. This is the key relationship that powers the contact panel task list.
- **Project privacy**: Projects have a `privacy_visibility` field controlling who can see them. The `_filtered_access('read')` call respects these visibility rules.
- **Multi-company**: Tasks and projects are company-scoped. The `with_company()` call in `task_create()` ensures the task is created in the correct company.

## Business Impact

### Productivity Gain

The primary benefit is eliminating context-switching. A project manager who receives 30 emails per day about task-related matters can create, assign, and link tasks without leaving their email client. The task is automatically linked to the email sender's contact record, creating a traceable connection between customer communication and project work.

### Email-Task Traceability

By storing the email sender as the task's `partner_id`, every task created from an email has a direct link to the customer's contact record. This enables Odoo's built-in reporting on task volume per customer and supports the CRM-like visibility of project-client relationships.

### Controlled Access

The access control model ensures that sensitive projects (e.g., internal R&D or HR projects with restricted visibility) do not appear in the Outlook panel for users who do not have Odoo access to those projects. This prevents information leakage through the mail plugin.

## Related

- [Modules/project](Modules/Project.md) — Project management: project, task, milestones
- [Modules/mail_plugin](Modules/mail_plugin.md) — Base mail plugin: Outlook/Gmail add-in infrastructure
- [Modules/project_todo](Modules/project_todo.md) — Project tasks backed by todo list (task sharing)
- [Modules/crm_mail_plugin](Modules/crm_mail_plugin.md) — CRM equivalent: email-to-lead conversion in Outlook

## Real-World Scenarios

### Scenario 1: Outbound Lead Response

A sales representative receives an inbound inquiry email from a prospective customer. In Outlook, they open the email and see the contact's sidebar panel. The panel shows:
- Contact name, email, company.
- Two existing tasks from previous interactions.
- A "Create Task" button.

The representative clicks "Create Task," enters the email subject as the task name, and confirms. The task is created in Odoo with the email sender linked as the `partner_id`. The task is automatically assigned to the sales representative and appears in their Odoo task list.

### Scenario 2: Customer Service Follow-Up

A customer support agent receives a complaint email about a delayed order. They create a task from the email in Outlook, linking it to the customer's contact record. The task appears in the project's task list with the full email history in the description. The project manager sees the task and can reassign it to the operations team.

### Scenario 3: Quick Project Assignment

A project manager receives an email that clearly relates to an existing project but does not contain enough detail to create a full task. They use the plugin to quickly search for the project and create a placeholder task, then add the email body as the initial description. This creates a traceable record in Odoo without interrupting their email workflow.

## RPC API Reference

### `/mail_plugin/project/search`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `search_term` | string | Yes | Project name search string (case-insensitive) |
| `limit` | integer | No | Maximum results (default: 5) |

**Response:**
```json
[
  {
    "project_id": 42,
    "name": "Website Redesign Q3",
    "partner_name": "Acme Corp",
    "company_id": 1
  }
]
```

**Error responses:**
```json
{"error": "no_results"}  // No matching projects found
```

### `/mail_plugin/task/create`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `email_subject` | string | Yes | Task name/subject |
| `email_body` | string | No | Email body text (used as task description) |
| `project_id` | integer | Yes | Target project ID |
| `partner_id` | integer | Yes | Contact's partner ID |

**Response:**
```json
{"task_id": 156, "name": "Follow up on proposal"}
```

**Error responses:**
```json
{"error": "partner_not_found"}
{"error": "project_not_found"}
```

### `/mail_plugin/project/create`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | Yes | New project name |

**Response:**
```json
{"project_id": 43, "name": "New Project Q4"}
```

## Testing the Controller

The module includes integration tests in `tests/test_controller.py` that validate:

1. **`projects_search` returns correct results**: Searching by partial name returns matching projects.
2. **`projects_search` respects access rights**: Users without project access do not see restricted projects.
3. **`task_create` validates input**: Missing or invalid partner/project IDs return appropriate error codes.
4. **`task_create` assigns to current user**: The created task has `user_ids` set to the authenticated user.
5. **`can_create_project` flag is correct**: Returns `True` only for users with project create access.

## Performance Considerations

### Access Control Filtering

The `projects_search` endpoint uses `.sudo()` to return all accessible projects. In large databases with thousands of projects, this is generally fast because the search is name-based. However, if performance becomes an issue, consider adding a domain filter:

```python
projects = request.env['project.project'].search([
    ('name', 'ilike', search_term),
    ('company_id', 'in', request.env.companies.ids),
], limit=limit)
```

### Task Search Limit

The `_get_contact_data` method limits task search to 5 results. This is a deliberate design choice to keep the sidebar response small and fast. For the full task history, users should open the partner's CRM or project record directly.

## Related

- [Modules/mail_plugin](Modules/mail_plugin.md) — Base mail plugin infrastructure: authentication, contact panel
- [Modules/project](Modules/Project.md) — Project management: tasks, milestones, planning
- [Modules/crm_mail_plugin](Modules/crm_mail_plugin.md) — CRM equivalent: email-to-lead conversion
- [Modules/project_helpdesk](project_helpdesk.md) — Project + Helpdesk integration
