# Flows/Account/invoice-post-flow.md

# Invoice Post Flow — Odoo 15

## Overview

Invoice posting is the action that validates a draft invoice, making it permanent in the accounting records. After posting, the invoice creates actual journal entries and becomes due for payment.

**Source**: `addons/account/models/account_move.py`

---

## Pre-Post State: Draft

A draft invoice (`state='draft'`) is editable:
- Can add/remove invoice lines
- Can modify quantities, prices, taxes
- Has no journal entry lines yet (only draft representation)
- Cannot be reconciled

```
account.move state = 'draft'
    │
    ├── name = '/' (sequence not assigned)
    ├── line_ids = draft lines
    │       └─► debit/credit not finalized
    └── payment_state = False
```

---

## The `action_post()` Method

```python
def action_post(self):
    """Main entry point to post an invoice"""
    self._post(soft=True)
    return True

def _post(self, soft=True):
    for move in self:
        if move.state != 'draft':
            continue

        # 1. Cash rounding validation
        move._notify_cash_rounding()

        # 2. Validate constraints
        move._validate_constrains_date_company()

        # 3. Recompute tax lines
        move._recompute_tax_lines()

        # 4. Create analytic lines (soft=only if not yet)
        if soft:
            move._create_analytic_lines()

        # 5. Hash lock for restricted journals
        if move.journal_id.restrict_mode_hash_table:
            move._constrains_date_sequence()

        # 6. Compute sequence number
        move._compute_name()

        # 7. Finalize
        move.write({'state': 'posted'})
```

---

## Step 1: Cash Rounding Validation

For invoices with cash rounding configured:

```python
def _notify_cash_rounding(self):
    """Check and apply cash rounding differences"""
    for move in self:
        rounding = move.currency_id.rounding
        total = sum(move.line_ids.mapped('debit'))
        if abs(total - move.amount_total) > rounding / 2:
            # Create rounding adjustment line
            diff = move.amount_total - total
            move.line_ids.create({
                'move_id': move.id,
                'account_id': move.company_id.cash_rounding_account_id.id,
                'name': 'Cash Rounding',
                'balance': diff,
            })
```

---

## Step 2: Constraint Validation

```python
def _validate_constrains_date_company(self):
    """Validate before posting"""
    for move in self:
        # Check date is within fiscal year
        if not move.company_id.fiscalyear_lock_date or \
           move.date > move.company_id.fiscalyear_lock_date:
            raise UserError(_("The date is locked for this period"))

        # Check all required fields
        if not move.line_ids:
            raise UserError(_("Cannot post an invoice without lines"))

        # Check line balances
        for line in move.line_ids:
            if not line.account_id:
                raise UserError(_("Line %s has no account", line.name))
```

---

## Step 3: Tax Line Recomputation

Tax lines are recomputed to ensure accuracy:

```python
def _recompute_tax_lines(self, recompute_tax_base_amount=False):
    """Recompute tax amounts from product lines"""
    for move in self:
        # 1. Remove existing tax lines
        move.line_ids.filtered('tax_line_id').unlink()

        # 2. Group taxes by tax_id from all product lines
        tax_map = {}
        for line in move.line_ids.filtered(
            lambda l: l.move_id.move_type != 'entry' and l.price_subtotal
        ):
            for tax in line.tax_ids.flatten_taxes_hierarchy():
                if tax.id not in tax_map:
                    tax_map[tax.id] = {
                        'tax': tax,
                        'base': 0.0,
                    }
                tax_map[tax.id]['base'] += line.balance

        # 3. Create new tax lines
        for tax_id, vals in tax_map.items():
            tax = vals['tax']
            base_amount = vals['base']
            tax_amount = tax.compute_all(base_amount)

            # Get account from repartition line
            rep_line = tax.invoice_repartition_line_ids.filtered(
                lambda r: r.account_id
            )
            account_id = rep_line.account_id.id if rep_line else None

            move.line_ids.create({
                'move_id': move.id,
                'account_id': account_id,
                'name': tax.name,
                'tax_line_id': tax.id,
                'tax_ids': [(5, 0, 0)],
                'balance': -tax_amount,
                'tax_tag_ids': [(6, 0, rep_line.mapped('tag_ids').ids)] if rep_line else [(5, 0, 0)],
            })
```

---

## Step 4: Analytic Line Creation

```python
def _create_analytic_lines(self):
    """Create analytic entries for each invoice line"""
    for move in self:
        for line in move.line_ids.filtered(
            lambda l: l.analytic_account_id and l.move_id.state = 'posted'
        ):
            # Create analytic line
            self.env['account.analytic.line'].create({
                'name': line.name,
                'account_id': line.analytic_account_id.id,
                'date': line.date,
                'amount': line.credit - line.debit,
                'product_id': line.product_id.id,
                'product_uom_id': line.product_uom_id.id,
                'unit_amount': line.quantity,
                'ref': line.ref,
                'partner_id': line.partner_id.id,
                'company_id': line.company_id.id,
            })
```

---

## Step 5: Hash Lock (Integrity)

For journals with `restrict_mode_hash_table=True`:

```python
def _constrains_date_sequence(self):
    """Lock the move against tampering after posting"""
    self.ensure_one()

    # Generate hash from all line values
    hash = self._generate_hash()
    self.write({
        'secure_hash': hash,
        'secure_hash_sequence': self.journal_id.sequence_id.number_next_actual,
    })
```

---

## Step 6: Sequence Number Assignment

```python
def _compute_name(self):
    """Assign sequence number to move"""
    for move in self:
        if move.name == '/':
            move.name = move.journal_id.sequence_id.next_by_id()
```

---

## Post-Result: State = Posted

After `action_post()`, the invoice state changes:

```
BEFORE (draft):
account.move
    ├── name = '/'         (not assigned)
    ├── state = 'draft'
    └── line_ids = draft lines

AFTER (posted):
account.move
    ├── name = 'INV/2023/0001'  (sequence assigned)
    ├── state = 'posted'
    ├── line_ids = finalized lines
    │       ├── Receivable line (debit)
    │       ├── Revenue line (credit)
    │       └── Tax line (credit)
    ├── payment_state = 'not_paid'
    └── amount_residual = amount_total
```

---

## Journal Entry Structure (Customer Invoice)

```
Invoice #INV/2023/0001
Customer: PT XYZ
Date: 2023-12-01
Subtotal: Rp 100,000,000
VAT 11%: Rp 11,000,000
Total: Rp 111,000,000

┌─────────────────────────────────┬───────┬─────────┐
│ Account                        │ Debit │ Credit  │
├────────────────────────────────┼───────┼─────────┤
│ 1200 - Accounts Receivable     │111,000,000       │
│ 4000 - Sales Revenue           │        │100,000,000│
│ 2200 - Output VAT Payable      │        │11,000,000 │
└────────────────────────────────┴───────┴─────────┘
```

---

## Journal Entry Structure (Vendor Bill)

```
Bill #BILL/2023/0001
Vendor: Supplier ABC
Date: 2023-12-01
Subtotal: Rp 50,000,000
VAT 11%: Rp 5,500,000
Total: Rp 55,500,000

┌─────────────────────────────────┬───────┬─────────┐
│ Account                        │ Debit │ Credit  │
├────────────────────────────────┼───────┼─────────┤
│ 5100 - Expenses                │ 50,000,000        │
│ 2100 - Input VAT               │  5,500,000        │
│ 2200 - Accounts Payable        │        │55,500,000 │
└────────────────────────────────┴───────┴─────────┘
```

---

## Tax Tags Assignment

During posting, tax lines get `tax_tag_ids` from repartition lines:

```python
# Tax line after posting
account.move.line
    ├── tax_line_id = account.tax (e.g., PPN 11%)
    ├── tax_tag_ids = [tag.id]  # from invoice_repartition_line_ids
    └── account_id = tax account (from repartition)
```

**Tax Tag → Tax Report**:

```
Invoice posted
    │
    └─► Tax line created with:
            tax_tag_ids = +tax_11_output
            balance = 11,000,000 (credit)

Tax Report computation:
    │
    └─► SUM(lines with +tax_11_output)
              - SUM(lines with -tax_11_output)
              = Balance for "PPN Keluaran" line
```

---

## Payment State Transition

After posting, the invoice enters the payment cycle:

```
┌─────────────────────────────────────────────────┐
│ INVOICE STATE TRANSITIONS                        │
├─────────────────────────────────────────────────┤
│                                                  │
│  draft ──[action_post()]──► posted               │
│                                  │                │
│                                  ▼                │
│                            payment_state         │
│                                  │                │
│              ┌───────────────────┼───────────────┐│
│              ▼                   ▼               ▼│
│         not_paid           partial          paid │
│              │                   │               │
│              │                   │               │
│              ▼                   ▼               ▼│
│         in_payment          in_payment      fully │
│              │                   │          reconciled
│              ▼                   ▼               │
│            paid                paid              │
│                                                  │
└─────────────────────────────────────────────────┘
```

---

## Reversal

Invoices can be reversed using the reversal wizard:

```python
def action_reverse_moves(self):
    """Open reversal wizard"""
    return {
        'name': 'Reverse Invoice',
        'view_mode': 'form',
        'res_model': 'account.move.reversal',
        'target': 'new',
        'context': {
            'active_ids': self.ids,
            'active_model': 'account.move',
        },
    }
```

**Reversal creates**:
- New journal entry with opposite debit/credit
- Links via `reversal_of` relation
- If the original was paid, creates credit note

---

## Related Flows

- [Flows/Account/invoice-creation-flow](odoo-19/Flows/Account/invoice-creation-flow.md) — Draft invoice creation
- [Flows/Account/payment-flow](odoo-19/Flows/Account/payment-flow.md) — Payment registration
- [Flows/Cross-Module/sale-stock-account-flow](odoo-19/Flows/Cross-Module/sale-stock-account-flow.md) — Full business cycle
- [Modules/Account](odoo-18/Modules/account.md) — Core account models

---

**Source**: `addons/account/models/account_move.py`
