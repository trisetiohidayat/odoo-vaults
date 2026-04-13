---
tags: [odoo, odoo17, module, iap, crm, lead-enrichment, reveal]
research_depth: medium
---

# CRM IAP Enrich — Lead Enrichment via Clearbit / IAP

**Source:** `addons/crm_iap_enrich/models/`

## Overview

Automatically enriches CRM leads with company information (name, address, phone, country, state) based on the lead's email domain. Uses the IAP `reveal` service (Clearbit-powered) to look up company data. Enrichment runs automatically on new leads via cron, or manually via a button on the lead form. This is the primary lead acquisition intelligence module in Odoo CRM.

## Key Models

### crm.lead — Enrichment Extension

**File:** `crm_lead.py`

Extends `crm.lead` with enrichment tracking and logic.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `iap_enrich_done` | Boolean | Whether enrichment has been attempted |
| `show_enrich_button` | Boolean (compute) | Show "Enrich Lead" button on form |

#### Computed Button Visibility (`_compute_show_enrich_button`)

Button is shown only when:
- Lead is `active` (not lost)
- `email_from` is present
- Email is not marked `incorrect`
- Not already enriched (`iap_enrich_done = False`)
- No `reveal_id` exists
- Probability is not 100% (won)

#### `iap_enrich(from_cron=False)` — Main Enrichment Method

Batch processing with per-lead error isolation:

1. **Lock rows** — `SELECT ... FOR UPDATE NOWAIT` prevents concurrent processing
2. **Filter leads** — skip won (probability=100), already enriched, no email, generic domain
3. **Generic domain check** — uses `iap_tools._MAIL_PROVIDERS` to skip gmail.com, hotmail.com, etc.
4. **Batch API call** — calls `iap.enrich.api._request_enrich({lead_id: email_domain, ...})` with up to 50 leads per batch
5. **Commit per batch** — avoids losing credits on failure; each batch commits independently

**Error Handling:**
- `InsufficientCreditError` → sends no-credit notification, stops processing remaining batches
- Generic `Exception` → sends error notification, logs, continues to next batch
- `OperationalError` (lock timeout) → skips batch, continues

**Manual vs Cron mode:**
- Manual: shows toast notifications for success/error/no-credit
- Cron: silent (background process), no user notifications

#### `_iap_enrich_from_response(iap_response)` — Apply Enrichment Data

Maps IAP response data to lead fields:

| IAP Field | Lead Field |
|-----------|-----------|
| `name` | `partner_name` |
| `clearbit_id` | `reveal_id` |
| `location` | (used in message) |
| `city` / `postal_code` | `city` / `zip` |
| `phone_numbers[0]` | `phone` |
| `phone_numbers[1]` | `mobile` |
| `country_code` | `country_id` (lookup by code) |
| `state_code` | `state_id` (lookup by code + country) |

Only writes a field if the lead currently has no value (non-destructive — never overwrites existing data).

Posts a `iap_mail.enrich_company` message on the lead chatter with enriched data and a flavor text.

#### Automatic Cron Triggering

`create()` checks `crm.iap.lead.enrich.setting` config parameter:
- If `'auto'` — triggers `ir_cron_lead_enrichment` immediately after lead creation
- If `'manual'` — no auto-enrichment; user must click the button

#### `_iap_enrich_leads_cron()` — Scheduled Enrichment

Runs hourly. Processes leads:
- Not enriched (`iap_enrich_done = False`)
- No `reveal_id`
- Not won (`probability < 100` or not set)
- Created in the last hour

#### Lead Merge Field

`_merge_get_fields_specific()` includes `iap_enrich_done` in lead merge: if any lead in the merge has enrichment done, the merged lead is marked as enriched.

### res.config.settings — Enrichment Mode Toggle

**File:** `res_config_settings.py`

| Field | Description |
|-------|-------------|
| `lead_enrich_auto` | `'auto'` or `'manual'` — controls the `crm.iap.lead.enrich.setting` config parameter |

Setting this to `'auto'` activates `ir_cron_lead_enrichment`; `'manual'` deactivates it.

## See Also

- [Modules/iap](iap.md) — IAP account and credit framework
- [Modules/crm](crm.md) — CRM lead model
- [Modules/iap_mail](iap_mail.md) — notification helpers for IAP operations
- [Modules/crm_iap_mine](crm_iap_mine.md) — lead mining / prospecting via IAP