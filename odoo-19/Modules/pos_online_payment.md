---
uuid: c3d4e5f6-a7b8-9c0d-1e2f-3a4b5c6d7e8f
tags:
  - odoo
  - odoo19
  - modules
  - point-of-sale
  - pos
  - payment
  - online-payment
  - payment-link
---

# Point of Sale Online Payment (`pos_online_payment`)

## Overview

| Property | Value |
|----------|-------|
| **Name** | Point of Sale online payment |
| **Technical** | `pos_online_payment` |
| **Category** | Sales/Point of Sale |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |
| **Depends** | `point_of_sale`, `account_payment` |
| **Auto-install** | True |
| **Installable** | True |

## Description

The POS Online Payment module bridges the gap between physical Point of Sale transactions and online payment processing. It enables cashiers to send payment links to customers via email or SMS, allowing customers to complete payments using their preferred online payment methods without being physically present at the POS terminal.

This module is particularly valuable for:

- **Remote Customers**: Customers who cannot pay immediately at the terminal
- **Split Payments**: Large orders where customers want to pay from different sources
- **Delivery Orders**: When delivery is required and payment happens online
- **Queue Reduction**: Moving payment processing off the POS terminal
- **Card-not-present Payments**: Handling payments where physical cards aren't available

The module leverages Odoo's existing payment infrastructure to process online payments while maintaining the POS order lifecycle. When a customer receives a payment link and completes payment, the POS order automatically updates to reflect the paid status.

## Key Features

### Payment Link Generation

Cashiers can generate payment links directly from the POS interface:

- Select the order or amount to be paid
- Choose the online payment provider
- Generate and send payment link
- Customer pays via the link (email/SMS)

### Multi-Provider Support

Works with any configured online payment provider:

- Credit/Debit cards (via Stripe, Adyen, etc.)
- Regional payment methods
- Alternative payment methods (APMs)
- Bank transfers

### Real-time Synchronization

Payment status syncs automatically:

- When payment is completed, POS order updates immediately
- No manual intervention required
- Payment validation happens automatically

### Customer Display Integration

The POS customer display shows payment status:

- Displays when payment link is sent
- Shows payment pending status
- Updates when payment is received
- Allows cashier to track payment progress

## Technical Architecture

### Module Structure

```
pos_online_payment/
├── __init__.py
├── __manifest__.py
├── controllers/
│   ├── __init__.py
│   └── main.py           # Payment link handling
└── models/
    ├── __init__.py
    └── pos_payment_method.py  # POS payment method extension
```

Plus extensive JavaScript components in `static/src/`:

```
static/
├── src/
│   ├── app/
│   │   ├── components/
│   │   │   └── popups/
│   │   │       └── online_payment_popup/
│   │   │           └── online_payment_popup.xml
│   │   └── pos_online_payment.js
│   └── overrides/
│       ├── pos_overrides/
│       └── customer_display_overrides/
└── tests/
    └── tours/
```

### Data Flow

```
POS Order Created
    │
    ▼
Cashier Initiates Online Payment
    │
    ├── Select payment method
    ├── Enter amount (partial or full)
    │
    ▼
Payment Link Generated
    │
    ├── Payment transaction created (state: draft)
    │
    ▼
Send to Customer
    │
    ├── Email notification
    ├── SMS notification
    │
    ▼
Customer Opens Link
    │
    ├── Online payment form displayed
    ├── Customer enters payment details
    │
    ▼
Payment Processed
    │
    ├── Payment provider processes
    ├── Webhook confirms payment
    │
    ▼
POS Order Updated
    │
    ├── Transaction state: done
    ├── Order payment status updated
    └── Order continues (invoicing, delivery)
```

## Model: `pos.payment.method` (Extended)

### Field Extension

