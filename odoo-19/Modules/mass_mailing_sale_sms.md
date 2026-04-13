# Mass Mailing Sale SMS

## Overview
- **Name:** Mass mailing SMS on sale orders
- **Category:** Marketing/Email Marketing
- **Summary:** Add sale order info on mass mailing SMS
- **Version:** 1.0
- **Depends:** `mass_mailing_sale`, `mass_mailing_sms`
- **Auto-install:** True
- **License:** LGPL-3

## Description
Extends `mass_mailing_sale` to support SMS campaigns for sale order customers. Combines sale order targeting with SMS mailing capabilities.

## Models

### `utm.campaign` (extends `utm.campaign`)
| Field | Type | Description |
|-------|------|-------------|
| `ab_testing_sms_winner_selection` | Selection | Adds `sale_quotation_count` and `sale_invoiced_amount` options for SMS A/B testing winner selection |

## Related
- [Modules/mass_mailing_sale](Modules/mass_mailing_sale.md) - Sale mass mailing
- [Modules/mass_mailing_sms](Modules/mass_mailing_sms.md) - SMS marketing
- [Modules/Sale](Modules/Sale.md) - Sales module
