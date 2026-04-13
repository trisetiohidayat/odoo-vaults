---
type: module
module: privacy_lookup
tags: [odoo, odoo19, privacy, gdpr, anonymization, compliance]
---

# Privacy Lookup (privacy_lookup)

## Overview

| Property | Value |
|----------|-------|
| **Technical Name** | `privacy_lookup` |
| **Version** | 1.0 |
| **Category** | Hidden |
| **Dependencies** | `mail` |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Auto-install** | True |
| **Location** | `~/odoo/odoo19/odoo/addons/privacy_lookup/` |

`privacy_lookup` is Odoo's GDPR compliance module. It provides a wizard-driven privacy lookup that searches all records linked to a data subject by name or email across the entire database, then allows archival or permanent deletion of those records, with a full anonymized audit trail logged to `privacy.log`. Intended to support Articles 17 and 18 of the GDPR (Right to Erasure / Right to Restriction of Processing).

> **Important:** This module is a discovery and action tool only. It does **not** perform automatic field-level anonymization, blob anonymization, or fiscal record erasure. Truly erasing all personal data from a system (including message bodies, attachment blobs, fiscal data) requires additional custom development or specialized anonymization modules.

---

## Module Architecture

```
privacy_lookup/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── res_partner.py           # Adds action_privacy_lookup() on res.partner
│   └── privacy_log.py           # privacy.log model (audit trail)
├── wizard/
│   ├── __init__.py
│   └── privacy_lookup_wizard.py # privacy.lookup.wizard + privacy.lookup.wizard.line
├── views/
│   └── privacy_log_views.xml    # privacy.log list/form views + menu
├── wizard/
│   └── privacy_lookup_wizard_views.xml  # wizard form + wizard line list
├── security/
│   └── ir.model.access.csv       # ACL: only base.group_system
├── data/
│   └── ir_actions_server_data.xml  # Archive Selection / Delete Selection server actions
└── tests/
    └── test_privacy_wizard.py
```

---

## Models

### `privacy.lookup.wizard` (TransientModel)

The primary entry point. A transient record that holds search criteria and the result set of found references. Transient models are automatically cleaned up by Odoo's garbage collector; `_transient_max_count = 0` and `_transient_max_hours = 24` are set — no size limit, but records are purged after 24 hours of inactivity.

#### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Data subject's full name. Used as `ILIKE` pattern in the search query. |
| `email` | Char | Yes | Data subject's email address. Normalized via `tools.email_normalize()` before search; raises `UserError` if invalid. |
| `line_ids` | One2many `privacy.lookup.wizard.line` | No | Found record references populated by `action_lookup()`. |
| `execution_details` | Text (compute+store) | No | Concatenated string of all line-level action descriptions (archive/unlink). Triggers `_post_log()` on every recompute. |
| `log_id` | Many2one `privacy.log` | No | Created-once privacy audit log record shared by all lines in this wizard session. |
| `records_description` | Text (compute) | No | Human-readable summary grouped by model, e.g. `Contact (2): #10, #42`. Internal model IDs (`model.model`) only shown to users in `base.group_no_one` (technical features). |
| `line_count` | Integer (compute) | No | Cached count of `line_ids`, displayed as a stat button on the wizard form. |

#### `_compute_execution_details()`

```python
@api.depends('line_ids.execution_details')
def _compute_execution_details(self):
    for wizard in self:
        wizard.execution_details = '\n'.join(
            line.execution_details for line in wizard.line_ids if line.execution_details)
        wizard._post_log()
```

Called whenever any line's `execution_details` changes. Also fires `_post_log()` as a side effect — including on the first compute after lookup, and again after each line is archived or deleted. This means `_post_log()` runs multiple times per wizard session, but its logic guards against duplicate log creation (see `_post_log()` below).

#### `_compute_records_description()`

Groups `line_ids` by `res_model_id`, then formats each group as `{model.name} ({count}): #{id1}, #{id2}, ...`. Internal technical IDs (`model.model`) are only revealed to users with the "Technical Features" group (`base.group_no_one`). This prevents a privacy officer from seeing model names they should not access in multi-company or restricted environments.

#### `_get_query_models_blacklist()`

