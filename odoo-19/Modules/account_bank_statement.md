# Account Bank Statement (`account_bank_statement`)

> **Module Classification:** Core Accounting (merged into `account` in Odoo 18+; Enterprise-only import variants live under `account_bank_statement_import` EE module)
> **Odoo 19 Location:** `/odoo/addons/account/models/account_bank_statement.py` and `account_bank_statement_line.py`
> **EE Variant:** `account_bank_statement_import`, `account_bank_statement_import_camt`, `account_bank_statement_import_ofx`, `account_bank_statement_import_qif`, `account_bank_statement_import_csv`, `account_bank_statement_extract`

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Model: `account.bank.statement`](#2-model-accountbankstatement)
3. [Model: `account.bank.statement.line`](#3-model-accountbankstatementline)
4. [Model: `account.journal` (Bank Statement Extensions)](#4-model-accountjournal-bank-statement-extensions)
5. [Computed Fields Deep Dive](#5-computed-fields-deep-dive)
6. [Balance Computation & Integrity Checks](#6-balance-computation--integrity-checks)
7. [Reconciliation Flow](#7-reconciliation-flow)
8. [Bidirectional Move–Statement Synchronization](#8-bidirectional-move-statement-synchronization)
9. [Multi-Currency Reconciliation](#9-multi-currency-reconciliation)
10. [Bank Statement Import (EE)](#10-bank-statement-import-ee)
11. [L3 Escalation: Edge Cases](#11-l3-escalation-edge-cases)
12. [L4 Escalation: Performance, Security & Historical Changes](#12-l4-escalation-performance-security--historical-changes)

---

## 1. Architecture Overview

### 1.1 From Standalone to Integrated (Odoo 16 → 17 → 18 → 19)

In Odoo 16 and earlier, `account_bank_statement` was a standalone module with its own table (`account_bank_statement`) and a separate `account_bank_statement_line` table. Starting with Odoo 17 and accelerating in Odoo 18, the architecture underwent a fundamental redesign:

| Aspect | Odoo 16 (Standalone) | Odoo 18 → 19 (Current) |
|--------|----------------------|------------------------|
| Statement lines table | `account_bankStatement` (parent) + `account_bank_statement_line` (child) | Only `account_bank_statement_line` + `account_bank_statement` as grouping only |
| Journal Entry creation | Manual or via `account.move.line` | Each line `_inherits` `account.move`; a journal entry is auto-created and auto-posted on line creation |
| Statement's role | Container with real balances | Virtual grouping container; balance computed from lines |
| Line states | `draft` / `open` / `done` | Inherits `account.move` states (`draft` / `posted`) |
| `balance_end_real` | User input only | Computed from `balance_end` by default, user can override |
| `running_balance` | Not available | New in Odoo 18+; computed from anchored statement balance |
| `internal_index` | Not available | New in Odoo 18+; composite sort key replacing date+sequence+id |
| `is_valid` / `is_complete` | Simple boolean checks | Full integrity validation with SQL window functions |
| `checked` field | Not available | New in Odoo 18+; marks manually verified moves |
| Bidirectional sync | Not present | `_synchronize_from_moves` / `_synchronize_to_moves` keep move and line in sync |

### 1.2 Delegation Inheritance Pattern

`account.bank.statement.line` uses `_inherits = {'account.move': 'move_id'}`:

```
account.bank.statement.line
    └── _inherits account.move
            └── account.move.line (the actual journal items)
```

This means:
- Every statement line **is-a** `account.move`; they share the same database row via `move_id` FK
- The `account.move` is automatically **posted** when a statement line is created (see `create()` method)
- Deleting a statement line cascades to its `account.move` (unless `company_id.restrictive_audit_trail` is set)
- Synchronization methods (`_synchronize_from_moves`, `_synchronize_to_moves`) keep both sides consistent
- The reverse relation `statement_line_ids` on `account.move` provides the back-reference

### 1.3 Key Indexes (Performance Critical)

```python
# On account.bank.statement:
_journal_id_date_desc_id_desc_idx = models.Index("(journal_id, date DESC, id DESC)")
_first_line_index_idx = models.Index("(journal_id, first_line_index)")

# On account.bank.statement.line:
_unreconciled_idx = models.Index("(journal_id, company_id, internal_index) WHERE is_reconciled IS NOT TRUE")
_orphan_idx = models.Index("(journal_id, company_id, internal_index) WHERE statement_id IS NULL")
_main_idx = models.Index("(journal_id, company_id, internal_index)")
_checked_idx = models.Index("(journal_id) WHERE (checked IS NOT TRUE)")  # On account.move
```

These indexes underpin the entire sorting, filtering, running-balance calculation, and reconciliation query logic.

---

## 2. Model: `account.bank.statement`

### 2.1 Class Declaration

```python
class AccountBankStatement(models.Model):
    _name = 'account.bank.statement'
    _description = "Bank Statement"
    _order = "first_line_index desc"
    _check_company_auto = True
```

- **`_order = "first_line_index desc"`**: Statements sort by the internal index of their first line (descending = newest first). This is critical because the `date` field alone cannot serve as a sort key when multiple statements exist on the same day.
- **`_check_company_auto = True`**: Company-dependent validation is auto-applied.

### 2.2 Field Definitions

#### Identity Fields

| Field | Type | Store | Compute | Description |
|-------|------|-------|---------|-------------|
| `name` | Char | Yes (compute) | `_compute_name` | Auto-generated reference string. Format: `{journal.code} Statement {date}`. User-editable (`readonly=False`). Example: `BNK1 Statement 2024/01/15` |
| `reference` | Char | Yes | No | External reference — stores the filename, online sync ID, or import reference. Not auto-generated. `copy=False`. |
| `date` | Date | Yes (compute) | `_compute_date` | Date of the last posted line in the statement. `index=True`. Derived from `first_line_index` ordering, not simply max(date). |

#### Balance Fields

| Field | Type | Store | Compute | Description |
|-------|------|-------|---------|-------------|
| `balance_start` | Monetary | Yes (compute) | `_compute_balance_start` | Computed from the previous statement's `balance_end_real`. Is `readonly=False` so users can override when needed. |
| `balance_end` | Monetary | Yes (compute) | `_compute_balance_end` | Running total: `balance_start + SUM(posted line amounts)`. Cannot be directly set by user. |
| `balance_end_real` | Monetary | Yes (compute) | `_compute_balance_end_real` | By default equals `balance_end`. User sets this to declare the actual bank-reported ending balance. Mismatch with `balance_end` causes `is_complete = False`. |

#### Relational Fields

| Field | Type | Description |
|-------|------|-------------|
| `journal_id` | Many2one `account.journal` | Computed from `line_ids.journal_id`. The journal this statement belongs to. |
| `company_id` | Many2one `res.company` | Related to `journal_id.company_id`, stored. |
| `currency_id` | Many2one `res.currency` | Journal currency or company currency fallback. |
| `line_ids` | One2many `account.bank.statement.line` | All lines belonging to this statement. Inverse of `statement_id`. |
| `first_line_index` | Many2one `account.bank.statement.line` | Points to the first (oldest) line in the statement. Used for ordering and validity checks. |
| `attachment_ids` | Many2many `ir.attachment` | `bypass_search_access=True` so attachments bypass record rules. |

#### Integrity / Status Fields

| Field | Type | Store | Description |
|-------|------|-------|-------------|
| `is_complete` | Boolean | Yes (compute) | `True` when there is at least one posted line AND `balance_end == balance_end_real` (using `currency_id.compare_amounts`). |
| `is_valid` | Boolean | No (compute + search) | `True` when `balance_start` matches the previous statement's `balance_end_real`. First statement in a journal is always valid. Uses SQL window function for batch computation. |
| `journal_has_invalid_statements` | Boolean | No | Related to `journal_id.has_invalid_statements` (on `account.journal`). |
| `problem_description` | Text | No (compute) | Human-readable explanation of why `is_valid` or `is_complete` is `False`. |

### 2.3 `first_line_index` Field Detail

```python
first_line_index = fields.Char(
    comodel_name='account.bank.statement.line',
    compute='_compute_first_line_index', store=True,
)
```

This is the **anchor point** for statement ordering and validity. It holds the `internal_index` string of the oldest line. Because `internal_index` is a lexicographically sortable composite (`YYYYMMDD + reversed_sequence + id`), the first line by `internal_index` is the chronologically oldest.

```python
@api.depends('line_ids.internal_index', 'line_ids.state')
def _compute_first_line_index(self):
    for stmt in self:
        sorted_lines = stmt.line_ids.filtered("internal_index").sorted('internal_index')
        stmt.first_line_index = sorted_lines[:1].internal_index
```

### 2.4 `balance_end_real` Default Coupling

```python
@api.depends('balance_start')
def _compute_balance_end_real(self):
    for stmt in self:
        stmt.balance_end_real = stmt.balance_end
```

By default, `balance_end_real` equals `balance_end`. The user can override it to set the actual bank-reported ending balance. The coupling is broken once the user writes a different value. This design allows:
- New statements: `balance_end_real = balance_end` automatically
- User input: user sets `balance_end_real` to match bank statement
- Discrepancy detection: `is_complete = False` when they don't match

---

## 3. Model: `account.bank.statement.line`

### 3.1 Class Declaration

```python
class AccountBankStatementLine(models.Model):
    _name = 'account.bank.statement.line'
    _inherits = {'account.move': 'move_id'}
    _description = "Bank Statement Line"
    _order = "internal_index desc"
    _check_company_auto = True
```

### 3.2 Field Definitions

#### Inherited Fields (from `account.move` via `_inherits`)

| Field | Inheritance Mode | Notes |
|-------|-----------------|-------|
| `journal_id` | `related='move_id.journal_id'`, `store=True`, `readonly=False`, `inherited=True` | Overridden on statement line. Syncs back to move. |
| `company_id` | `related='move_id.company_id'`, `store=True`, `readonly=False`, `inherited=True` | Overridden on statement line. |
| `date` | Inherited from `account.move` | The transaction date. Part of `internal_index` computation. |
| `name` | Inherited from `account.move` | Move name (auto-set to `False` on creation to avoid clutter). |
| `state` | Inherited from `account.move` | `'draft'` or `'posted'`. Statement lines are auto-posted on creation. |
| `narration` | Inherited from `account.move` | Extended note. Written back from statement line `narration`. |
| `line_ids` | One2many from `account.move` | The actual journal items (liquidity + suspense + other). |
| `currency_id` | Inherited from `account.move` but overridden | Statement lines use journal's currency, not move's currency. |
| `partner_id` | Standard Many2one `res.partner` | Not from `account.move`; defined directly on statement line. |

> **FIXME note from Odoo developers** (in source): "Field having the same name in both tables are confusing (partner_id). We don't change it because: It's a mess to track/fix. Some fields here could be simplified when the onchanges will be gone in account.move. there should be a better way for syncing account_moves with bank transactions, payments, invoices, etc."

#### Business Fields

| Field | Type | Store | Description |
|-------|------|-------|-------------|
| `move_id` | Many2one `account.move` | Required, `readonly=True`, `ondelete='cascade'`, `bypass_search_access=True` | The journal entry this line inherits from. `bypass_search_access` avoids expensive ACL checks during move creation. |
| `statement_id` | Many2one `account.bank.statement` | `index=True` | Parent statement. Null for unreconciled "orphan" lines. |
| `payment_ids` | Many2many `account.payment` | `relation='account_payment_account_bank_statement_line_rel'` | Auto-generated payments created during reconciliation. |
| `sequence` | Integer | `default=1` | Sequence within the day. Higher = appears first (reversed order). Max value is `2147483647` (MAXINT) for oldest line. |
| `partner_id` | Many2one `res.partner` | Domain: `['|', ('parent_id', '=', False), ('is_company', '=', True)]` | Customer/vendor. `ondelete='restrict'`. |
| `account_number` | Char | No | Temporary storage for bank account number before bank account creation during reconciliation. |
| `partner_name` | Char | `index='btree_not_null'` | Third-party name when importing electronic formats where partner doesn't exist yet. |
| `transaction_type` | Char | No | Transaction type from electronic formats (CAMT, OFX, etc.). |
| `payment_ref` | Char | `index='trigram'` | Label / payment reference. Shown prominently in the UI. |
| `amount` | Monetary | No | Transaction amount in journal's currency. Positive = inbound, negative = outbound. |
| `currency_id` | Many2one `res.currency` | Yes (compute) | Journal's currency (journal's own currency or company currency). |
| `foreign_currency_id` | Many2one `res.currency` | No | Optional second currency for multi-currency entries. Must differ from `currency_id`. |
| `amount_currency` | Monetary | Yes (compute, readonly=False) | Amount in foreign currency. |
| `running_balance` | Monetary | No (compute) | Cumulative balance anchored to the nearest preceding statement's `balance_start`. Includes draft and canceled lines as anchor points. |
| `amount_residual` | Float | Yes (store) | Technical field: signed amount left to reconcile. Used to speed up reconciliation model application. |
| `internal_index` | Char | Yes (compute, store) | Composite sort key: `{YYYYMMDD}{MAXINT - sequence:0>10}{id:0>10}`. Enables fast lexicographic ordering. |
| `is_reconciled` | Boolean | Yes (store) | `True` when all journal items are fully reconciled (amount_residual is zero). |
| `statement_complete` | Boolean | No (related) | Shortcut to `statement_id.is_complete`. |
| `statement_valid` | Boolean | No (related) | Shortcut to `statement_id.is_valid`. |
| `statement_balance_end_real` | Monetary | No (related) | Shortcut to `statement_id.balance_end_real`. |
| `statement_name` | Char | No (related) | Shortcut to `statement_id.name`. |
| `transaction_details` | Json | `readonly=True` | Structured details from electronic import (CAMT parsing results, raw bank transaction metadata). Used by AI extraction and online sync modules. |
| `country_code` | Char | No (related) | `related='company_id.account_fiscal_country_id.code'`. |
| `unique_import_id` | Char | In EE only | SQL unique constraint. Ensures transactions can only be imported once. Only in `account_bank_statement_import` (EE). |

### 3.3 `account.move` Model Extension

```python
class AccountMove(models.Model):
    _inherit = 'account.move'

    statement_line_ids = fields.One2many('account.bank.statement.line', 'move_id', string='Statements')
```

The reverse relation on `account.move` enables:
- `move.statement_line_ids` to access all statement lines linked to a move (normally 1:1, but could be 0 or more in edge cases)
- `move._get_valid_journal_types()` to return `['bank', 'cash', 'credit']` when `statement_line_id` is set (see `account.move` model)
- `move._search_default_journal()` to use the statement's journal as the default

Also on `account.move.line`:
```python
statement_line_id = fields.Many2one(
    comodel_name='account.bank.statement.line',
    related='move_id.statement_line_id', store=True,
    bypass_search_access=True,
    index='btree_not_null',
)
statement_id = fields.Many2one(
    related='statement_line_id.statement_id', store=True,
    bypass_search_access=True,
    index='btree_not_null',
    copy=False,
)
```

The `statement_id` field on `account.move.line` is used throughout the ORM for filtering lines by statement — it is derived via the chain `move_line → move_id.statement_line_id → statement_line.statement_id`.

---

## 4. Model: `account.journal` (Bank Statement Extensions)

### 4.1 Bank-Specific Fields (from `account_journal.py`)

```python
# In AccountJournal (account/models/account_journal.py)

suspense_account_id = fields.Many2one(
    comodel_name='account.account', check_company=True, ondelete='restrict',
    readonly=False, store=True, compute='_compute_suspense_account_id',
    help="Bank statements transactions will be posted on the suspense account until "
         "the final reconciliation allowing finding the right account.",
    string='Suspense Account',
    domain="[('account_type', '=', 'asset_current')]",
)

bank_statements_source = fields.Selection(
    selection=_get_bank_statements_available_sources,
    string='Bank Feeds',
    default='undefined',
    help="Defines how the bank statements will be registered"
    # In CE: only ('undefined', 'Undefined Yet')
    # In EE: extended with ('file_import', 'File Import'), online sources, etc.
)

bank_account_id = fields.Many2one(
    'res.partner.bank',
    string="Bank Account",
    ondelete='restrict', copy=False,
    index='btree_not_null',
    check_company=True,
    domain="[('partner_id', '=', company_partner_id)]"
)

has_invalid_statements = fields.Boolean(
    compute='_compute_has_invalid_statements',
)
```

### 4.2 `_get_bank_statements_available_sources` Detail

```python
def __get_bank_statements_available_sources(self):
    return [('undefined', _('Undefined Yet'))]

def _get_bank_statements_available_sources(self):
    return self.__get_bank_statements_available_sources()
```

In **Community Edition**, only `undefined` is available. In **Enterprise Edition**, this method is extended (via `_inherit`) by modules like `account_online_synchronization`, `account_bank_statement_import_camt`, `account_bank_statement_import_ofx`, etc., to register additional import sources. The double-indirection method pattern (`__get_*` + `_get_*`) is intentional — it allows EE subclasses to override only `_get_*` without needing to know the internal name.

### 4.3 `has_invalid_statements` Computation

```python
def _compute_has_invalid_statements(self):
    journals_with_invalid_statements = self.env['account.bank.statement'].search([
        ('journal_id', 'in', self.ids),
        '|',
        ('is_valid', '=', False),
        ('is_complete', '=', False),
    ]).journal_id
    journals_with_invalid_statements.has_invalid_statements = True
    (self - journals_with_invalid_statements).has_invalid_statements = False
```

This is a critical UX feature: journals display a warning indicator in the dashboard when any of their statements are incomplete or invalid. The computation is a simple domain search with a two-pass write — first True then False — which is safe because Odoo's ORM batches the writes.

### 4.4 Suspense Account — The Temporary Holding Place

Every bank/cash journal must have a `suspense_account_id` configured. When a statement line is created, the counterpart journal item is posted to this account:

```
Debit  Bank Account (liquidity)     $100
Credit Suspense Account (counterpart)  $100
```

The suspense account bridges the gap between the bank transaction arriving and it being matched to the correct customer invoice, vendor bill, or other account. Until reconciliation, the transaction sits here.

---

## 5. Computed Fields Deep Dive

### 5.1 `internal_index` — The Lexicographic Sort Key

```python
@api.depends('date', 'sequence')
def _compute_internal_index(self):
    for st_line in self.filtered(lambda line: line._origin.id):
        st_line.internal_index = (
            f'{st_line.date.strftime("%Y%m%d")}'
            f'{MAXINT - st_line.sequence:0>10}'
            f'{st_line._origin.id:0>10}'
        )
```

**How it works:**
- `MAXINT = 2147483647` (the maximum 32-bit signed integer)
- `sequence = 1` → `(2147483647 - 1) = 2147483646` → `0002147483646`
- Lines with **higher sequence** get a **lower index suffix**, so they sort **first** (descending order: newest at top)
- `id` is appended as final tiebreaker to guarantee uniqueness
- Example: line with date=2024-01-15, sequence=5, id=123 → `2024011500021474836420000000123`

**Why this design:**
- `date` alone cannot serve as a sort key because multiple lines can have the same date
- A compound index on `(date, sequence, id)` on the `account.move` table is not feasible because `date` lives in `account.move` not in `account_bank_statement_line`
- Using `internal_index` as a **single-column char index** solves both problems and enables efficient `WHERE internal_index < X` queries for running balance calculations
- The `filtered("internal_index")` guards against lines created in the current transaction (not yet flushed to DB)

### 5.2 `running_balance` — Statement-Anchored Cumulative Balance

```python
def _compute_running_balance(self):
    record_by_id = {x.id: x for x in self}
    company2children = {
        company: self.env['res.company'].search([('id', 'child_of', company.id)])
        for company in self.journal_id.company_id
    }
    for journal in self.journal_id:
        # SQL query fetching all lines up to max_index for this journal
        # Uses account_bank_statement.first_line_index as anchor point
```

**Key insight:** The running balance is anchored to the nearest **preceding statement's `balance_start`** rather than starting from zero. This means:
- If you compute balance for lines within a statement, the anchor is the statement's own `balance_start`
- Lines without a statement (orphan lines) use the preceding statement's `balance_end_real`
- Draft and canceled lines are included as anchor points but their amounts are **not added** to the running balance (only posted lines contribute)
- Multi-company: children companies share the same running balance since they share the bank journal

### 5.3 `balance_start` — Cross-Statement Calculation

```python
@api.depends('create_date')  # Non-obvious: triggers on ANY write
def _compute_balance_start(self):
    for stmt in self.sorted(lambda x: x.first_line_index or '0'):
        journal_id = stmt.journal_id.id or stmt.line_ids.journal_id.id
        previous_line_with_statement = self.env['account.bank.statement.line'].search([
            ('internal_index', '<', stmt.first_line_index),
            ('journal_id', '=', journal_id),
            ('state', '=', 'posted'),
            ('statement_id', '!=', False),
        ], limit=1)
        balance_start = previous_line_with_statement.statement_id.balance_end_real
        # ... adds amounts of all posted lines between previous and current statement
```

**Critical behavior:** `balance_start` is recomputed whenever `create_date` changes (which happens on any write to the record). It incorporates:
1. Previous statement's `balance_end_real` as base
2. Sum of all posted lines between the previous and current statement's first line (handles multi-editing scenarios)

The `create_date` dependency (rather than `line_ids` or `balance_end_real`) means the ORM tracks any write as a trigger. This is deliberate — a statement's starting balance can be affected by any change anywhere in the journal.

### 5.4 `is_valid` — Batch SQL Validation

```python
def _get_invalid_statement_ids(self, all_statements=None):
    self.env.cr.execute(f"""
        WITH statements AS (
            SELECT st.id,
                   st.balance_start,
                   st.journal_id,
                   LAG(st.balance_end_real) OVER (
                       PARTITION BY st.journal_id
                       ORDER BY st.first_line_index
                   ) AS prev_balance_end_real,
                   currency.decimal_places
              FROM account_bank_statement st
         LEFT JOIN res_company co ON st.company_id = co.id
         LEFT JOIN account_journal j ON st.journal_id = j.id
         LEFT JOIN res_currency currency ON COALESCE(j.currency_id, co.currency_id) = currency.id
             WHERE st.first_line_index IS NOT NULL
        )
        SELECT id
          FROM statements
         WHERE prev_balance_end_real IS NOT NULL
           AND ROUND(prev_balance_end_real, decimal_places) != ROUND(balance_start, decimal_places)
    """, {...})
```

This uses PostgreSQL's `LAG()` window function to look at the **previous statement's** `balance_end_real` in a single pass. The rounding accounts for currency decimal places. The `flush_model()` calls before the query ensure computed values are in the DB.

---

## 6. Balance Computation & Integrity Checks

### 6.1 Balance Flow Diagram

```
previous_statement.balance_end_real
        │
        ▼
current_statement.balance_start  (user-editable override)
        │
        │  + SUM(posted_line.amount) for all lines in statement
        ▼
current_statement.balance_end  (computed)
        │
        │  (if user sets balance_end_real)
        ▼
current_statement.balance_end_real  (user sets this to match bank report)
        │
        ├──── is_complete = (balance_end == balance_end_real AND posted lines exist)
        │
        └──── is_valid = (balance_start == previous.balance_end_real OR first statement)
```

### 6.2 `is_complete` vs `is_valid`

| Property | `is_complete` | `is_valid` |
|----------|--------------|------------|
| **Type** | Internal integrity | External integrity |
| **Checks** | `SUM(lines) == (balance_end_real - balance_start)` | `balance_start == prev_statement.balance_end_real` |
| **First statement** | Can be incomplete if no lines | Always valid |
| **Computation** | ORM `compare_amounts` | SQL `LAG()` window function |
| **Use case** | Did all bank transactions get entered? | Is there a gap/missing statement? |

### 6.3 Statement Validity Chain

The validity of statements forms a chain:

```
Statement[0].balance_end_real
    └── Statement[1].balance_start  (must match)
            └── Statement[1].balance_end_real
                    └── Statement[2].balance_start  (must match)
```

`_get_statement_validity()` (used for single-record `is_valid` reads) and `_get_invalid_statement_ids()` (used for batch reads and searches) both use the same LAG-window pattern. The single-record path avoids the ORM-to-SQL boundary overhead for simple reads.

---

## 7. Reconciliation Flow

### 7.1 Line Creation → Journal Entry Auto-Post

When a `account.bank.statement.line` is created:

1. `create()` sets `move_type = 'entry'` and calls `super().create()`
2. `account.move` is created via `_inherits` delegation
3. `_prepare_move_line_default_vals()` generates two journal items:
   - **Liquidity line**: Debit/credit on `journal.default_account_id` (the bank account), amount = journal amount
   - **Counterpart line**: On `journal.suspense_account_id` (until reconciled)
4. `move_id.action_post()` is called — the journal entry is **immediately posted**
5. The line's `internal_index` is computed and stored

The `is_statement_line=True` context key (set in `default_get`, `new()`, and `create()`) signals to `account.move` that this is a bank/cash transaction so it should use `['bank', 'cash', 'credit']` as valid journal types instead of `['general']`.

### 7.2 `_seek_for_lines()` — Line Classification

```python
def _seek_for_lines(self):
    liquidity_lines = self.env['account.move.line']
    suspense_lines = self.env['account.move.line']
    other_lines = self.env['account.move.line']

    for line in self.move_id.line_ids:
        if line.account_id == self.journal_id.default_account_id:
            liquidity_lines += line
        elif line.account_id == self.journal_id.suspense_account_id:
            suspense_lines += line
        else:
            other_lines += line
    if not liquidity_lines:
        # Fallback: any line with account_type asset_cash or liability_credit_card
        liquidity_lines = self.move_id.line_ids.filtered(
            lambda l: l.account_id.account_type in ('asset_cash', 'liability_credit_card')
        )
        other_lines -= liquidity_lines
    return liquidity_lines, suspense_lines, other_lines
```

This is the **core helper** used by every reconciliation method to understand the structure of a statement line's journal entry. The fallback for `liquidity_lines` handles cases where the journal's default account has changed since the line was created.

### 7.3 `_get_default_amls_matching_domain()` — Reconciliation Suggestions

Used by the bank reconciliation widget to find candidate journal items to match against the statement line. The `allow_draft=True` parameter includes draft invoices/bills with partners for display (but not for auto-matching):

```python
def _get_default_amls_matching_domain(self, allow_draft=False):
    # base domain includes:
    # - display_type filter
    # - company_id in child companies
    # - reconciled = False
    # - account_id in reconcilable accounts
    # - Special OR: either (not receivable/payable) OR (no payment_id)
    # - statement_line_id != self.id  (don't suggest self)
    state_domain = [('parent_state', '=', 'posted')]
    if allow_draft:
        partnered_drafts_domain = [('parent_state', '=', 'draft'), ('partner_id', '!=', False)]
        state_domain = Domain.OR([state_domain, partnered_drafts_domain])
    return state_domain + [...]
```

### 7.4 `action_undo_reconciliation()`

```python
def action_undo_reconciliation(self):
    self.line_ids.remove_move_reconcile()
    self.payment_ids.unlink()
    for st_line in self:
        st_line.with_context(force_delete=True, skip_readonly_check=True).write({
            'checked': True,
            'line_ids': [Command.clear()] + [
                Command.create(line_vals) for line_vals in st_line._prepare_move_line_default_vals()],
        })
```

This method:
1. Removes all move line reconciliations
2. Deletes auto-generated payments
3. Resets the line to its original state (liquidity + suspense entries only)
4. `checked = True` marks it as manually verified — this is critical for the `is_reconciled` computation: a line with `checked=True` derives `amount_residual` from the suspense line's residual currency amount

### 7.5 `_find_or_create_bank_account()`

```python
def _find_or_create_bank_account(self):
    # Search across all companies (SQL unique constraint is per partner+account_number, not per company)
    bank_account = self.env['res.partner.bank'].sudo().with_context(active_test=False).search([
        ('acc_number', '=', self.account_number),
        ('partner_id', '=', self.partner_id.id),
    ])
    # Filter to current company at return time
    return bank_account.filtered(lambda x: x.company_id.id in (False, self.company_id.id)).sudo(False)
```

**Important notes:**
- The SQL unique constraint on `res.partner.bank` is per `(partner_id, acc_number)` — not per company. So `sudo()` and `active_test=False` are required to search across all companies without triggering company-filtered domain.
- If `account.skip_create_bank_account_on_reconcile` config parameter is set, the bank account is NOT auto-created.
- If the account number exists on another active partner, the method returns an empty recordset (prevents linking to wrong partner).

---

## 8. Bidirectional Move–Statement Synchronization

### 8.1 The Synchronization Contract

Because a statement line `_inherits` an `account.move`, two copies of the same data can diverge:
- Fields written on `account.bank.statement.line` (e.g., `amount`, `payment_ref`)
- Fields written on `account.move` directly (e.g., via the move form view)

Odoo solves this with a pair of synchronization methods that run in the `skip_account_move_synchronization` context to prevent infinite loops.

### 8.2 `_synchronize_to_moves()` — Statement Line Changes Push to Move

Called from `account.bank.statement.line.write()`. Triggers only when these fields change:

```python
def _synchronize_to_moves(self, changed_fields):
    if not any(field_name in changed_fields for field_name in (
        'payment_ref', 'amount', 'amount_currency',
        'foreign_currency_id', 'currency_id', 'partner_id',
    )):
        return
    for st_line in self.with_context(skip_account_move_synchronization=True):
        liquidity_lines, suspense_lines, other_lines = st_line._seek_for_lines()
        line_vals_list = st_line._prepare_move_line_default_vals()
        # Rebuild liquidity line
        line_ids_commands = [(1, liquidity_lines.id, line_vals_list[0])]
        # Rebuild or create suspense line
        if suspense_lines:
            line_ids_commands.append((1, suspense_lines.id, line_vals_list[1]))
        else:
            line_ids_commands.append((0, 0, line_vals_list[1]))
        # Delete all other lines (counterparts from reconciliation)
        for line in other_lines:
            line_ids_commands.append((2, line.id))
        # Update move-level fields
        st_line_vals = {
            'currency_id': (st_line.foreign_currency_id or journal_currency or company_currency).id,
            'line_ids': line_ids_commands,
        }
        if st_line.move_id.journal_id != journal:
            st_line_vals['journal_id'] = journal.id
        if st_line.move_id.partner_id != st_line.partner_id:
            st_line_vals['partner_id'] = st_line.partner_id.id
        st_line.move_id.with_context(skip_readonly_check=True).write(st_line_vals)
```

**Key behavior:** Every time the statement line is modified, the entire set of counterpart lines (from reconciliation) is deleted and rebuilt as liquidity + suspense only. This is the "reset to default state" behavior.

### 8.3 `_synchronize_from_moves()` — Move Changes Pull to Statement Line

Called from `account.move.write()` when `line_ids` change. Updates the statement line regarding its related account.move:

```python
def _synchronize_from_moves(self, changed_fields):
    if 'line_ids' in changed_fields:
        liquidity_lines, suspense_lines, other_lines = st_line._seek_for_lines()
        # Validates: exactly 1 liquidity line, max 1 suspense line
        if len(liquidity_lines) != 1:
            raise UserError("The journal entry must always have exactly one "
                            "journal item involving the bank/cash account.")
        # Propagate from liquidity line
        st_line_vals_to_write.update({
            'payment_ref': liquidity_lines.name,
            'partner_id': liquidity_lines.partner_id.id,
            'amount': liquidity_lines.amount_currency if journal_currency else liquidity_lines.balance,
        })
        # Handle foreign currency cleanup when suspense is in journal currency
        if journal_currency and suspense_lines.currency_id == journal_currency:
            st_line_vals_to_write.update({
                'amount_currency': 0.0,
                'foreign_currency_id': False,
            })
```

### 8.4 The `checked` Field — Manual Verification Gate

On `account.move`, the `checked` field controls when a move is considered "reviewable":

```python
checked = fields.Boolean(
    string='Reviewed',
    compute='_compute_checked',
    store=True, readonly=False, tracking=True, copy=False,
)

@api.depends('state', 'journal_id.type')
def _compute_checked(self):
    for move in self:
        move.checked = (
            move.state == 'posted' and
            (move.journal_id.type == 'general' or move._is_user_able_to_review())
        )
```

For bank statement line moves (`journal_id.type == 'bank'`), `checked` is `True` only when the user has the `account.group_account_user` permission. This affects `is_reconciled` computation:

```python
def _compute_is_reconciled(self):
    for st_line in self:
        _liquidity_lines, suspense_lines, _other_lines = st_line._seek_for_lines()
        if not st_line.checked:
            # Not reviewed: residual = negative of the statement line's amount_currency
            st_line.amount_residual = -st_line.amount_currency if st_line.foreign_currency_id else -st_line.amount
        elif suspense_lines.account_id.reconcile:
            st_line.amount_residual = sum(suspense_lines.mapped('amount_residual_currency'))
        else:
            st_line.amount_residual = sum(suspense_lines.mapped('amount_currency'))
```

**Why this matters:** If the user hasn't reviewed the statement line's move, the residual amount is the negative of the statement line amount (pre-reconciliation state). Once reviewed (`checked=True`) and reconciled, the residual comes from the suspense line's `amount_residual_currency`. The `action_undo_reconciliation` method explicitly sets `checked=True` after resetting the line.

---

## 9. Multi-Currency Reconciliation

### 9.1 `_get_accounting_amounts_and_currencies()` — Three-Way Amount Extraction

This method is the authoritative source for the three amounts stored in a statement line's journal entry:

```python
def _get_accounting_amounts_and_currencies(self):
    liquidity_line, suspense_line, other_lines = self._seek_for_lines()
    if suspense_line and not other_lines:
        # Normal case: one liquidity + one suspense (pre-reconciliation)
        transaction_amount = -suspense_line.amount_currency
        transaction_currency = suspense_line.currency_id
    else:
        # Reconciliation case: use the statement line's own amounts
        transaction_amount = self.amount_currency if self.foreign_currency_id else self.amount
        transaction_currency = self.foreign_currency_id or liquidity_line.currency_id
    return (
        transaction_amount,      # positive = inbound, negative = outbound
        transaction_currency,
        sum(liquidity_line.mapped('amount_currency')),  # journal amount
        liquidity_line.currency_id,                      # journal currency
        sum(liquidity_line.mapped('balance')),         # company amount
        liquidity_line.company_currency_id,             # company currency
    )
```

The `not other_lines` condition distinguishes:
- **Pre-reconciliation**: exactly two lines (liquidity + suspense) → use suspense line amounts
- **Post-reconciliation**: extra counterpart lines exist → use statement line's own amount fields

### 9.2 `_prepare_counterpart_amounts_using_st_line_rate()` — Rate-Based Conversion

This method converts any amount into the statement line's currency using the rates embedded in the journal entry:

```python
def _prepare_counterpart_amounts_using_st_line_rate(self, currency, balance, amount_currency):
    transaction_amount, transaction_currency, journal_amount, journal_currency, \
        company_amount, company_currency = self._get_accounting_amounts_and_currencies()

    rate_journal2foreign_curr = journal_amount and abs(transaction_amount) / abs(journal_amount)
    rate_comp2journal_curr = company_amount and abs(journal_amount) / abs(company_amount)

    if currency == transaction_currency:
        # Convert from transaction currency to journal to company
        trans_amount_currency = amount_currency
        journ_amount_currency = journal_currency.round(trans_amount_currency / rate_journal2foreign_curr)
        new_balance = company_currency.round(journ_amount_currency / rate_comp2journal_curr)
    elif currency == journal_currency:
        # Convert from journal currency directly to company
        trans_amount_currency = transaction_currency.round(amount_currency * rate_journal2foreign_curr)
        new_balance = company_currency.round(amount_currency / rate_comp2journal_curr)
    else:
        # Convert from company currency through both rates
        journ_amount_currency = journal_currency.round(balance * rate_comp2journal_curr)
        trans_amount_currency = transaction_currency.round(journ_amount_currency * rate_journal2foreign_curr)
        new_balance = balance
```

This is the inverse of the normal conversion: given any AML amount (in any currency), it computes the counterpart amounts to record on the statement line's journal entry.

### 9.3 `_check_amounts_currencies` Constraint

```python
@api.constrains('amount', 'amount_currency', 'currency_id', 'foreign_currency_id', 'journal_id')
def _check_amounts_currencies(self):
    for st_line in self:
        if st_line.foreign_currency_id == st_line.currency_id:
            raise ValidationError(_("The foreign currency must be different than the journal one: %s",
                                    st_line.currency_id.name))
        if not st_line.foreign_currency_id and st_line.amount_currency:
            raise ValidationError(_("You can't provide an amount in foreign currency without "
                                    "specifying a foreign currency."))
        if not st_line.amount_currency and st_line.foreign_currency_id:
            raise ValidationError(_("You can't provide a foreign currency without specifying an "
                                    "'Amount in Currency' field."))
```

---

## 10. Bank Statement Import (EE)

### 10.1 Module Structure

The import functionality is split across Enterprise modules:

| Module | Format | Purpose |
|--------|--------|---------|
| `account_bank_statement_import` | Generic framework | Base wizard, view, and `unique_import_id` constraint |
| `account_bank_statement_import_camt` | CAMT (SEPA) | ISO 20022 CAMT.053 format |
| `account_bank_statement_import_ofx` | OFX / QFX | Open Financial Exchange |
| `account_bank_statement_import_qif` | QIF | Quicken Interchange Format |
| `account_bank_statement_import_csv` | CSV | Generic CSV with column mapping |
| `account_bank_statement_extract` | AI extraction | OCR + AI to extract from scanned PDFs |

### 10.2 `unique_import_id` — Idempotent Import (EE only)

```python
class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    unique_import_id = fields.Char(string='Import ID', readonly=True, copy=False)

    _unique_import_id = models.Constraint(
        'unique (unique_import_id)',
        "A bank account transactions can be imported only once!",
    )
```

When a bank statement is imported with a transaction ID from the file, Odoo stores it as `unique_import_id`. If the same transaction is imported again, the SQL unique constraint raises a `ValidationError`. This is the core mechanism preventing duplicate imports.

### 10.3 `get_import_templates()` (EE only)

```python
@api.model
def get_import_templates(self):
    return [{
        'label': _('Import Template for Bank Statement Lines'),
        'template': '/account_bank_statement_import/static/xls/bank_statement_line_import_template.xlsx'
    }]
```

Returns a downloadable Excel template for manual CSV/XLS import.

### 10.4 Setup Wizard Extension

```python
class AccountSetupBankManualConfig(models.TransientModel):
    _inherit = 'account.setup.bank.manual.config'

    def validate(self):
        """Default the bank statement source of new bank journals as 'file_import'"""
        res = super().validate()
        if (self.num_journals_without_account_bank == 0
                or self.linked_journal_id.bank_statements_source == 'undefined') \
           and self.env['account.journal']._get_bank_statements_available_import_formats():
            self.linked_journal_id.bank_statements_source = 'file_import'
        return res
```

When setting up a new bank journal via the configuration wizard, if any import formats are available, the journal's `bank_statements_source` is automatically set to `file_import`.

---

## 11. L3 Escalation: Edge Cases

### 11.1 Multi-Edit Scenarios

When multiple statement lines are edited simultaneously (from list view):

```python
elif context_st_line_id and len(active_ids) > 1:
    lines = self.env['account.bank.statement.line'].browse(active_ids).sorted()
    if len(lines.journal_id) > 1:
        raise UserError(_("A statement should only contain lines from the same journal."))
    # Check contiguity (canceled lines are ignored)
    indexes = lines.mapped('internal_index')
    lines_between = self.env['account.bank.statement.line'].search([
        ('internal_index', '>=', min(indexes)),
        ('internal_index', '<=', max(indexes)),
        ('journal_id', '=', lines.journal_id.id),
    ])
    canceled_lines = lines_between.filtered(lambda l: l.state == 'cancel')
    if len(lines) != len(lines_between - canceled_lines):
        raise UserError(_("Unable to create a statement due to missing transactions."))
```

### 11.2 Split Statement Flow

When splitting a statement from a single line (`split_line_id` context):

```python
# Lines from line_before's statement up to and including the split line
lines = self.env['account.bank.statement.line'].search([
    ('internal_index', '<=', current_st_line.internal_index),
    ('internal_index', '>', line_before.internal_index or ''),
    ('journal_id', '=', current_st_line.journal_id.id),
], order='internal_index desc')
```

### 11.3 Company Hierarchy in Running Balance

```python
company2children = {
    company: self.env['res.company'].search([('id', 'child_of', company.id)])
    for company in self.journal_id.company_id
}
```

Lines from child companies share the same running balance because they use the same bank journal. The SQL query uses `company_id = ANY(child_company_ids)` to include all related companies.

### 11.4 Statement Line Deletion Guard

```python
@api.ondelete(at_uninstall=False)
def _check_allow_unlink(self):
    if self.statement_id.filtered(lambda stmt: stmt.is_valid and stmt.is_complete):
        raise UserError(_("You can not delete a transaction from a valid statement.\n"
                          "If you want to delete it, please remove the statement first."))
```

Deletion is blocked if the statement is both **valid** (balances match previous) AND **complete** (all transactions entered). This prevents tampering with audited statements.

### 11.5 `unlink()` — Cascade to `account.move` with Audit Trail Check

```python
def unlink(self):
    tracked_lines = self.filtered(lambda stl: stl.company_id.restrictive_audit_trail)
    tracked_lines.move_id.button_cancel()
    moves_to_delete = (self - tracked_lines).move_id
    res = super().unlink()
    moves_to_delete.with_context(force_delete=True).unlink()
    return res
```

- Lines on companies with `restrictive_audit_trail`: the move is **cancelled** (not deleted) before unlinking the line, preserving the audit trail
- Lines on companies without that flag: the move is force-deleted along with the line
- `super().unlink()` cascades the `ondelete='cascade'` on `move_id`, deleting the `account.move` row

### 11.6 Attachment Handling in `create()` / `write()`

```python
@contextmanager
def _check_attachments(self, container, vals_list):
    attachments_to_fix_list = []
    for values in vals_list:
        attachment_ids = set()
        for orm_command in values.get('attachment_ids', []):
            if orm_command[0] == Command.LINK:
                attachment_ids.add(orm_command[1])
            elif orm_command[0] == Command.SET:
                for attachment_id in orm_command[2]:
                    attachment_ids.add(attachment_id)
        attachments = self.env['ir.attachment'].browse(list(attachment_ids))
        attachments_to_fix_list.append(attachments)
    yield  # <-- create/write happens here
    for stmt, attachments in zip(container['records'], attachments_to_fix_list):
        attachments.write({'res_id': stmt.id, 'res_model': stmt._name})
```

This context manager handles the timing issue where attachment `res_id` cannot be set before the statement record exists. It collects attachment IDs before `super().create()` and fixes them afterward.

### 11.7 `write()` Override — Multi-Record Attachment Limitation

```python
def write(self, vals):
    if len(self) != 1 and 'attachment_ids' in vals:
        vals.pop('attachment_ids')  # Silently drop attachment changes on multi-edit
```

Attachments can only be modified when writing to a **single** statement. On multi-edit, attachment changes are silently dropped. This prevents ambiguity when setting attachments on multiple statements simultaneously.

### 11.8 `formatted_read_group` Running Balance Integration

```python
@api.model
def formatted_read_group(self, domain, groupby=(), aggregates=(), having=(), offset=0, limit=None, order=None) -> list[dict]:
    result = super().formatted_read_group(...)
    for el in groupby:
        if (el == 'statement_id' or el == 'journal_id' or el.startswith('date')) \
           and self.env.context.get('show_running_balance_latest'):
            show_running_balance = True
    if show_running_balance:
        for group_line in result:
            group_line['running_balance'] = self.search(
                group_line['__extra_domain'] + domain, limit=1
            ).running_balance or 0.0
    return result
```

This allows the bank reconciliation kanban view to show the running balance at the group level by querying the first record of each group. The `show_running_balance_latest` context key controls this feature.

### 11.9 Default Date Propagation from Last Transaction

```python
def default_get(self, fields):
    if 'date' in fields and not defaults.get('date') and 'journal_id' in defaults:
        last_line = self.search([
            ('journal_id', '=', defaults['journal_id']),
            ('state', '=', 'posted'),
        ], limit=1)
        statement = last_line.statement_id
        if statement:
            defaults.setdefault('date', statement.date)
        elif last_line:
            defaults.setdefault('date', last_line.date)
```

When creating a new statement line from the UI, the form pre-fills the date from the latest posted transaction's statement (or the line itself). This is only possible when the journal is already set (single-journal view).

### 11.10 Multi-Currency: `_compute_amount_currency` Auto-Conversion Guard

```python
@api.depends('foreign_currency_id', 'date', 'amount', 'company_id')
def _compute_amount_currency(self):
    for st_line in self:
        if not st_line.foreign_currency_id:
            st_line.amount_currency = False
        elif st_line.date and not st_line.amount_currency:
            # only convert if it hasn't been set already
            st_line.amount_currency = st_line.currency_id._convert(...)
```

The conversion only happens **if `amount_currency` is not already set**, preventing auto-conversion from overwriting user-entered values. This is critical for reconciliation: when matching an AML, the user-entered exchange rate must not be overwritten.

---

## 12. L4 Escalation: Performance, Security & Historical Changes

### 12.1 Performance: Running Balance SQL Optimization

The `_compute_running_balance` method is the most performance-critical operation in this module. Key design decisions:

1. **Single SQL query per journal**: All lines up to `max_index` are fetched in one `SELECT` with `ORDER BY internal_index`. No per-line queries.

2. **Statement as anchor points**: Instead of computing from the absolute beginning of time, the algorithm finds the nearest preceding statement's `balance_start` and uses that as the starting point. This bounds the query scope.

3. **Pending items fallback**: Lines that don't appear in SQL results (e.g., deleted from form view but still in DB) fall back to `item.running_balance = item.running_balance`, which recomputes via ORM (slower but safe).

4. **Multi-company batch**: All lines from the same journal are processed in one SQL query, regardless of how many line records are in `self`.

5. **Index-only scan eligible**: The `_main_idx` covering index `(journal_id, company_id, internal_index)` allows PostgreSQL to satisfy the running balance query without touching the heap.

### 12.2 Performance: `is_valid` SQL Window Function

The `_get_invalid_statement_ids` method uses a single PostgreSQL `LAG()` window function to compute all invalid statements in one pass:

```sql
LAG(st.balance_end_real) OVER (PARTITION BY st.journal_id ORDER BY st.first_line_index)
```

This avoids N ORM queries for N statements. The query is executed with `flush_model()` calls before it to ensure all computed fields are persisted to the database. The `ROUND(x, decimal_places)` accounts for floating-point comparison, using the currency's actual decimal places.

### 12.3 Performance: `balance_start` Cascading Recomputation

`balance_start` depends on the previous statement's `balance_end_real`. When one statement is modified, **all subsequent statements** in the same journal may need their `balance_start` recomputed. This creates a cascading effect that can be expensive for journals with many statements. Mitigation:
- `balance_start` is computed in the context of the current statement only
- The ORM handles dependency tracking via `@api.depends`
- Large-scale changes should be done in a single `write()` call on multiple statements

### 12.4 Performance: Index Strategy

| Index | Type | Purpose |
|-------|------|---------|
| `_unreconciled_idx` | Partial (`WHERE is_reconciled IS NOT TRUE`) | Speeds up bank reconciliation widget query for unreconciled lines |
| `_orphan_idx` | Partial (`WHERE statement_id IS NULL`) | Fast lookup of lines not yet assigned to a statement |
| `_main_idx` | Full `(journal_id, company_id, internal_index)` | Covering index for most statement line queries |
| `_journal_id_date_desc_id_desc_idx` | On statement `(journal_id, date DESC, id DESC)` | Statement listing and ordering |
| `_first_line_index_idx` | On statement `(journal_id, first_line_index)` | Validity check ordering |
| `_checked_idx` | Partial on `account.move` (`WHERE checked IS NOT TRUE`) | Find unreviewed bank moves for approval workflows |

The partial indexes (`WHERE` clause) are dramatically smaller than full indexes since most lines are reconciled/assigned. The `_orphan_idx` is especially important for the "Bank Transactions" kanban view showing unassigned lines.

### 12.5 Historical Changes: Odoo 16 → 17 → 18 → 19

#### Odoo 17 Changes
- **Removed** the old XML workflow engine usage for statement state transitions
- **`state` field on `account.bank.statement`**: Changed from selection with `'confirm'` action to computed fields `is_complete` / `is_valid`
- Statement lines no longer have their own `state`; they inherit from `account.move`

#### Odoo 18 Changes (Major Refactoring)
- **`_inherits = {'account.move': 'move_id'}`**: Statement lines now inherit from journal entries
- **Auto-posting**: Lines are posted immediately on creation, removing the `draft` → `open` → `done` workflow
- **`running_balance`**: New field, not present in Odoo 17
- **`internal_index`**: New field replacing the old `date + sequence + id` sort logic
- **`amount_residual`**: New technical field for reconciliation performance
- **Statement as pure grouping**: `account.bank.statement` is no longer the primary data carrier; it is now a virtual grouping construct
- **`unique_import_id`**: Introduced in EE import module for idempotent imports
- **`checked` field**: New on `account.move`, controls manual verification gate for bank moves

#### Odoo 19 Changes (Refinement)
- **`_compute_balance_start`** improved to handle multi-edit scenarios where lines are moved between statements, including subtraction of lines in common during split operations
- **`_get_invalid_statement_ids`**: Added explicit `flush_model()` calls before SQL query to ensure computed field values are in the database before the window function runs
- **`formatted_read_group`**: Enhanced to support `running_balance` in grouped views via `show_running_balance_latest` context
- **`company2children`** handling in running balance: explicit multi-company support added via `child_of` domain
- **Suspense account validation**: More explicit `UserError` when suspense account is missing on the journal during line creation
- **`transaction_details`**: New `Json` field for structured import metadata
- **`_get_accounting_amounts_and_currencies`**: New method explicitly extracting all three amounts and currencies from the journal entry

### 12.6 Security Considerations

| Concern | Mitigation |
|---------|-----------|
| **Statement tampering** | `_check_allow_unlink` prevents deletion of lines from valid+complete statements |
| **Move audit trail** | Companies with `restrictive_audit_trail` cancel (not delete) moves on line unlink |
| **Attachment access** | `attachment_ids` field uses `bypass_search_access=True` — attachments bypass record rules, only ACL applies |
| **Multi-company isolation** | All queries respect `company_id` via `_check_company_auto` and explicit domain filters; partial indexes scope by company |
| **Reconciliation access** | `_get_default_amls_matching_domain()` restricts suggestion domain to reconcilable accounts and child companies |
| **SQL injection** | All raw SQL uses `SQL` object from `odoo.tools.SQL` (parameterized), not string formatting |
| **Field-level access** | No `groups` restrictions on standard fields; relies on `ir.model.access` + `ir.rule` |
| **Cross-partner bank account** | `_find_or_create_bank_account()` returns empty if account number exists on another active partner |
| **Suspense account missing** | `create()` raises `UserError` if journal has no suspense account — prevents posting to incorrect account |
| **`bypass_search_access`** | Used on `move_id` and `statement_line_id` fields to avoid expensive ACL checks during normal operations; does not grant access, only bypasses `ir.rule` search restrictions |

### 12.7 Edge Cases in `is_valid` SQL

The `_get_invalid_statement_ids` SQL query has subtle behavioral notes:

- **First statement**: Has no `prev_balance_end_real` (NULL from `LAG()`), so `IS NOT NULL` clause excludes it — first statements are always considered valid
- **Missing intermediate statements**: If a statement is deleted, the next statement's `balance_start` won't match the `LAG()` value (which points to the now-deleted statement's `balance_end_real`), making the current statement appear invalid
- **Decimal precision**: `ROUND(x, decimal_places)` handles floating-point comparison issues. The `decimal_places` comes from the currency's `decimal_places` field, not a hardcoded constant.
- **New records (not flushed)**: For single-record reads, the Python path `_get_statement_validity()` is used which avoids the SQL boundary entirely; for batch reads/searches, `flush_model()` ensures computed fields are DB-visible before the window function query

### 12.8 `bypass_search_access` — ORM Performance Optimization

```python
move_id = fields.Many2one(
    comodel_name='account.move',
    bypass_search_access=True,
    string='Journal Entry', required=True, readonly=True, ondelete='cascade',
)
```

`bypass_search_access=True` means that when the ORM executes `search()` or `browse()` on this field's related model (`account.move`), it skips the `ir.rule` check. This is safe here because:
- The `move_id` is always set to a newly-created `account.move` (not a user-provided ID)
- Read access on the statement line already implies the user can access the move
- The alternative (checking rules for every statement line query) would be prohibitively expensive

The same pattern is used on `statement_line_id` on `account.move.line`.

---

## Quick Reference

### Key Models

| Model | Purpose |
|-------|---------|
| `account.bank.statement` | Grouping container; computes balances and validates integrity |
| `account.bank.statement.line` | Individual transaction; inherits from `account.move` |
| `account.journal` | Bank/cash journal; defines suspense account and import source |

### Key Fields (Statement)

| Field | Purpose |
|-------|---------|
| `balance_start` | Previous statement's ending balance (editable) |
| `balance_end` | Computed: start + all posted line amounts |
| `balance_end_real` | User-set: actual bank-reported ending balance |
| `is_complete` | Internal check: does balance_end match balance_end_real? |
| `is_valid` | External check: does balance_start match previous statement's end? |
| `first_line_index` | Anchor point for statement ordering |
| `internal_index` | Sortable composite key per line |

### Key Fields (Line)

| Field | Purpose |
|-------|---------|
| `amount` | Transaction amount in journal currency |
| `amount_currency` | Transaction amount in foreign currency (optional) |
| `running_balance` | Cumulative balance anchored to nearest statement |
| `is_reconciled` | Has all journal items been fully matched? |
| `internal_index` | Composite sort key for fast ordering |
| `payment_ref` | Label/reference shown in reconciliation UI |
| `partner_id` | Counterparty (customer or vendor) |
| `statement_id` | Parent statement (null = orphan/ungrouped) |
| `amount_residual` | Signed residual for reconciliation model matching |
| `checked` | Manual verification gate (on the underlying `account.move`) |

### Key Computed Methods

| Method | Complexity | Purpose |
|--------|-----------|---------|
| `_compute_running_balance` | High (SQL) | Cumulative balance with statement anchoring |
| `_compute_balance_start` | High (ORM search) | Previous statement's balance + intermediate lines |
| `_compute_is_valid` | High (SQL window) | External integrity via LAG() |
| `_compute_internal_index` | Low (string format) | Lexicographic sort key |
| `_compute_is_reconciled` | Low (line iteration) | Residual amount check with checked-field gating |

### Key Action / Helper Methods

| Method | Purpose |
|--------|---------|
| `action_undo_reconciliation()` | Remove reconciliation links and reset to original state |
| `_find_or_create_bank_account()` | Link line to partner bank account during reconciliation |
| `_get_default_amls_matching_domain()` | Build search domain for reconciliation suggestions |
| `_prepare_move_line_default_vals()` | Generate liquidity + suspense journal items |
| `_seek_for_lines()` | Classify journal items into liquidity/suspense/other |
| `_get_accounting_amounts_and_currencies()` | Extract all three amounts from the journal entry |
| `_prepare_counterpart_amounts_using_st_line_rate()` | Convert amounts using embedded exchange rates |
| `_synchronize_to_moves()` | Push statement line changes to the underlying move |
| `_synchronize_from_moves()` | Pull move changes back to the statement line |

---

## Tags

#odoo #odoo19 #modules #accounting #bank-statement #reconciliation #orm #multi-currency #security
