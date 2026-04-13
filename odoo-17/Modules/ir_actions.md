---
tags: [odoo, odoo17, module, ir_actions, ir_rule, research_depth]
research_depth: deep
---

# ir_actions & ir_rule — Deep Research (Odoo 17)

**Source:**
- `addons/base/models/ir_actions.py` (1149 lines)
- `addons/base/models/ir_rule.py` (265 lines)

Files read in full: ir_actions.py (lines 1-1149), ir_rule.py (lines 1-265).

## Action Type Inheritance Map

```
ir.actions.actions (abstract base, _name='ir.actions.actions', _table='ir_actions')
    ├── ir.actions.act_window        → ir_act_window table
    ├── ir.actions.act_window_close  → ir_actions table (shared)
    ├── ir.actions.act_url            → ir_act_url table
    ├── ir.actions.server             → ir_act_server table
    ├── ir.actions.client             → ir_act_client table
    └── ir.actions.report             → ir_act_report_xml table

ir.actions.todo                          → ir_actions (config wizards)
```

All action types inherit `ir.actions.actions` which provides: `name`, `type`, `xml_id`, `help`, `binding_model_id`, `binding_type`, `binding_view_types`. The `type` field identifies the action class at runtime.

---

## ir.actions.actions — Base Action Model

File: `ir_actions.py`, lines 51-220

### All Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Action display name, required, translateable |
| `type` | Char | Action type string (e.g., `"ir.actions.act_window"`). Set as default in subclasses. |
| `xml_id` | Char (computed) | External ID (module.name). Uses `get_external_id()`. |
| `help` | Html | Optional help text for users |
| `binding_model_id` | Many2one ir.model | If set, action appears in sidebar for this model |
| `binding_type` | Selection | `action` (default) or `report`. Controls sidebar section. |
| `binding_view_types` | Char | Comma-separated view types where sidebar action appears. Default `"list,form"` |

### Cache Invalidation (Line 76-87)

Every `create()`, `write()`, and `unlink()` calls `self.env.registry.clear_cache()`. This is because `get_bindings()` and `_get_bindings()` are cached. Changing any action record must invalidate the bindings cache.

### `_get_bindings()` (Line 151-184) — ORMcached

```python
@tools.ormcache('model_name', 'self.env.lang')
def _get_bindings(self, model_name):
    cr.execute("""
        SELECT a.id, a.type, a.binding_type
          FROM ir_actions a
          JOIN ir_model m ON a.binding_model_id = m.id
         WHERE m.model = %s
      ORDER BY a.id
    """, [model_name])
    for action_id, action_model, binding_type in cr.fetchall():
        try:
            action = self.env[action_model].sudo().browse(action_id)
            fields = ['name', 'binding_view_types']
            for field in ('groups_id', 'res_model', 'sequence'):
                if field in action._fields:
                    fields.append(field)
            action = action.read(fields)[0]
            if action.get('groups_id'):
                groups = self.env['res.groups'].browse(action['groups_id'])
                action['groups_id'] = ','.join(ext_id for ext_id in groups._ensure_xml_id().values())
            result[binding_type].append(frozendict(action))
        except (MissingError):
            continue
```

Performance: raw SQL query + sudo read + frozendict. Group IDs converted to external IDs (e.g., `"base.group_user"`) for client-side comparison. Result sorted by ID for action order, then re-sorted by sequence for `action` type.

### `get_bindings()` (Line 122-149)

Filters `_get_bindings()` results by:
1. **Groups**: checks `user_has_groups(groups)` — skips action if user lacks required groups
2. **Read access**: checks `ir.model.access` for `res_model` with mode='read' — skips action if user cannot read target records

Returns dict: `{binding_type: [action_dict, ...]}`.

### `_for_xml_id()` and `_get_action_dict()` (Line 187-207)

`_for_xml_id(full_xml_id)`: Returns action content for XML ID by calling `_get_action_dict()` on the record. Used by `<action id="..."/>` XML tags.