Returns the hardcoded list of models excluded from the cross-model search. Rationale for each entry:

| Model | Reason |
|-------|--------|
| `res.partner` | Searched directly as the primary identity anchor; adding it again here would duplicate rows. |
| `res.users` | Searched directly as a primary anchor. |
| `mail.notification` | `ondelete = cascade` child of `mail.message`; retrieved through `mail.message.author_id` which already traces back to the partner. |
| `mail.followers` | `ondelete = cascade` child of `mail.message` or `discuss.channel`; the parent record is already in the result set. |
| `discuss.channel.member` | `ondelete = cascade` child of `discuss.channel`; already covered by the channel membership link back to partner. |
| `mail.message` | Handled as a **special case** in the SQL with a fixed `UNION ALL` (Step 2 in `_get_query()`) because direct messages are always readable regardless of access rules. |

> **L4 / Performance:** Omitting `mail.notification`, `mail.followers`, and `discuss.channel.member` from the per-model loop avoids scanning large tables that would produce rows immediately invalidated by their parent cascade. This can reduce the query footprint significantly on databases with high messaging volume.

#### `_get_query()` — The Core Search SQL

This method builds a single large SQL query using `SQL` (the safe query builder, introduced in Odoo 15 to replace string formatting). The query has three stages:

**Step 1: Anchor CTE — `indirect_references`**

```sql
WITH indirect_references AS (
    SELECT id FROM res_partner
    WHERE email_normalized = %s OR name ILIKE %s
)
```

Creates a Common Table Expression (CTE) of all `res.partner` records matching the email exactly (normalized) or the name via case-insensitive `ILIKE`. This CTE is reused for all subsequent joins.

**Step 1 (continued): Primary direct searches**

- `res_partner` rows where `id IN (SELECT id FROM indirect_references)` — retrieves the partner records themselves.
- `res_users` rows where `login ILIKE email` OR `partner_id IN indirect_references` — finds system user accounts matching the data subject.
- `mail_message` rows where `author_id IN indirect_references` — all messages authored by the partner, always included regardless of record-level `ir.rule`.

> **L4 / Security:** The `mail.message` search bypasses `ir.rule` intentionally. Privacy officers may need to see that messages exist even if ACLs would otherwise hide them. However, the message body content is not shown — only the record existence (ID/model) is logged.

**Step 3: Per-model iteration**

For every model in `self.env`:

1. Skip if transient, not `_auto`, or on the blacklist.
2. For each email field (`email_normalized`, `email`, `email_from`, `company_email`): if the field exists and is stored, add a condition using `=` (for normalized) or `ILIKE` (for others). Only `char`-type `_rec_name` fields that are not translated are included in the name search.
3. For each `Many2one` field pointing to `res.partner` with `store=True` and `ondelete != 'cascade'`: add a condition `field_name IN (SELECT id FROM indirect_references)`. This catches **indirect references** — records that reference the partner but do not store email/name directly (e.g., `sale.order.line` via `order_id.partner_id`).
4. If any conditions exist, `UNION ALL` the results into the growing query.

> **L4 / Performance:** The per-model loop iterates over every model registered in the ORM's environment (`self.env`). This means models from all installed modules are checked. The `model._transient` and `model._auto` guards skip transient and abstract models, but the iteration itself has O(n) overhead where n = total registered models. The actual performance bottleneck is the `UNION ALL` query with multiple `ILIKE` scans on large tables.
>
> **L4 / Edge case — `mailing.trace`:** The code special-cases `mailing.trace` by using `email` (not `email_normalized`) as a normalized-equivalent field. This is because mailing traces store email in a normalized form in the `email` column specifically, so `=` comparison is safe here even though `email` is a plain `Char`.

#### `action_lookup()`

```python
def action_lookup(self):
    self.ensure_one()
    query = self._get_query()
    self.env.flush_all()   # Ensure all pending writes are flushed to DB
    self.env.cr.execute(query)
    results = self.env.cr.dictfetchall()
    self.line_ids = [(5, 0, 0)] + [(0, 0, reference) for reference in results]
    return self.action_open_lines()
```

