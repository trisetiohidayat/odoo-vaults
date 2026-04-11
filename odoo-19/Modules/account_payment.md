---
module: account_payment
description: Payment integration between account and payment modules - token-based payments, online payment for invoices, refund handling, and batch payment creation
tags: [odoo, odoo19, modules, payment, accounting, integration, portal]
---

# account_payment Module

> **Module:** `account_payment` | **Depends:** `account`, `payment` | **Auto-installs:** `account`
> **Category:** Accounting/Accounting | **Version:** 2.0 | **License:** LGPL-3
> **Author:** Odoo S.A.

## Overview

The `account_payment` module bridges the gap between the accounting (`account`) and payment processing (`payment`) modules in Odoo 19. It enables merchants and customers to pay invoices through the portal, processes payments via third-party providers (Stripe, Adyen, etc.), creates accounting entries, manages refunds, and supports token-based (saved card) payments.

This module does **not** implement any payment provider itself; it depends on the `payment` module (and specific provider modules like `payment_stripe`, `payment_adyen`, etc.). It focuses on the accounting side: linking transactions to journal entries, handling invoice reconciliation, managing payment tokens, and providing portal-facing payment flows.

### Module Files

```
account_payment/
├── __init__.py
├── __manifest__.py
├── controllers/
│   ├── __init__.py
│   ├── payment.py          # JSON-RPC endpoints for invoice payment
│   └── portal.py           # Portal page extensions for invoices
├── models/
│   ├── __init__.py
│   ├── account_journal.py       # Journal restrictions for providers
│   ├── account_move.py           # Invoice extensions (transactions, QR codes)
│   ├── account_payment.py         # Payment model extensions (tokens, refunds)
│   ├── account_payment_method.py  # Payment method information registration
│   ├── account_payment_method_line.py  # Provider-linked payment method lines
│   ├── payment_provider.py       # Provider journal assignment
│   └── payment_transaction.py    # Transaction-to-payment mapping
├── wizards/
│   ├── __init__.py
│   ├── account_payment_register.py  # Register payment with token support
│   ├── payment_link_wizard.py       # Payment link with installments/EPD
│   ├── payment_refund_wizard.py     # Refund wizard
│   └── res_config_settings.py       # Portal payment toggle
├── tests/
│   ├── __init__.py
│   ├── common.py              # Shared test fixtures (AccountPaymentCommon)
│   ├── test_account_payment.py  # Unit tests for payment/refund logic
│   ├── test_payment_flows.py     # Integration tests for portal flows
│   └── test_payment_provider.py  # Provider journal assignment tests
├── security/
│   ├── ir.model.access.csv
│   └── ir_rules.xml
└── views/  (XML views for all extended models)
```

---

## Module Architecture

The module follows a layered architecture:

```
Portal User / API Client
        |
        v
controllers/  (payment.py, portal.py)
  - /invoice/transaction/<id>
  - /invoice/transaction/overdue
  - /my/invoices/overdue
        |
        v
models/  (payment_transaction, account_payment)
  - Transaction created -> Payment created
  - Payment posted -> Journal entries posted
        |
        v
account.move  (inherited)
  - transaction_ids, authorized_transaction_ids
  - amount_paid, QR code generation
  - Portal payment link, installments
        |
        v
wizards/
  - Payment registration (with token)
  - Payment link (with installments)
  - Refund wizard
```

---

## Models

### 1. `account.payment` (Extended)

**File:** `models/account_payment.py` | **Inheritance:** `account.payment` (from `account` module)

The base `account.payment` model provides all core payment fields:
- `payment_type` — `'inbound'` or `'outbound'`
- `partner_type` — `'customer'` or `'supplier'`
- `partner_id` — `res.partner`
- `amount` — `Monetary`
- `currency_id` — `res.currency`
- `journal_id` — `account.journal`
- `destination_account_id` — Target account for the payment
- `is_internal_transfer` — Boolean flag for internal transfers
- `batch_payment_ids` — `One2many` to `account.batch.payment`
- `payment_method_line_id` — `account.payment.method.line`

The `account_payment` module extends this with fields for token-based payments, refund traceability, and transaction linking.

#### Extended Fields

| Field | Type | Description |
|-------|------|-------------|
| `payment_transaction_id` | Many2one (`payment.transaction`) | Links a payment to its originating payment transaction. **Odoo 18→19:** Added `bypass_search_access=True` to bypass access rule checks when searching for transactions. This is safe because access to a payment implies access to its transaction. |
| `payment_token_id` | Many2one (`payment.token`) | Saved payment token used for token-based (offline) payments. Filtered by `suitable_payment_token_ids` domain. Only tokens from providers allowing capture are shown (not `capture_manually=True`). |
| `amount_available_for_refund` | Monetary | Computed amount that can still be refunded. Considers the original payment amount minus all confirmed refund payments linked via `source_payment_id`. |
| `suitable_payment_token_ids` | Many2many (`payment.token`) | Computed list of tokens available for the payment's partner, company, and provider combination. Used as domain filter on `payment_token_id`. |
| `use_electronic_payment_method` | Boolean | Technical field indicating whether the selected payment method is electronic (provider-based). Used to conditionally show/hide token fields. |
| `source_payment_id` | Many2one (`account.payment`) | Traceability field linking refund payments back to their source payment. Stored for group-by performance. Has a `btree_not_null` index. |
| `refunds_count` | Integer | Count of refund payments linked via `source_payment_id` with `operation='refund'`. |

#### L2: Field Types, Defaults, and Constraints

**`payment_transaction_id`**

```python
payment_transaction_id = fields.Many2one(
    string="Payment Transaction",
    comodel_name='payment.transaction',
    readonly=True,
    bypass_search_access=True,
)
```

- **Type:** Many2one — single linked transaction
- **Default:** None — payments without a transaction have no link
- **Constraints:** `readonly=True` — transactions are created programmatically
- **Odoo 18→19:** `bypass_search_access=True` was added. This parameter (introduced in Odoo 17) allows the ORM to bypass the normal access rights check when searching records of this related model. This is safe here because in the payment workflow, if a user has access to a payment, they should also have access to its transaction — they are the same business operation.

**`payment_token_id`**

```python
payment_token_id = fields.Many2one(
    string="Saved Payment Token",
    comodel_name='payment.token',
    domain="[('id', 'in', suitable_payment_token_ids)]",
    help="Note that only tokens from providers allowing to capture the amount are available."
)
```

- **Type:** Many2one — single saved payment method
- **Domain:** Dynamic, based on `suitable_payment_token_ids` (prevents invalid selections)
- **Help text:** Explains the capture limitation
- **Constraints:** Only populated when `use_electronic_payment_method=True`

**`amount_available_for_refund`**

```python
amount_available_for_refund = fields.Monetary(
    compute='_compute_amount_available_for_refund'
)
```

- **Type:** Monetary — currency-aware decimal
- **Dependencies:** `payment_transaction_id` (implicit via sudo access)
- **Computation:** Always returns 0 for non-transaction payments or unsupported providers

**`source_payment_id`**

```python
source_payment_id = fields.Many2one(
    string="Source Payment",
    comodel_name='account.payment',
    related='payment_transaction_id.source_transaction_id.payment_id',
    readonly=True,
    store=True,
    index='btree_not_null',
    help="The source payment of related refund payments",
)
```

- **Type:** Many2one — the original payment being refunded
- **Index:** `btree_not_null` — partial B-tree index on non-null values (Odoo 17+ feature). More efficient than a standard index because it only indexes rows where `source_payment_id IS NOT NULL`, which is a small subset of all payments.
- **Store:** `True` — stored for efficient grouping and filtering
- **Help text:** Clarifies the traceability purpose

#### L2: Compute Methods

**`_compute_amount_available_for_refund()`**

```
Dependencies: payment_transaction_id (implicit)
Logic:
1. Get the sudo-ed transaction linked to the payment
2. Check provider supports refund: tx.provider_id.support_refund != 'none'
3. Check payment method supports refund: payment_method.support_refund != 'none'
4. Check transaction is not a refund itself: tx.operation != 'refund'
5. Sum all confirmed refund payments (state='done') linked to this payment
6. Return: original_amount - confirmed_refunded_amount
```

The sudo access is used because the user may lack direct access to provider and payment method fields, but they should still see the refundable amount. Only confirmed (state='done') refund payments count — pending refund transactions do not reduce the available amount, which prevents a stuck refund transaction from permanently blocking future refunds.

```python
def _compute_amount_available_for_refund(self):
    for payment in self:
        tx_sudo = payment.payment_transaction_id.sudo()
        payment_method = (
            tx_sudo.payment_method_id.primary_payment_method_id
            or tx_sudo.payment_method_id
        )
        if (
            tx_sudo
            and tx_sudo.provider_id.support_refund != 'none'
            and payment_method.support_refund != 'none'
            and tx_sudo.operation != 'refund'
        ):
            refund_payments = self.search([('source_payment_id', '=', payment.id)])
            refunded_amount = abs(sum(refund_payments.mapped('amount')))
            payment.amount_available_for_refund = payment.amount - refunded_amount
        else:
            payment.amount_available_for_refund = 0
```

**`_compute_suitable_payment_token_ids()`**

```
Dependencies: payment_method_line_id
Logic:
1. If not using electronic method: return empty
2. Search tokens matching:
   - Company domain (via _check_company_domain)
   - provider_id.capture_manually = False
   - partner_id matches payment's partner
   - provider_id matches payment_method_line's provider
3. Return as Many2many recordset
```

The search is performed in sudo mode because payment users typically lack direct access to the `payment.token` model's access rights, but they should still see their own tokens when creating payments.

**`_compute_use_electronic_payment_method()`**