`_get_action_dict()`: Returns dict of readable fields only. Filters with `_get_readable_fields()` per subclass.

### `_get_readable_fields()` — Line 209-220

Default readable fields: `"binding_model_id", "binding_type", "binding_view_types", "display_name", "help", "id", "name", "type", "xml_id"`. Subclasses extend this.

---

## ir.actions.act_window — Window Actions

File: `ir_actions.py`, lines 223-343

The most common action type. Opens list, form, kanban, calendar, graph, pivot, or gantt views.

### All Fields

| Field | Type | Description |
|-------|------|-------------|
| `type` | Char | Default `"ir.actions.act_window"` |
| `view_id` | Many2one ir.ui.view | Specific view to open. Optional. If set, this view is prioritized in `view_mode` |
| `domain` | Char | Domain filter as Python expression string. Applied as `_domain` in the view |
| `context` | Char | Context dict as Python expression, default `"{}"`. Applied as `_context` |
| `res_id` | Integer | Specific record ID to open when `view_mode` is `'form'` only |
| `res_model` | Char | Target model name, required. Validated against known models via `_check_model()` |
| `target` | Selection | `current` (default), `new` (modal), `inline` (edit-in-list), `fullscreen`, `main` |
| `view_mode` | Char | Comma-separated view modes, required, default `"tree,form"`. Duplicates not allowed. No spaces allowed. |
| `mobile_view_mode` | Char | First view mode on mobile, default `"kanban"` |
| `usage` | Char | Used to filter menu and home actions |
| `view_ids` | One2many ir.actions.act_window.view | Explicit ordered list of `(view_id, view_mode)` pairs |
| `views` | Binary (computed) | Resolved ordered list of enabled views as list of `(view_id, view_mode)` tuples |
| `limit` | Integer | Default list page size, default 80 |
| `groups_id` | Many2many res.groups | Groups that can see this action |
| `search_view_id` | Many2one ir.ui.view | Default search view |
| `filter` | Boolean | Enable default filters on the search view |

### `_compute_views()` — Line 239-259

Merges `view_ids` (explicit, ordered) with `view_mode` string (fallback modes):

```python
act.views = [(view.view_id.id, view.view_mode) for view in act.view_ids]
got_modes = [view.view_mode for view in act.view_ids]
all_modes = act.view_mode.split(',')  # e.g., ['tree', 'form']
missing_modes = [mode for mode in all_modes if mode not in got_modes]
if missing_modes:
    if act.view_id.type in missing_modes:
        missing_modes.remove(act.view_id.type)
        act.views.append((act.view_id.id, act.view_id.type))  # view_id first
    act.views.extend([(False, mode) for mode in missing_modes])  # rest as default views
```

Priority: `view_ids` (explicitly ordered) first, then `view_id` (if its type is in `view_mode` but not in `view_ids`), then remaining modes as `(False, view_mode)` (default view for that mode).

### `_check_model()` — Line 231-237

Validates both `res_model` and `binding_model_id.model` against the registry. Raises `ValidationError` if invalid.

### `read()` — Help Message Augmentation — Line 296-310

When reading `help` field, evaluates `context` and calls `model.get_empty_list_help()` to augment the help message with model-specific guidance (e.g., "No invoices found. Create one now.").

### `create()` — Line 312-318

If `name` is not provided but `res_model` is, auto-sets name to the model's description (`model._description`).

### `_existing()` — Line 329-333

```python
@api.model
@tools.ormcache()
def _existing(self):
    self._cr.execute("SELECT id FROM %s" % self._table)
    return set(row[0] for row in self._cr.fetchall())
```

Ormcache'd set of existing action IDs for fast `exists()` checks. Cleared on create/write/unlink via `self.env.registry.clear_cache()` in the parent's write/create.

---

## ir.actions.act_window_close — Close Window Action

File: `ir_actions.py`, lines 378-392

Simple action type that closes the current window. No real fields beyond inherited ones. `_get_readable_fields()` adds `effect` and `infos` — these are not DB fields but are used by the web client for rainbowman animation and action service responses.