- `flush_all()` forces the ORM to write any pending changes before executing raw SQL.
- Results are a list of dicts with keys: `res_model_id`, `res_id`, `is_active`.
- `[(5, 0, 0)]` clears existing lines before adding new ones.
- After population, immediately opens the lines list view.

#### `_post_log()`

```python
def _post_log(self):
    self.ensure_one()
    if not self.log_id and self.execution_details:
        self.log_id = self.env['privacy.log'].create({...})  # create once
    else:
        self.log_id.execution_details = self.execution_details
        self.log_id.records_description = self.records_description
```

Two important behaviors:

1. The log is created **only on first compute** where `execution_details` is non-empty. Subsequent recomputes update the existing log record rather than creating new ones. This ensures one data subject lookup = one `privacy.log` record, regardless of how many lines are acted upon.
2. `_post_log()` is called from within `_compute_execution_details()` which is triggered by `@api.depends('line_ids.execution_details')`. If a user archives a line, then deletes another, `_post_log()` fires twice — but the guard `if not self.log_id` prevents duplicate creation.

> **L4 / Bug pattern — unique log test:** The test `test_wizard_unique_log` confirms this guard works correctly. Two partners with the same email both go through the wizard in sequence. Archiving both partner lines still results in exactly one `privacy.log` record, proving the log is deduplicated by the wizard session (not by email uniqueness at the DB level — `privacy.log` has no unique constraint on email).

#### `action_open_lines()`

Returns an `ir.actions.act_window` for `privacy.lookup.wizard.line` filtered to `wizard_id = self.id`. The lines view is a list (not form) so the operator can see all found records at a glance.

---

### `privacy.lookup.wizard.line` (TransientModel)

Represents one found record (a reference to any model) returned by the lookup. Lines are transient because they are temporary scratch records scoped to one wizard session.

#### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `wizard_id` | Many2one `privacy.lookup.wizard` | Yes | Parent wizard session. Cascade delete. |
| `res_id` | Integer | Yes | The database ID of the found record. |
| `res_model_id` | Many2one `ir.model` | Yes | The model (`ir.model` record) the found record belongs to. `ondelete = cascade`. |
| `res_model` | Char (related, stored) | No | The `model` string from `res_model_id`. Convenience field for filtering. |
| `res_name` | Char (compute+store) | No | Display name of the found record, fetched via `display_name` with sudo. Falls back to `{model.name}/{res_id}` if record not found or has no name. |
| `resource_ref` | Reference (compute) | No | Lazy reference field for one-click navigation. Uses `_selection_target_model()` to populate the model dropdown. |
| `has_active` | Boolean (compute+store) | No | Whether the target model has an `active` field. Controls visibility of the archive toggle. |
| `is_active` | Boolean | No | Current `active` state of the target record. Toggled by the user in the list view. Triggers `_onchange_is_active()`. |
| `is_unlinked` | Boolean | No | Set to `True` after `action_unlink()` completes. Controls visibility of the Delete button. |
| `execution_details` | Char | No | Human-readable action taken on this line, e.g. `Archived Contact #42`. |

#### `_selection_target_model()`

```python
@api.model
def _selection_target_model(self):
    return [(model.model, model.name) for model in self.env['ir.model'].sudo().search([])]
```

Returns the full list of all registered models for the `Reference` field widget. Uses `sudo()` because the user performing the lookup may not have read access to all `ir.model` records. The `res_model` stored field filters the actual display.

#### `_compute_resource_ref()`

```python
@api.depends('res_model', 'res_id', 'is_unlinked')
def _compute_resource_ref(self):
    for line in self:
        if line.res_model and line.res_model in self.env and not line.is_unlinked:
            try:
                self.env[line.res_model].browse(line.res_id).check_access('read')
                line.resource_ref = '%s,%s' % (line.res_model, line.res_id or 0)
            except Exception:
                line.resource_ref = None  # hidden in view when None
        else:
            line.resource_ref = None
```

Attempts to read the target record with the current user's access rights. If `check_access('read')` raises (e.g., due to a multi-company `ir.rule`), `resource_ref` is silently set to `None` and the record row hides the reference link and the Open Record button. The line **is still present** in the list (since it was found by raw SQL, not ORM access) — it just cannot be navigated to.

