---
Module: account_debit_note
Version: 18.0.0
Type: addon
Tags: #odoo18 #account #invoice #debit #correction
---

## Overview

Creates debit notes (opposite of credit notes) for posted invoices. Debit notes can also cancel credit notes. Links debit notes to their originating invoice via `debit_origin_id`, with optional line copying and journal override.

**Depends:** `account`

**Key Behavior:** Debit notes are invoice copies with a `debit_origin_id` pointing to the original. Journal sequence prefix is prefixed with 'D' for debit notes. Can copy lines from the original invoice or create a blank debit note.

---

## Models

### `account.move` (Inherited)

**Inherited from:** `account.move`

| Field | Type | Note |
|-------|------|------|
| `debit_origin_id` | Many2one `account.move` | Original invoice that was debited; indexed btree_not_null |
| `debit_note_ids` | One2many `account.move` | Debit notes created for this invoice |
| `debit_note_count` | Integer (compute) | Number of linked debit notes |

| Method | Returns | Note |
|--------|---------|------|
| `_compute_debit_count()` | — | Counts debit notes via `_read_group` |
| `action_view_debit_notes()` | Action | Opens list of this invoice's debit notes |
| `action_debit_note()` | Action | Opens debit note wizard |
| `_get_last_sequence_domain(relaxed)` | tuple | Adds `debit_sequence` filter for journal sequence lookup |
| `_get_starting_sequence()` | str | Prepends `'D'` to sequence for debit notes |
| `_get_copy_message_content(default)` | str | Custom message for debit note creation |

### `account.journal` (Inherited)

**Inherited from:** `account.journal`

| Field | Type | Note |
|-------|------|------|
| `debit_sequence` | Boolean (compute) | True for journals where sequence differs for debit notes |

### `account.debit.note` (Transient Wizard)

**Model:** `account.debit.note`
**Type:** Transient model

| Field | Type | Note |
|-------|------|------|
| `move_ids` | Many2many `account.move` | Posted invoices to debit |
| `date` | Date | Debit note date (default: today) |
| `reason` | Char | Optional reason/correction description |
| `journal_id` | Many2one `account.journal` | Override journal (optional) |
| `copy_lines` | Boolean | Copy invoice lines to debit note |
| `move_type` | Char (compute) | Single type if all moves share same type |
| `journal_type` | Char (compute) | `'purchase'` or `'sale'` based on move type |
| `country_code` | Char (related) | From `move_ids.company_id.country_id.code` |

| Method | Returns | Note |
|--------|---------|------|
| `default_get(fields)` | dict | Validates: moves must be posted, not already debited, and valid invoice types |
| `_compute_from_moves()` | — | Sets `move_type` if all moves have the same type |
| `_compute_journal_type()` | — | Sets to `'purchase'` for `in_*` moves, `'sale'` otherwise |
| `_prepare_default_values(move)` | dict | Builds copy vals: `ref`, `date`, `journal_id`, `debit_origin_id`, `move_type`; skips lines if `copy_lines=False` or source is a refund |
| `create_debit()` | Action | Creates debit note copies; returns action to open result(s) |
