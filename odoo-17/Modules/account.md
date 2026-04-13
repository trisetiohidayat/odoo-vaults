---
tags: [odoo, odoo17, module, account]
research_depth: deep
---

# Account Module — Deep Research

**Source:** `odoo/addons/account/models/`
**Files analyzed (full read):**
- `account_move.py` (251 KB) — account.move model
- `account_move_line.py` (178 KB) — account.move.line model
- `account_journal.py` (55 KB) — account.journal model
- `account_account.py` (50 KB) — account.account model
- `account_tax.py` (96 KB) — account.tax model
- `account_reconcile_model.py` (17 KB) — reconciliation rules
- `account_partial_reconcile.py` (32 KB) — partial reconciliation tracking
- `account_full_reconcile.py` (3.4 KB) — full reconciliation
- `account_move_line_tax_details.py` (27 KB) — tax detail helpers

---

## Module Architecture

The `account` module is the financial core of Odoo. It provides double-entry bookkeeping with full invoice lifecycle management, multi-currency support, tax computation, cash-basis taxation, and automated bank reconciliation.

```
account.move  (journal entry / invoice)
  └── account.move.line  (individual debit/credit lines)
        ├── account.account     (the ledger account)
        ├── account.tax         (applied taxes)
        ├── account.tax.group   (tax group for reporting)
        └── analytic.mixin      (analytic distribution)

Reconciliation Layer:
  account.move.line
    ├── matched_debit_ids  → account.partial.reconcile
    ├── matched_credit_ids → account.partial.reconcile
    └── full_reconcile_id  → account.full.reconcile

account.partial.reconcile
  └── exchange_move_id  → account.move (exchange difference entry)
  └── tax_cash_basis_rec_id → triggers CABA journal entry creation

account.reconcile.model
  └── account.reconcile.model.line (write-off rules)
  └── account.reconcile.model.partner.mapping (regex-based partner detection)

Journal Hierarchy:
  account.journal { type = sale }     → out_invoice, out_refund, out_receipt
  account.journal { type = purchase }  → in_invoice, in_refund, in_receipt
  account.journal { type = cash }     → payment entries
  account.journal { type = bank }     → bank statements + payments
  account.journal { type = general }  → manual journal entries (entry)
```

---

## Key Models (Deep)

### account.move

**File:** `account_move.py` (lines 79–4564)
**Inherits:** `portal.mixin`, `mail.thread.main.attachment`, `mail.activity.mixin`, `sequence.mixin`
**SQL constraints:**
- Unique partial index on `(name, journal_id)` WHERE `state = 'posted' AND name != '/'` (line 642)
- Index on `(journal_id, state, payment_state, move_type, date)` for dashboard queries (line 637)
- Index on `(journal_id, sequence_prefix desc, sequence_number+1 desc)` for gap detection (line 646)

#### Complete Field Table

**Accounting / Core fields (lines 112–284):**
| Field | Type | Notes |
|---|---|---|
| `name` | Char | Entry number; computed via `_compute_name`; inverse `_inverse_name`; copy=False; trigram index |
| `ref` | Char | Reference; copy=False; trigram index |
| `date` | Date | Accounting date; computed from `invoice_date` unless overridden; precompute |
| `state` | Selection | `draft` → `posted` → `cancel`; required, readonly |
| `move_type` | Selection | `entry`, `out_invoice`, `out_refund`, `in_invoice`, `in_refund`, `out_receipt`, `in_receipt` |
| `is_storno` | Boolean | Storno accounting flag; computed from company setting |
| `journal_id` | Many2one | Journal; computed from `move_type` via `_compute_journal_id` |
| `company_id` | Many2one | Company; computed from journal; indexed |
| `line_ids` | One2many | Journal items (`account.move.line`); copy=True |
| `payment_id` | Many2one | Set if this move was created by `account.payment` |
| `statement_line_id` | Many2one | Set if created by bank statement import |
| `statement_id` | Many2one | Related from statement_line |

**Hash / Inalterability fields (lines 279–283):**
| Field | Type | Notes |
|---|---|---|
| `restrict_mode_hash_table` | Boolean | Related from journal; enables hash chain |
| `secure_sequence_number` | Integer | Gapless sequence number for inalterability |
| `inalterable_hash` | Char | SHA-256 hash of entry content |
| `string_to_hash` | Char | Concatenation of hashed fields |

**Cash basis fields (lines 209–234):**
| Field | Type | Notes |
|---|---|---|
| `tax_cash_basis_rec_id` | Many2one | `account.partial.reconcile` that triggered CABA entry |
| `tax_cash_basis_origin_move_id` | Many2one | Original invoice/receipt that generated CABA entries |
| `tax_cash_basis_created_move_ids` | One2many | CABA entries generated from this move |
| `always_tax_exigible` | Boolean | True if no payable/receivable lines; CABA never needed |

**Auto-post fields (lines 236–258):**
| Field | Type | Notes |
|---|---|---|
| `auto_post` | Selection | `no`, `at_date`, `monthly`, `quarterly`, `yearly` |
| `auto_post_until` | Date | End date for recurring auto-post |
| `auto_post_origin_id` | Many2one | First recurring entry in chain |
| `posted_before` | Boolean | True if ever posted; blocks type switching |
| `hide_post_button` | Boolean | True if `date > today` with auto_post |

