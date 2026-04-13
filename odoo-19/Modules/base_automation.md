---
tags:
  - #odoo
  - #odoo19
  - #modules
  - #automation
  - #server-actions
  - #triggers
  - #webhooks
  - #scheduled-actions
---

# base_automation

> **Module:** `base_automation`
> **Official Name:** Automation Rules
> **Category:** Sales/Sales
> **Depends:** `base`, `digest`, `resource`, `mail`, `sms`
> **License:** LGPL-3
> **Odoo Version:** 19

## Overview

The `base_automation` module provides a powerful **rule-based automation engine** that triggers server-side actions in response to model events. It is the foundation for workflow automation in Odoo, operating entirely server-side without requiring Odoo Studio. Unlike UI-based automations, base_automation rules are defined programmatically as records of `base.automation` and execute via `ir.actions.server` children.

**Key architectural insight:** The module does NOT use the deprecated XML workflow engine. Instead, it patches ORM model methods (`create`, `write`, `unlink`, `_compute_field_value`, `message_post`) at registry load time, injecting automation checks directly into the ORM lifecycle. Time-based triggers use the `ir.cron` scheduler.

---

## Module Architecture

```
base_automation/
├── models/
│   ├── __init__.py
│   ├── base_automation.py      # Core model: base.automation
│   └── ir_actions_server.py    # IrActionsServer + IrCron extensions
├── views/
│   ├── base_automation_views.xml     # Form, tree, kanban, search, action
│   └── ir_actions_server_views.xml  # View extension for server actions
├── data/
│   ├── base_automation_data.xml     # ir.cron scheduler record
│   └── digest_data.xml
├── security/
│   └── ir.model.access.csv
└── __manifest__.py
```

### Dependencies Purpose

| Module | Purpose |
|--------|---------|
| `base` | Core ORM, `ir.model`, `ir.model.fields` |
| `digest` | Digest emails (weekly/monthly automation digests) |
| `resource` | `resource.calendar` for working-day-based time triggers |
| `mail` | `mail.thread`, message posting hooks, mail activity mixin |
| `sms` | SMS action type in `ir.actions.server` |

---

## 1. Core Model: `base.automation`

### 1.1 Model Definition

```python
class BaseAutomation(models.Model):
    _name = 'base.automation'
    _description = 'Automation Rule'
    _inherit = ['mail.thread', 'mail.activity.mixin']
```

The model inherits from `mail.thread` and `mail.activity.mixin` to enable **chatter tracking** on automation rule records. All changes to automation rules (activation, deactivation, field modifications) are tracked in the chatter. This is critical for auditability in production environments.

### 1.2 Field Reference (L2)

#### Identification Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | `Char` | Yes | — | Automation rule name, translatable, tracked in chatter |
| `description` | `Html` | No | — | Internal documentation explaining what the rule does and why |
| `active` | `Boolean` | No | `True` | When `False`, rule is hidden from UI and not executed |
| `model_id` | `Many2one(ir.model)` | Yes | — | Target model for this automation rule; domain restricts to non-abstract models |
| `model_name` | `Char` (related, readonly) | — | — | The `model` string of the target model (e.g., `"sale.order"`) |
| `model_is_mail_thread` | `Boolean` (related, readonly) | — | — | Whether target model inherits from `mail.thread` |

#### Trigger Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `trigger` | `Selection` | Yes | The event type that fires this rule. Stored and tracked. |
| `trigger_field_ids` | `Many2many(ir.model.fields)` | No | Watched fields for `on_create_or_write`; if empty, all fields are watched |
| `on_change_field_ids` | `Many2many(ir.model.fields)` | No | Watched fields for `on_change` trigger |
| `trg_field_ref` | `Many2oneReference` | No | Reference value for `on_stage_set` and `on_tag_set` triggers |
| `trg_field_ref_model_name` | `Char` (computed) | No | Model name for the referenced field in `on_stage_set`/`on_tag_set` |
| `trg_selection_field_id` | `Many2one(ir.model.fields.selection)` | No | Selected value for `on_state_set` and `on_priority_set` |
| `trg_date_id` | `Many2one(ir.model.fields)` | Conditional | Date/datetime field for time-based triggers (`on_time`, `on_time_created`, `on_time_updated`) |
| `trg_date_range` | `Integer` | Conditional | Delay offset (positive integer) for time triggers |
| `trg_date_range_type` | `Selection` | Conditional | Unit: `minutes`, `hour`, `day`, `month` |
| `trg_date_range_mode` | `Selection` | Conditional | `after` or `before` the trigger date |
| `trg_date_calendar_id` | `Many2one(resource.calendar)` | No | Calendar for working-day-based delays (only for day-based triggers) |

#### Domain/Filter Fields

| Field | Type | Description |
|-------|------|-------------|
| `filter_domain` | `Char` | Post-condition domain evaluated at execution time to filter which records the rule applies to |
| `filter_pre_domain` | `Char` | Pre-condition domain evaluated BEFORE write (only for `on_tag_set` trigger currently) |
| `previous_domain` | `Char` | Stores previous `filter_domain` value; used by `_onchange_domain` to track field changes |

#### Action Fields

| Field | Type | Description |
|-------|------|-------------|
| `action_server_ids` | `One2many(ir.actions.server)` | Child server actions executed when the rule fires |

#### Webhook Fields

| Field | Type | Description |
|-------|------|-------------|
| `url` | `Char` (computed) | The webhook endpoint URL; only non-empty when `trigger == 'on_webhook'` |
| `webhook_uuid` | `Char` | Unique UUID for the webhook; used in URL path `/web/hook/<uuid>` |
| `record_getter` | `Char` | Python code snippet to resolve the target record from the webhook payload |
| `log_webhook_calls` | `Boolean` | When `True`, webhook calls are logged to `ir.logging` |

#### Metadata Fields

| Field | Type | Description |
|-------|------|-------------|
| `last_run` | `Datetime` | Timestamp of the last successful execution of time-based triggers |

### 1.3 Trigger Types (L2)

The `trigger` field defines which model event fires the automation rule.

#### Creation Triggers (`CREATE_TRIGGERS`)

```python
CREATE_TRIGGERS = [
    'on_create',              # Fires when a new record is created
    'on_create_or_write',     # Fires on create AND any subsequent write
    'on_priority_set',        # Fires when the `priority` (selection) field changes
    'on_stage_set',           # Fires when the `stage_id` (many2one) field changes
    'on_state_set',           # Fires when the `state` (selection) field changes
    'on_tag_set',             # Fires when a tag is added to `tag_ids` (many2many)
    'on_user_set',            # Fires when a user field (`user_id`, `user_ids`) is set
]
```