---

## ir.actions.act_url — URL Redirect

File: `ir_actions.py`, lines 395-411

| Field | Type | Description |
|-------|------|-------------|
| `url` | Text | Target URL, required |
| `target` | Selection | `new` (new window), `self` (current window), `download` (force file download) |

Readabl

e fields include `close` (boolean) which tells the client to close the current window after opening the URL.

---

## ir.actions.server — Server Actions

File: `ir_actions.py`, lines 433-1031

Server actions run Python code or perform CRUD operations. Can be triggered from:
- "More" menu on list/form views
- Scheduled actions (cron) via `usage='ir_cron'`
- Base automation rules
- Onchange triggers

### All Fields (complete)

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Required |
| `type` | Char | Default `"ir.actions.server"` |
| `usage` | Selection | `ir_actions_server` (default, manual) or `ir_cron` (scheduled) |
| `state` | Selection | Action type — see below |
| `sequence` | Integer | Default 5. Execution order when multiple actions are triggered |
| `model_id` | Many2one ir.model | Required. The base model the action operates on. Indexed. |
| `available_model_ids` | Many2many ir.model | Computed: all models user has access to |
| `model_name` | Char | Related to `model_id.model`, stored |
| `code` | Text | Python code block. Groups: `base.group_system`. Default: template with variable documentation |
| `child_ids` | Many2many ir.actions.server | Child actions for `multi` state |
| `groups_id` | Many2many res.groups | Groups allowed to execute. Empty = allow everybody |
| `crud_model_id` | Many2one ir.model | Computed: target model for create/write |
| `crud_model_name` | Char | Related to `crud_model_id.model` |
| `link_field_id` | Many2one ir.model.fields | Field to link created record to active record |
| `update_field_id` | Many2one ir.model.fields | Field to update on target model (for `object_write`) |
| `update_path` | Char | Dot-path to nested field to update, e.g., `partner_id.name` |
| `update_related_model_id` | Many2one ir.model | Computed: model of the related field at end of path |
| `update_field_type` | Selection | Related to `update_field_id.ttype` |
| `update_m2m_operation` | Selection | For many2many: `add`, `remove`, `set`, `clear` |
| `update_boolean_value` | Selection | For boolean: `true` or `false` |
| `value` | Text | New value (or Python expression) |
| `evaluation_type` | Selection | `value` (static) or `equation` (Python eval) |
| `resource_ref` | Reference | Record picker for relational field values |
| `selection_value` | Many2one ir.model.fields.selection | Selection option picker |
| `value_field_to_show` | Selection | Computed: which widget to show based on field type |
| `webhook_url` | Char | POST URL for `webhook` state |
| `webhook_field_ids` | Many2many ir.model.fields | Fields to include in webhook payload |
| `webhook_sample_payload` | Text | Computed sample JSON payload |

### Five State Types (lines 490-506)

| State | Label | Method | Description |
|-------|-------|--------|-------------|
| `object_write` | Update Record | `_run_action_object_write` | Write values to a record |
| `object_create` | Create Record | `_run_action_object_create` | Create new record |
| `code` | Execute Code | `_run_action_code_multi` | Run arbitrary Python |
| `webhook` | Send Webhook Notification | `_run_action_webhook` | HTTP POST to external URL |
| `multi` | Execute Existing Actions | `_run_action_multi` | Run child actions in sequence |

Note: The XML help text mentions other types (Create Activity, Send Email, etc.) — these are legacy/stub references. The actual implementations for email/activity live in `mail` and other modules via `run_action_*` method overrides.

### `_compute_crud_relations()` — Line 605-637

Computes `crud_model_id` and `update_field_id` based on `state` and `update_path`:

- `object_create`: `crud_model_id = model_id`, no update_field
- `object_write` with path: traverses `update_path` via `_traverse_path()` to find target model + field
- `object_write` without path: `crud_model_id = model_id`, no update_field

