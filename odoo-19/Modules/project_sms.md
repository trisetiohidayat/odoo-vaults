---
type: module
module: project_sms
tags: [odoo, odoo19, project, sms, notifications]
created: 2026-04-06
updated: 2026-04-11
depth: L4
---

# Project SMS — L4 Module Documentation

## Quick Access

| Resource | Type | Description |
|---------|------|-------------|
| [Modules/Project](Modules/project.md) | Module | Parent `project.project`, `project.task` models |
| [Modules/sms](Modules/sms.md) | Module | SMS template, composer, and delivery pipeline |
| [Modules/project](Modules/project.md) | Module | Email notification counterpart for project stages |

---

## Module Overview

| Property | Value |
|---------|-------|
| **Name** | Project - SMS |
| **Technical** | `project_sms` |
| **Category** | Services/Project |
| **Version** | 1.1 |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Auto-install** | `True` |
| **CE/EE** | Community Edition only |

---

## L1: Core Functionality — SMS Notifications for Project Tasks

### What the Module Does

`project_sms` sends SMS text messages to customers automatically when a project or task transitions to a new stage. It is an event-driven notification system — not a scheduled reminder system and not a per-user routing engine. The notification trigger is the `stage_id` write event on `project.project` and `project.task` records.

### Two-Record Workflow Model

The module treats project stages and task stages as independent configuration surfaces:

```
project.project ──────> project.project.stage ──────> sms_template_id
project.task   ──────> project.task.type    ──────> sms_template_id
```

A stage carries its own `sms_template_id`. When a record enters that stage, the template fires. This design means:
- **No per-record SMS configuration** — assign a template once to the stage, every record using that stage inherits the notification.
- **Bulk reassignments work automatically** — changing 50 tasks to "In Progress" fires 50 SMS events with no additional configuration.
- **SMS is coupled to workflow progression** — not to field edits, not to deadline crossings, not to user assignments.

### Recipient Model

SMS is sent exclusively to the **record's `partner_id`** (the customer contact), not to project/task members. This is a deliberate business choice: SMS is a customer-facing channel for status updates, not an internal team notification tool. For internal team SMS, the `sms.composer` action button (added to project/task list/kanban views) provides ad-hoc sending.

### What Is NOT in This Module

