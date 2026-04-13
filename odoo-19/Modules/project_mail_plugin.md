---
type: module
module: project_mail_plugin
tags: [odoo, odoo19, project, mail, outlook, plugin]
created: 2026-04-06
---

# Project Mail Plugin

## Overview
| Property | Value |
|----------|-------|
| **Name** | Project Mail Plugin |
| **Technical** | `project_mail_plugin` |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Integrates the Odoo Outlook mail plugin with the Project application. Enables users to see project tasks directly from their email client (Outlook) when viewing a contact's emails, and create tasks from emails.

## Dependencies
- `project`
- `mail_plugin`

## Key Features
- **Contact panel in Outlook:** Adds a "Tasks" section showing up to 5 tasks linked to the contact
- **Task details:** Each task entry shows `task_id`, `name`, and `project_name`
- **Access control:** Tasks are only shown if the current user has access to the project; also checks `project.task` create access before exposing task functionality
- **Create project action:** Exposes `can_create_project` flag for creating new projects from the plugin
- **Mail logging whitelist:** Adds `project.task` to the models that can have mail content logged from emails

## Controller

### mail_plugin.MailPluginController
Inherits `mail_plugin.MailPluginController`.

**Key Methods:**
- `_get_contact_data(partner)` — Extends contact data dict to include tasks list and `can_create_project` flag. Only includes tasks the user can access (filtered by project read access)
- `_mail_content_logging_models_whitelist()` — Adds `project.task` to the whitelist of models that support mail content logging
- `_translation_modules_whitelist()` — Adds `project_mail_plugin` to the translation module whitelist

## Related
- [Modules/project](Modules/project.md) — Project management
- [Modules/mail_plugin](Modules/mail_plugin.md) — Mail plugin base (Outlook/Gmail integration)
- [Modules/project_todo](Modules/project_todo.md) — To-do tasks