> **L4 / Multi-company edge case:** `test_wizard_multi_company` explicitly verifies this behavior. A partner with a different `company_id` is found by SQL (email match) but `resource_ref` is `None` for the user running the wizard who lacks cross-company visibility. The line is still visible with just the ID shown.

#### `_onchange_is_active()`

```python
@api.onchange('is_active')
def _onchange_is_active(self):
    for line in self:
        if not line.res_model_id or not line.res_id:
            continue
        action = _('Unarchived') if line.is_active else _('Archived')
        line.execution_details = '%s %s #%s' % (action, line.res_model_id.name, line.res_id)
        self.env[line.res_model].sudo().browse(line.res_id).write({'active': line.is_active})
```

Fired on every toggle of the `is_active` boolean widget. `sudo()` bypasses record-level ACLs — a privacy officer must be able to archive records even if their normal role would not allow it. Model-level ACLs still apply (see security section). Sets `execution_details` which triggers the wizard's compute chain and ultimately `_post_log()`.

#### `action_unlink()`

```python
def action_unlink(self):
    self.ensure_one()
    if self.is_unlinked:
        raise UserError(_('The record is already unlinked.'))
    self.env[self.res_model].sudo().browse(self.res_id).unlink()
    self.execution_details = '%s %s #%s' % (_('Deleted'), self.res_model_id.name, self.res_id)
    self.is_unlinked = True
```

Permanently deletes the target record via `sudo().unlink()`. Sets `is_unlinked = True` to hide the button in the UI. Idempotent guard prevents double-deletion if called twice.

#### `action_archive_all()` / `action_unlink_all()`

Bulk action wrappers. `action_archive_all()` iterates lines that have an `active` field and are currently active, toggling each. `action_unlink_all()` calls `action_unlink()` per line, skipping already-unlinked ones. These are bound to `ir.actions.server` records in `ir_actions_server_data.xml` and appear as action buttons on the list view.

#### `action_open_record()`

```python
def action_open_record(self):
    self.ensure_one()
    return {
        'type': 'ir.actions.act_window',
        'view_mode': 'form',
        'res_id': self.res_id,
        'res_model': self.res_model,
    }
```

Opens the raw form of the target record directly, without going through the wizard's resource reference mechanism. Does not call `check_access` — the form action relies on the ORM's normal window action security which enforces ACLs when the form loads.

---

### `privacy.log` (BaseModel)

Immutable audit log of all privacy lookup executions. Records are created once per wizard session and updated in place as the operator acts on lines. The log stores **anonymized** identifiers to comply with GDPR's data minimization principle — even the audit log itself must not retain unredacted personal data.

#### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `date` | Datetime | Yes | Execution timestamp. Default: `fields.Datetime.now`. |
| `anonymized_name` | Char | Yes | Anonymized data subject name. All characters after the first of each word replaced with `*`. Example: `Rintin Tin` → `R***** T**`. |
| `anonymized_email` | Char | Yes | Anonymized email. Username and domain are individually masked. Common free providers (gmail.com, hotmail.com, yahoo.com) are preserved as-is because masking them adds no privacy value. Example: `rintin.tin@gmail.com` → `r*****.t**@gmail.com`. |
| `user_id` | Many2one `res.users` | Yes | The operator who performed the lookup. Default: `self.env.user`. |
| `execution_details` | Text | No | Action log: all individual archive/unlink operations, concatenated. |
| `records_description` | Text | No | Summary of records found per model at the time of last `_post_log()` call. |
| `additional_note` | Text | No | Free-text field for the operator to add context (e.g., "Subject confirmed identity via phone"). Editable post-creation. |

#### `create()` — Auto-Anonymization Hook

```python
@api.model_create_multi
def create(self, vals_list):
    for vals in vals_list:
        vals['anonymized_name'] = self._anonymize_name(vals['anonymized_name'])
        vals['anonymized_email'] = self._anonymize_email(vals['anonymized_email'])
    return super().create(vals_list)
```

Both `anonymized_name` and `anonymized_email` are overwritten with their anonymized equivalents before the record is saved. Even if a caller passes pre-anonymized strings, they are re-anonymized (idempotent for `_anonymize_name`, but `_anonymize_email` will re-mask an already-masked email — a minor inefficiency but safe).

