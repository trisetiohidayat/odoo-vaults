---
Module: privacy_lookup
Version: 18.0.0
Type: addon
Tags: #odoo18 #privacy_lookup #gdpr #compliance
---

## Overview

`privacy_lookup` provides GDPR/privacy compliance tooling for Odoo. It enables searching all records in the database that reference a specific person (by email or name), displaying results in a wizard, and optionally archiving or deleting matching records. Logs all lookups with anonymized PII (GDPR-safe storage). Works by executing raw SQL queries against the entire database.

## Models

### privacy.log
**Inheritance:** Standalone model (`_name = 'privacy.log'`)

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| date | Datetime | Lookup execution timestamp (required, default=now) |
| anonymized_name | Char | Anonymized name (first letter + asterisks per word, e.g., "J*** S***") |
| anonymized_email | Char | Anonymized email (same pattern for user part, domains preserved for gmail/hotmail/yahoo) |
| user_id | Many2one | `res.users` — who performed the lookup (required, default=current user) |
| execution_details | Text | Concatenated per-line execution details from wizard lines |
| records_description | Text | Human-readable summary of found records grouped by model, with record IDs |
| additional_note | Text | Free-text notes |

**Methods:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| create | vals_list | recordset | **Overridden:** Automatically anonymizes `anonymized_name` and `anonymized_email` via `_anonymize_name()` / `_anonymize_email()` before write |
| _anonymize_name | label | str | Splits on spaces, for each word keeps first character + asterisks: `'John Doe' → 'J*** D***'`. If '@' in label, delegates to `_anonymize_email()` |
| _anonymize_email | label | str | Splits `user@domain`. User part: first char + asterisks per dot-separated segment. Domain: same but preserves TLD. Special-case: gmail.com, hotmail.com, yahoo.com domains are preserved as-is (common enough to not reveal info) |

### res.partner (extends base)
**Inheritance:** `res.partner` (classic `_inherit`)

**Methods:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| action_privacy_lookup | self | dict | Opens `privacy.lookup.wizard` with `context` pre-filled with current partner's `email` and `name`. Uses `default_email`/`default_name` context keys |

### privacy.lookup.wizard
**Inheritance:** Standalone transient model (`_name = 'privacy.lookup.wizard'`)

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| name | Char | Name to search (required) |
| email | Char | Email to search (required) |
| line_ids | One2many | `privacy.lookup.wizard.line` records |
| execution_details | Text | Computed: concatenation of all line execution details (stored, auto-posts to privacy.log) |
| log_id | Many2one | `privacy.log` — the log entry created/updated from this lookup |
| records_description | Text | Computed: grouped summary of found records by model |
| line_count | Integer | Computed count of result lines |

**Methods:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _get_query_models_blacklist | self | list | Returns list of model names to exclude from search: `res.partner`, `res.users`, `mail.notification`, `mail.followers`, `discuss.channel.member` (cascade-deleted), `mail.message` (direct messages handled separately) |
| _get_query | self | SQL | Builds a recursive SQL query using `WITH indirect_references` CTE: (1) Finds partners/users matching email_normalized or name ilike. (2) Searches mail.message for messages by those partners. (3) For each auto model, adds a UNION ALL with conditions for email/name fields (normalized for exact match, ilike for partial) and indirect references via `partner_id` Many2one fields (non-cascade). Handles table-specific `active` field detection |
| action_lookup | self | dict | Executes `_get_query()`, fetches results, populates `line_ids`. Calls `action_open_lines()` |
| _post_log | self | None | Creates or updates `privacy.log` entry with anonymized name/email, execution_details, and records_description |
| _compute_execution_details | self | None | Computes `execution_details` from line details, triggers `_post_log()` |
| _compute_records_description | self | None | Computes `records_description` grouping results by model with counts and IDs. Non-admin users see only model names, not technical model names |
| action_open_lines | self | dict | Returns action to open the wizard line tree view |

### privacy.lookup.wizard.line
**Inheritance:** Standalone transient model (`_name = 'privacy.lookup.wizard.line'`)

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| wizard_id | Many2one | Parent wizard |
| res_id | Integer | Resource ID (required) |
| res_name | Char | Resource display name (computed, stored) |
| res_model_id | Many2one | `ir.model` record (cascade delete) |
| res_model | Char | Related model name (from `res_model_id.model`, stored, readonly) |
| resource_ref | Reference | Browsable record reference (computed, with inverse setter) |
| has_active | Boolean | Computed: True if the model has an `active` field |
| is_active | Boolean | Current active state of the record |
| is_unlinked | Boolean | True if record was deleted during this session |
| execution_details | Char | Single-line execution log (e.g., "Archived account.move #123") |

**Methods:**

| Method | Parameters | Returns | Description |
|--------|------------|---------|-------------|
| _selection_target_model | _model | list | Returns all ir.model records as selection options for the Reference field |
| _compute_resource_ref | self | None | Computes browsable record reference. Tries `check_access('read')` first; if access denied, sets to None |
| _set_resource_ref | self | None | Inverse of resource_ref: syncs back res_id |
| _compute_has_active | self | None | Checks if model has an `active` field |
| _compute_res_name | self | None | Fetches `display_name` of the target record via sudo, falls back to `model_name/ID` |
| _onchange_is_active | self | None | Archives/unarchives the target record. Sets `execution_details = "{Archived|Restored} {model} #{id}"` |
| action_unlink | self | None | Deletes the target record. Sets `is_unlinked=True`, `execution_details = "Deleted {model} #{id}"` |
| action_archive_all | self | None | Archives all active lines in the wizard |
| action_unlink_all | self | None | Unlinks all non-deleted lines |
| action_open_record | self | dict | Returns form action to open the specific record |

## Security / Data

**Security:** `ir.model.access.csv` — All three models (`privacy.lookup.wizard`, `privacy.lookup.wizard.line`, `privacy.log`) require `base.group_system`. Only administrators can access privacy lookup tools.

**Data:** None.

## Critical Notes

- **Raw SQL queries:** `_get_query()` uses raw SQL (`self.env.cr.execute`) with `SQL` objects for injection-safe query construction. Searches ALL auto models (non-transient, non-abstract).
- **Anonymized logging:** All PII in the log is anonymized before storage — GDPR compliance for audit trails.
- **Indirect reference search:** Finds records linked to a partner via `partner_id` Many2one (excluding cascade-delete fields which would clean up automatically).
- **Email normalization:** Uses `tools.email_normalized()` for exact email matching. Name matching uses `ilike` for partial matching.
- **Blacklisted models:** `res.partner`, `res.users`, cascade-deleted related records, and `mail.message` (direct messages handled separately in CTE) are excluded from indirect reference search.
- **Model-by-model iteration:** The query iterates over `self.env` — all available models — to build UNION ALL clauses dynamically for any installed module.
- **Access control on lines:** `_compute_resource_ref` catches access errors and sets reference to None, preventing crashes on records hidden by ir.rule.
- **v17→v18:** No specific changes. Privacy GDPR tooling unchanged.
