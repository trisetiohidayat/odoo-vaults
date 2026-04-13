# Flows/Account/payment-flow.md

# Payment Flow — Odoo 15

## Overview

Payments in Odoo 15 are represented as journal entries with special structure. They can be registered manually or automatically matched against open invoices through reconciliation.

**Source**: `addons/account/models/account_payment.py`

---

## Payment Model

`account.payment` is a special record that inherits from `account.move` via `_inherits`.

```python
class AccountPayment(models.Model):
    _name = "account.payment"
    _inherits = {'account.move': 'move_id'}
    _inherit = ['mail.thread', 'mail.activity.mixin']
```

### Field Inheritance

When you read a payment field like `date`, `journal_id`, `amount` — these come from the underlying `account.move` record (via `_inherits`).

---

## Payment Structure

### Journal Entry Created

Each payment creates a journal entry with a specific structure:

```
account.move (for payment)
    │
    ├── Line 1: Liquidity line
    │       account_id = bank/cash account (outstanding)
    │       debit/credit = amount (direction based on payment_type)
    │
    ├── Line 2: Counterpart line
    │       account_id = destination (receivable/payable)
    │       debit/credit = opposite of liquidity line
    │
    └── Line 3: Write-off line (optional)
            account_id = write-off account
            debit/credit = payment difference
```

### Example: Customer Payment

```
Customer pays Rp 1,000,000 (out_invoice)

Bank Journal Entry:
┌─────────────────────────────────────┬───────┬─────────┐
│ Account                            │ Debit │ Credit  │
├─────────────────────────────────────┼───────┼─────────┤
│ 1110 - Bank BCA                    │1,000,000        │
│ 1120 - Accounts Receivable         │        │1,000,000│
└─────────────────────────────────────┴───────┴─────────┘
```

### Example: Vendor Payment

```
Pay vendor Rp 500,000 (in_invoice)

Bank Journal Entry:
┌─────────────────────────────────────┬───────┬─────────┐
│ Account                            │ Debit │ Credit  │
├─────────────────────────────────────┼───────┼─────────┤
│ 2110 - Accounts Payable            │ 500,000         │
│ 1110 - Bank BCA                    │        │ 500,000 │
└─────────────────────────────────────┴───────┴─────────┘
```

---

## Payment Fields

| Field | Type | Description |
|-------|------|-------------|
| `payment_type` | Selection | `inbound` / `outbound` |
| `partner_type` | Selection | `customer` / `supplier` |
| `amount` | Monetary | Payment amount |
| `currency_id` | Many2one | Currency |
| `partner_id` | Many2one | Customer or supplier |
| `destination_account_id` | Many2one | Computed destination account |
| `outstanding_account_id` | Many2one | Computed outstanding account |
| `payment_method_line_id` | Many2one | Payment method |
| `journal_id` | Many2one | Bank/cash journal |
| `date` | Date | Payment date |
| `is_internal_transfer` | Boolean | Internal transfer flag |
| `paired_internal_transfer_payment_id` | Many2one | Paired payment |

---

## Destination Account Computation

```python
def _compute_destination_account_id(self):
    """Compute the account to use as counterpart"""
    self.ensure_one()

    if self.partner_type == 'customer':
        return self.partner_id.property_account_receivable_id
    elif self.partner_type == 'supplier':
        return self.partner_id.property_account_payable_id
```

## Outstanding Account Computation

```python
def _compute_outstanding_account_id(self):
    """Compute the bank/cash account"""
    self.ensure_one()

    if self.payment_method_line_id.payment_account_id:
        # Custom account from payment method
        return self.payment_method_line_id.payment_account_id
    else:
        # Default to journal's default account
        return self.journal_id.default_account_id
```

---

## Payment Creation

### Via Wizard

```
account.move (invoice)
    └─► action_register_payment()
          └─► account.payment.register (wizard)
                └─► action_create_payments()
                      └─► account.payment.create()
                            └─► _create_payment_journal_entry()
```

**Wizard Parameters**:
- `line_ids`: Invoice lines to pay
- `journal_id`: Payment journal
- `payment_date`: Payment date
- `amount`: Payment amount (auto-computed if not set)
- `payment_difference_handling`: `open` | `reconcile` | `writeoff`

### Code Flow

```python
def action_create_payments(self):
    payments = self.env['account.payment']
    for wizard in self:
        # Compute destination account
        if wizard.partner_id:
            if wizard.partner_type == 'customer':
                dest_account = wizard.partner_id.property_account_receivable_id
            else:
                dest_account = wizard.partner_id.property_account_payable_id
        else:
            dest_account = wizard.journal_id.default_account_id

        # Create payment
        payment = payments.create({
            'payment_type': 'inbound' if wizard.partner_type == 'customer' else 'outbound',
            'partner_type': wizard.partner_type,
            'partner_id': wizard.partner_id.id,
            'amount': wizard.amount,
            'currency_id': wizard.currency_id.id,
            'journal_id': wizard.journal_id.id,
            'date': wizard.payment_date,
            'destination_account_id': dest_account.id,
        })
        payments += payment

    # Post payments
    payments.action_post()
    return payments
```