**Invoice fields (lines 288–588):**
| Field | Type | Notes |
|---|---|---|
| `invoice_line_ids` | One2many | Filtered: `display_type IN ('product', 'line_section', 'line_note')` |
| `invoice_date` | Date | Document date |
| `invoice_date_due` | Date | Due date; computed from payment terms |
| `delivery_date` | Date | For delivery-based invoicing |
| `invoice_payment_term_id` | Many2one | Payment term (e.g., NET 30) |
| `needed_terms` | Binary | JSON blob of payment schedule lines |
| `narration` | Html | Terms and conditions |
| `partner_id` | Many2one | Customer or vendor |
| `commercial_partner_id` | Many2one | Root commercial partner |
| `partner_shipping_id` | Many2one | Delivery address |
| `partner_bank_id` | Many2one | Bank account for payment QR code |
| `fiscal_position_id` | Many2one | Fiscal position for tax/account mapping |
| `payment_reference` | Char | Payment reference / Odoo reference; trigram index |
| `invoice_origin` | Char | Source document (e.g., SO name) |
| `invoice_user_id` | Many2one | Salesperson |
| `invoice_cash_rounding_id` | Many2one | Cash rounding method |
| `quick_edit_mode` | Boolean | Fiduciary mode: enter total only |
| `quick_edit_total_amount` | Monetary | Expected total in quick edit mode |
| `is_move_sent` | Boolean | Invoice sent via EDI |
| `to_check` | Boolean | Manual "needs review" flag |
| `duplicated_ref_ids` | Many2many | Bills with same vendor ref (computed) |
| `need_cancel_request` | Boolean | Localization: requires government cancellation |
| `reversed_entry_id` | Many2one | The entry this move reverses |
| `reversal_move_id` | One2many | Inverse: entries that reverse this one |

**Amount fields — all computed + stored (lines 425–488):**
| Field | Type | Notes |
|---|---|---|
| `amount_untaxed` | Monetary | Subtotal before tax |
| `amount_tax` | Monetary | Total tax amount |
| `amount_total` | Monetary | Grand total |
| `amount_residual` | Monetary | Remaining due |
| `amount_total_signed` | Monetary | Signed total in company currency |
| `amount_residual_signed` | Monetary | Remaining due, signed |
| `tax_totals` | Binary | JSON for tax totals widget |
| `payment_state` | Selection | `not_paid`, `in_payment`, `paid`, `partial`, `reversed`, `invoicing_legacy` |

---

#### move_type Values (Complete List, lines 145–162)

```python
move_type = fields.Selection([
    ('entry',        'Journal Entry'),       # Manual journal entry
    ('out_invoice',  'Customer Invoice'),   # AR debit  — money owed TO company
    ('out_refund',   'Customer Credit Note'),# AR credit — money returned to customer
    ('in_invoice',   'Vendor Bill'),        # AP credit — money OWED by company
    ('in_refund',    'Vendor Credit Note'),  # AP debit  — money reclaimed from vendor
    ('out_receipt',  'Sales Receipt'),      # POS / immediate payment sale
    ('in_receipt',   'Purchase Receipt'),   # Immediate payment purchase
])
```

#### Document Classification Helpers (lines 4465–4497)

```python
def is_invoice(self, include_receipts=False):
    return self.is_sale_document(include_receipts) or self.is_purchase_document(include_receipts)

@api.model
def get_sale_types(self, include_receipts=False):
    return ['out_invoice', 'out_refund'] + (include_receipts and ['out_receipt'] or [])

def is_sale_document(self, include_receipts=False):
    return self.move_type in self.get_sale_types(include_receipts)

@api.model
def get_purchase_types(self, include_receipts=False):
    return ['in_invoice', 'in_refund'] + (include_receipts and ['in_receipt'] or [])

def is_inbound(self, include_receipts=True):   # Money coming TO company
    return self.move_type in ['out_invoice', 'in_refund'] + (include_receipts and ['out_receipt'] or [])

def is_outbound(self, include_receipts=True):  # Money going OUT
    return self.move_type in ['in_invoice', 'out_refund'] + (include_receipts and ['in_receipt'] or [])

# direction_sign (line 425):
# +1 for inbound (out_invoice, in_refund, out_receipt)
# -1 for outbound (in_invoice, out_refund, in_receipt)
```

---

#### action_post() — Full Implementation (line 4220)

```python
def action_post(self):  # account_move.py:4220
    """Public entry point called from the UI (Confirm button)."""
    moves_with_payments = self.filtered('payment_id')
    other_moves = self - moves_with_payments
    if moves_with_payments:
        moves_with_payments.payment_id.action_post()   # Post the payment move first
    if other_moves:
        other_moves._post(soft=False)                  # Then post remaining
    return False
```

---

#### _post() — Step-by-Step (line 3893)

The real work. Called with `soft=False` from UI, `soft=True` from auto-post scheduler.

**Step 1 — Access check (line 3907)**
```python
if not self.env.su and not self.env.user.has_group('account.group_account_invoice'):
    raise AccessError("You don't have the access rights to post an invoice.")
```

**Step 2 — Invoice validation (lines 3910–3946)**
```python
# For each invoice (move with move_type matching is_invoice()):
# - Quick edit total must match actual total
# - partner_bank_id must be active if set
# - Total must not be negative
# - Partner is required (sale: customer, purchase: vendor)
# - invoice_date auto-set to today for sales if missing
# - invoice_date must be set for purchases
```

**Step 3 — General move validation (lines 3948–3968)**
```python
# For each move:
# - Must be in draft state
# - Must have at least one non-section/non-note line
# - If soft=False and auto_post != 'no' with future date → raise
# - Journal must be active
# - Currency must be active
# - No deprecated accounts used
```

**Step 4 — Handle soft=True: future-dated moves (lines 3970–3979)**
```python
if soft:
    future_moves = self.filtered(lambda m: m.date > today)
    for move in future_moves:
        if move.auto_post == 'no':
            move.auto_post = 'at_date'   # Convert to at-date auto-post
        move.message_post(body=_(f"This move will be posted at: {date}"))
    to_post = self - future_moves  # Only immediate ones
else:
    to_post = self   # All posted immediately
```

**Step 5 — Lock date adjustment (lines 3981–3985)**
```python
for move in to_post:
    affects_tax_report = move._affect_tax_report()
    lock_dates = move._get_violated_lock_dates(move.date, affects_tax_report)
    if lock_dates:
        # Push date forward to first open period
        move.date = move._get_accounting_date(move.invoice_date or move.date, affects_tax_report)
```