```
Dependencies: payment_method_line_id
Logic:
1. Build list of all electronic payment method codes
   (from payment.provider.code selection)
2. Compare payment's payment_method_code against this list
3. Returns True if code matches any provider code
```

Electronic methods include all provider-specific methods (stripe, adyen, etc.) plus any method registered with `mode='electronic'`.

**`_compute_refunds_count()`**

Uses `read_group` for O(1) aggregation instead of O(n) individual searches:

```python
def _compute_refunds_count(self):
    rg_data = self.env['account.payment']._read_group(
        domain=[
            ('source_payment_id', 'in', self.ids),
            ('payment_transaction_id.operation', '=', 'refund')
        ],
        groupby=['source_payment_id'],
        aggregates=['__count']
    )
    data = {source_payment.id: count for source_payment, count in rg_data}
    for payment in self:
        payment.refunds_count = data.get(payment.id, 0)
```

The domain includes `payment_transaction_id.operation = 'refund'` to ensure only actual refund operations are counted, not all child transactions (captures, voids, etc.).

#### L2: Onchange Methods

**`_onchange_set_payment_token_id()`**

Triggered by changes to `partner_id`, `payment_method_line_id`, or `journal_id`:

```python
@api.onchange('partner_id', 'payment_method_line_id', 'journal_id')
def _onchange_set_payment_token_id(self):
    codes = [key for key in dict(self.env['payment.provider']._fields['code']._description_selection(self.env))]
    if not (self.payment_method_code in codes and self.partner_id and self.journal_id):
        self.payment_token_id = False
        return

    self.payment_token_id = self.env['payment.token'].sudo().search([
        *self.env['payment.token']._check_company_domain(self.company_id),
        ('partner_id', '=', self.partner_id.id),
        ('provider_id.capture_manually', '=', False),
        ('provider_id', '=', self.payment_method_line_id.payment_provider_id.id),
    ], limit=1)
```

This auto-selection helps users by pre-filling the most recent valid token for the selected partner and provider.

#### L3: `action_post()` — Payment Posting with Token Processing

This is the critical override that handles token-based payments. The flow differs significantly from standard payments:

```python
def action_post(self):
    # Step 1: Identify payments needing transactions (have token but no tx yet)
    # These are token-based payments initiated by the user
    payments_need_tx = self.filtered(
        lambda p: p.payment_token_id and not p.payment_transaction_id
    )
    # sudo required because creating transactions requires provider data
    # (state, code, credentials) that regular payment users may not have access to
    transactions = payments_need_tx.sudo()._create_payment_transaction()

    # Step 2: Post payments that don't need transactions normally
    # (manual payments, transfers, etc.)
    res = super(AccountPayment, self - payments_need_tx).action_post()

    # Step 3: Process token payments — charge via provider
    for tx in transactions:
        tx._charge_with_token()

    # Step 4: Run transaction post-processing
    # This creates payments from confirmed transactions, reconciles, etc.
    transactions._post_process()

    # Step 5: Handle payment states based on transaction result
    # If tx succeeded: post the payment normally
    payments_tx_done = payments_need_tx.filtered(
        lambda p: p.payment_transaction_id.state == 'done'
    )
    super(AccountPayment, payments_tx_done).action_post()

    # If tx failed: cancel the payment
    payments_tx_not_done = payments_need_tx.filtered(
        lambda p: p.payment_transaction_id.state != 'done'
    )
    payments_tx_not_done.action_cancel()

    return res
```

**Cross-model interaction:** This method orchestrates between `account.payment` and `payment.transaction`. The `payments_need_tx` filter ensures only token payments go through the transaction flow. The sudo escalation is necessary because payment creation users may lack provider access rights but need to trigger payment processing.

**Failure mode:** If `_charge_with_token()` fails (e.g., card declined, network error), the transaction enters an error state. The `action_cancel()` call then reverts the payment. The cancelled payment remains in the database for audit purposes.

#### L3: `_create_payment_transaction()` and `_prepare_payment_transaction_vals()`

```python
def _create_payment_transaction(self, **extra_create_values):
    for payment in self:
        if payment.payment_transaction_id:
            raise ValidationError(_(
                "A payment transaction with reference %s already exists.",
                payment.payment_transaction_id.reference
            ))
        elif not payment.payment_token_id:
            raise ValidationError(_("A token is required to create a new payment transaction."))

    transactions = self.env['payment.transaction']
    for payment in self:
        transaction_vals = payment._prepare_payment_transaction_vals(**extra_create_values)
        transaction = self.env['payment.transaction'].create(transaction_vals)
        transactions += transaction
        payment.payment_transaction_id = transaction
    return transactions
```

```python
def _prepare_payment_transaction_vals(self, **extra_create_values):
    self.ensure_one()
    # Extract invoice IDs from context for multi-invoice payments
    if self.env.context.get('active_model') == 'account.move':
        invoice_ids = self.env.context.get('active_ids', [])
    elif self.env.context.get('active_model') == 'account.move.line':
        invoice_ids = self.env['account.move.line'].browse(
            self.env.context.get('active_ids')
        ).move_id.ids
    else:
        invoice_ids = []

    return {
        'provider_id': self.payment_token_id.provider_id.id,
        'payment_method_id': self.payment_token_id.payment_method_id.id,
        'reference': self.env['payment.transaction']._compute_reference(
            self.payment_token_id.provider_id.code, prefix=self.memo
        ),
        'amount': self.amount,
        'currency_id': self.currency_id.id,
        'partner_id': self.partner_id.id,
        'token_id': self.payment_token_id.id,
        'operation': 'offline',  # Key: marks this as a token-based (offline) charge
        'payment_id': self.id,
        'invoice_ids': [Command.set(invoice_ids)],
        **extra_create_values,
    }
```

The `operation='offline'` flag tells the payment provider that this is a token-based charge initiated from Odoo, not a direct portal payment.

#### L3: `action_refund_wizard()` and `action_view_refunds()`

```python
def action_refund_wizard(self):
    self.ensure_one()
    return {
        'name': _("Refund"),
        'type': 'ir.actions.act_window',
        'view_mode': 'form',
        'res_model': 'payment.refund.wizard',
        'target': 'new',
    }

def action_view_refunds(self):
    self.ensure_one()
    action = {
        'name': _("Refund"),
        'res_model': 'account.payment',
        'type': 'ir.actions.act_window',
    }
    if self.refunds_count == 1:
        refund_tx = self.env['account.payment'].search([
            ('source_payment_id', '=', self.id)
        ], limit=1)
        action['res_id'] = refund_tx.id
        action['view_mode'] = 'form'
    else:
        action['view_mode'] = 'list,form'
        action['domain'] = [('source_payment_id', '=', self.id)]
    return action
```

`action_view_refunds()` handles both single-refund (opens form directly) and multi-refund (opens list) scenarios.

#### L4: Performance Implications

| Operation | Approach | Why |
|-----------|----------|-----|
| `refunds_count` | `_read_group` | Single SQL query instead of N individual searches |
| `source_payment_id` | `index='btree_not_null'` | Partial index only on non-null values |
| Token searches | `sudo()` + `_check_company_domain` | Avoids access denial errors, still filters by company |
| `_compute_invoices_count` | Raw SQL with `GROUP BY` | More efficient than ORM `read_group` for simple counts |

#### L4: Security Concerns

- **`sudo()` on transactions and tokens:** The sudo is intentional and necessary because payment creation users may lack provider access but need to trigger payment processing. The company domain is still enforced.
- **`bypass_search_access=True`:** Safe because payment→transaction is a one-to-one operational relationship; if you can see the payment, you should see the transaction.
- **Amount validation:** The refund wizard constrains `amount_to_refund` to be positive and within the `amount_available_for_refund`, which itself accounts for all confirmed refunds.

#### L4: `sudo()` Pattern — Complete Rationale Map

The `account_payment` module uses `sudo()` in several places. Here is the complete map of why each is safe:

| Location | Reason | Company Filter |
|---------|--------|----------------|
| `account_payment._onchange_set_payment_token_id()` | Payment users lack `payment.token` ACL but need to select their own tokens | `_check_company_domain` applied |
| `account_payment._compute_suitable_payment_token_ids()` | Payment users lack `payment.token` ACL but need to see available tokens | `_check_company_domain` applied |
| `account_payment.action_post()` (creates tx) | Provider state/credentials require `payment.provider` ACL not granted to payment users | Implicit via `payment_transaction_id` link |
| `payment_transaction._compute_invoices_count()` | Raw SQL for speed; sudo not needed (only `self.ids` used) | N/A |
| `account_journal._unlink_except_linked_to_payment_provider()` | Deletes journal only after provider deactivation; provider data requires sudo | `sudo()` on provider search |
| `payment_provider._check_existing_payment()` | Count check; runs without sudo when called from `_remove_provider` | Implicitly scoped to provider's company |
| `portal._get_common_page_view_values()` | Portal users lack `payment.provider`, `payment.token` ACL | Provider filtering by company via `_get_compatible_providers` |
| `portal._get_common_page_view_values()` (tokens) | Portal users may be logged-out (public user) or lack token ACL | `_get_available_tokens` filters by partner |
| `payment_refund_wizard._compute_support_refund()` | Provider fields require elevated access for non-admin users | `sudo()` on provider + payment method fields |
| `account_move.get_portal_last_transaction()` | Portal users lack `payment.transaction` ACL | `_get_last()` runs on own transactions |

#### L4: Webhook Failure and Refund State Machine

The refund flow is designed to be resilient to webhook delivery failures:

```
Source Payment Created
       |
       v
Refund Requested (refund wizard)
       |
       v
Refund Transaction Created (state='draft')
       |
       v
Provider notified -> state='pending' or 'authorized'
       |
       v (webhook failure -> tx stuck in pending)
       |
       v
has_pending_refund = True (blocks duplicate refunds)
amount_available_for_refund = 0 (blocks UI refunds)
       |
       v (when webhook finally arrives -> 'done')
       |
Refund Payment Created (state='done')
       |
       v
amount_available_for_refund updated (confirmed refunds deducted)
```

