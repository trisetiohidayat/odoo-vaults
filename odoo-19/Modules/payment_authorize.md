# Payment Authorize

## Overview

- **Name:** Payment Provider: Authorize.Net
- **Category:** Accounting/Payment Providers
- **Version:** 2.0
- **Sequence:** 350
- **Depends:** `payment`
- **Author:** Odoo S.A.
- **License:** LGPL-3

## L1 — How Authorize.Net Payment Works in Odoo

`payment_authorize` implements **Authorize.Net** as a full-stack payment provider in Odoo. It handles the complete payment lifecycle: tokenization, authorization, capture, refund, and void — all through Authorize.Net's XML API.

**Key characteristics of Authorize.Net:**

| Characteristic | Detail |
|----------------|--------|
| **Payment type** | Card present (Terminal) and card not present (online) |
| **Authorization model** | Two-step: authorize first, then capture |
| **Tokenization** | Creates customer profiles in Authorize.Net to store card data |
| **Currency** | **One currency per merchant account** — this is a hard constraint enforced by Authorize.Net |
| **Capture** | Manual capture required (`full_only` — no partial capture) |
| **Refund** | Full refund only (`full_only`) |
| **API type** | XML API (not REST) via `AuthorizeAPI` class |

---

## L2 — Field Types, Defaults, Constraints

### Models Extended (4 models)

#### 1. `payment.provider` — via `_inherit = 'payment.provider'`

**New `code` option:**

```python
code = fields.Selection(
    selection_add=[('authorize', 'Authorize.Net')],
    ondelete={'authorize': 'set default'}
)
```

This registers Authorize.Net as a payment provider alongside Odoo's other providers (Stripe, PayPal, etc.).

**New fields on `payment.provider`:**

| Field | Type | Required | Groups | Purpose |
|-------|------|----------|--------|---------|
| `authorize_login` | `Char` | Yes (if provider='authorize') | — | Authorize.Net API Login ID |
| `authorize_transaction_key` | `Char` | Yes (if provider='authorize') | `base.group_system` | Authorize.Net API Transaction Key |
| `authorize_signature_key` | `Char` | Yes (if provider='authorize') | `base.group_system` | Authorize.Net API Signature Key |
| `authorize_client_key` | `Char` | No | — | Public client key for Accept.js inline form |

**`authorize_login`** — Identifies the merchant account. Used in every API request as `merchantAuthentication.name`.

**`authorize_transaction_key`** — Secret key for API requests. Stored with maximum protection (`base.group_system` = only admin can see/write).

**`authorize_signature_key`** — Used for signature verification of webhook/redirect responses from Authorize.Net.

