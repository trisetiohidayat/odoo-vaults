---
uuid: account-accountant-l4
tags: [odoo, odoo19, modules, account, accounting, bank-reconciliation, enterprise]
description: Bank reconciliation widget, reconciliation models, deferred revenue/expense, lock dates, signing, and accounting workflow in Odoo 19 Enterprise
---

# account_accountant Module (`account_accountant`)

> **Note:** This is an **Enterprise-only** module. In Community Edition, bank reconciliation and deferred entries are handled differently or not available.

**Module Path (EE):** `enterprise/tracon-enterprise/account_accountant/`
**Category:** Accounting/Accounting
**License:** OEEL-1 (Odoo Enterprise Edition License)
**Odoo Version:** 19.0+
**Auto-install:** True (installed with `account` when EE is active)
**Dependencies:** `account`, `mail_enterprise`, `web_tour`

---

## L1 - All Fields and Method Signatures

### Models Overview

| Model | Purpose |
|-------|---------|
| `bank.rec.widget` | Non-persistent in-memory state machine for bank reconciliation |
| `bank.rec.widget.line` | Non-persistent per-line state for the reconciliation widget |
| `account.reconcile.model` | Auto-reconciliation rule definitions |
| `account.reconcile.model.line` | Per-line rules within a reconciliation model |
| `account.move` (extended) | Deferred entries generation, signing, lock date checks |
| `account.bank.statement` (extended) | Auto-reconciliation cron, partner detection |
| `account.bank.statement.line` (extended) | Partner detection strategies |
| `account.lock.exception` | Timed overrides for hard lock dates |
| `res.company` (extended) | Deferred settings, signing settings, fiscal year methods |
| `digest.digest` (extended) | Bank cash KPI for accountant dashboards |

---

### `bank.rec.widget` (Non-Persistent)

Non-persistent model (`_auto=False`, `_table_query="0"`) that acts as an in-memory state machine for the bank reconciliation process.

```python
class BankRecWidget(models.TransientModel):
    _name = 'bank.rec.widget'
    _description = 'Bank Rec Widget'
    _transient_max_hours = 24
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `st_line_id` | Many2one (`account.bank.statement.line`) | Current statement line being reconciled |
| `partner_id` | Many2one (`res.partner`) | Detected/assigned partner |
| `line_ids` | One2many (`bank.rec.widget.line`) | All counterpart lines in the widget |
| `available_reco_model_ids` | Many2many (`account.reconcile.model`) | Models applicable to this line |
| `selected_reco_model_id` | Many2one | Currently selected auto-match model |
| `state` | Selection (computed) | `'invalid'`, `'valid'`, or `'reconciled'` |
| `todo_command` | Json | Bidirectional JS<->Python command queue |
| `company_id` | Many2one | Current company |
| `move_ids` | Many2many (`account.move`) | Generated journal entries |
| `dispense_notes` | Html | Notes shown in the wizard |

**Key Methods:**

```python
def _compute_line_ids(self)              # Rebuilds all widget lines from st_line + amls
def _compute_partner_id(self)             # Detects partner from st_line + selected amls
def _compute_state(self)                  # 'invalid'/'valid'/'reconciled'
def _compute_available_reco_model_ids(self)  # Filters applicable recon models
def _js_action_*()                        # Handlers for JS widget commands
def _action_validate(self)                # Finalizes reconciliation
def _action_add_new_amls(self, aml_ids)   # Adds existing amls as counterpart
def _action_add_new_st_line(self, st_line_id)  # Switches to a different st_line
def _action_remove_st_line(self)           # Clears current st_line
def _action_toggle_bank_account(self)      # Switches journal bank account
def _action_write_off(self, vals)         # Creates manual write-off line
def _action_early_payment(self, epd_ids)  # Marks early payment discount lines
def _compute_dispense_notes(self)         # Returns HTML notes about the reconciliation
```

---

### `bank.rec.widget.line` (Non-Persistent)

Non-persistent model representing each line shown in the bank reconciliation widget. Inherits `analytic.mixin` for analytic distribution.

```python
class BankRecWidgetLine(models.TransientModel):
    _name = 'bank.rec.widget.line'
    _description = 'Bank Rec Widget Line'
    _auto = False
    _table_query = "0"