```python
class PosPaymentMethod(models.Model):
    _inherit = "pos.payment.method"

    is_online_payment = fields.Boolean(
        string="Online Payment",
        help="Use this payment method for online payments (payments made on a web page with online payment providers)",
        default=False
    )
    online_payment_provider_ids = fields.Many2many(
        'payment.provider',
        string="Allowed Providers",
        domain="[('is_published', '=', True), ('state', 'in', ['enabled', 'test'])]"
    )
    has_an_online_payment_provider = fields.Boolean(
        compute='_compute_has_an_online_payment_provider',
        readonly=True
    )
    type = fields.Selection(
        selection_add=[('online', 'Online')]
    )
```

### Key Fields Explained

**`is_online_payment`**

Boolean flag to identify payment methods configured for online payments:

- When `True`: Method is used for generating payment links
- When `False`: Method is a traditional POS payment method
- Default: `False`

**`online_payment_provider_ids`**

Many2many relation to allowed payment providers:

- Empty = All published providers allowed
- Non-empty = Only these providers allowed
- Filtered to only published providers in `enabled` or `test` state

**`has_an_online_payment_provider`**

Computed field indicating if a valid provider exists:

```python
@api.depends('is_online_payment', 'online_payment_provider_ids')
def _compute_has_an_online_payment_provider(self):
    for pm in self:
        if pm.is_online_payment:
            pm.has_an_online_payment_provider = bool(pm._get_online_payment_providers())
        else:
            pm.has_an_online_payment_provider = False
```

**`type`**

Extended with new `online` selection option:

```python
type = fields.Selection(selection_add=[('online', 'Online')])
```

### Key Methods

**`_get_online_payment_providers()`**

Returns providers valid for the POS configuration:

```python
def _get_online_payment_providers(self, pos_config_id=False, error_if_invalid=True):
    self.ensure_one()
    providers_sudo = self.sudo().online_payment_provider_ids
    if not providers_sudo:  # Empty = all published providers
        providers_sudo = self.sudo().env['payment.provider'].search([
            ('is_published', '=', True),
            ('state', 'in', ['enabled', 'test'])
        ])
    
    if not pos_config_id:
        return providers_sudo
    
    # Filter by currency compatibility
    config_currency = self.sudo().env['pos.config'].browse(pos_config_id).currency_id
    valid_providers = providers_sudo.filtered(
        lambda p: not p.journal_id.currency_id or
                  p.journal_id.currency_id == config_currency
    )
    if error_if_invalid and len(providers_sudo) != len(valid_providers):
        raise ValidationError(_("All payment providers configured for an online payment method must use the same currency as the Sales Journal..."))
    return valid_providers
```

**`_compute_type()`**

Sets type to `online` for online payment methods:

```python
@api.depends('is_online_payment')
def _compute_type(self):
    opm = self.filtered('is_online_payment')
    if opm:
        opm.type = 'online'
    super(PosPaymentMethod, self - opm)._compute_type()
```

**`_check_pos_config_online_payment()`**

Constraint ensuring one online payment method per POS config:

```python
@api.constrains('config_ids', 'is_online_payment')
def _check_pos_config_online_payment(self):
    for pm in self.filtered('is_online_payment'):
        for config in pm.config_ids:
            other_online_pms = config.payment_method_ids.filtered(
                lambda other_pm: other_pm.is_online_payment and other_pm.id != pm.id
            )
            if other_online_pms:
                raise ValidationError(_("The %s already has one online payment.", config.name))
```

**`_force_online_payment_values()`**

Ensures online payment methods have correct field values:

```python
@staticmethod
def _force_online_payment_values(vals, if_present=False):
    if 'type' in vals:
        vals['type'] = 'online'
    
    disabled_fields = (
        'split_transactions', 'receivable_account_id', 'outstanding_account_id',
        'journal_id', 'is_cash_count', 'use_payment_terminal', 'qr_code_method'
    )
    for name in disabled_fields:
        vals[name] = False
    vals['payment_method_type'] = 'none'
```

**`_get_or_create_online_payment_method()`**

Gets or creates an online payment method for a company/POS:

```python
@api.model
def _get_or_create_online_payment_method(self, company_id, pos_config_id):
    # Search for existing method in same config
    payment_method_id = self.env['pos.payment.method'].search([
        ('is_online_payment', '=', True),
        ('company_id', '=', company_id),
        ('config_ids', 'in', pos_config_id)
    ], limit=1).exists()
    
    # If not found, search for any in same company
    if not payment_method_id:
        payment_method_id = self.env['pos.payment.method'].search([
            ('is_online_payment', '=', True),
            ('company_id', '=', company_id)
        ], limit=1).exists()
    
    # If still not found, create new
    if not payment_method_id:
        payment_method_id = self.env['pos.payment.method'].create({
            'name': _('Online Payment'),
            'is_online_payment': True,
            'company_id': company_id,
        })
    return payment_method_id
```

### Write Protection

Online payment methods have restricted write access:

```python
def _is_write_forbidden(self, fields):
    return super(PosPaymentMethod, self)._is_write_forbidden(
        fields - {'online_payment_provider_ids'}
    )
```

Only `online_payment_provider_ids` can be modified after creation.

## Payment Flow: Step by Step

### Step 1: POS Configuration

1. Navigate to **Point of Sale > Configuration > Payment Methods**
2. Create a new payment method
3. Enable "Online Payment" checkbox
4. Optionally select specific providers
5. Add the method to POS configuration

### Step 2: Order Creation at POS

1. Cashier creates order at POS terminal
2. Customer requests to pay online
3. Cashier selects online payment method
4. Cashier enters payment amount (full or partial)

### Step 3: Payment Link Generation

1. POS calls server to generate payment
2. Server creates `payment.transaction` in draft state
3. Payment link is generated
4. Cashier chooses delivery method (email/SMS)

### Step 4: Customer Payment

1. Customer receives link via email/SMS
2. Customer opens link on phone/computer
3. Customer selects payment method
4. Customer enters payment details
5. Payment is processed

### Step 5: Synchronization

1. Payment provider sends webhook to Odoo
2. Transaction state changes to `done`
3. POS receives real-time update
4. Order status shows "Paid"
5. POS continues with order fulfillment

## Controller Endpoints

### Payment Link Processing

The module includes controller endpoints for handling online payment returns:

**Key responsibilities**:
- Process payment confirmation from providers
- Update transaction states
- Handle redirect URLs

### Webhook Integration

Payment providers send webhook notifications:

- Transaction state updates
- Payment confirmation
- Error notifications

## User Interface

### POS Interface

#### Online Payment Popup

A dedicated popup in the POS interface allows cashiers to:

- Enter payment amount
- Select payment provider
- Preview payment link
- Choose delivery method (email/SMS)
- Send payment link

#### Customer Display

The customer-facing display shows:

- "Payment link sent" status
- Amount to be paid
- Payment pending indicator
- Confirmation when payment received

### Backend Interface

#### Payment Method Configuration

Form view includes:

- Online Payment toggle
- Allowed Providers selection
- Provider currency validation
- Linked POS configurations

#### Transaction Tracking

Payment transactions are visible in:

- **Payment > Providers**: Transaction list
- **Accounting > Payments**: Related payments
- **POS Orders**: Linked payment status

## Configuration Examples

### Example 1: Basic Online Payment

Configure a simple online payment method:

1. Go to **Point of Sale > Configuration > Payment Methods**
2. Create new:
   - Name: "Online Payment"
   - Online Payment: Checked
   - Allowed Providers: Leave empty (all published)
3. Add to POS configuration
4. Save

### Example 2: Specific Provider

Configure to use only Stripe:

1. Go to **Point of Sale > Configuration > Payment Methods**
2. Create new:
   - Name: "Card Online"
   - Online Payment: Checked
   - Allowed Providers: Select "Stripe"
3. Add to POS configuration
4. Save

### Example 3: Regional Payment Methods