**Step 6 — Analytic lines (line 3988)**
```python
to_post.line_ids._create_analytic_lines()   # Batch-create all at once
```

**Step 7 — Recurring copy (line 3991)**
```python
to_post.filtered(lambda m: m.auto_post not in ('no', 'at_date')
                 )._copy_recurring_entries()
```

**Step 8 — Fix partner inconsistencies (lines 3993–4001)**
```python
# Force all lines' partner to match commercial_partner_id
# (OCR or concurrent edits can cause mismatch)
```

**Step 9 — Write state='posted' (lines 4003–4011)**
```python
draft_reverse_moves = to_post.filtered(
    lambda m: m.reversed_entry_id and m.reversed_entry_id.state == 'posted'
)
to_post.write({
    'state': 'posted',
    'posted_before': True,
})
# Reconcile any draft reverse moves with their original
draft_reverse_moves.reversed_entry_id._reconcile_reversed_moves(...)
# Process I*-marked reconciliation imports
to_post.line_ids._reconcile_marked()
```

**Step 10 — Subscribe partner, schedule activity (lines 4014–4029)**

**Step 11 — Update partner ranks (lines 4031–4047)**
```python
# Increments customer_rank or supplier_rank on commercial_partner_id
# based on how many invoices/bills were posted
```

**Step 12 — Zero-amount paid hook (lines 4049–4052)**
```python
# For invoices where amount_total == 0, call _invoice_paid_hook()
# immediately (no payment needed)
```

---

#### button_draft() (line 4253)

```python
def button_draft(self):  # account_move.py:4253–4263
    if any(move.state not in ('cancel', 'posted') for move in self):
        raise UserError("Only posted/cancelled journal entries can be reset to draft")
    if any(move.need_cancel_request for move in self):
        raise UserError("You can't reset to draft those journal entries...")

    self._check_draftable()   # blocks: exchange diff moves, CABA entries, locked journals
    self.mapped('line_ids.analytic_line_ids').unlink()   # Delete analytic entries
    self.mapped('line_ids').remove_move_reconcile()       # Unlink partials (cascade → full)
    self.state = 'draft'
```

**`_check_draftable()` raises for:**
1. Exchange difference entries (have an `exchange_move_id` in full/partial reconcile)
2. Cash basis tax entries (have `tax_cash_basis_rec_id` or `tax_cash_basis_origin_move_id`)
3. Entries in strict-mode journals that are already posted

---

#### button_cancel() (line 4308)

```python
def button_cancel(self):  # account_move.py:4308–4318
    moves_to_reset_draft = self.filtered(lambda x: x.state == 'posted')
    if moves_to_reset_draft:
        moves_to_reset_draft.button_draft()   # Full cascade: analytic delete, reconcile unlink
    if any(move.state != 'draft' for move in self):
        raise UserError("Only draft journal entries can be cancelled")
    self.write({'auto_post': 'no', 'state': 'cancel'})
```

---

#### _compute_payment_state() (lines 1016–1100)

Called on every write to posted invoice lines that could affect payment state. Uses direct SQL on `account.partial.reconcile` for performance:

```python
def _compute_payment_state(self):
    # Group moves into 'posted_invoice' or 'unpaid'
    posted_invoices = self.filtered(lambda m: m.state == 'posted' and m.is_invoice(True))

    # SQL: for each receivable/payable line, find all counterparty lines
    # across all partial reconcilizations, grouping by source_move_id
    # Returns: has_payment, has_st_line, all_payments_matched, counterpart_move_types

    for invoice in posted_invoices:
        reconciliation_vals = payment_data.get(invoice.id, [])

        if currency.is_zero(invoice.amount_residual):
            if has_payment OR has_st_line:
                if all_payments_matched: → 'paid'
                else:                     → 'in_payment' via _get_invoice_in_payment_state()
            else:
                if reversed by credit note: → 'reversed'
                else:                        → 'paid'
        elif reconciliation_vals: → 'partial'
        else:                             → 'not_paid'
```

---

#### Reconciliation Helpers (lines 3681–3796)

```python
def _get_reconciled_amls(self):
    """ All move lines matched against this move's receivable/payable lines """
    reconciled_lines = self.line_ids.filtered(
        lambda l: l.account_id.account_type in ('asset_receivable', 'liability_payable')
    )
    return (reconciled_lines.mapped('matched_debit_ids.debit_move_id')
          + reconciled_lines.mapped('matched_credit_ids.credit_move_id'))

def _get_reconciled_payments(self):
    return self._get_reconciled_amls().move_id.payment_id

def _get_reconciled_invoices(self):
    return self._get_reconciled_amls().move_id.filtered(lambda m: m.is_invoice(include_receipts=True))

def _get_reconciled_statement_lines(self):
    return self._get_reconciled_amls().move_id.statement_line_id
```

---

### account.move.line

**File:** `account_move_line.py` (lines 20–3500+)
**Inherits:** `analytic.mixin`
**SQL indexes:**
- Composite index `(account_id, date)` created in `init()` for fast lookup
- Index on `move_id` (auto)
- `account_move_line_account_id_date_idx` — explicit

#### Complete Field Table

**Parent link fields (all `related` from move, stored + precomputed):**
| Field | Type | Notes |
|---|---|---|
| `move_id` | Many2one | Parent; required; `ondelete=cascade` |
| `journal_id` | Many2one | Related from move; store=True |
| `company_id` | Many2one | Related from move |
| `company_currency_id` | Many2one | Related from company |
| `move_name` | Char | Related `move.name`; btree index |
| `parent_state` | Selection | Related `move.state`; store=True |
| `date` | Date | Related `move.date` |
| `ref` | Char | Related `move.ref` |
| `move_type` | Selection | Related `move.move_type` |
| `is_storno` | Boolean | Related `move.is_storno` |

