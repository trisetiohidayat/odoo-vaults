---
type: module
module: website_payment
tags: [odoo, odoo19, website, payment, donation, transaction, multi-website]
created: 2026-04-06
updated: 2026-04-11
---

# website_payment

> Payment integration bridge module for multi-website Odoo. Adds website-aware provider filtering, donation handling, and CMS snippets.

```
Module: website_payment
Category: Website/Website
Depends: website, account_payment, portal
Auto-install: True
License: LGPL-3
```

## Role

`website_payment` is a **bridge module** that extends the `payment` module with multi-website awareness. It does not provide payment processing itself — that is handled by provider-specific modules (e.g., `payment_stripe`). The module's responsibilities are:

1. Scope `payment.provider` records to specific websites via `website_id`
2. Inject website context into all payment portal controller calls
3. Handle donation-specific flows (custom amount validation, donor notifications, gift receipts)
4. Expose website builder snippets for donation forms and payment method display

**Auto-install note:** With `auto_install: True`, this module is installed automatically when both `website` and `account_payment` are present — no manual activation needed.

---

## Dependencies

| Module | Role |
|---|---|
| `website` | Website registry, `request.website`, multi-website routing |
| `account_payment` | Base payment models (`payment.provider`, `payment.transaction`, `account.payment`) |
| `portal` | Authentication middleware for payment portal routes |

Downstream modules that auto-install it: any module that depends on both `website` and `account_payment`.

---

## Architecture

```
payment.provider ──────[website_id]────────▶ website
       │
       │ _get_compatible_providers()
       │ filtered by website scope
payment.portal controller ──[request.website]────┘
       │
       ├── /donation/pay          → donation_pay()   → payment_pay(is_donation=True)
       ├── /donation/transaction  → donation_transaction()
       └── /website_payment/snippet/supported_payment_methods
```

---

## Models

### `payment.provider` (Extended)

**File:** `models/payment_provider.py`
**Parent:** `payment.provider` (from `payment` module)

#### Additional Fields

```python
website_id = fields.Many2one(
    "website",
    check_company=True,
    copy=False,  # handled in `copy` override to prevent company inconsistencies
    ondelete="restrict",
)
```

| Property | Value | Rationale |
|---|---|---|
| `copy=False` | Standard ORM copy is blocked at field level | `copy()` override manages website assignment manually |
| `ondelete="restrict"` | Cannot delete a website with assigned providers | Prevents orphaned provider records |
| `check_company=True` | Enforced via `_check_company_auto = True` | Company-domain matching on the field |

**L4:** The `check_company=True` combined with `_check_company_domain_parent_of` means that when a provider is assigned to a website, the provider's company must be the same as or a parent of the website's company. This prevents a child-company website from accessing a parent-company provider (or vice versa) through company hierarchy mismatch.

#### `_get_compatible_providers()` — Override

```python
@api.model
def _get_compatible_providers(self, *args, website_id=None, report=None, **kwargs):
    providers = super()._get_compatible_providers(
        *args, website_id=website_id, report=report, **kwargs
    )
    if website_id:
        unfiltered_providers = providers
        providers = providers.filtered(
            lambda p: not p.website_id or p.website_id.id == website_id
        )
        payment_utils.add_to_report(
            report,
            unfiltered_providers - providers,
            available=False,
            reason=REPORT_REASONS_MAPPING['incompatible_website'],
        )
    return providers
```

**Logic:** Filters the base-compatible providers (already filtered by amount, currency, state, etc.) to those whose `website_id` is unset (global provider) or matches the request's website. Rejected providers are logged to the availability `report` dict with reason `incompatible_website`.

**L4 — Performance:** This method is called on every portal payment page load and on AJAX calls to `payment_method()`. The Python-level `filtered()` runs after the ORM search; for large provider sets, the parent domain already constrains to `state IN ('enabled', 'test')` and `is_published = True`, so the filtered set is typically small (< 10 records). The overhead is negligible.

**L4 — Multi-website edge case:** A provider with no `website_id` is global. It appears on all websites. A provider with `website_id = website A` does NOT appear on website B — even if both websites share the same company. The website scope is a hard filter.

#### `get_base_url()` — Override