```

**Flag Values (stored in `flag` Char field):**

| Flag | Meaning |
|------|---------|
| `liquidity` | The bank statement line itself (always present, exactly one) |
| `aml` | Existing matched account move line |
| `new_aml` | Newly created counterpart (from recon model) |
| `exchange_diff` | Exchange difference line (auto-generated) |
| `tax_line` | Tax line (from invoice/bill) |
| `manual` | Manually entered write-off line |
| `early_payment` | Early payment discount line |
| `auto_balance` | Auto-generated balancing line when debits != credits |

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `widget_id` | Many2one (`bank.rec.widget`) | Parent wizard |
| `flag` | Char | Line type flag (above) |
| `account_id` | Many2one (`account.account`) | Target account |
| `name` | Char | Line label |
| `amount` | Monetary | Amount in company's currency |
| ` amount_currency` | Monetary | Amount in foreign currency |
| `currency_id` | Many2one | Foreign currency |
| `date` | Date | Effective date |
| `partner_id` | Many2one | Counterpart partner |
| `analytic_distribution` | Json | Analytic distribution (inherited from mixin) |
| `tax_ids` | Many2many | Taxes to apply |
| `tax_repartition_line_id` | Many2one | Tax distribution line |
| ` source_amount` | Monetary | Original amount (before tax) |
| `source_amount_currency` | Monetary | Original foreign amount |
| `source_date` | Date | Original date |
| `reconcile_model_id` | Many2one | Source recon model line |
| ` force_close` | Boolean | Force inclusion even if unbalanced |
| `is_already_reconciled` | Boolean | Read-only flag for already-reconciled |
| `account_code` | Char | Computed account code (for display) |
| `source_currency_id` | Many2one | Original aml currency |

**Key Methods:**

```python
def _compute_account_id(self)              # Determines target account based on flag
def _lines_check_partial_amount(self)       # Validates partial payment amount
def _lines_check_apply_early_payment_discount(self)  # Checks if epd applies
```

---

### `account.reconcile.model` (Extended)

Extends `account.reconcile.model` from the `account` module with SQL-based invoice matching and partner mapping.

```python
class AccountReconcileModel(models.Model):
    _name = 'account.reconcile.model'
    _inherit = 'account.reconcile.model'
```

**Additional Methods:**

```python
def _is_applicable_for(self, st_line, partner)           # Checks journal/nature/amount/partner/regex
def _get_invoice_matching_amls_candidates(self, st_line)  # SQL CTE for token-based matching
def _check_rule_propositions(self, st_line, propositions)  # Validates tolerance
def _get_partner_from_mapping(self, st_line)              # Regex match on payment_ref/narration
def _apply_in_bank_widget(self, widget, st_line, props)    # Applies model to widget lines
```

**Key SQL Feature — Token-Based Invoice Matching:**
```python
# Numerical tokens are extracted from st_line.payment_ref using:
REGEXP_SPLIT_TO_ARRAY(payment_ref, '\D+')

# Matched against invoice sequence numbers using:
REGEXP_SPLIT_TO_ARRAY(number, '\D+')

# Matching: share at least one common numerical token (invoice number, date digits, etc.)
```

---

### `account.reconcile.model.line` (Extended)

Extends `account.reconcile.model.line` with bank-widget-specific application logic.

```python
class AccountReconcileModelLine(models.Model):
    _name = 'account.reconcile.model.line'
    _inherit = 'account.reconcile.model.line'
```

**Key Override:**
```python
def _apply_in_bank_widget(self, widget, st_line, props):
    # For 'percentage_st_line' type: uses st_line's foreign currency, not journal currency
    # Creates counterpart aml in the correct currency for cross-border payments
```

---

### `account.move` (Extended)

Extends `account.move` with deferred entry generation and invoice signing.

```python
class AccountMove(models.Model):
    _inherit = 'account.move'
```

**Constants:**
```python
DEFERRED_DATE_MIN = '1900-01-01'
DEFERRED_DATE_MAX = '9999-12-31'
```

**Additional Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `deferred_move_ids` | One2many | Generated deferred entry moves |
| `deferred_original_move_ids` | Many2many | Original moves for deferred entries |
| `deferred_entry_type` | Selection (computed) | `'expense'`/`'revenue'` from line categories |
| `signing_user` | Many2one (`res.users`) | User who signed |
| `signature` | Binary (computed) | Base64 signature image |
| `show_signature_area` | Boolean (computed) | Whether to show signing UI |

**Key Methods:**

```python
def _get_deferred_entries_method(self)               # Returns 'on_validation' or 'manual'
def _generate_deferred_entries(self)                  # Creates all deferred entry moves
def _get_deferred_entry_name(self, entry)             # Formats "Deferred: {move_name}"
def _get_deferred_period_amount(self, amount, start, end, first_date, last_date, method)  # Day/month/full_months
def action_request_signature(self)                    # Triggers signature request
def action_sign(self)                                # Records signature
def _post(self, soft=True)                           # Extended: generates deferred + checks signing
def _recompute_payment_terms(self)                    # Also sets up deferred entry tracking
```

---

### `account.bank.statement` (Extended)

Extends `account.bank.statement` with batch auto-reconciliation.

```python
class AccountBankStatement(models.Model):
    _inherit = 'account.bank.statement'
