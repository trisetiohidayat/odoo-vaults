---
tags: [odoo, odoo17, module, payment, research_depth]
research_depth: deep
---

# Payment Module — Deep Research (Odoo 17)

**Source:** `addons/payment/models/`

Files: `payment_provider.py` (758 lines), `payment_transaction.py` (1161 lines), `payment_token.py` (197 lines), `payment_method.py` (272 lines), `ir_http.py` (13 lines)

## Module Architecture

```
payment.provider
    ├── code (selection: 'none' + provider-specific codes)
    ├── state: disabled | enabled | test
    ├── payment_method_ids (Many2many → payment.method)
    ├── allow_tokenization, capture_manually, allow_express_checkout
    ├── available_country_ids, available_currency_ids, maximum_amount
    └── _get_compatible_providers() — main discovery method

payment.transaction
    ├── provider_id (→ payment.provider)
    ├── payment_method_id (→ payment.method)
    ├── token_id (→ payment.token, optional)
    ├── state: draft | pending | authorized | done | cancel | error
    ├── operation: online_redirect | online_direct | online_token | validation | offline | refund
    ├── reference (unique), provider_reference, amount, currency_id
    ├── source_transaction_id, child_transaction_ids (for refunds/captures)
    └── callback_model_id, callback_res_id, callback_method, callback_hash (security)

payment.token
    ├── provider_id, payment_method_id, partner_id
    ├── provider_ref (provider's token reference — NOT the same as tx.provider_reference)
    └── payment_details (e.g., "•••• 1234")

payment.method
    ├── code, name, sequence
    ├── primary_payment_method_id (brand → primary parent)
    ├── brand_ids (inverse of above)
    ├── provider_ids (Many2many → payment.provider)
    └── support_tokenization, support_express_checkout, support_refund
      supported_country_ids, supported_currency_ids
```

---

## payment.provider — Payment Gateway Model

File: `addons/payment/models/payment_provider.py` (758 lines total)

### All Fields (complete, line-by-line)

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Provider display name, required, translateable |
| `sequence` | Integer | Display order among providers |
| `code` | Selection | Technical code. Default `'none'`. Provider modules append values like `'stripe'`, `'paypal'`, `'sepa'` |
| `state` | Selection | `disabled` (default), `enabled`, `test`. Controls availability |
| `is_published` | Boolean | Visibility on website. Auto-set via `_onchange_state_switch_is_published` when state → `enabled` |
| `company_id` | Many2one res.company | Required, indexed. One provider per company |
| `main_currency_id` | Many2one res.currency | Related to `company_id.currency_id`, used for `maximum_amount` display |
| `payment_method_ids` | Many2many payment.method | Payment methods this provider supports |
| `allow_tokenization` | Boolean | Allow customers to save payment methods as tokens |
| `capture_manually` | Boolean | Delay capture until delivery (2-step payment). Sets `support_manual_capture` |
| `allow_express_checkout` | Boolean | Enable express methods (Google Pay, Apple Pay) |
| `redirect_form_view_id` | Many2one ir.ui.view | QWeb template for redirect-based payments |
| `inline_form_view_id` | Many2one ir.ui.view | QWeb template for inline direct payments |
| `token_inline_form_view_id` | Many2one ir.ui.view | QWeb template for token-based payments |
| `express_checkout_form_view_id` | Many2one ir.ui.view | Template for express checkout |
| `available_country_ids` | Many2many res.country | Restrict provider to specific countries. Blank = all countries |
| `available_currency_ids` | Many2many res.currency | Computed from `_get_supported_currencies()`. Blank = all currencies |
| `maximum_amount` | Monetary | Max transaction amount. Blank = no limit |
| `pre_msg` | Html | Help message displayed before payment |
| `pending_msg` | Html | Message shown when tx is pending (default: "Your payment has been successfully processed but is waiting for approval.") |
| `auth_msg` | Html | Message shown when tx is authorized (default: "Your payment has been authorized.") |
| `done_msg` | Html | Message shown when tx is done (default: "Your payment has been successfully processed.") |
| `cancel_msg` | Html | Message shown when tx is cancelled (default: "Your payment has been cancelled.") |
| `support_tokenization` | Boolean (computed) | Default `False`. Provider-specific via `_compute_feature_support_fields` |
| `support_manual_capture` | Selection (computed) | Values: `full_only`, `partial`, or `None`. Default `None` |
| `support_express_checkout` | Boolean (computed) | Default `False` |
| `support_refund` | Selection (computed) | Values: `full_only`, `partial`, or `None`. Default `None` |
| `image_128` | Image | Provider logo (128x128 max) |
| `color` | Integer (computed+stored) | Kanban card color: 4=blue (module not installed), 3=yellow (disabled), 2=orange (test), 7=green (enabled) |
| `module_id` | Many2one ir.module.module | The provider's addon module |
| `module_state` | Selection (related, stored) | From `module_id.state`. Stored for SQL sorting |
| `module_to_buy` | Boolean (related) | From `module_id.to_buy` |
| `show_credentials_page` | Boolean (computed) | Whether to show the credentials notebook page |
| `show_allow_tokenization` | Boolean (computed) | Whether to show `allow_tokenization` field |
| `show_allow_express_checkout` | Boolean (computed) | Whether to show `allow_express_checkout` field |
| `show_pre_msg` | Boolean (computed) | Whether to show `pre_msg` field |
| `show_pending_msg` | Boolean (computed) | Whether to show `pending_msg` field |
| `show_auth_msg` | Boolean (computed) | Whether to show `auth_msg` field |
| `show_done_msg` | Boolean (computed) | Whether to show `done_msg` field |
| `show_cancel_msg` | Boolean (computed) | Whether to show `cancel_msg` field |
| `require_currency` | Boolean (computed) | Whether `available_currency_ids` is required |

