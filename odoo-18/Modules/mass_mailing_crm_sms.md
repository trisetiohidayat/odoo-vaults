---
Module: mass_mailing_crm_sms
Version: 18.0.0
Type: addon
Tags: #odoo18 #mass_mailing #crm #sms
---

## Overview

Bridges `mass_mailing` CRM integration with SMS support. Adds `crm_lead_count` as a winner selection criterion for SMS A/B testing campaigns.

**Depends:** `mass_mailing_sms`, `crm`, `mass_mailing`

**Key Behavior:** Extends `utm.campaign.ab_testing_sms_winner_selection` with CRM lead count metric for SMS campaign optimization.

---

## Models

### `utm.campaign` (Inherited)

**Inherited from:** `utm.campaign`

Extends the A/B testing winner selection to include CRM lead metrics.

| Field | Type | Note |
|-------|------|------|
| `ab_testing_sms_winner_selection` | Selection | Adds `'crm_lead_count'` to SMS winner criteria |

**Added Selection Values:**
- `'crm_lead_count'` — Leads generated
