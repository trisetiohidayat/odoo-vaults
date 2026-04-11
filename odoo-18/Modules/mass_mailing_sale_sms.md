---
Module: mass_mailing_sale_sms
Version: 18.0.0
Type: addon
Tags: #odoo18 #mass_mailing #sale #sms
---

## Overview

Bridges `mass_mailing` sale (quotation) tracking with SMS support. Adds sale-specific SMS A/B testing winner selection criteria to `utm.campaign`.

**Depends:** `mass_mailing_sms`, `sale`, `mass_mailing`

**Key Behavior:** Extends `ab_testing_sms_winner_selection` with `'sale_quotation_count'` and `'sale_invoiced_amount'`.

---

## Models

### `utm.campaign` (Inherited)

**Inherited from:** `utm.campaign`

| Field | Type | Note |
|-------|------|------|
| `ab_testing_sms_winner_selection` | Selection | Adds sale metrics to SMS winner criteria |

**Added Selection Values:**
- `'sale_quotation_count'` — Quotations sent
- `'sale_invoiced_amount'` — Revenues invoiced