### Provider State Transitions and Side Effects

```
disabled → enabled  (publishes: is_published=True, archives tokens)
disabled → test     (is_published=False, archives tokens)
enabled  → disabled (archives all linked tokens, deactivates unsupported PMs, pauses cron)
enabled  → test     (archives tokens due to state change)
test     → enabled  (archives tokens due to state change)
```

On state change to non-disabled: `_activate_default_pms()` activates default PMs (via `_get_default_payment_method_codes()`).
On state change to disabled: `_archive_linked_tokens()` archives all tokens; `_deactivate_unsupported_payment_methods()` deactivates PMs with only disabled providers.
On any create/write that changes state: `_toggle_post_processing_cron()` activates/deactivates the post-processing cron.

### Provider Discovery: `_get_compatible_providers()` (Line 498-577)

```python
def _get_compatible_providers(self, company_id, partner_id, amount,
    currency_id=None, force_tokenization=False, is_express_checkout=False,
    is_validation=False, **kwargs):
```

Full domain built step-by-step:
1. **Company domain** via `_check_company_domain(company_id)`
2. **State in** `['enabled', 'test']`
3. **Published** if user is not internal: `is_published=True`
4. **Partner country** in `available_country_ids` OR `available_country_ids` is empty
5. **Amount <= maximum_amount** (converted to company currency via `_convert()`)
6. **Currency** in `available_currency_ids` OR `available_currency_ids` is empty
7. **Tokenization** if `force_tokenization` or `_is_tokenization_required(**kwargs)`
8. **Express checkout** if `is_express_checkout`

### `_check_required_if_provider()` (Line 374-399)

Scans all fields with `required_if_provider='<code>'` attribute. For every enabled/test provider, if a field for its matching code is empty, raises `ValidationError`. Provider-specific views must mirror this condition in XML:

```python
# E.g., Stripe module defines:
api.constrains('api_key')
def _check_required(self):
    pass  # implemented in write()
# Field definition:
'api_key': fields.Char(required_if_provider='stripe')
```

### `_toggle_post_processing_cron()` (Line 401-416)

```python
post_processing_cron = self.env.ref('payment.cron_post_process_payment_tx')
any_active_provider = self.sudo().search_count([('state', '!=', 'disabled')], limit=1)
post_processing_cron.active = any_active_provider
```

Called on create/write of providers. Cron is only active when at least one non-disabled provider exists, saving resources when no providers are configured.

### Provider Lifecycle Methods (Line 681-757)

```python
_setup_provider(provider_code)      # Called after module install
_remove_provider(provider_code)      # Called on module uninstall
_get_removal_values()                # Returns: code='none', state='disabled', is_published=False,
                                      # all view IDs = None
_get_provider_name()                 # Returns translated description from code Selection
_get_code()                          # Returns self.code
_get_default_payment_method_codes()  # Override: return list of PM codes to auto-activate
```

### `_valid_field_parameter()` (Line 21-22)

```python
def _valid_field_parameter(self, field, name):
    return name == 'required_if_provider' or super()._valid_field_parameter(field, name)
```

