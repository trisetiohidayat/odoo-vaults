# Odoo 18 Account Module - L3 Documentation

## Module Overview
**Path:** `~/odoo/odoo18/odoo/addons/account/models/`
**Purpose:** Core accounting functionality - journal entries, invoices, payments, taxes, reconciliation

---

## Core Models

### 1. account.move (Journal Entry / Invoice)

#### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Move number, computed from sequence, can be '/' for draft |
| `move_type` | Selection | entry, out_invoice, out_refund, in_invoice, in_refund, out_receipt, in_receipt |
| `date` | Date | Accounting date |
| `journal_id` | Many2one | Journal for this entry |
| `line_ids` | One2many | Journal items (account.move.line) |
| `state` | Selection | draft, posted, cancel |
| `partner_id` | Many2one | Commercial partner |
| `commercial_partner_id` | Many2one | Commercial entity (company or individual) |
| `currency_id` | Many2one | Document currency |
| `company_currency_id` | Many2one | Company currency |
| `invoice_date` | Date | Invoice date |
| `invoice_date_due` | Date | Due date |
| `invoice_payment_term_id` | Many2one | Payment terms |
| `amount_untaxed` | Monetary | Subtotal before tax |
| `amount_tax` | Monetary | Tax amount |
| `amount_total` | Monetary | Grand total |
| `amount_residual` | Monetary | Remaining amount due |
| `payment_state` | Selection | not_paid, in_payment, paid, partial, reversed, blocked |
| `fiscal_position_id` | Many2one | Fiscal position |
| `auto_post` | Selection | no, at_date, monthly, quarterly, yearly |
| `reversed_entry_id` | Many2one | Original entry being reversed |
| `is_storno` | Boolean | Storno accounting enabled |
| `inalterable_hash` | Char | Hash for audit trail |
| `secure_sequence_number` | Integer | Inalterability sequence number |

#### State Machine

```
draft → posted → cancel
```

#### Key Methods

**`_post(soft=True)`** - Validates and posts the move
- Validates: partner required, no negative total, required dates, no deprecated accounts
- Checks lock dates
- Creates analytic lines
- Sets state to 'posted'
- Reconciles reversed entries if applicable
- Updates customer/supplier ranks

**`_reverse_moves(default_values_list, cancel)`** - Creates reversal entries
- Creates mirror entries with opposite balances
- If cancel=True, reconciles original with reversal

**`_compute_amount()`** - Computes untaxed, tax, total, residual amounts

**`_collect_tax_cash_basis_values()`** - Collects data for cash basis tax entries

#### Cross-Model Relationships

| Relationship | Model | Purpose |
|--------------|-------|---------|
| `line_ids` | account.move.line | Journal items |
| `invoice_line_ids` | account.move.line | Invoice lines only (subset) |
| `matched_payment_ids` | account.payment | Payments reconciled |
| `statement_line_id` | account.bank.statement.line | Bank statement origin |
| `tax_cash_basis_origin_move_id` | account.move | Cash basis source |

#### Edge Cases & Failure Modes

1. **Sequence gaps**: Moves breaking natural sequence get `made_sequence_gap=True`
2. **Lock date violations**: `_post()` checks fiscal lock dates
3. **Duplicate names**: SQL constraint `unique_name` prevents duplicates
4. **Currency mismatch**: `invoice_currency_rate` tracks rate changes
5. **Auto-post**: Recurring entries created via `_copy_recursive_entries()`
6. **Reversal without cancel**: Creates draft reversal, must be posted separately
7. **Zero amount invoices**: Triggers `_invoice_paid_hook()` automatically

---

### 2. account.move.line (Journal Item)

#### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `move_id` | Many2one | Parent journal entry |
| `account_id` | Many2one | Account to post to |
| `debit` | Monetary | Debit amount |
| `credit` | Monetary | Credit amount |
| `balance` | Monetary | Signed balance |
| `amount_currency` | Monetary | Amount in foreign currency |
| `currency_id` | Many2one | Foreign currency |
| `partner_id` | Many2one | Partner |
| `tax_ids` | Many2many | Taxes applied |
| `tax_line_id` | Many2one | Tax that generated this line |
| `tax_repartition_line_id` | Many2one | Tax distribution line |
| `tax_tag_ids` | Many2many | Tags for reports |
| `analytic_distribution` | JSON | Analytic account distribution |
| `date_maturity` | Date | Due date |
| `amount_residual` | Monetary | Unreconciled amount |
| `full_reconcile_id` | Many2one | Full reconciliation reference |
| `matched_debit_ids` | One2many | Partial reconciliations (debits) |
| `matched_credit_ids` | One2many | Partial reconciliations (credits) |
| `reconciled` | Boolean | Fully reconciled flag |
| `display_type` | Selection | product, cogs, tax, discount, rounding, payment_term, line_section, line_note |
| `product_id` | Many2one | Product |
| `quantity` | Float | Quantity |
| `price_unit` | Float | Unit price |

#### SQL Constraints

```python
# No negative debit AND credit simultaneously
"CHECK(credit * debit = 0 OR display_type IN ('line_section', 'line_note'))"

# Currency sign must match balance sign
"CHECK(balance * amount_currency >= 0)"

# Non-accountable lines have no balance
"CHECK(display_type IN ('line_section', 'line_note') OR account_id IS NOT NULL)"
```

#### Key Methods

**`_compute_amount_residual()`** - Computes residual amounts
- Queries `account_partial_reconcile` for matched amounts
- Sets `reconciled=True` when residual is zero

**`_compute_debit_credit()`** - Computes debit/credit from balance
- Handles storno accounting (reversed signs)

**`_create_analytic_lines()`** - Creates analytic entries from distribution

#### Storno Accounting Behavior

When `is_storno=True`:
- Debit/Credit computation is reversed
- Credit = positive balance, Debit = negative balance
- Affects how reconciliation and reporting work

---

### 3. account.journal (Journal)

#### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Journal name |
| `code` | Char | Short code |
| `type` | Selection | sale, purchase, cash, bank, general |
| `default_account_id` | Many2one | Default account |
| `currency_id` | Many2one | Currency |
| `company_id` | Many2one | Company |
| `profit_account_id` | Many2one | Profit journal account |
| `loss_account_id` | Many2one | Loss journal account |
| `restrict_mode_hash_table` | Boolean | Audit mode |
| `sequence_override_regex` | Char | Custom sequence regex |

#### Journal Types

| Type | Purpose | Typical Accounts |
|------|---------|------------------|
| `sale` | Customer invoices | Receivable |
| `purchase` | Vendor bills | Payable |
| `cash` | Cash transactions | Cash account |
| `bank` | Bank transactions | Bank account |
| `general` | Miscellaneous | Various |

---

### 4. account.payment (Payment)

#### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Payment number (from sequence) |
| `date` | Date | Payment date |
| `amount` | Monetary | Payment amount (must be >= 0) |
| `payment_type` | Selection | inbound, outbound |
| `partner_type` | Selection | customer, supplier |
| `partner_id` | Many2one | Customer/Supplier |
| `journal_id` | Many2one | Payment journal |
| `destination_account_id` | Many2one | Receivable/Payable account |
| `outstanding_account_id` | Many2one | Liquidity account |
| `move_id` | Many2one | Generated journal entry |
| `state` | Selection | draft, in_process, paid, canceled, rejected |
| `is_reconciled` | Boolean | Fully reconciled |
| `is_matched` | Boolean | Matched with bank statement |
| `payment_method_line_id` | Many2one | Payment method |
| `payment_reference` | Char | Reference/Check number |

#### Payment Flow

```
draft → in_process → paid
         ↓
      canceled
         ↓
      rejected
```

#### Key Methods

**`_prepare_move_line_default_vals(write_off_line_vals, force_balance)`**
- Creates liquidity and counterpart lines
- Handles write-off amounts
- Computes currency conversions

**`_seek_for_lines()`** - Returns (liquidity_lines, counterpart_lines, writeoff_lines)

#### Cross-Model Relationships

| Relationship | Model | Purpose |
|--------------|-------|---------|
| `move_id` | account.move | Generated journal entry |
| `invoice_ids` | account.move | Invoices being paid |
| `origin_payment_id` | account.payment | Payment that created entry |

---

### 5. account.tax (Tax)

#### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Tax name |
| `type_tax_use` | Selection | sale, purchase, none |
| `tax_scope` | Selection | service, consu, None |
| `amount_type` | Selection | group, percent, fixed, division |
| `amount` | Float | Tax rate/amount |
| `price_include` | Boolean | Tax included in price |
| `include_base_amount` | Boolean | Affects subsequent tax bases |
| `is_base_affected` | Boolean | Affected by previous taxes |
| `children_tax_ids` | Many2many | Child taxes (for groups) |
| `tax_exigibility` | Selection | on_invoice, on_payment |
| `cash_basis_transition_account_id` | Many2one | Transition account |
| `invoice_repartition_line_ids` | One2many | Invoice distribution |
| `refund_repartition_line_ids` | One2many | Refund distribution |
| `tax_group_id` | Many2one | Tax group |
| `analytic` | Boolean | Include in analytic |

#### Amount Types

| Type | Description | Formula |
|------|-------------|---------|
| `group` | Collection of taxes | Sum of children |
| `percent` | Percentage of price | `price * (1 + amount/100)` |
| `fixed` | Fixed amount per unit | `quantity * amount` |
| `division` | Tax included price | `price / (1 - amount/100)` |

#### Tax Exigibility

| Mode | When Tax Due | Mechanism |
|------|--------------|-----------|
| `on_invoice` | Invoice validation | Immediate entry |
| `on_payment` | Payment received | Cash basis entries via partial reconcile |

#### Edge Cases

1. **Tax groups**: Must have at least one child tax
2. **Price included**: Affects base computation for subsequent taxes
3. **Negative factor**: Used for reverse-charge taxes (e.g., +100%/-100%)
4. **Country-specific**: Tax applicability based on `country_id`

---

### 6. account.tax.group (Tax Group)

#### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Group name |
| `tax_payable_account_id` | Many2one | Payable account for tax |
| `tax_receivable_account_id` | Many2one | Receivable account for tax |
| `advance_tax_payment_account_id` | Many2one | Downpayment account |
| `country_id` | Many2one | Country |
| `preceding_subtotal` | Char | Label for subtotal grouping |

---

### 7. account.payment.term (Payment Terms)

#### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Payment term name |
| `line_ids` | One2many | Payment term lines |
| `early_discount` | Boolean | Early payment discount enabled |
| `discount_percentage` | Float | Discount percentage |
| `discount_days` | Integer | Days for early discount |
| `early_pay_discount_computation` | Selection | included, excluded, mixed |

#### Payment Term Line Fields

| Field | Type | Description |
|-------|------|-------------|
| `value` | Selection | percent, fixed |
| `value_amount` | Float | Percentage or fixed amount |
| `delay_type` | Selection | days_after, days_after_end_of_month, etc. |
| `nb_days` | Integer | Number of days |
| `days_next_month` | Char | Days in next month (1-31) |

#### Key Methods

**`_compute_terms(date_ref, currency, company, ...)`** - Computes payment schedule
- Handles percentages and fixed amounts
- Applies early payment discounts
- Respects cash rounding

**`_get_due_date(date_ref)`** - Computes due date based on delay type

#### Constraints

- Sum of percentages must equal 100%
- Early discount only allowed with single 100% line
- Discount percentage must be positive
- Discount days must be positive

---

### 8. account.fiscal.position (Fiscal Position)

Maps taxes and accounts for specific partner/ship-to scenarios.

#### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Position name |
| `auto_apply` | Boolean | Auto-apply based on VAT |
| `vat_required` | Boolean | Require VAT number |
| `country_id` | Many2one | Country |
| `state_ids` | Many2many | States |
| `zip_from` | Char | Zip range start |
| `zip_to` | Char | Zip range end |
| `account_ids` | One2many | Account mappings |
| `tax_ids` | One2many | Tax mappings |

#### Key Methods

**`map_account(account)`** - Maps source account to destination

**`map_tax(tax)`** - Maps source tax to destination

---

### 9. account.partial.reconcile (Partial Reconciliation)

Links debit and credit lines for partial reconciliation.

#### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `debit_move_id` | Many2one | Debit journal item |
| `credit_move_id` | Many2one | Credit journal item |
| `amount` | Monetary | Reconciled amount (company currency) |
| `debit_amount_currency` | Monetary | Debit amount (foreign currency) |
| `credit_amount_currency` | Monetary | Credit amount (foreign currency) |
| `full_reconcile_id` | Many2one | Full reconciliation |
| `exchange_move_id` | Many2one | Exchange difference move |

