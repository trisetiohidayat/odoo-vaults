# Odoo 18 account_payment Module - L3 Documentation

## Module Overview
**Path:** `~/odoo/odoo18/odoo/addons/account_payment/models/`
**Purpose:** Payment transaction handling and payment processing integration

---

## Core Models

### 1. payment.transaction (Payment Transaction)

Inherits from `payment.transaction` in the `payment` module.

#### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `payment_id` | Many2one | Linked account.payment |
| `invoice_ids` | Many2many | Invoices being paid |
| `invoices_count` | Integer | Number of linked invoices |

#### Transaction States

| State | Description |
|-------|-------------|
| `draft` | Created, awaiting processing |
| `pending` | Processing initiated |
| `authorized` | Payment authorized |
| `done` | Payment successful |
| `cancel` | Payment cancelled |
| `error` | Payment failed |

#### Transaction Operations

| Operation | Description |
|-----------|-------------|
| `online_redirect` | Customer redirected to payment provider |
| `online_token` | Using saved token/card |
| `validation` | Card validation without charge |
| `offline` | Offline payment initiated |
| `refund` | Refund transaction |
| `v-offline` | Vendor offline payment |
| `s-offline` | Settlement offline |

#### Key Methods

**`_post_process()`** - Post-processes confirmed transactions
- Validates draft invoices linked to transaction
- Creates missing payments via `_create_payment()`
- Logs messages on linked documents
- Cancels payments for cancelled transactions

**`_create_payment(**extra_create_values)`** - Creates account.payment
- Prepares payment values from transaction
- Handles early payment discounts on invoices
- Creates and posts the payment
- Reconciles payment with invoices
- Sets one-to-one link via `payment_id`

**`_log_message_on_linked_documents(message)`** - Posts to chatter
- On transaction and invoices
- Uses source transaction if available

**`_get_invoices_to_notify()`** - Returns invoices for notification

**`_compute_reference_prefix(provider_code, separator, **values)`** - Computes reference
- Uses invoice names if available
- Allows override via `name_next_installment`

#### Payment Flow Integration

```
Transaction confirmed (done)
    ↓
_post_process() called
    ↓
1. Validate draft invoices
2. Create payment (if needed)
3. Reconcile payment with invoices
4. Log message
```

#### Reconciliation Logic

```python
# Reconcile based on operation type
if self.operation == self.source_transaction_id.operation:
    invoices = self.source_transaction_id.invoice_ids
else:
    invoices = self.invoice_ids

# Filter and post draft invoices
invoices.filtered(lambda inv: inv.state == 'draft').action_post()

# Reconcile matching lines
(payment.move_id.line_ids + invoices.line_ids).filtered(
    lambda line: line.account_id == payment.destination_account_id
    and not line.reconciled
).reconcile()
```

#### Edge Cases

1. **Validation transactions**: No payment created
2. **Partial captures**: Reconciliation via child transactions
3. **Refund transactions**: Linked to source via `source_transaction_id`
4. **Multi-invoice**: Handles multiple invoices per transaction
5. **Early payment discount**: Computes and applies if applicable

---

### 2. account.payment Extension (account_payment)

Extends `account.payment` from core account module.

#### Additional Fields

| Field | Type | Description |
|-------|------|-------------|
| `payment_transaction_id` | Many2one | Linked transaction |
| `payment_token_id` | Many2one | Saved payment token |
| `amount_available_for_refund` | Monetary | Amount that can be refunded |
| `suitable_payment_token_ids` | Many2many | Available tokens |
| `use_electronic_payment_method` | Boolean | Electronic payment flag |
| `source_payment_id` | Many2one | Source of refund payments |
| `refunds_count` | Integer | Number of refunds |

#### Key Methods

