---
Module: project_sms
Version: 18.0.0
Type: addon
Tags: #odoo18 #project_sms #project #sms
---

## Overview

**Module:** `project_sms`
**Depends:** `project`, `sms`
**Location:** `~/odoo/odoo18/odoo/addons/project_sms/`
**Purpose:** Sends SMS notifications when projects or tasks reach specific stages. Configured via SMS templates on stage records.

## Models

### `project.project` (project_sms/models/project_project.py)

Inherits: `project.project`

| Method | Decorator | Description |
|---|---|---|
| `_send_sms()` | private | If project has `partner_id` and `stage_id` with `sms_template_id`: sends SMS using the stage's template to partner |
| `create()` | `@api.model_create_multi` | Calls `_send_sms()` after project creation |
| `write()` | override | Calls `_send_sms()` when `stage_id` changes |

### `project.task` (project_sms/models/project_task.py)

Inherits: `project.task`

| Method | Decorator | Description |
|---|---|---|
| `_send_sms()` | private | If task has `partner_id`, `stage_id` with `sms_template_id`: sends SMS using stage template |
| `create()` | `@api.model_create_multi` | Calls `_send_sms()` after task creation |
| `write()` | override | Calls `_send_sms()` when `stage_id` changes; uses `sudo()` for SMS template access |

### `project.project.stage` (project_sms/models/project_stage.py)

Inherits: `project.project.stage`

| Field | Type | Description |
|---|---|---|
| `sms_template_id` | Many2one (`sms.template`) | SMS template to send when project enters this stage; domain: `model='project.project'` |

### `project.task.type` (project_sms/models/project_task_type.py)

Inherits: `project.task.type`

| Field | Type | Description |
|---|---|---|
| `sms_template_id` | Many2one (`sms.template`) | SMS template to send when task enters this stage; domain: `model='project.task'` |

## Security / Data

`ir.model.access.csv` present.
`project_sms_security.xml` — security rules for SMS template access.

No data XML files.

## Critical Notes

- v17→v18: No breaking changes.
- SMS is sent only when both `partner_id` and `stage_id.sms_template_id` are set.
- Task `_send_sms` uses `sudo()` because SMS template model is access-rule protected.
- Stage change triggers (both project and task) only fire on `stage_id` write — other field changes don't trigger SMS.