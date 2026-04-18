---
Module: website_payment
Version: Odoo 18
Type: Integration
Tags: #payment #website #e-commerce #donations
Related: [Modules/Account](Modules/account.md), [Modules/Website](Modules/website.md)
---

# website_payment — Website Online Payments

## Overview

**Category:** Hidden | **Auto-install:** `True`
**Depends:** `website`, `account_payment`, `portal`

`website_payment` is the **bridge module** that makes the Odoo payment framework multi-website-aware. It enables:

- Per-website payment provider routing (providers assigned to specific websites)
- Donation payment flow with dedicated form and confirmation emails
- Country-aware provider visibility on the website checkout
- Stripe onboarding from website settings

This module does NOT implement any payment logic itself — it layers multi-website concerns onto the `payment` and `account_payment` foundations.

---

## Architecture

### Module Chain

```
payment.provider          (base — code, state, redirect/form controllers)
        ↑
        │  _inherit
        │
website_payment            (website_id on provider, donation flow, website-aware routing)
        ↑
        │  inherit
        │
account_payment           (payment → account.move journal entries, invoice matching)
```

### Provider Routing Flow (Cart → Checkout)

```
Customer on Website A
    ↓
/payment/pay  (website_payment/controllers/payment.py)
    → injects website_id=request.website.id
        ↓
PaymentProvider._get_compatible_providers(website_id=A)
    → filters providers: website_id=None OR website_id=A
    → drops providers assigned to other websites
        ↓
Only Website A's providers shown on checkout form
```

---

## Models

### `payment.provider` (EXTENDED by website_payment)

> Base model: `payment` module. `website_payment` adds `website_id` and overrides `_get_compatible_providers`.

#### Fields Added by website_payment

| Field | Type | Description |
|-------|------|-------------|
| `website_id` | `Many2one(website)` | Restricts this provider to a specific website. If empty, provider is **global** (available on all websites). `ondelete='restrict'` prevents deleting a website that has assigned providers. |

#### Methods Overridden

**`_get_compatible_providers(*args, website_id=None, report=None, **kwargs)`** (`@api.model`)

> Extends the base provider compatibility check. The base `payment` module already filters by: state (enabled), company, currency, partner-country availability. `website_payment` adds the website filter.

Logic:
1. Calls `super()` to get providers matching base criteria
2. If `website_id` is provided:
   - Filters to only providers where `website_id == provided_website_id` OR `website_id == False` (global)
   - Providers filtered out are logged to the `report` dict with reason `incompatible_website`
3. Returns filtered provider set

This is the core mechanism for **provider-specific routing per website**. A provider with `website_id=1` will only appear on Website 1's checkout. A provider with `website_id=False` appears on all websites.

**`get_base_url()`**

