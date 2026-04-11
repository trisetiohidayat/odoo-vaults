---
date_created: 2026-04-11
description: Newsletter subscription widgets integrated with the website builder and mass_mailing lists.
module: website_mass_mailing
tags: [#odoo19, #modules, #website, #mass_mailing, #newsletter, #subscription, #popup, #recaptcha]
related_modules: ["Mass Mailing", "Website", "Google reCAPTCHA", "Website Form Builder"]
---

# website_mass_mailing

> **Newsletter Subscribe Button** — Attract visitors to subscribe to mailing lists

**Category:** Website/Website
**Version:** 1.0
**License:** LGPL-3
**Author:** Odoo S.A.
**Depends:** `website`, `mass_mailing`, `google_recaptcha`
**Auto-installs on:** `website` + `mass_mailing` both present

---

## Module Overview

`website_mass_mailing` bridges the public-facing website with Odoo's `mass_mailing` engine. It provides a suite of drag-and-drop newsletter snippet templates, a popup subscription flow (with reCAPTCHA/Cloudflare Turnstile protection), and a form-builder integration for collecting subscriber data into `mailing.list` records.

It does **not** define any custom ORM models. Instead, it orchestrates existing `mass_mailing` infrastructure (`mailing.contact`, `mailing.subscription`, `mailing.list`) via JSON-RPC endpoints and the website form controller.

---

## Dependencies

| Module | Role |
|--------|------|
| `website` | Snippet rendering, session management, `auth='public'` routing |
| `mass_mailing` | `mailing.list`, `mailing.contact`, `mailing.subscription` models |
| `google_recaptcha` | Server-side reCAPTCHA/Turnstile token verification |

**Auto-install chain:** If both `website` and `mass_mailing` are installed, this module auto-installs. It will not install if either dependency is missing.

---

## Models

This module does **not** introduce any custom ORM model tables. It extends one existing model:

### `res.company` — Social Media Links

**File:** `models/res_company.py`
**Inheritance:** `_inherit = "res.company"`
**Method:** `_get_social_media_links()`

```python
def _get_social_media_links(self):
    social_media_links = super()._get_social_media_links()
    website_id = self.env['website'].get_current_website()
    social_media_links.update({
        'social_facebook': website_id.social_facebook or social_media_links.get('social_facebook'),
        'social_linkedin': website_id.social_linkedin or social_media_links.get('social_linkedin'),
        'social_twitter': website_id.social_twitter or social_media_links.get('social_twitter'),
        'social_instagram': website_id.social_instagram or social_media_links.get('social_instagram'),
        'social_tiktok': website_id.social_tiktok or social_media_links.get('social_tiktok'),
    })
    return social_media_links
```

**L2 — Why this override exists:**
Base `_get_social_media_links()` on `res.company` returns company-level social field values. This override delegates to the current website's social fields, falling back to company-level values if the website field is empty. This allows multi-website Odoo instances to have distinct social links per website while preserving the inheritance chain.

**L3 — Cross-model flow:**
- `website_id` is resolved via `self.env['website'].get_current_website()` — reads `website_id` from the HTTP request's matched routing rule.
- `self` is a `res.company` record — company context is independent of website context.
- Return value is a plain `dict` consumed by mass mailing email footer templates (`mass_mailing.s_mail_block_footer_social`, `mass_mailing.s_mail_block_footer_social_left`).
- The footer templates are patched by `views/snippets_templates.xml` to append a "Contact" link after the unsubscribe link.

---

## Controllers

### `MassMailController` — extends `mass_mailing.controllers.main.MassMailController`

**File:** `controllers/main.py`

All routes use `type='jsonrpc'` and `website=True` (binds to current website context) and `auth='public'` (no login required).

---

#### `is_subscriber(list_id, subscription_type, **post)` → JSON-RPC

**Route:** `GET/POST /website_mass_mailing/is_subscriber`
**Flags:** `website=True, auth='public'`

```python
@route('/website_mass_mailing/is_subscriber', type='jsonrpc', website=True, auth='public')
def is_subscriber(self, list_id, subscription_type, **post):
    value = self._get_value(subscription_type)
    fname = self._get_fname(subscription_type)
    is_subscriber = False
    if value and fname:
        contacts_count = request.env['mailing.subscription'].sudo().search_count(
            [('list_id', 'in', [int(list_id)]),
             (f'contact_id.{fname}', '=', value),
             ('opt_out', '=', False)])
        is_subscriber = contacts_count > 0
    return {'is_subscriber': is_subscriber, 'value': value}
```

**L2 — Parameters:**

| Parameter | Source | Values |
|---|---|---|
| `list_id` | DOM `data-list-id` (section or form level) | `int` mailing list ID |
| `subscription_type` | `input.name` in the DOM | `'email'` or `'mobile'` |
| `value` | Resolved by `_get_value()` | email string or `None` |

**L2 — `_get_value()` logic:**

```python
def _get_value(self, subscription_type):
    value = None
    if subscription_type == 'email':
        if not request.env.user._is_public():
            value = request.env.user.email        # logged-in user
        elif request.session.get('mass_mailing_email'):
            value = request.session['mass_mailing_email']  # prior session store
    return value
```

**L3 — Resolution chain:**

1. **Logged-in user:** `request.env.user.email` — reliable, verified email from the authenticated user account.
2. **Anonymous returning visitor:** Falls back to `request.session['mass_mailing_email']` — set previously by `subscribe_to_newsletter()` when the same visitor subscribed on an earlier page visit.
3. **First-time anonymous:** Returns `None` — `is_subscriber` evaluates to `False`.

**L3 — Subscriber query breakdown:**

```python
request.env['mailing.subscription'].sudo().search_count(
    [('list_id', 'in', [int(list_id)]),
     ('contact_id.email', '=', value),   # fname='email' for email type
     ('opt_out', '=', False)])
```

- Uses `mailing.subscription` (not `mailing.contact`) because a contact can be on many lists — this checks per-list opt-out status.
- `opt_out=False` filters out contacts who have unsubscribed from this specific list (not globally).
- `.sudo()` bypasses ACL — the public user lacks read rights on `mailing.subscription`.

**Returns:** `{'is_subscriber': bool, 'value': str|None}`

---

#### `subscribe(list_id, value, subscription_type, **post)` → JSON-RPC

**Route:** `POST /website_mass_mailing/subscribe`
**Flags:** `website=True, auth='public'`

```python
@route('/website_mass_mailing/subscribe', type='jsonrpc', website=True, auth='public')
def subscribe(self, list_id, value, subscription_type, **post):
    try:
        request.env['ir.http']._verify_request_recaptcha_token('website_mass_mailing_subscribe')
    except UserError as e:
        return {'toast_type': 'danger', 'toast_content': str(e)}

    fname = self._get_fname(subscription_type)
    self.subscribe_to_newsletter(subscription_type, value, list_id, fname)
    return {'toast_type': 'success', 'toast_content': _("Thanks for subscribing!")}
```

**L2 — ReCAPTCHA enforcement:**
- Token key: `'website_mass_mailing_subscribe'` — must be registered in `google_recaptcha` configuration.
- Throws `UserError` on failure → caught in JS as `toast_type: 'danger'`.
- If no CAPTCHA is configured at all, `_verify_request_recaptcha_token()` raises `UserError` and blocks all subscriptions — by design, site operators must configure CAPTCHA before enabling subscriptions.

**L3 — Failure modes:**

| Scenario | Result |
|---|---|
| Missing/invalid reCAPTCHA token | `UserError` → danger toast |
| Cloudflare Turnstile token provided | Accepted as alternative CAPTCHA |
| Both CAPTCHA providers configured | reCAPTCHA takes precedence |
| `list_id` does not exist | `subscribe_to_newsletter` creates subscription to list ID 0 — bad data |

---

#### `subscribe_to_newsletter(subscription_type, value, list_id, fname, address_name=None)` — static utility

```python
@staticmethod
def subscribe_to_newsletter(subscription_type, value, list_id, fname, address_name=None):
    ContactSubscription = request.env['mailing.subscription'].sudo()
    Contacts = request.env['mailing.contact'].sudo()

    if subscription_type == 'email':
        name, value = tools.parse_contact_from_email(value)   # RFC-2822 parsing
        if not name:
            name = address_name        # fallback if parsing yielded no display name

    elif subscription_type == 'mobile':
        name = value   # phone number stored as contact name

    # Upsert: check for existing subscription
    subscription = ContactSubscription.search(
        [('list_id', '=', int(list_id)), (f'contact_id.{fname}', '=', value)], limit=1)

    if not subscription:
        # Create contact if not exists
        contact_id = Contacts.search([(fname, '=', value)], limit=1)
        if not contact_id:
            contact_id = Contacts.create({'name': name, fname: value})
        ContactSubscription.create({'contact_id': contact_id.id, 'list_id': int(list_id)})
    elif subscription.opt_out:
        subscription.opt_out = False   # re-subscribe opt-out contact

    # Persist email in session for next page visit
    request.session[f'mass_mailing_{fname}'] = value
```

**L2 — Email parsing (`tools.parse_contact_from_email`):**
Handles the RFC-2822 `"Name <email@example.com>"` format. Extracts the display name and the address separately. If only a bare email is provided, `name` will be empty and `address_name` is used as fallback.

**L2 — Mobile subscription:**
Phone number is used as the contact's `name`. The actual phone value is not validated here — validation would happen via the `mailing.contact` model's field constraints if the `mobile` field type were used (but this module stores it in a generic char-based `name` field).

**L3 — Upsert behavior:**

| State | Action |
|---|---|
| Contact not in list | Creates `mailing.contact` + `mailing.subscription` |
| Contact exists in list, not opted out | No-op (contact already subscribed) |
| Contact exists in list, `opt_out=True` | Sets `opt_out=False` (re-subscribe) |

**L4 — Edge cases and performance:**

- The upsert uses `search()` + `limit=1` rather than `search_count()` — more efficient when the record exists because it returns the actual record.
- Re-subscribing via `opt_out=False` avoids creating a duplicate `mailing.subscription` row for the same contact+list pair — prevents the contact from appearing twice in the same list.
- If the contact already exists (matched by email), no new `mailing.contact` is created — the existing record is reused. This is intentional: the same email = same person = same record across all lists and page sources.
- Both `mailing.subscription` and `mailing.contact` use `.sudo()` — public user lacks write ACL on both models.
- `request.session[f'mass_mailing_{fname}'] = value` — stores the email in session for the `is_subscriber` check on subsequent page visits. The `fname` suffix supports future `mobile` subscription types, though only `email` is currently implemented.

**L4 — `list_id=0` behavior:**
If the snippet's `data-list-id` is left at the default `0` (no list selected in editor), the subscribe creates a subscription to list ID 0, which typically does not exist. The `mailing.subscription` record is created with `list_id=0`. This silently creates bad data — the subscriber is not on any real list. The JS does not validate `list_id` before submitting.

---

#### `_get_fname(subscription_type)` — field name resolver

```python
def _get_fname(self, subscription_type):
    return 'email' if subscription_type == 'email' else ''
```

Currently, only `'email'` maps to a real field. Any other `subscription_type` (e.g., `'mobile'`) returns an empty string, causing the domain to become `('contact_id.', '=', value)` — which is invalid and will cause a SQL error. The `mobile` subscription path is therefore not functional in the current implementation.

---

### `WebsiteNewsletterForm` — extends `website.controllers.form.WebsiteForm`

**File:** `controllers/website_form.py`

#### `_handle_website_form(model_name, **kwargs)` — form builder hook

```python
def _handle_website_form(self, model_name, **kwargs):
    if model_name == 'mailing.contact':
        list_ids = kwargs.get('list_ids')
        if not list_ids:
            return json.dumps({'error': _('Mailing List(s) not found!')})
        list_ids = [int(x) for x in list_ids.split(',')]

        private_list_ids = request.env['mailing.list'].sudo().search([
            ('id', 'in', list_ids), ('is_public', '=', False)
        ])
        if private_list_ids:
            return json.dumps({
                'error': _('You cannot subscribe to the following list anymore : %s',
                           ', '.join(private_list_ids.mapped('name')))
            })
    return super()._handle_website_form(model_name, **kwargs)
```

**L2 — Purpose:**
Intercepts the Website Form Builder's standard handler before it reaches `mailing.contact`. It enforces the `is_public` visibility rule on `mailing.list`: only lists where `is_public = True` can be subscribed to via a public website form.

**L3 — Private list protection:**

| Check | Result |
|---|---|
| `list_ids` absent | `"Mailing List(s) not found!"` error — prevents silent no-op |
| Any `list_ids` element has `is_public=False` | Lists named in error message, form submission rejected |

- Uses `.sudo()` because public user lacks ACL on `mailing.list`.
- The error message lists specific private list names — helps administrators understand why the form failed.
- Standard Website Form field validation and CSRF handling then applies for the remaining form fields.

---

## Frontend Interactions (JavaScript)

### `website_mass_mailing.subscribe` — `public.interactions` registry

**File:** `static/src/interactions/subscribe.js`
**Selector:** `.js_subscribe`
**Registry:** `public.interactions`

The `Subscribe` class is an Odoo 19 public interaction. It attaches to any `.js_subscribe` element and provides the subscription UI logic.

#### `willStart()` — subscriber status check

```javascript
const data = await this.waitFor(rpc(
    '/website_mass_mailing/is_subscriber',
    { 'list_id': this._getListId(), 'subscription_type': inputName },
))
this._updateView(data)
await this._recaptcha.loadLibs()
```

**L3 — Fires on every page load:**
The interaction `willStart()` runs on every page load for every `.js_subscribe` element in the DOM. Each fires an `is_subscriber` RPC. With multiple newsletter snippets on one page, this creates N concurrent `search_count()` queries.

**L3 — `_updateView(data)` behavior:**

```javascript
_updateSubscribeControlsStatus(!!data.is_subscriber)
// ...
valueInputEl.value = data.value || ''
// Compat: remove d-none for DBs with old button saved with it.
this.el.classList.remove('d-none')
```

If subscribed: form input is disabled, "Thanks" message shown, subscribe button disabled.
If not subscribed: form shown, reCAPTCHA/Turnstile widget rendered alongside button.

#### `onSubscribeClick()` — subscription flow

```
Client-side email regex validation
  → ReCaptcha/Turnstile token fetch
  → RPC /website_mass_mailing/subscribe with token + form data
  → toast notification (success or danger)
  → If modal: auto-close Bootstrap modal
```

**L2 — Client-side validation (UX only):**
```javascript
if (inputName === 'email' && isVisible(input) && !input.value.match(/.+@.+/)) {
    this.el.classList.add('o_has_error')
    this.el.querySelector('.form-control').classList.add('is-invalid')
    return
}
```
Simple regex `/.+@.+/` — avoids a server round-trip for obviously malformed input. Server also validates via `mailing.contact.email` field constraint.

**L2 — ReCAPTCHA/Turnstile token gathering:**

```javascript
const tokenObj = await this.waitFor(this._recaptcha.getToken('website_mass_mailing_subscribe'))
// ...
rpc('/website_mass_mailing/subscribe', {
    ...(tokenObj.token ? { recaptcha_token_response: tokenObj.token } : {}),
    turnstile_captcha: this.el.parentElement.querySelector('input[name="turnstile_captcha"]')?.value,
})
```

Both reCAPTCHA and Turnstile tokens are collected. Server's `_verify_request_recaptcha_token` handles reCAPTCHA first; Turnstile is accepted as fallback if reCAPTCHA fails.

**L2 — `_getListId()` — inconsistent resolution:**

```javascript
return this.el.closest('section[data-list-id]')?.dataset.listId || this.el.dataset.listId
```

| Snippet | List ID location |
|---|---|
| `s_newsletter_block` | `data-list-id` on outer `<section>` |
| `s_newsletter_popup` | `data-list-id` on inner form element |
| `s_newsletter_box`, `s_newsletter_centered`, `s_newsletter_grid` | `data-list-id` on section |
| Inline form | Falls back to own `data-list-id` |

The TODO comment in the source acknowledges this inconsistency — the popup stores the ID on the inner form while others store it on the section.

#### Popup auto-close on success

```javascript
const modalEl = this.el.closest('.o_newsletter_modal')
if (modalEl) {
    window.Modal.getOrCreateInstance(modalEl).hide()
}
```
Closes the Bootstrap modal programmatically after successful subscription. If the form is not inside a modal, this is a no-op.

---

### `website_mass_mailing.popup` — extends `@website/interactions/popup/popup`

**File:** `static/src/interactions/popup.js`
**Patches:** `Popup` prototype from `@website/interactions/popup/popup`

#### `canShowPopup()` — suppress for already-subscribed users

```javascript
if (this.el.classList.contains("o_newsletter_popup")
    && this.el.querySelector("input.js_subscribe_value, input.js_subscribe_email")?.disabled
) {
    return false
}
return super.canShowPopup(...arguments)
```

**L4 — Timing issue:**
The `Popup` interaction's `canShowPopup()` runs during the popup's own `willStart()`. The `Subscribe` interaction's `willStart()` (which disables the input when `is_subscriber=True`) may fire in the same frame. Whether suppression works on the current page load depends on interaction initialization order — the popup may already have decided to show before the input is disabled. The suppression is reliable on **subsequent page loads**.

**L4 — Why check `disabled` attribute:**
The `Subscribe` interaction sets `input.disabled = true` as part of `_updateSubscribeControlsStatus(isSubscriber=True)`. The popup uses this DOM state as a proxy for "already subscribed" — no separate state management needed.

#### `canBtnPrimaryClosePopup()` — prevent subscribe button from closing modal

```javascript
if (primaryBtnEl.classList.contains("js_subscribe_btn")) {
    return false
}
return super.canBtnPrimaryClosePopup(...arguments)
```

**L3 — UX intent:** The subscribe button inside the modal is the primary CTA. Clicking it should trigger subscription, not dismiss the modal. This override intercepts the generic popup close logic.

---

### `website_mass_mailing.fix_newsletter_list_class` — edit-mode migration helper

**File:** `static/src/interactions/fix_newsletter_list_class.edit.js`
**Registry:** `public.interactions.edit`
**Selector:** `.s_newsletter_subscribe_form:not(.s_subscription_list), .s_newsletter_block`

```javascript
dynamicContent = {
    _root: {
        "t-att-class": () => ({ s_newsletter_list: true }),
    },
}
```

**L4 — Historical context (pre-16.0 upgrade path):**
Prior to Odoo 16.0, newsletter snippets did not carry the `s_newsletter_list` CSS class. This class is required by the JS interactions to locate form elements. Instead of a database migration script, this edit-mode interaction dynamically adds the class in the website builder's editor iframe.

The class is only applied in edit mode (registered in `public.interactions.edit` — only loaded in the editor iframe). Permanent migration should ideally be done via an upgrade script. The TODO in the source explicitly says this should be replaced with a real upgrade script.

---

## Snippet Templates

All templates defined in `views/snippets_templates.xml` and `views/snippets/s_newsletter_benefits_popup.xml`. Each overrides a hook from `mass_mailing` or `website`.

| Snippet ID | Name | Default `data-list-id` | Notes |
|---|---|---|---|
| `s_newsletter_subscribe_form` | Newsletter | `0` | Inline email form; `.js_subscribe` attaches here |
| `s_newsletter_block` | Newsletter Block | `0` | Full-width section: heading + form |
| `s_newsletter_box` | Newsletter Box | `0` | Card with image + form |
| `s_newsletter_centered` | Newsletter Centered | `0` | Centered card layout |
| `s_newsletter_grid` | Newsletter Grid | `0` | Grid with image columns |
| `s_newsletter_subscribe_popup` | Newsletter Popup | `0` | Modal, `data-show-after="5000"`, `data-display="afterDelay"` |
| `s_newsletter_benefits_popup` | Newsletter Benefits | `0` | Modal with benefits list + SVG illustration |
| `s_newsletter_block_form_template` | (form editor, internal use) | — | Full multi-field form: name/email/lists/consent |

**Common CSS class:** `s_newsletter_list` — required by JS interactions for element discovery.

**`data-list-id` default `0`:** Designer must set a real `mailing.list` ID in the website editor. With `0`, subscriptions are created with `list_id=0` — bad data.

**`thank_you_message` variable:** The inline form snippet accepts a `thank_you_message` template variable to customize the post-subscription message per snippet instance. Variants like `s_newsletter_box`, `s_newsletter_grid` set custom messages.

---

## Form Builder Integration — `mailing.contact` as Website Form Model

**File:** `data/ir_model_data.xml`

```xml
<record id="mass_mailing.model_mailing_contact" model="ir.model">
    <field name="website_form_key">create_mailing_contact</field>
    <field name="website_form_access">True</field>
    <field name="website_form_label">Subscribe to Newsletter</field>
</record>

<function model="ir.model.fields" name="formbuilder_whitelist">
    <value>mailing.contact</value>
    <value eval="['name','first_name','last_name','company_name','email','list_ids','country_id','tag_ids']"/>
</function>
```

**Form builder whitelist fields:**

| Field | Type | Form Editor Behavior |
|---|---|---|
| `name` | `char` | Required; shown as single field unless `is_name_split_activated()=True` |
| `first_name` | `char` | Shown only when `mailing.contact.is_name_split_activated()` is True |
| `last_name` | `char` | Shown only when `mailing.contact.is_name_split_activated()` is True |
| `company_name` | `char` | Preset from partner's company |
| `email` | `char` | Model-required; unique constraint on `mailing.contact` |
| `list_ids` | `many2many:mailing.list` | Shown as multi-select of `is_public=True` lists only |
| `country_id` | `many2one:res.country` | Preset from partner's country |
| `tag_ids` | `many2many:mailing.tag` | Free-form tagging |

**L3 — `is_name_split_activated()` check in form template:**

```xml
<t t-if="request.env['mailing.contact']._is_name_split_activated()">
    <!-- first_name + last_name side by side -->
</t>
<t t-else="">
    <!-- single name field -->
</t>
```

Controls whether the contact form uses a split name or a combined `name` field. This is a computed flag from the `mass_mailing` module.

**L3 — `list_ids` filtering in form editor:**
`mass_mailing_form_editor.js` registers `create_mailing_contact` in `website.form_editor_actions` with `list_ids` as a `many2many` relation to `mailing.list`. The Website Form Builder only shows records accessible via the current user's ACL — since this form is public, it effectively filters to `is_public=True` lists.

---

## Security

**File:** `security/ir.model.access.csv`

```
access_mailing_list_website_designer,mass_mailing.model_mailing_list,website.group_website_designer,1,0,0,0
```

**Single ACL row:** Website designers (`website.group_website_designer`) get **read-only** access to `mailing.list`. They can view available lists in the editor but cannot modify them.

**Public user — no direct ACL:**
No ACL entry for `public` or `anonymous` on `mailing.list` or `mailing.contact`. All public-facing queries use `.sudo()` to bypass ACL entirely.

**L4 — Security implications of `.sudo()` bypass:**

- `ir.rule` record-level security on `mailing.list` and `mailing.subscription` is skipped for public operations.
- All unauthenticated website visitors can create `mailing.contact` records and `mailing.subscription` records.
- ReCAPTCHA is the primary anti-abuse mechanism — without it, the subscribe endpoint is an open contact creation endpoint.
- If `google_recaptcha` is not configured, `_verify_request_recaptcha_token()` raises `UserError` and all subscriptions are blocked — this is the intended safety default.

**L4 — ReCAPTCHA token single-use:**
ReCAPTCHA tokens are consumed server-side. If a subscription request fails network-side after the token is generated, the client must obtain a fresh token on retry.

---

## Session State

| Key | Set by | Purpose |
|---|---|---|
| `mass_mailing_email` | `subscribe_to_newsletter()` | Persist anonymous visitor's email for `is_subscriber` check |
| `mass_mailing_fname` | `subscribe_to_newsletter()` | Future-proof for non-email subscription types (currently unused) |

---

## Performance Considerations

1. **`is_subscriber` fires N times per page load** — one RPC per `.js_subscribe` element. Each is a `search_count()` with a domain on `contact_id.email`. The `limit=1` on count prevents full scanning but a DB query is still incurred per snippet.

2. **No subscriber status caching.** The `is_subscriber` result is not cached in session or browser storage — it re-queries on every page load, even for the same logged-in user with a stable email.

3. **ReCAPTCHA token per attempt.** Token is single-use. If the server rejects the subscription (e.g., network error after token generated), the visitor must complete CAPTCHA again on retry.

4. **`.sudo()` bypasses ORM security entirely.** The public-facing queries skip record rules — this is necessary but removes all per-record access control for these operations.

5. **`list_id=0` data integrity risk.** When a snippet's `data-list-id` is left at `0` (designer forgot to configure), subscriptions are created with `list_id=0`. No validation prevents this at form submission time.

---

## Odoo 18 → 19 Changes

| Area | Change |
|---|---|
| Public interactions framework | `Subscribe` class uses Odoo 19's new `public.interactions` registry. Pre-19 implementations used QWeb widgets or inline JS. |
| Cloudflare Turnstile support | `google_recaptcha` gained Turnstile support in Odoo 19. The JS interaction checks `session.turnstile_site_key` to render Turnstile as an alternative to reCAPTCHA. |
| `auth='public'` on JSON-RPC | Formalized in Odoo 19 for website-scoped JSON-RPC routes — used here for the subscribe and subscriber-check endpoints. |
| `is_name_split_activated()` form builder | `mailing.contact` gained the ability to split `name` into `first_name` + `last_name` in Odoo 18/19. The form editor integration conditionally renders name fields based on this flag. |

---

## Test Coverage

**File:** `tests/test_snippets.py`

```python
def test_snippet_newsletter_popup(self):
    self.start_tour("/", "snippet_newsletter_popup_edition", login='admin')
    self.start_tour("/", "snippet_newsletter_popup_use", login=None)
    mailing_list = self.env['mailing.list'].search([], limit=1)
    emails = mailing_list.contact_ids.mapped('email')
    self.assertIn("hello@world.com", emails)

def test_snippet_newsletter_block_with_edit(self):
    # Admin email unsubscribed from all lists first
    # Then tour edits the block, changes list, and re-subscribes
    self.start_tour(self.env['website'].get_client_action_url('/'),
                   "snippet_newsletter_block_with_edit", login='admin')
```

Tests cover: popup snippet in edit mode, popup in use mode, and block snippet with inline edit. The `test_snippet_newsletter_popup` test verifies the actual `mailing.contact` email `"hello@world.com"` is created in the database after the tour completes.

---

## Key Files Summary

| File | Purpose |
|------|---------|
| `__manifest__.py` | Module declaration, dependency chain, asset bundle registration |
| `models/res_company.py` | Extends `_get_social_media_links()` to read social fields from website record |
| `controllers/main.py` | JSON-RPC: `is_subscriber`, `subscribe`, `subscribe_to_newsletter` static method |
| `controllers/website_form.py` | Form builder hook: private list guard for `mailing.contact` submissions |
| `data/ir_model_data.xml` | `mailing.contact` as website form model with field whitelist |
| `security/ir.model.access.csv` | Read-only ACL for website designers on `mailing.list` |
| `views/snippets_templates.xml` | All snippet template definitions and hook overrides |
| `views/snippets/s_newsletter_benefits_popup.xml` | Benefits popup template |
| `static/src/interactions/subscribe.js` | Public interaction: subscriber check + subscription flow with reCAPTCHA |
| `static/src/interactions/popup.js` | Popup suppression for already-subscribed users |
| `static/src/interactions/fix_newsletter_list_class.edit.js` | Migration helper for pre-16.0 snippet upgrade |
| `static/src/js/mass_mailing_form_editor.js` | Form editor field configuration for `create_mailing_contact` |
| `static/src/xml/website_mass_mailing.xml` | QWeb template for modal wrapper in edit mode |
| `static/src/scss/website_mass_mailing.scss` | Newsletter form input sizing (responsive max-width) |
| `static/src/scss/website_mass_mailing_popup.scss` | Newsletter modal styling (close button positioning, color) |
| `static/src/scss/website_mass_mailing_edit_mode.scss` | Edit mode visibility overrides for subscribe form |

---

## Cross-Module Integration Map

```
website_mass_mailing
├── website
│   └── website routing, session, auth='public', WebsiteForm controller
├── mass_mailing
│   ├── mailing.list          (is_public check, read ACL for designers)
│   ├── mailing.contact       (form model, create, upsert)
│   └── mailing.subscription  (opt_out status, subscriber check, create)
├── google_recaptcha
│   ├── server: _verify_request_recaptcha_token()
│   └── client: ReCaptcha class, Turnstile fallback
└── website_cf_turnstile (optional, loaded via dynamic import)
    └── Cloudflare Turnstile as alternative CAPTCHA
```

---

## Related Documentation

- [[Modules/mass_mailing]] — `mailing.list`, `mailing.contact`, `mailing.subscription` model details
- [[Modules/Website]] — `website` routing, session management, public auth
- [[Core/API]] — `@route` decorators, `auth='public'`, `website=True` flags
- [[Modules/google_recaptcha]] — CAPTCHA configuration and token verification
