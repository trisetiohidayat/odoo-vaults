---
Module: project_mail_plugin
Version: 18.0.0
Type: addon
Tags: #odoo18 #project_mail_plugin #project #mail #outlook
---

## Overview

**Module:** `project_mail_plugin`
**Depends:** `project`, `mail_plugin` (auto_install: True)
**Location:** `~/odoo/odoo18/odoo/addons/project_mail_plugin/`
**License:** LGPL-3
**Purpose:** Integrates the Outlook/Gmail mail plugin with Project. Adds tasks panel to partner contacts, enables project/task search and creation directly from the email client.

---

## Controllers

### `controllers/mail_plugin.py` — `MailPluginController` (1–62)

Extends: `mail_plugin.MailPluginController`

Injects project context into the mail plugin's contact data and logging.

#### Methods

`_get_contact_data(partner)` (line 15)
: Overrides base. Adds a `tasks` key to the contact data dict returned to the Outlook add-in. Returns up to 5 tasks linked to the partner, filtered by accessible projects. Also sets `can_create_project` boolean.

`_mail_content_logging_models_whitelist()` (line 51)
: Adds `'project.task'` to the models whitelist for mail content logging. Enables internal note tracking on tasks.

`_translation_modules_whitelist()` (line 57)
: Adds `'project_mail_plugin'` to the translation modules whitelist.

### `controllers/project_client.py` — `ProjectClient` (1–51)

Provides JSON-RPC endpoints for the Outlook plugin sidebar.

#### Routes

`/mail_plugin/project/search` (line 7)
: `type=json`, `auth='outlook'`, `cors="*"`. Searches `project.project` by name (ilike). Returns `{project_id, name, partner_name, company_id}`. Runs as sudo.

`/mail_plugin/task/create` (line 25)
: `type=json`, `auth='outlook'`, `cors="*"`. Creates a `project.task` linked to partner_id and project_id. Uses `Command.link(request.env.uid)` to assign the current user. Returns `{task_id, name}` or `{'error': '...'}`. Uses `with_company(partner.company_id)`.

`/mail_plugin/project/create` (line 47)
: `type=json`, `auth='outlook'`, `cors="*"`. Creates a `project.project` by name. Returns `{project_id, name}`.

---

## Views

**XML:** `views/project_task_views.xml`

`ir.actions.act_window` id `project_task_action_form_edit` — form view of task, used by the plugin to redirect to a newly created task in edit mode.

---

## Security

No `ir.model.access.csv` (relies on parent module ACLs).
Access checks per-method: `has_access('create')` for tasks and projects.

---

## Critical Notes

- **No ORM models** — all behavior is in the controller layer.
- `auth='outlook'` means it uses the OAuth session from the Outlook add-in, not Odoo session auth.
- Tasks created via the plugin are assigned to the current user via `Command.link(request.env.uid)`.
- v17→v18: No breaking changes.