`_traverse_path()` (Line 639-670): Splits path by `.`, walks relation fields, ensures last field is non-relational (or Properties). Returns `(model_id, field_id, records)` where records is reduce(getitem, path[:-1], record).

### `_run_action_object_write()` — Line 784-796

```python
def _run_action_object_write(self, eval_context=None):
    vals = self._eval_value(eval_context=eval_context)
    res = {action.update_field_id.name: vals[action.id] for action in self}
    starting_record = self.env[self.model_id.model].browse(self._context.get('active_id'))
    _, _, target_records = self._traverse_path(record=starting_record)
    target_records.write(res)
```

For onchange mode (`onchange_self` in context), writes directly to the cached record instead of browsing. Supports dot-path traversal.

### `_run_action_object_create()` — Line 834-846

```python
def _run_action_object_create(self, eval_context=None):
    res_id, _res_name = self.env[self.crud_model_id.model].name_create(self.value)
    if self.link_field_id:
        record = self.env[self.model_id.model].browse(self._context.get('active_id'))
        if self.link_field_id.ttype in ['one2many', 'many2many']:
            record.write({self.link_field_id.name: [Command.link(res_id)]})
        else:
            record.write({self.link_field_id.name: res_id})
```

Creates record via `name_create()` (returns both ID and name). If `link_field_id` is set, links the new record to the active record via the appropriate field type.

### `_run_action_code_multi()` — Line 774-776

```python
def _run_action_code_multi(self, eval_context):
    safe_eval(self.code.strip(), eval_context, mode="exec", nocopy=True, filename=str(self))
    return eval_context.get('action')  # Return value becomes the action result
```

`nocopy=True` allows `action = {...}` in the code to return a result. `filename=str(self)` sets the code's identifier in error tracebacks.

### `_run_action_webhook()` — Line 798-832

```python
def _run_action_webhook(self, eval_context=None):
    record = self.env[self.model_id.model].browse(self._context.get('active_id'))
    url = self.webhook_url
    vals = {
        '_model': self.model_id.model,
        '_id': record.id,
        '_action': f'{self.name}(#{self.id})',
    }
    if self.webhook_field_ids:
        vals.update(record.read(self.webhook_field_ids.mapped('name'))[0])
    json_values = json.dumps(vals, sort_keys=True, default=str)
    response = requests.post(url, data=json_values,
        headers={'Content-Type': 'application/json'}, timeout=1)
    response.raise_for_status()
```

Always sends `_model`, `_id`, `_action`. If `webhook_field_ids` is set, reads those fields from the active record. Uses `default=str` for non-serializable fields (dates, binary, etc.). 1-second timeout with fire-and-forget strategy — timeouts are logged but not raised.

### `run()` — Execution Engine — Line 888-964

```python
def run(self):
    res = False
    for action in self.sudo():  # Always sudo for access checks
        # Check group access
        if action.groups_id and not (action.groups_id & self.env.user.groups_id):
            raise AccessError(...)
        # Check model access rights
        self.env[model_name].check_access_rights("write")
        # Load record context
        eval_context = self._get_eval_context(action)
        records = eval_context.get('record') or eval_context['model']
        records |= eval_context.get('records') or eval_context['model']
        if records.ids:
            records.check_access_rule('write')  # Check ir.rule
        runner, multi = action._get_runner()  # Find _run_action_{state}[_multi]
        if runner and multi:
            res = runner(run_self, eval_context=eval_context)
        elif runner:
            for active_id in active_ids:
                run_self = action.with_context(active_ids=[active_id], active_id=active_id)
                eval_context["env"].context = run_self._context
                eval_context['records'] = eval_context['record'] = records.browse(active_id)
                res = runner(run_self, eval_context=eval_context)
    return res or False
```

Runner lookup via `_get_runner()`: tries `_run_action_{state}_multi` first (multi-record), then `run_action_{state}_multi`, then `_run_action_{state}`, then `run_action_{state}`. Methods prefixed `run_action_` are wrapped with `partial(fn, self)`. Deprecated symbols starting with `run_action_` are logged as warnings in `_register_hook()`.

