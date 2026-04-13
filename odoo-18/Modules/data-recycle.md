---
Module: data_recycle
Version: Odoo 18
Type: Core
Tags: #GDPR #cleanup #archival #data-hygiene #retention
---

# Data Recycle (`data_recycle`)

**Module Path:** `~/odoo/odoo18/odoo/addons/data_recycle/`

**Depends:** `mail`

**Manifest Version:** `1.3`

**Category:** Productivity/Data Cleaning

**License:** LGPL-3

**Application:** `True` (appears in Apps menu)

## Overview

The `data_recycle` module provides rule-based automatic cleanup of stale database records. It implements a **recycle rule** system: for any Odoo model, an administrator defines a domain filter and a time-based threshold. Records matching the rule are queued as `data_recycle.record` entries for review, then either archived or permanently deleted — either automatically or with manual approval.

Primary use cases:
- **GDPR compliance:** Automatically delete or archive personal data older than the retention period.
- **Database hygiene:** Remove old log records, cancelled draft documents, deprecated test data.
- **Storage management:** Delete attachments and blobs associated with recycled records.

### Architecture

```
data_recycle.model (recycle rule)
  res_model_id ──► ir.model (target Odoo model)
  domain ────────► filter criteria
  time_field_id + time_field_delta ──► age threshold

data_recycle.record (pending action)
  res_id ──────────► original record in target model
  recycle_model_id ──► parent data_recycle.model

_cron_recycle_records() [daily at 3:00 AM]
  │
  ├── Search target model with domain + time filter
  ├── Create data_recycle.record for new candidates
  └── If recycle_mode == 'automatic': action_validate() immediately
  └── If recycle_mode == 'manual':    queue for review

action_validate()
  recycle_action == 'archive'  → toggle_active() on original record
  recycle_action == 'unlink'    → unlink() on original record
  └── Delete data_recycle.record
```

---

## Model: `data_recycle.model`

**File:** `~/odoo/odoo18/odoo/addons/data_recycle/models/data_recycle_model.py`

** `_name`: `data_recycle.model`**
** `_description`: `'Recycling Model'`
** `_order`: `name`**

Represents a single recycle rule. One rule per target model.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | `Char` | Rule name. Auto-filled from `res_model_id.name` if not set. Editable. |
| `active` | `Boolean` | Whether the rule is active. Disabling a rule deletes all pending `data_recycle.record` entries for it. |
| `res_model_id` | `Many2one(ir.model)` | The target Odoo model to recycle. Required. `ondelete='cascade'`. |
| `res_model_name` | `Char` (related, stored) | The `model` string of the target model (e.g., `'sale.order'`). |
| `recycle_record_ids` | `One2many(data_recycle.record)` | Inverse link to pending recycle records. |
| `recycle_mode` | `Selection` | `'manual'` (default) — queue records for review. `'automatic'` — execute immediately. |
| `recycle_action` | `Selection` | `'archive'` — set `active=False`. `'unlink'` — permanently delete. Default: `'unlink'`. |
| `domain` | `Char` (domain) | Additional Odoo domain filter applied alongside the time threshold. `False` or `'[]'` means no extra filter. |
| `time_field_id` | `Many2one(ir.model.fields)` | The date/datetime field on the target model used for age calculation. Must be `ttype` `'date'` or `'datetime'` and `store=True`. |
| `time_field_delta` | `Integer` | Number of time units (default: `1`). |
| `time_field_delta_unit` | `Selection` | `'days'`, `'weeks'`, `'months'`, `'years'`. Default: `'months'`. |
| `include_archived` | `Boolean` | When `True`, archived records are also considered as candidates. Only shown when `recycle_action == 'unlink'`. |
| `records_to_recycle_count` | `Integer` (computed) | Count of pending `data_recycle.record` entries for this rule. |
| `notify_user_ids` | `Many2many(res.users)` | Users to notify when new records are queued (manual mode only). Restricted to `base.group_system` members. Default: current user. |
| `notify_frequency` | `Integer` | Notification interval (default: `1`). |
| `notify_frequency_period` | `Selection` | `'days'`, `'weeks'`, `'months'`. Default: `'weeks'`. |
| `last_notification` | `Datetime` | Timestamp of last notification sent. Readonly. |

### SQL Constraints