The `_compute_amount_available_for_refund()` method only subtracts **confirmed** refund payments (`state='done'`), leaving pending refund transactions in a limbo state that prevents over-refunding. The `has_pending_refund` boolean on the refund wizard provides UI-level feedback that a refund is already in progress.

**L4: Edge Case — Refund on Captured Partial Authorization**

If a transaction was partially captured via child transactions (e.g., $100 authorized, $40 captured), the `source_transaction_id.invoice_ids` reconciliation logic in `_create_payment()` uses the source transaction's invoices rather than the capture's invoices. This ensures partial captures still reconcile correctly against the original invoice, even though the captured amount differs from the authorized amount.

#### L4: Historical Changes

| Version | Change |
|---------|--------|
| Odoo 17 | `bypass_search_access=True` introduced and applied to `payment_transaction_id` |
| Odoo 17 | `btree_not_null` index support added for `source_payment_id` |
| Odoo 18 | Refund tracking enhanced with `source_payment_id` and `refunds_count` |
| Odoo 19 | `sudo()` used on token search to handle access rights mismatch |

---

### 2. `payment.transaction` (Extended)

**File:** `models/payment_transaction.py` | **Inheritance:** `payment.transaction` (from `payment` module)

Extends the base payment transaction with invoice linking and accounting post-processing.

#### Extended Fields

| Field | Type | Description |
|-------|------|-------------|
| `payment_id` | Many2one (`account.payment`) | Links the transaction to the created payment record (readonly). |
| `invoice_ids` | Many2many (`account.move`) | **Odoo 18→19:** Changed from Many2one to Many2many. Allows a single transaction to pay multiple invoices simultaneously (e.g., overdue invoice batch payment). Uses the relation table `account_invoice_transaction_rel`. |
| `invoices_count` | Integer | Cached count of linked invoices, computed via raw SQL for performance. |

#### L2: Field Details

**`invoice_ids`** — Multi-Invoice Support (Odoo 19 Breaking Change)

In Odoo 18, `invoice_ids` was a `Many2one` (single invoice). Odoo 19 changed this to `Many2many`:

```python
invoice_ids = fields.Many2many(
    string="Invoices",
    comodel_name='account.move',
    relation='account_invoice_transaction_rel',
    column1='transaction_id',
    column2='invoice_id',
    readonly=True,
    copy=False,
    domain=[(
        'move_type', 'in',
        ('out_invoice', 'out_refund', 'in_invoice', 'in_refund')
    )]
)
```

The custom relation table `account_invoice_transaction_rel` with explicit `column1`/`column2` names allows a transaction to be linked to multiple invoices. This is the foundation of the overdue invoice batch payment flow (`/invoice/transaction/overdue` endpoint).

**`payment_id`** — One-to-One Link (reverse of `account.payment.payment_transaction_id`):

```python
payment_id = fields.Many2one(
    string="Payment",
    comodel_name='account.payment',
    readonly=True
)
```

The link is created by `tx.payment_id = payment` in `_create_payment()`.

#### L2: `_compute_invoices_count()` — Raw SQL Optimization

```python
@api.depends('invoice_ids')
def _compute_invoices_count(self):
    tx_data = {}
    if self.ids:
        self.env.cr.execute('''
            SELECT transaction_id, count(invoice_id)
            FROM account_invoice_transaction_rel
            WHERE transaction_id IN %s
            GROUP BY transaction_id
        ''', [tuple(self.ids)])
        tx_data = dict(self.env.cr.fetchall())
    for tx in self:
        tx.invoices_count = tx_data.get(tx.id, 0)
```

This raw SQL approach is faster than using ORM `read_group` because it avoids the overhead of the ORM layer for a simple aggregate. The query uses parameterized input (`tuple(self.ids)`) to prevent SQL injection.

#### L3: `action_view_invoices()` — Navigation

```python
def action_view_invoices(self):
    self.ensure_one()
    action = {
        'name': _("Invoices"),
        'type': 'ir.actions.act_window',
        'res_model': 'account.move',
        'target': 'current',
    }
    invoice_ids = self.invoice_ids.ids
    if len(invoice_ids) == 1:
        action['res_id'] = invoice_ids[0]
        action['view_mode'] = 'form'
        action['views'] = [(self.env.ref('account.view_move_form').id, 'form')]
    else:
        action['view_mode'] = 'list,form'
        action['domain'] = [('id', 'in', invoice_ids)]
    return action
```

The single vs. multiple invoice branching is critical for UX — single invoices open directly in form view, while multiple invoices open in a list.

#### L3: `_compute_reference_prefix()` — Installment Support

```python
@api.model
def _compute_reference_prefix(self, separator, **values):
    command_list = values.get('invoice_ids')
    if command_list:
        invoice_ids = self._fields['invoice_ids'].convert_to_cache(command_list, self)
        invoices = self.env['account.move'].browse(invoice_ids).exists()
        if len(invoices) == len(invoice_ids):  # All ids are valid (not deleted)
            prefix = separator.join(invoices.filtered(lambda inv: inv.name).mapped('name'))
            if name := values.get('name_next_installment'):
                prefix = name  # Override with installment-specific name
            return prefix
    return super()._compute_reference_prefix(separator, **values)
```

The `name_next_installment` parameter supports installment payments: when paying a specific installment, the transaction reference uses the installment name rather than the invoice name.

#### L3: `_post_process()` — Accounting Post-Processing

The `_post_process()` method is the bridge between payment confirmation and accounting entries:

```python
def _post_process(self):
    super()._post_process()  # Provider-specific state transitions
    for tx in self.filtered(lambda t: t.state == 'done'):
        # 1. Auto-validate draft invoices
        self.invoice_ids.filtered(lambda inv: inv.state == 'draft').action_post()

        # 2. Create and post payment (unless validation tx, already has payment, or has done/cancel children)
        if (
            tx.operation != 'validation'
            and not tx.payment_id
            and not any(child.state in ['done', 'cancel'] for child in tx.child_transaction_ids)
        ):
            tx.with_company(tx.company_id)._create_payment()

        # 3. Log confirmation message
        if tx.payment_id:
            message = _(
                "The payment related to transaction %(ref)s has been posted: %(link)s",
                ref=tx._get_html_link(),
                link=tx.payment_id._get_html_link(),
            )
            tx._log_message_on_linked_documents(message)

    for tx in self.filtered(lambda t: t.state == 'cancel'):
        tx.payment_id.action_cancel()
```

**Odoo 18→19 Change — Cancel Handling:**

In Odoo 18, cancelled transactions had inconsistent handling — some flows would leave payments in a posted state. Odoo 19 explicitly cancels the payment:

```python
for tx in self.filtered(lambda t: t.state == 'cancel'):
    tx.payment_id.action_cancel()
```

This ensures that when a transaction is cancelled (e.g., payment failed after authorization), the accounting side is also reverted.

**Odoo 18→19 Change — EPD in `_create_payment()`:**

Early Payment Discount (EPD) handling was added in Odoo 19. When paying an invoice with an active EPD:

```python
for invoice in self.invoice_ids:
    if invoice.state != 'posted':
        continue
    next_payment_values = invoice._get_invoice_next_payment_values()
    if next_payment_values['installment_state'] == 'epd' and \
       self.amount == next_payment_values['amount_due']:
        # Build EPD write-off lines from discount terms
        aml = next_payment_values['epd_line']
        epd_aml_values_list = [({
            'aml': aml,
            'amount_currency': -aml.amount_residual_currency,
            'balance': -aml.balance,
        })]
        open_balance = next_payment_values['epd_discount_amount']
        early_payment_values = self.env['account.move']._get_invoice_counterpart_amls_for_early_payment_discount(
            epd_aml_values_list, open_balance
        )
        for aml_values_list in early_payment_values.values():
            if aml_values_list:
                aml_vl = aml_values_list[0]
                aml_vl['partner_id'] = invoice.partner_id.id
                payment_values['write_off_line_vals'] += [aml_vl]
        break
```

This automatically applies the early payment discount when conditions are met (exact amount matching the discounted balance).

**Odoo 18→19 Change — `destination_account_id` from Payment Term:**

```python
payment_term_lines = self.invoice_ids.line_ids.filtered(
    lambda line: line.display_type == 'payment_term'
)
if payment_term_lines:
    payment_values['destination_account_id'] = payment_term_lines[0].account_id.id
```

In Odoo 19, the payment's destination account is taken from the invoice's payment term lines, ensuring that installment payments are correctly booked to the installment-specific receivable account.

#### L3: `_create_payment()` — Transaction-to-Payment Mapping

```python
def _create_payment(self, **extra_create_values):
    self.ensure_one()

    reference = f'{self.reference} - {self.provider_reference or ""}'

    payment_method_line = self.provider_id.journal_id.inbound_payment_method_line_ids\
        .filtered(lambda l: l.payment_provider_id == self.provider_id)

    payment_values = {
        'amount': abs(self.amount),  # Ensure non-negative (refunds can have negative amounts)
        'payment_type': 'inbound' if self.amount > 0 else 'outbound',
        'currency_id': self.currency_id.id,
        'partner_id': self.partner_id.commercial_partner_id.id,
        'partner_type': 'customer',
        'journal_id': self.provider_id.journal_id.id,
        'company_id': self.provider_id.company_id.id,
        'payment_method_line_id': payment_method_line.id,
        'payment_token_id': self.token_id.id,
        'payment_transaction_id': self.id,  # Back-link to transaction
        'memo': reference,
        'write_off_line_vals': [],  # EPD lines added below
        'invoice_ids': self.invoice_ids,  # Odoo 19: Many2many
        **extra_create_values,
    }

    # ... EPD handling ...

    # Set destination account from payment term lines
    payment_term_lines = self.invoice_ids.line_ids.filtered(
        lambda line: line.display_type == 'payment_term'
    )
    if payment_term_lines:
        payment_values['destination_account_id'] = payment_term_lines[0].account_id.id

    # Create, post, and link
    payment = self.env['account.payment'].create(payment_values)
    payment.action_post()
    self.payment_id = payment

    # Reconcile with invoices
    if invoices:
        invoices.filtered(lambda inv: inv.state == 'draft').action_post()
        (payment.move_id.line_ids + invoices.line_ids).filtered(
            lambda line: line.account_id == payment.destination_account_id
            and not line.reconciled
        ).reconcile()

    return payment
```