### `_get_eval_context()` — Line 848-886

Full evaluation context for Python code actions:

```python
{
    'uid': self._uid,
    'user': self.env.user,
    'time': tools.safe_eval.time,
    'datetime': tools.safe_eval.datetime,
    'dateutil': tools.safe_eval.dateutil,
    'timezone': timezone,
    'float_compare': float_compare,
    'b64encode': base64.b64encode,
    'b64decode': base64.b64decode,
    'Command': Command,
    # Added for server actions specifically:
    'env': self.env,
    'model': model,
    'UserError': odoo.exceptions.UserError,
    'record': record,    # single active_id or None
    'records': records,  # all active_ids or empty recordset
    'log': log,         # writes to ir_logging table
    '_logger': LoggerProxy,
}
```

The `log` function writes to `ir_logging` table in a separate cursor (to avoid committing partial work):

```python
def log(message, level="info"):
    with self.pool.cursor() as cr:
        cr.execute("""
            INSERT INTO ir_logging(create_date, create_uid, type, dbname, name,
                level, message, path, line, func)
            VALUES (NOW() at time zone 'UTC', %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (self.env.uid, 'server', self._cr.dbname, __name__, level,
              message, "action", action.id, action.name))
```

### `_eval_value()` — Line 998-1025

Evaluates the `value` field based on `evaluation_type` and `update_field_id.ttype`:

| ttype | evaluation_type=value | evaluation_type=equation |
|-------|----------------------|--------------------------|
| one2many/many2many | `Command.link(int)` / `Command.unlink(int)` / `Command.set([int])` / `Command.clear()` | safe_eval result |
| boolean | `update_boolean_value == 'true'` | safe_eval result |
| many2one/integer | `int(value)` | safe_eval result |
| float | `float(value)` (with contextlib.suppress) | safe_eval result |
| default | `value` (raw string) | safe_eval result |

---

## ir.actions.client — Client Actions

File: `ir_actions.py`, lines 1112-1149

Client actions delegate entirely to the web client's JavaScript. The `tag` string tells the client which widget to instantiate.

### All Fields

| Field | Type | Description |
|-------|------|-------------|
| `type` | Char | Default `"ir.actions.client"` |
| `tag` | Char | Required. JS widget identifier string. Examples: `'reload'`, `'reload_context'`, `'download'`, `'print'`, `'bus.refresh'` |
| `target` | Selection | `current` (default), `new` (modal), `fullscreen`, `main` |
| `res_model` | Char | Optional target model (used for needactions) |
| `context` | Char | Context dict as Python expression, default `"{}"` |
| `params` | Binary | Dict of arguments passed to the JS widget. Computed from `params_store` via repr/eval |
| `params_store` | Binary | Storage for params (attachment=False, not in DB) |

### Tag → Widget Examples

| Tag | Widget | Purpose |
|-----|--------|---------|
| `reload` | reload | Reload the current controller |
| `reload_context` | reload | Reload with updated context |
| `download` | download | Trigger file download |
| `print` | print | Trigger print dialog |
| `bus.refresh` | bus refresh | Force bus notification refresh |

The `target` controls whether the action replaces the current window or opens a new one. `res_model` allows the action to work with records of a specific model (e.g., for notification counts).

---

## ir.actions.todo — Configuration Wizards

File: `ir_actions.py`, lines 1033-1109

Shows setup/configuration tasks in the Settings dashboard. Forces only one open todo at a time.

### All Fields

| Field | Type | Description |
|-------|------|-------------|
| `action_id` | Many2one ir.actions.actions | Required. Action to launch |
| `sequence` | Integer | Default 10. Execution priority |
| `state` | Selection | `open` (default) or `done` |
| `name` | Char | Optional display name |

### Only One Open Todo Enforcement (Line 1062-1066)

