---
uid: data_recycle
title: Data Recycle
type: module
category: Productivity/Data Cleaning
version: "1.4"
created: 2026-04-06
updated: 2026-04-11
dependencies:
  - mail
author: Odoo S.A.
license: LGPL-3
summary: Find old records and archive or delete them automatically
application: true
tags: [odoo, odoo19, data-cleaning, archive, delete, cron, lifecycle]
---

# Data Recycle (`data_recycle`)

## Overview

| Property | Value |
|----------|-------|
| **Module** | `data_recycle` |
| **Category** | Productivity/Data Cleaning |
| **License** | LGPL-3 |
| **Edition** | Community (CE) |
| **Depends** | `mail` |
| **Application** | Yes |
| **Author** | Odoo S.A. |

`data_recycle` manages automatic **data lifecycle management** -- archiving or deleting stale records based on configurable rules. It surfaces pending deletions to admins before execution in manual mode, or runs fully automatically. Two core models: `data_recycle.model` (the rule definition) and `data_recycle.record` (the staged record pending action).

Key use cases:
- GDPR compliance: automatic purging of old/stale personal data
- Database hygiene: removing abandoned carts, archived leads, old log entries
- Storage management: deleting records whose date field indicates they are past retention policy

---

## File Structure

```
data_recycle/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── data_recycle_model.py    # data_recycle.model -- the rule
│   └── data_recycle_record.py   # data_recycle.record -- staged record
├── data/
│   └── ir_cron_data.xml         # ir.cron: runs daily at 03:00
├── views/
│   ├── data_recycle_model_views.xml
│   ├── data_recycle_record_views.xml
│   ├── data_cleaning_menu.xml
│   └── data_recycle_templates.xml  # QWeb notification template
├── security/
│   └── ir.model.access.csv      # base.group_system only
├── static/src/views/
│   ├── data_cleaning_common_list.js   # Base list controller
│   └── data_recycle_list_view.js      # data_recycle-specific controller
└── tests/
    └── test_data_recycle.py
```

---

## L1 -- Model Fields and Method Signatures

### `data_recycle.model` -- The Recycling Rule

`_name = 'data_recycle.model'` | `_description = 'Recycling Model'` | `_order = 'name'`

#### Identity
| Field | Type | Notes |
|-------|------|-------|
| `active` | Boolean, default `True` | Toggling off cascades-deletes all staged `data_recycle.record` entries via ORM-level `write()` hook |
| `name` | Char, `store=True`, `copy=True`, `required=True`, `readonly=False` | Auto-computed from `res_model_id.name` when left empty (`_compute_name`); `readonly=False` allows users to override the auto-generated name |

#### Model Target
| Field | Type | Notes |
|-------|------|-------|
| `res_model_id` | Many2one (`ir.model`), `required=True`, `ondelete='cascade'` | Target model to recycle |
| `res_model_name` | Char, `related='res_model_id.model'`, `store=True` | Technical model name, e.g. `fetchmail.server` |
| `recycle_record_ids` | One2many (`data_recycle.record`, `recycle_model_id`) | All staged records for this rule |

#### Rule Mode and Action
| Field | Type | Notes |
|-------|------|-------|
| `recycle_mode` | Selection, default `'manual'` | `'manual'` = stage for review; `'automatic'` = execute immediately |
| `recycle_action` | Selection, default `'unlink'` | `'archive'` = set `active=False`; `'unlink'` = delete from DB |
| `include_archived` | Boolean | When `True`, also scans records where `active=False` for recycling; hidden in UI when `recycle_action = 'archive'` |

#### Rule Definition
| Field | Type | Notes |
|-------|------|-------|
| `domain` | Char, `store=True` | Filter domain; rendered via `widget="domain"` in the UI; computed as `'[]'` on model change via `_compute_domain` |
| `time_field_id` | Many2one (`ir.model.fields`), `ondelete='cascade'` | Date/datetime field used to measure record age |
| | | **Domain filter:** `model_id=res_model_id`, `ttype in ('date', 'datetime')`, **`store=True`** |
| `time_field_delta` | Integer, default `1` | Age threshold value |
| `time_field_delta_unit` | Selection, default `'months'` | `days`, `weeks`, `months`, `years` -- maps to `relativedelta` kwargs |