**`action_post()`** - Enhanced post with transaction handling
```python
# For payments with token but no transaction
if payment.payment_token_id and not payment.payment_transaction_id:
    # Create transaction (sudo for provider access)
    tx = payment.sudo()._create_payment_transaction()

# Process transactions
for tx in transactions:
    tx._send_payment_request()

# Post payments for completed transactions
for tx in transactions:
    if tx.state == 'done':
        super().action_post()  # Post the payment
    else:
        action_cancel()  # Cancel if failed
```

**`_create_payment_transaction(**extra_create_values)`** - Creates payment transaction
- Validates no existing transaction
- Validates payment token exists
- Prepares transaction vals
- Links transaction to payment

**`_prepare_payment_transaction_vals(**extra_create_values)`** - Prepares vals
- Extracts invoice IDs from context
- Sets operation to 'offline'
- Includes invoice_ids for reconciliation

**`_compute_amount_available_for_refund()`** - Computes refundable amount
- Checks provider refund support
- Subtracts existing refund payments
- Only for non-refund operations

#### Refund Handling

```python
# Only refund if:
# 1. Transaction exists
# 2. Provider supports refunds
# 3. Token allows captures
# 4. Not already a refund transaction
```

---

### 3. payment.provider (Extended)

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `journal_id` | Many2one | Payment journal |
| `support_refund` | Selection | none, partial, full |

---

### 4. payment.token (Payment Token)

#### Purpose
Stores saved payment method credentials for recurring payments.

#### Key Fields

| Field | Type | Description |
|-------|------|-------------|
| `provider_id` | Many2one | Payment provider |
| `payment_method_id` | Many2one | Payment method |
| `partner_id` | Many2one | Customer |
| `capture_manually` | Boolean | Manual capture flag |

---

### 5. account.payment.method (Payment Method)

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `code` | Char | Method code |
| `name` | Char | Method name |
| `payment_type` | Selection | inbound, outbound |
| `provider_ids` | Many2many | Supported providers |

---

### 6. account.payment.method.line (Payment Method Line)

Links payment methods to journals and providers.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `journal_id` | Many2one | Journal |
| `payment_method_id` | Many2one | Payment method |
| `name` | Char | Display name |
| `sequence` | Integer | Priority order |
| `provider_id` | Many2one | Provider (optional) |
| `payment_account_id` | Many2one | Specific account |

---

## Payment Flow Architecture

### Online Payment Flow

```
1. Customer selects payment on website
2. Transaction created with operation='online_redirect'
3. Customer redirected to provider
4. Provider processes payment
5. Webhook received with result
6. _process_notification_data() called
7. Transaction state updated
8. _post_process() triggers:
   - Invoice validation (if draft)
   - Payment creation
   - Reconciliation
```

### Token Payment Flow

```
1. Customer has saved token
2. Payment created with payment_token_id
3. action_post() creates transaction
4. _send_payment_request() processes
5. _post_process() completes flow
```

### Manual Payment Flow

```
1. Payment created without token
2. No transaction created
3. action_post() posts directly
4. Manual reconciliation if needed
```

---

## Cross-Module Integration

### With account module

| Integration | Mechanism |
|-------------|-----------|
| Payment journal entry | `move_id` on account.payment |
| Invoice reconciliation | Reconcile via `_create_payment()` |
| Refund handling | Via `source_payment_id` link |
| Payment state | Updates `payment_state` on move |

### With payment module

| Integration | Mechanism |
|-------------|-----------|
| Transaction processing | Inherits payment.transaction |
| Provider communication | Via provider-specific methods |
| Token management | payment.token model |
| Webhook handling | `_process_notification_data()` |

---

## Webhook Processing

### Key Methods

**`_get_tx_from_notification_data(provider_code, data)`** - Finds transaction
- Implemented by provider-specific modules
- Returns matching transaction or creates new

**`_process_notification_data(data)`** - Updates transaction state
- Validates notification
- Updates `provider_reference`
- Sets state based on result

**`_process_feedback_data(data)`** - Processes feedback
- Generic processing logic
- Calls provider-specific method

### Security

- Hash validation on notifications
- Provider reference uniqueness
- Idempotency handling

---

## Early Payment Discount Handling