**`authorize_client_key`** — Public key used by Accept.js (Authorize.Net's inline payment form JS) to tokenize card data client-side without passing raw card numbers to Odoo.

**Feature support fields (computed):**

```python
def _compute_feature_support_fields(self):
    super()._compute_feature_support_fields()
    self.filtered(lambda p: p.code == 'authorize').update({
        'support_manual_capture': 'full_only',   # Can only capture full amount
        'support_refund': 'full_only',           # Can only refund full amount
        'support_tokenization': True,             # Customer profiles supported
    })
```

**Constraints:**

```python
@api.constrains('available_currency_ids', 'state')
def _limit_available_currency_ids(self):
    for provider in self.filtered(lambda p: p.code == 'authorize'):
        if len(provider.available_currency_ids) > 1 and provider.state != 'disabled':
            raise ValidationError(
                _("Only one currency can be selected by Authorize.Net account.")
            )
```

| Constraint | Why |
|-----------|-----|
| Only one currency allowed | Authorize.Net policy: one merchant account = one currency |

---

#### 2. `payment.token` — via `_inherit = 'payment.token'`

**New field:**

| Field | Type | Purpose |
|-------|------|---------|
| `authorize_profile` | `Char` | Authorize.Net Customer Profile ID (unique per partner in Authorize.Net) |

This stores the Authorize.Net `customerProfileId` linked to an Odoo `payment.token`. When a token is used for future payments, Authorize.Net charges the stored profile rather than requiring the card to be re-entered.

---

#### 3. `payment.transaction` — via `_inherit = 'payment.transaction'`

No new fields. The model overrides a comprehensive set of methods to handle Authorize.Net's specific transaction lifecycle.

| Method | Purpose |
|--------|---------|
| `_get_specific_processing_values()` | Returns an access token for Accept.js inline form |
| `_authorize_create_transaction_request()` | Creates an authorize or auth+capture transaction request |
| `_send_payment_request()` | Sends authorize or auth+capture request using a stored token |
| `_send_capture_request()` | Captures a previously authorized (not yet captured) payment |
| `_send_refund_request()` | Refunds or voids a captured payment |
| `_send_void_request()` | Voids an authorized (not yet captured) payment |
| `_extract_amount_data()` | Extracts amount/currency from Authorize.Net transaction details |
| `_apply_updates()` | Parses Authorize.Net response codes and updates transaction state |
| `_extract_token_values()` | Creates Authorize.Net customer profile and payment profile from a transaction |

---

#### 4. `AuthorizeAPI` — plain Python class (not an Odoo model)

The `AuthorizeAPI` class in `authorize_request.py` is a **plain Python class** (not inheriting from `models.Model`) that封装 all Authorize.Net XML API calls.

| Method | Authorize.Net API Call | Purpose |
|--------|----------------------|---------|
| `test_authenticate()` | `authenticateTestRequest` | Verify API credentials |
| `merchant_details()` | `getMerchantDetailsRequest` | Fetch merchant info, public key, supported currencies |
| `create_customer_profile()` | `createCustomerProfileFromTransactionRequest` | Create customer profile + payment profile from a transaction |
| `delete_customer_profile()` | `deleteCustomerProfileRequest` | Delete a customer profile |
| `authorize()` | `createTransactionRequest` (authOnlyTransaction) | Authorize without capture |
| `auth_and_capture()` | `createTransactionRequest` (authCaptureTransaction) | Authorize and capture in one step |
| `get_transaction_details()` | `getTransactionDetailsRequest` | Get full transaction details (for refunds) |
| `capture()` | `createTransactionRequest` (priorAuthCaptureTransaction) | Capture a prior authorization |
| `void()` | `createTransactionRequest` (voidTransaction) | Void an authorized transaction |
| `refund()` | `createTransactionRequest` (refundTransaction) | Refund a captured transaction |

---

## L3 — Cross-Model, Override Pattern, Workflow Trigger

### Cross-Model Architecture

```
payment_authorize
  ├─ payment.provider:    Adds 'authorize' code, API credentials, feature flags
  │   └─ action_update_merchant_details()  → Fetches merchant details from Authorize.Net
  ├─ payment.token:       authorize_profile field
  └─ payment.transaction: Full transaction lifecycle (authorize, capture, refund, void)
      └─ Uses AuthorizeAPI (plain Python class)
          └─ Makes XML HTTP requests to https://api.authorize.net/xml/v1/request.api

payment (base module)
  └─ Defines payment.transaction base lifecycle (state machine: pending→authorized→done)
  └─ Calls _send_*_request() methods on provider-specific extensions
```

### Authorize.Net Transaction State Machine

```
pending ──authorize()──► authorized ──capture()──► done
                              │
                              │ (if capture_manually=False: auth_and_capture skips authorized)
                              ▼
                         (captured)

done ──refund()──► done (refund tx created separately)
authorized ──void()──► canceled
```

### Response Code Handling (`_apply_updates`)

Authorize.Net returns a numeric `x_response_code`:

| Code | Meaning | Odoo Action |
|------|---------|-------------|
| `1` | Approved | Parse `x_type`: `auth_capture`/`prior_auth_capture` → `_set_done`; `auth_only` → `_set_authorized`; `void` → `_set_canceled` |
| `2` | Declined | `_set_canceled` with reason |
| `4` | Held for Review | `_set_pending` |
| `3` / other | Error | `_set_error` with reason text |

### Tokenization Flow

```
1. Customer enters card in Accept.js inline form (client-side)
2. Accept.js returns opaque_data (tokenized card data, no raw card number touches Odoo)
3. Odoo calls authorize() or auth_and_capture() with opaque_data
4. Authorize.Net returns transId (transaction ID)
5. _extract_token_values() called:
   └─ create_customer_profile(transId)
       └─ Creates customerProfileId + paymentProfileId in Authorize.Net
6. payment.token record created with:
   └─ provider_ref = paymentProfileId
   └─ authorize_profile = customerProfileId
   └─ payment_details = last 4 digits of card
7. Future payments: _send_payment_request(token=token_record)
   └─ authorize() with profile + paymentProfileId (no card data needed)
```

### Override Pattern Summary

| Pattern | Examples |
|---------|---------|
| Early-return guard | `_send_payment_request`, `_send_refund_request`, `_send_capture_request`, `_send_void_request` — all check `provider_code != 'authorize'` and call `super()` |
| super() chain | All base payment.transaction methods are called through `super()` when not Authorize.Net |
| Feature flag computation | `_compute_feature_support_fields` uses `filtered()` + `update()` pattern |
| State machine extension | `_apply_updates` completely overrides base to handle Authorize.Net-specific response codes |

---

## L4 — Version Changes: Odoo 18 to Odoo 19

### Overview

`payment_authorize` was **significantly refactored** between Odoo 18 and Odoo 19, primarily to align with Odoo's new payment architecture introduced in Odoo 17/18 (the split between `payment.token` / `payment.method` / `payment.provider` / `payment.transaction`).

### Key Changes

#### 1. Module Version: 1.0 → 2.0

The version bump from 1.0 to 2.0 reflects a breaking change in the provider architecture. In Odoo 18/19, Odoo introduced `payment.method` as a separate concept from `payment.provider`. Authorize.Net had to be updated to work with this new architecture.

#### 2. `payment.token.authorize_profile` — New in Odoo 19

In Odoo 18, the Authorize.Net profile ID may have been stored differently (possibly as part of `provider_ref` or a different field). In Odoo 19, it has a dedicated `authorize_profile` field on `payment.token` for clarity.

#### 3. `AuthorizeAPI._prepare_authorization_transaction_request()` — Refactored

The `billTo` parameter logic was reorganized in Odoo 19. The distinction between ACH transactions (which require `billTo`) and tokenized transactions (which must NOT have `billTo`) is now clearer:

```python
# Odoo 19 — explicit comment explaining the rule
# The billTo parameter is required for new ACH transactions (transactions without a payment.token),
# but is not allowed for transactions with a payment.token.
```

#### 4. `action_update_merchant_details()` — Enhanced

The merchant details fetch action was updated to:
- Set `available_currency_ids` using `Command.set()` (new Odoo 17+ API)
- Store the fetched `publicClientKey` as `authorize_client_key`

#### 5. `_send_payment_request()` — Two-step logic

In Odoo 19, `_send_payment_request()` was refactored to handle both authorize-only and auth+capture modes based on `capture_manually` flag:

```python
if self.provider_id.capture_manually:
    res_content = authorize_api.authorize(self, token=self.token_id)
else:
    res_content = authorize_api.auth_and_capture(self, token=self.token_id)
```

In earlier versions, this logic may have been split or handled differently.

#### 6. Accept.js Integration

The `_authorize_get_inline_form_values()` method on `payment.provider` was **added in Odoo 19** to support Authorize.Net's Accept.js inline payment form. It returns a JSON-serialized dict with `state`, `login_id`, and `client_key` for the frontend JS to initialize Accept.js.

#### 7. `payment.transaction._send_refund_request()` — Void vs Refund Logic

The refund flow was enhanced to handle Authorize.Net's specific states:

| Transaction Status | Action |
|-------------------|--------|
| `voided` (already voided in Authorize.Net) | `_set_canceled(extra_allowed_states=('done',))` |
| `refunded` (already refunded in Authorize.Net) | `_set_done()` + immediate post-process |
| `authorized` (not settled) | `void()` — cannot refund unsettled tx |
| `captured` (settled) | `refund()` — standard refund |

### Migration Summary

| Item | Change | Migration Effort |
|------|--------|-----------------|
| Module version | 1.0 → 2.0 | Clean install required |
| `authorize_profile` field | New dedicated field | Data migration if profiles exist |
| `AuthorizeAPI` refactor | billTo logic clarified | None — behavior preserved |
| `action_update_merchant_details()` | Uses `Command.set()` | None — automatic |
| Accept.js support | New `_authorize_get_inline_form_values()` | New feature — enable in frontend |
| Refund/void state handling | Enhanced state machine | None — improved edge case handling |

### Conclusion

`payment_authorize` requires **moderate attention** during migration. The core transaction lifecycle (authorize → capture → refund) remains the same, but field names, some method signatures, and Accept.js integration are new in Odoo 19. Existing Authorize.Net configurations will need to be verified after upgrade.

---

## Post-Init Hook

The module has a `post_init_hook` and `uninstall_hook` (defined in `__manifest__.py`) that likely handle migration of Authorize.Net-specific data during install/uninstall.

## Assets

- `web.assets_frontend`: `payment_form.js` (Accept.js integration) + `payment_authorize.scss`

## Related

- [Modules/payment](payment.md) — Base payment module (state machine, transaction lifecycle)
- [Modules/payment_stripe](payment_stripe.md) — Stripe payment provider
- [Modules/pos_online_payment_self_order](pos_online_payment_self_order.md) — Uses Authorize.Net (or other providers) for self-order online payments