- Scheduled/delay-based SMS reminders (deadline alerts require `project.mail` + custom cron logic or a separate alert module).
- Per-user SMS routing (e.g., routing to the assigned user instead of the partner).
- SMS on task creation (only stage transitions trigger SMS; creation triggers only if `stage_id` is passed in `vals_list`).
- Delivery receipt tracking (handled by the `sms` module's `sms.sms` state machine).
- Opt-out/blacklist enforcement at the application level (handled by `sms` module's `phone_blacklist`).

---

## L2: Field Types, Defaults, and Constraints

### `sms_template_id` on `project.project.stage`

**File:** `models/project_stage.py`

```python
class ProjectProjectStage(models.Model):
    _inherit = 'project.project.stage'

    sms_template_id = fields.Many2one(
        'sms.template',
        string="SMS Template",
        domain=[('model', '=', 'project.project')],
        help="If set, an SMS Text Message will be automatically sent "
             "to the customer when the project reaches this stage."
    )
```

| Property | Value |
|----------|-------|
| **Type** | `Many2one` |
| **Target** | `sms.template` |
| **Domain** | `model = 'project.project'` (static domain, not lambda) |
| **Required** | No |
| **Default** | `False` |
| **Ondelete** | Not specified — defaults to `set null` (nullify on template deletion) |
| **Store** | Yes (standard Many2one) |
| **Index** | No explicit index, but `sms.template` PK provides FK index |

**Why the static domain `domain=[('model', '=', 'project.project')]`:** Static domains on `Many2one` fields are evaluated at form-load time and constrain the dropdown selection. This prevents a Project Manager from accidentally assigning a task-level SMS template (`model='project.task'`) to a project stage, and vice versa. The constraint is enforced client-side; the server relies on the same model field for security rules.

**Ondelete behavior:** When the referenced `sms.template` is unlinked, the FK column `sms_template_id` is set to `NULL` on all affected stages. This means SMS silently stops firing — the stage's guard `if stage.sms_template_id` evaluates to falsy. No `MissingError` is raised because the reference resolves to `False`.

### `sms_template_id` on `project.task.type`

**File:** `models/project_task_type.py`

```python
class ProjectTaskType(models.Model):
    _inherit = "project.task.type"

    sms_template_id = fields.Many2one(
        'sms.template',
        string="SMS Template",
        domain=[('model', '=', 'project.task')],
        help="If set, an SMS Text Message will be automatically sent "
             "to the customer when the task reaches this stage."
    )
```

| Property | Value |
|----------|-------|
| **Type** | `Many2one` |
| **Target** | `sms.template` |
| **Domain** | `model = 'project.task'` |
| **Personal stages** | Field hidden via `invisible="user_id"` in form view |

**Personal task stages:** `project.task.type` records can be **personal** (`user_id` set) or **project-level** (`user_id` empty). The form view XML injects `sms_template_id` with `invisible="user_id"`, hiding it for personal stages. This prevents managers from configuring SMS on a colleague's personal stage. The field exists on the model for both types; visibility is purely a UI constraint.

### `_send_sms()` on `project.project`

**File:** `models/project_project.py`

```python
def _send_sms(self):
    for project in self.sudo():
        if project.partner_id and project.stage_id and project.stage_id.sms_template_id:
            project.with_env(self.env)._message_sms_with_template(
                template=project.stage_id.sms_template_id,
                partner_ids=project.partner_id.ids,
            )
```

| Property | Value |
|----------|-------|
| **Decorator** | None (recordset method, `@api.multi` implicit) |
| **Parameters** | None (uses `self` as recordset) |
| **Sudo scope** | `self.sudo()` — elevates to superuser for template read |
| **Env restoration** | `with_env(self.env)` — restores original `env` after sudo |

**Dot-access chain evaluated inside sudo:**
```
project.partner_id        → SELECT FROM res_partner WHERE id = project.partner_id
project.stage_id          → SELECT FROM project_task_type WHERE id = project.stage_id  
project.stage_id.sms_template_id → SELECT FROM sms_template WHERE id = stage.sms_template_id
```

**Guard conditions (all must be truthy):**
1. `project.partner_id` — project has a customer partner
2. `project.stage_id` — project has a stage assigned
3. `project.stage_id.sms_template_id` — the stage has a template configured

If any guard fails, the method silently returns `None` — no exception, no log entry. This is intentional: missing partners or stages are expected in many project creation flows.

### `_send_sms()` on `project.task`

**File:** `models/project_task.py`

```python
def _send_sms(self):
    for task in self:
        if task.partner_id and task.stage_id and task.stage_id.sms_template_id and not task.is_template:
            task._message_sms_with_template(
                template=task.stage_id.sms_template_id,
                partner_ids=task.partner_id.ids,
            )
```

| Property | Value |
|----------|-------|
| **Decorator** | None (recordset method) |
| **Sudo scope** | None — caller (`write()`) wraps with `sudo()` |
| **Extra guard** | `and not task.is_template` — skips template tasks |

**`is_template` guard:** When a task has `is_template=True` (created from a recurring template or a project template), this guard prevents SMS from firing during template instantiation. This is the **only functional difference** between task and project SMS logic.

---

## L3: Cross-Module Integration, Override Patterns, and Workflow Triggers

### Cross-Module Integration Map

```
project_sms
│
├── depends: [project, sms]
│
├── EXTENDS project.project.stage (project_stage.py)
│   └── adds: sms_template_id (Many2one → sms.template)
│
├── EXTENDS project.task.type (project_task_type.py)
│   └── adds: sms_template_id (Many2one → sms.template)
│
├── EXTENDS project.project (project_project.py)
│   └── hooks: create() → _send_sms()
│   └── hooks: write(stage_id) → _send_sms()
│
├── EXTENDS project.task (project_task.py)
│   └── hooks: create() → _send_sms()
│   └── hooks: write(stage_id) → sudo()._send_sms()
│
└── DEPENDS ON sms module (provides):
    ├── sms.template model
    ├── _message_sms_with_template() mixin method
    ├── _render_field() for QWeb template rendering
    ├── sms.sms delivery state machine
    └── phone_blacklist enforcement
```

### Override Pattern: Classic `_inherit` with Hook Methods

`project_sms` uses the **classic `_inherit` pattern** with ORM hooks into `create()` and `write()`. No delegation or mixins are used. The pattern is intentional: SMS sending is a side-effect of record lifecycle events, not core business data.

**Create hook pattern:**

```python
@api.model_create_multi
def create(self, vals_list):
    records = super().create(vals_list)  # Core logic first
    records._send_sms()                  # SMS side-effect after
    return records
```

This pattern guarantees:
- **Atomics** — if `super().create()` fails, `_send_sms()` is never called.
- **Idempotency of create** — calling `create()` multiple times on the same data always creates multiple records; SMS fires for each.
- **Order independence** — the hook is called after `super()`, meaning the record exists with its final `stage_id` before SMS fires.

**Write hook pattern:**

```python
def write(self, vals):
    result = super().write(vals)   # Core logic first
    if 'stage_id' in vals:         # Only if stage actually changed
        self._send_sms()           # SMS side-effect
    return result
```

Key characteristics:
- **Conditional trigger** — only fires when `stage_id` is in `vals`, meaning the stage was explicitly changed. Bulk writes without `stage_id` do not fire SMS.
- **Post-commit timing** — the `write()` completes fully (including DB commit) before SMS fires. If SMS fails, the stage change is already committed.
- **Same-record guard** — `write()` operates on `self` (the recordset the caller passed). If called on an empty recordset, the `for` loop in `_send_sms()` is a no-op.

### Workflow Trigger: Stage Transition Event

The trigger is the `stage_id` field write event, not a dedicated workflow engine transition. This means:

1. **Direct stage assignment** — `task.write({'stage_id': stage_id})` fires SMS.
2. **Stage change via button** — `action_stage_progress()`, `action_done()`, etc. in `project` ultimately call `write({'stage_id': ...})`, so SMS fires.
3. **Stage change via Kanban drag** — the Kanban view calls `write({'stage_id': ...})` server-side, so SMS fires.
4. **CSV import of stage_id** — `load()` or `import` calls `write()`, so SMS fires.
5. **Onchange-triggered stage change** — an onchange method that calls `self.write({'stage_id': ...})` fires SMS.

The trigger is consistent regardless of the client interface.

### `sms.composer` Action Button Integration

**File:** `views/project_project_views.xml`, `views/project_task_views.xml`

The module adds `sms.composer` as a bound action to both project and task models:

```
project_project_act_window_sms_composer  →  bound to model_project_project
                                            visible in: list, kanban
                                            restricted to: project.group_project_manager

project_task_act_window_sms_composer     →  bound to model_project_task
                                            visible in: list, kanban, form
                                            restricted to: (none — all users)
```

The `mass` composition mode means the composer operates on `active_ids` (multiple selected records), sending individual SMS to each record's partner. `mass_keep_log=True` creates a `mail.message` record for each SMS, providing an audit trail.

---

## L4: Version Changes Odoo 18 to 19, Security Deep Dive, and Upgrade Migration

### Version History

| Version | Changes |
|---------|---------|
| 1.0 | Initial module (Odoo ~16-17 era) |
| 1.1 | Current — includes migration script, refined security |

The version bump from 1.0 to 1.1 in Odoo 19 corresponds to the **ir.rule domain fix** (see Migration section below).

### Odoo 18 to 19: What Changed

#### 1. `ir.rule` `model` vs `model_id.model` Field Name Change

**The critical change:** In Odoo 18, `ir.rule` records used the field `model_id.model` to reference the model. In Odoo 19, this changed to `model`.

In the database, `ir_rule` table:

| Odoo Version | Column for model reference | Example value |
|---|---|---|
| Odoo 18 | `model_id` (FK to `ir_model.id`) | `SELECT id FROM ir_model WHERE model = 'sms.template'` |
| Odoo 19 | `model` (VARCHAR) | `'sms.template'` |

The `ir_rule_sms_template_project_manager` rule was originally written with the Odoo 18 field name in its domain. After an upgrade to Odoo 19, the rule would evaluate its domain against the wrong column, silently becoming ineffective or causing SQL errors.

#### 2. `perm_read` Now Explicitly `False`

In the `ir.rule` definition:
```xml
<field name="perm_read" eval="False"/>
```

Previously this field was simply omitted (defaulting to `False`), which had the same effect but was less explicit. Setting it explicitly makes the intent clearer and is more robust to framework changes.

#### 3. `sms.template` Model Reference Changed

The `sms.template` model may have changed its internal implementation between Odoo 18 and 19 (e.g., template rendering engine changes). The `_message_sms_with_template()` API has remained stable, but the underlying `body` field rendering and the SMS delivery state machine (`sms.sms`) may have subtle changes. No API-breaking changes were introduced to the mixin method signatures used by `project_sms`.

### Upgrade Migration Script

**File:** `upgrades/1.1/pre-migrate.py`

```python
def migrate(cr, version):
    cr.execute("""
        UPDATE ir_rule r
           SET domain_force = '[("model", "in", ("project.task", "project.project"))]'
          FROM ir_model_data d
         WHERE d.res_id = r.id
           AND r.domain_force = '[("model_id.model", "in", ("project.task.type", "project.project.stage"))]'
           AND d.model = 'ir.rule'
           AND d.module = 'project_sms'
           AND d.name = 'ir_rule_sms_template_project_manager'
    """)
```

**What this migration does:**

| Step | Detail |
|------|--------|
| Target | `ir_rule` records matching the old (Odoo 18) pattern |
| Old domain | `[('model_id.model', 'in', ('project.task.type', 'project.project.stage'))]` — references the wrong model names AND uses wrong field syntax |
| New domain | `[('model', 'in', ('project.task', 'project.project'))]` — correct model names and Odoo 19 field syntax |
| Condition | Must also have matching `ir_model_data` record with `module='project_sms'` and `name='ir_rule_sms_template_project_manager'` |

**Why `pre-migrate` and not `post-migrate`:** The `pre-migrate` hook runs **before** the module upgrade scripts apply their XML data updates. If the new XML with the correct domain was loaded first and then `post-migrate` tried to update it, the XML load would overwrite the fix. By using `pre-migrate`, the fix is applied before any new XML data is loaded, ensuring the correct domain survives the upgrade.

**Why this matters:** Without this migration, after upgrading to Odoo 19:
1. The new XML loads with the correct Odoo 19 domain `[('model', 'in', ...)]`.
2. But if there was an old Odoo 18 `ir_rule` record in the database (from a prior installation or an incompatible module version), it could conflict or create duplicate rules.
3. The `pre-migrate` ensures all legacy records of this rule are normalized to the Odoo 19 format before the new XML is applied.

### Security Deep Dive

#### ACL Architecture

`project_sms` ships two security files that work in tandem:

**`security/ir.model.access.csv`** — grants global model-level permissions:

```
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_sms_template_project_manager,access.sms.template.project.manager,
  sms.model_sms_template,project.group_project_manager,1,1,1,1
```

This gives Project Managers full CRUD on `sms.template`. The `group_id` is `project.group_project_manager` (not `base.group_system`), meaning Project Managers — not all employees — get SMS template management rights.

**`security/project_sms_security.xml`** — narrows the effective scope via record rule:

```xml
<record id="ir_rule_sms_template_project_manager" model="ir.rule">
    <field name="name">SMS Template: project manager CUD on project/task</field>
    <field name="model_id" ref="sms.model_sms_template"/>
    <field name="groups" eval="[(4, ref('project.group_project_manager'))]"/>
    <field name="domain_force">[('model', 'in', ('project.task', 'project.project'))]</field>
    <field name="perm_read" eval="False"/>
</record>
```

#### Effective Permissions Matrix

| User Group | Can Read SMS Templates? | Can Create Project/Task Templates? | Can Write Project/Task Templates? | Can Unlink Project/Task Templates? |
|------------|--------------------------|-----------------------------------|-----------------------------------|-------------------------------------|
| Internal employees (no project group) | No (inherited from `sms` module) | No | No | No |
| Project User (`project.group_project_user`) | No | No | No | No |
| Project Manager (`project.group_project_manager`) | **No** (explicit `perm_read=False`) | **Yes** | **Yes** | **Yes** |
| System/Admin (`base.group_system`) | Yes (inherits from `sms` ACL) | Yes | Yes | Yes |

**Why Project Managers cannot READ SMS templates:** `perm_read="False"` on the rule means Project Managers do not have ORM-level read access to `sms.template` records. This is intentional for data compartmentalization — Project Managers configure SMS templates through the project/task stage form (which uses `context={'default_model': ...}`) but should not browse all SMS templates directly. The `sudo()` in `project_project._send_sms()` bypasses this rule, allowing the system to read the template body for rendering.

#### Privilege Escalation Flow

The `sudo()` call in `project_sms` is a deliberate privilege escalation:

```
User (no sms.template read access)
  → task.write({'stage_id': new_stage})
    → super().write(vals)                    [normal ACL check]
    → self.sudo()._send_sms()               [privilege escalation]
      → reads sms.template.body              [bypasses ir.rule but NOT field groups]
      → renders template
      → sends SMS via sms.sms
```

**What `sudo()` bypasses:** Record-level `ir.rule` filters. The superuser can read all records regardless of domain rules.

**What `sudo()` does NOT bypass:** Field-level `groups` restrictions. If `sms.template.body` had `groups="base.group_system"`, even `sudo()` would raise an `AccessError` when trying to read that field. In practice, `body` has no `groups` restriction.

**Security implication:** The `sudo()` allows a standard project user to trigger SMS sending through a stage transition. The SMS template content is never exposed to the user — only the system reads it. The user sees only the outcome (SMS sent to customer). This is a safe pattern as long as template bodies do not contain sensitive internal data.

#### Portal User Behavior

Portal users (external collaborators) can change task stages via the project sharing interface. The test `test_portal_user_can_change_stage_with_sms_template` in `tests/test_project_sharing.py` validates this flow:

1. Portal user changes task stage via `web_portal` access.
2. `write()` fires `sudo()._send_sms()`.
3. SMS is sent from system sender to the partner (not to the portal user).
4. If the partner is the same as the task author (`self.assertSMSIapSent([])`), no SMS is sent (self-notification prevention handled by `sms` module's IAP gateway).

#### SQL Injection Risk Assessment

The `_send_sms()` method uses only ORM APIs (`_message_sms_with_template`), which are immune to SQL injection. No raw SQL is used. The only raw SQL is in the migration script, which uses hardcoded model names — no user input reaches the SQL.

#### CSRF Risk Assessment

No HTTP controllers in `project_sms`. No CSRF exposure.

### Performance Deep Dive

#### N+1 Query Analysis in `_send_sms()`

**Project SMS (`project_project._send_sms`):**

```python
for project in self.sudo():                    # N iterations
    if project.partner_id and ...:             # Triggers partner_id prefetch
        project.with_env(...)._message_sms_with_template(...)
```

| Query | Frequency | Reason |
|-------|-----------|--------|
| `SELECT FROM project_project WHERE id IN (...)` | 1 | Main batch read of `self` |
| `SELECT FROM res_partner WHERE id IN (pids)` | 1 | Prefetched via `partner_id` |
| `SELECT FROM project_task_type WHERE id IN (sids)` | 1 | Prefetched via `stage_id` |
| `SELECT FROM sms_template WHERE id IN (...)` | 1 | Prefetched via `stage_id.sms_template_id` |
| `_render_field()` | N | Template rendering per record |
| `INSERT INTO mail_message` | N | One message per SMS |
| `INSERT INTO sms_sms` | N | One SMS record per recipient |

The ORM's prefetch mechanism handles the first four queries efficiently — a single `SELECT` fetches all related records for the batch. The N calls to `_render_field()` are the main cost.

**Task SMS (`project_task._send_sms`):** Same pattern. The `sudo()` in the `write()` caller's scope does not break prefetch for the non-sudo'd reads of `partner_id` and `stage_id` (those are accessed before `sudo()` is called in the `if` condition, so they use the standard env).

#### Batch Write Optimization

When a user changes stages for N tasks at once (e.g., via Kanban drag of multiple cards, or `write()` on a recordset of N tasks):

```
write([{id: 1, stage_id: 3}, {id: 2, stage_id: 3}, ...])  # ORM batch
  → for each task, _send_sms() called on the batch
    → for task_1: _message_sms_with_template() → SMS to task_1.partner_id
    → for task_2: _message_sms_with_template() → SMS to task_2.partner_id
    → ...
```

The `for task in self:` loop sends SMS **sequentially**, not in parallel. For large batch operations (e.g., 100 tasks), this could be slow. No batch/SMS aggregation is performed.

#### Template Rendering Cost

`template._render_field('body', self.ids, compute_lang=True)` renders the QWeb template body for each record. If the template uses `{{ object.partner_id.name }}`, `{{ object.stage_id.name }}`, etc., these are resolved via the ORM. The cost is O(N * template_complexity).

#### Silent Failure and Error Visibility

`_message_sms_with_template()` catches and logs SMS gateway errors internally but does not propagate them to the caller. The `write()` call succeeds even if SMS delivery fails. Users see no error. The failure is only visible:
- In the `sms.sms` model (outbound SMS queue with state `error`).
- In the `mail.message` record with `message_type='sms'` and a failure sub-type.
- In server logs (if `mail` module logging is set to `DEBUG`).

### Edge Cases — Complete Catalog

#### EC-1: Project created without `stage_id` or `partner_id`

```
project.create({'name': 'New Project'})
  → super().create() creates the project with stage_id=False, partner_id=False
  → _send_sms() called
  → guard: project.partner_id = False → silently skips
  → guard: project.stage_id = False → silently skips
```

No error. SMS fires later when `write()` assigns stage or partner.

#### EC-2: Project stage changed to a stage with no `sms_template_id`

```
project.write({'stage_id': stage_without_template.id})
  → super().write() updates the stage
  → _send_sms() called
  → guard: stage.sms_template_id = False → silently skips
```

Correct behavior: moving away from a stage with a template (or to one without) stops SMS.

#### EC-3: `sms.template` record deleted after being assigned to a stage

```
stage.write({'sms_template_id': template_id})  # template exists
  → project moves to stage → SMS fires

sms.template.browse(template_id).unlink()  # template deleted
  → FK becomes NULL on the stage (ondelete='set null' default)
  → project moves to stage again → guard: stage.sms_template_id = False → skips
```

No `MissingError`. The FK nullification is handled by the ORM's CASCADE/SET NULL mechanism.

#### EC-4: Partner phone is invalid or missing

```
partner.write({'phone': False})  # or invalid format
  → _message_sms_with_template() is called
  → template renders
  → sms.sms record created with state='error'
  → failure reason: 'Missing phone number'
```

Handled by the `sms` module's validation layer. No exception propagates to the caller.

#### EC-5: Partner on phone blacklist

```
partner.write({'phone': '+1234567890'})
sms_blacklist.create({'number': '+1234567890'})

  → _message_sms_with_template() is called
  → sms.sms record created with state='error', failure_type='blacklist'
```

Handled by the `sms` module's `phone_blacklist` table check. Same silent failure pattern.

#### EC-6: Two concurrent `write()` calls on the same record changing to the same stage

```
Session A: write({'stage_id': 5}) → _send_sms() fires SMS #1
Session B: write({'stage_id': 5}) → _send_sms() fires SMS #2  (same stage, but fired twice)
```

No deduplication. Both sessions independently call `_send_sms()`. If the use case requires only one SMS per stage visit, implement a `_sms_last_stage_id` tracked field:

```python
# Extension pattern (not in core module)
if vals.get('stage_id'):
    # Only send if stage actually changed
    for record in self:
        if record.stage_id.id != vals['stage_id']:
            record._send_sms()
```

#### EC-7: Email AND SMS both configured on same stage

```
stage.mail_template_id = email_template_id  (from project.mail)
stage.sms_template_id = sms_template_id      (from project_sms)
```

Both fire independently. Email goes to followers (via `mail.thread`); SMS goes to `partner_id`. No coordination, no deduplication, no mutual exclusion. Two separate notifications dispatched.

#### EC-8: Task template (`is_template=True`) created with a stage that has `sms_template_id`

```
task.create({'name': 'Template Task', 'is_template': True, 'stage_id': stage_with_sms.id})
  → super().create() creates the task
  → _send_sms() called
  → guard: task.is_template = True → skips
```

No SMS. Template task creation does not send customer-facing notifications.

---

## Related Documentation

- [Modules/Project](Modules/project.md) — `project.project`, `project.task`, stage models
- [Modules/sms](Modules/sms.md) — `sms.template`, `_message_sms_with_template()`, delivery pipeline
- [Modules/project](Modules/project.md) — Email notification counterpart for project stages
- [Patterns/Security Patterns](odoo-18/Patterns/Security Patterns.md) — `ir.rule`, `perm_read`, sudo() patterns
- [Core/Fields](Core/Fields.md) — `Many2one` field types, `ondelete` behavior
- [Core/API](Core/API.md) — `@api.model_create_multi`, `write()` hook patterns