#### Write Triggers (`WRITE_TRIGGERS`)

```python
WRITE_TRIGGERS = [
    'on_write',               # DEPRECATED: Fires on any field update (use on_create_or_write)
    'on_archive',             # Fires when `active` boolean is set to False
    'on_unarchive',           # Fires when `active` boolean is set to True
    'on_create_or_write',
    'on_priority_set',
    'on_stage_set',
    'on_state_set',
    'on_tag_set',
    'on_user_set',
]
```

`WRITE_TRIGGERS` is the union of the above plus all `CREATE_TRIGGERS` (the list is pre-computed as `CREATE_WRITE_SET`).

#### Time-Based Triggers (`TIME_TRIGGERS`)

```python
TIME_TRIGGERS = [
    'on_time',                # Based on a date field: fires at a relative offset from that date
    'on_time_created',        # Fires X minutes/hours/days/months after record creation
    'on_time_updated',        # Fires X minutes/hours/days/months after last write_date
]
```

#### Mail Triggers (`MAIL_TRIGGERS`)

```python
MAIL_TRIGGERS = (
    "on_message_received",    # Fires when an external message arrives (customer email)
    "on_message_sent",        # Fires when a message is sent to a customer
)
```

#### Special Triggers

| Trigger | Description |
|---------|-------------|
| `on_unlink` | Fires when a record is deleted |
| `on_change` | Fires on UI onchange (form field change, before save) |
| `on_webhook` | Fires when an HTTP POST is received at `/web/hook/<uuid>` |

#### Automatic Filter Domain Derivation

For specific trigger types, `filter_domain` is **automatically computed** from the trigger configuration:

```python
case 'on_state_set' | 'on_priority_set':
    value = automation.trg_selection_field_id.value
    automation.filter_domain = repr([(field.name, '=', value)])

case 'on_stage_set':
    automation.filter_domain = repr([(field.name, '=', automation.trg_field_ref])])

case 'on_tag_set':
    automation.filter_domain = repr([(field.name, 'in', [automation.trg_field_ref])])

case 'on_user_set':
    automation.filter_domain = repr([(field.name, '!=', False)])

case 'on_archive':
    automation.filter_domain = repr([(field.name, '=', False)])

case 'on_unarchive':
    automation.filter_domain = repr([(field.name, '=', True)])
```

For `on_tag_set`, `filter_pre_domain` is also auto-computed as `[('tag_ids', 'not in', [value])]` — this ensures the tag is being **added**, not already present.

### 1.4 `_get_trigger_specific_field()` — Field Resolution by Trigger

This method resolves the canonical field(s) that a given trigger type watches. It is the backbone of auto-computed filter domains:

```python
def _get_trigger_specific_field(self):
    self.ensure_one()
    match self.trigger:
        case 'on_create_or_write':
            return _get_domain_fields(self.env, self.model_id.model, self.filter_domain)
        case 'on_stage_set':
            domain = [('ttype', '=', 'many2one'), ('name', 'in', ['stage_id', 'x_studio_stage_id'])]
        case 'on_tag_set':
            domain = [('ttype', '=', 'many2many'), ('name', 'in', ['tag_ids', 'x_studio_tag_ids'])]
        case 'on_priority_set':
            domain = [('ttype', '=', 'selection'), ('name', 'in', ['priority', 'x_studio_priority'])]
        case 'on_state_set':
            domain = [('ttype', '=', 'selection'), ('name', 'in', ['state', 'x_studio_state'])]
        case 'on_user_set':
            domain = [
                ('relation', '=', 'res.users'),
                ('ttype', 'in', ['many2one', 'many2many']),
                ('name', 'in', ['user_id', 'user_ids', 'x_studio_user_id', 'x_studio_user_ids']),
            ]
        case 'on_archive' | 'on_unarchive':
            domain = [('ttype', '=', 'boolean'), ('name', 'in', ['active', 'x_active'])]
        case 'on_time_created':
            domain = [('ttype', '=', 'datetime'), ('name', '=', 'create_date')]
        case 'on_time_updated':
            domain = [('ttype', '=', 'datetime'), ('name', '=', 'write_date')]
        case _:
            return self.env['ir.model.fields']
    domain += [('model_id', '=', self.model_id.id)]
    return self.env['ir.model.fields'].search(domain, limit=1)
```

**L4 Design insight:** The field resolution uses standard field naming conventions (`stage_id`, `tag_ids`, `state`, `priority`, `user_id`, `active`) plus their `x_studio_` counterparts (created by Studio). This means the automation system works out-of-the-box with standard Odoo models without explicit field configuration.

### 1.5 Action Server Integration

Each `base.automation` record can have multiple child `ir.actions.server` records stored in `action_server_ids`. The `usage` field of these actions is set to `'base_automation'`, linking them to the parent automation rule:

```python
action_server_ids = fields.One2many(
    "ir.actions.server",
    "base_automation_id",
    context={'default_usage': 'base_automation'},
    compute='_compute_action_server_ids',
    store=True,
    readonly=False,
)
```

`IrActionsServer` is extended in `ir_actions_server.py` to restrict `available_model_ids` to the parent rule's model, validate model matching, and provide `action_open_automation()`.

### 1.6 Critical Field Groups

```python
# Fields that trigger cron AND registry updates when changed
CRITICAL_FIELDS = ['model_id', 'active', 'trigger', 'on_change_field_ids']

# Fields that trigger only cron updates (not full registry reload)
RANGE_FIELDS = ['trg_date_range', 'trg_date_range_type']
```

When any `CRITICAL_FIELD` changes, `_update_registry()` is called to re-patch model methods. When only `RANGE_FIELDS` change, only the cron schedule is updated — a significant performance optimization.

### 1.7 Validation Constraints

| Constraint | Method | What it checks |
|-----------|--------|----------------|
| Mail trigger on non-mail model | `_check_trigger()` | `MAIL_TRIGGERS` require `model_id.is_mail_thread == True` |
| Action model matches rule model | `_check_action_server_model()` | All child actions must have `model_id == rule.model_id` |
| Time trigger delay is positive | `_check_time_trigger()` | `trg_date_range >= 0`; use "before" mode for negative |
| Trigger/action compatibility | `_check_trigger_state()` | on_change: only code; on_unlink: no mail/followers/activity; no unresolved warnings |

