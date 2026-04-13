---
tags: [odoo, odoo17, flow, account, reconciliation, payment]
---

# Account Reconciliation Flow — Odoo 17

Complete guide to how Odoo 17 reconciles invoices with payments, covering partial reconciliation, full reconciliation, exchange differences, and cash basis taxes.

## Core Architecture

### Three Reconciliation Models

| Model | File | Purpose | Created When |
|-------|------|---------|-------------|
| `account.partial.reconcile` | `account/models/account_partial_reconcile.py` | Partial match of two lines | Partial payment, overpayment, or first payment on invoice |
| `account.full.reconcile` | `account/models/account_full_reconcile.py` | Complete match of a group | All lines in group reach `amount_residual = 0` |
| Bank Statement Line | `account/models/account_bank_statement.py` | Manual bank matching | User matches bank line to invoice |

### Core Fields on `account.move.line`

**File:** `account/models/account_move_line.py:L229-273`

```python
amount_residual          # Monetary  — remaining amount in company currency
amount_residual_currency # Monetary  — remaining amount in foreign currency
reconciled              # Boolean   — True when amount_residual = 0
full_reconcile_id       # Many2one  — set when fully reconciled
matched_debit_ids        # One2many  — partials where this line is credit_move_id
matched_credit_ids       # One2many  — partials where this line is debit_move_id
matching_number           # Char      — display label, e.g. "P123" or "4523"
```

`matched_debit_ids` and `matched_credit_ids` are the inverse of `credit_move_id` and `debit_move_id` on `account.partial.reconcile`, forming a bidirectional link.

---

## How Reconciliation Works — Step by Step

### Entry Points

1. **Manual reconcile**: User selects lines in the journal entries list and clicks **Reconcile**
   - Calls `account.move.line.reconcile()` at line 3130
2. **Payment registration**: User registers a payment from an invoice
   - `account.payment.register` wizard calls `_create_payments()` (line 933)
   - Which calls `_reconcile_payments()` (line 907)
   - Which calls `.reconcile()` on filtered lines
3. **Automatic reconciliation**: Cron job runs `account.automatic.reconciliation.wizard`

All three paths eventually call `self._reconcile_plan([self])`.

---

### `_reconcile_plan()` — Plan-Based Reconciliation

**File:** `account/models/account_move_line.py:L2513`

```python
def _reconcile_plan(self, reconciliation_plan):
    plan_list, all_amls = self._optimize_reconciliation_plan(reconciliation_plan)
    with all_amls.move_id._check_balanced(move_container),\
         all_amls.move_id._sync_dynamic_lines(move_container):
        self._reconcile_plan_with_sync(plan_list, all_amls)
```

The plan is a nested structure:
- `[aml1, aml2]` — reconcile aml1 first, then aml2
- `[[aml1, aml2], [aml3, aml4]]` — reconcile inner list sequentially, then cross-reconcile filtered unreconciled lines

---

### `_optimize_reconciliation_plan()` — Sorting & Currency Splitting

**File:** `account/models/account_move_line.py:L2406`

Key operations:
1. Sort all lines by maturity date (or `date`), then by currency
2. **Split by currency**: if lines use different foreign currencies, they are placed in separate sub-nodes and reconciled independently
3. Validate no cross-account or cross-company reconciliation is attempted

Sorting key:
```python
sorted(key=lambda aml: (
    aml.date_maturity or aml.date,   # oldest first
    aml.currency_id,
    aml.amount_currency,
    aml.balance,
))
```

---

### `_reconcile_plan_with_sync()` — The 10-Step Engine

**File:** `account/models/account_move_line.py:L2537`

This is the core reconciliation engine. Each step is described below.

#### Step 1 — Prefetch and Hook
```python
all_amls.move_id
all_amls.matched_debit_ids
all_amls.matched_credit_ids
pre_hook_data = all_amls._reconcile_pre_hook()
```
Populates the ORM cache for all related fields and calls a hook for subclasses to react before reconciliation begins.

#### Step 2 — Collect Residual Values
```python
aml_values_map = {
    aml: {
        'aml': aml,
        'amount_residual': aml.amount_residual,
        'amount_residual_currency': aml.amount_residual_currency,
    }
    for aml in all_amls
}
```
Reads `amount_residual` and `amount_residual_currency` once and caches them. These drive all partial amount computations.