The reconciliation step automatically matches the payment's receivable line with the invoice's payable line on the same account, marking both as paid.

#### L3: `_log_message_on_linked_documents()` — Audit Trail

```python
def _log_message_on_linked_documents(self, message):
    self.ensure_one()
    if self.env.uid == SUPERUSER_ID or self.env.context.get('payment_backend_action'):
        author = self.env.user.partner_id  # Internal user
    else:
        author = self.partner_id  # Portal user
    if self.source_transaction_id:
        for invoice in self.source_transaction_id.invoice_ids:
            invoice.message_post(body=message, author_id=author.id)
        payment_id = self.source_transaction_id.payment_id
        if payment_id:
            payment_id.message_post(body=message, author_id=author.id)
    for invoice in self._get_invoices_to_notify():
        invoice.message_post(body=author_id=author.id)
```

The author is selected based on context: internal users see internal author attribution, portal users see their partner as the author.

#### L4: `_get_invoices_to_notify()` — Notification Target Extension Point

```python
def _get_invoices_to_notify(self):
    """ Return the invoices on which to log payment-related messages. """
    return self.invoice_ids
```

This method is designed as an **extension point** for modules that link additional documents to a transaction (e.g., sale orders via `sale_payment` module). Third-party modules can override this to return additional invoices beyond `self.invoice_ids`, enabling payment status notifications to appear on related documents. The `super()._get_invoices_to_notify()` call in the overriding module should include the parent invoices.

#### L4: Performance

- Raw SQL for invoice count avoids ORM overhead
- Batched operations in `_post_process()` handle multiple transactions
- `with_company()` context manager ensures correct company is used without repeated context manipulation

#### L4: Security

- All field access in `_create_payment()` uses the transaction's already-validated data
- `with_company()` ensures the payment is created in the correct company context
- `sudo()` is used internally by the payment provider when creating child transactions

---

### 3. `account.move` (Extended)

**File:** `models/account_move.py` | **Inheritance:** `account.move` (from `account` module)

Extends the invoice/journal entry model with payment transaction linking and portal payment features.

#### Extended Fields

| Field | Type | Description |
|-------|------|-------------|
| `transaction_ids` | Many2many (`payment.transaction`) | All transactions linked to the invoice. Inverse of `payment.transaction.invoice_ids`. |
| `authorized_transaction_ids` | Many2many (`payment.transaction`) | Computed: transactions in `authorized` state only. |
| `transaction_count` | Integer | Count of linked transactions. |
| `amount_paid` | Monetary | Computed sum of amounts from transactions in `authorized` or `done` state. |

#### L2: Field Details

**`transaction_ids`** — Bidirectional M2M link:

```python
transaction_ids = fields.Many2many(
    string="Transactions",
    comodel_name='payment.transaction',
    relation='account_invoice_transaction_rel',
    column1='invoice_id',
    column2='transaction_id',
    readonly=True,
    copy=False
)
```

Shares the same relation table `account_invoice_transaction_rel` as `payment.transaction.invoice_ids`.

**`amount_paid`** — Cumulative paid amount:

```python
@api.depends('transaction_ids')
def _compute_amount_paid(self):
    for invoice in self:
        invoice.amount_paid = sum(
            invoice.transaction_ids.filtered(
                lambda tx: tx.state in ('authorized', 'done')
            ).mapped('amount')
        )
```

Only `authorized` and `done` transactions count. `pending` transactions are excluded because the payment has not yet been confirmed. This is different from `amount_residual` which is the accounting balance.

#### L3: `_has_to_be_paid()` — Portal Payment Eligibility

Determines whether an invoice should show a "Pay Now" button on the portal:

```python
def _has_to_be_paid(self):
    self.ensure_one()
    transactions = self.transaction_ids.filtered(
        lambda tx: tx.state in ('pending', 'authorized', 'done')
    )
    pending_transactions = transactions.filtered(
        lambda tx: tx.state in {'pending', 'authorized'}
                   and tx.provider_code not in {'none', 'custom'}
    )
    enabled_feature = str2bool(
        self.env['ir.config_parameter'].sudo().get_param(
            'account_payment.enable_portal_payment'
        )
    )
    return enabled_feature and bool(
        (self.amount_residual or not transactions)  # Has balance OR first payment
        and self.state == 'posted'                   # Invoice is posted
        and self.payment_state in ('not_paid', 'in_payment', 'partial')
        and not self.currency_id.is_zero(self.amount_residual)
        and self.amount_total
        and self.move_type == 'out_invoice'         # Customer invoice only
        and not pending_transactions                 # No pending electronic payments
    )
```

**L4: Failure Modes and Edge Cases:**

| Condition | `_has_to_be_paid()` returns False because |
|-----------|-------------------------------------------|
| Feature disabled | `enable_portal_payment` config param is False |
| Fully paid | `amount_residual == 0` and `transactions` exist |
| Draft invoice | `state != 'posted'` |
| Cancelled | `state == 'cancel'` (not in payment_state check) |
| Not an invoice | `move_type` is not `out_invoice` |
| Zero amount | `amount_total == 0` |
| Pending electronic tx | Prevents double-payment risk |
| Non-electronic pending tx | `provider_code in {'none', 'custom'}` are ignored — these are manual/placeholder transactions |

#### L3: `_get_online_payment_error()` — Error Messages

Returns user-friendly error messages explaining each reason `_has_to_be_paid()` returned `False`. The messages are joined with `\n` and displayed on the portal invoice page when payment is not available.

#### L3: Payment Action Methods

```python
def payment_action_capture(self):
    self.ensure_one()
    payment_utils.check_rights_on_recordset(self)
    return self.sudo().transaction_ids.action_capture()

def payment_action_void(self):
    payment_utils.check_rights_on_recordset(self)
    self.sudo().authorized_transaction_ids.action_void()
```

Both run in `sudo()` mode because transaction-level operations require provider access that the accounting user may not have. `check_rights_on_recordset()` is called first to verify the user has basic write access to the invoice.

#### L3: `_get_default_payment_link_values()` — Installment Support

```python
def _get_default_payment_link_values(self):
    next_payment_values = self._get_invoice_next_payment_values()
    amount_max = next_payment_values.get('amount_due')
    additional_info = {}
    open_installments = []
    installment_state = next_payment_values.get('installment_state')
    next_amount_to_pay = next_payment_values.get('next_amount_to_pay')

    if installment_state in ('next', 'overdue'):
        # Build list of installments for multi-installment invoices
        open_installments = []
        for installment in next_payment_values.get('not_reconciled_installments'):
            data = {
                'type': installment['type'],
                'number': installment['number'],
                'amount': installment['amount_residual_currency_unsigned'],
                'date_maturity': format_date(self.env, installment['date_maturity']),
            }
            open_installments.append(data)

    elif installment_state == 'epd':
        amount_max = next_amount_to_pay  # Use discounted amount for EPD
        additional_info.update({
            'has_eligible_epd': True,
            'discount_date': next_payment_values.get('discount_date')
        })

    return {
        'currency_id': self.currency_id.id,
        'partner_id': self.partner_id.id,
        'open_installments': open_installments,
        'amount': next_amount_to_pay,
        'amount_max': amount_max,
        **additional_info
    }
```

**Odoo 18→19 Change — Installment Fields:**
- `open_installments` (Json): Stores structured installment data
- `open_installments_preview` (Html): Renders the installment list as HTML
- `display_open_installments`: Controls visibility based on count (> 1)

These replace the previous approach of embedding installment data directly in the payment link.

#### L3: QR Code Generation

```python
def _generate_portal_payment_qr(self):
    self.ensure_one()
    portal_url = self._get_portal_payment_link()
    barcode = self.env['ir.actions.report'].barcode(
        barcode_type="QR",
        value=portal_url,
        width=128,
        height=128,
        quiet=False
    )
    return image_data_uri(base64.b64encode(barcode))
```

The QR code embeds the portal payment URL. When scanned, it opens the invoice's portal payment page. The `quiet=False` parameter adds quiet zones around the QR code for reliable scanning.

#### L4: `get_portal_last_transaction()` — Portal Payment Status

```python
@api.private
def get_portal_last_transaction(self):
    self.ensure_one()
    return self.with_context(active_test=False).sudo().transaction_ids._get_last()
```

Returns the most recent transaction for the invoice, regardless of state. Uses `active_test=False` to include inactive records and `sudo()` to bypass access controls since portal users may not have direct transaction access. This method powers the "Pay Now" button state on the portal: if the last transaction is in `pending` or `authorized` state, the button may be hidden to prevent double-payment.

The `_get_last()` method on `payment.transaction` returns the transaction with the highest `id` (most recently created) from `self`.

#### L4: `_get_portal_payment_link()` — Lazy Payment Link Generation

```python
def _get_portal_payment_link(self):
    self.ensure_one()
    payment_link_wizard = self.env['payment.link.wizard'].with_context(
        active_id=self.id, active_model=self._name
    ).create({
        'amount': self.amount_residual,
        'res_model': self._name,
        'res_id': self.id,
    })
    return payment_link_wizard.link
```