```

**Key Methods:**

```python
def _cron_try_auto_reconcile_statement_lines(self)  # Batch auto-reconciliation cron
def _auto_reconcile_lines(self, lines)               # Core auto-reconciliation logic
```

---

### `account.bank.statement.line` (Extended)

Extends `account.bank.statement.line` with partner detection.

```python
class AccountBankStatementLine(models.Model):
    _inherit = 'account.bank.statement.line'
```

**Partner Detection Strategies (in `_retrieve_partner`):**
1. **Direct match** — aml with same partner
2. **Bank account match** — partner with matching bank account
3. **Name match** — partner with matching `name` or `contact_name`
4. **Reconciliation model mapping** — regex match on `payment_ref` or `narration`

---

### `account.lock.exception`

Stores timed overrides for hard lock dates.

```python
class AccountLockException(models.Model):
    _name = 'account.lock.exception'
    _description = 'Lock Date Exception'
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `company_id` | Many2one | Company |
| `lock_date` | Date | The hard lock date being overridden |
| `exception_applies_to` | Selection | `'all'`, `'advisers'`, or `'controllers'` |
| `exception_duration` | Selection | `'5min'`, `'15min'`, `'1h'`, `'24h'`, `'forever'` |
| `exception_reason` | Text | Justification for the exception |
| `create_date` | Datetime | When exception was created |

**Exception durations map to expiry timestamps:**
```python
'5min': now + 5min
'15min': now + 15min
'1h': now + 1h
'24h': now + 24h
'forever': datetime.max (2099-12-31)
```

---

### `res.company` (Extended)

**Deferred Settings Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `deferred_expense_journal_id` | Many2one | Journal for deferred expense entries |
| `deferred_revenue_journal_id` | Many2one | Journal for deferred revenue entries |
| `deferred_expense_account_id` | Many2one | Prolongation account for expenses |
| `deferred_revenue_account_id` | Many2one | Prolongation account for revenue |
| `generate_deferred_expense_entries_method` | Selection | `'on_validation'` or `'manual'` |
| `generate_deferred_revenue_entries_method` | Selection | `'on_validation'` or `'manual'` |
| `deferred_expense_amount_computation_method` | Selection | `'day'`, `'month'`, or `'full_months'` |
| `deferred_revenue_amount_computation_method` | Selection | `'day'`, `'month'`, or `'full_months'` |

**Signing Settings:**

| Field | Type | Description |
|-------|------|-------------|
| `sign_invoice` | Boolean | Enable invoice signing |
| `signing_user` | Many2one | Default signing user |

**Fiscal Year Methods:**
```python
def compute_fiscalyear_dates(self, date)  # Checks account.fiscal.year first, then date_utils
```

**Invoicing Switch Threshold:**
```python
def _auto_init()                           # Bulk SQL update of all related moves when threshold changes
```

---

## L2 - Bank Reconciliation Widget Architecture

### Non-Persistent State Machine

The `bank.rec.widget` is a **non-persistent transient model** — it never writes to the database except to create the final reconciled journal entries. It serves as a stateful wizard-like interface powered entirely by in-memory computed fields.

**Key architectural decisions:**
- `_auto = False` + `_table_query = "0"` = no database table created
- All state is computed via `_compute_line_ids()` which rebuilds from `st_line_id` + selected `aml_ids`
- JS frontend polls `_compute_todo_command` to get the next command to execute
- Python responds with JSON commands that the JS interpreter dispatches

### JS Command System

The widget uses a bidirectional command queue stored in `todo_command` (Json field):

```python
# Python -> JS (response to a JS action)
todo_command = {"action": "display_notification", "body": "Reconciliation complete"}

# JS -> Python (user action)
todo_command = {"action": "action_add_new_amls", "args": [aml_ids]}
```

**Command handlers (`_js_action_*`):**

