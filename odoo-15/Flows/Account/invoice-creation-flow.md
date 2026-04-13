# Flows/Account/invoice-creation-flow.md

# Invoice Creation Flow — Odoo 15

## Overview

Invoice creation in Odoo 15 follows a structured flow from draft entry to confirmed posting. This document describes the complete lifecycle of an invoice from creation to posting.

**Source**: `addons/account/models/account_move.py`

---

## Invoice Types

| `move_type` | Direction | Description |
|-------------|-----------|-------------|
| `out_invoice` | Customer | Customer invoice |
| `out_refund` | Customer | Customer credit note |
| `in_invoice` | Vendor | Vendor bill |
| `in_refund` | Vendor | Vendor credit note |
| `in_receipt` | Vendor | Vendor receipt |
| `out_receipt` | Customer | Sales receipt |

---

## Creation Methods

### 1. Manual Creation

```
res.partner (customer)
    └── action_invoice_create()
        └── account.move (draft)
            ├── line_ids (empty or template)
            └── move_type set
```

**Method**: `_create_invoices()` on `sale.order` / `purchase.order`
**Model**: `account.move`

### 2. From Sale Order

```python
# sale.order
def action_invoice_create(self, grouped=False, final=False):
    # Creates draft invoice from SO lines
    moves = self.env['account.move']
    for order in self:
        moves += order._create_invoices_from_data(grouped, final)
    return moves
```

**Flow**:
```
sale.order.action_confirm()
    └─► _create_invoices()
          └─► account.move (draft, move_type='out_invoice')
```

### 3. From Purchase Order

```python
# purchase.order
def action_invoice_create(self):
    # Creates vendor bill from PO lines
    moves = self.env['account.move']
    for order in self:
        moves += order._create_invoices_from_data()
    return moves
```

**Flow**:
```
purchase.order.button_confirm()
    └─► action_invoice_create()
          └─► account.move (draft, move_type='in_invoice')
```

### 4. From Bank Statement

```
account.bank.statement.line
    └─► button_duplicate_to_invoice()
          └─► account.move (draft)
```

---

## Draft Invoice Structure

### Default Values

```python
# account_move.py — _prepare_invoice_default_lines()

invoice_default_lines = {
    'move_type': source_move_type,
    'journal_id': _get_default_journal(),
    'partner_id': partner,
    'currency_id': partner.currency_id or company.currency_id,
    'date': current_date,
    'ref': source_document.ref,
}
```

### Journal Selection

```python
def _get_default_journal(self):
    """Get default journal based on move_type"""
    if self.move_type in ('out_invoice', 'out_receipt'):
        return sale_journal
    elif self.move_type in ('in_invoice', 'in_receipt'):
        return purchase_journal
    else:
        return general_journal

def _search_default_journal(self):
    """Search journal by types"""
    domain = [('company_id', '=', self.company_id.id)]
    if self.move_type in ('out_invoice', 'out_refund', 'out_receipt'):
        domain += [('type', '=', 'sale')]
    elif self.move_type in ('in_invoice', 'in_refund', 'in_receipt'):
        domain += [('type', '=', 'purchase')]
    return self.env['account.journal'].search(domain, limit=1)
```

---

## Line Creation

### Invoice Lines

Each invoice line represents a product/service to bill.

```python
# account.move.line
line = {
    'move_id': move.id,
    'account_id': product_account.id,
    'product_id': product.id,
    'name': product.name,
    'quantity': qty,
    'price_unit': price_unit,
    'tax_ids': [(6, 0, tax_ids.ids)],
}
```

### Tax Computation

```python
# Called when tax_ids change or price_unit changes
def _compute_amount():
    for line in self:
        taxes = line.tax_ids.compute_all(
            line.price_unit * (1 - line.discount/100),
            line.currency_id,
            line.quantity,
            line.product_id,
            line.partner_id
        )
        line.amount_untaxed = taxes['total_excluded']
        line.amount_tax = taxes['total_included'] - taxes['total_excluded']
        line.amount_total = taxes['total_included']
```

### Invoice Totals

```python
# account.move
def _compute_amount():
    self.amount_untaxed = sum(line.debit if line.account_id.internal_type == 'receivable' else 0
                              for line in self.line_ids)
    self.amount_tax = sum(tax_line.credit - tax_line.debit
                          for tax_line in self.line_ids.filtered('tax_line_id'))
    self.amount_total = self.amount_untaxed + self.amount_tax
```

