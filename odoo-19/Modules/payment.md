---
module: payment
description: Core payment processing framework - provider-agnostic abstraction, transaction lifecycle, tokenization, webhook handling, and post-payment workflows
tags: [odoo, odoo19, modules, payment, gateway, tokenization, webhook]
---

# Payment Module

> **Module:** `payment` | **Depends:** `onboarding`, `portal` | **Auto-installs:** `None`
> **Category:** Hidden (not visible in Apps menu by default) | **Version:** 2.0 | **License:** LGPL-3
> **Author:** Odoo S.A.

## Overview

The `payment` module is the core payment processing framework in Odoo 19. It provides a unified, provider-agnostic abstraction over payment gateways, handling the full transaction lifecycle, tokenization, webhook processing, and post-payment workflows. Provider-specific integrations (Stripe, PayPal, Adyen, etc.) are separate modules that extend this framework.

This module does **not** implement any specific payment provider -- it defines the architecture, models, and hooks that provider modules (`payment_stripe`, `payment_adyen`, `payment_paypal`, etc.) implement. This design allows Odoo to support any payment provider without modifying the core framework.

---

## L1: All Models with Fields

### 1. `payment.provider`

The central model representing a payment service provider. One provider record exists per company per payment module installed.

```python
class PaymentProvider(models.Model):
    _name = 'payment.provider'
    _description = 'Payment Provider'
    _order = 'module_state, state desc, sequence, name'
    _check_company_auto = True
    _check_company_domain = models.check_company_domain_parent_of
```

#### Configuration Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | Char | Yes | — | Provider display name; translatable |
| `sequence` | Integer | No | — | Display order in kanban view |
| `code` | Selection | Yes | `'none'` | Technical code; base selection is `('none', "No Provider Set")`; provider modules extend this |
| `state` | Selection | Yes | `'disabled'` | `disabled` / `enabled` / `test`; setting this auto-toggles `is_published` |
| `is_published` | Boolean | No | `False` | Controls website visibility; auto-set when state != `disabled` |
| `company_id` | Many2one | Yes | `env.company.id` | Company the provider belongs to |
| `main_currency_id` | Many2one | — | related to `company_id.currency_id` | Used to display monetary fields |
| `payment_method_ids` | Many2many | No | — | Payment methods supported by this provider |
| `allow_tokenization` | Boolean | No | `False` | Whether customers can save payment methods as tokens |
| `capture_manually` | Boolean | No | `False` | Two-step capture (authorize then capture); used for "ship first, charge later" |
| `allow_express_checkout` | Boolean | No | `False` | Support for Google Pay / Apple Pay express checkout |
| `redirect_form_view_id` | Many2one | No | — | QWeb template for redirect-based payments |
| `inline_form_view_id` | Many2one | No | — | QWeb template for inline/embedded payments |
| `token_inline_form_view_id` | Many2one | No | — | QWeb template for token-based inline payments |
| `express_checkout_form_view_id` | Many2one | No | — | QWeb template for express checkout |
| `available_country_ids` | Many2many | No | — | Restrict provider to specific countries |
| `available_currency_ids` | Many2many | No | All | Restrict provider to specific currencies; computed from `_get_supported_currencies()` |
| `maximum_amount` | Monetary | No | Unbounded | Maximum payment amount for which this provider is available |
| `pre_msg` | Html | No | — | Message shown before payment |
| `pending_msg` | Html | No | "Your payment is waiting for approval." | Shown when tx is pending |
| `auth_msg` | Html | No | "Your payment has been authorized." | Shown when tx is authorized |
| `done_msg` | Html | No | "Your payment has been processed." | Shown when tx is confirmed |
| `cancel_msg` | Html | No | "Your payment has been cancelled." | Shown when tx is cancelled |
| `image_128` | Image | No | — | Provider logo for kanban |
| `color` | Integer | No | Computed | Kanban card color; auto-computed from state |
| `module_id` | Many2one | No | — | Link to `ir.module.module` record |
| `module_state` | Selection | — | related to `module_id.state` | Module install state |
| `module_to_buy` | Boolean | — | related to `module_id.to_buy` | Whether provider requires paid module |

#### Feature Support Fields (Computed)