---

## 2. Extended Models

### 2.1 `ir.actions.server` Extension (`ir_actions_server.py`)

```python
class IrActionsServer(models.Model):
    _inherit = "ir.actions.server"

    usage = fields.Selection(selection_add=[
        ('base_automation', 'Automation Rule')
    ], ondelete={'base_automation': 'cascade'})

    base_automation_id = fields.Many2one(
        'base.automation',
        string='Automation Rule',
        index='btree_not_null',
        ondelete='cascade'
    )
```

#### `_get_children_domain()` Override

```python
def _get_children_domain(self):
    return super()._get_children_domain() & Domain("base_automation_id", "=", False)
```

Prevents multi-actions (`state == 'multi'`) from linking to automation rule actions as children. This enforces a clean separation: automation actions are leaf nodes in the server action graph.

#### `_compute_available_model_ids()` Override

For server actions with `usage == 'base_automation'`, the available models are restricted to only the automation rule's model:

```python
@api.depends('usage')
def _compute_available_model_ids(self):
    super()._compute_available_model_ids()
    rule_based = self.filtered(lambda action: action.usage == 'base_automation')
    for action in rule_based:
        rule_model = action.base_automation_id.model_id
        action.available_model_ids = rule_model.ids if rule_model in action.available_model_ids else []
```

#### `_get_eval_context()` Extension

Injects webhook payload and `json_scriptsafe` into Python code actions:

```python
def _get_eval_context(self, action=None):
    eval_context = super()._get_eval_context(action)
    if action and action.state == "code":
        eval_context['json'] = json_scriptsafe
        payload = get_webhook_request_payload()
        if payload:
            eval_context["payload"] = payload
    return eval_context
```

**L4 Security:** `json_scriptsafe` (not `json`) is used to prevent unsafe JSON operations in Python code actions executed via webhooks.

### 2.2 `ir.cron` Extension

```python
class IrCron(models.Model):
    _inherit = "ir.cron"

    def action_open_automation(self):
        return self.ir_actions_server_id.action_open_automation()
```

Enables navigation from the scheduled action form to the underlying automation rule. The `ir_actions_server_id` field links the cron to its `ir.actions.server` record, which links to `base.automation` via `base_automation_id`.

---

## 3. Domain Evaluation Engine (L3)

### 3.1 Safe Domain Field Extraction

The module uses a **regex-based parser** (`DOMAIN_FIELDS_RE`) to extract field names from domain expressions without using `safe_eval`:

```python
DOMAIN_FIELDS_RE = re.compile(r"""
    [([]\s*                 # opening bracket with any whitespace
    (?P<quote>['"])         # opening quote
    (?P<field>[a-z]\w*)     # field name, should start with a letter
    (?:\.[.\w]*)?           # dot followed by dots or text for relation traversal
    (?P=quote)              # closing quote, matching the opening one
    (?:[^,]*?,){2}          # anything with two commas (triplet)
    [^,]*?[()[\]]           # anything except comma followed by closing bracket
""", re.VERBOSE)
```

**Why regex instead of safe_eval?** Because `_get_domain_fields()` is called from a **compute method**, which can be triggered by an onchange from a maliciously crafted domain. Using `safe_eval` here would create a code injection vector. The regex parser extracts only field names, which are then resolved through the ORM, completely avoiding arbitrary code execution.

The regex specifically targets domain **triplets** — patterns like `('field_name', 'operator', value)` — by requiring exactly two commas between the opening and closing brackets. This prevents matching field names inside string values or comments.

### 3.2 `_get_eval_context()` — Python Code Sandbox

```python
def _get_eval_context(self, payload=None):
    self.ensure_one()
    model = self.env[self.model_name]
    eval_context = {
        'datetime': safe_eval.datetime,
        'dateutil': safe_eval.dateutil,
        'time': safe_eval.time,
        'uid': self.env.uid,
        'user': self.env.user,
        'model': model,
    }
    if payload is not None:
        eval_context['payload'] = payload
    return eval_context
```

This context is used for:
- Evaluating `filter_domain` and `filter_pre_domain`
- Evaluating `record_getter` in webhooks
- Python code actions in server actions triggered by the automation

**L4 Security boundary:** Only `datetime`, `dateutil`, `time`, `uid`, `user`, and `model` are available. There is no direct database access (no `env.cr`), no `self`, and no arbitrary imports. The `payload` key is added only when processing webhook-triggered automations. Automation rules cannot escalate privileges through Python code to gain raw SQL or filesystem access.

---

## 4. Trigger Execution Pipeline (L3)

### 4.1 Hook Registration: `_register_hook()`

The `_register_hook()` method is called when the Odoo registry is loaded. It iterates over all `base.automation` records and **patches the corresponding model classes** with custom methods that intercept ORM operations. The patching uses a `patched_models` defaultdict to ensure each model-method combination is only patched once:

```python
patched_models = defaultdict(set)

def patch(model, name, method):
    if model not in patched_models[name]:
        patched_models[name].add(model)
        ModelClass = model.env.registry[model._name]
        method.origin = getattr(ModelClass, name)
        setattr(ModelClass, name, method)
```

Each factory function (`make_create()`, `make_write()`, etc.) uses a closure pattern where `method.origin` stores the original method. This ensures the original ORM behavior is always preserved even when multiple automations target the same model.

#### Model Method Patches

| Model Method | Patched For | Purpose |
|---|---|---|
| `create` | `CREATE_TRIGGERS` | Intercept record creation |
| `write` | `WRITE_TRIGGERS` | Intercept record updates |
| `_compute_field_value` | `WRITE_TRIGGERS` | Intercept field recomputations |
| `unlink` | `['on_unlink']` | Intercept record deletion |
| `message_post` | `MAIL_TRIGGERS` | Intercept mail thread messages |
| `_onchange_methods` | `['on_change']` | Register onchange handlers per field |

### 4.2 `make_write()` Deep Dive