| Handler | JS Action | Purpose |
|---------|-----------|---------|
| `_js_action_add_new_amls` | `action_add_new_amls` | Add existing amls as counterpart |
| `_js_action_add_new_st_line` | `action_add_new_st_line` | Switch to different st_line |
| `_js_action_remove_st_line` | `action_remove_st_line` | Clear current line |
| `_js_action_toggle_bank_account` | `action_toggle_bank_account` | Switch journal |
| `_js_action_write_off` | `action_write_off` | Manual write-off |
| `_js_action_early_payment` | `action_early_payment` | Apply early payment discount |
| `_js_action_apply_reco_model` | `action_apply_reco_model` | Apply auto-match model |
| `_js_action_mount_line_in_edit` | `action_mount_line_in_edit` | Edit a line's account/tax |
| `_js_action_validate` | `action_validate` | Finalize reconciliation |

### Widget Line Computation Flow

```
st_line_id changes
  → _compute_line_ids()
      → Get st_line's journal entry (liquidity line)
      → Get selected aml_ids (counterpart lines)
      → For each aml, call _compute_account_id() to determine flag
      → Build bank.rec.widget.line recordsets
      → Compute exchange_diff lines if currency mismatch
      → Auto-balance if debits != credits
  → _compute_partner_id()
  → _compute_available_reco_model_ids()
  → _compute_state()
```

### State Computation Logic

```python
def _compute_state(self):
    for rec in self:
        if rec.st_line_id.is_reconciled:
            rec.state = 'reconciled'
        elif rec._lines_are_strictly_valid():
            rec.state = 'valid'
        else:
            rec.state = 'invalid'

def _lines_are_strictly_valid(self):
    # Must have exactly one liquidity line
    # All aml lines must reference existing accounts
    # No suspense account in non-exchange lines
    # Amounts must be non-null
    # Balance must be zero (or within tolerance)
```

### Analytic Distribution on Widget Lines

Widget lines inherit `analytic.mixin` which provides:
- `analytic_distribution` Json field
- `distribution_analytic_account_ids` computed many2many
- Validation of mandatory plans

When a user sets analytic distribution on a widget line, it is passed through to the generated journal entry line via `_action_validate()`.

---

## L3 - Reconciliation Models, Deferred Entries, Lock Dates

### Reconciliation Model Rule Engine

The extended `account.reconcile.model` provides enterprise-grade auto-matching:

**Applicability Filter (`_is_applicable_for`):**
```python
# Each rule is checked against st_line in order of priority:
1. journal_ids:     st_line.journal_id in rule.journal_ids?
2. match_natule:    'any' / 'amount_positive' / 'amount_negative' / 'both'
3. match_amount:    min/max amount range
4. match_partner:   partner_ids restriction
5. match_label:     regex on payment_ref (e.g., 'INV\d+' matches invoices)
```

**Token-Based Invoice Matching (`_get_invoice_matching_amls_candidates`):**
```sql
-- Extracts numerical tokens from payment_ref and invoice numbers
-- Matches if any token is shared
WITH tokens AS (
    SELECT REGEXP_SPLIT_TO_ARRAY(payment_ref, '\D+') AS arr
),
invoice_tokens AS (
    SELECT id, number, REGEXP_SPLIT_TO_ARRAY(number, '\D+') AS arr
    FROM account_move_line
    WHERE ...  -- partner, currency, date range filters
)
SELECT DISTINCT l.id
FROM tokens t
JOIN invoice_tokens l ON t.arr && l.arr  -- array overlap operator
WHERE ...
```

**Proposition Validation (`_check_rule_propositions`):**
```python
# Tolerance can be fixed amount or percentage
# 'allowed_residual辕nalysis <= tolerance' -> still valid
# 'fixed_amount' or 'percentage' tolerance type
```

### Deferred Entries Architecture

When an invoice uses deferred entries (e.g., "Spread costs monthly over 12 months"):

**Trigger:** `_post()` is called with `method == 'on_validation'`

**Flow:**
```python
_post()
  → _generate_deferred_entries()
      → For each line with defer_until > invoice_date:
          → Determine period dates
          → Call _get_deferred_period_amount(amount, start, end, method)
          → Create deferred move per period (or single aggregated move)
```

**Amount Computation Methods:**
```python
# 'day': proportional by days in period
# 'month': each full month gets 1/n of total (last month gets remainder)
# 'full_months': only fully-covered months are counted
```