#### Key Methods

**`unlink()`** - Handles cascade deletion
- Unlinks full reconciliation
- Reverses cash basis entries
- Updates payment states

**`_collect_tax_cash_basis_values()`** - Collects data for cash basis entries

---

### 10. account.full.reconcile (Full Reconciliation)

Complete reconciliation linking multiple partial reconciliations.

#### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Reconciliation reference |
| `partial_reconcile_ids` | One2many | Child partial reconciliations |
| `reconciled_line_ids` | One2many | Fully reconciled lines |

---

## Reconciliation Flow

### Partial Reconciliation
1. When payment matches invoice partially:
   - `account.partial.reconcile` created
   - Lines' `amount_residual` updated
   - Payment state changes from 'in_process' to 'paid' when full

### Full Reconciliation
1. When all lines fully reconciled:
   - `account.full.reconcile` created
   - All partials linked
   - Lines marked as `reconciled=True`

### Exchange Difference
- When currencies differ and rates change:
  - Exchange move created automatically
  - Linked via `exchange_move_id`

### Cash Basis Tax Reconciliation
1. Invoice posted with `tax_exigibility='on_payment'`
2. On partial payment:
   - `_collect_tax_cash_basis_values()` called
   - Proportional tax entry created
   - Links to partial via `tax_cash_basis_rec_id`

---

## Workflow Triggers

| Event | Model | Action |
|-------|-------|--------|
| Post invoice | account.move | Validates, locks, creates analytic lines |
| Reverse invoice | account.move | Creates reversal entry |
| Create payment | account.payment | Generates journal entry |
| Reconcile | account.move.line | Updates residuals, creates partials |
| Cash basis payment | account.partial.reconcile | Creates tax entries |

---

## Common Patterns

### Invoice Workflow
```python
# Create invoice
move = self.env['account.move'].create(vals)
# Add lines
move.line_ids.create(...)
# Post
move.action_post()
# Payment
payment = self.env['account.payment'].create(...)
payment.action_post()
# Reconciliation happens automatically
```

### Manual Reconciliation
```python
# Reconcile lines
lines = move1.line_ids + move2.line_ids
lines.reconcile()
# Undo reconciliation
lines.remove_move_reconcile()
```

### Tax Computation
```python
# On invoice line, taxes computed via:
taxes = tax_ids._compute_taxes({
    'unit_price': line.price_unit,
    'quantity': line.quantity,
    'product_id': line.product_id,
})
```

---

## Security Considerations

1. **Lock dates**: Prevent posting to locked periods
2. **Audit trail**: Hash validation for inalterable entries
3. **Tax exclusivity**: Tax selection restricted by country
4. **Reconciliation validation**: Currency and account type checks

---

## Performance Considerations

1. **Batch processing**: `_create_analytic_lines()` batch creates
2. **Caching**: Heavy use of `@api.depends` for computed fields
3. **Indexing**: Strategic indexes on `date`, `state`, `company_id`
4. **Partial reconciliation**: Avoids full-table reconciliation

---

## Key Hooks/Extension Points

| Method | Purpose |
|--------|---------|
| `_affect_tax_report()` | Determine tax report impact |
| `_get_accounting_date()` | Compute effective posting date |
| `_find_and_set_purchase_orders()` | Link to PO (hook for purchase module) |
| `_invoice_paid_hook()` | Custom action on invoice payment |
| `_create_analytic_lines()` | Create analytic entries |

---

## Database Indexes

```sql
-- Performance indexes
CREATE INDEX account_move_payment_idx ON account_move(journal_id, state, payment_state, move_type, date);
CREATE INDEX account_move_unique_name ON account_move(name, journal_id) WHERE state = 'posted' AND name != '/';
CREATE INDEX account_move_journal_id_company_id_idx ON account_move(journal_id, company_id, date);
```

---

## Related Modules

- `account_payment`: Payment transaction integration
- `account_edi`: Electronic document exchange
- `account_tax_python`: Python-based tax computation
- `account_check_printing`: Check printing support