#### `_anonymize_name(label)`

```python
def _anonymize_name(self, label):
    if not label:
        return ''
    if '@' in label:  # Delegates to email anonymizer if "@" is detected
        return self._anonymize_email(label)
    return ' '.join(e[0] + '*' * (len(e) - 1) for e in label.split(' ') if e)
```

- Splits on spaces, masks all characters after the first in each token.
- Detects `@` in the input string and delegates to `_anonymize_email()` if the "name" field accidentally received an email.

#### `_anonymize_email(label)`

```python
def _anonymize_email(self, label):
    def _anonymize_user(label):
        return '.'.join(e[0] + '*' * (len(e) - 1) for e in label.split('.') if e)
    def _anonymize_domain(label):
        if label in ['gmail.com', 'hotmail.com', 'yahoo.com']:
            return label  # Preserved: already publicly associated with subject
        split_domain = label.split('.')
        return '.'.join([e[0] + '*' * (len(e) - 1) for e in split_domain[:-1] if e] + [split_domain[-1]])
    if not label or '@' not in label:
        raise UserError(_('This email address is not valid (%s)', label))
    user, domain = label.split('@')
    return '{}@{}'.format(_anonymize_user(user), _anonymize_domain(domain))
```

- The `UserError` raised inside `_anonymize_email` during `create()` propagates through the ORM's transaction — a privacy log cannot be created with an invalid email.
- The `gmail.com`/`hotmail.com`/`yahoo.com` special case keeps these domains visible because they are already publicly associated with the data subject (no additional disclosure).
- Domain tokens after the TLD (e.g., `bbc` in `bbc.co.uk`) are masked: `b**`, but the TLD (`co.uk`) is always preserved as-is.

---

### `res.partner` — Extension via `_inherit`

```python
class ResPartner(models.Model):
    _inherit = 'res.partner'

    def action_privacy_lookup(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('privacy_lookup.action_privacy_lookup_wizard')
        action['context'] = {
            'default_email': self.email,
            'default_name': self.name,
        }
        return action
```

Added as a context action button on the partner form. Pre-fills the wizard with the partner's `email` and `name`. Called directly from `res.partner` form views and also from the `res.users` server action (which delegates to `record.partner_id.action_privacy_lookup()`).

---

## Wizard UI Flow

```
Partner form (action button)  or  Settings > Privacy > Privacy Logs
         │                                                      │
         ▼                                                      ▼
  privacy.lookup.wizard (create)  ←  (no direct menu entry)
         │
         ├─ [Lookup] button ──→ action_lookup()
         │                           │
         │    ┌──────────────────────┘
         │    ▼ (flush_all + raw SQL query)
         │    populates line_ids
         │    triggers _post_log() → creates privacy.log
         │    opens privacy.lookup.wizard.line list
         │
         ▼
  privacy.lookup.wizard.line list
         │
         ├─ Toggle is_active ──→ _onchange_is_active()
         │                          ├─ writes active=False on target record (sudo)
         │                          ├─ sets execution_details
         │                          └─ triggers wizard compute → _post_log() update
         │
         ├─ [Delete] button ──→ action_unlink()
         │                          ├─ unlink() on target record (sudo)
         │                          ├─ sets is_unlinked = True
         │                          └─ sets execution_details
         │
         ├─ [Open Record] ──→ action_open_record()
         │                          └─ opens raw form of target record
         │
         ├─ [Archive Selection] (server action)
         │                          └─ action_archive_all() on selected lines
         │
         └─ [Delete Selection] (server action)
                                └─ action_unlink_all() on selected lines
```

---

## Cross-Module Integration

| Module | Integration Point | Details |
|--------|-----------------|---------|
| `mail` | `depends: mail` | Required for `mail.message` search (Step 2 of `_get_query()`) and `author_id` Many2one field. Also required for `mail.notification`/`mail.followers` blacklist comments. |
| `base` | `ir.model.data` lookups | Used to convert model XML IDs (`base.model_res_partner`, etc.) to database IDs in the raw SQL query. |
| `base` | `ir.model` search in lines | `_selection_target_model()` searches all `ir.model` records to populate the Reference widget. |
| `base` | `res.users` partner link | `res.users` server action uses `partner_id` Many2one to find the partner and invoke `action_privacy_lookup()`. |
| `base` | `ir.rule` multi-company | `_compute_resource_ref()` uses `check_access('read')` to suppress lines that fail record-level rules. |
| `base` | `group_no_one` | `records_description` only shows internal model names (`model.model`) to users in the technical features group. |
| `discuss` | Implicit blacklist | `discuss.channel.member` is on the blacklist because it is a cascade child. |

