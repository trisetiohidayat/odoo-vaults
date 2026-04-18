---
uuid: e5f9d2b3-4c6a-7b8c-9d0e-1f2a3b4c5d6e
tags:
  - odoo
  - odoo19
  - modules
  - payment
  - payment-provider
  - wire-transfer
  - manual-payment
---

# Payment Custom (`payment_custom`)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Payment Provider: Custom Payment Modes |
| **Technical** | `payment_custom` |
| **Category** | Accounting/Payment Providers |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Depends** | `payment` |

## Description

The Custom payment module provides a flexible payment provider that allows businesses to configure their own manual payment flows. Unlike fully automated payment gateways that process transactions electronically, the Custom payment provider enables offline payment methods where customers receive payment instructions and make payments through channels outside of Odoo (such as bank transfers).

This module is particularly useful for:

- **Bank Wire Transfers**: Displaying company bank details for customers to make manual transfers
- **Pending Payment Workflow**: Allowing time for payment verification before order processing
- **Invoice-based Payments**: When invoices are sent separately and payment is expected via traditional banking
- **B2B Scenarios**: Where payment terms and bank transfers are standard practice
- **Cash Payments**: When customers pay in person after order confirmation

The module's key differentiator is its ability to dynamically pull bank account information from Odoo's configured journals, ensuring that payment details displayed to customers are always current and accurate.

## Key Features

### Wire Transfer Support

The primary use case is enabling wire transfer (bank transfer) payments:

- **Dynamic Bank Details**: Automatically pulls bank accounts from `account.journal` records
- **Multiple Accounts**: Supports displaying multiple bank accounts
- **QR Code Generation**: Optional QR code generation for easier bank transfer initiation
- **Custom Pending Messages**: Configurable messages shown until payment is confirmed

### Pending Payment Workflow

Unlike instant payment methods, wire transfers require a manual verification step:

1. Customer places order and selects wire transfer payment
2. Order is confirmed but marked as awaiting payment
3. Customer makes bank transfer (externally)
4. Business verifies receipt of payment
5. Payment is manually confirmed in Odoo
6. Order processing continues

This workflow is common in B2B transactions where payment verification is part of the accounts receivable process.

### Auto-Clear Pending

When a wire transfer provider is created, the module automatically sets `pending_msg` to `None`. This forces the system to recompute the message and include actual bank account details from configured journals. This ensures customers always see real, current bank information.

### QR Code Support

For customers who prefer scanning to typing, the module supports generating QR codes that can be scanned with banking apps to initiate transfers:

```python
qr_code = fields.Boolean(
    string="Enable QR Codes",
    help="Enable the use of QR-codes when paying by wire transfer."
)
```

QR code generation uses Odoo's standard QR code mechanism and is rendered in the payment form.

## Technical Architecture

### Module Structure

```
payment_custom/
├── __init__.py
├── const.py                  # Constants for payment method codes
└── models/
    ├── __init__.py
    └── payment_provider.py    # PaymentProvider extension
```

### Data Flow

```
Customer Checkout
    │
    ▼
Select Wire Transfer Payment
    │
    ▼
Payment Form Displays
    │
    ├── Bank Account Details (from account.journal)
    ├── QR Code (if enabled)
    └── Pending Message Instructions
    │
    ▼
Customer Initiates Bank Transfer (external)
    │
    ▼
Business Receives Payment
    │
    ▼
Manual Payment Confirmation
    │
    ├── Mark transaction as done in Odoo
    ├── Payment registered in Odoo
    └── Order continues processing
```

## Provider Configuration Fields

### Core Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `code` | Selection | Yes | Fixed value: `custom` |
| `custom_mode` | Selection | Yes (if code=`custom`) | Must be `wire_transfer` |
| `qr_code` | Boolean | No | Enable QR code generation |
| `pending_msg` | Html | No | Message shown until payment confirmed |

### Field Details

**`custom_mode`**

Currently only supports `wire_transfer`:

```python
custom_mode = fields.Selection(
    string="Custom Mode",
    selection=[('wire_transfer', "Wire Transfer")],
    required_if_provider='custom',
)
```

A database constraint ensures only custom providers have a custom mode:

```python
_custom_providers_setup = models.Constraint(
    "CHECK(custom_mode IS NULL OR (code = 'custom' AND custom_mode IS NOT NULL))",
    'Only custom providers should have a custom mode.',
)
```

**`qr_code`**

When enabled, the payment form displays a QR code containing:
- Company bank account details
- Payment reference (transaction reference)
- Amount and currency

This allows customers with mobile banking apps to scan and pay easily.

## Models Extended

### `payment.provider` (Extended)

The module extends the base payment provider model:

#### Field Extension