```python
def make_write():
    def write(self, vals, **kw):
        automations = self.env['base.automation']._get_actions(self, WRITE_TRIGGERS)
        if not (automations and self):
            return write.origin(self, vals, **kw)

        records = self.with_env(automations.env).filtered('id')

        # Preconditions checked BEFORE write
        pre = {a: a._filter_pre(records) for a in automations}

        # Capture old values before write (stored fields only)
        old_values = {
            record.id: {field_name: record[field_name]
                        for field_name in vals
                        if field_name in record._fields and record._fields[field_name].store}
            for record in records
        }

        write.origin(self.with_env(automations.env), vals, **kw)

        for automation in automations.with_context(old_values=old_values):
            records, domain_post = automation._filter_post_export_domain(
                pre[automation], feedback=True
            )
            automation._process(records, domain_post=domain_post)
        return True
    return write
```

**L4 key insight:** Preconditions (`_filter_pre`) are evaluated BEFORE the write using current DB state. Postconditions (`_filter_post`) are evaluated AFTER the write using the new state. This enables "fire when state changes TO 'done'" patterns where `pre: state != done` and `post: state == done`.

The old values capture is **restricted to stored fields only** (`record._fields[field_name].store`). This means computed fields are not tracked for change detection, which is correct since they are handled by the `_compute_field_value` hook separately.

### 4.3 `make_compute_field_value()` — Recomputation Hook

This patch catches field updates made by **stored computed fields**. When a computed field is recalculated, the new value may trigger automations:

```python
def make_compute_field_value():
    def _compute_field_value(self, field):
        stored_fnames = [f.name for f in self.pool.field_computed[field] if f.store]
        if not stored_fnames:
            return _compute_field_value.origin(self, field)

        automations = self.env['base.automation']._get_actions(self, WRITE_TRIGGERS)
        records = self.filtered('id').with_env(automations.env)
        if not (automations and records):
            _compute_field_value.origin(self, field)
            return True

        # All stored fields computed by this function are considered "changed"
        changed_fields = [f for f in records._fields.values() if f.compute == field.compute]
        pre = {a: a.with_context(changed_fields=changed_fields)._filter_pre(records) for a in automations}

        old_values = {record.id: {fname: record[fname] for fname in stored_fnames} for record in records}

        _compute_field_value.origin(self, field)

        for automation in automations.with_context(old_values=old_values):
            records, domain_post = automation._filter_post_export_domain(
                pre[automation], feedback=True
            )
            automation._process(records, domain_post=domain_post)
        return True
    return _compute_field_value
```

**L4 edge case:** The `changed_fields` context is used in `_filter_pre()` to preserve computed fields that depend on the currently changing field. Without this, computed fields would be prematurely recalculated during the precondition check, potentially losing their original values before the postcondition is evaluated.

### 4.4 Pre-condition Filtering: `_filter_pre()`

The `_filter_pre()` method evaluates `filter_pre_domain` **before** the record is modified. Used for `on_tag_set` triggers where it checks that the tag is NOT already present before the new tag is added:

```python
filter_pre_domain = [('tag_ids', 'not in', [tag_id])]
# Ensures the tag is being ADDED, not already present
```

The `__action_feedback` context flag enables detection of recursive automation executions during precondition evaluation. When set, the `__action_done` dictionary is modified **in place**, allowing automations triggered during precondition evaluation to be tracked before the postcondition check.

The `to_compute` handling preserves computed fields that depend on changing fields:

```python
to_compute = {
    dep: comp
    for f in changed_fields
    for dep in self.env.registry.get_dependent_fields(f)
    if (comp := self.env.records_to_compute(dep))
}
records = records.with_context(changed_fields=()).sudo().filtered_domain(domain).sudo(records.env.su)
for dep, comp in to_compute.items():
    self.env.add_to_compute(dep, comp)
```

### 4.5 Post-condition Filtering: `_filter_post()`

```python
def _filter_post_export_domain(self, records, feedback=False):
    self_sudo = self.sudo()
    if self_sudo.filter_domain and records:
        if feedback:
            records = records.with_context(__action_feedback=True)
        domain = safe_eval.safe_eval(self_sudo.filter_domain, self._get_eval_context())
        return records.sudo().filtered_domain(domain).with_env(records.env), domain
    else:
        return records, None
```

**Evaluation as superuser:** The `filtered_domain` is called with `.sudo()` because automation rules should execute regardless of the triggering user's record rules. The result is then switched back to the original environment to maintain the correct security context for subsequent operations.

### 4.6 Main Processing: `_process()`

```python
def _process(self, records, domain_post=None):
    # 1. Deduplicate: filter out already-processed records
    automation_done = self.env.context.get('__action_done', {})
    records_done = automation_done.get(self, records.browse())
    records -= records_done
    if not records:
        return

    # 2. Mark as done (prevents recursion)
    if self.env.context.get('__action_feedback'):
        automation_done[self] = records_done + records  # modify in place
    else:
        automation_done = dict(automation_done)
        automation_done[self] = records_done + records
        self = self.with_context(__action_done=automation_done)
        records = records.with_context(__action_done=automation_done)

    # 3. Filter by trigger fields (watched fields only)
    records = records.filtered(self._check_trigger_fields)
    automation_done[self] = records_done + records

    # 4. Set date_automation_last if field exists
    if records and 'date_automation_last' in records._fields:
        records.date_automation_last = self.env.cr.now()

    # 5. Execute all child server actions
    contexts = [
        {
            'active_model': record._name,
            'active_ids': record.ids,
            'active_id': record.id,
            'domain_post': domain_post,
        }
        for record in records
    ]

    for action in self.sudo().action_server_ids:
        for ctx in contexts:
            try:
                action.with_context(**ctx).run()
            except Exception as e:
                self._add_postmortem(e)
                raise
```

**Deduplication via `__action_done`:** Tracks which automations have been processed on which records. Modified **in place** during pre/post filtering (where the context dict is shared with compute methods), copied otherwise.

**Trigger field filtering:** `_check_trigger_fields()` returns `True` if any watched field changed. On creation (`old_values is None`), all fields are considered changed. This enables `on_create_or_write` to fire on newly created records.

### 4.7 Time-Based Record Search: `_search_time_based_automation_records()`

Finds records matching a time-based trigger. Key behaviors:

**Standard date/datetime:** Searches for records where `date_field` is in the range `(last_run + offset, until + offset)`. The offset is negated for "before" mode.

**Non-stored date fields:** Falls back to `Model.search(domain).filtered_domain(time_domain)` — a less performant but necessary approach for computed date fields.

**Calendar-based day triggers:** Uses `resource.calendar.plan_days()` for working-day-relative dates. The calendar is fetched per-record via `_get_calendar()`, which is designed to be overridden to support per-record calendars:

