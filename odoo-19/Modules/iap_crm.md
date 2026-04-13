# IAP CRM

## Overview

- **Category**: Hidden/Tools
- **Depends**: `crm`, `iap_mail`
- **License**: LGPL-3
- **Auto-install**: Yes

Bridge module between [Modules/iap](odoo-18/Modules/iap.md) and [Modules/CRM](odoo-18/Modules/CRM.md). Provides integration between IAP-based services (like lead enrichment and reveal) and the CRM pipeline.

## Models

### `crm.lead` (Extended)

| Field | Type | Description |
|-------|------|-------------|
| `reveal_id` | Char | Technical ID of the IAP reveal request. Indexed `btree_not_null`. Used to track which IAP service revealed this lead's company data. |

| Method | Description |
|--------|-------------|
| `_merge_get_fields()` | Adds `reveal_id` to the list of fields preserved during lead merging. |

## What It Does

This is a thin bridge module. The `reveal_id` field allows Odoo to track which IAP reveal request populated a given lead, which is useful for:
- Auditing which IAP service enriched a lead.
- Correlating with IAP service logs.
- Avoiding duplicate enrichment requests.

The actual IAP reveal/enrichment logic lives in `crm_iap_enrich` and other CRM+IAP modules that call into IAP services.

## Related

- [Modules/CRM](odoo-18/Modules/CRM.md) — CRM pipeline and lead/opportunity management.
- [Modules/iap_mail](odoo-17/Modules/iap_mail.md) — IAP bus notifications and mail.thread on IAP accounts.
- [Modules/crm_iap_enrich](odoo-17/Modules/crm_iap_enrich.md) — IAP lead enrichment (company data enrichment).
- [Modules/crm_iap_mine](odoo-18/Modules/crm_iap_mine.md) — IAP lead mining.
- [Modules/partner_autocomplete](odoo-18/Modules/partner_autocomplete.md) — Company data autocomplete via IAP.