#### Notifications (manual mode only)
| Field | Type | Notes |
|-------|------|-------|
| `notify_user_ids` | Many2many (`res.users`) | Users to notify; domain restricted to `base.group_system`; defaults to current user |
| `notify_frequency` | Integer, default `1`, `CHECK > 0` | Notification interval |
| `notify_frequency_period` | Selection, default `'weeks'` | `days`, `weeks`, `months` -- **not `years`** (only these three are valid for notifications) |
| `last_notification` | Datetime, `readonly=True` | Timestamp of last notification sent |

#### Counters
| Field | Type | Notes |
|-------|------|-------|
| `records_to_recycle_count` | Integer | Count of active staged records, computed via `_read_group` |

#### SQL Constraint
```python
_check_notif_freq = models.Constraint(
    'CHECK(notify_frequency > 0)',
    'The notification frequency should be greater than 0',
)
```

#### API Constraints
```python
@api.constrains('recycle_action')
def _check_recycle_action(self):
    for model in self:
        if model.recycle_action == 'archive' and 'active' not in self.env[model.res_model_name]:
            raise UserError(_("This model doesn't manage archived records. Only deletion is possible."))
```

#### Module-Level Constants
```python
DR_CREATE_STEP_AUTO = 5000    # automatic mode: validate + commit per batch
DR_CREATE_STEP_MANUAL = 50000  # manual mode: stage only, bulk commit
```

---

### `data_recycle.record` -- The Staged Record

`_name = 'data_recycle.record'` | `_description = 'Recycling Record'`

| Field | Type | Notes |
|-------|------|-------|
| `active` | Boolean, default `True` | `True` = pending; `False` = discarded (via `action_discard`) |
| `name` | Char, `compute='_compute_name'`, `compute_sudo=True` | Display name of original record; shows `**Record Deleted**` if original was removed |
| `recycle_model_id` | Many2one (`data_recycle.model`), `index='btree_not_null'`, `ondelete='cascade'` | Parent rule; `btree_not_null` (Odoo 19) creates a partial index that is more efficient than a full btree index on a nullable FK |
| `res_id` | Integer, `index=True` | Original record database ID |
| `res_model_id` | Many2one, `related='recycle_model_id.res_model_id'`, `store=True` | Original model |
| `res_model_name` | Char, `related='recycle_model_id.res_model_name'`, `store=True` | Original model technical name |
| `company_id` | Many2one (`res.company`), `compute='_compute_company_id'`, `store=True` | Extracted from original record if it has a `company_id` field; purely for display/filtering -- does not affect recycling behavior |

#### Method: `action_validate()`
```python
def action_validate(self) -> records_done
```
Dispatches original records to either `action_archive()` (for `archive` action) or `unlink()` (for `delete` action), grouped by model name, then deletes the staged recycle records. Runs via `sudo()` on the target model. In automatic mode, called per batch inside `_recycle_records`.

#### Method: `action_discard()`
```python
def action_discard(self) -> bool
```
Sets `active=False` on the recycle record. Does NOT delete the original record. The original record remains in the system; the recycle record is excluded from future counts and re-staging via `active_test=False`.

---

## L2 -- Field Types, Defaults, and Rule Evaluation Logic

### Rule Domain Evaluation -- How Age Is Computed

The rule domain is built in two stages inside `_recycle_records()`:

```python
# Stage 1: static domain from the Char field
rule_domain = Domain(ast.literal_eval(recycle_model.domain)) \
    if recycle_model.domain and recycle_model.domain != '[]' \
    else Domain.TRUE

# Stage 2: time-based threshold appended as AND
if recycle_model.time_field_id and recycle_model.time_field_delta and recycle_model.time_field_delta_unit:
    if recycle_model.time_field_id.ttype == 'date':
        now = fields.Date.today()          # date only, no time component
    else:
        now = fields.Datetime.now()        # datetime with timezone
    delta = relativedelta(**{recycle_model.time_field_delta_unit: recycle_model.time_field_delta})
    rule_domain &= Domain(recycle_model.time_field_id.name, '<=', now - delta)
```