```python
def calendar_filter(record):
    record_dt = get_record_dt(record)
    calendar = self._get_calendar(automation, record)  # overridable
    if calendar.id not in past_until:
        past_until[calendar.id] = calendar.plan_days(date_range, until, compute_leaves=True)
        past_last_run[calendar.id] = calendar.plan_days(date_range, last_run, compute_leaves=True)
    return past_last_run[calendar.id] <= record_dt < past_until[calendar.id]
```

**Caching per calendar:** Results are cached per calendar ID (`past_until`/`past_last_run` dicts), avoiding repeated `plan_days()` calls for records sharing the same calendar.

**`date_automation_last` special handling:** When `trg_date_id` points to this field and the model has `create_date`, records with no `date_automation_last` value are matched using `create_date` instead. This enables "process once after creation" semantics.

### 4.8 Cron Processing: `_cron_process_time_based_actions()`

```python
@api.model
def _cron_process_time_based_actions(self):
    if '__action_done' not in self.env.context:
        self = self.with_context(__action_done={})

    final_exception = None
    automations = self.with_context(active_test=True).search([('trigger', 'in', TIME_TRIGGERS)])
    self.env['ir.cron']._commit_progress(remaining=len(automations))

    for automation in automations:
        try:
            if not automation.active:
                continue
        except MissingError:
            continue

        now = self.env.cr.now()
        records = automation._search_time_based_automation_records(until=now)

        try:
            for record in records:
                automation._process(record)
            self.env.flush_all()
        except Exception as e:
            self.env.cr.rollback()
            _logger.exception("Error in time-based automation rule `%s`.", automation.name)
            final_exception = e
            continue

        automation.write({'last_run': now})
        if not self.env['ir.cron']._commit_progress(1):
            break

    if final_exception is not None:
        raise final_exception
```

**Per-automation rollback:** Each failed automation rolls back independently, enabling other automations to continue. The final exception is re-raised to mark the cron as failed.

**Progress tracking:** `_commit_progress()` commits intermediate progress, enabling long-running cron jobs to survive worker restarts. The cron breaks early if the remaining count reaches zero (all automations processed).

**`last_run` only on success:** If an automation fails, `last_run` is NOT updated, so the automation retries on the next cron run with the same `last_run` timestamp.

---

## 5. Webhook Trigger System (L3)

### 5.1 Endpoint Registration

Webhook automations register endpoints at `/web/hook/<webhook_uuid>`. The URL is computed as:

```python
automation.url = "%s/web/hook/%s" % (automation.get_base_url(), automation.webhook_uuid)
# e.g., https://my-odoo.example.com/web/hook/a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

### 5.2 Default Record Getter

```python
record_getter = fields.Char(
    default="model.env[payload.get('_model')].browse(int(payload.get('_id')))"
)
```

Expects a JSON payload with `_model` and `_id` fields, enabling Odoo-to-Odoo webhook communication out of the box. For third-party integrations, `record_getter` can be customized.

### 5.3 Webhook Execution Flow

```python
def _execute_webhook(self, payload):
    ir_logging_sudo = self.env['ir.logging'].sudo()
    msg = "Webhook #%s triggered with payload %s"

    if self.log_webhook_calls:
        ir_logging_sudo.create(self._prepare_loggin_values(message=msg % (self.id, payload)))

    record = self.env[self.model_name]
    if self.record_getter:
        try:
            record = safe_eval.safe_eval(self.record_getter, self._get_eval_context(payload=payload))
        except Exception as e:
            # log + raise
            raise e

    if not record.exists():
        raise exceptions.ValidationError(_("No record to run the automation on was found."))

    return self._process(record)
```

Errors at any stage are logged to `ir.logging` if `log_webhook_calls` is enabled, with full tracebacks.

### 5.4 Webhook UUID Rotation

```python
def action_rotate_webhook_uuid(self):
    for automation in self:
        automation.webhook_uuid = str(uuid4())
```

Regenerates the webhook URL when the old URL has been compromised. The old URL becomes invalid immediately.

---

## 6. Child Action Execution (L3)

### 6.1 Action Server States and Trigger Compatibility

| Trigger | Allowed Action States | Forbidden |
|---------|----------------------|-----------|
| `on_unlink` | All except mail/followers/activity | `mail_post`, `followers`, `next_activity` |
| `on_change` | Only `code` | All other states |
| All others | All states | None |

These constraints are enforced via `_check_trigger_state()`. The method also validates that no action has an unresolved warning.

### 6.2 OnChange Action Execution

For `on_change` triggers, server actions are registered per-field on the model's `_onchange_methods` dictionary:

```python
def make_onchange(automation_rule_id):
    def base_automation_onchange(self):
        automation_rule = self.env['base.automation'].browse(automation_rule_id)
        if not automation_rule._filter_post(self):
            return

        result = {}
        actions = automation_rule.sudo().action_server_ids.with_context(
            active_model=self._name,
            active_id=self._origin.id,
            active_ids=self._origin.ids,
            onchange_self=self,
        )
        for action in actions:
            res = action.run()
            if res:
                if 'value' in res:
                    res['value'].pop('id', None)
                    self.update({key: val for key, val in res['value'].items() if key in self._fields})
                if 'domain' in res:
                    result.setdefault('domain', {}).update(res['domain'])
                if 'warning' in res:
                    result['warning'] = res["warning"]
        return result
    return base_automation_onchange
```

**L4 edge case:** The `id` field is explicitly excluded from value updates (`pop('id', None)`) to prevent attempting to write the record ID on a new (unsaved) record during an onchange. Fields that don't exist on the model are also filtered out, preventing crashes from mismatched field names in the action code.

---

## 7. Registry and Cron Management (L3)

### 7.1 `_update_registry()` — Model Patch Management

```python
def _update_registry(self):
    if self.env.registry.ready and not self.env.context.get('import_file'):
        self._unregister_hook()
        self._register_hook()
        self.env.registry.registry_invalidated = True
