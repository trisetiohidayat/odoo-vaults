# Test Base Automation (`test_base_automation`)

## Overview
- **Name:** Test - Base Automation
- **Category:** Hidden (Test Module)
- **Summary:** Base Automation Tests: Ensure Flow Robustness
- **Depends:** `base_automation`
- **Author:** Odoo S.A.
- **License:** LGPL-3

## Overview

Test module for Odoo's `base_automation` (automated actions) feature. Contains test models and test cases to validate that automated action rules fire correctly on model create, write, unlink, and cron events. Not installable in production.

## Test Models

### `base.automation.lead.test` — Lead Test Model
Core model for automation testing.

**Fields:**
- `name` — Subject (required)
- `user_id` — Responsible user
- `state` — Selection: draft/cancel/open/pending/done (default: draft)
- `active` — Boolean (default: True)
- `tag_ids` — Many2many to `test_base_automation.tag`
- `partner_id` — Partner
- `date_automation_last` — Last automation run timestamp (readonly)
- `employee` — Computed from `partner_id.employee` (stored)
- `line_ids` — One2many to `base.automation.line.test`
- `priority` — Boolean
- `deadline` — Computed: if `priority` set and `create_date` exists, equals `create_date + 3 days` (stored). Uses `relativedelta` for date math.
- `is_assigned_to_admin` — Boolean
- `stage_id` — Computed from state: defaults to stage named "New"

**Key behavior:** `write()` method calls `self.mapped('employee')` to force recomputation of `deadline` — this ensures automation rules based on `deadline` are properly triggered.

### `base.automation.lead.thread.test` — Threaded Lead
Extends `base.automation.lead.test` with `mail.thread`. Used for tests involving automation rules combined with chatter.

### `base.automation.line.test` — Line/Task Test Model
- `name` — Char
- `lead_id` — Many2one to `base.automation.lead.test` (cascade delete)
- `user_id` — User

### `base.automation.link.test` — Link Test Model
- `name` — Char
- `linked_id` — Many2one to `base.automation.linked.test` (cascade delete)

### `base.automation.linked.test` — Linked Test Model
- `name` — Char
- `another_field` — Char

### `test_base_automation.project` — Project-like Model
- `name` — Char
- `task_ids` — One2many to `test_base_automation.task`
- `stage_id` — Many2one to `test_base_automation.stage`
- `tag_ids` — Many2many to `test_base_automation.tag`
- `priority` — Selection: 0=Low, 1=Normal, 2=High (default: 1)
- `user_ids` — Many2many to `res.users`

### `test_base_automation.task` — Task Model
- `name` — Char
- `parent_id` — Self-referencing Many2one (subtask)
- `project_id` — Computed (recursive) from parent task
- `allocated_hours` — Float
- `trigger_hours` — Float: saving to this field triggers effective_hours computation
- `remaining_hours` — Computed: `allocated_hours - effective_hours`
- `effective_hours` — Computed from `trigger_hours` (stored, sudo)

**Note:** `trigger_hours` is used to trigger computed field changes which can fire automation rules.

### `test_base_automation.stage`
- `name` — Char

### `test_base_automation.tag`
- `name` — Char

### `base.automation.model.with.recname.char` — Char as _rec_name
- `description` — Char (used as display name)
- `user_id` — User

### `base.automation.model.with.recname.m2o` — M2O as _rec_name
- `_rec_name = 'user_id'` — Uses many2one as display name
- `user_id` — Many2one to `base.automation.model.with.recname.char`
- `name_create()` — Custom name_create that searches by `description` instead of `name`

## Test Coverage

- `test_flow.py` — Automated action flow tests
- `test_server_actions.py` — Server action execution tests
- `test_tour.py` — UI tour tests

## Related
- [[Modules/base_automation]]
