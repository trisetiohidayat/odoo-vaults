---
title: POS Adyen
description: Integrates Adyen payment terminals with the Point of Sale. Handles terminal pairing, payment requests, tip adjustment, and asynchronous notification handling.
tags: [odoo19, pos, payment, adyen, module]
model_count: 3
models:
  - pos.payment.method (adyen fields, proxy method)
  - res.config.settings (adyen tip setting)
dependencies:
  - point_of_sale
category: Sales/Point of Sale
source: odoo/addons/pos_adyen/
created: 2026-04-06
---

# POS Adyen

## Overview

**Module:** `pos_adyen`
**Category:** Sales/Point of Sale
**Depends:** `point_of_sale`
**License:** LGPL-3

Integrates Adyen payment terminals with the Odoo Point of Sale. The module communicates with Adyen's Terminal API over the internet (not requiring a local HOP / terminal SDK). It handles payment initiation, HMAC-signed metadata injection, and asynchronous notification processing.

## Key Features

- Adyen terminal integration via Terminal API (cloud-based, no local SDK required)
- Payment request proxying through Odoo server (CORS workaround)
- HMAC-signed metadata injection into payment requests
- Test/live environment switching
- Terminal identifier uniqueness validation (per company)
- Tip adjustment after payment (via `set_tip_after_payment`)
- Asynchronous notification handling via `adyen_latest_response`
- Event URL auto-generation for terminal webhook configuration

## Models

### pos.payment.method (inherited)

| Field | Type | Description |
|-------|------|-------------|
| `adyen_api_key` | Char | Adyen API key for terminal requests (groups: `base.group_erp_manager`) |
| `adyen_terminal_identifier` | Char | Terminal ID in format `[Model]-[Serial]`, e.g., `P400Plus-123456789` |
| `adyen_test_mode` | Boolean | Run transactions in Adyen test environment |
| `adyen_latest_response` | Char | Buffer for latest async notification from Adyen (groups: `base.group_erp_manager`) |
| `adyen_event_url` | Char | Auto-generated webhook URL (`/pos_adyen/notification`), read-only |

**Key Methods:**
- `_get_payment_terminal_selection()` — adds `('adyen', 'Adyen')` to terminal options
- `_load_pos_data_fields()` — sends `adyen_terminal_identifier` to POS frontend
- `_check_adyen_terminal_identifier()` — validates uniqueness per company; raises `ValidationError` if duplicate
- `_get_adyen_endpoints()` — returns `{'terminal_request': 'https://terminal-api-{environment}.adyen.com/async'}`
- `_is_write_forbidden()` — allows write to `adyen_latest_response` even when other fields are locked
- `get_latest_adyen_status()` — returns the buffered latest response JSON
- `proxy_adyen_request()` — main RPC proxy for all Adyen requests (CORS workaround); validates request structure, injects HMAC metadata, routes to `_proxy_adyen_request_direct()`
- `_is_valid_adyen_request_data()` — validates request structure against expected schema
- `_get_expected_message_header()` — builds expected message header for a given message category
- `_get_expected_payment_request()` — builds expected payment request structure (with/without acquirer data)
- `_get_valid_acquirer_data()` — returns allowed acquirer data keys: `tenderOption: AskGratuity`, `authorisationType: PreAuth`
- `_get_hmac()` — computes HMAC signature using `pos_adyen_payment` scope
- `_proxy_adyen_request_direct()` — makes the actual HTTP request to Adyen Terminal API; returns JSON or `True` for "ok" response; returns error dict for 401

### res.config.settings (inherited)

| Field | Type | Description |
|-------|------|-------------|
| `pos_adyen_ask_customer_for_tip` | Boolean | Ask customer for tip on Adyen terminal (linked to `pos_iface_tipproduct`) |

## Request Flow

1. POS frontend sends payment request to Odoo server via `proxy_adyen_request()`
2. Odoo validates request structure (prevents injection)
3. Odoo injects HMAC-signed metadata
4. Odoo proxies request to Adyen Terminal API
5. Adyen processes payment on terminal
6. Adyen sends async notification to Odoo's `/pos_adyen/notification` endpoint
7. Odoo stores response in `adyen_latest_response` on the payment method
8. POS polls `get_latest_adyen_status()` to retrieve result

## HMAC Security

The `_get_hmac()` method signs terminal requests with a database-level HMAC key scoped to `pos_adyen_payment`. This prevents tampering with `SaleID`, `ServiceID`, `POIID`, and `TransactionID` in flight.

## Tip After Payment

When `set_tip_after_payment` is enabled on the POS config and `pos_iface_tipproduct` is active, Adyen supports adjusting the payment amount post-authorization. The `pos_adyen_ask_customer_for_tip` setting controls whether the terminal prompts the customer for a tip.

## Source Files

- `models/pos_payment_method.py` — Adyen terminal integration, proxy method, HMAC signing
- `models/res_config_settings.py` — tip-asking settings field