| Field | Type | Description |
|-------|------|-------------|
| `support_tokenization` | Boolean | Provider allows tokenization; overridden by provider modules |
| `support_manual_capture` | Selection | `'full_only'` / `'partial'` / `None` |
| `support_express_checkout` | Boolean | Provider supports express checkout |
| `support_refund` | Selection | `'full_only'` / `'partial'` / `'none'` (default) |

#### Key Business Methods

| Method | Description |
|--------|-------------|
| `_get_compatible_providers()` | Filters providers by company, state, country, currency, amount, tokenization, express checkout |
| `_is_tokenization_required()` | Override in provider modules to enforce tokenization |
| `_should_build_inline_form()` | Returns `True` by default; override for redirect-only providers |
| `_get_validation_amount()` | Override to define amount for token validation transactions (often $0) |
| `_setup_provider()` | Called by `_register_provider` from provider-specific modules |
| `_setup_payment_method()` | Creates `account.payment.method` records on provider install |
| `_remove_provider()` | Removes payment method on provider uninstall |
| `_get_supported_currencies()` | Returns all currencies by default; override to restrict |

### 2. `payment.transaction`

The model representing a single payment attempt. Every payment flow creates exactly one transaction record.

```python
class PaymentTransaction(models.Model):
    _name = 'payment.transaction'
    _description = 'Payment Transaction'
    _order = 'id desc'
    _rec_name = 'reference'
```

#### Core Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `provider_id` | Many2one | Yes | — | The `payment.provider` handling this transaction |
| `provider_code` | Char | — | related | Technical code of the provider |
| `company_id` | Many2one | — | related | Company (indexed, from provider) |
| `payment_method_id` | Many2one | Yes | — | The `payment.method` used |
| `payment_method_code` | Char | — | related | Technical code of the payment method |
| `primary_payment_method_id` | Many2one | — | computed | Top-level payment method (for card brands) |
| `reference` | Char | Yes | auto | Unique internal reference; enforced unique SQL constraint |
| `provider_reference` | Char | No | — | External reference from the payment gateway |
| `amount` | Monetary | Yes | — | Transaction amount |
| `currency_id` | Many2one | Yes | — | Currency of the amount |
| `token_id` | Many2one | No | — | Saved payment token used (if any) |
| `state` | Selection | Yes | `'draft'` | `draft` / `pending` / `authorized` / `done` / `cancel` / `error` |
| `state_message` | Text | No | — | Human-readable state reason |
| `last_state_change` | Datetime | No | now | When the state last changed |

#### Operation Types

The `operation` field classifies what the transaction is doing:

| Value | Meaning |
|-------|---------|
| `online_redirect` | Payment with redirect to external page (e.g., PayPal) |
| `online_direct` | Direct payment via inline form (e.g., Stripe Elements) |
| `online_token` | Payment using a saved token via inline form |
| `offline` | Payment by token created from account payment flow |
| `validation` | $0 authorization to validate and save a token |
| `refund` | Refund initiated from Odoo |

#### Traceability Fields

| Field | Type | Description |
|-------|------|-------------|
| `is_live` | Boolean | `True` if `provider_id.state == 'enabled'` (production) |
| `source_transaction_id` | Many2one | Parent transaction (for refunds, partial captures, voids) |
| `child_transaction_ids` | One2many | Child transactions (refunds, captures, voids) |
| `refunds_count` | Integer | Computed count of refund child transactions |
| `is_post_processed` | Boolean | Whether post-processing has completed |
| `tokenize` | Boolean | Whether to create a token after successful payment |
| `landing_route` | Char | URL to redirect user after payment |

#### Partner Snapshot Fields (Duplicated for Audit Trail)

These fields store partner data at transaction creation time to preserve historical accuracy even if the partner record changes:

| Field | Description |
|-------|-------------|
| `partner_name`, `partner_lang`, `partner_email` | Partner name, language, email |
| `partner_address`, `partner_zip`, `partner_city` | Partner address parts |
| `partner_state_id`, `partner_country_id` | Partner location |
| `partner_phone` | Partner phone |

#### State Machine Transitions

The `_update_state()` method manages transitions with a whitelist approach:

```
draft         → pending, authorized, done, cancel, error
pending       → authorized, done, cancel, error
authorized    → done (capture), cancel (void), error
done          → (terminal, but refund creates child transaction)
cancel        → (terminal)
error         → (terminal, can retry)
```

Each state transition logs a message to linked documents via `_log_received_message()`. The `match` statement (Python 3.10+) in `_get_received_message()` generates state-specific messages.

#### Key Business Methods

| Method | Description |
|--------|-------------|
| `_create_child_transaction()` | Spawns a refund/capture/void child transaction |
| `_compute_reference()` | Generates unique references with sequence numbers |
| `_get_processing_values()` | Returns dict for JS payment form; includes provider-specific rendering values |
| `_process()` | Main entry point called by provider-specific webhook handlers |
| `_validate_amount()` | Verifies gateway-returned amount/currency matches the transaction |
| `_tokenize()` | Creates `payment.token` record after successful payment |
| `_set_pending/authorized/done/cancel/error()` | State transition methods that log to chatter |
| `_capture()` / `_void()` / `_refund()` | Create child transactions and call provider API |
| `_send_capture_request()` / `_send_refund_request()` / `_send_void_request()` | Provider-implemented hooks (empty in base) |
| `_cron_post_process()` | Scheduled action for transactions not handled by client |
| `_post_process()` | Generic hook for module-specific post-processing (empty in base) |
| `_log_sent_message()` / `_log_received_message()` | Chatter logging |
| `_build_action_feedback_notification()` | Builds display_notification for capture/void/refund results |

### 3. `payment.token`

Stores saved payment method credentials (tokens) for repeat payments without re-entering card details.

