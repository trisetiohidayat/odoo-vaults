---
Module: iap_mail
Version: Odoo 18
Type: Integration
Tags: #odoo18, #iap, #mail, #integration
---

# IAP Mail Module (`iap_mail`)

## Overview

**Category:** Hidden/Tools
**Depends:** `iap`, `mail`
**Auto-install:** Yes
**License:** LGPL-3

The `iap_mail` module bridges the IAP (In-App Purchase) infrastructure and the mail/messaging layer. It performs three distinct roles:

1. **Extends `iap.account`** with `mail.thread` (chatter), so IAP account status changes are tracked and users can receive notifications directly on the account record.
2. **Provides the `enrich_company` QWeb email template** used by `crm_iap_enrich` to post enriched company data as a message on CRM leads.
3. **Provides a front-end notification service** (`iapNotification`) that displays IAP status messages (success, error, no-credit) in the Odoo web client via the bus service.

This module is the shared IAP notification layer for all IAP-aware modules — not just CRM.

## How IAP Enhances Mail

IAP services interact with the mail layer in two ways:

- **IAP status notifications** — When IAP operations succeed, fail, or run out of credits, the `iap.account` model sends structured notifications via `bus.bus`. The `iapNotification` JS service subscribes to the `iap_notification` bus channel and displays in-app notifications.
- **Company enrichment template** — `crm_iap_enrich` posts enriched company data (logo, industry, employee count, revenue, social links, technology stack) onto CRM leads using the `iap_mail.enrich_company` QWeb mail template.

## Models Extended

### `iap.account` — Extended by `iap_mail`

**File:** `models/iap_account.py`
**Inheritance:** `_inherit = ['iap.account', 'mail.thread']`

The base `iap.account` model (from module `iap`) manages IAP service credentials and credit balances. `iap_mail` adds `mail.thread` to enable:
- Full chatter on IAP account forms (messages, followers, tracking)
- Automatic notification to followers when account state changes
- Audit trail for manual configuration changes

#### Fields (from base `iap.account`, augmented by tracking)

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Account name (defaults to service name on create) |
| `service_id` | Many2one `iap.service` | The IAP service this account is for |
| `service_name` | Char (related) | Technical name of the service (e.g. `reveal`, `partner_autocomplete`) |
| `service_locked` | Boolean | If True, the service cannot be edited (account exists on IAP server) |
| `description` | Char (related) | Human-readable service description |
| `account_token` | Char | UUID-based authentication token for this service |
| `company_ids` | Many2many `res.company` | Companies this account applies to (False = all) |
| `balance` | Char (readonly) | Current credit balance, fetched from IAP server on `web_read` |
| `warning_threshold` | Float | Email alert threshold (triggers warning when balance falls below) |
| `warning_user_ids` | Many2many `res.users` | Recipients of low-credit email alerts |
| `state` | Selection | `banned`, `registered`, `unregistered` — synced from IAP server |

#### Methods

**`_send_success_notification(message, title=None)`** — `@api.model`
Sends a success notification via the bus to the current user.
```python
self._send_status_notification(message, 'success', title=title)
```

**`_send_error_notification(message, title=None)`** — `@api.model`
Sends an error/danger notification via the bus.
```python
self._send_status_notification(message, 'danger', title=title)
```

**`_send_no_credit_notification(service_name, title)`** — `@api.model`
Sends a special "no credit" notification that includes a **"Buy more credits"** link:
```python
params = {
    'title': title,
    'type': 'no_credit',
    'get_credits_url': self.env['iap.account'].get_credits_url(service_name),
}
self.env.user._bus_send("iap_notification", params)
```
The `get_credits_url()` method constructs a URL to the IAP credit purchase page with the database UUID, account token, and service name as query parameters.

**`_send_status_notification(message, status, title=None)`** — `@api.model`
Core bus notification dispatcher. Serialises params and sends via `bus.bus`:
```python
params = {'message': message, 'type': status}
if title is not None:
    params['title'] = title
self.env.user._bus_send("iap_notification", params)
```

#### Tracking

Three fields have `tracking=True` on the extended form, so changes to `company_ids`, `warning_threshold`, and `warning_user_ids` are automatically logged as mail messages on the IAP account record.

## QWeb Templates

### `iap_mail.enrich_company`

**File:** `data/mail_templates.xml`

This is the QWeb email template used by `crm_iap_enrich` to post enriched company information as a note message on CRM leads. It renders a rich card with:

- **Company name** with social media icon links (Twitter/X, Facebook, LinkedIn, Crunchbase)
- **Logo** (right-aligned, 80px max width)
- **Description/bio** text
- **Industry information** — `sector_primary`, `industry`, `industry_group`, `sub_industry` rendered as tags
- **Founded year**, **company type**, **employee count**, **estimated annual revenue**
- **Phone numbers** — rendered as clickable `tel:` links
- **Email addresses** — rendered as clickable `mailto:` links
- **Timezone**
- **Technology stack** — each technology rendered as a tag
- **Twitter bio** with follower count and profile link

The template receives `flavor_text` as a parameter (set to `"Lead enriched based on email address"` by `crm_iap_enrich`).

## Views

### Form Extension: `iap.account`

**File:** `views/iap_views.xml`

Extends the base `iap.account` form view (`iap.iap_account_view_form`) by adding `<chatter/>` after the sheet. This enables the full messaging pane (followers, messages, activities) on the IAP account form.

## Frontend (JavaScript)

### Service: `iapNotification`

**File:** `static/src/js/services/iap_notification_service.js`
**Odoo Module:** `odoo` (OWL-based)

Registered in `web.core` registry category `"services"` as `"iapNotification"`.

**Bus subscription:**
```javascript
bus_service.subscribe("iap_notification", (params) => {
    if (params.type == "no_credit") {
        displayCreditErrorNotification(params);
    } else {
        displayNotification(params);
    }
});
bus_service.start();
```

**Two notification paths:**

| Type | Display | Content |
|------|---------|---------|
| `success` / `danger` / other | Standard `notification.add()` | `params.message` as HTML, `params.title` |
| `no_credit` | Danger banner with CTA | "Buy more credits" button linking to `params.get_credits_url` |

The "Buy more credits" link is constructed server-side by `iap.account.get_credits_url()` and embedded in the notification as a styled `<a>` tag.

## Static Assets

- `static/src/js/services/iap_notification_service.js` — Frontend bus listener and notification display
- `static/src/scss/iap_mail.scss` — Styles: `.o_partner_autocomplete_enrich_info i { min-width: fit-content; }` (prevents icon cropping)
- `static/src/scss/iap_mail.dark.scss` — Dark mode overrides

## L4: IAP Mail Service Architecture

```
iap account low credit / operation complete
        |
        v
iap.account._send_*_notification()
        |
        v
bus.bus._sendone()  --->  browser bus (websocket)
        |
        v
iapNotification service (JS)
        |
        +-- type != "no_credit" --> notification.add() [success/danger]
        |
        +-- type == "no_credit" --> notification.add() [danger + "Buy credits" link]
```

The IAP notification system is entirely decoupled from email — these are **in-app notifications** delivered via the Odoo bus (WebSocket). They do not generate outbound emails. The outbound low-credit **email alerts** (when `balance < warning_threshold`) are sent by the IAP server itself, using the `warning_user_ids` email list and `warning_threshold` stored on `iap.account`.

**Credit purchase URL construction:**
```
/iap/1/credit?dbuuid=<uuid>&service_name=<svc>&account_token=<tok>&credit=<amt>
```

This URL is generated by `iap.account.get_credits_url()` and is the target of the "Buy more credits" button shown when IAP operations fail due to insufficient credits.