**Why two `now` variants?** Date fields (`date`) compare against `fields.Date.today()` which has no time component. Datetime fields compare against `fields.Datetime.now()` which includes time. This matters for edge cases: a record created on January 1st at 08:00 with a delta of 0 days will appear old by noon on January 1st when using datetime comparison, but will only appear old after midnight when using date comparison.

**Domain class:** Uses `odoo.fields.Domain` (Odoo 17+), not string concatenation. This is more efficient and avoids injection risks compared to older `expression.domain` manipulation. The `Domain` class from `odoo.fields` is a domain AST object that can be AND-ed directly.

**On model change:** `_compute_domain` always resets `domain` to `'[]'`. This prevents stale domain references when switching to a different target model, since domains are model-specific.

### `include_archived` -- UI Visibility and Search Behavior

```python
# The UI hides include_archived when recycle_action = 'archive'
<field name="include_archived" invisible="recycle_action != 'unlink'"/>
```

The field is only relevant for `recycle_action = 'unlink'`. When `include_archived=True`, the search includes both `active=True` and `active=False` records via `with_context(active_test=False)`. For `archive` action, including archived records is redundant since they would be deleted anyway.

### `_check_recycle_action` Constraint

```python
@api.constrains('recycle_action')
def _check_recycle_action(self):
    for model in self:
        if model.recycle_action == 'archive' and 'active' not in self.env[model.res_model_name]:
            raise UserError(_("This model doesn't manage archived records. Only deletion is possible."))
```

Archive action requires the target model to have an `active` field (standard Odoo active-inactive pattern). Models that do not implement `active` can only be recycled via `unlink`. This is a runtime check that fires on write, not a DB-level constraint.

### Cron Job Definition (`data/ir_cron_data.xml`)

```xml
<record id="ir_cron_clean_records" model="ir.cron">
    <field name="name">Data Recycle: Clean Records</field>
    <field name="model_id" ref="model_data_recycle_model"/>
    <field name="state">code</field>
    <field name="code">model._cron_recycle_records()</field>
    <field name="active" eval="True"/>
    <field name="interval_number">1</field>
    <field name="interval_type">days</field>
    <field name="nextcall" eval="(DateTime.now().replace(hour=3, minute=0) + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')" />
</record>
```

**Cron mechanism:** `state='code'` is an Odoo-specific cron type that executes arbitrary Python code from the `code` field. The code `model._cron_recycle_records()` calls the method on the recordset returned by `search([])` -- that is, **all** `data_recycle.model` records, regardless of their `active` field value.

The cron runs **daily at 03:00 AM server time**, targeting all rules. After recycling, it calls `_notify_records_to_recycle()` separately. Both happen within the same cron job execution.

### View Architecture and JS Controllers

The recycle record list view uses a custom JS controller (`js_class="data_recycle_list"`):

**`data_cleaning_common_list.js` -- Base controller:**
```javascript
openRecord(record) {
    // Override: open the ORIGINAL record form, not the recycle record
    this.actionService.doAction({
        type: 'ir.actions.act_window',
        views: `False, 'form'`,
        res_model: record.data.res_model_name,  // Navigate to original model
        res_id: record.data.res_id,              // Navigate to original ID
        context: { create: false, edit: false }
    });
}
```

This is critical: clicking any recycle record row opens the **original record's form view** (e.g., `fetchmail.server` form), not the `data_recycle.record` form. The list view is intentionally read-only (`create="0" export_xlsx="0"`).

**`data_recycle_list_view.js` -- Bulk validate:**
```javascript
async onValidateClick() {
    const record_ids = await this.model.root.getResIds(true);
    await this.orm.call('data_recycle.record', 'action_validate', [record_ids]);
    await this.model.load();  // Refresh list
}
```

The "Validate" button in the list view header calls `action_validate` via `orm.call()` on **all selected records** in a single RPC, enabling bulk processing from the list view.

---

## L3 -- Cross-Model Relationships, Override Patterns, and Workflow Triggers

### Cross-Model Dispatch in `action_validate()`

