---
Module: account (Reconciliation & Bank Statements)
Version: Odoo 18
Type: Extension
Tags: #odoo, #odoo18, #accounting, #reconciliation, #bank-statements, #payments
---

# Reconciliation Models & Bank Statement Handling

**Addon:** `account` | **Source:** `~/odoo/odoo18/odoo/addons/account/models/`
**Related Files:** `account_reconcile_model.py`, `account_bank_statement.py`, `account_bank_statement_line.py`, `account_journal.py`, `account_payment.py`

## Overview

This document covers the **bank reconciliation subsystem** within the `account` module:

1. **`account.reconcile.model`** — Templates/rules for automatic reconciliation and write-off generation
2. **`account.journal`** — Journal configuration including bank/cash journals
3. **`account.bank.statement`** — Bank statement container with balance validation
4. **`account.bank.statement.line`** — Individual imported bank transaction (inherits `account.move`)
5. **`account.payment`** — Payment transaction records

---

## `account.reconcile.model`

**File:** `models/account_reconcile_model.py`

Defines **reconciliation rules** used to automatically match bank statement lines to open invoices/payments, and to generate write-off journal entries.

### Model Hierarchy

```
account.reconcile.model
    ├── account.reconcile.model.line        (One2many) — write-off rules
    └── account.reconcile.model.partner.mapping  (One2many) — partner matching by regex
```

### `account.reconcile.model` Fields

| Field | Type | Description |
|-------|------|-------------|
| `active` | Boolean | Enable/disable this model (default True) |
| `name` | Char | Rule name (required, unique per company) |
| `sequence` | Integer | Priority order (default 10) |
| `company_id` | Many2one(`res.company`) | Rule scope (required, default: current company) |
| `rule_type` | Selection | `writeoff_button` / `writeoff_suggestion` / `invoice_matching` |
| `auto_reconcile` | Boolean | Auto-validate after matching |
| `to_check` | Boolean | Mark matched lines as "To Check" |
| `matching_order` | Selection | `old_first` / `new_first` — invoice matching order |
| `counterpart_type` | Selection | `general` / `sale` / `purchase` — type of counterpart journal entry |

#### Rule Types

| Value | Behavior |
|-------|----------|
| `writeoff_button` | Generates a write-off journal entry on user action |
| `writeoff_suggestion` | Shows write-off suggestion without forcing action |
| `invoice_matching` | Auto-matches statement lines to open invoices/bills |

#### Counterpart Types

| Value | Writes off to |
|-------|--------------|
| `general` | General journal entry |
| `sale` | Customer invoice journal |
| `purchase` | Vendor bill journal |

### Matching Conditions