**Accounting fields (lines 86–148):**
| Field | Type | Notes |
|---|---|---|
| `account_id` | Many2one | Domain: not deprecated, not off_balance |
| `name` | Char | Line label |
| `debit` | Monetary | Positive debit; computed from balance |
| `credit` | Monetary | Positive credit; computed from balance |
| `balance` | Monetary | Net = debit - credit; write target for journal entries |
| `amount_currency` | Monetary | Amount in foreign currency |
| `currency_id` | Many2one | Foreign currency |
| `currency_rate` | Float | Company-to-document currency rate |
| `partner_id` | Many2one | Customer/vendor |
| `date_maturity` | Date | Due date for payable/receivable lines |

**Tax fields (lines 177–227):**
| Field | Type | Notes |
|---|---|---|
| `tax_ids` | Many2many | Taxes applied; `context={'active_test': False}` |
| `tax_line_id` | Many2one | If this IS a tax line |
| `tax_group_id` | Many2one | Tax group (from tax_line_id) |
| `tax_base_amount` | Monetary | Base amount for tax computation |
| `tax_repartition_line_id` | Many2one | Which repartition line generated this |
| `tax_tag_ids` | Many2many | Tags for tax report |
| `tax_tag_invert` | Boolean | Inverts tag sign for refunds/sales |
| `group_tax_id` | Many2one | For group taxes: the group that generated this |

**Reconciliation fields (lines 229–273):**
| Field | Type | Notes |
|---|---|---|
| `amount_residual` | Monetary | Original minus reconciled; computed via SQL |
| `amount_residual_currency` | Monetary | Same in foreign currency |
| `reconciled` | Boolean | True if both residuals are zero |
| `full_reconcile_id` | Many2one | Set on full reconciliation |
| `matched_debit_ids` | One2many | Partials where this is credit side |
| `matched_credit_ids` | One2many | Partials where this is debit side |
| `matching_number` | Char | `P123`=partial, `FROZEN-1`=full, `Ixxx`=import |
| `is_account_reconcile` | Boolean | Related from `account_id.reconcile` |

**Product / display fields (lines 291–375):**
| Field | Type | Notes |
|---|---|---|
| `display_type` | Selection | `product`, `cogs`, `tax`, `discount`, `rounding`, `payment_term`, `line_section`, `line_note`, `epd` |
| `product_id` | Many2one | Product |
| `quantity` | Float | Quantity; precomputed |
| `price_unit` | Float | Unit price |
| `discount` | Float | Discount % |
| `price_subtotal` | Monetary | Subtotal pre-tax |
| `price_total` | Monetary | Subtotal with tax |
| `product_uom_id` | Many2one | Unit of measure |

**Early payment discount fields (lines 386–400):**
| Field | Type | Notes |
|---|---|---|
| `discount_date` | Date | Last date for EPD |
| `discount_amount_currency` | Monetary | Amount to pay with EPD |
| `discount_balance` | Monetary | Same in company currency |

**Analytic (lines 377–383):**
| Field | Type | Notes |
|---|---|---|
| `analytic_distribution` | Json | Distribution by analytic account |
| `analytic_line_ids` | One2many | Generated analytic entries |

---

#### _compute_balance() (lines 651–667)

```python
def _compute_balance(self):
    for line in self:
        if line.display_type in ('line_section', 'line_note'):
            line.balance = False
        elif not line.move_id.is_invoice(include_receipts=True):
            # For journal entries: balance = -sum of all OTHER lines' balance
            # This enforces double-entry: total debit = total credit
            active_line_ids = [lid for lid in self.env.context.get('line_ids', [])
                             if isinstance(lid, int)]
            existing_lines = self.env['account.move.line'].browse(active_line_ids)
            outdated_lines = line.move_id.line_ids._origin
            new_lines = line.move_id.line_ids - line
            line.balance = -sum((existing_lines - outdated_lines + new_lines).mapped('balance'))
        else:
            # For invoices: balance stays 0; set explicitly via debit/credit
            line.balance = 0
```

---

#### _compute_debit_credit() (lines 670–677)

```python
def _compute_debit_credit(self):
    for line in self:
        if not line.is_storno:
            line.debit  = line.balance if line.balance > 0.0 else 0.0
            line.credit = -line.balance if line.balance < 0.0 else 0.0
        else:
            # Storno: sign convention is inverted
            line.debit  = line.balance if line.balance < 0.0 else 0.0
            line.credit = -line.balance if line.balance > 0.0 else 0.0
```

---

#### _compute_amount_residual() (lines 736–801)

```python
def _compute_amount_residual(self):
    """ residual = original balance - SUM(partial reconciliation amounts) """
    need_residual_lines = self.filtered(
        lambda x: x.account_id.reconcile
               or x.account_id.account_type in ('asset_cash', 'liability_credit_card')
    )
    stored_lines = need_residual_lines._origin

    # Direct SQL: sum all partial reconcile amounts per line in both currencies
    self._cr.execute('''
        SELECT part.debit_move_id AS line_id, 'debit' AS flag,
               COALESCE(SUM(part.amount), 0.0) AS amount,
               ROUND(SUM(part.debit_amount_currency), curr.decimal_places) AS amount_currency
        FROM account_partial_reconcile part
        JOIN res_currency curr ON curr.id = part.debit_currency_id
        WHERE part.debit_move_id IN %s
        GROUP BY part.debit_move_id, curr.decimal_places
        UNION ALL
        SELECT part.credit_move_id AS line_id, 'credit' AS flag,
               COALESCE(SUM(part.amount), 0.0) AS amount,
               ROUND(SUM(part.credit_amount_currency), curr.decimal_places) AS amount_currency
        FROM account_partial_reconcile part
        JOIN res_currency curr ON curr.id = part.credit_currency_id
        WHERE part.credit_move_id IN %s
        GROUP BY part.credit_move_id, curr.decimal_places
    ''', [aml_ids, aml_ids])

    # For each line:
    line.amount_residual = comp_curr.round(
        line.balance - debit_amount + credit_amount
    )
    line.amount_residual_currency = foreign_curr.round(
        line.amount_currency - debit_amount_currency + credit_amount_currency
    )
    line.reconciled = (
        comp_curr.is_zero(line.amount_residual)
        and foreign_curr.is_zero(line.amount_residual_currency)
    )
```