#### Step 3 — Build Partial Values
```python
for plan in plan_list:
    plan_results = self._prepare_reconciliation_plan(plan, amls_values_map)
    for results in plan_results:
        partials_values_list.append(results['partial_values'])
        if results.get('exchange_values'):
            exchange_diff_values_list.append(results['exchange_values'])
```
For each pair of lines in the plan, computes the partial amount to reconcile (the minimum of both lines' residuals) and any exchange difference to create.

#### Step 4 — Create Partial Reconciles
```python
partials = self.env['account.partial.reconcile'].create(partials_values_list)
```
Inserts `account.partial.reconcile` records. On create, `_update_matching_number()` assigns a `matching_number` to all involved lines.

#### Step 5 — Exchange Difference Moves
```python
exchange_moves = self._create_exchange_difference_moves(exchange_diff_values_list)
for index, exchange_move in zip(exchange_diff_partial_index, exchange_moves):
    partials[index].exchange_move_id = exchange_move
```
If invoice and payment use different exchange rates, an exchange difference move is created:
- **Debit side** (receivable/payable): adjusts the residual amount
- **Credit side**: goes to exchange gain or loss account

#### Step 6 — Cash Basis Tax (CABA) Entries
```python
for plan in plan_list:
    if is_cash_basis_needed(plan['amls'].account_id):
        plan['partials']._create_tax_cash_basis_moves()
```
Only triggered for receivable/payable accounts when `tax_exigibility = 'on_payment'` is enabled. See CABA section below.

#### Step 7 — Full Reconciliation Check
```python
for plan in plan_list:
    for aml in plan['amls']:
        involved_amls = plan['amls']._filter_reconciled_by_number(number2lines)
        is_fully_reconciled = all(
            is_line_reconciled(involved_aml, has_multiple_currencies)
            for involved_aml in involved_amls
        )
```
After partials are created, checks whether every line in each matching group has reached zero residual. Groups lines by their `matching_number` to find connected components.

#### Step 8 — Full Exchange Differences
```python
exchange_moves = self._create_exchange_difference_moves(exchange_diff_values_list)
for full_batch_index, exchange_move in zip(exchange_diff_full_batch_index, exchange_moves):
    full_batch['exchange_move'] = exchange_move
    exchange_move_lines = exchange_move.line_ids.filtered(lambda l: l.account_id == amls.account_id)
    full_batch['amls'] |= exchange_move_lines
```
For fully reconciled groups, any remaining minor exchange differences (rounding) are booked here.

#### Step 9 — Create `account.full.reconcile`
```python
for full_batch_index, full_batch in enumerate(full_batches):
    involved_partials = amls.matched_debit_ids + amls.matched_credit_ids
    if full_batch['is_fully_reconciled']:
        full_reconcile_values_list.append({
            'exchange_move_id': full_batch.get('exchange_move') and full_batch['exchange_move'].id,
            'partial_reconcile_ids': [Command.link(partial.id) for partial in involved_partials],
            'reconciled_line_ids': [Command.link(aml.id) for aml in amls],
        })
self.env['account.full.reconcile'].create(full_reconcile_values_list)
```
Creates `account.full.reconcile` records linking all partials and all lines in the fully reconciled group. Bulk-written to `full_reconcile_id` on lines using `cr.execute_values`.

#### Step 10 — Post Hook
```python
all_amls._reconcile_post_hook(pre_hook_data)
```
Called after all records are committed. Invoices transition to `payment_state = 'paid'`.

---

## The `matching_number` — Union-Find Algorithm

**File:** `account/models/account_partial_reconcile.py:L142`

### Data Structure
Each `account.partial.reconcile` is an **edge** in a graph. Each `account.move.line` is a **node**. A connected component = one matching number.

### Assignment Logic (on partial create)
```python
number2lines = {}  # matching_number → list of line ids
line2number = {}   # line id → matching_number (its root)

for partial in all_partials.sorted('id'):
    debit_min_id = line2number.get(partial.debit_move_id.id)
    credit_min_id = line2number.get(partial.credit_move_id.id)

    if debit_min_id and credit_min_id:       # merge two graphs
        if debit_min_id != credit_min_id:
            min_min_id = min(debit_min_id, credit_min_id)
            max_min_id = max(debit_min_id, credit_min_id)
            for line_id in number2lines[max_min_id]:
                line2number[line_id] = min_min_id
            number2lines[min_min_id].extend(number2lines.pop(max_min_id))
    elif debit_min_id:                        # add credit node to existing graph
        number2lines[debit_min_id].append(partial.credit_move_id.id)
        line2number[partial.credit_move_id.id] = debit_min_id
    elif credit_min_id:                       # add debit node to existing graph
        number2lines[credit_min_id].append(partial.debit_move_id.id)
        line2number[partial.debit_move_id.id] = credit_min_id
    else:                                     # new isolated graph
        number2lines[partial.id] = [partial.debit_move_id.id, partial.credit_move_id.id]
        line2number[partial.debit_move_id.id] = partial.id
        line2number[partial.credit_move_id.id] = partial.id
```

### Display Format
- Partial only: `'P' + str(partial.id)` — e.g., `P4821`
- Full reconcile: the `full_reconcile_id` as text — e.g., `4523`
- Import temporary: starts with `'I'` — see `_reconcile_marked()`

### SQL Assignment (bulk)
```sql
UPDATE account_move_line l
   SET matching_number = CASE
           WHEN l.full_reconcile_id IS NOT NULL THEN l.full_reconcile_id::text
           ELSE 'P' || source.number
       END
  FROM (VALUES %s) AS source(number, ids)
 WHERE l.id = ANY(source.ids)
```
Written in bulk via `execute_values` for performance.

---

## Partial Reconciliation Details

### Fields on `account.partial.reconcile`

| Field | Type | Description |
|-------|------|-------------|
| `debit_move_id` | Many2one | The debit line (receivable increases, payable decreases) |
| `credit_move_id` | Many2one | The credit line (payment side) |
| `full_reconcile_id` | Many2one | Set when all lines in group are fully reconciled |
| `exchange_move_id` | Many2one | Link to exchange difference move |
| `amount` | Monetary | Amount reconciled in company currency (always positive) |
| `debit_amount_currency` | Monetary | Amount in debit line's foreign currency |
| `credit_amount_currency` | Monetary | Amount in credit line's foreign currency |
| `debit_currency_id` | Many2one | Related to debit_move_id.currency_id |
| `credit_currency_id` | Many2one | Related to credit_move_id.currency_id |
| `company_id` | Many2one | Company; from invoice side if move is an invoice |
| `max_date` | Date | Max of the two line dates — used for aged reports |

### Creating a Partial Reconcile (SQL structure)
```sql
INSERT INTO account_partial_reconcile
  (debit_move_id, credit_move_id, amount,
   debit_amount_currency, credit_amount_currency, currency_id, company_id)
VALUES
  (invoice_line_id, payment_line_id, 600.0,
   600.0, 600.0, currency_id, company_id);
```

### Reversing a Partial Reconcile
```python
def unlink(self):
    full_to_unlink = self.full_reconcile_id
    all_reconciled = self.debit_move_id + self.credit_move_id
    moves_to_reverse = self.env['account.move'].search([
        ('tax_cash_basis_rec_id', 'in', self.ids)
    ])
    moves_to_reverse += self.exchange_move_id
    res = super().unlink()
    full_to_unlink.unlink()          # removes full reconcile if now orphaned
    moves_to_reverse._reverse_moves(default_values_list, cancel=True)
    self._update_matching_number(all_reconciled)  # recompute matching numbers
```

---

## Exchange Difference

### When It Occurs
- Invoice posted in foreign currency (e.g., USD)
- Payment posted at a different exchange rate
- Exchange rate changes between invoice date and payment date

### Example
```
Invoice: 1000 USD @ 1.20 = €1200 company currency
Payment:  1000 USD @ 1.10 = €1100 company currency
Loss:              €100 company currency
```

### How Odoo Handles It
1. During `_prepare_reconciliation_amls()`, computes the difference between the invoice's residual (in company currency) and the payment amount (converted at payment rate)
2. If non-zero, adds exchange diff values to `exchange_diff_values_list`
3. Creates a separate `account.move` (type: 'entry') with:
   - DR/CR to the same receivable/payable account (completing the match)
   - CR/DR to exchange gain/loss account
4. Links the exchange move to the partial via `exchange_move_id`

### Configuration
```python
# In ir.config_parameter:
account.disable_partial_exchange_diff = True  # disables exchange diff creation
```

---

## Cash Basis Tax (CABA)

### When It Is Used
Taxes with `tax_exigibility = 'on_payment'` (not the default `on_invoice`). Requires `tax_calculation_rounding_method = 'round_globally'` for full compatibility.

### How CABA Works

**Trigger:** After a partial reconcile is created for a line with CABA taxes on a receivable/payable account.

#### Step A — Collect Values
```python
def _collect_tax_cash_basis_values(self):
    for partial in self:
        for move in {partial.debit_move_id.move_id, partial.credit_move_id.move_id}:
            move_values = move._collect_tax_cash_basis_values()
            # Compute percentage = partial_amount / total_move_balance
            # If foreign currency: percentage = partial_amount_currency / total_move_amount_currency
```
The percentage represents what fraction of the invoice has been paid.

#### Step B — Create Cash Basis Move
```python
def _create_tax_cash_basis_moves(self):
    for move_values in tax_cash_basis_values_per_move.values():
        for partial_values in move_values['partials']:
            # For each line in the original invoice:
            amount_currency = line.amount_currency * partial_values['percentage']
            balance = amount_currency / payment_rate

            # Create mirrored CABA line:
            # DR/CR to tax receivable/payable account
            # CR/DR to base account
```
Each invoice line gets a proportional CABA entry created.

#### Step C — Reconcile CABA Tax Lines
```python
for lines, move_index, sequence in to_reconcile_after:
    counterpart_line = moves[move_index].line_ids.filtered(...)
    reconciliation_plan.append((counterpart_line + lines))
self.env['account.move.line']._reconcile_plan(reconciliation_plan)
```
Tax lines on the transfer account are reconciled with their counterpart CABA lines.

### What Gets Recorded
For a CABA tax at 20% on a €1000 invoice (paid 60% = €600):
- Base amount: €600 × 20% = €120 proportional base
- Tax amount: €120 × 20% rate = €24 proportional tax

---

## Manual Reconciliation

### From Invoice Form
1. Open a posted invoice
2. Click **Add payments** button
3. Select one or more payment journal items
4. Click **Validate** → triggers `reconcile()`

### From Journal Entries List
1. Go to **Accounting > Journal Entries**
2. Select multiple lines on the same account
3. Click **Reconcile** button
4. Wizard shows total debit/credit and difference
5. Optionally enter a write-off amount
6. Confirm → `reconcile()` called

### `_check_amls_exigibility_for_reconciliation()`
Before any reconciliation:
- All lines must be `posted`
- All lines must be on the **same account**
- All lines must be **not already reconciled**
- Account must have `reconcile = True` (or be cash/credit card type)

---

## Payment Registration Flow

**File:** `account/wizard/account_payment_register.py:L933`

```
User clicks "Register Payment" on invoice
    │
    ├── _get_batches()           — groups invoice lines by partner/currency/account
    │
    ├── _create_payment_vals_from_wizard()
    │       — computes amount, currency, payment date
    │       — handles early payment discounts (EPD)
    │
    ├── _init_payments()         — creates account.payment record
    │
    ├── _post_payments()          — posts the payment move
    │
    └── _reconcile_payments()     ← key step
            │
            for each payment batch:
            │
            ├── Filter payment lines for receivable/payable account
            │
            ├── Filter invoice lines for same account, not yet reconciled
            │
            ├── Add forced exchange rate if writeoff_is_exchange_account
            │
            └── (payment_lines + invoice_lines).reconcile()
                    → calls _reconcile_plan([...])
                    → creates partial(s), possibly full reconcile
```

---

## Reversing a Reconciliation

```python
# Via UI: "Unreconcile" button on journal entry lines
line.remove_move_reconcile()
# Internally:
(line.matched_debit_ids + line.matched_credit_ids).unlink()
```

The `unlink()` on partials handles:
- Deleting the `account.full.reconcile` if it becomes orphaned
- Reversing any exchange difference moves
- Reversing any CABA moves
- Recomputing `matching_number` on all affected lines

---

## See Also
- [Modules/account](Modules/account.md) — `account.move`, `account.move.line`
- [Flows/Cross-Module/analytic-distribution-flow](Flows/Cross-Module/analytic-distribution-flow.md) — analytic distribution
- [Flows/Sale/full-sale-to-cash-flow](Flows/Sale/full-sale-to-cash-flow.md) — sale reconciliation end-to-end
- [Flows/Purchase/full-purchase-to-payment-flow](Flows/Purchase/full-purchase-to-payment-flow.md) — purchase reconciliation end-to-end