```python
def action_validate(self):
    record_ids_to_archive = defaultdict(list)
    record_ids_to_unlink = defaultdict(list)
    original_records = {'%s_%s' % (r._name, r.id): r for r in self._original_records()}
    for record in self:
        original_record = original_records.get('%s_%s' % (record.res_model_name, record.res_id))
        records_done |= record
        if not original_record:
            continue
        if record.recycle_model_id.recycle_action == "archive":
            record_ids_to_archive[original_record._name].append(original_record.id)
        elif record.recycle_model_id.recycle_action == "unlink":
            record_ids_to_unlink[original_record._name].append(original_record.id)
    for model_name, ids in record_ids_to_archive.items():
        self.env[model_name].sudo().browse(ids).action_archive()
    for model_name, ids in record_ids_to_unlink.items():
        self.env[model_name].sudo().browse(ids).unlink()
    records_done.unlink()
```

**Critical behavior:** For archive, it calls the **target model's own `action_archive()` method**, not `write({'active': False})` directly. This means if the target model has overrides (e.g., cascading unlink of child records, logging, workflow triggers), those are triggered. For models without `action_archive()`, this falls back to the base implementation in `base.model`.

Note that `records_done |= record` (line 5) accumulates every recycle record processed into `records_done`, including those whose original record was already deleted. All of these are then deleted via `records_done.unlink()` at the end. Only records whose `original_record` is missing are skipped for actual archiving/unlinking.

### `_original_records()` -- Batch Resolution Pattern

```python
def _original_records(self):
    if not self:
        return []
    records_per_model = {}
    for record in self.filtered(lambda r: r.res_model_name):
        ids = records_per_model.get(record.res_model_name, [])
        ids.append(record.res_id)
        records_per_model[record.res_model_name] = ids
    for model, record_ids in records_per_model.items():
        recs = self.env[model].with_context(active_test=False).sudo().browse(record_ids).exists()
        records += [r for r in recs]
    return records
```

Key behaviors:
- **Batches by model:** All `res_id` values per `res_model_name` are resolved in a single `browse().exists()` call per model -- avoids N+1 ORM queries
- **`sudo()`:** Bypasses ACL to resolve existence even if the current user lacks read access to the target model
- **`with_context(active_test=False)`:** Includes records where `active=False` -- needed because `include_archived=True` rules stage archived records, and these must be re-resolved on validation
- **`exists()`:** Filters out `res_id` values that were already deleted from the target model -- produces a clean, live recordset

Both `_compute_name` and `_compute_company_id` call `_original_records()` independently. On forms displaying many recycle records, this results in two batch queries (one per computed field). This is acceptable for typical use (hundreds of staged records), but could be a bottleneck for rules with thousands of staged records.

### Notification System -- Complete Flow

```python
def _notify_records_to_recycle(self):
    for recycle in self.search([('recycle_mode', '=', 'manual')]):
        if not recycle.notify_user_ids or not recycle.notify_frequency:
            continue
        delta = relativedelta(**{recycle.notify_frequency_period: recycle.notify_frequency})
        if not recycle.last_notification or (recycle.last_notification + delta) < fields.Datetime.now():
            recycle.last_notification = fields.Datetime.now()
            recycle._send_notification(delta)

def _send_notification(self, delta):
    self.ensure_one()
    last_date = fields.Date.today() - delta
    records_count = self.env['data_recycle.record'].search_count([
        ('recycle_model_id', '=', self.id),
        ('create_date', '>=', last_date)
    ])
    partner_ids = self.notify_user_ids.partner_id.ids if records_count else []
    if partner_ids:
        menu_id = self.env.ref('data_recycle.menu_data_cleaning_root').id
        self.env['mail.thread'].message_notify(
            body=self.env['ir.qweb']._render('data_recycle.notification', {...}),
            model=self._name, partner_ids=partner_ids,
            res_id=self.id, subject=_('Data to Recycle'),
        )
```

**Notification frequency mapping:** Only `days`, `weeks`, `months` are valid `relativedelta` kwargs -- `years` is available for the rule's `time_field_delta_unit` but NOT for `notify_frequency_period`.

**Counting window:** `records_count` counts recycle records created **since `last_date`** (`fields.Date.today() - delta`), meaning new records added since the last notification. This ensures the notification reports only newly-identified records.

**Idempotency:** `last_notification` is set **before** `_send_notification()` runs. If the notification fails (e.g., email service down), it will not be retried until the next interval elapses.