Generates a portal payment URL on-demand by creating a transient `payment.link.wizard` record. The wizard's `link` property (inherited from the `payment` module) computes the full URL with access token. This lazy approach avoids storing payment links — the link is regenerated each time, ensuring the token is always current.

---

### 4. `account.journal` (Extended)

**File:** `models/account_journal.py` | **Inheritance:** `account.journal`

#### Extensions

**`_get_available_payment_method_lines()`**

```python
def _get_available_payment_method_lines(self, payment_type):
    lines = super()._get_available_payment_method_lines(payment_type)
    return lines.filtered(lambda l: l.payment_provider_state != 'disabled')
```

Filters out payment method lines linked to disabled providers. This prevents users from selecting a payment method that would route to an inactive payment provider.

**`_unlink_except_linked_to_payment_provider()`**

```python
@api.ondelete(at_uninstall=False)
def _unlink_except_linked_to_payment_provider(self):
    linked_providers = self.env['payment.provider'].sudo().search([]).filtered(
        lambda p: p.journal_id.id in self.ids and p.state != 'disabled'
    )
    if linked_providers:
        raise UserError(_(
            "You must first deactivate a payment provider before deleting its journal.\n"
            "Linked providers: %s", ', '.join(p.display_name for p in linked_providers)
        ))
```

The `@api.ondelete(at_uninstall=False)` decorator ensures the constraint only runs during normal operation, not during module uninstall. This allows journals to be deleted when the module is uninstalled.

---

### 5. `account.payment.method` (Extended)

**File:** `models/account_payment_method.py` | **Inheritance:** `account.payment.method`

#### Extension

**`_get_payment_method_information()`**

```python
@api.model
def _get_payment_method_information(self):
    res = super()._get_payment_method_information()
    for code, _desc in self.env['payment.provider']._fields['code'].selection:
        if code in ('none', 'custom'):
            continue
        res[code] = {
            'mode': 'electronic',
            'type': ('bank',),
        }
    return res
```

This dynamically registers every active payment provider code as an electronic payment method with `mode='electronic'` and `type=('bank',)`. This is how the account module becomes aware of provider-specific payment methods, enabling them to appear in the payment method line selection.

---

### 6. `account.payment.method.line` (Extended via `AccountPaymentMethodLine`)

**File:** `models/account_payment_method_line.py` | **Inheritance:** `account.payment.method.line`

#### Extended Fields

| Field | Type | Description |
|-------|------|-------------|
| `payment_provider_id` | Many2one (`payment.provider`) | Provider linked to this method line. Computed/stored. Domain: `[('code', '=', code)]`. |
| `payment_provider_state` | Selection | Related provider state (disabled/test/enabled). |

#### L2: `_compute_name()` — Override

```python
@api.depends('payment_provider_id.name')
def _compute_name(self):
    super()._compute_name()
    for line in self:
        if line.payment_provider_id and not line.name:
            line.name = line.payment_provider_id.name
```

When a provider is assigned but the line has no custom name, the provider's name is used as the default.

#### L3: `_compute_payment_provider_id()` — Auto-Assignment

When a payment method line is created for an electronic method, this method auto-assigns an available provider:

```python
@api.depends('payment_method_id')
def _compute_payment_provider_id(self):
    results = self.journal_id._get_journals_payment_method_information()
    manage_providers = results['manage_providers']
    method_information_mapping = results['method_information_mapping']
    providers_per_code = results['providers_per_code']

    for line in self:
        journal = line.journal_id
        company = journal.company_id
        if (
            company
            and line.payment_method_id
            and not line.payment_provider_id
            and manage_providers
            and method_information_mapping.get(line.payment_method_id.id, {}).get('mode') == 'electronic'
        ):
            provider_ids = providers_per_code.get(company.id, {}).get(line.code, set())

            # Exclude providers already assigned to other lines on the same journal
            protected_provider_ids = set()
            for payment_type in ('inbound', 'outbound'):
                lines = journal[f'{payment_type}_payment_method_line_ids']
                for journal_line in lines:
                    if journal_line.payment_method_id:
                        if (
                            manage_providers
                            and method_information_mapping.get(journal_line.payment_method_id.id, {}).get('mode') == 'electronic'
                        ):
                            protected_provider_ids.add(journal_line.payment_provider_id.id)

            candidates_provider_ids = provider_ids - protected_provider_ids
            if candidates_provider_ids:
                line.payment_provider_id = next(iter(candidates_provider_ids))
```

The logic ensures that each provider is linked to at most one payment method line per journal, preventing duplicate assignments.

#### L3: `_unlink_except_active_provider()`

```python
@api.ondelete(at_uninstall=False)
def _unlink_except_active_provider(self):
    active_provider = self.payment_provider_id.filtered(
        lambda provider: provider.state in ['enabled', 'test']
    )
    if active_provider:
        raise UserError(_(
            "You can't delete a payment method that is linked to a provider in the enabled "
            "or test state.\nLinked providers(s): %s",
            ', '.join(a.display_name for a in active_provider),
        ))
```

Prevents accidental deletion of payment method lines that are actively linked to providers.

#### L3: `action_open_provider_form()`

```python
def action_open_provider_form(self):
    self.ensure_one()
    return {
        'type': 'ir.actions.act_window',
        'name': _('Provider'),
        'view_mode': 'form',
        'res_model': 'payment.provider',
        'target': 'current',
        'res_id': self.payment_provider_id.id
    }
```

Provides a quick link from the payment method line to its provider configuration.

---

### 7. `payment.provider` (Extended)

**File:** `models/payment_provider.py` | **Inheritance:** `payment.provider`

#### Extended Fields

| Field | Type | Description |
|-------|------|-------------|
| `journal_id` | Many2one (`account.journal`) | Journal where successful transactions are posted. Computed/inverse. Domain: `[("type", "=", "bank")]`. |

#### L2: Journal Computation and Inverse

**`_compute_journal_id()`**

```python
@api.depends('code', 'state', 'company_id')
def _compute_journal_id(self):
    for provider in self:
        pay_method_line = self.env['account.payment.method.line'].search([
            ('payment_provider_id', '=', provider._origin.id),
            ('journal_id', '!=', False),
        ], limit=1)

        if pay_method_line:
            provider.journal_id = pay_method_line.journal_id
        elif provider.state in ('enabled', 'test'):
            provider.journal_id = self.env['account.journal'].search(
                [('company_id', '=', provider.company_id.id), ('type', '=', 'bank')],
                limit=1,
            )
            if provider.id:
                provider._ensure_payment_method_line()
```

On-demand journal creation: if a provider is enabled but has no journal, it searches for a bank journal and creates the payment method line.

**`_inverse_journal_id()`**

```python
def _inverse_journal_id(self):
    for provider in self:
        provider._ensure_payment_method_line()
```

When the user manually sets a journal, `_ensure_payment_method_line()` is called to sync the payment method line.

#### L3: `_ensure_payment_method_line()` — Provider-to-Accounting Sync

This is the core method for keeping the provider and its payment method line synchronized:

```python
def _ensure_payment_method_line(self, allow_create=True):
    self.ensure_one()
    if not self.id:
        return  # Skip unsaved records

    default_payment_method = self._get_provider_payment_method(self._get_code())
    if not default_payment_method:
        return  # No payment method for this code

    pay_method_line = self.env['account.payment.method.line'].search([
        ('payment_provider_id', '=', self.id),
        ('journal_id', '!=', False),
    ], limit=1)

    # Remove link if journal is cleared
    if not self.journal_id:
        if pay_method_line:
            pay_method_line.unlink()
        return

    # Update existing line
    if pay_method_line:
        pay_method_line.payment_provider_id = self
        pay_method_line.journal_id = self.journal_id
        pay_method_line.name = self.name
    # Create new line
    elif allow_create:
        create_values = {
            'name': self.name,
            'payment_method_id': default_payment_method.id,
            'journal_id': self.journal_id.id,
            'payment_provider_id': self.id,
            'payment_account_id': self._get_payment_method_outstanding_account_id(default_payment_method)
        }
        # Copy payment account from existing line with same code
        pay_method_line_same_code = self.env['account.payment.method.line'].search([
            ('code', '=', self._get_code()),
        ], limit=1)
        if pay_method_line_same_code:
            create_values['payment_account_id'] = pay_method_line_same_code.payment_account_id.id
        self.env['account.payment.method.line'].create(create_values)
```

**L3: `_get_payment_method_outstanding_account_id()`**

```python
def _get_payment_method_outstanding_account_id(self, payment_method_id):
    if self.code == 'custom':
        return False  # Custom providers use the journal's default account
    account_ref = ('account_journal_payment_debit_account_id'
                   if payment_method_id.payment_type == 'inbound'
                   else 'account_journal_payment_credit_account_id')
    chart_template = self.with_context(allowed_company_ids=self.company_id.root_id.ids)\
        .env['account.chart.template']
    outstanding_account_id = (
        chart_template.ref(account_ref, raise_if_not_found=False)
        or self.company_id.transfer_account_id
    ).id
    return outstanding_account_id
```

Determines the outstanding payment account to use for the payment method line:
- Inbound methods: debit account (money coming in)
- Outbound methods: credit account (money going out)
- Falls back to the company's transfer account if the specific journal account is not configured

#### L3: `_setup_provider()` and `_setup_payment_method()`

```python
@api.model
def _setup_provider(self, code, **kwargs):
    super()._setup_provider(code, **kwargs)
    self._setup_payment_method(code)

@api.model
def _setup_payment_method(self, code):
    if code not in ('none', 'custom') and not self._get_provider_payment_method(code):
        providers_description = dict(self._fields['code']._description_selection(self.env))
        self.env['account.payment.method'].sudo().create({
            'name': providers_description[code],
            'code': code,
            'payment_type': 'inbound',
        })
```