This allows provider-specific fields to use `required_if_provider='<code>'` on their field definitions. See `_check_required_if_provider()` usage above.

---

## payment.transaction — Transaction Model

File: `addons/payment/models/payment_transaction.py` (1161 lines total)

### All Fields (complete, line-by-line)

| Field | Type | Description |
|-------|------|-------------|
| `provider_id` | Many2one payment.provider | Required, readonly |
| `provider_code` | Selection (related) | Provider code for quick lookups |
| `company_id` | Many2one res.company | Related to provider, indexed for ir_rule performance |
| `payment_method_id` | Many2one payment.method | Required, readonly |
| `payment_method_code` | Char (related) | Payment method code |
| `reference` | Char | Unique internal reference, auto-generated via `_compute_reference()` |
| `provider_reference` | Char | External reference from payment processor (e.g., Stripe charge ID) |
| `amount` | Monetary | Transaction amount |
| `currency_id` | Many2one res.currency | Transaction currency |
| `token_id` | Many2one payment.token | If using saved payment method. Domain: same provider as tx |
| `state` | Selection | `draft`, `pending`, `authorized`, `done`, `cancel`, `error`. Default `draft`. Indexed. |
| `state_message` | Text | Human-readable state explanation |
| `last_state_change` | Datetime | Auto-set to `fields.Datetime.now()` on state transitions |
| `operation` | Selection | `online_redirect`, `online_direct`, `online_token`, `validation`, `offline`, `refund`. Indexed. |
| `source_transaction_id` | Many2one | Parent transaction for refunds/captures |
| `child_transaction_ids` | One2many | Child transactions (refunds, partial captures) |
| `refunds_count` | Integer (computed) | Count of `operation='refund'` child transactions via `_read_group` |
| `is_post_processed` | Boolean | Whether post-processing has been completed |
| `tokenize` | Boolean | Whether to create a token after successful payment |
| `landing_route` | Char | URL path to redirect user after payment |
| `callback_model_id` | Many2one ir.model | Model for callback (groups: base.group_system only) |
| `callback_res_id` | Integer | Record ID for callback |
| `callback_method` | Char | Method name to call on the record |
| `callback_hash` | Char | HMAC hash for security |
| `callback_is_done` | Boolean | Whether callback has been executed (groups: base.group_system) |
| `partner_id` | Many2one res.partner | Customer, readonly, required |
| `partner_name/email/phone/address/zip/city/state_id/country_id/lang` | Various | Duplicated partner fields to preserve history if partner is edited later |

**SQL Constraint:** `reference_uniq` — reference must be globally unique.

### State Machine

```
draft ──→ pending   (allowed from: draft)
draft ──→ authorized (allowed from: draft, pending)
draft ──→ done      (allowed from: draft, pending, authorized, error)
draft ──→ cancel    (allowed from: draft, pending, authorized)
draft ──→ error     (allowed from: draft, pending, authorized)
```

Key transitions:
- `pending → authorized`: common flow after provider redirect returns
- `authorized → done`: capture confirmed
- `authorized → cancel`: void confirmed
- `error → done`: retry succeeded

Each `_set_*` method calls `_update_state()` which classifies into three groups: to process (write state), already processed (INFO log, idempotent), wrong state (WARNING log, invalid transition attempted).

### Reference Generation: `_compute_reference()` (Line 320-399)

Multi-sequence prefix system:
1. Normalize prefix: remove diacritics via NFKD/ASCII encoding
2. If no prefix: call `_compute_reference_prefix()` (override point for sale, account modules)
3. If still no prefix: use `payment_utils.singularize_reference_prefix()` → `"tx-{datetime}"`
4. Check if reference already exists; if yes, find max sequence number and append `-N`
5. Regex ensures exact match: `^{prefix}{separator}(\d+)$` (prevents collisions like `example` vs `example-1` vs `example-ref`)

Override point: `_compute_reference_prefix(provider_code, separator, **values)` — receives transaction values (invoice_ids, sale_order_id, etc.) so modules can derive meaningful prefixes.

### Processing Values: `_get_processing_values()` (Line 436-490)

Returns dict with: `provider_id`, `provider_code`, `reference`, `amount`, `currency_id`, `partner_id`, plus provider-specific values from `_get_specific_processing_values()`. For `online_redirect` and `validation` operations, also renders redirect form HTML:

