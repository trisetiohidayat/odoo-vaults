---
type: module
module: crm_iap_enrich
tags: [odoo, odoo19, crm, iap, enrichment, lead]
created: 2026-04-06
---

# CRM IAP Enrich

## Overview
| Property | Value |
|----------|-------|
| **Name** | Lead Enrichment |
| **Technical** | `crm_iap_enrich` |
| **License** | LGPL-3 |
| **Author** | Odoo S.A. |

## Description
Enriches CRM leads and opportunities automatically using the IAP (In-App Purchase) service based on email domain. Fills in missing company data (name, address, phone, city, zip, country) from the lead's email domain.

## Dependencies
- `iap_crm`
- `iap_mail`

## Models

### crm.lead
Inherits `crm.lead`. Extends lead with IAP enrichment tracking.

**Fields:**
- `iap_enrich_done` (Boolean) — Whether IAP enrichment has been performed on this lead
- `show_enrich_button` (Boolean, computed) — Whether manual enrichment button should be shown

**Key Methods:**
- `iap_enrich()` — Handles both cron and manual enrichment triggers; calls `_iap_enrich_from_response()`
- `_iap_enrich_from_response()` — Fills in: `name`, `clearbit_id`/`reveal_id`, `street`, `city`, `zip`, `phone` (first from response), `country_id`, `state_id` (from codes); posts a mail message with enriched data
- `_merge_get_fields_specific()` — Ensures `iap_enrich_done` is properly merged when leads are merged (True if any merged lead was enriched)

## Key Features

### Automatic Enrichment
- Cron job (`ir_cron_lead_enrichment`) runs every 24 hours (configurable)
- Enriches leads created in the last 24 hours that have an email address but no existing enrichment
- Uses `iap.enrich.api._request_enrich()` to fetch company data from email domain
- Skips generic email providers (gmail.com, hotmail.com, etc.)
- Batched processing (50 leads per batch) with credit management

### Manual Enrichment
- `show_enrich_button` computed based on: active lead, has email, not already enriched, not already revealed, not 100% probability
- User can trigger enrichment manually via button

## Configuration
- Setting: `crm.iap.lead.enrich.setting` — controls auto-enrichment on lead creation (`auto`, `manual`)
- Credits consumed via IAP `reveal` service

## Related
- [Modules/iap_crm](modules/iap_crm.md) — IAP CRM base
- [Modules/crm_iap_mine](modules/crm_iap_mine.md) — Lead mining
