---
Module: website_event_jitsi
Version: 18.0.0
Type: addon
Tags: #odoo18 #website_event_jitsi
---

## Overview

Provides Cloudflare Turnstile anti-bot configuration for website forms. Replaces Google reCAPTCHA (removed in v18). Uses Cloudflare's privacy-friendly Turnstile challenge system integrated into the `ir.http` verification pipeline.

**Key Dependencies:** `website`

**Python Files:** 2 model files

---

## Models

### res_config_settings.py — ResConfigSettings

**Inheritance:** `res.config.settings`

| Field | Type | Config Parameter | Notes |
|-------|------|-----------------|-------|
| `jitsi_server_domain` | Char | `website_jitsi.jitsi_server_domain` | Default: `'meet.jit.si'` |

---

## Critical Notes

- The `jitsi_server_domain` config parameter (`website_jitsi.jitsi_server_domain`) is read by the `chat.room` model's `_compute_jitsi_server_domain()` method
- The actual Jitsi integration lives in the `website_jitsi` module (separate from `website_event_jitsi`); `website_event_jitsi` is a thin connector module that only provides config settings
- In v18, Google reCAPTCHA was removed and replaced by Cloudflare Turnstile across the codebase