```xml
<template id="notification">
We've identified <t t-esc="records_count" /> records to clean with the '<t t-esc="res_model_label" />' recycling rule.<br/>
You can validate those changes <a t-attf-href="/odoo/{{recycle_model_id}}/action-data_recycle.action_data_recycle_record_notification?menu_id={{menu_id}}">here</a>.
</template>
```

The notification link routes through a web controller URL (`/odoo/<rule_id>/action-...`) which dispatches to the `action_data_recycle_record_notification` action. This action has `context='{searchpanel_default_recycle_model_id: active_id}'` pre-filtering the recycle records list to only the rule that triggered the notification.

### `action_recycle_records()` -- Manual Trigger

```python
def action_recycle_records(self):
    self.sudo()._recycle_records()          # batch_commits=False by default
    if self.recycle_mode == 'manual':
        return self.open_records()
    return

def open_records(self):
    self.ensure_one()
    action = self.env["ir.actions.actions"]._for_xml_id("data_recycle.action_data_recycle_record")
    action['context'] = dict(ast.literal_eval(action.get('context', '{}')),
                             searchpanel_default_recycle_model_id=self.id)
    return action
```

**`open_records()` detail:** The `searchpanel_default_recycle_model_id` context key pre-filters the recycle records list to show only records belonging to this rule. The action's own context (`{}`) is merged with this via `ast.literal_eval`, so if the action had any pre-existing context values they are preserved.

When an admin clicks "Run Now" from the form header, `_recycle_records()` is called with `batch_commits=False` (the default). In automatic mode, this means the full batch runs in a single transaction -- with large record sets this can cause transaction timeouts. The cron path uses `batch_commits=True` specifically to avoid this.

### Deactivation Cascade (ORM-level, not DB-level)

```python
def write(self, vals):
    if 'active' in vals and not vals['active']:
        self.env['data_recycle.record'].search([('recycle_model_id', 'in', self.ids)]).unlink()
    return super().write(vals)
```

When a rule is deactivated (set `active=False`), all its staged recycle records are immediately deleted via `unlink()`. This is an ORM-level cascade in `write()`, **not** a DB-level `ON DELETE CASCADE` constraint on the FK. The distinction matters: the `ondelete='cascade'` on `recycle_model_id` only fires if the `data_recycle.model` record itself is deleted from the database, not when `active` is set to False.

---

## L4 -- Performance, Odoo 18-to-19 Changes, Security, and Expert Mode

### Performance: Complete `_recycle_records()` Execution Flow

The full method reveals two distinct execution paths that are important to understand:

```python
def _recycle_records(self, batch_commits=False):
    self.env.flush_all()     # (1) Sync all pending ORM writes before scanning
    records_to_clean = []   # (2) Accumulator for manual mode across ALL rules
    is_test = modules.module.current_test

    # (3) Pre-fetch existing recycle records to avoid re-staging
    existing_recycle_records = self.env['data_recycle.record'].with_context(
        active_test=False).search([('recycle_model_id', 'in', self.ids)])
    mapped_existing_records = defaultdict(list)
    for recycle_record in existing_recycle_records:
        mapped_existing_records[recycle_record.recycle_model_id].append(recycle_record.res_id)

    for recycle_model in self:   # (4) Iterate ALL rules (active or not)
        rule_domain = Domain(ast.literal_eval(recycle_model.domain)) if recycle_model.domain and recycle_model.domain != '[]' else Domain.TRUE

        # (5) Append time-based filter
        if recycle_model.time_field_id and recycle_model.time_field_delta and recycle_model.time_field_delta_unit:
            now = fields.Date.today() if recycle_model.time_field_id.ttype == 'date' else fields.Datetime.now()
            delta = relativedelta(**{recycle_model.time_field_delta_unit: recycle_model.time_field_delta})
            rule_domain &= Domain(recycle_model.time_field_id.name, '<=', now - delta)

        model = self.env[recycle_model.res_model_name]
        if recycle_model.include_archived:
            model = model.with_context(active_test=False)
        records_to_recycle = model.search(rule_domain)

        # (6) Deduplication: skip already-staged res_ids
        records_to_create = [{
            'res_id': record.id,
            'recycle_model_id': recycle_model.id,
        } for record in records_to_recycle if record.id not in mapped_existing_records[recycle_model]]

        if recycle_model.recycle_mode == 'automatic':
            # (7a) Automatic: validate each batch, commit per batch
            for batch in split_every(DR_CREATE_STEP_AUTO, records_to_create):
                self.env['data_recycle.record'].create(batch).action_validate()
                if batch_commits and not is_test:
                    self.env.cr.commit()
        else:
            # (7b) Manual: accumulate, create in bulk at end
            records_to_clean = records_to_clean + records_to_create

    # (8) Manual mode: create all accumulated records at once
    for batch in split_every(DR_CREATE_STEP_MANUAL, records_to_clean):
        self.env['data_recycle.record'].create(batch)
        if batch_commits and not is_test:
            self.env.cr.commit()
```