---

#### reconcile() Method (line 3130)

```python
def reconcile(self):  # account_move_line.py:3130
    """ Reconcile the current move lines all together. """
    return self._reconcile_plan([self])
```

**`_reconcile_plan(reconciliation_plan)` (lines 2513–2535):**
```python
def _reconcile_plan(self, reconciliation_plan):
    # plan: nested list of recordset groups
    # [account.move.line(1,2), account.move.line(3,4)]
    # = first reconcile 1+2, then reconcile 3+4
    plan_list, all_amls = self._optimize_reconciliation_plan(reconciliation_plan)
    move_container = {'records': all_amls.move_id}
    with all_amls.move_id._check_balanced(move_container),\
         all_amls.move_id._sync_dynamic_lines(move_container):
        self._reconcile_plan_with_sync(plan_list, all_amls)
```

**`_reconcile_plan_with_sync()` (lines 2537–2712) — core reconciliation engine:**

1. **Prefetch**: load all `move_id`, `matched_debit_ids`, `matched_credit_ids` for all amls in batch
2. **Collect residuals** into `aml_values_map` for performance
3. **Prepare partials**: call `_prepare_reconciliation_plan()` to compute amounts
4. **Create partials**: `account.partial.reconcile.create(partials_values_list)`
5. **Exchange diff moves**: if lines have different currencies, create exchange difference entries
6. **CABA entries**: for cash-basis taxes on receivable/payable, call `_create_tax_cash_basis_moves()`
7. **Full reconcile check**: if all residuals are zero for a group of lines → `account.full.reconcile` created
8. **Matching numbers**: updated via `_update_matching_number()`

**`remove_move_reconcile()` (line 3134):**
```python
def remove_move_reconcile(self):
    """ Undo reconciliation: just unlink all related partials """
    (self.matched_debit_ids + self.matched_credit_ids).unlink()
    # unlink() cascades: reverses CABA + exchange moves, unlinks full reconcile
```

---

#### _create_analytic_lines() (lines 3198–3208)

```python
def _create_analytic_lines(self):
    """ Called during _post() to create analytic items from line distribution """
    self._validate_analytic_distribution()
    analytic_line_vals = []
    for line in self:
        analytic_line_vals.extend(line._prepare_analytic_lines())
    context = dict(self.env.context)
    context.pop('default_account_id', None)
    self.env['account.analytic.line'].with_context(context).create(analytic_line_vals)
```

Each line's `_prepare_analytic_lines()` distributes balance proportionally across multiple analytic accounts, with rounding correction applied to the last entry.

---

### account.journal

**File:** `account_journal.py`

#### journal_type Values (lines 89–99)

```python
type = fields.Selection([
    ('sale',     'Sales'),        # Customer invoice journals (creates out_invoice, out_refund)
    ('purchase', 'Purchase'),     # Vendor bill journals (creates in_invoice, in_refund)
    ('cash',     'Cash'),         # Cash payment journals
    ('bank',     'Bank'),         # Bank statements + bank payment journals
    ('general',  'Miscellaneous'), # Manual journal entries (entry type)
])
```

#### Default Account by Type (lines 65–77)

```python
# account_journal.py: _get_default_account_domain()

if type == 'bank':     account_type in ('asset_cash', 'liability_credit_card')
if type == 'cash':     account_type in ('asset_cash',)
if type == 'sale':     account_type in ('income', 'income_other')
if type == 'purchase': account_type in ('expense', 'expense_depreciation', 'expense_direct_cost')
if type == 'general':  all account types including off_balance
```

#### Key Fields

| Field | Type | Notes |
|---|---|---|
| `name` | Char | Journal display name |
| `code` | Char(5) | Short code (e.g., "SAL", "BNK1") |
| `type` | Selection | sale/purchase/cash/bank/general |
| `company_id` | Many2one | |
| `currency_id` | Many2one | Foreign currency (for bank/cash in multi-currency) |
| `default_account_id` | Many2one | Default posting account |
| `account_control_ids` | Many2many | Whitelist of allowed accounts |
| `suspense_account_id` | Many2one | Bank suspense for unreconciled transactions |
| `restrict_mode_hash_table` | Boolean | Enables hash chain / inalterability |
| `sequence_override_regex` | Char | Override the sequence format |
| `invoice_reference_model` | Selection | How to generate payment refs: `odoo`, `europe`, `fi`, `nl`, `at`, `be`, `fr`, `de` |
| `refund_sequence` | Boolean | Separate sequence for refunds |
| `secure_sequence_id` | Many2one | Gapless sequence for inalterability |
| `alias_id` | Many2one | Email alias for EDI import |
| `profit_account_id` | Many2one | Gain account for cash rounding |
| `loss_account_id` | Many2one | Loss account for cash rounding |

---

### account.account

**File:** `account_account.py` (50 KB)

#### All 18 Account Types (lines 51–75)

```python
account_type = fields.Selection([
    # ===== ASSETS =====
    ("asset_receivable",     "Receivable"),            # AR — MUST reconcile=True
    ("asset_cash",           "Bank and Cash"),         # Bank/cash accounts
    ("asset_current",        "Current Assets"),        # Inventory, short-term assets
    ("asset_non_current",   "Non-current Assets"),    # Long-term assets
    ("asset_prepayments",    "Prepayments"),           # Prepaid expenses
    ("asset_fixed",          "Fixed Assets"),          # PP&E, vehicles, buildings

    # ===== LIABILITIES =====
    ("liability_payable",    "Payable"),               # AP — MUST reconcile=True
    ("liability_credit_card","Credit Card"),           # Credit card payables
    ("liability_current",   "Current Liabilities"),  # Short-term payables
    ("liability_non_current","Non-current Liabilities"),# Long-term debt

    # ===== EQUITY =====
    ("equity",               "Equity"),                # Capital, reserves
    ("equity_unaffected",    "Current Year Earnings"), # P&L — ONE per company!

    # ===== INCOME =====
    ("income",               "Income"),                # Revenue
    ("income_other",         "Other Income"),         # Non-operating income

    # ===== EXPENSES =====
    ("expense",              "Expenses"),              # Operating expenses
    ("expense_depreciation", "Depreciation"),         # Depreciation expense
    ("expense_direct_cost",  "Cost of Revenue"),       # COGS / direct costs

    # ===== OTHER =====
    ("off_balance",          "Off-Balance Sheet"),    # Excluded from financial reports
])
```