---

## Internal Transfers

Internal transfers create two paired payments.

```python
# Internal transfer between journals
source_payment = payment.create({
    'payment_type': 'outbound',
    'destination_journal_id': dest_journal.id,
    'is_internal_transfer': True,
})

# Paired payment automatically created
paired_payment = self.env['account.payment'].browse(
    source_payment.paired_internal_transfer_payment_id
)
```

**Journal Entry (Source)**:
```
┌─────────────────────────────────────┬───────┬─────────┐
│ Account                            │ Debit │ Credit  │
├─────────────────────────────────────┼───────┼─────────┤
│ 1110 - Bank BCA (source)           │        │ 1,000,000│
│ 1111 - Outstanding Receipts        │1,000,000         │
└─────────────────────────────────────┴───────┴─────────┘
```

**Journal Entry (Destination)**:
```
┌─────────────────────────────────────┬───────┬─────────┐
│ Account                            │ Debit │ Credit  │
├─────────────────────────────────────┼───────┼─────────┤
│ 1112 - Bank Mandiri (dest)         │1,000,000         │
│ 1111 - Outstanding Receipts        │        │1,000,000│
└─────────────────────────────────────┴───────┴─────────┘
```

---

## Reconciliation

### Manual Reconciliation

```python
def action_register_final():
    """Reconcile selected lines manually"""
    lines = self.env['account.move.line']
    for rec in self:
        lines += rec.line_ids

    # Open reconciliation view
    return {
        'type': 'ir.actions.act_window',
        'name': 'Reconcile',
        'res_model': 'account.move.line',
        'view_mode': 'form',
        'target': 'new',
        'context': {'active_ids': lines.ids}
    }
```

### Auto-Reconciliation via Reconcile Model

```
account.reconcile.model
    │
    ├── invoice_matching
    │       Search open invoices/bills
    │       Match by partner, amount, reference
    │       Create partial/full reconcile
    │
    ├── writeoff_suggestion
    │       Suggest write-off account
    │       Create counterpart entry
    │
    └── writeoff_button
            Manual write-off on demand
            Creates counterpart entry
```

### Reconciliation Status

```python
def _compute_reconciliation_status(self):
    """Compute is_reconciled and is_matched"""
    for payment in self:
        all_lines = payment.line_ids

        # is_reconciled: liquidity lines fully reconciled
        liquidity_lines = all_lines.filtered(
            lambda l: l.account_id == payment.outstanding_account_id
        )
        payment.is_reconciled = all(
            line.reconciled for line in liquidity_lines
        )

        # is_matched: matched with bank statement
        payment.is_matched = bool(
            all_lines.mapped('statement_line_id')
        )
```

---

## Cash Basis Accounting (CABA) with Payments

When payment is made for invoice with `on_payment` tax:

```
Payment Registered
    │
    └─► account.partial.reconcile created
            │
            └─► _create_tax_cash_basis_moves()
                    │
                    └─► Cash Basis Journal Entry:
                        ┌─────────────────────────────────────┬───────┬─────────┐
                        │ Account                             │ Debit │ Credit  │
                        ├─────────────────────────────────────┼───────┼─────────┤
                        │ Tax Receivable (base)               │ XXX   │         │
                        │ Tax Payable (base)                   │       │ XXX    │
                        │ Transition Account (counterpart)    │       │ 0      │
                        └─────────────────────────────────────┴───────┴─────────┘
```

**Source**: `addons/account/models/account_partial_reconcile.py:_create_tax_cash_basis_moves()`

---

## Payment QR Code

For some countries (e.g., India), QR codes are generated for payment.

```python
def _compute_qr_code(self):
    """Generate QR code for payment"""
    for payment in self:
        if payment.partner_bank_id:
            # Generate SEPA/ country-specific QR code
            payment.qr_code = payment._generate_qr_code_url()
        else:
            payment.qr_code = False
```

---

## Payment States

```
payment.state progression:

draft ──► posted ──► reconciled/matched
             │
             └──► cancelled
```

| State | Description |
|-------|-------------|
| `draft` | Payment created, not posted |
| `posted` | Journal entry validated |
| `reconciled` | Fully matched with invoice |
| `matched` | Matched with bank statement |

---

## Related Flows

- [Flows/Account/invoice-post-flow](flows/account/invoice-post-flow.md) — Invoice posting
- [Modules/Account](modules/account.md) — Core payment model
- [Flows/Cross-Module/sale-stock-account-flow](flows/cross-module/sale-stock-account-flow.md) — Full cycle

---

**Source**: `addons/account/models/account_payment.py`
