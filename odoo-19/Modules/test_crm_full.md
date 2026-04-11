# Test Full CRM Flow (`test_crm_full`)

**Category:** Hidden/Tests
**Depends:** `crm`, `crm_iap_enrich`, `crm_iap_mine`, `crm_sms`, `event_crm`, `sale_crm`, `website_crm`, `website_crm_iap_reveal`, `website_crm_partner_assign`, `website_crm_livechat`
**Author:** Odoo S.A.
**License:** LGPL-3

## Overview

End-to-end integration test for the full CRM flow. Installs CRM and all its IAP/external service bridge modules to test complete business flows including lead enrichment, lead mining, SMS notifications, event registration leads, sale orders from CRM, website lead capture, partner geo-assignment, and livechat-to-lead conversion.

## Dependencies

| Module | Purpose |
|--------|---------|
| `crm` | Core CRM |
| `crm_iap_enrich` | Automatic lead enrichment via IAP |
| `crm_iap_mine` | Lead mining/search via IAP |
| `crm_sms` | SMS notifications from CRM |
| `event_crm` | Event registration to lead |
| `sale_crm` | Sale order to opportunity |
| `website_crm` | Website form to lead |
| `website_crm_iap_reveal` | Reveal anonymous website visitors into leads |
| `website_crm_partner_assign` | Geo-based partner assignment |
| `website_crm_livechat` | Livechat visitor to lead |

## Models

This module has no Python models. It serves as a meta-package that installs all CRM sub-modules simultaneously, enabling full-stack tests without modifying individual modules.