```python
code = fields.Selection(
    selection_add=[('custom', "Custom")],
    ondelete={'custom': 'set default'}
)
custom_mode = fields.Selection(...)
qr_code = fields.Boolean(...)
```

#### Key Methods

**`create()` - Auto-pending Message**

When a wire transfer provider is created, pending_msg is automatically nullified to trigger recomputation with actual bank accounts:

```python
@api.model_create_multi
def create(self, vals_list):
    providers = super().create(vals_list)
    providers.filtered(lambda p: p.custom_mode == 'wire_transfer').pending_msg = None
    return providers
```

**`action_recompute_pending_msg()`**

Recomputes the pending message to include bank accounts from `account.journal` records:

```python
def action_recompute_pending_msg(self):
    for provider in self.filtered(lambda p: p.custom_mode == 'wire_transfer'):
        company_id = provider.company_id.id
        accounts = self.env['account.journal'].search([
            *self.env['account.journal']._check_company_domain(company_id),
            ('type', '=', 'bank'),
        ]).bank_account_id
        
        account_names = "".join(
            f"<li><pre>{account.display_name}</pre></li>" 
            for account in accounts
        )
        provider.pending_msg = f'<div>' \
            f'<h5>{_("Please use the following transfer details")}</h5>' \
            f'<p><br></p>' \
            f'<h6>{_("Bank Account") if len(accounts) == 1 else _("Bank Accounts")}</h6>' \
            f'<ul>{account_names}</ul>' \
            f'<p><br></p>' \
            f'</div>'
```

This method:
1. Searches for bank journals belonging to the provider's company
2. Extracts the bank account from each journal
3. Builds an HTML list of account details
4. Updates the pending_msg with formatted bank information

**`_transfer_ensure_pending_msg_is_set()`**

Cron/job helper method to ensure all wire transfer providers have a pending message:

```python
def _transfer_ensure_pending_msg_is_set(self):
    transfer_providers_without_msg = self.filtered(
        lambda p: p.custom_mode == 'wire_transfer' and not p.pending_msg
    )
    if transfer_providers_without_msg:
        transfer_providers_without_msg.action_recompute_pending_msg()
```

This can be called by a scheduled action to handle cases where:
- New bank accounts are added
- Existing accounts are modified
- Providers were created before bank accounts were set up

**`_get_provider_domain()`**

Extends the provider domain to filter by custom mode:

```python
@api.model
def _get_provider_domain(self, provider_code, *, custom_mode='', **kwargs):
    res = super()._get_provider_domain(provider_code, custom_mode=custom_mode, **kwargs)
    if provider_code == 'custom' and custom_mode:
        return Domain.AND([res, [('custom_mode', '=', custom_mode)]])
    return res
```

**`_get_removal_values()`**

Nullifies custom_mode when the provider is removed:

```python
@api.model
def _get_removal_values(self):
    res = super()._get_removal_values()
    res['custom_mode'] = None
    return res
```

**`_get_default_payment_method_codes()`**

Returns wire_transfer as the default payment method code:

```python
def _get_default_payment_method_codes(self):
    if self.code != 'custom' or self.custom_mode != 'wire_transfer':
        return super()._get_default_payment_method_codes()
    return const.DEFAULT_PAYMENT_METHOD_CODES
```

## Bank Account Integration

### How Bank Accounts Are Retrieved

The module queries `account.journal` records to find bank accounts:

1. **Search Criteria**:
   - Journal type must be 'bank'
   - Journal must belong to the provider's company

2. **Bank Account Extraction**:
   - From each bank journal, get the `bank_account_id` field
   - The `bank_account_id` is a Many2one to `res.partner.bank`

3. **Display**:
   - Uses `display_name` which includes bank name, account number, and IBAN
   - Displayed in a `<pre>` block for consistent formatting

### Configuration in Odoo

For bank accounts to appear correctly:

1. **Create Bank Journal**: Settings > Accounting > Journals > New
   - Type: Bank
   - Name: Your bank name
   - Bank Account: Enter account details

2. **Configure Provider**: Website > Administration > Payment Providers
   - Select Custom provider
   - Custom Mode: Wire Transfer
   - Select Company (if multi-company)

3. **Recompute Message**: Click "Recompute Pending Message" or wait for scheduled action

## Payment Flow: Wire Transfer

### Customer Journey

#### Step 1: Selecting Wire Transfer

1. Customer proceeds to checkout on Odoo e-commerce or portal
2. Customer selects "Wire Transfer" as payment method
3. Payment form displays with bank account details

#### Step 2: Displayed Information

The payment form shows:

```
Please use the following transfer details

Bank Accounts:
- Bank: First National Bank
  Account: 1234567890
  IBAN: ZA00FNBZ000000000000
  Branch: 250655
```