```python
redirect_form_view = self.provider_id._get_redirect_form_view(is_validation=...)
rendering_values = self._get_specific_rendering_values(processing_values)
redirect_form_html = self.env['ir.qweb']._render(redirect_form_view.id, rendering_values)
processing_values.update(redirect_form_html=redirect_form_html)
```

Secret keys hidden from logs via `_get_specific_secret_keys()`.

### Callback System

Three-layer security on callbacks:
1. `callback_model_id`, `callback_res_id`, `callback_method` must be set
2. `callback_hash` must match HMAC of `model|res_id|method`
3. `callback_is_done` prevents double-execution (can reschedule if conditions unmet)

```python
valid_callback_hash = self._generate_callback_hash(model_sudo.id, res_id, method)
if not consteq(ustr(valid_callback_hash), callback_hash):
    continue  # Ignore tampered callbacks

record = self.env[model_sudo.model].browse(res_id).exists()
if not record:
    continue  # Ignore invalidated records

success = getattr(record, method)(tx)  # Execute the callback
tx_sudo.callback_is_done = success or success is None
```

### Cron Post-Processing: `_cron_finalize_post_processing()` (Line 979-1006)

```python
# Only processes transactions within 4 days of last_state_change
retry_limit_date = datetime.now() - relativedelta(days=4)
txs_to_post_process = self.search([
    ('state', '=', 'done'),
    ('is_post_processed', '=', False),
    ('last_state_change', '>=', retry_limit_date),
])
for tx in txs_to_post_process:
    tx._finalize_post_processing()
    self.env.cr.commit()  # Commit per tx to avoid blocking
```

4-day window accommodates slow providers (PayPal can take days to confirm).

### `_finalize_post_processing()` (Line 1008-1014)

```python
self.filtered(lambda tx: tx.operation != 'validation')._reconcile_after_done()
self.is_post_processed = True
```

Validation transactions (tokenization attempts) skip reconciliation — no actual payment occurred.

### Partial Capture / Refund Child Transactions

For partial captures: `P-{reference}`, same `operation` as parent, amount = partial capture amount. When all child captures sum to parent amount, `_update_source_transaction_state()` marks parent as done.

For refunds: `R-{reference}`, operation=`refund`, amount negated. Refunds can be partial — multiple child refund transactions.

---

## payment.token — Saved Payment Methods

File: `addons/payment/models/payment_token.py` (197 lines)

### All Fields

| Field | Type | Description |
|-------|------|-------------|
| `provider_id` | Many2one payment.provider | Required |
| `provider_code` | Selection (related) | Provider code synonym |
| `company_id` | Many2one res.company | Related to provider, indexed |
| `payment_method_id` | Many2one payment.method | Required, readonly |
| `payment_method_code` | Char (related) | Payment method code |
| `payment_details` | Char | Clear text details, e.g., `"•••• 1234"` |
| `partner_id` | Many2one res.partner | Required |
| `provider_ref` | Char | Provider's token reference (NOT same as `payment.transaction.provider_reference`) |
| `transaction_ids` | One2many payment.transaction | Inverse |
| `active` | Boolean | Default True. **Irreversible: cannot unarchive once deactivated.** |

### Display Name: `_build_display_name()` (Line 138-175)

Format: `"•••• 1234"` with left-padding to max 34 characters (largest IBAN length).

Algorithm:
- `padding_length = 34 - len(payment_details)`
- If `padding_length >= 2`: pad with `min(padding_length - 1, 4)` bullets + space
- If `padding_length == 1`: show details without padding
- If `padding_length < 0`: trim details from left to fit max_length
- If no `payment_details`: fallback to `"Payment details saved on YYYY/MM/DD"`

### Tokenization Cannot Target Public Partner

```python
@api.constrains('partner_id')
def _check_partner_is_never_public(self):
    for token in self:
        if token.partner_id.is_public:
            raise ValidationError(_("No token can be assigned to the public partner."))
```

### Archival Is Irreversible

```python
if 'active' in values:
    if values['active']:  # Trying to unarchive
        if any(not token.active for token in self):
            raise UserError(_("A token cannot be unarchived once it has been archived."))
    else:
        self.filtered('active').sudo()._handle_archiving()
```

### `_get_available_tokens()` (Line 113-136)

- Regular payment: search by `provider_id` + `partner_id`
- Validation (tokenization): search partner AND commercial_partner, regardless of provider availability (needed because validation creates new tokens, so all related tokens must be shown to allow the partner to manage them)

---

## payment.method — Payment Instruments