---

## Security

### ACL Summary

| Record | Model | Group | read | write | create | unlink |
|--------|-------|-------|------|-------|--------|--------|
| `privacy.lookup.wizard` | `privacy.lookup.wizard` | `base.group_system` | Yes | Yes | Yes | Yes |
| `privacy.lookup.wizard.line` | `privacy.lookup.wizard.line` | `base.group_system` | Yes | Yes | Yes | No |
| `privacy.log` | `privacy.log` | `base.group_system` | Yes | Yes | Yes | Yes |

**Access is restricted exclusively to `base.group_system`** (Settings > Users & Companies > Users with "Settings" rights). Regular admin, GDPR officer roles without full system access, or portal users cannot use this module. This is by design: data privacy operations are among the most sensitive actions in the system.

### Server Actions

Two `ir.actions.server` records are registered:
- `ir_actions_server_archive_all`: Bound to `privacy.lookup.wizard.line` in list/kanban views. `group_ids = base.group_system`. Called via `records.action_archive_all()`.
- `ir_actions_server_unlink_all`: Same model binding. `group_ids = base.group_system`. Called via `records.action_unlink_all()`.

### Context Menu Actions

| Action | Model | Binding | group_ids |
|--------|-------|---------|-----------|
| `ir_action_server_action_privacy_lookup_partner` | `res.partner` | Form view | `base.group_system` |
| `ir_action_server_action_privacy_lookup_user` | `res.users` | Form view | `base.group_system` |

Both are server actions bound to form views. The `res.users` action delegates to `partner_id.action_privacy_lookup()` to reuse the partner's method.

### Menu Path

Privacy Logs are accessible via **Settings > Privacy > Privacy Logs** (`base.menu_custom` parent). The menu itself is only visible to users in `base.group_system`.

---

## Performance

### O(n) Model Scan

`_get_query()` iterates over every model registered in `self.env`. On a fully-featured Odoo instance with 200+ installed modules, this means iterating over thousands of registered model names. The actual SQL generation is the bottleneck, not the Python loop.

The per-model loop has three stages:
1. **Email field scan** — checks if `email_normalized`, `email`, `email_from`, or `company_email` fields exist and are stored. Most models have one of these.
2. **Name scan** — for models with a `char`-type `_rec_name` that is not translated. Adds an `ILIKE` condition.
3. **Indirect reference scan** — iterates all fields on the model to find `Many2one` to `res.partner` with `store=True` and `ondelete != 'cascade'`. This is the most expensive check at the Python level but filters out cascade children like `res.partner.bank`.

### `flush_all()` Cost

`action_lookup()` calls `flush_all()` before raw SQL execution. On a database with heavy uncommitted writes, this can be slow. However, it is necessary to ensure the search covers all relevant data.

### `ILIKE` on Large Tables

Email and name `ILIKE` scans on tables like `crm_lead`, `sale_order`, `account_move` can be slow on databases with millions of rows. These fields should have indexes. Odoo core adds `email` indexes on many models, but `name` fields are typically not indexed. Adding a `pg_trgm` index on commonly searched `name` columns can significantly improve performance:

```sql
CREATE INDEX IF NOT EXISTS res_partner_name_trgm_idx ON res_partner USING gin (name gin_trgm_ops);
```

### Transient Model Cleanup

With `_transient_max_count = 0` and `_transient_max_hours = 24`, wizard records live for 24 hours. High-volume usage can accumulate many transient records in the database. The ORM's cleanup cron removes these, but in very high throughput scenarios, `_transient_max_hours` could be lowered.

### No Result Limit

`action_lookup()` has no `LIMIT` clause. A data subject with an extremely common email (e.g., `test@gmail.com`) could return thousands of lines, making the list view slow. There is no built-in pagination at the wizard level.