```python
def get_base_url(self):
    if request and request.httprequest.url_root:
        return iri_to_uri(request.httprequest.url_root)
    return super().get_base_url()
```

**Why it exists:** In multi-website configurations, a provider configured for `website A` may have its callback originate from `website B`'s domain (e.g., if the payment gateway redirects back to Odoo using a stored return URL). The `request.httprequest.url_root` ensures the base URL matches the actual request's originating domain, not the provider's stored `company_id.website` or other static URL.

**L4 — Punycode handling:** `iri_to_uri()` converts internationalized domain names (IDN) stored as ASCII Punycode in DNS into URI-compliant format. For example, `xn--nxasmq6b.com` (Punycode for `cafe.com`) is converted to `http://xn--nxasmq6b.com/`. Some payment gateway APIs reject non-ASCII hostnames, so this conversion is required for international domains to work correctly.

#### `copy()` — Override

```python
def copy(self, default=None):
    res = super().copy(default=default)
    if not default or 'website_id' not in default:
        for src, copy in zip(self, res):
            if src.website_id and src.company_id in copy.company_id.parent_ids:
                copy.website_id = src.website_id
    return res
```

**Why it exists:** The standard ORM `copy()` copies all non-`copy=False` fields. Since `website_id` has `copy=False`, it would be left blank. For multi-website setups, copying a provider from a parent company to a child company should preserve the website if the website also belongs to that company hierarchy.

**Edge case:** If `default` dict explicitly sets `website_id`, the override defers to the caller's intent and does not reassign. `zip(self, res)` handles batch copy operations correctly (each source record matched to its corresponding copy).

---

### `payment.transaction` (Extended)

**File:** `models/payment_transaction.py`
**Parent:** `payment.transaction` (from `payment` module)

#### Additional Fields

```python
is_donation = fields.Boolean(string="Is donation")
```

Set to `True` on the transaction record after creation in the donation flow (`donation_transaction()` controller).

#### `_post_process()` — Override

```python
def _post_process(self):
    super()._post_process()
    for donation_tx in self.filtered(lambda tx: tx.state == 'done' and tx.is_donation):
        donation_tx._send_donation_email()
        msg = [_('Payment received from donation with following details:')]
        for field in ['company_id', 'partner_id', 'partner_name',
                      'partner_country_id', 'partner_email']:
            field_name = donation_tx._fields[field].string
            value = donation_tx[field]
            if value:
                if hasattr(value, 'name'):
                    value = value.name
                msg.append(Markup('<br/>- %s: %s') % (field_name, value))
        donation_tx.payment_id._message_log(body=Markup().join(msg))
```

**Workflow trigger:** Called by the payment processing pipeline after a transaction reaches `done` state. The parent `payment.transaction._post_process()` handles settlement, token creation, and invoice linking. This override adds donation-specific post-processing.

**Email behavior:** Sends two emails — donor confirmation and internal admin notification — via `_send_donation_email()`. The order of the two calls within the loop matters: `_send_donation_email()` is called first without `is_internal_notification` (donor receipt), then the internal notification is handled in the controller before `_post_process()` is reached (via `donation_transaction()`).

**Failure mode:** If `payment_id` is not set on the transaction (possible in some acquirer flows where settlement is deferred), `_message_log()` will raise an `AttributeError`. The `payment_id` field is populated by `payment`'s `_create_payment_vals_from_tx()` during post-processing. Most payment providers set this correctly, but custom providers may not.

**L4 — N+1 on `_message_log`:** The loop iterates over fields and calls `hasattr(value, 'name')` for each. If these fields are not prefetched, each access triggers a read. The recordset is small (donations are processed one at a time in practice), so this is not a significant concern.

#### `_send_donation_email()`

```python
def _send_donation_email(self, is_internal_notification=False, comment=None, recipient_email=None):
```

| Parameter | Direction | Meaning |
|---|---|---|
| `is_internal_notification=True` | Outbound → site admin | Internal notification; subject: "A donation has been made on your website" |
| `is_internal_notification=False` | Outbound → donor | Donor receipt; subject: "Donation confirmation" |
| `comment` | Internal only | Donor comment shown in admin notification |
| `recipient_email` | Internal only | Admin email from snippet's `donationEmail` data attribute |