> Overrides base to give priority to `request.httprequest.url_root` (the website's domain).

```python
if request and request.httprequest.url_root:
    return iri_to_uri(request.httprequest.url_root)
return super().get_base_url()
```

Used by payment providers (especially Stripe) to build redirect URLs back to the correct website domain in multi-website setups.

**`copy(default=None)`**

> Overrides base copy. If `stripe_connect_onboarding` context is active, unsets `website_id` on the copy so the new provider is global. This allows Stripe Connect onboarding to create a global provider from a website-specific one.

---

### `payment.transaction` (EXTENDED by website_payment)

> Base model: `payment` module.

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `is_donation` | `Boolean` | Set to `True` for donation payments (vs. standard e-commerce payments). Used downstream to trigger donation-specific behavior. |

#### Methods

**`_post_process()`**

> Extends base `_post_process()`. After the base post-processing (state update, journaling), if the transaction is `state='done'` AND `is_donation=True`:

1. Calls `_send_donation_email()` to send a confirmation email to the donor
2. Logs a detailed message on the `payment_id` (account.payment record) with donor details: company, partner, name, country, email

The message log uses `Markup` for safe HTML insertion. This gives accountants a traceable record in the payment's chatter.

**`_send_donation_email(is_internal_notification=False, comment=None, recipient_email=None)`**

Sends a donation-specific email using QWeb template `website_payment.donation_mail_body`.

- If `is_internal_notification=True`: sends to `recipient_email` (the website owner) with subject "A donation has been made on your website"
- Otherwise: sends to `self.partner_email` (the donor) with subject "Donation confirmation"
- Uses `email_layout_xmlid="mail.mail_notification_light"` for consistent styling
- `force_send=True` bypasses the mail queue cron for immediate delivery

---

### `account.payment` (EXTENDED by website_payment)

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `is_donation` | `Boolean` (related) | `related="payment_transaction_id.is_donation"`. Mirrors the donation flag from the linked transaction. |

This makes the donation flag visible and searchable on the payment record in the accounting app, without duplicating storage.

---

### `res.config.settings` (EXTENDED by website_payment)

> Transient wizard. Inherits from `base` + `account_payment` settings.

#### Fields Added

| Field | Type | Description |
|-------|------|-------------|
| `providers_state` | `Selection([none/paypal_only/other_than_paypal])` | Computed field. Shows the state of active providers for this website. Used to conditionally display UI elements (Stripe activation button vs. "Configure" button). |
| `first_provider_label` | `Char` | Computed. Returns the display name of the first active provider (prefers Stripe). Used as the wizard action button label. |
| `is_stripe_supported_country` | `Boolean` (related) | `related='company_id.country_id.is_stripe_supported_country'`. Indicates whether the current company's country is supported by Stripe. |

#### Methods

**`_get_activated_providers()`**

> Searches for all non-disabled payment providers, excluding the manual "Wire Transfer" provider, and filters to those either global (`website_id=False`) or matching the current website. Used as the basis for `providers_state` computation.

**`_compute_providers_state()`**

> Computes `providers_state` and `first_provider_label` based on `_get_activated_providers()`:
- `none`: no active providers
- `paypal_only`: exactly 1 provider and it is PayPal
- `other_than_paypal`: 1+ providers, at least one is not PayPal

This drives the UI branching in `res_config_settings_views.xml`:
- `is_stripe_supported_country=False` → hide Stripe activation button
- `providers_state == 'none'` → show "Configure First Provider" button
- `providers_state == 'paypal_only'` → show PayPal config link

**`action_activate_stripe()`**

> Opens the Stripe Connect onboarding wizard if the company country supports Stripe. Redirects to the website settings page after. Returns `False` if country not supported.

**`action_configure_first_provider()`**

> Opens the form view of the first active payment provider (prefers Stripe) for quick configuration.

---

## Controllers

### `website_payment.controllers.payment.PaymentPortal`

Extends `account_payment.controllers.payment.PaymentPortal`.

#### Routes

**`/donation/pay` (GET/POST, `auth='public'`, `website=True`)**

The dedicated donation landing page. Behaves like `payment_pay` but with donation-specific defaults:

- `is_donation=True` injected into kwargs
- Default amount: `25.0` (or URL param)
- Default currency: company currency (or URL param)
- `donation_options` JSON parsed from URL, defaults to `{"customAmount": "freeAmount"}`
- For public users: generates an access token from partner_id, amount, currency_id
- Delegates to `payment_pay` for rendering

**`/donation/transaction/<minimum_amount>` (JSON, `auth='public'`, `website=True`)**

Creates a donation payment transaction with donation-specific validation:

- Validates `amount >= minimum_amount`
- For public users: requires name, email, country_id in `partner_details`
- For logged-in users: uses their partner record
- Sets `is_donation=True` on the transaction
- Calls `_send_donation_email(True, ...)` to notify the website owner immediately
- Returns `_get_processing_values()` (redirect to provider's hosted form)

**`_get_extra_payment_form_values(is_donation=False, ...)`**

> Builds the rendering context for the payment form template. For donations, adds: `is_donation`, `partner`, `submit_button_label='Donate'`, `transaction_route`, `partner_details`, `countries`, `donation_options`, `donation_amounts`, `donation_descriptions`.

**`_get_payment_page_template_xmlid(**kwargs)`**

> Returns `'website_payment.donation_pay'` template XMLID when `is_donation=True`, otherwise delegates to `super()`.

**`_compute_show_tokenize_input_mapping(providers_sudo, **kwargs)`**

> Hides "Save my payment details" checkbox for donations by public (unauthenticated) users. Tokenization requires a partner to assign the token to, which public users don't have.

---

### `website_payment.controllers.portal.PortalAccount`

Extends `account_payment.controllers.portal.PortalAccount`.

**`_invoice_get_page_view_values(*args, **kwargs)`**

> Overrides to pass `website_id=request.website.id` into the parent call. This ensures that when a customer views their invoice in the portal, the payment providers shown are filtered by the website the invoice originated from.

---

## Donation Snippet: `s_donation`

### Architecture

The donation snippet is a drag-and-drop website snippet (not a model). It is registered in `website_payment/views/snippets/snippets.xml` and configured via JavaScript options in `website_payment/static/src/snippets/s_donation/options.js`.

### Snippet Options (from `options.js`)

When an administrator edits the donation snippet in WYSIWYG mode, they can configure:

| Option | Description |
|--------|-------------|
| `donationEmail` | Email address to receive donation notifications |
| `minimumAmount` | Minimum donation amount (validated server-side) |
| `maximumAmount` | Maximum donation amount (validated client-side) |
| `customAmount` | `"freeAmount"` (user types any amount) or fixed preset amounts |
| `donationAmounts` | Array of preset amounts (e.g., `[10, 25, 50, 100]`) |
| `prefilledOptions` | Whether to show preset amount radio buttons |
| `descriptions` | Per-amount descriptions shown as subtitles |

### Donation Data Flow

```
Snippet Options (JS) → /donation/pay URL params
    ↓
payment.py donation_pay() builds kwargs
    ↓
payment_pay() renders donation_pay template
    ↓
User fills form → /donation/transaction/<min>
    ↓
donation_transaction() creates tx with is_donation=True
    ↓
_post_process() → _send_donation_email (confirmation to donor)
                 → _send_donation_email(True, ...) (notification to owner)
                 → message_log on payment_id
```

---

## L4: Country-Aware Provider Filtering

The `payment` base module (in `addons/payment`) implements `provider._get_compatible_providers` which filters by:

1. Provider state (must be enabled)
2. Company (must match context)
3. Available currencies (provider's `journal_id.currency_id` must match transaction currency)
4. Partner country availability (`provider.country_ids` must include partner's country, or be empty = all countries)

`website_payment` adds step 5:

5. **Website filtering** — provider must either have `website_id=False` (global) or `website_id == request_website_id`

This means a provider can be:
- **Global**: `website_id=False` — appears on all websites
- **Website-specific**: `website_id=3` — appears only on Website 3
- **Hidden**: filtered out by country, currency, or state

The combined effect: website administrators can configure different payment options per website, and even per-country within a website.

---

## Data Files

| File | Purpose |
|------|---------|
| `data/mail_templates.xml` | Email template for donation confirmation to donor |
| `data/mail_template_data.xml` | Internal notification template for website owner |
| `views/payment_provider.xml` | Adds `website_id` field to the provider form view |
| `views/payment_form_templates.xml` | Donation payment form QWeb template |
| `views/res_config_settings_views.xml` | Conditional UI for Stripe activation / provider config |
| `views/snippets/snippets.xml` + `s_donation.xml` | Donation snippet registration |

---

## Key Design Notes

- **Auto-install**: `auto_install=True` — installs automatically when both `website` and `account_payment` are installed. This ensures the multi-website payment layer is always present.
- **Provider copy**: The `copy()` override for `stripe_connect_onboarding` ensures that providers created during Stripe Connect OAuth flow are global by default.
- **Donation email**: Sent immediately (`force_send=True`) rather than queued, because donors expect instant confirmation.
- **Stripe country support**: The `is_stripe_supported_country` is a computed proxy to `res.country.is_stripe_supported_country`, which is defined in the base `payment` module's country data.
- **Wire transfer exclusion**: `_get_activated_providers` explicitly excludes the `payment_provider_transfer` (manual/wire transfer) provider from the "active providers" count, since it requires no configuration.
