---
Module: base_automation
Version: Odoo 18
Type: Core Extension
Tags: #odoo18, #orm, #workflow, #modules, #automation
---

# base_automation

Automated server actions triggered by record events (create, write, unlink, time-based, webhooks, mail). The automation rules are stored as records of `base.automation` and linked to `ir.actions.server` child actions.

## Module Overview

- **Primary model:** `base.automation`
- **Actions model:** `ir.actions.server` (extended, `usage = 'base_automation'`)
- **Cron model:** `ir.cron` (auto-manages the `ir_cron_data_base_automation_check` job)
- **Dependency:** `base`, `base_automation` (own module)
- **Pattern:** Model method monkey-patching in `_register_hook()`

---

## Models

### `base.automation`

```python
class BaseAutomation(models.Model):
    _name = 'base.automation'
    _description = 'Automation Rule'
```

**Key fields:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Rule name (required, translateable) |
| `description` | Html | Free-form description |
| `model_id` | Many2one `ir.model` | Target model (domain: must have fields) |
| `model_name` | Char (related) | Technical model name |
| `model_is_mail_thread` | Boolean (related) | Whether model is a mail thread |
| `action_server_ids` | One2many `ir.actions.server` | Server actions to execute |
| `url` | Char (computed) | Webhook URL (empty unless `trigger == 'on_webhook'`) |
| `webhook_uuid` | Char | UUID for webhook endpoint, generated at create |
| `record_getter` | Char | Python code to retrieve record from webhook payload |
| `log_webhook_calls` | Boolean | Whether to log webhook calls to `ir.logging` |
| `active` | Boolean | Enable/disable rule |
| `trigger` | Selection | Trigger type (computed, stored) |
| `trg_selection_field_id` | Many2one `ir.model.fields.selection` | Selection field value to match |
| `trg_field_ref_model_name` | Char | Model of the trigger reference field |
| `trg_field_ref` | Many2oneReference | ID reference to trigger field value |
| `trg_date_id` | Many2one `ir.model.fields` | Date/datetime field for time triggers |
| `trg_date_range` | Integer | Delay after trigger date (minutes/hours/days/months) |
| `trg_date_range_type` | Selection | Delay unit |
| `trg_date_calendar_id` | Many2one `resource.calendar` | Working calendar for day-based delays |
| `filter_pre_domain` | Char | Domain evaluated BEFORE record update |
| `filter_domain` | Char | Domain evaluated AFTER record update (apply condition) |
| `last_run` | Datetime | When the rule last ran (for time triggers) |
| `on_change_field_ids` | Many2many `ir.model.fields` | Fields that trigger onchange (for `on_change` trigger) |
| `trigger_field_ids` | Many2many `ir.model.fields` | Fields watched for changes |

---

## Triggers

```python
CREATE_TRIGGERS = [
    'on_create',
    'on_create_or_write',
    'on_priority_set',
    'on_stage_set',
    'on_state_set',
    'on_tag_set',
    'on_user_set',
]

WRITE_TRIGGERS = [
    'on_write',
    'on_archive',
    'on_unarchive',
    'on_create_or_write',
    'on_priority_set',
    'on_stage_set',
    'on_state_set',
    'on_tag_set',
    'on_user_set',
]

TIME_TRIGGERS = [
    'on_time',
    'on_time_created',
    'on_time_updated',
]

MAIL_TRIGGERS = ("on_message_received", "on_message_sent")
```

Full trigger selection values:
- `on_stage_set` — Stage is set to a specific value
- `on_user_set` — User is assigned
- `on_tag_set` — Tag is added
- `on_state_set` — State is set to a specific value
- `on_priority_set` — Priority is set
- `on_archive` — Record is archived
- `on_unarchive` — Record is unarchived
- `on_create_or_write` — On save (create or update)
- `on_create` — On creation (deprecated, use `on_create_or_write`)
- `on_write` — On update (deprecated, use `on_create_or_write`)
- `on_unlink` — On deletion
- `on_change` — On UI live change
- `on_time` — Based on date field
- `on_time_created` — After creation (delay relative to `create_date`)
- `on_time_updated` — After last update (delay relative to `write_date`)
- `on_message_received` — Incoming mail message
- `on_message_sent` — Outgoing mail message
- `on_webhook` — Webhook received

---

## Model Patch Architecture

`_register_hook()` monkey-patches model classes dynamically. Each model with at least one automation rule gets the following patches installed:

| Patch | Method | Trigger |
|-------|--------|---------|
| `create` | `make_create()` | `CREATE_TRIGGERS` |
| `write` | `make_write()` | `WRITE_TRIGGERS` |
| `_compute_field_value` | `make_compute_field_value()` | `WRITE_TRIGGERS` (catches computed field updates) |
| `unlink` | `make_unlink()` | `on_unlink` |
| onchange methods | `make_onchange(rule_id)` | `on_change` (appends to `_onchange_methods`) |
| `_message_post` | `make_message_post()` | `MAIL_TRIGGERS` (if model is mail thread) |

### `make_create()`

Intercepts `create()`. Retrieves automations for `CREATE_TRIGGERS`, calls original `create.origin()`, then runs `_filter_post()` and `action_server_ids` for each matching automation.