File: `addons/payment/models/payment_method.py` (272 lines)

### All Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Display name, required |
| `code` | Char | Technical code, required |
| `sequence` | Integer | Sort order, default 1 |
| `primary_payment_method_id` | Many2one payment.method | Parent for brands. E.g., `"Card"` is primary of `"VISA"` |
| `brand_ids` | One2many payment.method | Inverse of primary_payment_method_id |
| `is_primary` | Boolean (computed+search) | True if no `primary_payment_method_id`. Search enabled. |
| `provider_ids` | Many2many payment.provider | Which providers support this method |
| `active` | Boolean | Default True |
| `image` | Image | Base image, 64x64 px max, required |
| `image_payment_form` | Image | Resized to 45x30 px, stored |
| `support_tokenization` | Boolean | Allow saving as token |
| `support_express_checkout` | Boolean | Usable in express checkout |
| `support_refund` | Selection | `full_only` or `partial` |
| `supported_country_ids` | Many2many res.country | Country restrictions |
| `supported_currency_ids` | Many2many res.currency | Currency restrictions |

### Payment Method Hierarchy

Primary methods (e.g., "Card") can have brand children (e.g., "VISA", "Mastercard"). Only primary methods are returned in compatibility searches (`is_primary=True`). Brands are considered children of their primary.

### Onchange: Disabling/Detaching Has Consequences (Line 103-134)

Three onchange handlers warn when archiving, detaching from provider, or removing tokenization support — all will archive related tokens:

```python
# Detecting: disabling, removing provider, blocking tokenization
disabling = self._origin.active and not self.active
detached_providers = self._origin.provider_ids - self.provider_ids
blocking_tokenization = self._origin.support_tokenization and not self.support_tokenization
if any:
    related_tokens = self.env['payment.token'].search([...])
    if related_tokens:
        return {'warning': {...}}
```

### `_get_compatible_payment_methods()` (Line 199-255)

```python
domain = [
    ('provider_ids', 'in', provider_ids),
    ('is_primary', '=', True),  # Never return brand children
]
# + partner country filter (if list not empty)
# + currency filter (if currency provided and list not empty)
# + support_tokenization if force_tokenization
# + support_express_checkout if is_express_checkout
```

---

## Payment Flow — Complete Lifecycle

### Flow 1: Online Redirect (Stripe, PayPal)

```
Customer checkout
  └─→ sale.order / website_sale → calls _get_compatible_providers()
  └─→ User selects provider + payment method
  └─→ payment.transaction.create():
        - reference auto-generated via _compute_reference()
        - partner fields duplicated (name, email, address, etc.)
        - state = draft, operation = online_redirect
        - callback_hash generated for security
  └─→ _get_processing_values() renders redirect form HTML
  └─→ Customer redirected to provider with provider-specific signature
  └─→ Provider processes, sends notification to Odoo controller
  └─→ _handle_notification_data(provider_code, notification_data):
        - _get_tx_from_notification_data() → find tx by reference
        - _process_notification_data() → provider parses webhook
        - _execute_callback() → call tx.callback_method if configured
  └─→ State transitions: pending → authorized → done
  └─→ _finalize_post_processing():
        - _reconcile_after_done() (provider-specific: sale order → paid)
        - is_post_processed = True
  └─→ Cron: _cron_finalize_post_processing() cleans up not-yet-processed txs
```

### Flow 2: Tokenization (Recurring Payments)

```
First payment: operation='validation' OR normal payment with tokenize=True
  └─→ Transaction confirmed → done
  └─→ _finalize_post_processing() → provider-specific _reconcile_after_done()
  └─→ If tokenize=True: payment.token.create({
        provider_id=tx.provider_id,
        payment_method_id=tx.payment_method_id,
        partner_id=tx.partner_id,
        provider_ref=...  (from _process_notification_data)
      })
  └─→ Token display_name auto-generated via _build_display_name()

Subsequent payments: operation='online_token' or 'offline'
  └─→ _send_payment_request() → provider charges token directly (no redirect)
```

### Flow 3: Manual Capture (Two-Step)

```
1. Payment authorized: tx.state = authorized (provider.capture_manually=True)
2. Merchant reviews order, ships goods
3. action_capture() → _send_capture_request(amount_to_capture)
   - Full capture: direct capture
   - Partial capture: creates child transaction (P-{reference}, same operation)
4. Provider captures → state = done
5. _update_source_transaction_state():
   - Sums child captures with state='done' and same operation
   - When total == original amount → parent goes done
```