#### Internal Group (computed, lines 456–464)

```python
def _compute_internal_group(self):
    for account in self:
        if account.account_type == 'off_balance':
            account.internal_group = 'off_balance'
        else:
            account.internal_group = account.account_type.split('_')[0]
        # asset, liability, equity, income, expense, off_balance
```

#### Key Constraints

```python
@api.constrains('account_type', 'reconcile')
def _check_reconcile(self):
    # asset_receivable and liability_payable MUST have reconcile=True
    if account.account_type in ('asset_receivable', 'liability_payable') \
       and not account.reconcile:
        raise ValidationError("You cannot have a receivable/payable account "
                               "that is not reconcilable. (account code: %s)" % account.code)

@api.constrains('account_type')
def _check_account_type_unique_current_year_earning(self):
    # Only ONE equity_unaffected account per company allowed
    result = self._read_group(
        domain=[('account_type', '=', 'equity_unaffected')],
        groupby=['company_id'],
        aggregates=['id:recordset'],
        having=[('__count', '>', 1)],
    )
    for _company, accounts in result:
        raise ValidationError("You cannot have more than one account with "
                              "'Current Year Earnings' as type.")
```

#### Key Fields

| Field | Type | Notes |
|---|---|---|
| `code` | Char | Account number (e.g., "121000") |
| `name` | Char | Account name |
| `account_type` | Selection | 18 types above |
| `internal_group` | Selection | Computed: asset/liability/equity/income/expense/off_balance |
| `reconcile` | Boolean | Allow reconciliation on this account |
| `deprecated` | Boolean | Flag account as inactive |
| `company_id` | Many2one | |
| `tax_ids` | Many2many | Default taxes for this account |
| `tag_ids` | Many2many | Tags for custom reporting |
| `root_id` | Many2one | Computed root (first 2 chars); used for grouping |
| `note` | Text | Internal notes |
| `include_initial_balance` | Boolean | Bring balance forward from previous fiscal years |

---

### account.tax

**File:** `account_tax.py` (96 KB)
**Inherits:** `mail.thread`

#### amount_type / Tax Computation Types (lines 101–112)

```python
amount_type = fields.Selection([
    ('group',    'Group of Taxes'),           # Container; recursively expands children
    ('fixed',    'Fixed'),                    # Flat amount: quantity * abs(amount)
    ('percent',  'Percentage of Price'),      # e.g., 20% of price_unit
    ('division', 'Percentage of Price Tax Included'), # Reverse%: 180/(1-10%)=200
])
```

**Computation formulas (lines 592–620):**
```python
# fixed:
amount = quantity * abs(self.amount) * fixed_multiplicator

# percent, price_excluded:
amount = price_unit * quantity * (self.amount / 100.0)

# percent, price_included:
amount = price_unit * quantity - (price_unit * quantity / (1 + self.amount / 100.0))

# division, price_excluded:
amount = price_unit * quantity * (self.amount / (100.0 - self.amount))

# division, price_included:
amount = price_unit * quantity * self.amount / 100.0
```

#### tax_type / Type of Use (lines 98–99)

```python
type_tax_use = fields.Selection([
    ('sale',     'Sales'),     # Can be used on sales invoices
    ('purchase', 'Purchases'), # Can be used on vendor bills
    ('none',     'None'),      # Cannot be used alone; only in groups, or for adjustments
])
```

#### Tax Exigibility — Cash Basis vs. Invoice Basis (lines 142–152)

```python
tax_exigibility = fields.Selection([
    ('on_invoice', 'Based on Invoice'),   # Tax due when invoice is posted
    ('on_payment', 'Based on Payment'),   # Tax due when payment is received/made
])
```

When `on_payment`:
1. On invoice post: tax amount goes to `cash_basis_transition_account_id`
2. On reconciliation of the receivable/payable line: CABA entry is created proportionally
3. CABA entry debits/credits the proper tax account, reversing the transition account

#### compute_all() — Tax Computation Engine (line 671)

```python
def compute_all(self, price_unit, currency=None, quantity=1.0,
                product=None, partner=None, is_refund=False,
                handle_price_include=True, include_caba_tags=False,
                fixed_multiplicator=1):
    """ Returns: {
        'total_excluded': float,   # Subtotal without taxes
        'total_included': float,   # Subtotal with taxes
        'total_void': float,      # Total of taxes without account
        'base_tags': [tag_ids],
        'taxes': [{
            'id', 'name', 'amount', 'base', 'sequence',
            'account_id', 'refund_account_id', 'analytic',
            'price_include', 'tax_exigibility', 'tax_repartition_line_id',
            'group', 'tag_ids', 'tax_ids'
        }]
    }"""
```

**Algorithm (lines 718–870):**
1. Flatten: recursively expand `amount_type == 'group'` via `flatten_taxes_hierarchy()`
2. Rounding: `round_per_line` (default) or `round_globally` (company setting)
3. Iterate in **reversed sequence order** — compute base cumulatively so child taxes see updated base
4. `include_base_amount=True` on a tax → taxes with higher sequence add to parent's base
5. Strip tax from price first if `price_include=True` using formula above
6. Assign `tax_repartition_line_id` based on `is_refund` and document type

#### Repartition Lines (lines 153–174)

Each tax has two sets of `account.tax.repartition.line` records:
- `invoice_repartition_line_ids` — for invoices
- `refund_repartition_line_ids` — for refunds/credit notes