| Field | Type | Description |
|-------|------|-------------|
| `match_text_location_label` | Boolean | Search in statement label for invoice reference (default True) |
| `match_text_location_note` | Boolean | Search in statement note |
| `match_text_location_reference` | Boolean | Search in statement reference |
| `match_journal_ids` | Many2many | Only apply this model in selected journals |
| `match_nature` | Selection | `amount_received` / `amount_paid` / `both` (default `both`) |
| `match_amount` | Selection | `lower` / `greater` / `between` — amount filter |
| `match_amount_min` | Float | Minimum amount threshold |
| `match_amount_max` | Float | Maximum amount threshold |
| `match_label` | Selection | `contains` / `not_contains` / `match_regex` on label |
| `match_label_param` | Char | String/regex parameter for label match |
| `match_note` | Selection | `contains` / `not_contains` / `match_regex` on note |
| `match_note_param` | Char | Parameter for note match |
| `match_transaction_type` | Selection | `contains` / `not_contains` / `match_regex` on transaction type |
| `match_transaction_type_param` | Char | Parameter for transaction type match |
| `match_same_currency` | Boolean | Only match lines with same currency (default True) |
| `allow_payment_tolerance` | Boolean | Accept underpayment/overpayment within tolerance (default True) |
| `payment_tolerance_param` | Float | Gap amount/percentage (computed 0-100%) |
| `payment_tolerance_type` | Selection | `percentage` / `fixed_amount` |
| `match_partner` | Boolean | Only apply when partner is set |
| `match_partner_ids` | Many2many(`res.partner`) | Only apply for specific partners |
| `match_partner_category_ids` | Many2many(`res.partner.category`) | Only apply for partner categories |
| `past_months_limit` | Integer | How many months back to search invoices (default 18) |
| `decimal_separator` | Char | Decimal separator for regex-based amount extraction (from user's lang) |
| `show_decimal_separator` | Boolean | Computed: show separator field when any line uses `regex` amount type |

### Write-Off Configuration

| Field | Type | Description |
|-------|------|-------------|
| `line_ids` | One2many(`account.reconcile.model.line`) | Write-off line definitions |

### Statistics

| Field | Type | Description |
|-------|------|-------------|
| `number_entries` | Integer | Count of journal entries created using this model |

### Key Methods

```python
def action_reconcile_stat(self):
    # Returns an action to view all journal entries created by this model
    # Queries account_move_line where reconcile_model_id = self.id

def _compute_number_entries(self):
    # _read_group on account.move.line grouped by reconcile_model_id

@api.constrains('allow_payment_tolerance', 'payment_tolerance_param', 'payment_tolerance_type')
def _check_payment_tolerance_param(self):
    # percentage: must be 0-100
    # fixed_amount: must be >= 0
```

---

## `account.reconcile.model.line`

**File:** `models/account_reconcile_model.py`

Defines individual write-off journal entry lines for a reconciliation model. Inherits `analytic.mixin` for automatic analytic distribution on write-offs.

```python
class AccountReconcileModelLine(models.Model):
    _name = 'account.reconcile.model.line'
    _inherit = 'analytic.mixin'
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `model_id` | Many2one(`account.reconcile.model`) | Parent reconciliation model (readonly, cascade delete) |
| `sequence` | Integer | Line order (default 10) |
| `account_id` | Many2one(`account.account`) | Destination account (required, ondelete cascade) |
| `journal_id` | Many2one(`account.journal`) | Journal for this line (auto-filtered to counterpart_type) |
| `label` | Char | Journal item label (translateable) |
| `amount_type` | Selection | `fixed` / `percentage` / `percentage_st_line` / `regex` |
| `amount_string` | Char | Raw amount input (e.g., "100" or `([\d,]+)` for regex) |
| `amount` | Float | Parsed float amount (computed from amount_string) |
| `force_tax_included` | Boolean | Force tax price included |
| `show_force_tax_included` | Boolean | Computed: show button only when exactly one tax selected |
| `tax_ids` | Many2many(`account.tax`) | Taxes to apply |

### Amount Types

| Value | Meaning | Example |
|-------|---------|---------|
| `fixed` | Fixed amount (sign determines debit/credit) | `-50.00` = debit 50 |
| `percentage` | Percentage of the **residual balance** | `100` = write off full residual |
| `percentage_st_line` | Percentage of the **statement line amount** | `1.5` = 1.5% of statement |
| `regex` | Extract amount from statement label using regex | `([\d,]+)` extracts digits |

### Constraints

```python
@api.constrains('amount_string')
def _validate_amount(self):
    # fixed: amount must not be 0
    # percentage_st_line: amount must not be 0
    # percentage: amount must not be 0
    # regex: must compile without error
```

### Compute Methods

```python
@api.depends('amount_string')
def _compute_float_amount(self):
    # Parses amount_string to float; 0 on ValueError

@api.depends('rule_type', 'model_id.counterpart_type')
def _compute_amount_type(self):
    # writeoff_button + sale/purchase: default 'percentage_st_line'
    # others: default 'percentage'

@api.depends('model_id.counterpart_type', 'account_id', 'company_id')
def _compute_tax_ids(self):
    # For sale/purchase writeoff_button: auto-suggest taxes from account or company defaults
    # Filters tax_ids to match counterpart_type

@api.onchange('tax_ids')
def _onchange_tax_ids(self):
    # Multiple taxes → force_tax_included = False
```

---

## `account.reconcile.model.partner.mapping`

**File:** `models/account_reconcile_model.py`

Matches a partner to statement lines based on regex patterns in the label or narration.

```python
class AccountReconcileModelPartnerMapping(models.Model):
    _name = 'account.reconcile.model.partner.mapping'
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `model_id` | Many2one(`account.reconcile.model`) | Parent model (readonly, cascade) |
| `partner_id` | Many2one(`res.partner`) | Partner to assign (required) |
| `payment_ref_regex` | Char | Regex pattern to find in statement label |
| `narration_regex` | Char | Regex pattern to find in statement note |

### Constraint

```python
@api.constrains('narration_regex', 'payment_ref_regex')
def validate_regex(self):
    # Must set at least one regex
    # Both regexes must compile without error
```

---

## `account.bank.statement`

**File:** `models/account_bank_statement.py`

A **statement** is a container grouping related bank statement lines, with validated starting/ending balances.

```python
class AccountBankStatement(models.Model):
    _name = "account.bank.statement"
    _order = "first_line_index desc"
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Reference (computed from journal code + date, stored) |
| `reference` | Char | External reference (imported file name, online sync ID) |
| `date` | Date | Date of first posted line (computed+stored from lines) |
| `first_line_index` | Char | Internal index of the first line (sorting anchor) |
| `balance_start` | Monetary | Starting balance (computed from previous statement) |
| `balance_end` | Monetary | Computed ending balance (start + posted line sums) |
| `balance_end_real` | Monetary | Bank-reported ending balance (user input) |
| `company_id` | Many2one | Related from journal.company_id |
| `currency_id` | Many2one | Journal currency or company currency |
| `journal_id` | Many2one | Bank/cash journal (computed from lines) |
| `line_ids` | One2many | Statement lines in this statement |
| `is_complete` | Boolean | Computed: posted lines sum matches ending balance |
| `is_valid` | Boolean | Computed+searchable: starting balance matches previous statement |
| `problem_description` | Text | Computed: explains why statement is incomplete/invalid |
| `attachment_ids` | Many2many | Supporting documents |

### Balance Computation Logic (L4)

```python
def _compute_balance_start(self):
    # Walks back: finds previous posted line with a statement
    # balance_start = prev_statement.balance_end_real
    # + sum of all posted lines between prev statement and this one
    # (corrects for multi-edit of lines already in another statement)

def _compute_balance_end(self):
    # balance_start + sum(posted_lines.amount)

def _compute_is_complete(self):
    # is_complete = (has posted lines) AND (balance_end == balance_end_real)

def _get_statement_validity(self):
    # Compare balance_start to previous statement's balance_end_real
    # Return True if equal (within currency decimal_places)
```

### Statement Validity SQL (L4)

```python
def _get_invalid_statement_ids(self):
    # LATERAL join finds previous statement per journal
    # WHERE ROUND(prev.balance_end_real, decimal_places) != ROUND(st.balance_start, decimal_places)
    # Returns IDs of invalid statements
```

### `default_get()` — Multi-Line Creation Context

Supports three creation scenarios:
1. **Split button:** Finds contiguous block ending at the split line, creates statement with all lines
2. **Single line edit:** Creates statement for one line
3. **Multi-edit:** Validates all selected lines are from the same journal and contiguous (no gaps), then creates statement

```python
active_ids, split_line_id, st_line_id = context.get(...)
```

### `create()` / `write()` — Attachment Handling

```python
def _check_attachments(self, container, values_list):
    # Context manager: records attachment_ids from Command.set/link
    # On yield complete: writes res_model=account.bank.statement on attachments
```

---

## `account.bank.statement.line`

**File:** `models/account_bank_statement_line.py`

An **individual bank transaction**. Uses `_inherits` from `account.move` — the line IS a journal entry. This is a core Odoo accounting design pattern: the statement line **is** an `account.move` with extra bank-specific fields.

```python
class AccountBankStatementLine(models.Model):
    _name = "account.bank.statement.line"
    _inherits = {'account.move': 'move_id'}
```

### Inherits from `account.move`

The line stores additional bank-specific fields; the core accounting data lives in `move_id`.

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `move_id` | Many2one(`account.move`) | The underlying journal entry (required, cascade delete) |
| `journal_id` | Many2one(`account.journal`) | Inherited+related+stored+precompute from move_id |
| `company_id` | Many2one | Inherited+related+stored+precompute from move_id |
| `statement_id` | Many2one(`account.bank.statement`) | Parent statement |
| `payment_ids` | Many2many(`account.payment`) | Auto-generated payments during reconciliation |
| `sequence` | Integer | Reversed display order (default 1) |
| `partner_id` | Many2one(`res.partner`) | Detected/assigned partner (restrict delete) |
| `account_number` | Char | Bank account number (before partner bank creation) |
| `partner_name` | Char | Third-party name when partner not yet in DB |
| `transaction_type` | Char | Transaction type from electronic format |
| `payment_ref` | Char | Statement label |
| `currency_id` | Many2one | Journal currency |
| `amount` | Monetary | Transaction amount in journal currency |
| `running_balance` | Monetary | Computed cumulative balance from last statement anchor |
| `foreign_currency_id` | Many2one | Optional other currency |
| `amount_currency` | Monetary | Amount in foreign currency |
| `amount_residual` | Float | Amount left to reconcile (technical, stored) |
| `internal_index` | Char | Composite sort key: `{date}{MAXINT-seq}{id}` (stored, indexed) |
| `is_reconciled` | Boolean | All lines fully matched (computed+stored) |
| `statement_complete` | Boolean | Related from statement_id |
| `statement_valid` | Boolean | Related from statement_id |
| `statement_balance_end_real` | Monetary | Related from statement |
| `statement_name` | Char | Related from statement |
| `transaction_details` | Json | Raw details from electronic bank feed (readonly) |

### `internal_index` — Composite Sort Key (L4)

```python
def _compute_internal_index(self):
    # Format: YYYYMMDD + (MAXINT - sequence):10 + id:10
    # Example: "20240115149999999950000000042"
    # MAXINT = 2147483647 (asserted to be int4 column)
    # Enables: ordering by index = chronological order (accounting for sequence/id ties)
    # Allows finding "all lines before this line" with simple string comparison
```

### Running Balance Compute (L4)

```python
def _compute_running_balance(self):
    # 1. Find last statement's balance_start as anchor
    # 2. Raw SQL query walks all lines from anchor to max_index
    # 3. When encountering a statement's first_line_index: reset to that statement's balance_start
    # 4. Running balance += amount for each posted line
    # 5. Skips draft/canceled lines (still shows same balance as prior)
```

### `is_reconciled` / `amount_residual` Compute (L4)

```python
def _compute_is_reconciled(self):
    liquidity, suspense, other = st_line._seek_for_lines()
    if not checked:
        amount_residual = -amount_currency (if foreign) else -amount
    elif suspense.account_id.reconcile:
        amount_residual = sum(suspense.amount_residual_currency)
    else:
        amount_residual = sum(suspense.amount_currency)
    is_reconciled = (suspense and currency.is_zero(amount_residual)) or currency.is_zero(amount)
```

### `_seek_for_lines()` Helper

```python
def _seek_for_lines(self):
    # Dispatches move line_ids into:
    # liquidity_lines: where account_id == journal.default_account_id
    # suspense_lines: where account_id == journal.suspense_account_id
    # other_lines: everything else
    # Fallback: liquidity = lines with account_type in (asset_cash, liability_credit_card)
```

### Create — Auto-Posting

```python
@api.model_create_multi
def create(self, vals_list):
    # For each line:
    # - Inherits journal_id from statement if not set
    # - Prevents foreign_currency_id == journal_currency
    # - Forces move_type = 'entry'
    # - Pops counterpart_account_id for suspense override
    # - Sets amount = 0 if not provided
    # Creates move via super(), then adds line_ids via _prepare_move_line_default_vals
    # Auto-posts via move_id.action_post() — no draft state for statements
```

### Reconciliation Undo

```python
def action_undo_reconciliation(self):
    # 1. remove_move_reconcile() on all line_ids
    # 2. Unlink auto-generated payments
    # 3. Reset move lines: delete all lines, recreate from _prepare_move_line_default_vals
    # 4. Set checked = True (keeps current amount)
```

### Synchronization with `account.move` (L4)

```python
def _synchronize_from_moves(self, changed_fields):
    # When move is edited externally, resync statement line fields
    # Validates: exactly 1 liquidity line, 0 or 1 suspense line
    # Updates: payment_ref, partner_id, amount, amount_currency, foreign_currency_id

def _synchronize_to_moves(self, changed_fields):
    # When statement line is edited, update the underlying move
    # Rebuilds liquidity and suspense lines via _prepare_move_line_default_vals
    # Other lines are removed
```

### Constraints

```python
@api.constrains('amount', 'amount_currency', 'currency_id', 'foreign_currency_id', 'journal_id')
def _check_amounts_currencies(self):
    # foreign_currency != journal_currency
    # If foreign_currency set → amount_currency must be set
    # If amount_currency set → foreign_currency must be set
```

---

## `account.journal`

**File:** `models/account_journal.py`

### `account.journal.group`

```python
class AccountJournalGroup(models.Model):
    _name = 'account.journal.group'
    # Ledger filter grouping for reporting
    # excluded_journal_ids: journals hidden from this group
```

### `account.journal` Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Journal name (required, translateable) |
| `code` | Char | Short code (max 5 chars, unique per company, computed from type) |
| `type` | Selection | `sale` / `purchase` / `cash` / `bank` / `credit` / `general` |
| `active` | Boolean | Archive without deleting |
| `default_account_id` | Many2one | Default debit/credit account |
| `suspense_account_id` | Many2one | Suspense account for bank/cash (auto-set from company) |
| `restrict_mode_hash_table` | Boolean | Enable hash chain for posted entries |
| `currency_id` | Many2one | Override currency for bank/cash journals |
| `company_id` | Many2one | Owning company (required) |
| `profit_account_id` | Many2one | Cash difference profit account |
| `loss_account_id` | Many2one | Cash difference loss account |
| `bank_account_id` | Many2one(`res.partner.bank`) | Linked bank account (bank journals) |
| `bank_statements_source` | Selection | `undefined` / online source (bank feeds) |
| `bank_acc_number` | Char | Related from bank_account_id.acc_number |
| `bank_id` | Many2one | Related from bank_account_id.bank_id |
| `alias_id` | Many2one | Email alias for incoming invoices |
| `invoice_reference_type` | Selection | `none` / `partner` / `invoice` |
| `invoice_reference_model` | Selection | `odoo` / `euro` / country-specific |
| `refund_sequence` | Boolean | Separate sequence for refunds |
| `payment_sequence` | Boolean | Separate sequence for payments |
| `sequence_override_regex` | Text | Complex sequence enforcement regex |
| `inbound_payment_method_line_ids` | One2many | Inbound payment method lines |
| `outbound_payment_method_line_ids` | One2many | Outbound payment method lines |
| `available_payment_method_ids` | Many2many | Computed: available payment methods |
| `selected_payment_method_codes` | Char | Computed: comma-separated method codes |
| `accounting_date` | Date | Computed: next accounting date |
| `display_alias_fields` | Boolean | Show alias config (based on alias domain) |
| `journal_group_ids` | Many2many | Journal groups this journal belongs to |
| `account_control_ids` | Many2many | Allowed accounts for this journal |

### Journal Types and Default Accounts

| Type | Default Account Type | Suspense Account |
|------|--------------------|--------------------|
| `sale` | `income%` | No |
| `purchase` | `expense%` | No |
| `bank` | `asset_cash` | Yes (company suspense) |
| `cash` | `asset_cash` | Yes (company suspense) |
| `credit` | `liability_credit_card` | Yes (company suspense) |
| `general` | Any except off_balance | No |

### Payment Method Lines

Journals define which **payment method lines** (inbound/outbound) they support. The `available_payment_method_ids` is computed respecting:
- **Unique** methods: only one journal per company
- **Electronic** methods: one journal per company per provider
- **Multi** methods: unlimited per journal

```python
@api.depends('type', 'currency_id')
def _compute_inbound_payment_method_line_ids(self):
    # Bank/cash/credit journals: auto-create Manual In payment method line

@api.depends('type', 'currency_id')
def _compute_outbound_payment_method_line_ids(self):
    # Bank/cash/credit journals: auto-create Manual Out payment method line
```

### Constraints

```python
@api.constrains('account_control_ids')
def _constrains_account_control_ids(self):
    # All existing journal items must use only allowed accounts

@api.constrains('type', 'bank_account_id')
def _check_bank_account(self):
    # Bank journal's bank account must belong to the company
    # Account holder must be the company's partner

@api.constrains('type', 'default_account_id')
def _check_type_default_account_id_type(self):
    # Sale/purchase journals cannot use receivable/payable accounts

@api.constrains('inbound_payment_method_line_ids', 'outbound_payment_method_line_ids')
def _check_payment_method_line_ids_multiplicity(self):
    # unique/electronic methods must not exceed one per company (or per company+provider)
```

### Suspense Account

```python
@api.depends('type', 'company_id')
def _compute_suspense_account_id(self):
    # Bank/cash/credit journals: use company.account_journal_suspense_account_id
    # Sale/purchase/general: no suspense
```

---

## `account.payment`

**File:** `models/account_payment.py`

Payments are tracked separately from journal entries. In Odoo 18, `account.payment` inherits from `mail.thread.main.attachment` and `mail.activity.mixin`.

### Payment States

```
draft → in_process → paid
                 ↘ rejected
                       ↘ canceled
```

| State | Meaning |
|-------|---------|
| `draft` | Initial state, not yet processed |
| `in_process` | Being processed (validation step) |
| `paid` | Successfully completed |
| `rejected` | Payment was rejected by provider |
| `canceled` | Payment was canceled |

### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Payment number (computed from journal sequence) |
| `date` | Date | Payment date |
| `move_id` | Many2one(`account.move`) | The underlying journal entry |
| `journal_id` | Many2one | Payment journal |
| `company_id` | Many2one | Company |
| `payment_type` | Selection | `inbound` / `outbound` |
| `partner_type` | Selection | `customer` / `supplier` |
| `amount` | Monetary | Payment amount |
| `currency_id` | Many2one | Payment currency |
| `destination_account_id` | Many2one | Counterpart receivable/payable account |
| `partner_id` | Many2one | Customer or supplier |
| `reconciled` | Boolean | Fully matched against invoices |
| `is_internal_transfer` | Boolean | Between own company accounts |
| `payment_method_line_id` | Many2one | Selected payment method |

---

## Reconciliation Flow

### Statement Line → Invoice Matching

1. Statement line imported via CAMT/COSTA/OFX or manual entry
2. System searches open invoices with:
   - Same partner
   - Matching reference (label/note/reference fields)
   - Amount within `payment_tolerance_param`
   - Within `past_months_limit` months
3. Matching order: `old_first` or `new_first` based on model setting
4. If `auto_reconcile`: reconciliation validated automatically
5. If `to_check`: reconciliation created but flagged for review

### Write-Off Generation

When reconciliation requires a residual write-off:
1. `account.reconcile.model.line` entries processed in sequence
2. For each line: amount computed based on `amount_type`
3. Tax applied if `tax_ids` set (respects `force_tax_included`)
4. Analytic distribution applied from line's `analytic_distribution` (via `analytic.mixin`)
5. Journal entry created linking to statement line via `reconcile_model_id`

---

## See Also

- [[Modules/Account]] — Full account module documentation
- [[Modules/Payment]] — Payment provider integration
- [[Core/Fields]] — Json field for distribution models
- [[Patterns/Workflow Patterns]] — State machine patterns in reconciliation