**Step-by-step breakdown:**

1. **`flush_all()`:** Critical for correctness. All pending writes in the current transaction (e.g., records created earlier in the same cron run, or in a preceding wizard action) are flushed to the DB before the search runs. Without this, pending-but-unflushed records could satisfy the domain and be incorrectly staged.

2. **`records_to_clean` accumulator:** In manual mode, this list accumulates across all rules before any DB insert happens. This means if the cron processes 10 rules, each with 1,000 candidates, the 10,000 dicts are held in memory and then batch-inserted. This is safe for moderate sizes but worth monitoring.

3. **Rule iteration covers ALL rules:** `for recycle_model in self` iterates all `data_recycle.model` records passed to the method. The cron calls `self.search([])` which returns all records regardless of `active`. An inactive rule (`active=False`) is still processed by `_recycle_records()` but its staged records were already deleted when it was deactivated (via the ORM cascade in `write`). So effectively only active rules produce new staged records.

4. **Dedup across rules:** `mapped_existing_records` is built once at the top using `recycle_model_id in self.ids`. Since `_cron_recycle_records()` calls `search([])`, this includes recycle records from all rules currently being processed. However, a res_id staged by rule A is correctly excluded from rule B only if rule B is also in `self.ids` -- in the cron, all rules are, so cross-rule deduplication works correctly.

5. **Automatic mode commit-per-batch:** After each 5,000 records are created and validated, `cr.commit()` is called. If the cron is interrupted (e.g., Odoo restart), only uncommitted batches are lost; already-committed batches are durable. If the cron fails partway through a rule, that rule's partially created recycle records remain in the DB and will be skipped on the next run (they're already in `mapped_existing_records`).

6. **`is_test` guard:** `modules.module.current_test` is Odoo's registry flag. When running under the test suite, `commit()` is skipped to avoid corrupting the test transaction. Forcing commits in test mode would make subsequent test assertions unreliable.

### Performance: Computed Field Double-Query Pattern

Both `_compute_name` and `_compute_company_id` use `@api.depends('res_id')`:

```python
@api.depends('res_id')
def _compute_name(self):
    original_records = {(r._name, r.id): r for r in self._original_records()}
    for record in self:
        original_record = original_records.get((record.res_model_name, record.res_id))
        record.name = original_record.display_name if original_record else _('**Record Deleted**')

@api.depends('res_id')
def _compute_company_id(self):
    original_records = {(r._name, r.id): r for r in self._original_records()}
    for record in self:
        original_record = original_records.get((record.res_model_name, record.res_id))
        record.company_id = self._get_company_id(original_record) if original_record else self.env['res.company']
```

When Odoo renders a form with N recycle records, it calls each compute method separately. For N = 1000, this generates:
- 1 query in `_compute_name` (batch browse + exists on each distinct model)
- 1 query in `_compute_company_id` (same batch, re-resolved)
- Plus N `display_name` reads (one per distinct original record)

The `_original_records()` call is essentially a cache-busting mechanism -- it re-queries the DB for every render even if the original records have not changed. This is by design (always show current state) but means the form view of a rule with 10,000 staged records will be slow.

### Odoo 18 -> 19 Changes

