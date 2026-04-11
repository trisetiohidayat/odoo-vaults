---
tags: [odoo, odoo17, module, iap, in-app-purchase, credits, api]
research_depth: medium
---

# IAP (In-App Purchase) Module — Deep Reference

**Source:** `addons/iap/models/`

## Overview

The IAP framework enables Odoo to charge for metered API services. Services (SMS sending, email validation, phone enrichment, OCR, lead enrichment, etc.) consume credits from an IAP account. Odoo SaaS and on-premise deployments use IAP to provide paid API services without requiring manual billing integration.

## Architecture

```
Service Module (e.g., sms) → iap.authorize() → IAP service endpoint
                                        ↓
                               iap.account (per-service)
                                        ↓
                              Credit deduction per call
```

## Key Models

### iap.account — Service Account

**File:** `iap_account.py`

One record per service per company. Stores authentication tokens and credit balance info.

| Field | Type | Description |
|-------|------|-------------|
| `name` | Char | Account display name |
| `service_name` | Char (readonly) | Service identifier: `sms`, `reveal`, `partner_autocomplete` |
| `account_token` | Char | UUID token used as API key for this service (auto-generated) |
| `company_ids` | Many2many res.company | Companies using this account |
| `account_info_id` | Many2one (compute/inverse) | Latest IAP account info record |
| `account_info_ids` | One2many → `iap.account.info` | All balance/info records fetched from server |
| `balance` | Char (compute) | Display string: "{credits} {unit_name}" |
| `warn_me` | Boolean | Email alert when balance below threshold |
| `warning_threshold` | Float | Threshold for balance alert |
| `warning_email` | Char | Email address for balance alerts |
| `show_token` | Boolean | Toggle to reveal/hide account token in UI |

### iap.account.info — Balance Info (Transient)

Transient model fetched from the IAP server. Not stored long-term — used to display current balance.

| Field | Type | Description |
|-------|------|-------------|
| `account_id` | Many2one → `iap.account` | Parent account |
| `account_token` | Char | Token (from server) |
| `balance` | Float | Current credit balance |
| `account_uuid_hashed` | Char | Server-side UUID hash |
| `service_name` | Char | Service identifier |
| `description` | Char | Service description |
| `warn_me` | Boolean | Alert preference |
| `warning_threshold` | Float | Threshold |
| `warning_email` | Char | Alert email |
| `unit_name` | Char | "Credits" by default |

## Core Methods

### `iap.account.get(service_name, force_create=True)` — Account Resolution

Finds or creates the IAP account for a service. Key logic:

```python
domain = [
    ('service_name', '=', service_name),
    '|', ('company_ids', 'in', self.env.companies.ids), ('company_ids', '=', False)
]
accounts = self.search(domain, order='id desc')
# Prefer accounts scoped to current companies
# Prefer accounts with explicit company_ids
# Create new if none found and force_create=True
```

During concurrent requests, it uses a separate cursor to create the account in a transaction-safe way, then syncs the `account_token` back to the original cursor's cache.

### `get_services()` — Fetch All Balances

Called when viewing the IAP account tree view. Makes an RPC call to `https://iap.odoo.com/iap/services-token` with all known account tokens. Creates `iap.account.info` records for each service.

### `get_credits(service_name)` — Get Balance

RPC call to `/iap/1/balance` returning current credit count. Returns `-1` on `AccessError` (network/permission issues). Used by services to check balance before making a request.

### `get_credits_url(service_name, ...)` — Buy Credits URL

Builds the URL for the IAP credit purchase page:
```
https://iap.odoo.com/iap/1/credit?dbuuid=...&service_name=sms&account_token=...&credit=5
```

## Credit Management Flow

### Service (e.g., sms.mass_mailing) Usage

```python
# 1. Authorize credit before API call
account = self.env['iap.account'].get('sms')
# Internally: iap.authorize(env, 'sms', credit_needed)

# 2. Make the API call
result = iap_jsonrpc('/sms/send', params={...})

# 3. If call fails mid-way, credits not consumed
# 4. On success, service records the credit use
```

### `iap.authorize()` / `iap.cancel()`

The `iap` module provides `authorize()` and `cancel()` context helpers for reliable credit management. Services call these to hold credits before making risky external API calls, and cancel if the operation fails.

## Enrich API

**File:** `iap_enrich_api.py`

Abstract model used by CRM for lead enrichment. The `IapEnrichAPI` class wraps the IAP call for enrichment:

```python
@api.model
def _request_enrich(self, lead_emails):
    # lead_emails: dict{lead_id: email}
    params = {'domains': lead_emails}
    return self._contact_iap(
        '/iap/clearbit/1/lead_enrichment_email',
        params
    )
```

Uses the `reveal` IAP service (with account token and dbuuid). Raises `InsufficientCreditError` if balance is zero.

## IAP Service Discovery

When the IAP account form is opened in tree view, `get_view` with `view_type='tree'` calls `get_services()` which fetches all services and creates `iap.account.info` records. This populates the balance column.

## Neutralized Database Handling

During account creation, if `database.is_neutralized` config parameter is set, the `account_token` is suffixed with `+disabled`. This prevents a neutralized database from making real IAP calls in a test environment.

## Common IAP Services

| Service Name | Used By | Description |
|-------------|---------|-------------|
| `sms` | `sms` module | SMS sending |
| `partner_autocomplete` | `partner_autocomplete` | Company/contact data enrichment |
| `reveal` | `crm_iap_enrich` | Lead enrichment from Clearbit |
| `email_validation` | Various | Email deliverability check |
| `ocr` | Document OCR | Invoice/scanned document OCR |
| `leet` | CRM | Lead scoring/enrichment |

## See Also

- [[Modules/sms]] — SMS sending
- [[Modules/crm_iap_enrich]] — CRM lead enrichment via IAP
- [[Modules/mail]] — email infrastructure