### Flow 4: Refunds

```
1. Merchant clicks "Refund" on confirmed transaction
2. action_refund(amount_to_refund=None) → _send_refund_request()
3. Creates child transaction: R-{reference}, amount=-amount, operation=refund
4. Provider processes refund → child state = done
5. refunds_count updated on original transaction via _read_group
```

### Provider-Specific Override Points

| Method | Purpose |
|--------|---------|
| `_get_supported_currencies()` | Restrict currencies (default: all) |
| `_compute_feature_support_fields()` | Set support_tokenization/capture/refund/express |
| `_compute_view_configuration_fields()` | Hide/show form elements |
| `_get_specific_create_values()` | Add provider-specific token fields |
| `_get_specific_processing_values()` | Add provider-specific processing data |
| `_get_specific_rendering_values()` | Add form rendering values |
| `_get_specific_secret_keys()` | Keys to hide in logs |
| `_get_tx_from_notification_data()` | Parse webhook to find transaction |
| `_process_notification_data()` | Parse webhook, update state + provider_reference |
| `_send_payment_request()` | Charge token (online_token/offline) |
| `_send_capture_request()` | Capture authorized payment |
| `_send_void_request()` | Void authorized payment |
| `_reconcile_after_done()` | Post-payment book-keeping (e.g., update sale order) |

---

## ir_http — Session-Level Translation

File: `addons/payment/models/ir_http.py` (13 lines)

```python
class IrHttp(models.AbstractModel):
    _inherit = 'ir.http'

    @classmethod
    def _get_translation_frontend_modules_name(cls):
        mods = super()._get_translation_frontend_modules_name()
        return mods + ['payment']
```

Adds `payment` module to the list of frontend modules whose strings are exported for translation. Ensures all payment-related strings are available for website translation in all installed languages.

---

## Key Discoveries

1. **Dual-record privacy design**: `hr.employee` stores private data (SSN, bank accounts, etc.) with `groups="hr.group_hr_user"` field restrictions. `hr.employee.public` is a read-only SQL view for non-HR users. `payment.transaction` similarly uses `base.group_system` for callback fields.

2. **Provider as plug-in architecture**: `payment.provider` with `code='none'` is the base state. Provider addons (payment_stripe, payment_paypal, etc.) inherit and implement override points. The `code` field is the primary discriminator. Field-level `required_if_provider` attribute enables per-provider required fields.

3. **State machine is fully idempotent**: `_update_state()` silently skips already-processed transactions (INFO log) and logs illegal transitions (WARNING log). Safe to call multiple times from any source (webhook, cron, manual button).

4. **Callback security is three-layer**: sudo check for record existence, HMAC hash verification using `hmac_tool()`, and `callback_is_done` flag prevents double-execution. Valid hash is regenerated and compared via `consteq()` (timing-safe comparison).

5. **Token provider_ref vs Transaction provider_reference**: These are **different values**. `payment.token.provider_ref` stores the provider's token ID (for subsequent charges). `payment.transaction.provider_reference` stores the provider's transaction/charge ID (for reconciliation).

6. **4-day retry window**: `_cron_finalize_post_processing` only processes transactions within 4 days of `last_state_change`. Older transactions are abandoned by the cron (but can be processed manually). This window accommodates PayPal which can take days to confirm.

7. **Employee has resource.mixin**: Employees have working hours via `resource_calendar_id`, timezone support (`tz` field), and `_get_expected_attendances()` for working time calculations. `_get_calendar_periods()` allows different calendars over time.

8. **Manager auto-propagation on department change**: `hr.department.write()` calls `_update_employee_manager()` which updates `parent_id` of all employees whose current manager is the old department manager. This ensures org chart stays consistent.

9. **`global` field is a Python keyword workaround**: In `ir_rule.py`, `global_ = fields.Boolean(...)` is assigned via `setattr(IrRule, 'global', global_)` because `global` is a reserved keyword in Python. The same technique is used for other ORM-reserved names.

10. **Currency conversion for maximum_amount**: `_get_compatible_providers()` converts the transaction amount to the company currency via `_convert()` before comparing against `maximum_amount`. This ensures multi-currency compatibility.

## See Also

- [[Modules/account_payment]] — Payment-related account flow
- [[Modules/sale]] — sale.order payment integration
- [[Modules/website_sale]] — Website payment form
- [[Tools/ORM Operations]] — search/browse/create/write patterns