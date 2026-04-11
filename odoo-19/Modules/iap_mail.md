---
title: IAP Mail
description: Bridge between IAP and mail. Adds bus-based notifications for IAP events (no credit, success, error) and email alert tracking to iap.account.
tags: [odoo19, iap, mail, notification, module]
model_count: 1
models:
  - iap.account (adds mail.thread, notification bus)
dependencies:
  - iap
  - mail
category: Hidden/Tools
source: odoo/addons/iap_mail/
created: 2026-04-06
---

# IAP Mail

## Overview

**Module:** `iap_mail`
**Category:** Hidden/Tools
**Depends:** `iap`, `mail`
**Auto-install:** Yes
**License:** LGPL-3

Bridge between IAP and mail. Adds real-time notification capabilities to IAP accounts via the Odoo bus (WebSocket) and extends `iap.account` with `mail.thread` for tracking changes.

## Key Features

- Bus-based real-time notifications via Odoo's notification bus
- No-credit notification with direct link to credit purchase
- Success/error/status notifications
- Mail thread tracking on `iap.account` (chatter on account form)
- Field tracking for `company_ids`, `warning_threshold`, `warning_user_ids`

## Models

### iap.account (inherited)

Extends `iap.account` with `mail.thread` for activity tracking.

**Additional Fields (via inheritance):**
- `company_ids` — now tracked
- `warning_threshold` — now tracked
- `warning_user_ids` — now tracked

**Key Methods:**
- `_send_success_notification()` — sends a `success` type bus notification
- `_send_error_notification()` — sends a `danger` type bus notification
- `_send_status_notification()` — generic notification sender via `env.user._bus_send()` with type, message, and optional title
- `_send_no_credit_notification()` — sends a `no_credit` type notification with the IAP credit purchase URL

## Notification Types

| Type | Description | Payload |
|------|-------------|---------|
| `success` | Operation succeeded | `message`, `type: success`, optional `title` |
| `danger` / `error` | Operation failed | `message`, `type: danger`, optional `title` |
| `no_credit` | Insufficient credits | `title`, `type: no_credit`, `get_credits_url` |

## Frontend Integration

The bus notifications are consumed by the Odoo web frontend JavaScript (`static/src/js/*`) which displays them as toast notifications or banners in the UI.

## Mail Thread Tracking

Adding `mail.thread` to `iap.account` enables:
- Chatter on the IAP account form view
- Change tracking for `company_ids`, `warning_threshold`, `warning_user_ids`
- Message posting on account changes

## Source Files

- `models/iap_account.py` — inherits `iap.account`, adds bus notification methods
- `data/mail_templates.xml` — mail templates for IAP account communications
- `views/iap_views.xml` — form/list views for IAP accounts with chatter
- `static/src/js/` — frontend notification handlers
- `static/src/scss/` — styling for notification components