```

The registry is only updated when:
- The registry is fully ready (not during module installation when models are being built)
- The operation is not an import file (not during data migration)

The `registry_invalidated` flag notifies other workers (in multi-process deployments) to reload the registry on their next request. This ensures all workers stay synchronized.

### 7.2 `_update_cron()` — Scheduler Configuration

```python
def _update_cron(self):
    cron = self.env.ref('base_automation.ir_cron_data_base_automation_check', ...)
    try:
        cron.lock_for_update(allow_referencing=True)
    except LockError:
        return

    automations = self.with_context(active_test=True).search([('trigger', 'in', TIME_TRIGGERS)])
    interval_number, interval_type = self._get_cron_interval(automations)
    cron.write({'active': bool(automations)})

    # Only decrease interval (increase frequency), never slow down
    new_cron_timedelta = TIMEDELTA_TYPES[interval_type](interval_number)
    if new_cron_timedelta < actual_cron_timedelta:
        cron.write({'interval_type': interval_type, 'interval_number': interval_number})
```

**Lock acquisition:** Prevents race conditions in multi-process deployments. If lock fails, update is skipped — the next automation write will retry.

**Frequency-only increase:** Cron interval is only decreased, never increased. When all time-based automations are deleted, the cron is deactivated but its interval is not restored to the default 4 hours.

### 7.3 `_get_cron_interval()`

```python
def _get_cron_interval(self, automations=None):
    def get_delay(rec):
        return abs(rec.trg_date_range) * DATE_RANGE_FACTOR[rec.trg_date_range_type]

    delays = [d for d in automations.mapped(get_delay) if d]
    interval = min(max(1, min(delays) // 10), 4 * 60) if delays else 4 * 60
    interval_type = 'minutes'
    if interval % 60 == 0:
        interval //= 60
        interval_type = 'hours'
    return interval, interval_type
```

Cron frequency = 10% of the shortest automation delay, clamped to [1 minute, 4 hours]. Example: 30-minute automation -> cron every 3 minutes. 5-minute automation -> cron every 1 minute.

---

## 8. Mail Thread Integration (L3)

### 8.1 Message-Post Hook

```python
def make_message_post():
    def _message_post(self, *args, **kwargs):
        message = _message_post.origin(self, *args, **kwargs)
        message_sudo = message.sudo().with_context(active_test=False)

        if "__action_done" in self.env.context:
            return message
        if message_sudo.is_internal or message_sudo.subtype_id.internal:
            return message
        if message_sudo.message_type in ('notification', 'auto_comment', 'user_notification'):
            return message

        mail_trigger = "on_message_received" if not message_sudo.author_id or message_sudo.author_id.partner_share else "on_message_sent"
        automations = self.env['base.automation']._get_actions(self, [mail_trigger])
        for automation in automations.with_context(old_values=None):
            records = automation._filter_pre(self, feedback=True)
            automation._process(records)

        return message
    return _message_post
```

**Trigger determination:** `on_message_received` fires for messages from external contacts (portal users, customers). `on_message_sent` fires for messages to external contacts. The automation applies only to the **current record**, not to the full thread.

**Skipped message types:** `notification` (system notifications), `auto_comment` (auto-reply tracking), and `user_notification` (user-facing notifications) do not trigger automations.

---

## 9. Odoo 18 to Odoo 19 Changes (L4)

### 9.1 New Trigger Types

- **`on_create_or_write`** replaces `on_write` as the recommended update trigger
- **`on_webhook`** — HTTP webhook integration with UUID-based URL scheme
- **`on_time_created`** and **`on_time_updated`** — time-based triggers relative to creation/modification timestamps

### 9.2 Deprecated `_check()` Method

```python
@api.deprecated("Since 19.0, use _cron_process_time_based_automations")
def _check(self, automatic=False, use_new_cursor=False):
    if not automatic:
        raise RuntimeError("can run time-based automations only in automatic mode")
    self._cron_process_time_based_actions()
```

Old `ir.cron` records pointing to `_check()` continue to work (the method is deprecated, not removed), but new automations use `_cron_process_time_based_actions()` directly.

### 9.3 Regex-Based Domain Parsing (Security Fix)

```python
# The regex parser was introduced in response to:
# https://github.com/odoo/odoo/pull/189772#issuecomment-2548804283
for match in DOMAIN_FIELDS_RE.finditer(domain):
    if field := match.groupdict().get('field'):
        fields |= IrModelFields._get(model, field)
```

Replaced `safe_eval`-based domain parsing that was unsafe in compute/onchange contexts. This was a security fix backported to Odoo 18 as well.

### 9.4 `record_getter` Default Change

```python
# Odoo 19 default:
default="model.env[payload.get('_model')].browse(int(payload.get('_id')))"
```

Odoo 18 used a different default. The Odoo 19 default supports cross-instance Odoo communication with standard `_model`/`_id` payload fields.

### 9.5 `date_automation_last` Field Support

When `trg_date_id` points to the `date_automation_last` field on the target model, `_process()` sets it to the current timestamp for each processed record. This enables "one-shot" automations that only fire once per record.

Special handling in `_search_time_based_automation_records()` treats records with `date_automation_last == False` as "never processed," using `create_date` for the time range instead.

### 9.6 `_compute_field_value` Patch Addition

The patch for `_compute_field_value` was added to properly handle automation triggers when stored computed fields change. This ensures field recomputation by the ORM (not just direct writes) fires automation rules.

### 9.7 Webhook Logging and UUID Rotation

`log_webhook_calls` field and `action_rotate_webhook_uuid()` method are new in Odoo 19, providing observability and key rotation for webhook integrations.

### 9.8 `record_variable_timeout` — Not Present

The spec mentions `record_variable_timeout` — this field does not exist in the Odoo 19 source code. It may be a planned feature for a future version or a misremembered field name.

---

## 10. Performance Implications (L4)

### 10.1 Patch Registration Overhead

The `_register_hook()` method patches model classes at registry load time, affecting every `create`, `write`, `unlink`, `_compute_field_value`, and `message_post` call on every patched model. However, the overhead is minimal:

```python
def make_write():
    def write(self, vals, **kw):
        automations = self.env['base.automation']._get_actions(self, WRITE_TRIGGERS)
        if not (automations and self):  # Fast path: no automations
            return write.origin(self, vals, **kw)
```

The `_get_actions()` call is a simple database search with `active_test=True` context and a domain on `(model_name, trigger)`. For models with no automations, this is a single fast query per operation.

### 10.2 Field Watching Optimization

`on_create_or_write` triggers with explicit `trigger_field_ids` reduce processing to only relevant field changes. The UI auto-populates this from the domain, so most automations only evaluate when needed.

### 10.3 Batch vs. Individual Processing

Time-based automations process records **individually** (not as batches), ensuring each record's actions execute independently. However, this means N automations with M records each will execute N x M server action transactions. For high-volume models, this can be a bottleneck.

### 10.4 Domain Evaluation Performance

The regex parser in `_get_domain_fields()` is O(n) where n is the domain string length. Results are cached by the ORM's compute system, so repeated evaluations of the same domain are fast.

### 10.5 Cron Interval and System Load

The cron interval is dynamically adjusted to 10% of the shortest automation delay. A system with a 10-minute automation runs the cron every 1 minute. Combined with many time-based automations, this can increase system load significantly. The 4-hour maximum interval provides a safety ceiling.

### 10.6 Memory Considerations

The `__action_done` context dict grows as automations process records. In very large batch operations (e.g., updating 100,000 records), this dict can become large. The dict is modified in place during `_process()` when `__action_feedback` is set, which keeps memory usage bounded within a single transaction.

---

## 11. Security Considerations (L4)

### 11.1 Code Injection Prevention

The most significant security concern in automation rules is **arbitrary code execution**:

1. **Regex-based domain parsing** for `_get_domain_fields()` — field names extracted via regex, not `safe_eval`. Malicious domains cannot inject code through the automation's domain field.
2. **Restricted `_get_eval_context()`** — only safe Python objects are available. No `env.cr`, no raw SQL access.
3. **ORM-based record access** — all record lookups go through the ORM, respecting ACLs.
4. **`json_scriptsafe` instead of `json`** — prevents unsafe JSON operations in webhook-triggered code actions.
5. **Webhook UUID v4** — 122 bits of randomness make URL guessing infeasible.

### 11.2 Access Control Interaction

Automation rules execute with the **credentials of the triggering user**. When a cron job triggers a time-based automation, it runs as the **superuser**. Child server actions respect ACLs — if the user cannot write to a field, the server action will fail with an AccessError.

The `_add_postmortem()` method attaches the automation ID and name to exceptions for debugging, but only for internal users:

```python
def _add_postmortem(self, e):
    if self.env.user._is_internal():
        e.context['exception_class'] = 'base_automation'
        e.context['base_automation'] = {'id': self.id, 'name': self.sudo().name}
```

### 11.3 Webhook Security

Webhook calls are **not CSRF-protected** since they are designed for machine-to-machine communication. Authentication and authorization must be implemented through `record_getter` logic and server action code. The UUID provides obscurity but not authentication.

### 11.4 Record-Level Security Interaction

Automation rules respect `ir.rule` record rules. The `_filter_post()` method uses `filtered_domain()` which applies record rules. A user cannot use an automation to gain access to records they would not normally see.

### 11.5 Recursive Execution Prevention

The `__action_done` context variable prevents infinite loops when an automation's action modifies a record in a way that would re-trigger the same automation. The context tracks which automations have processed which records, and `_check_trigger_fields()` prevents re-triggering on the same field.

### 11.6 SQL Injection Prevention

The `DOMAIN_FIELDS_RE` regex extracts field names from domain strings. The extracted names are used as arguments to `IrModelFields._get()`, which returns ORM field objects — not raw SQL column names. The domain evaluation itself uses `filtered_domain()` (the ORM method), not raw SQL WHERE clauses.

### 11.7 Privilege Escalation via Stored Computed Fields

An automation with Python code action could potentially write to fields it normally couldn't access. However, since automations run as the triggering user, the ACLs of that user still apply. A malicious admin could still create such automation, but that is a configuration trust issue, not a code vulnerability.

---

## 12. Failure Modes and Error Handling (L3)

### 12.1 Time-Based Automation Failures

1. Transaction rolled back
2. Error logged via `_logger.exception()`
3. Automation skipped; others continue
4. Last exception re-raised to mark cron as failed
5. `last_run` NOT updated — automation retries on next cron run

### 12.2 Write/Create/Unlink Trigger Failures

1. Exception propagates up through the ORM method
2. Entire transaction rolled back (including the triggering write)
3. Exception re-raised with automation context via `_add_postmortem()`
4. User sees error in UI

### 12.3 OnChange Trigger Failures

1. Exception caught in `make_onchange()` and re-raised
2. Automation context attached via `_add_postmortem()`
3. Form displays error as an onchange validation error

### 12.4 Missing Automation Records (Cron Context)

If the automation is deleted mid-execution (concurrent deletion), `MissingError` is caught and the automation is silently skipped.

### 12.5 Webhook Failures

1. **record_getter failure:** Exception re-raised, full traceback logged
2. **Record not found:** `ValidationError` raised, logged if enabled
3. **Automation execution failure:** Exception re-raised, traceback logged

### 12.6 LockError During Cron Update

If `_update_cron()` cannot acquire a lock on the cron record (another process is updating), it skips the update silently. This prevents blocking on concurrent updates in multi-process deployments.

---

## 13. CRUD Operations

### 13.1 `create()` — Registry and Cron Update

```python
@api.model_create_multi
def create(self, vals_list):
    base_automations = super().create(vals_list)
    self._update_cron()
    self._update_registry()
    if base_automations._has_trigger_onchange():
        self.env.registry.clear_cache('templates')
    return base_automations
```

When a new automation is created, the cron is updated (activated if time-based), the registry re-patches target model methods, and template caches are cleared if `on_change` triggers are present.

### 13.2 `write()` — Selective Registry Update

```python
def write(self, vals: dict):
    clear_templates = self._has_trigger_onchange()
    res = super().write(vals)
    if set(vals).intersection(self.CRITICAL_FIELDS):
        self._update_cron()
        self._update_registry()
        if clear_templates or self._has_trigger_onchange():
            self.env.registry.clear_cache('templates')
    elif set(vals).intersection(self.RANGE_FIELDS):
        self._update_cron()  # Only update cron
    return res
```

**Optimization:** Only `RANGE_FIELDS` (`trg_date_range`, `trg_date_range_type`) changed → only cron updated. Full registry re-patch only for `CRITICAL_FIELDS`.

### 13.3 `unlink()` — Cleanup

```python
def unlink(self):
    clear_templates = self._has_trigger_onchange()
    res = super().unlink()
    self._update_cron()
    self._update_registry()
    if clear_templates:
        self.env.registry.clear_cache('templates')
    return res
```

Child `ir.actions.server` records are cascade-deleted via `ondelete='cascade'` on `base_automation_id`.

### 13.4 `copy()` — Action Cloning

```python
def copy(self, default=None):
    actions = self.action_server_ids.copy()
    record_copy = super().copy(default)
    record_copy.action_server_ids = actions
    return record_copy
```

When duplicating an automation rule, child server actions are also duplicated and re-linked to the copy. Each action's copy is a separate record with its own state.

---

## 14. Views and UI

### 14.1 Form View Architecture

The form view uses a custom `base_automation_trigger_selection` widget for the trigger field, providing a grouped selection UI. The trigger field dynamically shows/hides related fields:

- `trg_date_id` — shown only for `on_time` trigger
- `trg_selection_field_id` — shown for `on_state_set` and `on_priority_set`
- `trg_field_ref` — shown for `on_stage_set` and `on_tag_set`
- `filter_pre_domain` — shown for most triggers except create/unlink/change/webhook/time-based
- `filter_domain` — shown for all triggers except `on_webhook`
- `trigger_field_ids` — shown for `on_create_or_write`
- `on_change_field_ids` — shown for `on_change`

### 14.2 Kanban View

The kanban view displays automation rules as cards showing the trigger type and key configuration. The `base_automation_actions_one2many` widget renders child actions inline within the kanban card.

### 14.3 Scheduled Action Button

For time-based triggers, a button links directly to the underlying `ir.cron` scheduler record, enabling administrators to view/modify the cron configuration (priority, retry policy, etc.) directly from the automation form.

### 14.4 Webhook URL Widget

The `url` field (computed for `on_webhook` triggers) uses a dedicated widget that renders a copy-to-clipboard button and a regenerate UUID button, making webhook URL management straightforward.

---

## 15. Edge Cases (L4)

### 15.1 Automation on Abstract Models

`model_id` has domain `("abstract", "=", False)`, preventing automation rules from being created on abstract models. Abstract models cannot be instantiated at runtime, so patching them would serve no purpose.

### 15.2 Automation on `base.automation` Itself

The model allows creating automations on `base.automation` (it is not abstract). This is a valid use case for meta-automation (automations that trigger other automations). However, such automations will not be automatically patched since `_register_hook()` is called at registry load time before any automations exist.

**Workaround:** After creating a self-referential automation, manually trigger `_update_registry()` via a Python console or by writing any field on the automation record.

### 15.3 Computed Fields as Triggers

Stored computed fields are handled by `_compute_field_value`. Non-stored computed fields are NOT tracked for change detection — they are evaluated on demand and their changes cannot be observed by the automation system.

### 15.4 `on_change` on New (Unsaved) Records

`on_change` triggers fire for form field changes on records that may not yet have an ID (`active_id` context variable may be `False`). Server actions executed in this context receive `onchange_self` in the context, which is the unsaved record. Actions that try to write to fields that require an existing record will fail.

### 15.5 Webhook Payload Size

Webhook payloads are loaded via `request.get_json_data()` which parses the entire JSON body into memory. Very large payloads (dozens of MB) could cause memory issues. There is no built-in payload size limit.

### 15.6 Concurrent Automation Modification

If an admin modifies a time-based automation's trigger or model while another automation is being processed by the cron, the behavior is undefined. The `_unregister_hook()` / `_register_hook()` cycle during `write()` temporarily removes all patches, which could cause a race condition if the cron worker is running simultaneously.

**Mitigation:** The `_update_registry()` method is called within a `write()` transaction, so the registry is updated atomically. However, multi-process Odoo deployments with separate workers may still experience brief inconsistencies.

### 15.7 Deleted Module Models

If a module containing a model targeted by an automation rule is uninstalled, `_register_hook()` skips the automation with a `_logger.warning()`:

```python
if Model is None:
    _logger.warning("Automation rule with name '%s' (ID %d) depends on model %s (ID: %d)...",
                    automation_rule.name, automation_rule.id, automation_rule.model_name,
                    automation_rule.model_id.id)
    continue
```

The automation record itself is NOT deleted or deactivated, so the admin is notified of the broken configuration on the automation list view.

---

## 16. Related Concepts

- [Modules/base_automation](modules/base_automation.md) — Server Actions model powering automation actions
- [Modules/mail](modules/mail.md) — Mail Thread integration for message triggers
- [Modules/base_automation](modules/base_automation.md) — Scheduler configuration
- [Modules/resource](modules/resource.md) — Resource Calendar for working-day calculations
- [Core/API](core/api.md) — `@api.model`, `@api.depends`, `@api.onchange` decorators
- [Patterns/Workflow Patterns](patterns/workflow-patterns.md) — State machine and action workflow patterns
- [Core/Fields](core/fields.md) — Field types (Domain, Many2oneReference, etc.)
- [Core/Exceptions](core/exceptions.md) — ValidationError, UserError for automation error handling

---

## 17. Summary: Key Design Patterns

1. **Registry Patching** — Model methods are monkey-patched at startup. Each model is patched exactly once regardless of how many automations target it. `method.origin` preserves the original for chaining.
2. **Context-Based Deduplication** — `__action_done` context prevents recursive execution within transactions. Modified in place during pre/post filtering, copied otherwise.
3. **Computed Trigger Domains** — Filter domains auto-derived from trigger configuration for common patterns (state, stage, tag, user, archive).
4. **Regex Domain Parsing** — Security hardening: field names extracted via regex from domain strings, not via eval. Prevents code injection in onchange contexts.
5. **Per-Automation Transactions** — Time-based automations use individual transactions for fault isolation; write/create/unlink automations share the triggering transaction.
6. **Webhook-First Design** — `record_getter` abstraction enables Odoo-to-Odoo (default `_model`/`_id` payload) and third-party integrations with custom parsing.
7. **UI-Driven Field Watching** — `on_change_field_ids` and `trigger_field_ids` auto-populated from domain field analysis.
8. **Selective Registry Updates** — Only `CRITICAL_FIELDS` trigger full re-patching; `RANGE_FIELDS` only update cron frequency.
9. **Cron Frequency Auto-Tuning** — Scheduler interval set to 10% of the shortest automation delay, clamped to [1 min, 4 hrs].
10. **Message Thread Awareness** — Mail triggers differentiate received/sent based on author's partner sharing status.
11. **Fast Path Optimization** — `_get_actions()` returning empty triggers immediate return to the original ORM method with zero overhead.
12. **Calendar Caching** — `plan_days()` results cached per calendar ID to avoid redundant working-day calculations for records sharing the same calendar.