Each line:
- `account_id` — where tax amount is posted
- `factor_percent` — e.g., 100 (normal), 50 (partial), -100 (full reversal)
- `use_in_tax_closing` — include in tax report
- `tag_ids` — tags for tax report generation

#### tax_group_id — Tax Groups (lines 24–81)

```python
class AccountTaxGroup(models.Model):
    name = fields.Char()
    company_id = fields.Many2one('res.company')
    tax_payable_account_id = fields.Many2one  # Credit here when tax is due
    tax_receivable_account_id = fields.Many2one # Debit here when recoverable
    advance_tax_payment_account_id = fields.Many2one # Downpayments on tax account
    country_id = fields.Many2one('res.country')   # Country for this tax group
    preceding_subtotal = fields.Char()  # Label of subtotal before this group
```

---

### account_reconcile_model

**File:** `account_reconcile_model.py` (17 KB)

#### rule_type Values (lines 139–145)

```python
rule_type = fields.Selection([
    ('writeoff_button',    'Button to generate counterpart entry'),  # Manual write-off
    ('writeoff_suggestion', 'Rule to suggest counterpart entry'),    # Auto-suggestion
    ('invoice_matching',   'Rule to match invoices/bills'),          # Bank auto-match
])
```

#### All Conditions (lines 157–269)

| Field | Scope | Values |
|---|---|---|
| `match_text_location_label/note/reference` | Boolean | Search in statement label/note/reference |
| `match_journal_ids` | Journal | Only these bank/cash journals |
| `match_nature` | Amount | `amount_received`, `amount_paid`, `both` |
| `match_amount` | Amount | `lower`, `greater`, `between` |
| `match_amount_min` / `_max` | Amount | Threshold values |
| `match_label` / `match_label_param` | Label | `contains`, `not_contains`, `match_regex` |
| `match_note` / `match_note_param` | Note | same |
| `match_transaction_type` / `match_transaction_type_param` | Transaction type | same |
| `match_same_currency` | Currency | Boolean |
| `allow_payment_tolerance` | Tolerance | Boolean |
| `payment_tolerance_param` | Gap | Float (% or fixed amount) |
| `payment_tolerance_type` | Gap type | `percentage` / `fixed_amount` |
| `match_partner` | Partner | Boolean (partner must be set) |
| `match_partner_ids` | Partner | Whitelist of partners |
| `match_partner_category_ids` | Category | Partner category whitelist |
| `past_months_limit` | Age | Months to search back (default: 18) |
| `decimal_separator` | Regex | Locale-specific decimal separator |

#### account_reconcile_model.line.amount_type (lines 60–75)

```python
amount_type = fields.Selection([
    ('fixed',              'Fixed'),                      # Fixed write-off amount
    ('percentage',          'Percentage of balance'),      # % of remaining balance
    ('percentage_st_line',  'Percentage of statement line'),# % of bank line amount
    ('regex',              'From label'),                # Extract from label via regex
])
```

#### Partner Mapping (lines 11–36)

Regex-based partner detection during bank reconciliation:
- `payment_ref_regex`: matched against statement line payment reference
- `narration_regex`: matched against move narration

---

## account.partial.reconcile

**File:** `account_partial_reconcile.py` (32 KB)

Represents a **partial** match between two journal items — only part of the balance is matched. Multiple partial reconciliations accumulate on a line until it is fully matched.

### Fields

| Field | Type | Notes |
|---|---|---|
| `debit_move_id` | Many2one | The debit journal item |
| `credit_move_id` | Many2one | The credit journal item |
| `full_reconcile_id` | Many2one | Set when fully reconciled (groups all partials) |
| `exchange_move_id` | Many2one | Exchange difference move created |
| `amount` | Monetary | Amount in **company currency** (always positive) |
| `debit_amount_currency` | Monetary | Amount in debit line's foreign currency |
| `credit_amount_currency` | Monetary | Amount in credit line's foreign currency |
| `max_date` | Date | MAX(debit_line.date, credit_line.date) — for aged reports |

### unlink() Cascade (lines 100–133)

1. Collects linked exchange moves and CABA moves
2. Calls `super().unlink()` (removes partials, nullifies `full_reconcile_id` on lines)
3. Unlinks any orphaned `full_reconcile_id`
4. **Reverses** all CABA entries via `_reverse_moves(cancel=True)`
5. **Reverses** all exchange moves via `_reverse_moves(cancel=True)`
6. Updates `matching_number` on all affected lines

### _create_tax_cash_basis_moves() (lines 475–636)

Triggered during `_reconcile_plan_with_sync()` when a partial reconciliation involves a **cash-basis tax** on a receivable/payable account.

```python
def _create_tax_cash_basis_moves(self):
    """
    For each partial reconcile involving CABA taxes:
    1. Compute percentage paid = partial_amount / total_move_balance
    2. Create move in tax_cash_basis_journal:
       - For each base line: create base_line + counterpart (on transition account)
       - For each tax line: create tax_line + counterpart (on transition account)
    3. Group by (account, partner, currency, tax) to minimize entries
    4. Post the CABA move
    5. Reconcile counterpart lines with original lines
    """
    # Move date = max(partial.max_date, lock_date) or today
    # balance = amount_currency * percentage / payment_rate
```

### _update_matching_number() (lines 142–186)

Uses **Union-Find graph traversal** across partial reconciliation edges to assign `matching_number`:
- Part of `full_reconcile`: number = `full_reconcile_id.name`
- Partial only: number = `"P" + min(partial_ids_in_component)`
- Import-marked: number = `"I*" + matching_number` (processed later by `_reconcile_marked`)

---

## account.full.reconcile

**File:** `account_full_reconcile.py` (3.4 KB)

### Fields

| Field | Type | Notes |
|---|---|---|
| `partial_reconcile_ids` | One2many | All partial reconciliations in this group |
| `reconciled_line_ids` | One2many | All fully-matched journal items |
| `exchange_move_id` | Many2one | Exchange difference entry |