```python
class PaymentToken(models.Model):
    _name = 'payment.token'
    _order = 'partner_id, id desc'
    _check_company_auto = True
    _rec_names_search = ['payment_details', 'partner_id', 'provider_id']
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `provider_id` | Many2one | Yes | Provider that issued this token |
| `provider_code` | Char | — | related |
| `company_id` | Many2one | — | related to provider; indexed |
| `payment_method_id` | Many2one | Yes | The payment method (card, bank transfer, etc.) |
| `payment_method_code` | Char | — | related |
| `payment_details` | Char | No | Masked details, e.g., "•••• 1234" |
| `partner_id` | Many2one | Yes | Partner who owns this token; indexed |
| `provider_ref` | Char | Yes | Provider's reference for this token |
| `transaction_ids` | One2many | — | Transactions using this token |
| `active` | Boolean | No | `True`; archiving a token doesn't delete it |

#### `_build_display_name()`

Formats the token name with masked details: `'•••• 1234'`. If `payment_details` is empty (token created before details were captured), shows `'Payment details saved on YYYY/MM/DD'`.

#### Token Creation

Tokens are created by provider-specific modules via `_get_specific_create_values()`. The base method returns an empty dict -- providers override to add `provider_ref` and `payment_details`.

#### Archiving Logic

Tokens are **archived** (not deleted) when:
- The provider state changes between `enabled`/`test` ↔ `disabled`
- The linked payment method is deactivated or detached from the provider
- Tokenization support is removed from the payment method

An `active=False` token cannot be used for new transactions (`_check_token_is_active` constraint). Tokens linked to `res.partner` records that are `is_public` raise a `ValidationError` on creation.

### 4. `payment.method`

Represents a payment instrument type (credit card, SEPA, etc.) and its characteristics. This model separates the *method* (e.g., "Card") from the *provider* (e.g., "Stripe"), allowing the same method to work across multiple providers.

```python
class PaymentMethod(models.Model):
    _name = 'payment.method'
    _order = 'active desc, sequence, name'
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | Char | Yes | Display name; translatable |
| `code` | Char | Yes | Technical identifier (e.g., `card`, `sepa_direct_debit`) |
| `sequence` | Integer | No | Display order |
| `primary_payment_method_id` | Many2one | No | For card *brands* (e.g., "Visa" brand's primary is "Card") |
| `brand_ids` | One2many | — | Reverse of primary; brands under this method |
| `is_primary` | Boolean | computed | `True` if no `primary_payment_method_id` |
| `provider_ids` | Many2many | No | Providers supporting this method |
| `active` | Boolean | No | `True` |
| `image` | Image | Yes | 64x64 logo for the payment form |
| `image_payment_form` | Image | — | 45x30 resized version for form display |
| `support_tokenization` | Boolean | No | Whether this method supports token storage |
| `support_express_checkout` | Boolean | No | Whether usable for express checkout |
| `support_manual_capture` | Selection | Yes | `none` / `full_only` / `partial` |
| `support_refund` | Selection | Yes | `none` / `full_only` / `partial` |
| `supported_country_ids` | Many2many | No | Countries where this method is available |
| `supported_currency_ids` | Many2many | No | Currencies this method supports |

#### `_get_compatible_payment_methods()`

Filters payment methods by provider support, partner country, currency, tokenization requirement, and express checkout. Returns only **primary** methods (not brands).

### 5. `res.partner` (extension)

```python
class ResPartner(models.Model):
    _inherit = 'res.partner'

    payment_token_ids = fields.One2many('payment.token', 'partner_id')
    payment_token_count = fields.Integer(compute='_compute_payment_token_count')
```

### 6. `res.company` (extension)

When a new company is created, `_create()` duplicates all installed providers from the root user's company to the new company via `copy()`.

### 7. `ir_http` (extension)

Handles webhook callback verification and routing. The `_handle_callback` method delegates to the provider's `_webhook_notify()` method.

---

## L2: Field Types, Defaults, Constraints

### Field Type Inventory

| Model | Field | Type | Special Characteristics |
|-------|-------|------|------------------------|
| `payment.provider` | `code` | Selection | Base has only `('none', ...)`; extended by provider modules |
| `payment.provider` | `state` | Selection | Triggers `is_published` toggle via `_onchange_state_switch_is_published` |
| `payment.provider` | `available_currency_ids` | Many2many | Computed and `store=True, readonly=False`; left empty for UX if all supported |
| `payment.provider` | `support_*` fields | Computed | All computed from `_compute_feature_support_fields()`; delegated to provider modules |
| `payment.transaction` | `reference` | Char | UNIQUE SQL constraint `_reference_uniq`; auto-generated via `_compute_reference()` |
| `payment.transaction` | `state` | Selection | `default='draft'`, `index=True` |
| `payment.transaction` | `operation` | Selection | `index=True`; drives messaging and child transaction logic |
| `payment.transaction` | `partner_*` fields | Various | Duplicated snapshot fields; stored for audit |
| `payment.transaction` | `is_live` | Boolean | Set at creation from `provider_id.state == 'enabled'` |
| `payment.transaction` | `source_transaction_id` | Many2one | `index='btree_not_null'` for efficient child lookups |
| `payment.token` | `payment_details` | Char | Masked display string; not the actual sensitive data |
| `payment.token` | `provider_ref` | Char | Provider-side token reference; stored but not logged |
| `payment.method` | `image` | Image | `max_width=64, max_height=64, required=True` |
| `payment.method` | `image_payment_form` | Image | `max_width=45, max_height=30`, `store=True`, `related='image'` |

### SQL Constraints

```python
# payment.transaction
_reference_uniq = models.Constraint(
    'unique(reference)',
    'Reference must be unique!',
)
```

### API Constraints

```python
# payment.transaction
@api.constrains('state')
def _check_state_authorized_supported(self):
    illegal = self.filtered(
        lambda tx: tx.state == 'authorized' and not tx.provider_id.support_manual_capture
    )
    if illegal:
        raise ValidationError(...)

@api.constrains('token_id')
def _check_token_is_active(self):
    if self.token_id and not self.token_id.active:
        raise ValidationError("Creating a transaction from an archived token is forbidden.")

# payment.provider
@api.constrains('capture_manually')
def _check_manual_capture_supported_by_payment_methods(self):
    # Raises if capture_manually=True but some active payment methods have support_manual_capture='none'

# payment.method
@api.constrains('active', 'support_manual_capture')
def _check_manual_capture_supported_by_providers(self):
    # Raises if an active payment method has 'none' capture support but is linked to a capture_manually=True provider
```

### `required_if_provider` Pattern

Provider-specific required fields use a special attribute pattern. Fields defined in provider modules with `required_if_provider='stripe'` are only enforced when `code='stripe'` and `state in ('enabled', 'test')`:

```python
# In provider-specific module, e.g., payment_stripe:
stripe_api_key = fields.Char(
    string="Stripe API Key",
    required_if_provider='stripe',  # Custom field parameter recognized by _check_required_if_provider()
)
```

---

## L3: Cross-Model, Override Patterns, Workflow Triggers

### Cross-Model Relationships

```
payment.provider
  ├── 1:N → payment.method           (via payment_method_ids)
  ├── 1:N → payment.token            (via provider_id)
  └── 1:N → payment.transaction     (via provider_id)

payment.transaction
  ├── N:1 → payment.provider         (provider_id)
  ├── N:1 → payment.token           (token_id)
  ├── N:1 → payment.method         (payment_method_id)
  ├── N:1 → payment.transaction    (source_transaction_id, for refunds/captures)
  ├── 1:N → payment.transaction    (child_transaction_ids)
  ├── N:N → account.move           (via account_invoice_transaction_rel, added by account_payment)

payment.token
  ├── N:1 → payment.provider
  ├── N:1 → payment.method
  └── N:1 → res.partner            (partner_id)

payment.method
  └── N:N → payment.provider        (via provider_ids)
      ├── 1:N → payment.method      (brand_ids, for card brands)
      └── N:1 → payment.method    (primary_payment_method_id)

res.partner
  └── 1:N → payment.token          (payment_token_ids)
```

### Module Dependency Chain

```
payment (base framework)
  ├── base, onboarding, portal (depends)
  ├── payment_stripe, payment_adyen, payment_paypal (extend)
  │
  └── account_payment (extends payment.transaction, account.move, account.payment)
        ├── account, payment (depends)
        └── auto_installs: account
```

### Payment Flow Patterns (Operation → State → Action)

| Operation | Initiation | State Flow | Child Transaction |
|-----------|-----------|-----------|-----------------|
| `online_redirect` | User redirected to provider | draft → pending → done | None |
| `online_direct` | Inline form submitted | draft → done | None |
| `online_token` | Token selected in form | draft → done | None |
| `offline` | Payment registered from account | draft → done | None (created by account.payment) |
| `validation` | User saves card | draft → authorized → done | None |
| `refund` | User clicks refund | draft → done (child of source) | Yes, negative amount |

### Post-Processing Cron (`_cron_post_process`)

A scheduled action (`payment.cron_post_process_payment_tx`) processes transactions that the client never finished:
1. Runs every 15 minutes (configurable)
2. Queries transactions where `is_post_processed = False` and `last_state_change >= now - 4 days`
3. Calls `_post_process()` on each
4. Commits after each successful transaction

The cron is **toggled automatically**: enabled when any provider is non-disabled, disabled when all providers are disabled (`_toggle_post_processing_cron()`).

### Portal Controller Architecture

```
PaymentPortal (payment/controllers/portal.py)
  ├── /payment/pay            GET  → renders payment form with available providers/methods/tokens
  ├── /payment/transaction    JSON → creates tx, returns processing values
  ├── /payment/confirmation   GET  → displays confirmation page
  ├── /my/payment_method     GET  → manage saved tokens
  └── /payment/archive_token  JSON → archive a token

PaymentPostProcessing (payment/controllers/post_processing.py)
  ├── /payment/status         GET  → display status page (called after redirect)
  └── /payment/status/poll    JSON → poll state + trigger _post_process()
```

### Override Patterns

**Provider module example** (`payment_stripe`):

```python
class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    def _setup_provider(self, code, **kwargs):
        super()._setup_provider(code, **kwargs)
        if code == 'stripe':
            self._setup_payment_method(code)

    @api.model
    def _setup_payment_method(self, code):
        if code == 'stripe' and not self.env['payment.method'].search([('code', '=', 'stripe')]):
            self.env['payment.method'].sudo().create({
                'name': 'Stripe',
                'code': 'stripe',
                ...
            })

    def _get_default_payment_method_codes(self):
        # Return which payment.method codes are default for this provider
        return {'stripe'}

    def _get_feature_support_fields(self):
        # Override computed feature support fields
        self.update({
            'support_express_checkout': True,
            'support_manual_capture': 'partial',
            'support_refund': 'partial',
            'support_tokenization': True,
        })
```

### Hook Methods (Override Points)

| Hook Method | Called By | Purpose |
|-------------|-----------|---------|
| `_setup_provider(code)` | Provider module install | One-time setup when provider module is installed |
| `_setup_payment_method(code)` | `_setup_provider()` | Create the `payment.method` record |
| `_remove_provider(code)` | Provider module uninstall | Remove payment method; blocked if payments exist |
| `_get_supported_currencies()` | `_compute_available_currency_ids()` | Restrict currencies per provider |
| `_get_validation_amount()` | `_create_transaction()` | Define amount for validation ($0 or small hold) |
| `_is_tokenization_required()` | `_get_compatible_providers()` | Force tokenization for specific flows |
| `_should_build_inline_form()` | Transaction processing | Return `False` for redirect-only providers |
| `_get_specific_create_values(provider_code, values)` | `payment.token.create()` | Provider-specific token fields |
| `_get_specific_processing_values()` | `_get_processing_values()` | Add provider-specific data to processing dict |
| `_get_specific_rendering_values()` | `_get_processing_values()` | Build redirect form HTML |
| `_get_specific_rendering_values()` | `_get_redirect_form_view()` | Build inline form rendering |
| `_get_sent_message()` / `_get_received_message()` | `_log_sent_message()` / `_log_received_message()` | Custom log messages |
| `_get_invoices_to_notify()` | `_log_message_on_linked_documents()` | Account_payment hook |
| `_post_process()` | `_cron_post_process()`, poll endpoint | Module-specific post-processing |
| `_handle_callback()` | `ir_http._handle_callback()` | Route webhook to provider |

### `_create_transaction()` Static Method

The `PaymentPortal._create_transaction()` method (non-ORM) is the central factory for creating transaction records from portal flows:

```python
@staticmethod
def _create_transaction(
    provider_id, payment_method_id, token_id, amount, currency_id,
    partner_id, flow, tokenization_requested, landing_route,
    reference_prefix=None, is_validation=False, custom_create_values=None, **kwargs
):
```

It handles:
1. Token vs direct payment distinction (`flow == 'token'`)
2. Token ownership verification (partner must match)
3. Provider-determined amount/currency for validation transactions
4. Immediate `_charge_with_token()` for token payments
5. Token creation flag (`tokenize`) determination

---

## L4: Performance, Version Changes, Security

### Performance Considerations

#### Query Optimization in `_compute_invoices_count` (account_payment)

The `account_payment` extension uses a raw SQL query instead of ORM for counting invoice links, avoiding N+1:

```python
def _compute_invoices_count(self):
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

This is a deliberate ORM bypass because the many2many table has no ORM Many2one pointing back, so a standard `_read_group` would generate multiple queries.

#### Payment Token Search Optimization

`_get_available_tokens()` in `payment.token` uses a simple domain search. For partners with many tokens, consider adding a composite index on `(partner_id, provider_id, active)` since this is the dominant filter pattern.

#### `_compute_reference()` with Search Count

```python
if self.sudo().search_count([('reference', '=', prefix)], limit=1):
    same_prefix_references = self.sudo().search(
        [('reference', '=like', f'{prefix}{separator}%')]
    ).with_context(prefetch_fields=False).mapped('reference')
```

The `search_count` + `search` pattern is used to avoid regex in SQL while still guaranteeing uniqueness. The double-search (count then fetch) is accepted because most prefixes don't collide, making the fast count path dominant.

#### Avoid Prefetching Partner Fields in `_create_transaction`

The `_create_transaction()` static method runs in an HTTP request context with sudo access. It deliberately bypasses access rights checks (`sudo()`) for performance and because these are internal API calls from the payment portal.

#### `_cron_post_process()` Retry Logic

The cron commits after each transaction (not after all), ensuring partial success:
```python
for tx in txs_to_post_process:
    try:
        tx._post_process()
        self.env.cr.commit()
    except psycopg2.OperationalError:
        self.env.cr.rollback()  # Rollback and try next
    except Exception:
        self.env.cr.rollback()
        _logger.exception(...)
```

### Version Changes: Odoo 17 → 18 → 19

#### Odoo 17 → 18 Breaking Changes

1. **`payment.method` model split**: Odoo 17 had a combined `payment.method` / `payment.acquirer` model. Odoo 18 split these into `payment.provider` (formerly `payment.acquirer`) and `payment.method` (new separate model). Migration required custom provider modules to be rewritten.

2. **Brand vs Method hierarchy**: The new `payment.method` model uses `primary_payment_method_id` for card brands (Visa, Mastercard) under a "Card" parent method. This replaced the older `payment.icon` model.

3. **`operation` field added**: The `operation` selection field was introduced to explicitly classify transaction types, replacing implicit logic based on `state` and token presence.

4. **Child transactions**: Refunds and partial captures now create explicit `payment.transaction` child records linked via `source_transaction_id`, replacing the older `_reconcile_payment` method.

5. **`tokenize` boolean**: Replaced the older pattern of conditionally creating tokens. Now explicitly flagged at transaction creation time.

#### Odoo 18 → 19 Breaking Changes

1. **`required_if_provider` field attribute**: Introduced as a standardized way to mark provider-specific required fields. Provider modules must add this attribute instead of overriding `_check_required_if_provider`.

2. **`capture_manually` on provider vs method**: The manual capture flag moved to the provider level (`payment.provider.capture_manually`). Previously this was handled differently. Provider-specific payment method codes must still respect the provider-level flag.

3. **`available_currency_ids` computed with `store=True`**: Currency availability is now a stored computed field, allowing efficient filtering without recalculation. Providers that restrict currencies must implement `_get_supported_currencies()`.

4. **`payment.method` brand support refined**: The `brand_ids` one2many inverse was stabilized. Provider modules should use the standard brand hierarchy when registering card brands.

5. **`payment_transaction` table performance**: The `is_post_processed` field and improved index strategy (`index='btree_not_null'` on `source_transaction_id`) reduce cron processing time on large transaction tables.

6. **`available_country_ids` and `available_currency_ids` left empty by default**: Empty = unrestricted (UX improvement over previous "all selected" behavior).

7. **`module_state` in `_order`**: Providers are now ordered by module install state first, keeping un-installed modules at the bottom.

### Security Analysis

#### Access Control

| Model | Public Read | Authenticated Read | Write | Delete |
|-------|------------|-------------------|--------|--------|
| `payment.provider` | No (published only for non-internal) | Yes (internal users) | Limited | Blocked for xmlid-linked |
| `payment.transaction` | No | Limited by ir.rule | Limited | Blocked |
| `payment.token` | No | Partner-specific via ir.rule | Partner/Owner | Partner/Owner |
| `payment.method` | Yes (for public portal) | Yes | Limited | Blocked for `payment_method_unknown` |

#### Token Security

1. **No public partner tokens**: `_check_partner_is_never_public()` raises `ValidationError` if `partner_id.is_public`. This prevents tokens being assigned to the `public` demo user.

2. **Token ownership verification** in `_create_transaction()`:
   ```python
   if partner_sudo.commercial_partner_id != token_sudo.partner_id.commercial_partner_id:
       raise AccessError("You do not have access to this payment token.")
   ```
   Even if a user knows a token ID, they cannot use it for a different partner.

3. **Archived tokens blocked**: `_check_token_is_active()` constraint prevents creating transactions from `active=False` tokens.

4. **Token archiving cascade**: When a provider is disabled, all linked tokens are automatically archived via `_archive_linked_tokens()`. Similarly when a payment method is deactivated.

5. **No `sudo()` without purpose**: Token operations in the portal run in `sudo()` only to bypass access rights on provider fields for rendering purposes. The actual token operations (`_handle_archiving()`, `_get_available_tokens()`) respect access rights.

#### CSRF / Request Validation

1. **`_validate_transaction_kwargs()` whitelist**: All kwargs from the payment form must pass through a whitelist check:
   ```python
   whitelist = {
       'provider_id', 'payment_method_id', 'token_id', 'amount',
       'flow', 'tokenization_requested', 'landing_route', 'is_validation', 'csrf_token',
       *additional_allowed_keys
   }
   ```
   Rejected keys raise `BadRequest`. This prevents injecting arbitrary fields into transaction create values.

2. **Access token on every payment**: `payment_utils.generate_access_token()` and `check_access_token()` verify that `partner_id`, `amount`, and `currency_id` match the original request on every transaction creation. This prevents tampering with payment parameters after the form loads.

3. **`csrf_token` in whitelist**: CSRF is validated by the Odoo HTTP framework by default for non-API routes. For JSON-RPC routes (`/payment/transaction`), it is explicitly whitelisted.

#### Amount Validation

`_validate_amount()` in `payment.transaction` compares the gateway-returned amount and currency against the stored transaction values. This catches tampering where a malicious actor intercepts and modifies the webhook payload.

For refunds, the amount is negated before comparison since providers send positive amounts:
```python
if self.operation == 'refund':
    amount = -amount
```

#### Provider Disable Safety

When a provider is disabled:
1. All linked tokens are archived (`_archive_linked_tokens()`)
2. Unsupported payment methods are deactivated
3. The cron is disabled if no providers are active

This prevents orphaned active tokens pointing to a disabled provider.

#### Logging Sensitivity

The module uses `SENSITIVE_KEYS` (from `payment/const.py`) -- an extensible set of field names that should not be logged. Provider modules extend this set with their own sensitive fields (e.g., card numbers, API keys). The `_logger` in `payment.transaction` and `payment.provider` is initialized with these keys:

```python
SENSITIVE_KEYS = set()  # Extended by provider modules
_logger = get_payment_logger(__name__, sensitive_keys=SENSITIVE_KEYS)
```

#### Multi-Company Security

- `_check_company_domain_parent_of` on `payment.provider` ensures providers can only be accessed in companies that are ancestors of the provider's company (prevents cross-company access).
- Company change on a provider with existing transactions is blocked by `_onchange_company_block_if_existing_transactions()`.

### Key Security Hooks for Provider Modules

```python
# 1. Use SENSITIVE_KEYS in your provider module:
from odoo.addons.payment.const import SENSITIVE_KEYS
SENSITIVE_KEYS.update({'stripe_api_key', 'stripe_webhook_secret'})

# 2. Implement _get_reset_values() for safe credential clearing:
def _get_reset_values(self):
    return {'stripe_api_key': False, 'stripe_webhook_secret': False}

# 3. Use required_if_provider for credential fields:
stripe_api_key = fields.Char(
    string="Stripe API Key",
    required_if_provider='stripe',  # Only required when state is enabled/test
)
```

---

## Wizard Models

### `payment.capture.wizard` (payment/wizards/payment_capture_wizard.py)

Allows partial capture of authorized transactions. Created when any linked transaction's provider supports `support_manual_capture='partial'`.

| Field | Type | Description |
|-------|------|-------------|
| `transaction_ids` | Many2many | Source transactions to capture |
| `authorized_amount` | Monetary | Sum of all source tx amounts |
| `captured_amount` | Monetary | Already captured (direct + partial child txs) |
| `voided_amount` | Monetary | Already voided (child txs in cancel state) |
| `available_amount` | Monetary | `authorized - captured - voided` |
| `amount_to_capture` | Monetary | Amount to capture; default = available |
| `is_amount_to_capture_valid` | Boolean | `0 < amount <= available` |
| `void_remaining_amount` | Boolean | Also void any uncaptured remainder |
| `support_partial_capture` | Boolean | All source txs support partial |
| `has_draft_children` | Boolean | Draft child txs exist |
| `has_remaining_amount` | Boolean | `amount_to_capture < available` |

The wizard processes multiple authorized transactions in sequence, capturing up to the specified `amount_to_capture`, then optionally voiding the remainder.

### `payment.link.wizard` (payment/wizards/payment_link_wizard.py)

Generates payment links for sharing via email. Works for any document that implements `_get_default_payment_link_values()`.

| Field | Type | Description |
|-------|------|-------------|
| `res_model` | Char | Document model |
| `res_id` | Integer | Document ID |
| `amount` | Monetary | Amount to pay |
| `amount_max` | Monetary | Maximum allowed (for partial payments) |
| `currency_id` | Many2one | Currency |
| `partner_id` | Many2one | Partner |
| `link` | Char | Computed payment URL |

The `_prepare_access_token()` generates a token based on `(partner_id, amount, currency_id)` to prevent link tampering.