**Rendering pipeline:**
1. `ir.qweb` renders `website_payment.donation_mail_body` with `minimal_qcontext=True` (QWeb template-only context, no Odoo web context)
2. `mail.render.mixin._render_encapsulate()` wraps the body in `mail.mail_notification_light` for consistent styling
3. `mail.mail.sudo().create()` sends via the mail queue

**L4 — `sudo()` rationale:** Donation transactions may be created by public users who lack `mail.mail` create rights. Using `sudo()` bypasses record-level ACLs. The security implication is that any public donation can create an outbound email record, but the content is controlled by the transaction record (not user-supplied free text except for the comment, which is passed as a parameter and rendered via QWeb's auto-escaping `t-out`).

**L4 — Email from address:** Uses `self.company_id.email_formatted` — if the company has no email configured, this renders as `company.name@` (empty domain) and may fail SPF/DKIM checks or be flagged as spoofed by email filters. Odoo does not validate this on transaction creation.

**L4 — Language handling:** Both the QWeb rendering and `_render_encapsulate` use `lang=self.partner_id.lang`, meaning the donation email is sent in the donor's preferred language. The company must have translations for all donor languages.

---

### `account.payment` (Extended)

**File:** `models/account_payment.py`
**Parent:** `account.payment` (from `account_payment` module)

```python
is_donation = fields.Boolean(
    string="Is Donation",
    related="payment_transaction_id.is_donation",
)
```

One-way non-stored `related` field. Derives donation status from the linked `payment.transaction` record via `payment_transaction_id`.

**L4 — Performance:** The `related` field performs a `read()` on the `payment.transaction` record whenever accessed. In list views showing many payments, this generates N+1 queries unless `payment_transaction_id` is prefetched. The related field pattern is appropriate here since donation status is rarely displayed in high-volume payment list contexts.

---

### `res.config.settings` (Extended)

**File:** `models/res_config_settings.py`
**Parent:** `res.config.settings` (from `payment` module)

#### `_get_active_providers_domain()` — Override

```python
def _get_active_providers_domain(self, *args, **kwargs):
    self.ensure_one()
    return Domain.AND([
        super()._get_active_providers_domain(*args, **kwargs),
        ['|', ('website_id', '=', False), ('website_id', '=', self.website_id.id)],
    ])
```

**Why this exists:** The `payment` module's `res.config.settings` computes `active_provider_id` and `has_enabled_provider` from `_get_active_providers_domain()`. By interspersing a website filter at the domain level, the Settings UI shows only providers active on the current website, not all providers across all websites.

**Domain pattern:** `['|', ('website_id', '=', False), ('website_id', '=', self.website_id.id)]` matches global providers (no website) OR providers assigned to the current website. Uses `Domain.AND()` so the full expression is pushed to the ORM search layer (not Python-level `filtered()`), which is more efficient.

#### `action_w_payment_start_payment_onboarding()`

```python
def action_w_payment_start_payment_onboarding(self):
    menu = self.env.ref('website.menu_website_website_settings', raise_if_not_found=False)
    return self._start_payment_onboarding(menu and menu.id)
```

**Why the unique name prefix `action_w_payment_`:** The `sale` module (`sale_payment`) also overrides `res.config.settings` with an `action_start_payment_onboarding` method. Both inherit from the same parent. Without the prefix, Python's MRO would cause one to shadow the other unpredictably. The `w_payment_` prefix ensures distinct method resolution.

**L4 — Onboarding flow:** `_start_payment_onboarding()` launches the payment provider setup wizard (typically Stripe). The `menu` parameter determines where the user lands after completing onboarding. Passing `website.menu_website_website_settings` redirects to the website settings page, keeping the context consistent with the website settings UI.

---

## Controllers

### `website_payment.controllers.payment.PaymentPortal`

**Parent classes (MRO):**
1. `payment.controllers.portal.PaymentPortal`
2. `account_payment.controllers.payment.PaymentPortal`

Extends both to inject `website_id` into all payment-provider-filtering calls.

**File:** `controllers/payment.py`

#### `payment_pay()` — Website-Aware Override

```python
@route()
def payment_pay(self, *args, **kwargs):
    return super().payment_pay(*args, website_id=request.website.id, **kwargs)
```

**Injects:** `website_id=request.website.id` into the parent call. The parent `payment` module's `payment_pay()` passes `website_id` to `_get_compatible_providers()`, which is overridden by `website_payment` to scope providers to the current website.

This is the core mechanism that makes the payment form website-scoped — all downstream template rendering, provider filtering, and payment method display respect the website boundary.

#### `payment_method()` — Website-Aware Override

```python
@route()
def payment_method(self, **kwargs):
    return super().payment_method(website_id=request.website.id, **kwargs)
```

Same pattern as `payment_pay()`. Used for dynamic payment method reloads (e.g., when the user changes currency on the payment page). Ensures the provider list stays website-scoped across all AJAX interactions.

---

### `website_payment.controllers.portal.PortalAccount`

**Parent:** `account_payment.controllers.portal.PortalAccount`

**File:** `controllers/portal.py`

#### `_invoice_get_page_view_values()` — Website-Aware Override

```python
def _invoice_get_page_view_values(self, *args, **kwargs):
    return super()._invoice_get_page_view_values(*args, website_id=request.website.id, **kwargs)
```

When a customer views an invoice from the portal, embedded payment options are filtered to the current website. Prevents cross-website payment provider exposure on invoice payment pages.

---

### `website_payment.controllers.payment.PaymentPortal` (Donation Controller)

**Parent:** `payment.controllers.portal.PaymentPortal`
**File:** `controllers/payment.py`

#### `GET/POST /donation/pay`

```python
@http.route('/donation/pay', type='http', methods=['GET', 'POST'],
            auth='public', website=True, sitemap=False,
            list_as_website_content=_lt("Donation Payment"))
def donation_pay(self, **kwargs):
```

| Injected Parameter | Default | Source |
|---|---|---|
| `is_donation` | `True` | Forced in method body |
| `currency_id` | `request.env.company.currency_id.id` | From `kwargs` or company default |
| `amount` | `25.0` | From `kwargs` or constant default |
| `donation_options` | `{"customAmount": "freeAmount"}` | JSON from `kwargs` or fallback |
| `partner_id` | `request.env.user.partner_id.id` | Public user partner |
| `access_token` | Generated from partner, amount, currency | For public users only |

**Auth:** `auth='public'` — donations are accessible to unauthenticated users. For public users, the partner is `website.user_id.partner_id` (a generic placeholder). This prevents real personal data from being associated with anonymous donations.

**L4 — `list_as_website_content`:** Causes Odoo to index this route as website content, enabling SEO metadata and sitemap inclusion. The translated string is used as the page title in search results.

**L4 — CSRF:** `website=True` on the route enables the website routing middleware which handles CSRF validation differently from standard controller routes (website routes use a relaxed CSRF policy for public-facing forms, but POST from the donation snippet still requires a valid token, injected by `donation_snippet.js` via `odoo.csrf_token`).

#### `POST /donation/transaction/<minimum_amount>`

```python
@http.route('/donation/transaction/<minimum_amount>', type='jsonrpc',
            auth='public', website=True, sitemap=False)
def donation_transaction(self, amount, currency_id, partner_id, access_token,
                         minimum_amount=0, **kwargs):
```

**Validation chain:**

1. `amount >= minimum_amount` → `ValidationError` if violated
2. If public user or no partner: requires `partner_details` with non-empty `name`, `email`, `country_id`
3. `_validate_transaction_kwargs()` with `additional_allowed_keys=('donation_comment', 'donation_recipient_email', 'partner_details', 'reference_prefix')`
4. Access token validated by parent `_create_transaction()`

**Public user handling:**

```python
use_public_partner = request.env.user._is_public() or not partner_id
if use_public_partner:
    partner_id = request.website.user_id.partner_id.id
    kwargs['custom_create_values'] = {'tokenize': False}
    tx_sudo.update({
        'partner_name': details['name'],
        'partner_email': details['email'],
        'partner_country_id': int(details['country_id']),
    })
```

**L4 — Tokenization security:** For public users, `tokenize=False` is forced to prevent creating payment tokens bound to the generic public partner. Tokens stored on the public partner would be accessible to any subsequent public donation, creating a security issue. Donors who want tokenization must log in.

**L4 — Partner override:** When a logged-in user makes a donation and has no `partner_country_id` on the transaction, the country is back-filled from `kwargs['partner_details']['country_id']`. This is a fallback for a race condition where the transaction is created before the country field is set.

**Post-transaction flow:**
- `tx_sudo.is_donation = True` set explicitly
- Internal notification email sent via `_send_donation_email(is_internal_notification=True, comment, recipient_email)`
- Access token regenerated with actual transaction partner/amount (user may have changed amount on payment page)
- `_update_landing_route()` updates transaction's landing URL with the new access token
- Returns `_get_processing_values()` (payment provider-specific redirect form or inline form data)

#### `_get_extra_payment_form_values()` — Donation Context Injection

```python
def _get_extra_payment_form_values(
    self, donation_options=None, donation_descriptions=None, is_donation=False, **kwargs
):
```

| Key | Content |
|---|---|
| `is_donation` | `True` |
| `partner` | Logged-in user's `res.partner`, or empty recordset for public |
| `submit_button_label` | `"Donate"` (translated) |
| `transaction_route` | `/donation/transaction/<minimumAmount>` |
| `partner_details` | Pre-filled from logged-in partner (name, email, country) |
| `error` | `{}` (empty; errors handled client-side) |
| `countries` | All `res.country` records (for public donation form dropdown) |
| `donation_options` | Parsed JSON from snippet configuration |
| `donation_amounts` | List of preconfigured amounts |
| `donation_descriptions` | Per-amount descriptions |

**Security design:** For logged-in users, `partner_details` is pre-filled from the authenticated session's partner record — not from request parameters. This prevents parameter injection attacks where a malicious actor passes `partner_details[name]=Admin` to override the real partner's name.

**L4 — Countries query:** All countries are loaded with `sudo()` and no domain. For a portal with many countries (~250), the query is acceptable but could be scoped to the website's countries of operation in a future optimization.

#### `_get_payment_page_template_xmlid()` — Donation Template Routing

```python
def _get_payment_page_template_xmlid(self, **kwargs):
    if kwargs.get('is_donation'):
        return 'website_payment.donation_pay'
    return super()._get_payment_page_template_xmlid(**kwargs)
```

Routes donation payments to `website_payment.donation_pay` instead of the standard `payment.form`. The donation template wraps `payment.form` in a branded layout with breadcrumb and donation-specific header.

#### `_compute_show_tokenize_input_mapping()` — Tokenization Security Override

```python
@staticmethod
def _compute_show_tokenize_input_mapping(providers_sudo, **kwargs):
    res = super(PaymentPortal, PaymentPortal)._compute_show_tokenize_input_mapping(
        providers_sudo, **kwargs
    )
    if kwargs.get('is_donation') and request.env.user._is_public():
        for provider_sudo in providers_sudo:
            res[provider_sudo.id] = False
    return res
```

Public users cannot save payment tokens because there is no persistent partner to associate them with. This override hides the "Save my payment details" checkbox on donation forms for unauthenticated users.

#### `GET /website_payment/snippet/supported_payment_methods`

```python
@http.route('/website_payment/snippet/supported_payment_methods',
            type='http', methods=['GET'], auth='public', website=True,
            sitemap=False, readonly=True)
def get_supported_payment_methods(self, limit=None):
```

**Returns:** `List[{'name': str, 'image_url': str}]`

**Query domain construction:**

```python
# Brands (non-primary) of compatible primary payment methods
# e.g., Amex brand under Card primary method
brands_domain = Domain([
    ('is_primary', '=', False),
    ('primary_payment_method_id.provider_ids', 'in', compatible_providers_sudo.ids),
    ('primary_payment_method_id.active', '=', True),
])
# Primary payment methods with no brand children (e.g., PayPal standalone)
primary_without_brands_domain = Domain([
    ('is_primary', '=', True),
    ('brand_ids', '=', False),
    ('provider_ids', 'in', compatible_providers_sudo.ids),
])
```

**L4 — Company context:** Uses `website.company_id` (not the user's company) to determine which providers are considered. The snippet displays what the website owner configured, regardless of which customer is viewing.

**L4 — User context:** The query uses `.with_user(website.user_id).sudo()` to run as the website's public user. This ensures that the payment methods visible to customers match what the public user can access — it bypasses any `ir.rule` that might restrict payment methods to specific internal user groups.

**Cache control headers:**

| User type | Cache-Control | Rationale |
|---|---|---|
| Internal (`_is_internal()`) | `no-cache` | Editors must see live provider configuration |
| Public/portal | `public, max-age=604800, stale-while-revalidate=86400` | 7-day cache + 1-day stale window |

The stale window prevents visual glitches during provider updates — the old list continues to be served while the client could revalidate (no automatic revalidation is triggered; the stale value is simply permitted).

---

## Views

### `views/payment_provider.xml`

Injects `website_id` into the payment provider form under `payment_state` group:

```xml
<field name="website_id"
       options="{'no_open': True, 'no_create_edit': True}"
       groups="website.group_multi_website"/>
```

- `groups="website.group_multi_website"`: Field is hidden for single-website installations
- `no_open=True`: Prevents navigating to the website record from the provider form (it's a selector, not a navigation target)
- `no_create_edit=True`: Prevents creating/editing websites from this field (website management is done elsewhere)

### `views/payment_form_templates.xml`

**`website_payment.payment_form`** (extends `payment.form`):
Injects donation information section before `#o_payment_form_options`. Uses `t-call="website_payment.donation_information"` to render donor fields inside the standard payment form.

**`website_payment.donation_pay`**:
Full-page template wrapping `payment.form` with `portal.frontend_layout`. Includes `payment.portal_breadcrumb` and handles edge cases:
- No amount → "There is nothing to pay." (`alert-info`)
- Missing currency → "The currency is missing or incorrect." (`alert-warning`)

**`website_payment.donation_information`**:
Donor details form section (name, email, country dropdown, amount selector, optional comment). For logged-in users, name and email are `readonly`. Country dropdown is disabled for logged-in users with an existing country.

**`website_payment.donation_input`**:
Reusable partial for custom amount numeric input. Supports `min` (minimumAmount), `max` (maximumAmount, only when `customAmount == 'slider'`), with inline validation warning elements.

### `views/snippets/snippets.xml`

Registers three snippets in the Website Builder palette:

| Snippet | XML ID | Group | Key Attribute |
|---|---|---|---|
| Donation Block | `website_payment.s_donation` | `contact_and_forms` | Full section with image |
| Donation Button | `website_payment.s_donation_button` | `contact_and_forms` | Grid-span 3, form only |
| Supported Payment Methods | `website_payment.s_supported_payment_methods` | (default) | Dynamic logo display |

All use `t-forbid-sanitize="form"` because they contain user-configured donation amounts and descriptions that must be rendered verbatim.

### `views/snippets/s_donation.xml`

**`s_donation_button`:** Interactive snippet with:
- Hidden `donation_descriptions` inputs (`o_translatable_input_hidden` class for in-editor translation)
- Prefilled amount buttons with descriptions
- Custom amount input field
- "Donate Now" submit button

**Snippet data attributes on `.s_donation`:**

| Attribute | Type | Purpose |
|---|---|---|
| `data-donation-email` | String | Internal notification recipient |
| `data-custom-amount` | Enum | `"freeAmount"` (default), `"slider"`, `"fixed"` |
| `data-prefilled-options` | Bool | Show preset amount buttons |
| `data-descriptions` | Bool | Show per-amount descriptions |
| `data-donation-amounts` | JSON list | Preset amounts, e.g. `["10", "25", "50", "100"]` |
| `data-minimum-amount` | Float | Minimum donation validation |
| `data-maximum-amount` | Float | Maximum for slider mode |
| `data-slider-step` | Float | Slider increment step |
| `data-default-amount` | Float | Pre-selected amount |
| `data-display-options` | String | `"true"` activates button grid view |

**`s_donation`:** Full-width section wrapping `s_donation_button` with `o_cc o_cc1` (centered content, color scheme 1) and a decorative SVG shape image using `o-color-1`.

### `views/snippets/s_supported_payment_methods.xml`

Renders as an empty `<div>` with `o_not_editable` and `data-oe-protected="true"`. Actual payment method logos are loaded via `supported_payment_methods.js` which calls `/website_payment/snippet/supported_payment_methods`. The `data-oe-protected` flag prevents the history plugin from recording DOM changes during live preview (which would cause a spurious "Unsaved changes" warning).

### `views/res_config_settings_views.xml`

**Header block** (shown when no provider is active):
- Warning banner: "Enable a payment provider to accept online payments"
- "Activate [Stripe]" button (disabled with tooltip if unavailable in the user's country)
- "Activate" button (links to onboarding)
- "Find another provider" button

**Payments block** (inserted after `website_info_settings`):
- "Configure Payment Methods" setting with "Visa, Mastercard..." help text
- Shows "Activate [ModuleName]" or "Configure [ActiveProvider]" based on state

Both blocks toggle via `invisible="active_provider_id"` / `invisible="not active_provider_id"`.

---

## Static Assets

### `static/src/snippets/s_donation/donation_snippet.js`

`DonationSnippet` extends `Interaction` (Owl-based public interaction system).

**`willStart()`:** Fetches currency via `rpc("/website/get_current_currency")`. Currency is needed for localized symbol display. The RPC is async; the template renders before it resolves, showing raw numbers initially.

**`start()`:** Iterates all amount button elements, removes any existing currency span, inserts the correct currency symbol based on `currency.position` (`before` or `after`). Uses `<canvas>` text measurement to size the custom amount input field precisely to fit the placeholder text + currency symbol.

**`onDonateClick()`:** Client-side validation:
1. Collect active amount (from clicked button, slider, or custom input)
2. Validate against `minimumAmount`
3. Build hidden form inputs (amount, currency_id, csrf_token, donation_options JSON)
4. Submit form to `/donation/pay`

**Edit mode mixin (`donation_snippet.edit.js`):** `DonationSnippetEdit` mixin overrides `onDonateClick` to a no-op. Registered in `public.interactions.edit` category, preventing the donation form from submitting when clicked in the website builder preview.

### `static/src/interactions/donation_form.js`

`DonationForm` extends `Interaction` for the payment page donation sub-form:

| Handler | Behavior |
|---|---|
| `onFocusAmountInput` | Auto-checks "Other Amount" radio button when custom input is focused |
| `onDonationCommentChange` | Toggles visibility of comment textarea |
| `onChangeAmountInput` | Validates against `min` and `data-min`; shows/hides warning messages |
| `onSelectRadioButton` | Focuses custom input for "Other Amount"; clears warnings for fixed amounts |

### `static/src/snippets/s_supported_payment_methods/`

- `supported_payment_methods.js`: Fetches payment methods from `/website_payment/snippet/supported_payment_methods`, renders logos into the container, respects `data-limit` attribute.
- `supported_payment_methods.edit.js`: Edit-mode JS that adds website builder options (e.g., logo count limit, display style).

### `static/src/snippets/s_donation/000.scss`

SCSS for the donation snippet. Uses `o-input-number-no-arrows()` mixin to hide browser number input spinners. The custom amount input uses `border: none; outline: none` for a seamless inline appearance within the donation button.

### `static/src/website_builder/`

- `donation_option_plugin.js`: Website builder plugin adding donation-specific options to the snippet options panel.
- `donation_option.xml`: XML definitions for the donation snippet's website builder options.
- `supported_payment_methods_option_plugin.js`, `supported_payment_methods_option.xml`: Same pattern for the supported payment methods snippet.

---

## Data Files

### `data/mail_templates.xml`

**Template:** `website_payment.donation_mail_body`

**Donor confirmation mode** (`is_internal_notification=False`):
- Subject: "Donation confirmation"
- Recipient: `tx.partner_email`
- Body: "Dear [partner_name]", thank you message with amount and date
- All transaction fields rendered via `t-out` (auto-escaped)

**Internal notification mode** (`is_internal_notification=True`):
- Subject: "A donation has been made on your website"
- Recipient: `donation_recipient_email` (site admin)
- Body: "Donation notification" header, full transaction details, donor comment if present
- Internal-only `comment` field displayed

Both modes use `tx.create_date` formatted as date only (not datetime) for cleaner display.

---

## Odoo 18 → 19 Changes

### Architecture Changes

| Aspect | Odoo 18 | Odoo 19 |
|---|---|---|
| Per-provider website scoping | Context-based or `ir.rule` filtering | Explicit `website_id` field on `payment.provider` with `check_company=True` |
| Donation form system | jQuery-based `$()` interactions | Owl `Interaction` class (`@web/public/interaction`) |
| Payment method model | Monolithic `payment.icon` | `payment.method` with primary/brand hierarchy |
| Supported PMs snippet | Static icon list | Dynamic `/website_payment/snippet/supported_payment_methods` endpoint with per-website filtering |
| Settings provider domain | Compute-level filtering | `_get_active_providers_domain()` override at domain level |
| Tokenization security | Not enforced per context | `_compute_show_tokenize_input_mapping()` explicitly hides for public donation users |

### Breaking Changes for Custom Integrations

- Custom payment portal controllers overriding `payment_pay()` without passing `website_id` will break multi-website filtering
- `payment.transaction` `is_donation` must be set explicitly — no automatic detection based on amount or provider
- Public donation transactions use `website.user_id.partner_id` as the partner — older custom integrations that created dynamic partner records may have stale patterns

---

## Security Considerations

| Concern | Mitigation |
|---|---|
| Public user donations creating tokens | `tokenize=False` forced for public users; `show_tokenize_input_mapping` hides the checkbox |
| Access token for public donations | Generated using `payment_utils.generate_access_token(partner_id, amount, currency_id)` — partner is the website's generic public partner |
| Donation amount validation | Server-side validation in `donation_transaction()` enforces `minimum_amount` even if client-side JS is bypassed |
| Stored XSS in donor details | `partner_name`, `partner_email` stored on `payment.transaction` (not rendered without escaping). Mail template uses `t-out` which auto-escapes |
| CSRF on donation form | Standard Odoo CSRF token injected as hidden input via `odoo.csrf_token` in `donation_snippet.js` |
| Email spoofing | `email_from` uses `company_id.email_formatted`; unconfigured company renders as `name@` (no domain) |
| Cross-site payment confusion | `get_base_url()` ensures callback URLs match the originating website's domain |
| Partner detail injection | Logged-in user `partner_details` are read from the authenticated session's partner record, not from request parameters |

---

## Edge Cases

| Scenario | Behavior |
|---|---|
| Provider has no `website_id` | Global provider — appears on all websites |
| Provider `website_id` set to website A, request from website B | Provider is invisible — hard filter, not soft fallback |
| Donation with `amount=0` | Renders "There is nothing to pay." on `donation_pay`; `donation_transaction` validates `amount >= minimum_amount` |
| Currency missing | Renders "The currency is missing or incorrect." warning |
| Website deleted with active providers | `ondelete="restrict"` blocks deletion |
| Provider copied to same company hierarchy | `website_id` propagates via `copy()` override |
| Internal user viewing supported PMs | `no-cache` header ensures live configuration |
| Logged-in user changes amount on payment page | Access token regenerated post-transaction; landing route updated via `_update_landing_route()` |
| Public user on donation form without JS | Standard HTML form submission to `/donation/pay` with server-side amount validation |
| Currency fetched via RPC before snippet renders | Button shows raw number until `start()` injects currency symbol |
| Company has no email configured | Donation emails send with empty domain in `From:` header |

---

## Cross-Module Integration

| Integration Point | Module | Mechanism |
|---|---|
| Payment provider availability | `payment` | `_get_compatible_providers()` filter |
| Transaction post-processing | `payment` | `_post_process()` hook after `state='done'` |
| Access token generation | `payment` | `payment_utils.generate_access_token()` |
| Donation email templating | `mail` | `ir.qweb` + `mail.mail_notification_light` |
| Website context | `website` | `request.website` injected in all controllers |
| Payment portal layout | `portal` | `portal.frontend_layout` + `portal_breadcrumb` |
| Payment form rendering | `payment` | `payment.form` QWeb template |
| Settings UI | `website` | `res.config.settings` form |
| Snippet registry | `website` | `website.snippets` extension |
| Donation snippet options | `website` | `donation_option.xml` (website builder options) |
| Company/currency | `account_payment` | `account.payment` model, `company.currency_id` |
| Public user partner | `website` | `website.user_id.partner_id` for anonymous donations |

---

## Related

- [[Modules/website]]
- [[Modules/payment]]
- [[Modules/account_payment]]
- [[Modules/website_sale]]