**Generated Deferred Move Structure:**
```
Deferred: {move_name} - {month_year}
  Debit:  {pro_rata_amount}   Deferred Expense Account
  Credit: {pro_rata_amount}   Deferral Account (opposite of original)
```

### Lock Date Exception System

**Hard Lock Date (`hard_lock_date`):** Irreversible once set. No entries can be posted before this date.

**Exception System (`account.lock.exception`):**
- Creates a timed override with justification
- Scope: `'all'` (anyone), `'advisers'` (accountants), `'controllers'` (managers)
- Duration: 5min to forever
- `forever` sets expiry to 2099-12-31 (effectively permanent override)

**Check Flow:**
```python
# In account.move._check_fiscal_year_lock_date()
# If st_line date < hard_lock_date:
#     Check for matching account.lock.exception
#     If valid exception exists for current user:
#         Allow (with audit trail)
#     Else:
#         Block with UserError
```

---

## L4 - Full Depth Analysis

### Odoo 18 to Odoo 19 Changes

| Aspect | Odoo 18 | Odoo 19 |
|--------|---------|---------|
| Bank rec widget | Standard form view | Dedicated non-persistent model with JS command system |
| Deferred entries | On `account.move.line` | On `account.move` with `deferred_original_move_ids` |
| Deferred method | Via `deferred_date_range_id` | Via `method` ('on_validation'/'manual') |
| Hard lock date | Binary flag | `account.lock.exception` with timed overrides |
| Early payment discount | Via `early_pay_discount_computation` | Via `action_early_payment` widget command |
| Auto-reconciliation | Statement-level | Batch with row-level locking via `SELECT FOR UPDATE` |
| Signing | Embedded in move | `signing_user`, `signature`, `show_signature_area` |

### Performance Patterns

#### 1. Non-Persistent Model Performance
`bank.rec.widget` and `bank.rec.widget.line` use `_auto=False` and `_table_query="0"` to completely bypass database writes during the reconciliation process. This means:
- No ORM overhead during widget interaction
- No table bloat from transient records
- State lives only in the HTTP session/JS frontend

#### 2. Batch Cron with Row-Level Locking
```python
# _cron_try_auto_reconcile_statement_lines uses:
SELECT id FROM account_bank_statement_line
WHERE ... AND is_reconciled = False
ORDER BY date, sequence
LIMIT :batch_size
FOR UPDATE SKIP LOCKED  -- Prevents concurrent cron instances

# Each batch processes, then releases locks
# Row-level locking (not table-level) allows parallel processing
```

#### 3. SQL CTE for Invoice Matching
`_get_invoice_matching_amls_candidates` uses a raw SQL CTE (avoiding the ORM entirely) to perform token-based matching efficiently:
```sql
WITH RECURSIVE is not needed; simple CTE with array overlap
(`&&` PostgreSQL array operator) enables fast matching without LIKE
```

#### 4. Deferred Entry Bulk Creation
`_generate_deferred_entries` creates multiple `account.move` records in a single transaction. Uses `deferred_original_move_ids` many2many to track the relationship without duplicating line data.

#### 5. GIN Index on Analytic Distribution
Widget lines inherit `analytic.mixin` which creates GIN indexes on `analytic_distribution` for fast JSON key lookups during distribution validation.

### Cross-Module Dependencies

```
account_accountant (EE)
  ├── account (required)
  │     ├── account.move — extended with deferred + signing
  │     ├── account.move.line — carries analytic_distribution
  │     ├── account.bank.statement — extended with auto-reconcile
  │     ├── account.bank.statement.line — extended with partner detection
  │     ├── account.reconcile.model — extended with SQL matching
  │     ├── account.reconcile.model.line — extended with currency handling
  │     └── res.company — settings for deferred/sign lock dates
  ├── analytic (inherited via analytic.mixin)
  │     ├── analytic.mixin — provides analytic_distribution Json field
  │     └── account.analytic.plan — plans for distribution validation
  ├── mail_enterprise — notification on line splits
  └── web_tour — guided tours for reconciliation workflow
```

### Failure Modes