```python
@api.model
def ensure_one_open_todo(self):
    open_todo = self.search([('state', '=', 'open')],
                            order='sequence asc, id desc', offset=1)
    if open_todo:
        open_todo.write({'state': 'done'})  # Auto-close older open todos
```

When a todo is set to `open`, all other open todos are automatically set to `done` (except the first one found by sequence). Applied in both `create()` and `write()`.

### `action_launch()` — Line 1080-1105

Sets todo to `done`, then reads and returns the action. For act_window actions, evaluates `context` and extracts `res_id` from it. Disables logging for automatic wizards via `disable_log=True` in context.

---

## ir.rule — Record-Level Security

File: `ir_rule.py` (265 lines)

### All Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Index, no unique constraint |
| `active` | Boolean | Default True. Disabling skips rule without deleting. |
| `model_id` | Many2one ir.model | Required, indexed. Ondelete cascade. |
| `groups` | Many2many res.groups | Groups this rule applies to. Empty = global. Ondelete restrict. |
| `domain_force` | Text | Domain expression as Python code (safe_eval) |
| `perm_read` | Boolean | Default True. Read access enabled. |
| `perm_write` | Boolean | Default True. Write access enabled. |
| `perm_create` | Boolean | Default True. Create access enabled. |
| `perm_unlink` | Boolean | Default True. Delete access enabled. |

**SQL Constraint:** At least one permission must be True.

### Global Rule: `_compute_global()`

```python
def _compute_global(self):
    for rule in self:
        rule['global'] = not rule.groups  # Keyword workaround via setattr
```

Rules without groups are "global" — applied to all users. The `global` field is assigned via `setattr(IrRule, 'global', global_)` at module load because `global` is a Python keyword.

### Domain Combination Formula

From `_compute_domain()` (Line 139-167):

```
Final domain = AND(global_rules) if no group_rules
Final domain = AND(global_rules) + [OR(group_rules_matching_user)]
```

In SQL terms:
```sql
WHERE (global_rule_1) AND (global_rule_2)
  AND (group_rule_1 OR group_rule_2 OR ...)  -- only rules matching user's groups
```

For inheritance: parent model domains are wrapped as `[(parent_field, 'any', parent_domain)]` and AND-ed with the child's rules. This propagates access control up the inheritance chain.

### Evaluation Context: `_eval_context()` (Line 35-50)

```python
def _eval_context(self):
    return {
        'user': self.env.user.with_context({}),
        'time': time,
        'company_ids': self.env.companies.ids,  # All activated companies
        'company_id': self.env.company.id,       # Current company
    }
```

`user` is created with empty context to make evaluation deterministic regardless of call context. `company_ids` contains all companies the user has access to via the switch company menu.

### `_compute_domain()` — ORMcached (Line 133-167)

```python
@api.model
@tools.conditional(
    'xml' not in config['dev_mode'],  # Skip cache in dev mode with --dev xml
    tools.ormcache('self.env.uid', 'self.env.su', 'model_name', 'mode',
                   'tuple(self._compute_domain_context_values())'),
)
def _compute_domain(self, model_name, mode="read"):
```

Cache key: `(uid, is_sudo, model_name, mode, context_values)`. Cache is invalidated by `create()`, `write()`, `unlink()` via `self.env.registry.clear_cache()`. In dev mode (`--dev xml`), the cache is skipped so that XML-defined domain changes take effect without restarting.

### `_get_rules()` — Raw SQL Query (Line 112-131)

```python
query = """ SELECT r.id FROM ir_rule r JOIN ir_model m ON (r.model_id=m.id)
            WHERE m.model=%s AND r.active AND r.perm_{mode}
            AND (r.id IN (SELECT rule_group_id FROM rule_group_rel rg
                          JOIN res_groups_users_rel gu ON (rg.group_id=gu.gid)
                          WHERE gu.uid=%s)
                 OR r.global)
            ORDER BY r.id
        """
self._cr.execute(query, (model_name, self._uid))
return self.browse(row[0] for row in self._cr.fetchall())
```

