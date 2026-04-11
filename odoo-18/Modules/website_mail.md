---
Module: website_mail
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_mail
---

## Overview

Thin connector module. Adds `mail` to the list of modules whose strings are translated on the frontend. Also marks the website publisher in the Odoo update telemetry.

**Key Dependencies:** `website`, `mail`

**Python Files:** 2 model files

---

## Models

### ir_http.py — IrHttp

**Inheritance:** `ir.http`

| Method | Description |
|--------|-------------|
| `_get_translation_frontend_modules_name()` | Adds `'mail'` to the list of modules included in frontend translation |

---

### update.py — PublisherWarrantyContract

**Inheritance:** `publisher_warranty.contract`

| Method | Description |
|--------|-------------|
| `_get_message()` | Adds `'website': True` to the publisher telemetry message |

---

## Critical Notes

- This module is extremely thin — it primarily provides data (views, controllers) and translation hooks
- The telemetry change (`'website': True`) marks that the installation has both website and mail modules
- No security files needed
- v17→v18: Minimal change from v17