```python
_sql_constraints = [
    ('check_notif_freq', 'CHECK(notify_frequency > 0)',
     'The notification frequency should be greater than 0'),
]
```

### Constraints

#### `_check_recycle_action`

```python
@api.constrains('recycle_action')
def _check_recycle_action(self):
    for model in self:
        if model.recycle_action == 'archive' and \
           'active' not in self.env[model.res_model_name]:
            raise UserError(_("This model doesn't manage archived records. "
                              "Only deletion is possible."))
```

Blocks setting `recycle_action = 'archive'` if the target model does not have an `active` field. Only models with `active` support (the standard Odoo mixin) can be archived.

### Key Methods

#### `_compute_name`

```python
@api.depends('res_model_id')
def _compute_name(self):
    for model in self:
        if not model.name:
            model.name = model.res_model_id.name if model.res_model_id else ''
```

Auto-fills the rule name from the target model's technical name (e.g., `res.partner`). Only set if the name is currently empty (preserves user-set names).

#### `_compute_records_to_recycle_count`

```python
def _compute_records_to_recycle_count(self):
    count_data = self.env['data_recycle.record']._read_group(
        [('recycle_model_id', 'in', self.ids)],
        ['recycle_model_id'],
        ['__count'])
    counts = {recycle_model.id: count for recycle_model, count in count_data}
    for model in self:
        model.records_to_recycle_count = counts.get(model.id, 0)
```

Uses `_read_group` aggregation to efficiently count pending records per rule.

#### `_recycle_records(batch_commits=False)`

```python
def _recycle_records(self, batch_commits=False):
    self.env.flush_all()
    records_to_clean = []
    is_test = bool(config['test_enable'] or config['test_file'])

    # Build map of existing recycle records to avoid duplicates
    existing_recycle_records = self.env['data_recycle.record'].with_context(
        active_test=False).search([('recycle_model_id', 'in', self.ids)])
    mapped_existing_records = defaultdict(list)
    for recycle_record in existing_recycle_records:
        mapped_existing_records[recycle_record.recycle_model_id].append(
            recycle_record.res_id)

    for recycle_model in self:
        # Build the domain: explicit domain + time-based threshold
        rule_domain = ast.literal_eval(recycle_model.domain) \
            if recycle_model.domain and recycle_model.domain != '[]' else []
        if recycle_model.time_field_id and recycle_model.time_field_delta:
            if recycle_model.time_field_id.ttype == 'date':
                now = fields.Date.today()
            else:
                now = fields.Datetime.now()
            delta = relativedelta(**{recycle_model.time_field_delta_unit:
                                     recycle_model.time_field_delta})
            rule_domain = expression.AND([
                rule_domain,
                [(recycle_model.time_field_id.name, '<=', now - delta)]
            ])
        model = self.env[recycle_model.res_model_name]
        if recycle_model.include_archived:
            model = model.with_context(active_test=False)
        records_to_recycle = model.search(rule_domain)

        # Create recycle records for new candidates only
        records_to_create = [{
            'res_id': record.id,
            'recycle_model_id': recycle_model.id,
        } for record in records_to_recycle
          if record.id not in mapped_existing_records[recycle_model]]

        if recycle_model.recycle_mode == 'automatic':
            # Execute immediately in batches, commit per batch to avoid rollback
            for batch in split_every(DR_CREATE_STEP_AUTO, records_to_create):
                self.env['data_recycle.record'].create(batch).action_validate()
                if batch_commits and not is_test:
                    self.env.cr.commit()
        else:
            # Queue for manual review
            records_to_clean = records_to_clean + records_to_create

    # Batch-create pending records for all manual rules
    for batch in split_every(DR_CREATE_STEP_MANUAL, records_to_clean):
        self.env['data_recycle.record'].create(batch)
        if batch_commits and not is_test:
            self.env.cr.commit()
```