Configure for specific regional methods:

1. Create multiple payment methods:
   - "Indonesian E-Wallets" - OVO, DANA
   - "Philippine E-Wallets" - GCash, Maya
2. Add Xendit provider with regional methods
3. Link methods to appropriate POS configs

## Payment Methods Compatibility

### Compatible Providers

The module works with any payment provider configured in Odoo:

- **Stripe**: Cards, Apple Pay, Google Pay
- **Adyen**: Cards, Regional methods
- **Xendit**: OVO, DANA, GCash, QRIS
- **Flutterwave**: M-Pesa, Cards
- **Nuvei**: Boleto, SPEI, PSE
- **PayPal**: PayPal payments

### Currency Considerations

Online payment providers must match POS currency:

- POS configured with IDR currency
- Payment provider must support IDR
- If mismatch, validation error occurs

## Real-time Updates

### WebSocket Communication

The POS uses Odoo's real-time infrastructure:

1. Payment transaction created
2. POS subscribes to transaction updates
3. Payment provider processes payment
4. Webhook received by Odoo
5. Transaction state updated
6. WebSocket pushes update to POS
7. POS UI refreshes payment status

### Offline Considerations

If POS loses connection:

- Payment link remains valid
- Customer can still complete payment
- When connection restored, status updates
- Order can be completed manually if needed

## Data Files

### Views

| File | Purpose |
|------|---------|
| `res_config_settings_views.xml` | Settings form |
| `payment_transaction_views.xml` | Transaction views |
| `pos_payment_views.xml` | POS payment views |
| `pos_payment_method_views.xml` | Payment method config |
| `payment_portal_templates.xml` | Portal templates |
| `account_payment_views.xml` | Account payment views |

### Assets

| Asset | Purpose |
|-------|---------|
| `pos_online_payment.assets_prod` | Main POS app assets |
| `pos_online_payment.customer_display_assets` | Customer display popup |
| `pos_online_payment.customer_display_assets_test` | Test tour |

## Integration with Other Modules

### With `payment` Module

- Creates payment transactions
- Processes payments via providers
- Receives webhook notifications
- Updates transaction states

### With `account_payment` Module

- Records payments in accounting
- Creates journal entries
- Handles payment reconciliation

### With `point_of_sale` Module

- Syncs with POS orders
- Updates order payment status
- Triggers order completion

### With `pos_online_payment_self_order` Module

Extends self-ordering capabilities:

- Customers can pay online in self-checkout
- Kiosk-style ordering and payment

## Security Considerations

### Payment Link Security

- Links include secure tokens
- Links are time-limited (configurable)
- Links tied to specific transactions

### Provider Validation

- Only published providers allowed
- State must be `enabled` or `test`
- Currency compatibility validated

### Write Restrictions

- Most fields are read-only after creation
- Only provider selection can be modified
- Prevents accidental configuration changes

## Troubleshooting

### Payment Link Not Sent

**Check**:
1. Email/SMS configuration in Odoo
2. Customer contact information
3. Provider availability

### Payment Not Reflecting in POS

**Check**:
1. Webhook configuration in payment provider
2. Network connectivity to Odoo
3. Transaction in Odoo database

### Provider Currency Mismatch

**Error**: "All payment providers configured for an online payment method must use the same currency..."

**Solution**: Ensure provider journal uses same currency as POS config currency.

### Multiple Online Payment Methods

**Error**: "The X already has one online payment."

**Solution**: Each POS config can only have one online payment method.

## Related

- [Modules/point_of_sale](Modules/point_of_sale.md) — Base POS module
- [Modules/payment](Modules/payment.md) — Payment engine and providers
- [Modules/payment_stripe](Modules/payment_stripe.md) — Stripe payment provider
- [Modules/payment_xendit](Modules/payment_xendit.md) — Southeast Asian payment provider
- [Modules/pos_online_payment_self_order](Modules/pos_online_payment_self_order.md) — Self-order online payment