| Failure | Cause | Fix/Workaround |
|---------|-------|----------------|
| Widget stuck in "invalid" state | Liquidity line missing or suspense account in counterpart | Call `_action_toggle_bank_account` to reset |
| Deferred entries not generating | `generate_deferred_*_entries_method = 'manual'` | Change to `'on_validation'` in company settings |
| Partner not detected | No matching bank account, name, or recon model | Manually assign partner on st_line |
| Auto-reconcile cron misses lines | Another cron already locked them | Uses `FOR UPDATE SKIP LOCKED` — normal behavior |
| Hard lock date blocks posting | `hard_lock_date` is set and no valid exception | Create `account.lock.exception` with justification |
| Exchange difference loop | Currency mismatch with no corresponding rate | Manually create exchange difference move |
| Rec model not appearing | `match_label` regex not matching payment_ref | Check regex pattern in model rule |
| Early payment discount not applying | Invoice already fully paid or past discount date | Check `payment_term_lines` and `allow_edition` |

### Security Model

| Access | Required Group |
|--------|---------------|
| View bank statements | `account.group_account_user` |
| Manual bank reconciliation | `account.group_account_user` |
| Auto-reconciliation cron | `account.group_account_manager` (creates cron) |
| Set hard lock date | `account.group_account_manager` |
| Create lock exception | `account.group_account_manager` |
| View lock exceptions | `account.group_account_user` |
| Generate deferred entries | `account.group_account_user` |
| Sign invoices | `account.group_account_user` (with `sign_invoice` enabled) |
| Deferred journal settings | `account.group_account_manager` |

### Deferred Entry Computation Detail

The `_get_deferred_period_amount` method handles three computation strategies:

```python
def _get_deferred_period_amount(self, amount, start, end, first_date, last_date, method):
    if method == 'day':
        # Proportional by days
        # total_amount * days_in_period / total_days
        return float_round(total * nb_days / total_nb_days, precision_rounding=precision)
    
    elif method == 'month':
        # Monthly buckets; first and last partial months get prorated
        # Middle full months get 1/n each
        # Last month absorbs any rounding remainder
        
    elif method == 'full_months':
        # Only months fully covered by start/end get allocated
        # Partial months at edges are skipped
        # remainder stays on last covered month
```

**Boundary constants:**
- `DEFERRED_DATE_MIN = '1900-01-01'`: Used as start for "from invoice date" deferrals
- `DEFERRED_DATE_MAX = '9999-12-31'`: Used as end for "until consumed" deferrals

---

## Wizard Flows

### Bank Reconciliation Wizard Flow

```
1. User opens bank statement
   → action_open_bank_reconciliation_widget()
   → Creates bank.rec.widget with st_line_id

2. Widget computes line_ids (liquidity line only initially)
   → User sees single bank transaction line

3. User clicks "Match" or selects auto-recon model
   → _js_action_apply_reco_model() / _js_action_add_new_amls()
   → Counterpart aml lines appear in widget

4. User adjusts accounts, taxes, analytic distribution
   → Widget recomputes state (valid/invalid)

5. User clicks "Validate"
   → _action_validate()
   → Creates/matches journal entries
   → Marks st_line as reconciled

6. Wizard closes, statement updated
```

### Lock Date Exception Wizard Flow

```
1. Manager opens Settings > Accounting > Lock Dates
   → wizard/model: account.change.lock.date

2. Sets hard_lock_date (irreversible warning shown)
   → Write to res.company

3. If posting blocked later (before hard_lock_date):
   → User sees "Hard lock date" error

4. Manager opens exception wizard
   → account.lock.exception form
   → Selects duration (5min/15min/1h/24h/forever)
   → Provides justification

5. Blocked user can post within exception window
   → All exceptions logged with reason + timestamp
```

### Auto-Reconciliation Cron Flow

```
1. Cron triggers (account_accountant_cron)
   → _cron_try_auto_reconcile_statement_lines()

2. FOR UPDATE SKIP LOCKED on statement lines
   → Gets batch_size (default 50) unreconciled lines

3. For each line:
   → _retrieve_partner() (4 strategies)
   → For each applicable recon model:
       → _is_applicable_for()
       → _get_invoice_matching_amls_candidates()
       → _check_rule_propositions()
   → If single valid proposition:
       → _auto_reconcile_lines()
       → Mark line as reconciled

4. All lines released
   → Next cron instance processes next batch
```

---

## See Also

- [Modules/Account](Modules/Account.md) — Core account.move, journal entries, reconcile models (base)
- [Modules/account_accountant](Modules/account_accountant.md) — This module (EE): bank rec widget, deferred, signing
- [Modules/Analytic](Modules/Analytic.md) — analytic_distribution Json field used by widget lines
- [Modules/base_setup](Modules/base_setup.md) — Bank account configuration, statement import
- [New Features/What's New](New-Features/What's-New.md) — Deferred entry changes, lock date exceptions