### unlink() (lines 13–36)

1. Collects exchange moves linked via `exchange_move_id`
2. Calls `super().unlink()` — removes full reconcile, nullifies `full_reconcile_id` on lines
3. Reverses all exchange moves via `_reverse_moves(cancel=True)`

### create() (lines 38–71)

Uses `cr.execute_values()` for bulk SQL update of `full_reconcile_id` on all lines and partials in a single round-trip — high-performance bulk operation.

---

## account_move_line_tax_details.py (27 KB)

Helper model for tax report engine. Provides `_compute_tax_lines_details()` which builds per-line, per-tax breakdowns used to populate tax report grids (tax tags × fiscal positions).

---

## Invoicing Flow

### Customer Invoice Flow

```
1. CREATE DRAFT
   account.move: state='draft', move_type='out_invoice'
   name = '/' (not assigned)
   invoice_line_ids: [product lines + tax lines]
   Fiscal position auto-applied → maps accounts and taxes
   price_subtotal/price_total recomputed via tax_ids._compute_all()

2. CONFIRM → action_post()
   a. Validates: customer required, total >= 0, journal active
   b. Assigns name via journal sequence
   c. Sets date (possibly adjusted for lock dates)
   d. Creates analytic lines (line_ids._create_analytic_lines)
   e. Sets state='posted', posted_before=True
   f. Reconciles any draft reverse moves
   g. Updates commercial_partner_id.customer_rank++
   h. If amount_total == 0: calls _invoice_paid_hook() immediately
   i. Subscribes partner to message thread
   j. Schedules follow-up activity if configured

3. PAYMENT
   User: "Register Payment" → action_register_payment()
   → account.payment created
   → payment move created: [bank/debit, receivable/credit]
   → payment.action_post() → posts payment move
   → On reconciliation:
      account.partial.reconcile created
      If CABA taxes: _create_tax_cash_basis_moves()
      If fully matched: account.full.reconcile created
      payment_state → 'in_payment' (partial) → 'paid' (full)

4. PAYMENT WIDGET (js_assign_outstanding_line, line 4229)
   Called from payment widget on invoice form
   → reconciles suggested bank statement line with invoice receivable line
```

### Vendor Bill Flow

```
1. CREATE DRAFT
   account.move: state='draft', move_type='in_invoice'
   line_ids: [expense/debit, payable/credit] + [tax/debit, payable/credit]
   vendor required, invoice_date required

2. CONFIRM → action_post()
   Same as customer invoice but:
   - Checks vendor required (not customer)
   - Updates commercial_partner_id.supplier_rank++

3. PAYMENT
   Similar to customer invoice, but reversed direction
   → payment: debit bank, credit payable
   → Reconciles payable line
```

---

## Chart of Accounts Structure

### Account Type Behaviors

| Account Type | Initial Balance | Reconciliation | Rounding |
|---|---|---|---|
| `asset_receivable` | Carried forward | **Required** | Per line |
| `liability_payable` | Carried forward | **Required** | Per line |
| `asset_cash` | Carried forward | Optional | Per line |
| `asset_current` | Carried forward | No | Per line |
| `asset_fixed` | Carried forward | No | Per line |
| `income` | **Reset to 0** | No | Per line |
| `income_other` | **Reset to 0** | No | Per line |
| `expense` | **Reset to 0** | No | Per line |
| `expense_direct_cost` | **Reset to 0** | No | Per line |
| `equity` | Carried forward | No | Per line |
| `equity_unaffected` | Auto-updated | No | Per line |
| `off_balance` | Excluded | No | N/A |

**Reset accounts (P&L):** On fiscal year opening, `include_initial_balance=False` means the account balance starts at 0. Revenue/expense accounts do NOT carry forward — they accumulate during the year, then close to `equity_unaffected` (Current Year Earnings) at year-end.

### Tax Distribution via Repartition Lines

```
For a sale tax at 20%:
  invoice_repartition_line_ids:
    Line 1 (Invoice): account_id = tax_payable_account, factor = 100%
    Line 2 (Refund):  account_id = tax_payable_account, factor = -100%

For a purchase tax with partial recovery (80%):
  invoice_repartition_line_ids:
    Line 1: account_id = tax_receivable_account, factor = 80%
    Line 2: account_id = recovery_loss_account,    factor = 20%
```

---

## SQL Constraints and Indexes

```sql
-- Only posted moves with real name must be unique per journal
CREATE UNIQUE INDEX account_move_unique_name
  ON account_move(name, journal_id)
  WHERE (state = 'posted' AND name != '/')

-- Gap detection for inalterability
CREATE INDEX account_move_sequence_index3
  ON account_move (journal_id, sequence_prefix desc, (sequence_number+1) desc)

-- Dashboard fast filter
CREATE INDEX account_move_payment_idx
  ON account_move (journal_id, state, payment_state, move_type, date)

-- AML fast lookup by account+date
CREATE INDEX account_move_line_account_id_date_idx
  ON account_move_line (account_id, date)

-- Inalterability gapless sequence
CREATE UNIQUE INDEX account_move_secure_sequence_idx
  ON account_move (secure_sequence_number)
```

---

## See Also

- [Modules/Payment](Modules/Payment.md) — `account.payment` model, payment workflows
- [Modules/AccountAnticipation](Modules/AccountAnticipation.md) — early payment discounts, EPD
- [Modules/AccountFollowup](Modules/AccountFollowup.md) — partner payment follow-up / dunning
- [Modules/AccountBatchPayment](Modules/AccountBatchPayment.md) — batch payment processing
- [Modules/AccountDebitNote](Modules/AccountDebitNote.md) — debit note issuance
- [Modules/AccountTaxCalculation](Modules/AccountTaxCalculation.md) — tax calculation details
- [Tools/ORM Operations](Tools/ORM-Operations.md) — `search()`, `browse()`, `write()` fundamentals
- [Patterns/Security Patterns](Patterns/Security-Patterns.md) — ACL CSV, `ir.rule` for account records
