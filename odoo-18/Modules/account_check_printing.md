---
Module: account_check_printing
Version: 18.0.0
Type: addon
Tags: #odoo18 #account #check #payment #printing
---

## Overview

Enables check printing for outgoing payments via bank journals. Supports both pre-numbered (manual sequencing) and auto-numbered check workflows. Renders check PDF reports with optional multi-stub pages showing paid invoices.

**Depends:** `account`

**Key Behavior:** Check payments are linked to a journal-level `ir.sequence` for numbering. The `_auto_init` hook creates the `check_number` column via raw SQL to avoid MemoryError on large databases. Unique constraint enforced via raw SQL across journal and check number.

---

## Models

### `account.payment` (Inherited)

**Inherited from:** `account.payment`

| Field | Type | Note |
|-------|------|------|
| `check_amount_in_words` | Char (compute) | Amount spelled out in words via `currency_id.amount_to_text` |
| `check_manual_sequencing` | Boolean (related) | From `journal_id` |
| `check_number` | Char (compute/inverse) | Stored in DB; computed from sequence or set manually |
| `show_check_number` | Boolean (compute) | True for `check_printing` method with a number |

| Method | Returns | Note |
|--------|---------|------|
| `_auto_init()` | — | Creates `check_number` column via raw SQL (MemoryError avoidance) |
| `_constrains_check_number()` | — | Digits-only validation |
| `_constrains_check_number_unique()` | — | Raw SQL query: no duplicate check numbers per journal |
| `_compute_check_amount_in_words()` | — | Delegates to `currency_id.amount_to_text` |
| `_compute_check_number()` | — | Reads from sequence if manual sequencing + check printing |
| `_inverse_check_number()` | — | Sets sequence padding from check number length |
| `_get_trigger_fields_to_synchronize()` | — | Adds `check_number` to synchronization fields |
| `_get_aml_default_display_name_list()` | — | Includes check number in AML display name |
| `action_post()` | — | Auto-assigns check number from sequence on post |
| `print_checks()` | — | Wizard flow: validates, asks for starting number if pre-printed, calls `do_print_checks` |
| `action_void_check()` | — | Draft → Cancel workflow for voiding |
| `do_print_checks()` | — | Validates layout, sets `is_sent=True`, returns report action |
| `_check_fill_line(amount_str)` | str | Pads check amount string to 200 chars with `*` |
| `_check_build_page_info(i, p)` | dict | Per-page check data: date, partner, amount, stub lines |
| `_check_get_pages()` | list | Builds all pages from stub pages |
| `_check_make_stub_pages()` | list | Decodes reconciliation, groups invoices by type, paginates |

### `account.journal` (Inherited)

**Inherited from:** `account.journal`

| Field | Type | Note |
|-------|------|------|
| `check_manual_sequencing` | Boolean | Default outbound method includes check |
| `check_sequence_id` | Many2one `ir.sequence` | Auto-created on journal creation |
| `check_next_number` | Char (compute/inverse) | Next check number from sequence |
| `bank_check_printing_layout` | Selection | Check layout reference |

| Method | Returns | Note |
|--------|---------|------|
| `_default_outbound_payment_methods()` | recordset | Adds `check_printing` method |
| `_get_check_printing_layouts()` | list | Returns non-disabled layout options |
| `_compute_check_next_number()` | — | Reads from sequence or defaults to 1 |
| `_inverse_check_next_number()` | — | Validates and writes to sequence; checks MAX_INT32 |
| `create(vals_list)` | — | Auto-creates check sequence for journals without one |
| `_create_check_sequence()` | — | Creates `ir.sequence` with `no_gap` implementation, padding 5 |
| `_get_journal_dashboard_data_batched()` | — | Adds `num_checks_to_print` count to dashboard |
| `action_checks_to_print()` | Action | Opens filtered payment list for checks to send |

### `account.payment.method` (Inherited)

**Inherited from:** `account.payment.method`

| Method | Returns | Note |
|--------|---------|------|
| `_get_payment_method_information()` | dict | Adds `'check_printing': {'mode': 'multi', 'type': ('bank',)}` |

### `res.company` (Inherited)

**Inherited from:** `res.company`

| Field | Type | Note |
|-------|------|------|
| `account_check_printing_layout` | Selection | Default check layout |
| `account_check_printing_date_label` | Boolean | Print date label on check |
| `account_check_printing_multi_stub` | Boolean | Multiple stub pages |
| `account_check_printing_margin_top` | Float | Top margin |
| `account_check_printing_margin_left` | Float | Left margin |
| `account_check_printing_margin_right` | Float | Right margin |

---

## Critical Notes

- **`_auto_init` Pattern:** Creating a stored computed field column via raw SQL `create_column` is the standard Odoo pattern to avoid MemoryError on large tables — the field definition in Python would normally trigger `SELECT *` on all rows.
- **Multi-Stub Pagination:** `_check_make_stub_pages` groups invoices into Bills and Refunds sections. When `multi_stub` is disabled and there are too many lines, stub is cropped to `INV_LINES_PER_STUB - 1` with an ellipsis.
- **Stub Without Reconciliation:** If `move_id` has no reconciled invoices, stub lines are computed by iterating invoices and applying `remaining` amount.
- **Pre-Printed Check Wizard:** `print_checks` detects last used check number from DB and prompts for starting number.
- **MAX_INT32 Constraint:** Check numbers exceeding 2,147,483,647 are rejected in `_inverse_check_next_number`.
