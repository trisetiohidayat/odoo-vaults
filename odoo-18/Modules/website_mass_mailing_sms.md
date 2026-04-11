---
Module: website_mass_mailing_sms
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_mass_mailing_sms
---

## Overview

Thin connector module enabling SMS marketing capabilities on mass mailing campaigns when sent from a website context. No Python models — relies entirely on data (IR model data) to link the SMS composer to mass mailing recipients.

**Key Dependencies:** `website_mass_mailing`, `sms`

**Python Files:** None (no models directory)

---

## Critical Notes

- No ORM models defined
- The `ir_model_data.xml` registers OdooBot SMS template references for mass mailing SMS campaigns
- Acts as a bridge between `mass_mailing` and `sms` modules for website-aware SMS sending
- v17→v18: Architecture unchanged