---

## Tax Line Generation

### Automatic Tax Lines

Tax lines are created via `_recompute_tax_lines()` or when posting.

```python
def _recompute_tax_lines(self, recompute_tax_base_amount=False):
    """Recompute tax lines based on product lines"""
    for move in self:
        # Remove existing tax lines
        move.line_ids.filtered('tax_line_id').unlink()

        # Compute new tax lines from tax_ids on product lines
        taxes = {}
        for line in move.line_ids.filtered(lambda l: l.move_id.move_type != 'entry'):
            for tax in line.tax_ids:
                taxes[tax] = taxes.get(tax, 0) + line.balance

        # Create tax lines
        for tax, base_amount in taxes.items():
            tax_amount = tax.compute_all(base_amount)
            move.line_ids.create({
                'move_id': move.id,
                'account_id': tax.account_id,
                'name': tax.name,
                'tax_line_id': tax.id,
                'balance': -tax_amount,
            })
```

---

## Repost Mechanism

Invoices can be "reposted" to recompute taxes and analytic lines.

```python
def action_post(self):
    """Validate invoice - main entry point"""
    self._post(soft=True)
    return True

def _post(self, soft=True):
    for move in self:
        if move.state != 'draft':
            continue

        # 1. Validate
        move._notify_cash_rounding()
        move._validate_constrains_date_company()

        # 2. Tax computation
        move._recompute_tax_lines()

        # 3. Auto-create analytic lines
        if soft:
            move._create_analytic_lines()

        # 4. Hash lock
        if move.journal_id.restrict_mode_hash_table:
            move._constrains_date_sequence()

        # 5. Set name (sequence)
        move._compute_name()

        # 6. Post
        move.write({'state': 'posted'})

    return True
```

---

## State Machine

```
┌─────────┐
│  DRAFT  │ ← Editable, can add/remove lines
└────┬────┘
     │ action_post()
     ▼
┌─────────┐
│ POSTED  │ ← Posted, creates move lines
└────┬────┘    State: 'posted'
     │ action_reverse_moves() / button_cancel
     ▼
┌─────────┐
│CANCELLED│ ← Cancelled
└─────────┘
```

---

## Payment State

After posting, the `payment_state` tracks collection status.

```
payment_state progression:

not_paid
    │
    ├──► in_payment     (payment registered)
    │         │
    │         └──► paid    (fully reconciled)
    │
    └──► partial       (partial payment)
              │
              └──► paid    (fully reconciled)

```

**Computation**:
```python
def _compute_payment_state():
    for move in self:
        if move.move_type == 'entry':
            move.payment_state = False
            continue

        residual = sum(line.amount_residual
                      for line in move.line_ids
                      if line.account_id.reconcile)

        if residual == 0 and not move.line_ids.filtered('matched_debit_ids'):
            move.payment_state = 'paid'
        elif residual < move.amount_total:
            move.payment_state = 'partial'
        else:
            move.payment_state = 'not_paid'
```

---

## Validation Rules

### Constraints

```python
@api.constrains('line_ids')
def _check_duplicate_partner(self):
    """Customer invoice must have same partner on receivable lines"""
    for move in self:
        if move.is_invoice():
            partners = move.line_ids.filtered(
                lambda l: l.account_id == move.partner_id.property_account_receivable_id
            ).mapped('partner_id')
            if len(partners) > 1:
                raise ValidationError(_("All receivable lines must have same partner"))

@api.constrains('journal_id', 'move_type')
def _check_journal_type(self):
    """Journal type must match move_type"""
    for move in self:
        if move.move_type in ('out_invoice', 'out_refund', 'out_receipt'):
            assert move.journal_id.type == 'sale'
        elif move.move_type in ('in_invoice', 'in_refund', 'in_receipt'):
            assert move.journal_id.type == 'purchase'
```

---

## Related Flows

- [Flows/Account/invoice-post-flow](flows/account/invoice-post-flow.md) — Posting and validation
- [Flows/Account/payment-flow](flows/account/payment-flow.md) — Payment registration
- [Flows/Cross-Module/sale-stock-account-flow](flows/cross-module/sale-stock-account-flow.md) — SO → Invoice flow
- [Modules/Account](modules/account.md) — Core account models

---

**Source**: `addons/account/models/account_move.py`