If QR codes are enabled, a scannable QR code is also displayed.

#### Step 3: Customer Initiates Transfer

1. Customer opens their banking app or website
2. Customer enters/scans the bank details
3. Customer initiates the transfer with the transaction reference

#### Step 4: Waiting Period

The order/sale remains in a pending state while:
- The transfer is processed by banks (may take 1-3 business days)
- The business receives and verifies the funds

#### Step 5: Payment Confirmation

1. Business receives notification from bank (or checks statements)
2. Accountant or admin marks the payment as received in Odoo
3. Odoo transaction state changes from `pending` to `done`
4. Order processing continues (delivery, invoicing, etc.)

## Payment Method Configuration

### Creating a Custom Payment Method

In the Odoo interface:

1. Navigate to **Website > Administration > Payment Providers**
2. Click **New**
3. Select **Custom** from the Provider dropdown
4. Set **Custom Mode** to "Wire Transfer"
5. Optionally enable **QR Codes**
6. Configure company and other settings
7. Click **Recompute Pending Message** to fetch bank details

### Payment Method in Payment Form

The wire transfer payment method is added automatically when the provider is configured:

```python
# const.py
DEFAULT_PAYMENT_METHOD_CODES = {
    'wire_transfer',
}
```

This creates a `payment.method` record that appears in the payment form selection.

## Customizing the Pending Message

### Default Behavior

By default, the pending message includes bank account details automatically extracted from journal configurations. This ensures customers always see accurate, up-to-date information.

### Manual Customization

Administrators can override the pending message by:

1. Editing the provider record
2. Modifying the **Pending Message** HTML field
3. Saving the record

Custom HTML can include:
- Additional payment instructions
- Business hours for payment inquiries
- Reference numbers or codes
- Support contact information

### Best Practices for Custom Messages

```html
<h3>Wire Transfer Payment Instructions</h3>

<p>Please transfer the total amount to our bank account below.
Include your order number in the payment reference.</p>

<h4>Bank Details</h4>
<ul>
    <li>Bank: Example Bank</li>
    <li>Account: 1234567890</li>
    <li>IBAN: XX00XXXX0000000000</li>
</ul>

<p><strong>Note:</strong> Orders are processed after payment verification.
This may take 2-3 business days.</p>
```

## Scheduled Actions

### Ensuring Pending Message is Set

A recommended scheduled action ensures all wire transfer providers have proper pending messages:

```python
# Cron configuration
# Model: payment.provider
# Method: _transfer_ensure_pending_msg_is_set
# Schedule: Weekly or daily
```

This handles:
- Newly created providers that haven't fetched bank accounts
- Bank accounts added after provider creation
- Edge cases where pending_msg might be cleared

## Integration with Accounting

### Journal Entries

When a wire transfer payment is confirmed:

1. A payment record is created in Odoo
2. Journal entry is generated:
   - **Debit**: Bank account (from journal configuration)
   - **Credit**: Customer receivable account

### Reconciliation

The payment can be reconciled with the customer invoice/sale order to:
- Mark the invoice as paid
- Clear outstanding receivables
- Update customer account balance

## Multi-Company Support

### Company-Specific Providers

Each company can have its own wire transfer configuration:

1. Create separate payment providers for each company
2. Each provider pulls bank accounts from that company's journals
3. The correct bank details display based on the order's company

### Configuration

```python
# Provider searches for bank journals matching company
accounts = self.env['account.journal'].search([
    *self.env['account.journal']._check_company_domain(company_id),
    ('type', '=', 'bank'),
]).bank_account_id
```

## Feature Support

| Feature | Support Level | Notes |
|---------|--------------|-------|
| Express Checkout | No | Manual process required |
| Tokenization | No | Not applicable for wire transfer |
| Manual Capture | N/A | No pre-authorization |
| Refund | Yes | Manual refund via accounting |
| Partial Refund | Yes | Via credit note flow |
| Validation | Yes | Can validate customer details |

## Constants (`const.py`)

```python
DEFAULT_PAYMENT_METHOD_CODES = {
    'wire_transfer',
}
```

## Related

- [Modules/payment](Modules/payment.md) — Base payment engine and transaction processing
- [Modules/payment_demo](Modules/payment_demo.md) — Demo payment provider for testing
- [Modules/payment_flutterwave](Modules/payment_flutterwave.md) — African payment provider
- [Modules/payment_xendit](Modules/payment_xendit.md) — Southeast Asian payment provider
- [Modules/payment_nuvei](Modules/payment_nuvei.md) — Latin American payment provider
- [Modules/account_payment](Modules/account_payment.md) — Payment recording and reconciliation