Called when a payment provider module is installed. Creates the corresponding `account.payment.method` record so the accounting module knows about the provider's payment method.

#### L3: `_remove_provider()` — Uninstall Guard

```python
def _check_existing_payment(self, payment_method):
    existing_payment_count = self.env['account.payment'].search_count(
        [('payment_method_id', '=', payment_method.id)], limit=1
    )
    return bool(existing_payment_count)

@api.model
def _remove_provider(self, code, **kwargs):
    payment_method = self._get_provider_payment_method(code)
    if self._check_existing_payment(payment_method):
        raise UserError(_(
            "You cannot uninstall this module as payments using this payment method already exist."
        ))
    super()._remove_provider(code, **kwargs)
    payment_method.unlink()
```

Prevents accidental uninstallation of a payment provider that has existing payments, protecting data integrity.

---

## Wizards

### 1. `account.payment.register` (Extended)

**File:** `wizards/account_payment_register.py` | **Inheritance:** `account.payment.register` (from `account` module)

Extends the standard payment registration wizard with token support for electronic payments.

#### Extended Fields

| Field | Type | Description |
|-------|------|-------------|
| `payment_token_id` | Many2one (`payment.token`) | Token to use for the payment. Filtered by `suitable_payment_token_ids`. Only tokens from providers that support direct capture. |
| `suitable_payment_token_ids` | Many2many (`payment.token`) | Computed tokens matching the partner, company, and provider. |
| `use_electronic_payment_method` | Boolean | Whether the selected payment method is electronic. |

#### L2: `_compute_suitable_payment_token_ids()` — Multi-Partner Handling

```python
@api.depends('payment_method_line_id')
def _compute_suitable_payment_token_ids(self):
    for wizard in self:
        wizard.suitable_payment_token_ids = [Command.clear()]
        if wizard.can_edit_wizard and wizard.use_electronic_payment_method:
            token_partners = wizard.partner_id
            lines_partners = wizard.batches[0]['lines'].move_id.partner_id
            if len(lines_partners) == 1:
                token_partners |= lines_partners  # Include both commercial and specific partner
            wizard.suitable_payment_token_ids = self.env['payment.token'].sudo().search([
                *self.env['payment.token']._check_company_domain(wizard.company_id),
                ('partner_id', 'in', token_partners.ids),
                ('provider_id.capture_manually', '=', False),
                ('provider_id', '=', wizard.payment_method_line_id.payment_provider_id.id),
            ])
```

When paying multiple invoices for a single partner, the wizard includes tokens from both the specific partner and their commercial partner. When paying invoices from different partners, only tokens from their shared commercial partner are available.

#### L3: `_create_payment_vals_from_wizard()` — Token Injection

```python
def _create_payment_vals_from_wizard(self, batch_result):
    payment_vals = super()._create_payment_vals_from_wizard(batch_result)
    payment_vals['payment_token_id'] = self.payment_token_id.id
    return payment_vals
```

The token is injected into the payment creation values, which then triggers the token-based `action_post()` flow.

---

### 2. `payment.link.wizard` (Extended)

**File:** `wizards/payment_link_wizard.py` | **Inheritance:** `payment.link.wizard` (from `payment` module)

Extends the generic payment link wizard with invoice-specific fields for installments and early payment discounts.

#### Extended Fields

| Field | Type | Description |
|-------|------|-------------|
| `invoice_amount_due` | Monetary | Alias for `amount_max` (the amount due on the invoice). |
| `open_installments` | Json | **Odoo 19:** Installment data for payment links with multiple installments. Stored as Json. |
| `open_installments_preview` | Html | Rendered HTML preview of installments for portal display. |
| `display_open_installments` | Boolean | Whether to show the installments section (True if > 1 installment). |
| `has_eligible_epd` | Boolean | Whether the invoice qualifies for early payment discount. |
| `discount_date` | Date | Last date to avail the early payment discount. |
| `epd_info` | Char | Computed message about EPD eligibility for display. |

#### L2: `_compute_warning_message()` — Feature Flag Warning

```python
def _compute_warning_message(self):
    super()._compute_warning_message()
    for wizard in self:
        if not wizard.warning_message and not str2bool(
            self.env['ir.config_parameter'].sudo().get_param('account_payment.enable_portal_payment')
        ):
            wizard.warning_message = _("Online payment option is not enabled in Configuration.")
```

Appends a warning if the portal payment feature is disabled, guiding the user to enable it in settings.

#### L2: `_compute_open_installments_preview()` — Html Rendering

```python
@api.depends('open_installments')
def _compute_open_installments_preview(self):
    for wizard in self:
        preview = ""
        if wizard.display_open_installments:
            for installment in wizard.open_installments or []:
                preview += "<div>"
                preview += _(
                    '#%(number)s - Installment of <strong>%(amount)s</strong> '
                    'due on <strong class="text-primary">%(date)s</strong>',
                    number=installment['number'],
                    amount=formatLang(self.env, installment['amount'], currency_obj=wizard.currency_id),
                    date=installment['date_maturity'],
                )
                preview += "</div>"
        wizard.open_installments_preview = preview
```

Renders installment data as HTML with proper currency formatting and date display. The `_()` translation function allows the template to be translated into different languages.

#### L3: `_prepare_url()` — Portal vs Generic Link

```python
def _prepare_url(self, base_url, related_document):
    res = super()._prepare_url(base_url, related_document)
    if self.res_model != 'account.move':
        return res
    return f'{base_url}/{related_document.get_portal_url()}'
```

For invoices, returns the portal page URL instead of the generic payment link. This ensures the user lands on the invoice portal page, not a generic payment page.

#### L3: `_prepare_access_token()` — Amount-Tied Token (Odoo 19 Change)

```python
def _prepare_access_token(self):
    res = super()._prepare_access_token()
    if self.res_model != 'account.move':
        return res
    return payment_utils.generate_access_token(self.res_id, self.amount, env=self.env)
```

**Odoo 18→19 Change:** In Odoo 18, the access token was based solely on the document ID. In Odoo 19, it is tied to both the document ID and the payment amount. This prevents a malicious actor from intercepting a payment link and changing the amount before payment:

```
Odoo 18: token = hash(res_id)
Odoo 19: token = hash(res_id, amount)
```

The `payment_utils.generate_access_token()` function creates a cryptographic token combining both values. When the payment is submitted, the backend verifies both the ID and amount match.

#### L4: `_prepare_query_params()` — Invoice Payment Link Parameters

```python
def _prepare_query_params(self, related_document):
    """ Override of `payment` to define custom query params for invoice payment. """
    res = super()._prepare_query_params(related_document)
    if self.res_model != 'account.move':
        return res

    return {
        'move_id': related_document.id,
        'amount': self.amount,
        'payment_token': self._prepare_access_token(),
        'payment': True,
    }
```

Overwrites the base query params to inject invoice-specific values for the portal payment page. The `payment=True` flag signals the portal controller to use invoice-specific payment routing. `move_id` is used by `payment_pay()` to identify the invoice context, while `payment_token` is the amount-bound access token validated on submission.

#### L4: `_prepare_anchor()` — Portal Anchor Navigation

```python
def _prepare_anchor(self):
    """ Override of `payment` to set the 'portal_pay' anchor. """
    res = super()._prepare_anchor()
    if self.res_model != 'account.move':
        return res

    return '#portal_pay'
```

For invoices, the generated payment link scrolls directly to the `#portal_pay` anchor on the portal invoice page. This anchors to the payment form section, improving UX by eliminating manual scrolling after landing on the page.

---

### 3. `payment.refund.wizard`

**File:** `wizards/payment_refund_wizard.py` | **Inheritance:** None (standalone)

Dedicated wizard for processing refunds on payments created from transactions.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `payment_id` | Many2one (`account.payment`) | The payment to refund. Defaults to active context. |
| `transaction_id` | Many2one (`payment.transaction`) | Related via `payment_id.payment_transaction_id`. |
| `payment_amount` | Monetary | Amount of the original payment (related from payment). |
| `refunded_amount` | Monetary | Amount already refunded (computed: `payment_amount - amount_available_for_refund`). |
| `amount_available_for_refund` | Monetary | Maximum amount that can be refunded (related from payment). |
| `amount_to_refund` | Monetary | Amount the user wants to refund. Default = `amount_available_for_refund`. |
| `currency_id` | Many2one (`res.currency`) | Transaction currency. |
| `support_refund` | Selection | Refund capability: `'none'`, `'full_only'`, `'partial'`. |
| `has_pending_refund` | Boolean | Whether a refund is already in progress (draft/pending/authorized). |

#### L2: Compute Methods

**`_compute_support_refund()`**

```python
@api.depends('transaction_id.provider_id', 'transaction_id.payment_method_id')
def _compute_support_refund(self):
    for wizard in self:
        tx_sudo = wizard.transaction_id.sudo()
        p_support_refund = tx_sudo.provider_id.support_refund
        pm_sudo = tx_sudo.payment_method_id
        pm_support_refund = (pm_sudo.primary_payment_method_id or pm_sudo).support_refund
        if p_support_refund == 'none' or pm_support_refund == 'none':
            wizard.support_refund = 'none'
        elif p_support_refund == 'full_only' or pm_support_refund == 'full_only':
            wizard.support_refund = 'full_only'
        else:
            wizard.support_refund = 'partial'
```

Takes the minimum support level from both the provider and the payment method. If either doesn't support refunds, refunds are blocked.

**`_compute_has_pending_refund()`**

