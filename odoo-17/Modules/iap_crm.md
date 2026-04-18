---
tags: [odoo, odoo17, module, iap, crm, reveal-id]
research_depth: medium
---

# IAP CRM — Reveal ID Tracking

**Source:** `addons/iap_crm/models/`

## Overview

Minimal extension to `crm.lead` that adds a `reveal_id` field — the technical identifier returned by the IAP `reveal` service during lead enrichment. This allows Odoo to track which leads have been processed through the enrichment API and prevent duplicate enrichment attempts.

## Key Model

### crm.lead — Reveal ID Extension

**File:** `crm_lead.py`

| Field | Type | Description |
|-------|------|-------------|
| `reveal_id` | Char | Technical ID of the reveal/IAP enrichment request |

**Purpose:** When a lead is enriched via `crm_iap_enrich`, the Clearbit service returns a `clearbit_id`. This is stored in `reveal_id`. The `crm_iap_enrich` module uses this field to:
1. Skip already-enriched leads in the enrichment cron and manual flow
2. Correlate IAP API responses back to the correct lead

**Lead Merge:** `_merge_get_fields()` includes `reveal_id` so that when leads are merged, the `reveal_id` is preserved in the resulting record.

## See Also

- [Modules/crm_iap_enrich](Modules/crm_iap_enrich.md) — lead enrichment via IAP Clearbit
- [Modules/crm](Modules/crm.md) — CRM lead model