When paying before due date:

```python
# In _create_payment():
for invoice in self.invoice_ids:
    if invoice.state != 'posted':
        continue

    # Check for early payment discount
    next_payment_values = invoice._get_invoice_next_payment_values()

    if (epd_conditions_met):
        # Get early payment lines
        aml_values_list = [...]

        # Compute discount entries
        early_payment_values = invoice._get_invoice_counterpart_amls_for_early_payment_discount(...)

        # Add to payment write-off
        payment_values['write_off_line_vals'] += aml_values_list
```

---

## Refund Processing

### Refund Flow

```
1. User requests refund via action_refund_wizard()
2. Wizard collects amount and reason
3. New transaction created with operation='refund'
4. _create_payment() for refund
5. Reconciliation with original invoice
```

### Amount Available for Refund

```python
# Computed as:
available = payment.amount
# Minus all refund payments
for refund in existing_refunds:
    available -= abs(refund.amount)
```

---

## State Transitions

### Transaction States

```
draft → pending → authorized → done
                ↓         ↓
              cancel    error

draft → pending → done → cancel (refund)
```

### Payment States (Extended)

```
draft → in_process → paid
         ↓         ↓
       cancel    rejected
```

---

## Edge Cases & Failure Modes

1. **Webhook failure**: Transaction stuck in pending
   - Manual intervention required
   - Payment stays in 'in_process'

2. **Partial capture**: Multiple child transactions
   - Parent transaction not reconciled
   - Child transactions reconciled

3. **Token expiry**: Saved token becomes invalid
   - Payment fails at `_send_payment_request()`
   - User must update payment method

4. **Provider outage**: Transaction in limbo
   - Polling mechanism (if configured)
   - Manual state override possible

5. **Currency mismatch**: Invoice and payment currencies differ
   - Handled via `_prepare_move_line_default_vals()`
   - Exchange differences tracked

6. **Multi-invoice payment**: Single payment for multiple invoices
   - Distributed across invoices in reconciliation
   - Each invoice updated independently

7. **Refund exceeds original**: Validated against `amount_available_for_refund`

---

## Security Considerations

1. **sudo() usage**: For provider access during transaction creation
2. **Token security**: Only tokens for matching provider/partner
3. **Amount validation**: Check for negative amounts
4. **Provider reference**: Uniqueness enforced
5. **Operation validation**: Only allowed operations per provider

---

## Performance Considerations

1. **Batch reconciliation**: Groups lines before reconcile
2. **Caching**: Transaction state cached
3. **Minimal queries**: Single query for invoice matching
4. **Idempotent webhooks**: Duplicate detection

---

## Extension Points

### Custom Provider Integration

```python
class PaymentTransaction(models.AbstractModel):
    _inherit = 'payment.transaction'

    def _process_notification_data(self, data):
        # Provider-specific processing
        return super()._process_notification_data(data)

    def _get_tx_from_notification_data(self, provider_code, data):
        # Provider-specific lookup
        return super()._get_tx_from_notification_data(provider_code, data)
```

### Custom Payment Creation

```python
# Override _create_payment() to add:
# - Custom payment values
# - Additional reconciliation logic
# - Extra write-off handling
```

---

## Database Schema

### Key Tables

- `payment_transaction`: Core transaction data
- `account_invoice_transaction_rel`: Many2many with invoices
- `account_move__account_payment`: Many2many with payments
- `payment_token`: Saved payment methods

### Indexes

```sql
CREATE INDEX payment_transaction_provider_reference ON payment_transaction(provider_reference);
CREATE INDEX account_payment_payment_idx ON account_payment(journal_id, company_id) WHERE NOT is_matched OR is_matched IS NULL;
```

---

## Related Modules

- `payment`: Base payment framework
- `payment_adyen`: Adyen provider
- `payment_stripe`: Stripe provider
- `payment_paypal`: PayPal provider
- `account`: Core accounting
- `sale`: Sales order integration
- `website_sale`: E-commerce integration