```python
@api.depends('payment_id')
def _compute_has_pending_refund(self):
    for wizard in self:
        pending_refunds_count = self.env['payment.transaction'].search_count([
            ('source_transaction_id', '=', wizard.payment_id.payment_transaction_id.id),
            ('operation', '=', 'refund'),
            ('state', 'in', ['draft', 'pending', 'authorized']),
        ])
        wizard.has_pending_refund = pending_refunds_count > 0
```

Checks for any refund transactions in a non-terminal state. If a refund is stuck (webhook failure, etc.), this prevents duplicate refund attempts.

#### L3: `action_refund()`

```python
def action_refund(self):
    self.ensure_one()
    return self.transaction_id.action_refund(amount_to_refund=self.amount_to_refund)
```

Delegates the actual refund creation to the transaction's `action_refund()` method with the specified amount.

---

## Controllers

### 1. `payment.py` — JSON-RPC Endpoints

**File:** `controllers/payment.py` | **Inheritance:** `payment.controllers.portal.PaymentPortal`

Provides JSON-RPC endpoints for the invoice payment flow. All endpoints use `type='jsonrpc'` for API-style communication.

#### Endpoint: `/invoice/transaction/<int:invoice_id>`

```python
@route('/invoice/transaction/<int:invoice_id>', type='jsonrpc', auth='public')
def invoice_transaction(self, invoice_id, access_token, **kwargs):
    invoice_sudo = self._document_check_access('account.move', invoice_id, access_token)
    logged_in = not request.env.user._is_public()
    partner_sudo = request.env.user.partner_id if logged_in else invoice_sudo.partner_id
    self._validate_transaction_kwargs(kwargs, additional_allowed_keys={'name_next_installment'})
    return self._process_transaction(
        partner_sudo.id, invoice_sudo.currency_id.id, [invoice_id], False, **kwargs
    )
```

Supports `name_next_installment` for paying specific installments on multi-installment invoices.

#### Endpoint: `/invoice/transaction/overdue`

```python
@route('/invoice/transaction/overdue', type='jsonrpc', auth='public')
def overdue_invoices_transaction(self, payment_reference, **kwargs):
    logged_in = not request.env.user._is_public()
    if not logged_in:
        raise ValidationError(_("Please log in to pay your overdue invoices"))
    partner = request.env.user.partner_id
    overdue_invoices = request.env['account.move'].search(self._get_overdue_invoices_domain())
    currencies = overdue_invoices.mapped('currency_id')
    if not all(currency == currencies[0] for currency in currencies):
        raise ValidationError(_("Impossible to pay all the overdue invoices if they don't share the same currency."))
    self._validate_transaction_kwargs(kwargs)
    return self._process_transaction(
        partner.id, currencies[0].id, overdue_invoices.ids, payment_reference, **kwargs
    )
```

Requires authentication. All overdue invoices must share the same currency (enforced before processing). The `payment_reference` parameter is used for the transaction reference prefix.

#### `payment_pay()` Override

Injects invoice values into the payment form context:

```python
def payment_pay(self, *args, amount=None, invoice_id=None, access_token=None, **kwargs):
    invoice_id = self._cast_as_int(invoice_id)
    if invoice_id:
        invoice_sudo = request.env['account.move'].sudo().browse(invoice_id).exists()
        if not invoice_sudo:
            raise ValidationError(_("The provided parameters are invalid."))
        if not payment_utils.check_access_token(
            access_token, invoice_sudo.partner_id.id, amount, invoice_sudo.currency_id.id
        ):
            raise ValidationError(_("The provided parameters are invalid."))
        kwargs.update({
            'reference': invoice_sudo.name,
            'currency_id': invoice_sudo.currency_id.id,
            'partner_id': invoice_sudo.partner_id.id,
            'company_id': invoice_sudo.company_id.id,
            'invoice_id': invoice_id,
        })
    return super().payment_pay(*args, amount=amount, access_token=access_token, **kwargs)
```

The access token check uses both partner ID and amount (Odoo 19 security enhancement).

#### `_get_extra_payment_form_values()` Override

Reroutes the payment flow back to the invoice portal page:

```python
def _get_extra_payment_form_values(self, invoice_id=None, access_token=None, **kwargs):
    form_values = super()._get_extra_payment_form_values(
        invoice_id=invoice_id, access_token=access_token, **kwargs
    )
    if invoice_id:
        invoice_id = self._cast_as_int(invoice_id)
        try:
            invoice_sudo = self._document_check_access('account.move', invoice_id, access_token)
        except AccessError:
            if not payment_utils.check_access_token(
                access_token, kwargs.get('partner_id'), kwargs.get('amount'), kwargs.get('currency_id'),
            ):
                raise
            invoice_sudo = request.env['account.move'].sudo().browse(invoice_id)

        if invoice_sudo.state == 'cancel':
            form_values['amount'] = 0.0

        form_values.update({
            'transaction_route': f'/invoice/transaction/{invoice_id}',
            'landing_route': f'{invoice_sudo.access_url}?access_token={invoice_sudo._portal_ensure_token()}',
            'access_token': invoice_sudo.access_token,
        })
    return form_values
```

The double token check (portal token first, then payment token) handles both authenticated portal access and unauthenticated payment link flows.

---

### 2. `portal.py` — Portal Page Extensions

**File:** `controllers/portal.py` | **Inheritance:** `account.controllers.portal.PortalAccount` + `PaymentPortal`

#### `_invoice_get_page_view_values()`

```python
def _invoice_get_page_view_values(self, invoice, access_token, payment=False, amount=None, **kwargs):
    values = super()._invoice_get_page_view_values(invoice, access_token, amount=amount, **kwargs)

    if not invoice._has_to_be_paid():
        return {**values, 'payment': payment}

    epd = values.get('epd_discount_amount_currency', 0.0)
    discounted_amount = invoice.amount_residual - epd

    common_view_values = self._get_common_page_view_values(
        invoices_data={
            'partner': invoice.partner_id,
            'company': invoice.company_id,
            'total_amount': invoice.amount_total,
            'currency': invoice.currency_id,
            'amount_residual': discounted_amount,
            'landing_route': invoice.get_portal_url(),
            'transaction_route': f'/invoice/transaction/{invoice.id}',
        },
        access_token=access_token,
        **kwargs
    )
    values |= {
        **common_view_values,
        'amount_custom': float(amount or 0.0),
        'payment': payment,
        'invoice_id': invoice.id,
        'invoice_name': invoice.name,
        'show_epd': epd,
    }
    return values
```

The EPD discount reduces the displayed `amount_residual` so the customer sees the amount they'd pay after applying the early payment discount.

#### `portal_my_overdue_invoices()` — `/my/invoices/overdue`

```python
@http.route(['/my/invoices/overdue'], type='http', auth='public', methods=['GET'], website=True, sitemap=False)
def portal_my_overdue_invoices(self, access_token=None, **kw):
    try:
        request.env['account.move'].check_access('read')
    except (AccessError, MissingError):
        return request.redirect('/my')

    overdue_invoices = request.env['account.move'].search(self._get_overdue_invoices_domain())
    values = self._overdue_invoices_get_page_view_values(overdue_invoices, **kw)
    return request.render(
        "account_payment.portal_overdue_invoices_page", values
    ) if 'payment' in values else request.redirect('/my/invoices')
```

The `_get_overdue_invoices_domain()` is provided by the parent `PortalAccount` class (from `account` module). It filters for posted invoices with past due dates and outstanding residual amounts.

#### `_overdue_invoices_get_page_view_values()`

```python
def _overdue_invoices_get_page_view_values(self, overdue_invoices, **kwargs):
    values = {'page_name': 'overdue_invoices'}
    if len(overdue_invoices) == 0:
        return values

    first_invoice = overdue_invoices[0]
    partner = first_invoice.partner_id
    company = first_invoice.company_id
    currency = first_invoice.currency_id

    if any(invoice.partner_id != partner for invoice in overdue_invoices):
        raise ValidationError(_("Overdue invoices should share the same partner."))
    if any(invoice.company_id != company for invoice in overdue_invoices):
        raise ValidationError(_("Overdue invoices should share the same company."))
    if any(invoice.currency_id != currency for invoice in overdue_invoices):
        raise ValidationError(_("Overdue invoices should share the same currency."))

    total_amount = sum(overdue_invoices.mapped('amount_total'))
    amount_residual = sum(overdue_invoices.mapped('amount_residual'))
    batch_name = company.get_next_batch_payment_communication() if len(overdue_invoices) > 1 else first_invoice.name

    values.update({
        'payment': {
            'date': fields.Date.today(),
            'reference': batch_name,
            'amount': total_amount,
            'currency': currency,
        },
        'amount': total_amount,
    })
    common_view_values = self._get_common_page_view_values(
        invoices_data={
            'partner': partner,
            'company': company,
            'total_amount': total_amount,
            'currency': currency,
            'amount_residual': amount_residual,
            'payment_reference': batch_name,
            'landing_route': '/my/invoices/',
            'transaction_route': '/invoice/transaction/overdue',
        },
        **kwargs)
    values |= common_view_values
    return values
```

All overdue invoices must share the same partner, company, and currency. When paying multiple invoices, a batch name is generated using `company.get_next_batch_payment_communication()` for the payment reference.

#### `_get_common_page_view_values()`

The core method that gathers all payment context:

```python
def _get_common_page_view_values(self, invoices_data, access_token=None, **kwargs):
    logged_in = not request.env.user._is_public()
    partner_sudo = request.env.user.partner_id if logged_in else invoices_data['partner']
    invoice_company = invoices_data['company'] or request.env.company

    availability_report = {}
    providers_sudo = request.env['payment.provider'].sudo()._get_compatible_providers(
        invoice_company.id, partner_sudo.id, invoices_data['total_amount'],
        currency_id=invoices_data['currency'].id, report=availability_report, **kwargs,
    )
    payment_methods_sudo = request.env['payment.method'].sudo()._get_compatible_payment_methods(
        providers_sudo.ids, partner_sudo.id, currency_id=invoices_data['currency'].id,
        report=availability_report,
    )
    tokens_sudo = request.env['payment.token'].sudo()._get_available_tokens(
        providers_sudo.ids, partner_sudo.id
    )

    company_mismatch = not PaymentPortal._can_partner_pay_in_company(partner_sudo, invoice_company)

    payment_context = {
        'currency': invoices_data['currency'],
        'partner_id': partner_sudo.id,
        'providers_sudo': providers_sudo,
        'payment_methods_sudo': payment_methods_sudo,
        'tokens_sudo': tokens_sudo,
        'transaction_route': invoices_data['transaction_route'],
        'landing_route': invoices_data['landing_route'],
        'access_token': access_token,
        'payment_reference': invoices_data.get('payment_reference', False),
    }
    values = {...} | {...} | payment_context | self._get_extra_payment_form_values(**kwargs)
    return values
```

All provider, method, and token lookups are done in `sudo()` mode because the portal user may not have direct access to these models. The `availability_report` captures why specific providers/methods are unavailable (for display in the payment form).

#### L4: `portal_my_invoice_detail()` — Access Token Tampering Guard

```python
@http.route()
def portal_my_invoice_detail(self, invoice_id, payment_token=None, amount=None, **kw):
    # EXTENDS account

    # If we have a custom payment amount, make sure it hasn't been tampered with
    if amount and not payment_utils.check_access_token(payment_token, invoice_id, amount):
        return request.redirect('/my')
    return super().portal_my_invoice_detail(invoice_id, amount=amount, **kw)
```

This override guards against **payment amount tampering** on the invoice detail page. Even though `_prepare_access_token()` in the payment link wizard already ties the token to `(res_id, amount)`, this second check on the invoice portal page provides defense-in-depth. If a malicious actor crafts a URL with a different `amount` parameter than what was signed into the token, the request is silently redirected to `/my` rather than processing the tampered amount.

The `super()` call delegates to the standard portal invoice detail handler in the `account` module.

#### L4: Batch Payment Context in Overdue Invoice Flow

In the overdue invoice batch flow, the payment `reference` is set using `company.get_next_batch_payment_communication()`. This generates a sequential batch reference (e.g., `BNK/2026/04/0001`) that ties all invoices in the batch to a single payment communication. The reference appears in the transaction and payment `memo` field, and is used as the `reference_prefix` when creating the transaction via `_process_transaction()`.

This differs from single-invoice payments where `invoice_sudo.name` (e.g., `INV/2026/04/0001`) is used as the reference.

---

## Hooks

### `__init__.py`

**`post_init_hook(env)`** — Runs after module installation:

```python
def post_init_hook(env):
    PaymentProvider = env['payment.provider']
    installed_providers = PaymentProvider.search([('module_id.state', '=', 'installed')])
    for code in set(installed_providers.mapped('code')):
        PaymentProvider._setup_payment_method(code)
```

Creates `account.payment.method` records for all already-installed payment provider modules. This ensures that if `payment_stripe` is installed before `account_payment`, the payment method is still created.

**`uninstall_hook(env)`** — Runs before module uninstallation:

```python
def uninstall_hook(env):
    installed_providers = env['payment.provider'].search([('module_id.state', '=', 'installed')])
    env['account.payment.method'].search([
        ('code', 'in', installed_providers.mapped('code')),
        ('payment_type', '=', 'inbound'),
    ]).unlink()
```

Removes only the payment method records. The provider's `_remove_provider` hook in `payment_provider.py` additionally blocks uninstallation if payments exist using that provider's method.

---

## Security

### Record Rules

The module defines record rules in `ir_rules.xml` that work in conjunction with the `bypass_search_access=True` on `payment_transaction_id`. Since users who can access a payment can also access its transaction (they represent the same business operation), the access bypass is safe.

### SQL Injection Prevention

All raw SQL uses parameterized queries:

```python
self.env.cr.execute(
    '''SELECT transaction_id, count(invoice_id)
       FROM account_invoice_transaction_rel
       WHERE transaction_id IN %s
       GROUP BY transaction_id''',
    [tuple(self.ids)]  # Parameterized — prevents SQL injection
)
```

### Portal Access Control

- `auth='public'` on invoice endpoints: Allows unauthenticated payment via access tokens
- Access token validation: Tied to (res_id, amount) in Odoo 19, preventing tampering
- Company mismatch check: Partners can only pay invoices in companies they're associated with

---

## Configuration

### `ir.config_parameter` Settings

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `account_payment.enable_portal_payment` | Boolean | `False` | Enables/disables online invoice payment on the portal. Controlled via `ResConfigSettings.pay_invoices_online`. When `False`, `_has_to_be_paid()` returns `False` and the "Pay Now" button is hidden. |

### ResConfigSettings

```python
class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pay_invoices_online = fields.Boolean(config_parameter='account_payment.enable_portal_payment')
```

A single checkbox in Settings > Accounting > Payments controls the entire portal payment feature.

#### L4: `ir.config_parameter` Lifecycle and Data File

The module ships a `data/ir_config_parameter.xml` file that initializes the default value for the portal payment setting:

```xml
<record id="account_payment.enable_portal_payment" model="ir.config_parameter">
    <field name="key">account_payment.enable_portal_payment</field>
    <field name="value">False</field>
</record>
```

Key lifecycle notes:
- **Default is `False`**: Portal payment is opt-in. Even after installing `account_payment`, the feature must be explicitly enabled in settings.
- **Per-database**: `ir.config_parameter` records are stored in the database, not the module file. The XML only sets the default on first installation.
- **Security implication**: Since this is a company-wide setting, only users with `Settings` access (typically administrators) can change it.
- **`str2bool()` guard**: All code checking this parameter uses `str2bool()` from `odoo.tools`, which safely converts string values to boolean, handling `0`, `false`, `False`, etc.

---

## Key Odoo 18 to 19 Changes Summary

| Feature | Odoo 18 | Odoo 19 | Impact |
|---------|---------|---------|--------|
| `invoice_ids` on transaction | `Many2one` (single) | `Many2many` | Enables batch payment of multiple overdue invoices |
| Installment data | Embedded in payment link | `Json` + `Html` fields | Cleaner data structure, better portal rendering |
| Access tokens | Tied to `res_id` only | Tied to `(res_id, amount)` | Prevents payment amount tampering |
| `payment_transaction_id` | No bypass flag | `bypass_search_access=True` | Safe access to transactions via payments |
| `_post_process` cancel | No explicit cancel | `tx.payment_id.action_cancel()` | Cancelled transactions properly revert payments |
| EPD in `_create_payment()` | Not present | Added | Automatic discount application on payment |
| `destination_account_id` | Partner receivable | From payment term lines | Correct account for installment payments |
| `source_payment_id` index | Standard index | `btree_not_null` | Partial index for performance |
| Token access | No sudo | `sudo()` on token search | Handles access rights mismatch for payment users |
| Refund tracking | Via transaction only | Via `source_payment_id` | Enables refunds_count and traceability |

---

## Tests

### Test Files

The module includes a test suite under `tests/` with the following structure:

```
tests/
├── __init__.py
├── common.py                  # AccountPaymentCommon — shared fixtures
├── test_account_payment.py    # Unit tests for payment/refund logic
├── test_payment_flows.py      # Integration tests for portal flows
└── test_payment_provider.py   # Provider journal assignment tests
```

#### `common.py` — Shared Test Fixtures (`AccountPaymentCommon`)

Provides standard setup for all test classes:
- Creates a `res.company` or uses an existing one
- Sets up a `payment.provider` (test mode)
- Creates an `account.journal` linked to the provider
- Sets up a `res.partner` for payment testing
- Creates an `account.move` (customer invoice) in `posted` state

#### `test_account_payment.py` — Core Payment Logic

Tests cover:
- `_compute_amount_available_for_refund()` — full, partial, no refunds
- `_create_payment_transaction()` with token
- `action_post()` with token-based payment (creates and charges transaction)
- `action_refund_wizard()` and refund wizard field computations
- `action_view_refunds()` navigation

#### `test_payment_flows.py` — Portal and Controller Integration

Tests cover:
- `_has_to_be_paid()` eligibility conditions
- `_get_online_payment_error()` error message generation
- `/invoice/transaction/<id>` endpoint
- Access token validation (tamper resistance)
- Overdue invoice batch payment flow

#### `test_payment_provider.py` — Provider Journal Assignment

Tests cover:
- `_compute_journal_id()` auto-assignment
- `_ensure_payment_method_line()` creation and update
- `_inverse_journal_id()` setter
- Journal deletion protection via `_unlink_except_linked_to_payment_provider()`

#### L4: Testing Considerations

Key testing patterns used:
- `test_tags`: Tests may be tagged `['post_install', 'at_install']` to control execution timing. Payment tests typically require `post_install` because they need full module initialization.
- `HttpCase` vs `TransactionCase`: Portal flow tests extend `HttpCase` for HTTP endpoint testing; core logic tests use `TransactionCase`.
- `mock`: Provider-specific tests may mock `_charge_with_token()` or provider API calls to test accounting logic without live payment processing.
- chatter tests: `_log_message_on_linked_documents()` is tested by verifying `message_ids` on linked invoices and payments after transaction confirmation.

---

## Related Documentation

- [[Modules/Payment]] — Payment provider base module (`payment`)
- [[Modules/Account]] — Accounting core module (`account`)
- [[Modules/Sale]] — Sales order with payment integration
- [[Core/API]] — @api decorators (@api.depends, @api.ondelete, etc.)
- [[Core/Fields]] — Field types (Monetary, Many2many, Json, Html)
- [[Patterns/Security Patterns]] — Access control and record rules
