# Mass Mailing CRM SMS

## Overview
- **Name:** Mass mailing SMS on lead / opportunities
- **Category:** Marketing/Email Marketing
- **Summary:** Add lead/opportunities info on mass mailing SMS
- **Version:** 1.0
- **Depends:** `mass_mailing_crm`, `mass_mailing_sms`
- **Auto-install:** True
- **License:** LGPL-3

## Description
Extends `mass_mailing_crm` to add CRM leads/opportunities as targets for SMS campaigns. Combines the CRM lead targeting with the SMS mailing capabilities.

## Models

### `utm.campaign` (extends `utm.campaign`)
| Field | Type | Description |
|-------|------|-------------|
| `ab_testing_sms_winner_selection` | Selection | Adds `crm_lead_count` option for SMS A/B testing winner selection |

## Related
- [Modules/mass_mailing_crm](mass_mailing_crm.md) - CRM mass mailing
- [Modules/mass_mailing_sms](mass_mailing_sms.md) - SMS marketing
- [Modules/CRM](CRM.md) - CRM module