**Execution flow per rule:**
1. Get all existing `data_recycle.record` entries for this rule (including discarded ones — `active_test=False`).
2. Build the search domain:
   - Start with the user-defined `domain` (from the UI's domain widget).
   - Append a time-based condition: `time_field <= now - delta` using `dateutil.relativedelta`.
   - Combine with `expression.AND` (both conditions must match).
3. Search the target model for matching records.
4. Filter out any records already in the recycle queue.
5. If `recycle_mode == 'automatic'`: create records and immediately call `action_validate()`, processing in batches of `5000` with per-batch DB commits.
6. If `recycle_mode == 'manual'`: add to the queue for later review, processed in batches of `50000`.

**Batch size constants:**
- `DR_CREATE_STEP_AUTO = 5000` — smaller because each batch triggers `unlink()` or `toggle_active()`.
- `DR_CREATE_STEP_MANUAL = 50000` — larger because records are just inserted.

#### `_cron_recycle_records()`

```python
def _cron_recycle_records(self):
    self.sudo().search([])._recycle_records(batch_commits=True)
    self.sudo()._notify_records_to_recycle()
```

Scheduled action entry point. Called by the daily cron (runs at **3:00 AM**). Runs as superuser (`sudo()`). Two steps:
1. Process all recycle rules and queue/execute records.
2. Send notifications for manual-mode rules.

Registered in `data/ir_cron_data.xml`:
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

#### `_notify_records_to_recycle()`

```python
@api.model
def _notify_records_to_recycle(self):
    for recycle in self.search([('recycle_mode', '=', 'manual')]):
        if not recycle.notify_user_ids or not recycle.notify_frequency:
            continue
        delta = relativedelta(**{
            recycle.notify_frequency_period: recycle.notify_frequency
        })
        if not recycle.last_notification or \
                (recycle.last_notification + delta) < fields.Datetime.now():
            recycle.last_notification = fields.Datetime.now()
            recycle._send_notification(delta)
```

Evaluates whether to send a notification for each manual rule:
- Checks `last_notification + frequency_delta < now`.
- If true, sends an Odoo email notification via `mail.thread.message_notify`.

#### `_send_notification(delta)`

```python
def _send_notification(self, delta):
    self.ensure_one()
    last_date = fields.Date.today() - delta
    records_count = self.env['data_recycle.record'].search_count([
        ('recycle_model_id', '=', self.id),
        ('create_date', '>=', last_date)
    ])
    partner_ids = self.notify_user_ids.partner_id.ids if records_count else []
    if partner_ids:
        self.env['mail.thread'].message_notify(
            body=self.env['ir.qweb']._render('data_recycle.notification', {...}),
            ...
        )
```

Counts records created in the last notification period and sends an email with a direct link to the recycle record list view. If no new records, no notification is sent.

Notification template (`data_recycle_templates.xml`):
```xml
<template id="notification">
We've identified <t t-esc="records_count" /> records to clean with the
'<t t-esc="res_model_label" />' recycling rule.<br/>
You can validate those changes <a href="...">here</a>.
</template>
```

#### `action_recycle_records()`

```python
def action_recycle_records(self):
    self.sudo()._recycle_records()
    if self.recycle_mode == 'manual':
        return self.open_records()
    return
```

"Run Now" button handler. Executes the rule immediately. If manual mode, opens the recycle record list view for review. If automatic, returns nothing (records were already processed).

#### `open_records()`

```python
def open_records(self):
    self.ensure_one()
    action = self.env["ir.actions.actions"]._for_xml_id(
        "data_recycle.action_data_recycle_record")
    action['context'] = dict(
        ast.literal_eval(action.get('context', '{}')),
        searchpanel_default_recycle_model_id=self.id)
    return action
```

Opens the recycle record list filtered to this specific rule via `searchpanel_default_recycle_model_id`.

#### `write(vals)` — Disable Rule Cleanup

```python
def write(self, vals):
    if 'active' in vals and not vals['active']:
        # Deleting a rule removes all its pending records
        self.env['data_recycle.record'].search(
            [('recycle_model_id', 'in', self.ids)]).unlink()
    return super().write(vals)
```

When a rule is deactivated, all pending `data_recycle.record` entries are deleted. This prevents orphaned queue entries for disabled rules.

---

## Model: `data_recycle.record`

**File:** `~/odoo/odoo18/odoo/addons/data_recycle/models/data_recycle_record.py`

** `_name`: `data_recycle.record`**
** `_description`: `'Recycling Record'**

Represents a single record queued for recycling.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `active` | `Boolean` | `True` (default). Set to `False` when discarded via `action_discard()`. Discarded records are hidden but remain in the DB. |
| `name` | `Char` (computed) | Display name of the original record. Shows `'**Record Deleted**'` if the original record no longer exists. |
| `recycle_model_id` | `Many2one(data_recycle.model)` | The rule this record belongs to. `ondelete='cascade'` — deleting the rule deletes these records. |
| `res_id` | `Integer` | The `id` of the original record in the target model. `index=True`. |
| `res_model_id` | `Many2one(ir.model)` (related, stored) | The model of the original record. |
| `res_model_name` | `Char` (related, stored) | The `_name` string of the original record. |
| `company_id` | `Many2one(res.company)` (computed) | The company of the original record (resolved via `_get_company_id`). Falls back to empty if no `company_id` field exists on the target model. |

### Key Methods

#### `_get_company_id(record)`

```python
@api.model
def _get_company_id(self, record):
    company_id = self.env['res.company']
    if 'company_id' in self.env[record._name]:
        company_id = record.company_id
    return company_id
```

Resolves the company from the original record if it has a `company_id` field. Used for `company_id` computation and multi-company filtering.

#### `_compute_name()` and `_compute_company_id()`

Both use `_original_records()` to resolve the current state of the original records. If the original record was deleted externally (not via the recycle flow), the name shows `'**Record Deleted**'` and the company is cleared.

#### `_original_records()`

```python
def _original_records(self):
    if not self:
        return []
    records = []
    records_per_model = {}
    for record in self.filtered(lambda r: r.res_model_name):
        ids = records_per_model.get(record.res_model_name, [])
        ids.append(record.res_id)
        records_per_model[record.res_model_name] = ids
    for model, record_ids in records_per_model.items():
        recs = self.env[model].with_context(active_test=False).sudo().browse(
            record_ids).exists()
        records += [r for r in recs]
    return records
```

Batches all `res_id` lookups by model and fetches the original records in bulk. Uses `sudo()` to bypass record rules (a system-level operation). `active_test=False` to include archived records. Returns only `exists()` records — deleted originals are excluded.

#### `action_validate()`

```python
def action_validate(self):
    records_done = self.env['data_recycle.record']
    record_ids_to_archive = defaultdict(list)
    record_ids_to_unlink = defaultdict(list)
    original_records = {'%s_%s' % (r._name, r.id): r
                        for r in self._original_records()}

    for record in self:
        original_record = original_records.get(
            '%s_%s' % (record.res_model_name, record.res_id))
        records_done |= record
        if not original_record:
            continue  # Already deleted externally
        if record.recycle_model_id.recycle_action == "archive":
            record_ids_to_archive[original_record._name].append(original_record.id)
        elif record.recycle_model_id.recycle_action == "unlink":
            record_ids_to_unlink[original_record._name].append(original_record.id)

    for model_name, ids in record_ids_to_archive.items():
        self.env[model_name].sudo().browse(ids).toggle_active()
    for model_name, ids in record_ids_to_unlink.items():
        self.env[model_name].sudo().browse(ids).unlink()

    records_done.unlink()  # Remove recycle record after action
```

**Validate button handler:**
1. Collects all original records via `_original_records()`.
2. Batches by action type (`archive` vs `unlink`) and by model.
3. Executes `toggle_active()` for archive — sets `active=False`.
4. Executes `unlink()` for delete — permanent removal.
5. Deletes the `data_recycle.record` entries after processing.
6. Runs as `sudo()` — bypasses ACL for the system-level cleanup operation.

#### `action_discard()`

```python
def action_discard(self):
    self.write({'active': False})
```

Sets the recycle record to inactive (soft-delete). Discarded records remain in the DB with `active=False`, hidden in the UI but visible via the "Discarded" search filter.

---

## Security Model

**File:** `~/odoo/odoo18/odoo/addons/data_recycle/security/ir.model.access.csv`

```
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_data_recycle_model_group_system, ..., model_data_recycle_model, base.group_system, 1,1,1,1
access_data_recycle_record_group_system, ..., model_data_recycle_record, base.group_system, 1,1,1,1
```

Only members of **Technical Settings / Administration** (`base.group_system`) have CRUD access to both models. Regular users cannot create or modify recycle rules.

---

## Menu Structure

```
Settings → Data Cleaning                    [menu_data_cleaning_root]
  ├── Recycle Records                        [menu_data_recycle_record]
  │      → action: action_data_recycle_record
  └── Configuration                          [menu_data_cleaning_config]
         └── Rules                           [menu_data_cleaning_config_rules]
                └── Recycle Records          [menu_data_cleaning_config_rules_recycle]
                       → action: action_data_recycle_config
```

---

## L4: Setting Up Recycle Rules — Step by Step

### Step 1: Choose a Model

Select the Odoo model to clean (e.g., `crm.lead`, `account.move`, `res.partner`).

### Step 2: Choose Time Field and Threshold

Pick the date/datetime field that represents record age:
- `create_date` — when the record was created
- `date_deadline` — project's due date
- `write_date` — last modification date
- Any custom `date`/`datetime` field on the model

Set `time_field_delta` and `time_field_delta_unit`. Example: `time_field_delta=24, unit=months` means records older than 24 months.

### Step 3: Add Domain Filter (Optional)

Use the domain widget to add extra conditions. Examples:
- `[('state', '=', 'cancel')]` — only cancelled records
- `[('active', '=', False)]` — only already-archived records
- `[('probability', '<=', 10)]` — lost leads with low probability

Combined domain (both time + filter): `expression.AND([time_domain, extra_domain])`.

### Step 4: Choose Action

| Action | Behavior | Constraint |
|--------|----------|------------|
| `Archive` | Sets `active=False` on the record | Target model must have `active` field |
| `Delete` | Permanently calls `unlink()` | No constraint, but irreversible |

### Step 5: Choose Mode

| Mode | Behavior | Notification |
|------|----------|--------------|
| `Manual` | Records queued for review. Admin clicks "Validate" on each. | Optional email to `notify_user_ids` per schedule |
| `Automatic` | Records deleted/archived immediately on cron run | No notification |

### Step 6: Configure Notifications (Manual Mode Only)

Select users to notify and set frequency. The notification email links directly to the recycle record list filtered by this rule.

---

## L4: Related Records and Cascade Behavior

The `data_recycle` module **does not cascade deletes** — it acts only on the target model record.

**If a record has child/related records:**
- `unlink` on the parent does **not** automatically delete child records unless `ondelete='cascade'` is defined on the foreign key in PostgreSQL.
- For example, recycling a `sale.order` will NOT automatically delete its `sale.order.line` records unless the database schema has `ondelete='cascade'` on the `order_id` FK.
- It is the administrator's responsibility to set up cascade rules in the database or to use `unlink()` overrides that handle related records.

**Recommendation:** Use `archive` mode (`recycle_action='archive'`) as a first step. This makes the records invisible in Odoo's normal UI but keeps them in the database for audit or recovery. After a retention period, switch to `unlink` mode once cascade behavior is confirmed.

---

## L4: Audit Trail

### What Happens When a Record Is Recycled

1. **Archive (`toggle_active`):**
   - `active` set to `False` on the original record.
   - Standard Odoo archival — `write_date` updated.
   - Record disappears from normal views but remains queryable with `active_test=False`.
   - `mail.thread` tracked messages (chatter) are preserved.

2. **Delete (`unlink`):**
   - Record permanently removed from the database.
   - `data_recycle.record` entry deleted at the same time.
   - No `mail.message` or `mail.tracking.value` records are automatically preserved.
   - For GDPR erasure requests, consider overriding `unlink()` to create an audit log entry first.

### Tracking Who Initiated the Action

The recycle action runs under `sudo()` in the context of the cron job. The initiating user is not recorded on the individual records. For compliance requiring an audit trail of who deleted what, consider:
- Subclassing `action_validate()` to log to `audit.log` or `res.log`.
- Using `mail.thread.message_notify()` to create a chatter message before deletion.

### Preventing Accidental Recycling

- `include_archived` defaults to `False` — archived records are not re-queued.
- Domain filters are combined with `AND`, so time condition AND domain must both match.
- Discarded records (`active=False` on `data_recycle.record`) are not re-created for the same rule.

---

## Related

- [Modules/cloud-storage](modules/cloud-storage.md) — attachments stored externally
- [Patterns/Security Patterns](patterns/security-patterns.md) — ACL, ir.rule, record rules
- [Core/Fields](core/fields.md) — date/datetime fields
