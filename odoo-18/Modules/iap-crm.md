---
Module: iap_crm
Version: Odoo 18
Type: Integration
Tags: #odoo18, #iap, #crm, #integration
---

# IAP CRM Module (`iap_crm`)

## Overview

**Category:** Hidden/Tools
**Depends:** `crm`, `iap_mail`
**Auto-install:** Yes
**License:** LGPL-3

The `iap_crm` module is a thin integration bridge between the **IAP (In-App Purchase)** infrastructure and the **CRM** module. Its sole purpose is to add the `reveal_id` technical field to `crm.lead`, which is populated by IAP reveal services (Clearbit-based company enrichment and visitor-to-lead conversion).

This module is always installed automatically when both `crm` and `iap_mail` are present — it has no UI and no business logic of its own.

## Relationship to CRM IAP Services

`iap_crm` provides the shared `reveal_id` field used by two upstream modules:

```
crm_iap_enrich             → website_crm_iap_reveal
         \                       /
          → reveal_id field ← –
                |
           crm.lead
```

- **`crm_iap_enrich`** — Enriches existing CRM leads with company data (name, phone, address, logo, social links) based on the lead's email domain. Uses the IAP `reveal` service. Populates `reveal_id` with the Clearbit company ID.
- **`website_crm_iap_reveal`** — Automatically generates new CRM leads from website visitor data (GeoIP-based). Also uses the IAP `reveal` service. Stores the Clearbit person ID in `reveal_id` for deduplication.

Both modules write to `crm.lead.reveal_id`; `iap_crm` is the module that declares the field.

## How IAP Credit Consumption Works in CRM

CRM IAP services consume credits from the **IAP Reveal service** (`reveal`):

1. **Reveal Rule Trigger** (`website_crm_iap_reveal`) — A visitor lands on a tracked website page. GeoIP + industry/role/seniority filters in `crm.reveal.rule` are evaluated. If matched, a request is sent to `https://iap-services.odoo.com` with the visitor's data.
2. **Credit Deduction** — Each successful reveal (new lead created or contact tracked) consumes **1 credit per contact**. Extra contacts above `extra_contacts` each consume an additional credit.
3. **Lead Enrichment** (`crm_iap_enrich`) — A cron job (`ir_cron_lead_enrichment`) triggers enrichment for new leads that have an email address but no `reveal_id` and no `iap_enrich_done`. It batches leads in groups of 50 and calls `iap.enrich.api._request_enrich()`.
4. **Insufficient Credit Handling** — If `InsufficientCreditError` is raised, a "no credit" notification is sent to configured users via `iap.account._send_no_credit_notification()`. The `_MAIL_PROVIDERS` denylist (gmail.com, yahoo.com, etc.) prevents wasted credit on generic domains.
5. **Enrich Domain Blocking** — Email domains matching `iap_tools._MAIL_PROVIDERS` are skipped immediately, with a note posted on the lead.

## Models Extended or Created

### `crm.lead` — Extended by `iap_crm`

**File:** `models/crm_lead.py`
**Inheritance:** `_inherit = 'crm.lead'`
**No new model file** — this module only adds one field and one mixin method to the base CRM lead.

#### Fields

| Field | Type | Description |
|-------|------|-------------|
| `reveal_id` | Char (index: `btree_not_null`) | Technical ID of the IAP reveal request that created or enriched this lead. Populated by Clearbit (via `website_crm_iap_reveal`) with the person or company ID. Used for deduplication — prevents creating duplicate leads for the same revealed contact. Also consumed by `crm_iap_enrich` as a marker that the lead came from IAP reveal. |

#### Methods

**`_merge_get_fields()`** — Extends the CRM lead merge mixin

```python
def _merge_get_fields(self):
    return super(Lead, self)._merge_get_fields() + ['reveal_id']
```

When multiple CRM leads are merged (using the lead merge wizard), `reveal_id` is included as a tracked field — if any merged lead had a `reveal_id`, the resulting lead retains it.

---

## L4: How CRM IAP Services Are Connected

The full CRM IAP picture spans three modules:

```
website_crm_iap_reveal     crm_iap_enrich
         |                       |
   crm.reveal.rule         iap_enrich_cron
   website visitor         _request_enrich()
   person reveal           company enrich
         |                       |
         +---- crm.lead ----+----+
              reveal_id          |
              iap_enrich_done    |
                                 |
                    iap_mail (enrich_company template)
```

**Credit flow:**
- `website_crm_iap_reveal` uses `iap_tools.iap_jsonrpc()` to call `reveal` service at `iap-services.odoo.com`
- `crm_iap_enrich` uses `iap.enrich.api` (the `reveal` service) to look up company data by email domain
- Both services consume credits from the database's IAP account for the `reveal` service
- Balance is shown on `iap.account` form (via `iap_mail`'s chatter extension)
- No-credit notifications route through `iap.account._send_no_credit_notification()` → `bus.bus` → `iapNotification` JS service

**Key deduplication logic (from `website_crm_iap_reveal`):**

```python
already_created_lead = self.env['crm.lead'].search_count(
    [('reveal_id', '=', result['clearbit_id'])], limit=1)
```

A lead is only created if no existing lead has the same `reveal_id` (Clearbit person ID). This prevents duplicate leads from repeated website visits.

**Enrichment blocking conditions (from `crm_iap_enrich`):**

```python
if (not lead.active or not lead.email_from or
    lead.email_state == 'incorrect' or
    lead.iap_enrich_done or
    lead.reveal_id or              # already revealed
    lead.probability == 100):      # already won
    lead.show_enrich_button = False
```

The `show_enrich_button` is only `True` when enrichment is still useful and credits won't be wasted.