### `make_write()`

Intercepts `write()`. Reads old values before update, calls original method, then runs post-filter and actions for each automation. Uses `__action_done` context to prevent recursive triggers.

### `make_compute_field_value()`

Catches updates made by field recomputation. Retrieves WRITE_TRIGGERS automations and runs post-filter + actions after the computed field update.

### `make_unlink()`

Retrieves `on_unlink` automations, runs `_filter_post()` and actions **before** calling the original `unlink.origin()`. This is the only case where actions run before the base operation.

### `make_onchange()`

Creates an onchange handler for the given automation rule. Registers it on each `on_change_field_ids` field. Only `Execute Python Code` actions are allowed for `on_change` triggers.

### `make_message_post()`

Hooks into `_message_post()` on mail-thread models. Triggers `on_message_received` for messages from customers/external sources, and `on_message_sent` for internal messages.

---

## Key Methods

### `_get_actions(records, triggers)`

```python
def _get_actions(self, records, triggers):
    """ Return the automations of the given triggers for records' model. """
```

Searches `base.automation` for rules matching the records' model and the given trigger types. Returns a sudo'd recordset.

### `_get_filter_domain_fields()`

Parses `filter_domain` using a regex (`DOMAIN_FIELDS_RE`) to extract all field names referenced in the domain. Returns `ir.model.fields` records. Uses regex instead of `safe_eval` for security in compute/onchange contexts.

### `_process(records, domain_post=None)`

Core execution method. Filters out already-processed records via `__action_done` context, checks trigger fields, updates `date_automation_last`, and runs each `action_server_id` in sudo mode.

### `_check(automatic=False, use_new_cursor=False)`

Scheduler method (`ir.cron`). Called periodically by `base_automation.ir_cron_data_base_automation_check`. Iterates all time-based automations, computes which records are due, and runs `_process()`.

Cron interval is dynamically computed as the minimum delay across all time triggers, capped at 1 minute minimum and 4 hours maximum.

### `_update_cron()`

Called on create/write/unlink of automation records. Updates the cron job's active state and interval based on existing time-based rules.

### `_update_registry()`

Called on create/write/unlink. Re-patches all models by calling `_unregister_hook()` followed by `_register_hook()`, then invalidates the registry cache.

### `_compute_url()`

```python
@api.depends("trigger", "webhook_uuid")
def _compute_url(self):
    for automation in self:
        if automation.trigger != "on_webhook":
            automation.url = ""
        else:
            automation.url = "%s/web/hook/%s" % (automation.get_base_url(), automation.webhook_uuid)
```

### `_execute_webhook(payload)`

Executes the automation for a given webhook payload. Runs `record_getter` code to resolve the target record, then calls `_process()`.

### `action_rotate_webhook_uuid()`

Rotates the webhook UUID (regenerates with `uuid4()`).

### `action_view_webhook_logs()`

Opens `ir.logging` for entries with path `"base_automation(%s)" % self.id`.

### `copy()`

Copies the automation and duplicates all `action_server_ids` via their own `copy()` method.

---

## `ir.actions.server` Extension

```python
class ServerAction(models.Model):
    _inherit = "ir.actions.server"

    usage = fields.Selection(selection_add=[
        ('base_automation', 'Automation Rule')
    ], ondelete={'base_automation': 'cascade'})
    base_automation_id = fields.Many2one('base.automation', string='Automation Rule',
                                         ondelete='cascade')
```

**Constraint:** `_check_model_coherency_with_automation` ensures the action's `model_id` matches the automation rule's model.

**Auto-naming:** `_compute_name()` generates automatic names for automation-linked actions based on their `state` (e.g., `"Update field_name"`, `"Send email: template_name"`).

**Evaluation context:** `_get_eval_context()` adds `json` (from `odoo.tools.json.scriptsafe`) and `payload` (from webhook request) to the Python code eval context.

---

## L4 Notes

- **`__action_done` context:** A dict mapping automation rules to sets of already-processed record IDs. Prevents infinite loops when an automation action writes back to the same record.
- **`__action_feedback` context:** Flagged during pre/post filter evaluation so that `_filter_pre()` can detect if it is being called recursively from within another automation.
- **`date_automation_last` convention:** If the target model has a `date_automation_last` field, it is updated to `Datetime.now()` after processing. This field can be used as the trigger date field to avoid re-processing.
- **Webhook UUID as primary key:** Each `on_webhook` automation gets a unique UUID. The endpoint is `/web/hook/<uuid>`. The `record_getter` code uses `payload.get('_model')` and `payload.get('_id')` by default.
- **Mail thread validation:** Mail triggers (`on_message_received`, `on_message_sent`) are only allowed on models where `model_id.is_mail_thread` is `True`. This is enforced by `_check_trigger()` constraint.
- **`_unregister_hook()`:** Removes all patches by iterating `self.env.registry.values()` and attempting to delete patched methods. Safe to call multiple times (uses `AttributeError` suppression).
- **Performance:** Time-triggered rules use a single cron job whose interval is the minimum delay across all rules. Maximum interval is 4 hours. For rules with calendars and day-based delays, `resource.calendar.plan_days()` is used to compute working-day-accurate deadlines.