Uses raw SQL for performance (avoids ORM overhead). Returns rules matching model + mode + user's groups. Sorted by ID.

### `_make_access_error()` — Enhanced Error Messages (Line 202-253)

When `base.group_no_one` is active (debug mode), includes:
- List of failing records (up to 6)
- List of rule names that caused the denial
- Special handling for company-related rules: suggests switching company

Without debug mode: shows generic "Access Denied" with a cookie joke.

```python
if not self.user_has_groups('base.group_no_one') or not self.env.user.has_group('base.group_user'):
    records.invalidate_recordset()
    return AccessError(f"{operation_error}\n{failing_model}\n\n{resolution_info}")

# Extended error in debug mode...
failing_rules = _("Blame the following rules:\n%s", rules_description)
if company_related:
    failing_rules += "\n\n" + _('Note: this might be a multi-company issue.')
```

### Domain Normalization

```python
dom = safe_eval(rule.domain_force, eval_context) if rule.domain_force else []
dom = expression.normalize_domain(dom)
```

`expression.normalize_domain()` converts any domain to a normalized AND-tree. Essential for combining multiple rules.

---

## Key Discoveries

1. **`global` is not a real field**: `ir_rule.py` defines `global_ = fields.Boolean(...)` and assigns it via `setattr(IrRule, 'global', global_)`. Python's `global` keyword is reserved, so this workaround is necessary. The ORM handles it transparently in searches and reads.

2. **Server action runner uses partial binding**: `_get_runner()` returns `(fn, multi)` where `fn` may be wrapped in `partial(fn, self)` if the method name starts with `run_action_`. This allows both `_run_action_code_multi(self, eval_context)` and `run_action_code_multi(action, eval_context)` calling conventions.

3. **`multi` server action returns last child result**: `_run_action_multi` iterates `self.child_ids.sorted()` and updates `res = act.run() or res`. The last non-False return value becomes the overall result.

4. **Webhook field group restriction**: `_check_webhook_field_ids()` prevents group-restricted fields from being included in webhook payloads. This prevents accidental data leakage — a user with access to the model but not the field could otherwise configure the webhook to extract sensitive data.

5. **Webhook uses `default=str` for JSON serialization**: Standard `json.dumps` would fail on datetime, date, binary fields. Using `default=str` handles all edge cases. However, special types like `markupsafe.Markup` or recordset values still need careful handling.

6. **Ormcache conditional in dev mode**: `_compute_domain()` skips the ormcache when `'xml' in config['dev_mode']`. This means XML-defined rule domains are re-evaluated every time in dev mode — useful during development but slower in production.

7. **`_get_failing()` for access error diagnostics**: Only used in debug mode. Runs actual search queries to identify which rules would exclude each record. This is why the extended error message only appears when `base.group_no_one` is active — it's a deliberate security measure to avoid information disclosure.

8. **Company multi-security via `company_ids` in domain context**: The `_eval_context()` exposes both `company_id` (current) and `company_ids` (all activated). Rules typically use these to restrict access by company. `company_ids` in the context is the list selected in the switch company menu, not all companies the user has access to.

9. **ir.actions.act_window view resolution is deterministic**: `view_ids` (explicit order) takes precedence. Then `view_id` type is inserted before other missing modes (so `view_id` form opens first). Remaining modes from `view_mode` string are appended as `(False, mode)` — default view for that mode.

10. **Action `type` field is the discriminator**: Every action record stores its type as a Char field (e.g., `"ir.actions.act_window"`). The framework reads this and instantiates the correct model class. This is why `type` must be set as a default in every subclass — it's the runtime polymorphic key.

## See Also

- [Patterns/Security Patterns](Patterns/Security-Patterns.md) — Record rules and ACLs
- [Core/BaseModel](Core/BaseModel.md) — ORM foundation
- [Core/API](Core/API.md) — @api.depends, @api.onchange
- [Modules/base](Modules/base.md) — res.users, res.groups
- [Tools/ORM Operations](Tools/ORM-Operations.md) — search/browse/create/write patterns