---

## GDPR Compliance Notes

This module supports GDPR Articles 17 (Right to Erasure / "Right to be Forgotten") and 18 (Right to Restriction of Processing):

| GDPR Article | Mechanism | Details |
|-------------|-----------|---------|
| Article 17 | `action_unlink()` per line | Permanently deletes records linked to the data subject. |
| Article 18 | `_onchange_is_active()` | Toggling `is_active = False` archives records, restricting processing without deletion. |
| Data minimization | `privacy.log` only stores anonymized identifiers | The audit log itself is GDPR-compliant. |
| Audit trail | Every action recorded with operator ID, timestamp, record description | Full accountability for all archive/unlink operations. |
| Field-level data | `records_description` shows only record counts and IDs, not field values | Privacy officer cannot see personal data values in the log. |

---

## Edge Cases

1. **Email-only or name-only lookup:** Both fields are required (`required=True`). Passing one without the other raises a validation error at form level before `_get_query()` is reached. This is intentional to reduce false-positive matches on common names.

2. **Invalid email format:** `tools.email_normalize()` returns `False` for malformed addresses. `action_lookup()` raises `UserError` with the message `'Invalid email address "%s"'`. The test `test_wizard_lookup_with_invalid_email` verifies this.

3. **Records deleted externally after lookup:** When a line's `res_id` points to a record deleted by another process, `_compute_res_name()` calls `record.exists()` which returns `False`. The name falls back to `{model.name}/{res_id}` so the line is still visible but cannot be opened. `_compute_resource_ref()` also handles this — `check_access('read')` on a deleted record raises, so `resource_ref` is `None` and the Open Record button is hidden.

4. **Indirect reference cascade:** `test_wizard_indirect_reference_cascade` creates a `res.partner.bank` record linked to the partner. Because `res.partner.bank` has `ondelete='cascade'` on its `partner_id` field, it is excluded from the search (the `ondelete != 'cascade'` guard in `_get_query()`). Deleting the partner would automatically delete the bank record, so listing it separately would be redundant.

5. **Duplicate email across multiple partners:** The SQL query and ORM search both return all matching records. The wizard line list will show all of them. Each line can be independently archived or deleted. The privacy log will record all actions.

6. **Self-lookup:** If the operator (privacy officer) is themselves the data subject they are looking up, they can still use the wizard. Archiving or deleting their own partner record may lock them out of the system — this is an organizational policy decision, not a technical guard.

7. **Log uniqueness:** There is **no database-level uniqueness constraint** on `privacy.log` for a given data subject. Running the wizard twice for the same person creates two log entries (both with anonymized identifiers). This may be desirable for audit purposes (each session timestamped separately).

8. **Non-char `_rec_name` fields:** In `_get_query()`, name search on a model is only performed if `model._rec_name` is stored, of type `char`, and not translated. Models that use `display_name` as their record name or have non-stored `_rec_name` will not have a name-based search applied. Only email-based search applies to such models.

---

## Version Change: Odoo 18 to 19

In Odoo 17 and earlier, the privacy lookup module used the old XML workflow engine and stored references in a `privacy.lookup` + `privacy.lookup.found` model pair. The Odoo 18/19 architecture consolidated this into the wizard-based approach with:

- **`privacy.lookup.wizard`** replaces the old `privacy.lookup` as the transient session holder.
- **`privacy.lookup.wizard.line`** replaces the old `privacy.lookup.found` as the per-record line model.
- **`privacy.log`** replaces an older log model with full anonymization built into `create()`.
- The raw SQL query using `SQL` (safe query builder) was introduced or significantly enhanced in this period, replacing fragile string formatting.
- The blacklist approach (`_get_query_models_blacklist()`) replaced an older inclusion-based approach.

The old models (`privacy.lookup`, `privacy.lookup.found`) no longer exist in Odoo 18+.

---

## See Also

- [Modules/mail](Modules/mail.md) - Email functionality, required dependency
- [Core/API](Core/API.md) - Cron jobs and scheduled actions
- [Patterns/Security Patterns](odoo-18/Patterns/Security Patterns.md) - ACL and record rules
- [Modules/res.partner](Modules/res.partner.md) - Partner model, the primary identity anchor
