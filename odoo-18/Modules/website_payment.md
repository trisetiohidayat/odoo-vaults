# website_payment - Payment Method Management on Website

## Overview

The `website_payment` module extends the payment framework to support website-based payment processing. It provides payment forms, donation handling, and integration with the website e-commerce platform.

## Module Information

- **Technical Name**: `website_payment`
- **Location**: `addons/website_payment/`
- **Depends**: `payment`, `account_payment`, `website`
- **License**: LGPL-3

---

## Models

### payment.provider Extension

**File**: `models/payment_provider.py`

Extends `payment.provider` to add website-specific functionality:

```python
class PaymentProvider(models.Model):
    _inherit = "payment.provider"

    website_id = fields.Many2one(
        "website",
        check_company=True,
        ondelete="restrict",
    )
```

**Key Fields**:
- `website_id` - Many2one to website; restricts provider visibility to specific websites

**Key Methods**:

```python
# Get compatible providers filtered by website
def _get_compatible_providers(self, *args, website_id=None, report=None, **kwargs):
    """ Override of `payment` to only return providers matching website-specific criteria.
    The website must either not be set or be the same as the one provided in the kwargs.
    """

# Get base URL with priority to request URL root (handles multi-website cases)
def get_base_url(self):
    if request and request.httprequest.url_root:
        return iri_to_uri(request.httprequest.url_root)
    return super().get_base_url()

# Copy provider with website reset during Stripe Connect onboarding
def copy(self, default=None):
    if self._context.get('stripe_connect_onboarding'):
        res.website_id = False
    return res
```

---

### payment.transaction Extension

**File**: `models/payment_transaction.py`

Extends `payment.transaction` for donation tracking:

```python
class PaymentTransaction(models.Model):
    _inherit = "payment.transaction"

    is_donation = fields.Boolean(string="Is donation")
```

**Key Methods**:

```python
# Post-process transaction and send donation email
def _post_process(self):
    super()._post_process()
    for donation_tx in self.filtered(lambda tx: tx.state == 'done' and tx.is_donation):
        donation_tx._send_donation_email()
        # Log donation details to payment record

# Send donation confirmation email
def _send_donation_email(self, is_internal_notification=False, comment=None, recipient_email=None):
    """Send email for donation with QWeb template rendering"""
```

---

### account.payment Extension

**File**: `models/account_payment.py`

```python
class AccountPayment(models.Model):
    _inherit = 'account.payment'

    is_donation = fields.Boolean(
        string="Is Donation",
        related="payment_transaction_id.is_donation"
    )
```

Links account payment records to donation transactions.

---

## Controllers

### Payment Portal

**File**: `controllers/payment.py`

```python
class PaymentPortal(account_payment.PaymentPortal):
    @route()
    def payment_pay(self, *args, **kwargs):
        """Override to make provider filtering website-aware."""
        return super().payment_pay(*args, website_id=request.website.id, **kwargs)

    @route()
    def payment_method(self, **kwargs):
        """Override to make provider filtering website-aware."""
        return super().payment_method(website_id=request.website.id, **kwargs)
```

### Portal Controller

**File**: `controllers/portal.py`

Extends `PaymentPortal` for donation functionality:

```python
class PaymentPortal(payment_portal.PaymentPortal):

    # Donation payment page
    @http.route('/donation/pay', type='http', methods=['GET', 'POST'],
                auth='public', website=True, sitemap=False)
    def donation_pay(self, **kwargs):
        """Render donation form with customizable amounts and options"""
        kwargs['is_donation'] = True
        kwargs['currency_id'] = ...
        kwargs['amount'] = 25.0  # Default donation amount
        return self.payment_pay(**kwargs)

    # Create donation transaction
    @http.route('/donation/transaction/<minimum_amount>', type='json',
                auth='public', website=True, sitemap=False)
    def donation_transaction(self, amount, currency_id, partner_id,
                             access_token, minimum_amount=0, **kwargs):
        """Validate and create donation transaction"""
        # Validates minimum amount
        # Handles public user vs logged-in user
        # Creates transaction with is_donation flag
        # Sends notification email
        return tx_sudo._get_processing_values()

    # Extra form context for donation
    def _get_extra_payment_form_values(self, donation_options=None, ...):
        """Add donation-specific rendering context"""

    # Template selection
    def _get_payment_page_template_xmlid(self, **kwargs):
        if kwargs.get('is_donation'):
            return 'website_payment.donation_pay'
        return super()._get_payment_page_template_xmlid(**kwargs)

    # Hide tokenization for public donation users
    @staticmethod
    def _compute_show_tokenize_input_mapping(providers_sudo, **kwargs):
        """Hide 'Save my payment details' for anonymous donation users"""
```

---

## Key Features

### 1. Website-Aware Payment Providers

Providers can be restricted to specific websites:
```python
provider = env['payment.provider'].create({
    'name': 'Acquirer',
    'provider': 'stripe',
    'website_id': website.id,  # Only shows on this website
})
```

### 2. Donation Processing

Donations have special handling:
- Customizable donation amounts
- Donor details collection (name, email, country)
- Automatic email confirmation
- Internal notification to configured recipient
- Comments/reason tracking

### 3. Multi-Website Support

Payment providers respect website boundaries through `_get_compatible_providers()` override.

---

## Template QWeb IDs

- `website_payment.donation_pay` - Donation payment form
- `website_payment.donation_mail_body` - Donation confirmation email body
- `website_payment.mail_template_donation` - Email template

---

## Security Considerations

1. **Access Token Validation**: Donations use `generate_access_token()` with partner, amount, and currency
2. **CSRF Protection**: JSON endpoints use standard Odoo CSRF handling
3. **Partner Details Validation**: Required fields (name, email, country) validated server-side
4. **Amount Validation**: Minimum donation amount enforced

---

## Related Modules

- `payment` - Core payment framework
- `account_payment` - Account payment integration
- `website_sale` - E-commerce website integration
- `payment_stripe` / `payment_paypal` - Provider-specific implementations

---

## Database Schema

### New Fields Added

**Table: `payment_provider`**:
| Column | Type | Description |
|--------|------|-------------|
| `website_id` | integer | FK to website (nullable) |

**Table: `payment_transaction`**:
| Column | Type | Description |
|--------|------|-------------|
| `is_donation` | boolean | Flag for donation transactions |

---

## Workflow: Donation Payment

1. User visits `/donation/pay` with optional parameters
2. Form displays customizable donation amounts
3. User selects amount and payment method
4. AJAX call to `/donation/transaction/<min>`:
   - Validates minimum amount
   - Creates transaction with `is_donation=True`
   - For public users: collects and stores donor details
   - Sends notification email to recipient
5. User completes payment on provider's page
6. `_post_process()` hook sends confirmation email
7. Payment record updated with donation details

---

## Extension Points

1. **Custom Donation Amounts**: Override `donation_pay()` to customize options
2. **Additional Donor Fields**: Extend form and `_send_donation_email()`
3. **Custom Payment Providers**: Use `website_id` field for per-site configuration
4. **Donation Campaigns**: Link to `utm.campaign` for tracking