| Aspect | Odoo 18 | Odoo 19 | Impact |
|--------|---------|---------|--------|
| `time_field_id` domain | No `store=True` filter | `('store', '=', True)` added to domain | Prevents selecting non-stored computed date fields, which would cause errors at `search()` time |
| `Domain` class usage | `expression.domain()` string eval | `Domain(ast.literal_eval(...))` from `odoo.fields` | Cleaner, safer domain composition; avoids manual `expression` module |
| Archive constraint check | `if model.uses_active` | `'active' not in self.env[model.res_model_name]` | More explicit membership test; functionally equivalent |
| `recycle_model_id` index | Plain `index=True` (full btree) | `index='btree_not_null'` (partial btree) | More efficient: only indexes rows where `recycle_model_id IS NOT NULL` (all rows, since it's non-nullable in Odoo 19) |
| `notify_user_ids` domain | Unknown | `all_group_ids` field used for inherited group matching | Respects group inheritance chains; a user in a group that itself is in `base.group_system` qualifies |

### Security Model

**ACL:** Both models require `base.group_system` (full admin). No other group has any access:

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_data_recycle_model_group_system,access_data_recycle_model_group_system,model_data_recycle_model,base.group_system,1,1,1,1
access_data_recycle_record_group_system,access_data_recycle_record_group_system,model_data_recycle_record,base.group_system,1,1,1,1
```

**`sudo()` execution:** The cron, `_recycle_records()`, `action_validate()`, and `_original_records()` all execute via `sudo()`. This bypasses both record rules (`ir.rule`) and field-level access rights (`groups` attribute on fields). This is intentional: recycle rules are defined only by system administrators and must operate across all data regardless of per-record access rules. A user with access to configure recycle rules implicitly has `base.group_system` access.

**Cross-model sudo risk:** Because `_recycle_records()` calls `sudo()` on arbitrary target models, it can archive/delete records that the system administrator itself cannot normally delete (e.g., records protected by record rules that exempt certain users). This is correct behavior for a system cleanup tool but means the recycle rule configuration should be carefully guarded.

**`notify_user_ids` restriction:**
```python
domain=lambda self: [('all_group_ids', 'in', self.env.ref('base.group_system').id)]
```
Only users who are direct or inherited members of the System Administrator group can be selected as notification recipients. The `all_group_ids` field on `res.users` (introduced in Odoo 15+) resolves the full group inheritance chain, not just direct group assignments.

**No `share` users:** The UI also enforces `('share', '=', False)` on the many2many widget, preventing portal/internal users from being selected even if they somehow have system admin rights.

### Expert Mode: `open_records()` Action Context Resolution

```python
def open_records(self):
    self.ensure_one()
    action = self.env["ir.actions.actions"]._for_xml_id("data_recycle.action_data_recycle_record")
    action['context'] = dict(ast.literal_eval(action.get('context', '{}')),
                             searchpanel_default_recycle_model_id=self.id)
    return action
```

This method resolves an action defined in XML and injects a context key. The action originally has no explicit context, so `action.get('context', '{}')` returns `'{}'`. `ast.literal_eval('{}')` produces an empty dict `{}`. `dict({}, searchpanel_default_recycle_model_id=self.id)` adds the key, producing `{'searchpanel_default_recycle_model_id': <id>}`.

This context is read by the list view's search panel:
```xml
<searchpanel>
    <field name="recycle_model_id" icon="fa-bars" string="Recycle Rules" />
</searchpanel>
```

The searchpanel pre-selects the rule matching the context key, filtering the list to only that rule's staged records.

### Expert Mode: Notification `_send_notification()` IDOR Protection

The notification uses `message_notify` with `model=self._name` and `res_id=self.id` -- the recycle **rule** ID, not the original record ID. The link in the notification body points to `/odoo/<recycle_model_id>/action-data_recycle.action_data_recycle_record_notification?menu_id=<menu_id>`. The controller resolves this to the `action_data_recycle_record_notification` action which has `context='{searchpanel_default_recycle_model_id: active_id}'`. Because `active_id` comes from the URL path (the recycle model ID), an attacker cannot use this link to view another rule's recycle records without knowing its numeric ID. The ACL (`base.group_system`) already restricts who can access the recycle rule list.

### Edge Cases

**1. Record deleted externally between staging and validation:**
`_original_records()` calls `exists()` which silently drops IDs no longer in the DB. In `action_validate()`, such records are skipped (`if not original_record: continue`), and the orphaned recycle record is also deleted via `records_done.unlink()` at the end -- no error is raised.

**2. Target model lacks `company_id` field:**
`_get_company_id()` checks `'company_id' in self.env[record._name]` before accessing `record.company_id`. If absent, it returns `self.env['res.company']` (empty recordset). The `company_id` field on `data_recycle.record` is purely for display/filtering -- it does not affect recycling behavior. When the searchpanel is used, records from models without `company_id` simply show an empty company filter value.

**3. `recycle_mode = 'automatic'` with cascading deletes:**
Each `action_validate()` call calls `sudo().unlink()` or `sudo().action_archive()` on the target model. For models with deep `ondelete='cascade'` hierarchies (e.g., `sale.order` -> `sale.order.line` -> `account.analytic.line`), each `unlink()` triggers recursive cascade deletes that may be slow. For example, deleting 5,000 `sale.order` records could cascade to delete hundreds of thousands of line records within a single `action_validate()` call. No sub-batching within the per-model unlink is provided.

**4. `domain` with invalid Python on old rules:**
If a rule was created with a custom domain in an earlier version and the domain becomes invalid (e.g., referencing a field that no longer exists), `ast.literal_eval()` will raise an `ValueError`. In the current implementation, there is no try/except around the domain parse -- the cron will fail for that rule, rolling back any uncommitted changes from earlier rules in the same call. Production rules should use the domain widget to ensure syntactically valid domains.

**5. Multiple recycle rules targeting the same model:**
Each `data_recycle.model` operates independently. If two rules target the same model with overlapping domains, the same `res_id` may be staged by both rules simultaneously. On the next cron run, the newly staged records are again checked against `mapped_existing_records`, so re-staging the same res_id from the other rule is prevented. However, `_original_records()` and `action_validate()` on one rule do not affect the other rule's recycle records. If both rules are in automatic mode, the same original record could be deleted by the first rule and cause the second rule's recycle record to show `**Record Deleted**`.

**6. Notification with `records_count = 0`:**
`_send_notification()` checks `if records_count else []` for `partner_ids` -- no notification is sent if no new records were staged since the last notification. This prevents spamming admins with empty notifications.

**7. `notify_frequency_period = 'weeks'` -- relativedelta quirk:**
`relativedelta(weeks=1)` counts in 7-day units, not calendar weeks. A notification scheduled for every 1 week fires 7 days after the last notification, not on the same weekday. Use `notify_frequency_period = 'months'` with `notify_frequency = 1` for approximate monthly notifications.

**8. Rule deactivation during an active cron run:**
If a rule's `active` is set to `False` while `_recycle_records()` is iterating over `self`, the rule is still processed (the rule was already in the recordset when iteration started). However, the ORM-level cascade deletes any recycle records created earlier in the same cron run for that rule when the write completes. The `mapped_existing_records` dict is built before any rule processing, so it does not include records that would be cascade-deleted mid-iteration.

**9. Cron runs on inactive rules with `active=False`:**
`_cron_recycle_records()` calls `self.search([])` which returns ALL rules. For an inactive rule, `recycle_record_ids` is empty (already cleaned by the deactivation cascade), and the search against the target model produces zero candidates (since the rule's domain/time fields are still valid). The inactive rule consumes a small amount of processing time but produces no side effects. To fully stop processing, set `active=False` on the rule.

---

## Related Documentation

- [Modules/mail](Modules/mail.md) -- `mail.thread` notifications via `message_notify()`
- [Core/API](Core/API.md) -- `@api.depends`, `@api.constrains`, `compute_sudo`, `@api.model`
- [Core/Fields](Core/Fields.md) -- `Domain` field class, `Many2one`, `One2many`, `index='btree_not_null'`
- [Patterns/Workflow Patterns](odoo-18/Patterns/Workflow Patterns.md) -- Cron-based automation, `state='code'` cron type
- [Patterns/Security Patterns](odoo-18/Patterns/Security Patterns.md) -- ACL CSV, `sudo()`, record rules, `all_group_ids`
- [Tools/ORM Operations](odoo-18/Tools/ORM Operations.md) -- `search()`, `flush_all()`, `sudo()`, `exists()`, `read_group`, batch processing with `split_every`
